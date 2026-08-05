"""CFF2 variable-font punctuation, kana-mark, and joining-symbol generation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import pathops
from fontTools.cffLib import TopDict
from fontTools.misc.bezierTools import solveCubic, splitCubicAtT
from fontTools.misc.fixedTools import floatToFixedToFloat
from fontTools.otlLib.builder import (
    buildLigatureSubstSubtable,
    buildLookup,
    buildSingleSubstSubtable,
)
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.pens.recordingPen import RecordingPen, replayRecording
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.varLib.cff import CFF2CharStringMergePen
from fontTools.varLib.models import normalizeValue, piecewiseLinearMap

from . import geometry
from .features import (
    compact_auxiliary_single_substitutions,
    consolidate_vrt2_lookups,
    merge_features,
    punctuation_feature_source,
    symbol_feature_source,
)
from .marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    CHOON_DAKUTEN_PUA,
    HEART_DAKUTEN_MARK_TRANSFORMS,
    KOBURI_HEART_BASE_PUA,
    KOBURI_HEART_MARK_PAIRS,
    KOBURI_HEART_OUTPUT_PUA,
    KOBURI_PUA_MARK_PAIRS,
    KOBURI_PUA_START,
    MANGA_MARK_PAIRS,
    MANGA_MISSING_SMALL_KANA,
    PUNCTUATION_MARK_PAIRS,
    MarkPair,
    MarkPositionMap,
    load_mark_position_overrides,
    load_punctuation_mark_positions,
)
from .metadata import set_japanese_name, set_name
from .operations import (
    add_unicode_mapping,
    allocate_cid_names,
    feature_ligatures,
    feature_single_substitutions,
    remove_repeated_ligatures,
    vertical_glyph_or_self,
)
from .pipeline import (
    CONNECTED_STROKE_REFERENCE_CODEPOINTS,
    OVERLAP,
    LINEAR_WAVE_TRANSITION_GLYPH_COUNT,
    LINEAR_MANGA_TRANSITION_GLYPH_COUNT,
    MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT,
    WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT,
    MANGA_WAVE_GLYPH_COUNT,
    NEW_GLYPH_COUNT,
    ONE_CYCLE_WAVE_GLYPH_COUNT,
    RELAXED_WAVE_GLYPH_COUNT,
    WAVE_GLYPH_COUNT,
    connected_stroke_widths,
    flatten_horizontal_centerline,
    make_horizontal_parts,
    make_linear_wave_transition_parts,
    make_linear_manga_transition_parts,
    make_manga_wave_parts,
    make_manga_to_wave_transition_parts,
    make_wave_to_manga_transition_parts,
    make_one_cycle_wave_parts,
    make_relaxed_wave_parts,
    make_vertical_parts,
    make_wave_parts,
    make_wave_stroke_model,
    normalize_linear_stroke_width,
)
from .profiles import (
    NOTO_WEIGHT_CLASSES,
    SHIPPORI_STROKE_ADJUSTMENTS,
)
from .punctuation import (
    MANGA_PUNCTUATION_SEQUENCES,
    PUNCTUATION_VARIANT_SEQUENCES,
    make_original_punctuation_ligature,
    make_variable_shippori_punctuation_ligature,
    rotate_punctuation_outline,
)
from .version import VERSION, VERSION_NUMBER

_STYLES = tuple(NOTO_WEIGHT_CLASSES.items())
_WEIGHTS = tuple(value for _, value in _STYLES)
_SPACING = {0x3099: 0x309B, 0x309A: 0x309C}
_SYMBOL_VERTICAL_ORIGIN = 880


def _scalar(x: float, support: tuple[float, float, float]) -> float:
    start, peak, end = support
    if x <= start or x >= end:
        return 0.0
    if x == peak:
        return 1.0
    return (x - start) / (peak - start) if x < peak else (end - x) / (end - peak)


def _inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    rows = [
        [*row, *(1.0 if i == j else 0.0 for j in range(n))]
        for i, row in enumerate(matrix)
    ]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(rows[row][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ValueError("Reviewed weight regions are not independent")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for row in range(n):
            if row != col:
                factor = rows[row][col]
                rows[row] = [
                    v - factor * p for v, p in zip(rows[row], rows[col], strict=True)
                ]
    return [row[n:] for row in rows]


class _DeltaModel:
    def __init__(
        self, locations: Sequence[float], supports: Sequence[tuple[float, float, float]]
    ) -> None:
        self.locations = tuple(locations)
        self.inverse = _inverse(
            [[_scalar(x, support) for support in supports] for x in locations[1:-1]]
        )

    def getDeltas(self, values: Sequence[float], *, round) -> list[float]:
        default, endpoint = values[0], values[-1] - values[0]
        residuals = [
            v - default - endpoint * x
            for v, x in zip(values[1:-1], self.locations[1:-1], strict=True)
        ]
        interior = [
            sum(c * r for c, r in zip(row, residuals, strict=True))
            for row in self.inverse
        ]
        return [round(default), round(endpoint), *(round(v) for v in interior)]


def _validate(font: TTFont) -> tuple[TopDict, list[float]]:
    if "CFF2" not in font or "glyf" in font or "fvar" not in font:
        raise ValueError("Variable marks require a CFF2 OpenType variable source")
    axes = font["fvar"].axes
    if len(axes) != 1 or axes[0].axisTag != "wght":
        raise ValueError("Variable marks require exactly one wght axis")
    axis = axes[0]
    expected, actual = (
        (_WEIGHTS[0], _WEIGHTS[0], _WEIGHTS[-1]),
        (axis.minValue, axis.defaultValue, axis.maxValue),
    )
    if actual != expected:
        raise ValueError(
            f"Variable marks require wght min/default/max {expected}, got {actual}"
        )
    if "avar" not in font or "wght" not in font["avar"].segments:
        raise ValueError("Variable marks require the source wght avar mapping")
    if not all(tag in font for tag in ("GSUB", "HVAR", "VVAR", "vmtx")):
        raise ValueError("Variable marks require GSUB, HVAR, VVAR, and vmtx tables")
    top = font["CFF2"].cff.topDictIndex[0]
    if not all(
        hasattr(top, n) for n in ("CharStrings", "FDArray", "FDSelect", "VarStore")
    ):
        raise ValueError(
            "Variable marks require CFF2 CharStrings, FDArray, FDSelect, and VarStore"
        )
    if font["head"].unitsPerEm != 1000:
        raise ValueError("Variable marks require a 1000 units-per-em source")
    triple, mapping = (
        (axis.minValue, axis.defaultValue, axis.maxValue),
        font["avar"].segments["wght"],
    )
    locations = [
        floatToFixedToFloat(piecewiseLinearMap(normalizeValue(w, triple), mapping), 14)
        for w in _WEIGHTS
    ]
    if (
        locations[0] != 0
        or locations[-1] != 1
        or any(a >= b for a, b in pairwise(locations))
    ):
        raise ValueError("The source wght normalization must increase from 0 to 1")
    return top, locations


def _paths(font: TTFont, names: Sequence[str]) -> dict[int, dict[str, pathops.Path]]:
    result = {}
    for weight in _WEIGHTS:
        glyph_set, result[weight] = font.getGlyphSet(location={"wght": weight}), {}
        for name in names:
            path = pathops.Path()
            glyph_set[name].draw(DecomposingFilterPen(path.getPen(), glyph_set))
            result[weight][name] = path
    return result


def _append_var_data(
    top: TopDict, locations: Sequence[float]
) -> tuple[int, _DeltaModel]:
    wrapper, store = top.VarStore, top.VarStore.otVarStore
    regions = store.VarRegionList.Region
    global_index = next(
        (
            i
            for i, r in enumerate(regions)
            if len(r.VarRegionAxis) == 1
            and (
                r.VarRegionAxis[0].StartCoord,
                r.VarRegionAxis[0].PeakCoord,
                r.VarRegionAxis[0].EndCoord,
            )
            == (0.0, 1.0, 1.0)
        ),
        None,
    )
    if global_index is None:
        region, axis = otTables.VarRegion(), otTables.VarRegionAxis()
        axis.StartCoord, axis.PeakCoord, axis.EndCoord = 0.0, 1.0, 1.0
        region.VarRegionAxis = [axis]
        global_index = len(regions)
        regions.append(region)
    supports = [(locations[i - 1], locations[i], locations[i + 1]) for i in range(1, 6)]
    interior = []
    for start, peak, end in supports:
        region, axis = otTables.VarRegion(), otTables.VarRegionAxis()
        axis.StartCoord, axis.PeakCoord, axis.EndCoord = start, peak, end
        region.VarRegionAxis = [axis]
        interior.append(len(regions))
        regions.append(region)
    store.VarRegionList.RegionCount = len(regions)
    data = otTables.VarData()
    data.ItemCount, data.NumShorts, data.Item = 0, 0, []
    data.VarRegionIndex = [global_index, *interior]
    data.VarRegionCount = len(data.VarRegionIndex)
    vsindex = len(store.VarData)
    store.VarData.append(data)
    store.VarDataCount = len(store.VarData)
    wrapper.data = None
    return vsindex, _DeltaModel(locations, supports)


def _charstring(
    name: str,
    outlines: Sequence[pathops.Path],
    private,
    global_subrs,
    model: _DeltaModel,
    vsindex: int,
):
    commands = []
    pen = CFF2CharStringMergePen(commands, name, len(outlines), 0)
    outlines[0].draw(pen)
    for index, outline in enumerate(outlines[1:], 1):
        pen.restart(index)
        outline.draw(pen)
    cs = pen.getCharString(
        private=private, globalSubrs=global_subrs, var_model=model, optimize=True
    )
    if "blend" in cs.program:
        cs.program[:0] = [vsindex, "vsindex"]
    return cs


def _append_glyphs(
    font: TTFont,
    top: TopDict,
    glyphs,
    model: _DeltaModel,
    vsindex: int,
    metric_source: str,
    vertical_origin: int = 880,
) -> None:
    fd_index = top.FDSelect[font.getGlyphID(metric_source)]
    private = top.FDArray[fd_index].Private
    advance, vertical_advance = (
        font["hmtx"].metrics[metric_source][0],
        font["vmtx"].metrics[metric_source][0],
    )
    if (advance, vertical_advance) != (1000, 1000):
        raise ValueError("Variable marks require full-width 1000-unit kana metrics")
    names = []
    for name, outlines in glyphs:
        cs = _charstring(
            name, outlines, private, font["CFF2"].cff.GlobalSubrs, model, vsindex
        )
        top.CharStrings.charStrings[name] = len(top.CharStrings.charStringsIndex)
        top.CharStrings.charStringsIndex.append(cs)
        top.FDSelect.gidArray.append(fd_index)
        x_min, _, _, y_max = outlines[0].bounds
        font["hmtx"].metrics[name] = (advance, math.floor(x_min))
        font["vmtx"].metrics[name] = (
            vertical_advance,
            math.floor(vertical_origin - y_max),
        )
        names.append(name)
    order = [*font.getGlyphOrder(), *names]
    font.setGlyphOrder(order)
    top.charset, top.numGlyphs = order, len(order)
    font["maxp"].numGlyphs = len(order)
    for tag in ("HVAR", "VVAR"):
        for attribute, varmap in vars(font[tag].table).items():
            if attribute.endswith("Map") and varmap is not None:
                for name in names:
                    varmap.mapping[name] = otTables.NO_VARIATION_INDEX


def _replace_var_glyph(
    font: TTFont,
    top: TopDict,
    name: str,
    outlines: Sequence[pathops.Path],
    vertical_origin: int,
    model: _DeltaModel,
    vsindex: int,
) -> None:
    glyph_id = font.getGlyphID(name)
    fd_index = top.FDSelect[glyph_id]
    charstring = _charstring(
        name,
        outlines,
        top.FDArray[fd_index].Private,
        font["CFF2"].cff.GlobalSubrs,
        model,
        vsindex,
    )
    index = top.CharStrings.charStrings[name]
    top.CharStrings.charStringsIndex[index] = charstring
    x_min, _, _, y_max = outlines[0].bounds
    advance = font["hmtx"].metrics[name][0]
    vertical_advance = font["vmtx"].metrics[name][0]
    font["hmtx"].metrics[name] = (advance, math.floor(x_min))
    font["vmtx"].metrics[name] = (
        vertical_advance,
        math.floor(vertical_origin - y_max),
    )


@dataclass(frozen=True)
class _ContourSegment:
    start: tuple[float, float]
    controls: tuple[tuple[float, float], ...]
    end: tuple[float, float]

    def split(self, t: float) -> tuple[_ContourSegment, _ContourSegment]:
        if not self.controls:
            point = (
                self.start[0] + (self.end[0] - self.start[0]) * t,
                self.start[1] + (self.end[1] - self.start[1]) * t,
            )
            return (
                _ContourSegment(self.start, (), point),
                _ContourSegment(point, (), self.end),
            )
        left, right = splitCubicAtT(self.start, *self.controls, self.end, t)
        return (
            _ContourSegment(left[0], tuple(left[1:3]), left[3]),
            _ContourSegment(right[0], tuple(right[1:3]), right[3]),
        )

    def draw(self, pen) -> None:
        if self.controls:
            pen.curveTo(*self.controls, self.end)
        else:
            pen.lineTo(self.end)


def _contour_segments(source: pathops.Path) -> list[_ContourSegment]:
    recording = RecordingPen()
    source.draw(recording)
    segments = []
    contour_start = None
    current = None
    closed = False
    for operation, points in recording.value:
        if operation == "moveTo":
            if contour_start is not None:
                raise ValueError("The variable choon source must have one contour")
            contour_start = current = points[0]
        elif operation == "lineTo":
            if current is None:
                raise ValueError("The variable choon source has no contour start")
            segments.append(_ContourSegment(current, (), points[0]))
            current = points[0]
        elif operation == "curveTo":
            if current is None or len(points) != 3:
                raise ValueError("The variable choon source must use cubic curves")
            segments.append(_ContourSegment(current, tuple(points[:2]), points[2]))
            current = points[2]
        elif operation == "closePath":
            if current is None or contour_start is None:
                raise ValueError("The variable choon source has no contour start")
            if current != contour_start:
                segments.append(_ContourSegment(current, (), contour_start))
            closed = True
        else:
            raise ValueError(
                f"Unsupported variable choon contour operation: {operation}"
            )
    if not closed or not segments:
        raise ValueError("The variable choon source must be a closed contour")
    return segments


def _segment_crossings(
    segment: _ContourSegment, coordinate: int, seam: float
) -> list[float]:
    if not segment.controls:
        distance = segment.end[coordinate] - segment.start[coordinate]
        roots = [] if distance == 0 else [(seam - segment.start[coordinate]) / distance]
    else:
        p0 = segment.start[coordinate]
        p1 = segment.controls[0][coordinate]
        p2 = segment.controls[1][coordinate]
        p3 = segment.end[coordinate]
        roots = solveCubic(
            -p0 + 3 * p1 - 3 * p2 + p3,
            3 * p0 - 6 * p1 + 3 * p2,
            -3 * p0 + 3 * p1,
            p0 - seam,
        )
    result = []
    for root in roots:
        try:
            t = float(root)
        except (TypeError, ValueError):
            continue
        if math.isfinite(t) and 1e-9 < t < 1 - 1e-9:
            result.append(t)
    return result


def _cap_between(
    segments: Sequence[_ContourSegment],
    start_crossing: tuple[int, float],
    end_crossing: tuple[int, float],
    coordinate: int,
    seam: float,
) -> pathops.Path:
    start_index, start_t = start_crossing
    end_index, end_t = end_crossing
    if start_index == end_index:
        raise ValueError("The variable choon crossings must use separate segments")
    _, first = segments[start_index].split(start_t)
    last, _ = segments[end_index].split(end_t)

    def snap(point: tuple[float, float]) -> tuple[float, float]:
        values = list(point)
        values[coordinate] = seam
        return values[0], values[1]

    first = _ContourSegment(snap(first.start), first.controls, first.end)
    last = _ContourSegment(last.start, last.controls, snap(last.end))
    result = pathops.Path()
    pen = result.getPen()
    pen.moveTo(first.start)
    first.draw(pen)
    index = (start_index + 1) % len(segments)
    while index != end_index:
        segments[index].draw(pen)
        index = (index + 1) % len(segments)
    last.draw(pen)
    pen.closePath()
    return result


def _split_caps(
    source: pathops.Path, axis: str, seam: float
) -> tuple[pathops.Path, pathops.Path]:
    coordinate = 0 if axis == "horizontal" else 1
    segments = _contour_segments(source)
    crossings = sorted(
        (index, t)
        for index, segment in enumerate(segments)
        for t in _segment_crossings(segment, coordinate, seam)
    )
    if len(crossings) != 2:
        raise ValueError(f"The variable choon must cross its {axis} seam exactly twice")
    first = _cap_between(segments, crossings[0], crossings[1], coordinate, seam)
    second = _cap_between(segments, crossings[1], crossings[0], coordinate, seam)

    def side(outline: pathops.Path) -> str | None:
        low, high = (
            (outline.bounds[0], outline.bounds[2])
            if coordinate == 0
            else (outline.bounds[1], outline.bounds[3])
        )
        if high <= seam + 0.01:
            return "low"
        if low >= seam - 0.01:
            return "high"
        return None

    first_side, second_side = side(first), side(second)
    if (first_side, second_side) == ("low", "high"):
        return first, second
    if (first_side, second_side) == ("high", "low"):
        return second, first
    raise ValueError(f"The variable choon {axis} caps overlap their seam")


def _overlaid_path(*outlines: pathops.Path) -> pathops.Path:
    result = pathops.Path()
    pen = result.getPen()
    for outline in outlines:
        outline.draw(pen)
    return result


def _cap_cut_span(outline: pathops.Path, axis: str) -> tuple[float, float]:
    recording = RecordingPen()
    outline.draw(recording)
    start = next(
        points[0] for operation, points in recording.value if operation == "moveTo"
    )
    end = next(
        points[-1]
        for operation, points in reversed(recording.value)
        if operation in {"lineTo", "curveTo"}
    )
    coordinate = 1 if axis == "horizontal" else 0
    return tuple(sorted((start[coordinate], end[coordinate])))


def _split_horizontal_parts(
    outline: pathops.Path, advance: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance / 2
    start_cap, end_cap = _split_caps(outline, "horizontal", seam)
    y_min, y_max = _cap_cut_span(start_cap, "horizontal")
    start_bar = geometry.rectangle(seam, y_min, advance + OVERLAP, y_max)
    middle = geometry.rectangle(-OVERLAP, y_min, advance + OVERLAP, y_max)
    end_bar = geometry.rectangle(-OVERLAP, y_min, seam, y_max)
    return (
        _overlaid_path(start_cap, start_bar),
        middle,
        _overlaid_path(end_bar, end_cap),
    )


def _split_vertical_parts(
    outline: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance * 0.4
    bottom_cap, top_cap = _split_caps(outline, "vertical", seam)
    x_min, x_max = _cap_cut_span(bottom_cap, "vertical")
    cell_top = vertical_origin
    cell_bottom = vertical_origin - advance
    start_bar = geometry.rectangle(x_min, cell_bottom - OVERLAP, x_max, seam)
    middle = geometry.rectangle(x_min, cell_bottom - OVERLAP, x_max, cell_top + OVERLAP)
    end_bar = geometry.rectangle(x_min, seam, x_max, cell_top + OVERLAP)
    return (
        _overlaid_path(top_cap, start_bar),
        middle,
        _overlaid_path(end_bar, bottom_cap),
    )


def _pad_degenerate_curves(
    outline: pathops.Path, count: int, *, at_start: bool
) -> pathops.Path:
    if count == 0:
        return outline
    recording = RecordingPen()
    outline.draw(recording)
    commands = list(recording.value)
    if at_start:
        index = next(
            i for i, (operation, _) in enumerate(commands) if operation == "moveTo"
        )
        point = commands[index][1][0]
        insert_at = index + 1
    else:
        insert_at = max(
            i for i, (operation, _) in enumerate(commands) if operation == "closePath"
        )
        point = commands[insert_at - 1][1][-1]
    commands[insert_at:insert_at] = [
        ("curveTo", (point, point, point)) for _ in range(count)
    ]
    result = pathops.Path()
    replayRecording(commands, result.getPen())
    return result


def _normalize_cubic_contours(
    outlines: Sequence[pathops.Path],
) -> list[pathops.Path]:
    contour_counts: list[list[int]] = []
    for outline in outlines:
        counts: list[int] = []
        for verb, _ in outline:
            if verb == pathops.PathVerb.MOVE:
                counts.append(0)
            elif verb == pathops.PathVerb.CUBIC:
                counts[-1] += 1
            elif verb != pathops.PathVerb.CLOSE:
                raise ValueError(
                    f"Spliced variable transition contains unsupported {verb!r}"
                )
        contour_counts.append(counts)
    if len({len(counts) for counts in contour_counts}) != 1:
        raise ValueError("Spliced variable transition contour counts do not match")
    maximums = [
        max(counts[index] for counts in contour_counts)
        for index in range(len(contour_counts[0]))
    ]

    normalized = []
    for outline, counts in zip(outlines, contour_counts, strict=True):
        result = pathops.Path()
        pen = result.getPen()
        contour_index = -1
        current = None
        for verb, points in outline:
            if verb == pathops.PathVerb.MOVE:
                contour_index += 1
                current = points[0]
                pen.moveTo(current)
            elif verb == pathops.PathVerb.CUBIC:
                pen.curveTo(*points)
                current = points[-1]
            else:
                if current is None:
                    raise ValueError("Spliced transition contour has no points")
                for _ in range(maximums[contour_index] - counts[contour_index]):
                    pen.curveTo(current, current, current)
                pen.closePath()
        normalized.append(result)
    return normalized


def _normalize_spliced_transition_masters(
    masters: Sequence[tuple[pathops.Path, ...]],
) -> list[tuple[pathops.Path, ...]]:
    normalized = [list(master) for master in masters]
    half_count = len(normalized[0]) // 2
    indices = tuple(index for index in range(half_count) if index != 2)
    for index in (*indices, *(index + half_count for index in indices)):
        outlines = _normalize_cubic_contours([master[index] for master in normalized])
        for master, outline in zip(normalized, outlines, strict=True):
            master[index] = outline
    return [tuple(master) for master in normalized]


def _normalize_vertical_parts(
    masters: Sequence[tuple[pathops.Path, pathops.Path, pathops.Path]],
) -> list[tuple[pathops.Path, pathops.Path, pathops.Path]]:
    # At y=400 the Black master crosses the next source curve. Degenerate
    # cubics preserve each exact cap while equalizing the CFF2 command topology.
    start_count = max(len(parts[0].verbs) for parts in masters)
    end_count = max(len(parts[2].verbs) for parts in masters)
    return [
        (
            _pad_degenerate_curves(
                start,
                start_count - len(start.verbs),
                at_start=True,
            ),
            middle,
            _pad_degenerate_curves(
                end,
                end_count - len(end.verbs),
                at_start=False,
            ),
        )
        for start, middle, end in masters
    ]


def _named_master_outlines(names: Sequence[str], masters):
    return [
        (
            name,
            [master[index] for master in masters],
        )
        for index, name in enumerate(names)
    ]


def _append_symbols(
    font: TTFont,
    top: TopDict,
    cmap: Mapping[int, str],
    paths: Mapping[int, Mapping[str, pathops.Path]],
    vertical_sources: Mapping[str, str],
    model: _DeltaModel,
    vsindex: int,
) -> None:
    reference_names = [
        cmap[codepoint] for codepoint in CONNECTED_STROKE_REFERENCE_CODEPOINTS
    ]
    reference_vertical_names = [vertical_sources[name] for name in reference_names]
    stroke_widths = {
        weight: connected_stroke_widths(
            [paths[weight][name] for name in reference_names],
            [paths[weight][name] for name in reference_vertical_names],
        )
        for weight in _WEIGHTS
    }
    wave_base = cmap[0x301C]
    wave_stroke_models = {
        weight: make_wave_stroke_model(
            paths[weight][wave_base],
            1000,
            stroke_widths[weight],
        )
        for weight in _WEIGHTS
    }
    allocated = allocate_cid_names(
        font,
        2 * NEW_GLYPH_COUNT
        + WAVE_GLYPH_COUNT
        + RELAXED_WAVE_GLYPH_COUNT
        + ONE_CYCLE_WAVE_GLYPH_COUNT
        + 2 * LINEAR_WAVE_TRANSITION_GLYPH_COUNT
        + 2 * LINEAR_MANGA_TRANSITION_GLYPH_COUNT
        + MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT
        + WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
        + MANGA_WAVE_GLYPH_COUNT,
    )
    extensions = []
    linear_masters = []
    offset = 0
    for prefix, codepoint in (("choon", 0x30FC), ("dash", 0x2015)):
        base = cmap[codepoint]
        vertical = vertical_sources[base]
        names = allocated[offset : offset + NEW_GLYPH_COUNT]
        offset += NEW_GLYPH_COUNT
        horizontal_masters = []
        vertical_masters = []
        for weight in _WEIGHTS:
            horizontal_outline = paths[weight][base]
            if codepoint == 0x30FC:
                horizontal_outline = flatten_horizontal_centerline(
                    horizontal_outline, 1000
                )
            horizontal_outline = normalize_linear_stroke_width(
                horizontal_outline,
                "horizontal",
                500,
                1000,
                stroke_widths[weight].horizontal,
            )
            vertical_outline = normalize_linear_stroke_width(
                paths[weight][vertical],
                "vertical",
                400,
                1000,
                stroke_widths[weight].vertical,
            )
            if codepoint == 0x30FC:
                horizontal_masters.append(
                    _split_horizontal_parts(horizontal_outline, 1000)
                )
                vertical_masters.append(
                    _split_vertical_parts(
                        vertical_outline,
                        1000,
                        _SYMBOL_VERTICAL_ORIGIN,
                    )
                )
            else:
                horizontal_masters.append(
                    make_horizontal_parts(horizontal_outline, 1000)
                )
                vertical_masters.append(
                    make_vertical_parts(vertical_outline, 1000, _SYMBOL_VERTICAL_ORIGIN)
                )
        if codepoint == 0x30FC:
            vertical_masters = _normalize_vertical_parts(vertical_masters)
        masters = [
            horizontal + vertical_parts
            for horizontal, vertical_parts in zip(
                horizontal_masters, vertical_masters, strict=True
            )
        ]
        linear_masters.append(masters)
        _append_glyphs(
            font,
            top,
            _named_master_outlines(names, masters),
            model,
            vsindex,
            base,
            _SYMBOL_VERTICAL_ORIGIN,
        )
        extensions.append((prefix, base, vertical, names))

    wave_vertical = vertical_sources[wave_base]
    wave_names = allocated[offset : offset + WAVE_GLYPH_COUNT]
    offset += WAVE_GLYPH_COUNT
    wave_masters = []
    for weight in _WEIGHTS:
        wave_masters.append(
            make_wave_parts(
                paths[weight][wave_base],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
                wave_stroke_models[weight],
            )
        )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(wave_names, wave_masters),
        model,
        vsindex,
        wave_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )
    wave = ("wave", wave_base, wave_vertical, wave_names)

    relaxed_names = allocated[offset : offset + RELAXED_WAVE_GLYPH_COUNT]
    offset += RELAXED_WAVE_GLYPH_COUNT
    relaxed_masters = []
    for weight in _WEIGHTS:
        relaxed_masters.append(
            make_relaxed_wave_parts(
                paths[weight][wave_base],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
                wave_stroke_models[weight],
            )
        )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(relaxed_names, relaxed_masters),
        model,
        vsindex,
        wave_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )

    one_cycle_names = allocated[offset : offset + ONE_CYCLE_WAVE_GLYPH_COUNT]
    offset += ONE_CYCLE_WAVE_GLYPH_COUNT
    one_cycle_masters = []
    for weight in _WEIGHTS:
        one_cycle_masters.append(
            make_one_cycle_wave_parts(
                paths[weight][wave_base],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
                wave_stroke_models[weight],
            )
        )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(one_cycle_names, one_cycle_masters),
        model,
        vsindex,
        wave_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )
    one_cycle_wave = (
        "one_cycle_wave",
        wave_base,
        wave_vertical,
        one_cycle_names,
    )

    relaxed_wave = (
        "relaxed_wave",
        wave_base,
        wave_vertical,
        relaxed_names,
    )

    linear_wave_transitions = []
    for index, (prefix, base, _, _) in enumerate(extensions):
        names = allocated[offset : offset + LINEAR_WAVE_TRANSITION_GLYPH_COUNT]
        offset += LINEAR_WAVE_TRANSITION_GLYPH_COUNT
        transition_masters = [
            make_linear_wave_transition_parts(
                linear_masters[index][weight_index],
                wave_masters[weight_index],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
            )
            for weight_index in range(len(_WEIGHTS))
        ]
        transition_masters = _normalize_spliced_transition_masters(transition_masters)
        _append_glyphs(
            font,
            top,
            _named_master_outlines(names, transition_masters),
            model,
            vsindex,
            base,
            _SYMBOL_VERTICAL_ORIGIN,
        )
        linear_wave_transitions.append((f"{prefix}_wave", names))

    manga_base = cmap[0x3030]
    transition_names = allocated[offset : offset + MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT]
    offset += MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT
    transition_masters = []
    for weight in _WEIGHTS:
        transition_masters.append(
            make_manga_to_wave_transition_parts(
                paths[weight][wave_base],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
                wave_stroke_models[weight],
            )
        )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(transition_names, transition_masters),
        model,
        vsindex,
        wave_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )
    manga_to_wave_transition = ("manga_to_wave", transition_names)
    reverse_transition_names = allocated[
        offset : offset + WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
    ]
    offset += WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
    reverse_transition_masters = []
    for weight in _WEIGHTS:
        reverse_transition_masters.append(
            make_wave_to_manga_transition_parts(
                paths[weight][wave_base],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
                wave_stroke_models[weight],
            )
        )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(reverse_transition_names, reverse_transition_masters),
        model,
        vsindex,
        manga_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )
    wave_to_manga_transition = ("wave_to_manga", reverse_transition_names)
    manga_names = allocated[offset : offset + MANGA_WAVE_GLYPH_COUNT]
    offset += MANGA_WAVE_GLYPH_COUNT
    manga_isolated = []
    manga_masters = []
    for weight in _WEIGHTS:
        isolated, parts = make_manga_wave_parts(
            paths[weight][wave_base],
            1000,
            _SYMBOL_VERTICAL_ORIGIN,
            wave_stroke_models[weight],
        )
        manga_isolated.append(isolated)
        manga_masters.append(parts)
    _replace_var_glyph(
        font,
        top,
        manga_base,
        manga_isolated,
        _SYMBOL_VERTICAL_ORIGIN,
        model,
        vsindex,
    )
    _append_glyphs(
        font,
        top,
        _named_master_outlines(manga_names, manga_masters),
        model,
        vsindex,
        manga_base,
        _SYMBOL_VERTICAL_ORIGIN,
    )
    manga_wave = ("manga_wave", manga_base, manga_names)
    linear_manga_transitions = []
    for index, (prefix, base, _, _) in enumerate(extensions):
        names = allocated[offset : offset + LINEAR_MANGA_TRANSITION_GLYPH_COUNT]
        offset += LINEAR_MANGA_TRANSITION_GLYPH_COUNT
        transition_masters = [
            make_linear_manga_transition_parts(
                linear_masters[index][weight_index],
                manga_masters[weight_index],
                1000,
                _SYMBOL_VERTICAL_ORIGIN,
            )
            for weight_index in range(len(_WEIGHTS))
        ]
        transition_masters = _normalize_spliced_transition_masters(transition_masters)
        _append_glyphs(
            font,
            top,
            _named_master_outlines(names, transition_masters),
            model,
            vsindex,
            base,
            _SYMBOL_VERTICAL_ORIGIN,
        )
        linear_manga_transitions.append((f"{prefix}_manga", names))
    merge_features(
        font,
        symbol_feature_source(
            extensions,
            wave,
            relaxed_wave,
            manga_wave,
            one_cycle_wave,
            manga_to_wave_transition,
            wave_to_manga_transition,
            linear_wave_transitions,
            linear_manga_transitions,
        ),
    )


def _append_punctuation(
    font: TTFont,
    top: TopDict,
    cmap: Mapping[int, str],
    model: _DeltaModel,
    vsindex: int,
    punctuation_fonts: Mapping[int, TTFont],
) -> None:
    default_count = len(MANGA_PUNCTUATION_SEQUENCES)
    variant_count = len(PUNCTUATION_VARIANT_SEQUENCES)
    allocated = allocate_cid_names(font, default_count + 3 * variant_count)
    default_names = dict(
        zip(
            MANGA_PUNCTUATION_SEQUENCES,
            allocated[:default_count],
            strict=True,
        )
    )
    alternate_names = allocated[default_count:]
    variants = []
    for index, sequence in enumerate(PUNCTUATION_VARIANT_SEQUENCES):
        default = (
            cmap[0xFF01 if sequence == "!" else 0xFF1F]
            if len(sequence) == 1
            else default_names[sequence]
        )
        variants.append(
            (
                sequence,
                (
                    default,
                    alternate_names[index],
                    alternate_names[variant_count + index],
                    alternate_names[2 * variant_count + index],
                ),
            )
        )

    serif_masters = {
        sequence: [
            make_variable_shippori_punctuation_ligature(
                punctuation_fonts[weight],
                sequence,
                weight,
                SHIPPORI_STROKE_ADJUSTMENTS[style],
            )
            for style, weight in _STYLES
        ]
        for sequence in PUNCTUATION_VARIANT_SEQUENCES
    }
    sans_masters = {
        sequence: [
            make_original_punctuation_ligature(sequence, weight, sans=True)
            for weight in _WEIGHTS
        ]
        for sequence in PUNCTUATION_VARIANT_SEQUENCES
    }
    for sequence, codepoint in (("!", 0xFF01), ("?", 0xFF1F)):
        _replace_var_glyph(
            font,
            top,
            cmap[codepoint],
            serif_masters[sequence],
            _SYMBOL_VERTICAL_ORIGIN,
            model,
            vsindex,
        )

    glyphs = []
    for sequence, names in variants:
        default, rotated, sans, rotated_sans = names
        if len(sequence) > 1:
            glyphs.append((default, serif_masters[sequence]))
        glyphs.extend(
            (
                (
                    rotated,
                    [
                        rotate_punctuation_outline(outline)
                        for outline in serif_masters[sequence]
                    ],
                ),
                (sans, sans_masters[sequence]),
                (
                    rotated_sans,
                    [
                        rotate_punctuation_outline(outline)
                        for outline in sans_masters[sequence]
                    ],
                ),
            )
        )
    _append_glyphs(
        font,
        top,
        glyphs,
        model,
        vsindex,
        cmap[0xFF01],
        _SYMBOL_VERTICAL_ORIGIN,
    )
    merge_features(font, punctuation_feature_source(variants))


def _append_lookup(font: TTFont, tags: set[str], subtable) -> None:
    table = font["GSUB"].table
    index = len(table.LookupList.Lookup)
    table.LookupList.Lookup.append(buildLookup([subtable], table="GSUB"))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    found = set()
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag in tags:
            record.Feature.LookupListIndex.append(index)
            record.Feature.LookupCount = len(record.Feature.LookupListIndex)
            found.add(record.FeatureTag)
    if found != tags:
        raise ValueError(
            "The source GSUB lacks features " + ", ".join(sorted(tags - found))
        )


def _small_paths(paths, horizontal: str, vertical: str):
    return (
        [
            geometry.centered_scaled_path(paths[w][horizontal], 0.775, 500, 253)
            for w in _WEIGHTS
        ],
        [
            geometry.centered_scaled_path(paths[w][vertical], 0.78, 654, 397)
            for w in _WEIGHTS
        ],
    )


def _compositions(
    pair: MarkPair,
    orientation: str,
    paths,
    bases,
    cmap,
    positions: Mapping[int, MarkPositionMap],
):
    base, mark = pair
    result = []
    for weight in _WEIGHTS:
        base_path, mark_path = (
            paths[weight][bases[(base, orientation)]],
            paths[weight][cmap[mark]],
        )
        if pair == CHOON_DAKUTEN_PAIR:
            x, y = CHOON_DAKUTEN_MARK_CENTERS[orientation]
            transform = geometry.centered_transform(mark_path, 1, x, y)
        else:
            transform = geometry.mark_placement_transform(
                mark_path, positions[weight][pair][orientation]
            )
        result.append(geometry.compose_mark_glyph(base_path, mark_path, transform))
    return result


def _append_punctuation_mark_composites(
    font: TTFont,
    top: TopDict,
    cmap: Mapping[int, str],
    model: _DeltaModel,
    vsindex: int,
) -> None:
    positions = {
        weight: load_punctuation_mark_positions(base="noto", weight=style)
        for style, weight in _STYLES
    }
    bases = {}
    source_names = {cmap[0x3099], cmap[0x309A]}
    for base, _ in PUNCTUATION_MARK_PAIRS:
        horizontal = cmap[base]
        vertical = vertical_glyph_or_self(font, horizontal)
        bases[(base, "horizontal")] = horizontal
        bases[(base, "vertical")] = vertical
        source_names.update((horizontal, vertical))
    paths = _paths(font, sorted(source_names))

    names = allocate_cid_names(font, 2 * len(PUNCTUATION_MARK_PAIRS))
    horizontal_names = names[: len(PUNCTUATION_MARK_PAIRS)]
    vertical_names = names[len(PUNCTUATION_MARK_PAIRS) :]
    outputs = dict(zip(PUNCTUATION_MARK_PAIRS, horizontal_names, strict=True))
    vertical_outputs = dict(zip(PUNCTUATION_MARK_PAIRS, vertical_names, strict=True))
    glyphs = []
    for pair in PUNCTUATION_MARK_PAIRS:
        glyphs.append(
            (
                outputs[pair],
                _compositions(pair, "horizontal", paths, bases, cmap, positions),
            )
        )
        glyphs.append(
            (
                vertical_outputs[pair],
                _compositions(pair, "vertical", paths, bases, cmap, positions),
            )
        )
    _append_glyphs(
        font,
        top,
        glyphs,
        model,
        vsindex,
        cmap[0xFF01],
        _SYMBOL_VERTICAL_ORIGIN,
    )

    ccmp = {
        (cmap[base], cmap[mark]): outputs[(base, mark)]
        for base, mark in PUNCTUATION_MARK_PAIRS
    }
    liga = {
        (cmap[base], cmap[_SPACING[mark]]): outputs[(base, mark)]
        for base, mark in PUNCTUATION_MARK_PAIRS
    }
    vertical = {
        outputs[pair]: vertical_outputs[pair] for pair in PUNCTUATION_MARK_PAIRS
    }
    _append_lookup(font, {"ccmp"}, buildLigatureSubstSubtable(ccmp))
    _append_lookup(font, {"liga"}, buildLigatureSubstSubtable(liga))
    _append_lookup(font, {"vert", "vrt2"}, buildSingleSubstSubtable(vertical))


def _append_heart_mark_composites(
    font: TTFont,
    top: TopDict,
    cmap: dict[int, str],
    paths: Mapping[int, Mapping[str, pathops.Path]],
    model: _DeltaModel,
    vsindex: int,
) -> None:
    def cubic_segments(contour: pathops.Path) -> list[_ContourSegment]:
        result = []
        for segment in _contour_segments(contour):
            if segment.controls:
                result.append(segment)
                continue
            first = (
                (2 * segment.start[0] + segment.end[0]) / 3,
                (2 * segment.start[1] + segment.end[1]) / 3,
            )
            second = (
                (segment.start[0] + 2 * segment.end[0]) / 3,
                (segment.start[1] + 2 * segment.end[1]) / 3,
            )
            result.append(_ContourSegment(segment.start, (first, second), segment.end))
        return result

    def align_segments(
        reference: Sequence[_ContourSegment],
        source: Sequence[_ContourSegment],
    ) -> list[_ContourSegment | None]:
        if len(source) > len(reference):
            raise ValueError("A heart master exceeds the reference contour topology")

        def cost(left: _ContourSegment, right: _ContourSegment) -> float:
            left_points = (left.start, *left.controls, left.end)
            right_points = (right.start, *right.controls, right.end)
            return sum(
                (left_x - right_x) ** 2 + (left_y - right_y) ** 2
                for (left_x, left_y), (right_x, right_y) in zip(
                    left_points, right_points, strict=True
                )
            )

        width = len(source) + 1
        scores = [[math.inf] * width for _ in range(len(reference) + 1)]
        matched = [[False] * width for _ in range(len(reference) + 1)]
        scores[0][0] = 0
        for reference_index in range(1, len(reference) + 1):
            scores[reference_index][0] = 0
            for source_index in range(1, min(reference_index, len(source)) + 1):
                gap_score = scores[reference_index - 1][source_index]
                match_score = scores[reference_index - 1][source_index - 1] + cost(
                    reference[reference_index - 1],
                    source[source_index - 1],
                )
                if match_score <= gap_score:
                    scores[reference_index][source_index] = match_score
                    matched[reference_index][source_index] = True
                else:
                    scores[reference_index][source_index] = gap_score

        aligned: list[_ContourSegment | None] = []
        reference_index, source_index = len(reference), len(source)
        while reference_index:
            if source_index and matched[reference_index][source_index]:
                aligned.append(source[source_index - 1])
                source_index -= 1
            else:
                aligned.append(None)
            reference_index -= 1
        if source_index:
            raise ValueError("Could not align the heart master contour topology")
        aligned.reverse()
        return aligned

    def normalize(masters: Sequence[pathops.Path]) -> list[pathops.Path]:
        contours = [list(master.contours) for master in masters]
        expected_count = 1 + len(HEART_DAKUTEN_MARK_TRANSFORMS)
        if any(len(items) != expected_count for items in contours):
            raise ValueError(
                "Heart boolean construction must produce one body and two marks"
            )
        body_segments = [cubic_segments(items[0]) for items in contours]
        reference = max(body_segments, key=len)
        mark_signatures = [
            tuple(tuple(contour.verbs) for contour in items[1:]) for items in contours
        ]
        if any(signature != mark_signatures[0] for signature in mark_signatures[1:]):
            raise ValueError("Heart dakuten mark contours are not compatible")

        result = []
        for items, segments in zip(contours, body_segments, strict=True):
            aligned = align_segments(reference, segments)
            normalized = pathops.Path()
            pen = normalized.getPen()
            point = segments[0].start
            pen.moveTo(point)
            for segment in aligned:
                if segment is None:
                    pen.curveTo(point, point, point)
                else:
                    segment.draw(pen)
                    point = segment.end
            pen.closePath()
            for contour in items[1:]:
                normalized.addPath(contour)
            result.append(normalized)

        signature = tuple(result[0].verbs)
        if any(tuple(master.verbs) != signature for master in result[1:]):
            raise ValueError("Heart master normalization did not produce CFF2 topology")
        return result

    allocated = allocate_cid_names(font, len(KOBURI_HEART_MARK_PAIRS))
    glyphs = []
    outputs = {}
    for pair, name in zip(KOBURI_HEART_MARK_PAIRS, allocated, strict=True):
        base, mark = pair
        raw_masters = [
            geometry.compose_heart_dakuten_glyph(
                paths[weight][cmap[base]],
                paths[weight][cmap[mark]],
            )
            for weight in _WEIGHTS
        ]
        glyphs.append((name, normalize(raw_masters)))
        outputs[pair] = name
    _append_glyphs(
        font,
        top,
        glyphs,
        model,
        vsindex,
        cmap[KOBURI_HEART_MARK_PAIRS[0][0]],
    )

    for codepoint, (base, _) in zip(
        KOBURI_HEART_BASE_PUA,
        KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        add_unicode_mapping(font, codepoint, cmap[base])
        cmap[codepoint] = cmap[base]
    for codepoint, pair in zip(
        KOBURI_HEART_OUTPUT_PUA,
        KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        add_unicode_mapping(font, codepoint, outputs[pair])
        cmap[codepoint] = outputs[pair]

    _append_lookup(
        font,
        {"ccmp"},
        buildLigatureSubstSubtable(
            {
                (cmap[base], cmap[mark]): outputs[(base, mark)]
                for base, mark in KOBURI_HEART_MARK_PAIRS
            }
        ),
    )
    _append_lookup(
        font,
        {"liga"},
        buildLigatureSubstSubtable(
            {
                (cmap[base], cmap[_SPACING[mark]]): outputs[(base, mark)]
                for base, mark in KOBURI_HEART_MARK_PAIRS
            }
        ),
    )


def rename_variable_font(
    font: TTFont,
    family: str = "Nobigoe Variable Marks",
    japanese_family: str = "Nobigoe Variable Marks",
    postscript_prefix: str = "NobigoeVariableMarks",
) -> None:
    """Apply consistent variable-family names and named-instance PostScript names."""

    style = "ExtraLight"
    postscript_name = f"{postscript_prefix}-{style}"
    full_name = f"{family} {style}"
    set_name(font, 1, family)
    set_name(font, 2, style)
    set_name(font, 3, f"{VERSION_NUMBER};NOBIGOE;{postscript_name}")
    set_name(font, 4, full_name)
    set_name(font, 5, VERSION)
    set_name(font, 6, postscript_name)
    set_name(font, 16, family)
    set_name(font, 17, style)
    set_name(font, 25, postscript_prefix)
    japanese_full_name = f"{japanese_family} {style}"
    for name_id, value in (
        (1, japanese_family),
        (4, japanese_full_name),
        (16, japanese_family),
        (17, style),
    ):
        set_japanese_name(font, name_id, value)
    styles = {weight: name for name, weight in _STYLES}
    for instance in font["fvar"].instances:
        instance_style = styles[instance.coordinates["wght"]]
        if instance.postscriptNameID != 0xFFFF:
            set_name(
                font,
                instance.postscriptNameID,
                f"{postscript_prefix}-{instance_style}",
            )


def build_variable_marks(
    source_path: Path,
    output_path: Path,
    face: int = 0,
    punctuation_sources: Mapping[int, Path] | None = None,
) -> None:
    """Write a Noto Serif JP CFF2 VF with Nobigoe punctuation and marks."""

    if punctuation_sources is None or set(punctuation_sources) != set(_WEIGHTS):
        raise ValueError("Shippori punctuation sources are required for all weights")
    punctuation_fonts = {
        weight: TTFont(punctuation_sources[weight]) for weight in _WEIGHTS
    }
    font = TTFont(source_path, fontNumber=face)
    top, locations = _validate(font)
    original_order = list(font.getGlyphOrder())
    _ = (
        font["post"].formatType,
        font["cmap"].tables,
        font["hmtx"].metrics,
        font["vmtx"].metrics,
    )
    for tag in ("HVAR", "VVAR"):
        table = font[tag].table
        _ = table.VarStore
        for attribute, varmap in vars(table).items():
            if attribute.endswith("Map") and varmap is not None:
                _ = varmap.mapping
    cmap = dict(font.getBestCmap())
    required = {
        0x3042,
        0x3053,
        0x30B3,
        0x2015,
        0x301C,
        0x3030,
        0xFF5E,
        0xFF01,
        0xFF1F,
        0x3099,
        0x309A,
        0x309B,
        0x309C,
        0x30FC,
        *CONNECTED_STROKE_REFERENCE_CODEPOINTS,
        *(base for base, _ in KOBURI_HEART_MARK_PAIRS),
        *(base for base, _ in MANGA_MARK_PAIRS if base not in MANGA_MISSING_SMALL_KANA),
    }
    missing = sorted(required - cmap.keys())
    if missing:
        raise ValueError(
            "The variable source lacks " + ", ".join(f"U+{cp:04X}" for cp in missing)
        )
    if cmap[0x301C] != cmap[0xFF5E]:
        raise ValueError("U+301C and U+FF5E must share a source glyph")
    pairs = (*MANGA_MARK_PAIRS, CHOON_DAKUTEN_PAIR)
    source_ccmp = feature_ligatures(font, "ccmp")
    native = {}
    for pair in pairs:
        base, mark = pair
        if (
            base in cmap
            and (output := source_ccmp.get((cmap[base], cmap[mark]))) is not None
        ):
            native[pair] = output
    generated = [pair for pair in pairs if pair not in native]
    positions = {
        weight: load_mark_position_overrides(weight=style) for style, weight in _STYLES
    }
    names = {
        cmap[0x3053],
        cmap[0x30B3],
        cmap[0x3099],
        cmap[0x309A],
        *(cmap[base] for base, _ in generated if base in cmap),
    }
    names.update(cmap[codepoint] for codepoint in (0x2015, 0x301C, 0x3030, 0x30FC))
    names.update(cmap[codepoint] for codepoint in CONNECTED_STROKE_REFERENCE_CODEPOINTS)
    vertical_sources = {name: vertical_glyph_or_self(font, name) for name in names}
    names.update(vertical_sources.values())
    names.update(cmap[base] for base, _ in KOBURI_HEART_MARK_PAIRS)
    paths = _paths(font, sorted(names))
    allocated = allocate_cid_names(font, 4 + 2 * len(generated))
    small = {
        0x1B132: (allocated[0], allocated[2]),
        0x1B155: (allocated[1], allocated[3]),
    }
    glyphs = []
    small_outlines = {}
    for codepoint, source in ((0x1B132, 0x3053), (0x1B155, 0x30B3)):
        horizontal, vertical = _small_paths(
            paths, cmap[source], vertical_sources[cmap[source]]
        )
        h_name, v_name = small[codepoint]
        small_outlines[h_name], small_outlines[v_name] = horizontal, vertical
        glyphs.extend(((h_name, horizontal), (v_name, vertical)))
    for index, weight in enumerate(_WEIGHTS):
        for h_name, v_name in small.values():
            paths[weight][h_name] = small_outlines[h_name][index]
            paths[weight][v_name] = small_outlines[v_name][index]
    bases = {}
    for base, _ in generated:
        horizontal, vertical = (
            small[base] if base in small else (cmap[base], vertical_sources[cmap[base]])
        )
        bases[(base, "horizontal")], bases[(base, "vertical")] = horizontal, vertical
    h_names = allocated[4 : 4 + len(generated)]
    v_names = allocated[4 + len(generated) :]
    outputs = dict(zip(generated, h_names, strict=True))
    vertical_outputs = dict(zip(generated, v_names, strict=True))
    for pair in generated:
        glyphs.append(
            (
                outputs[pair],
                _compositions(pair, "horizontal", paths, bases, cmap, positions),
            )
        )
        glyphs.append(
            (
                vertical_outputs[pair],
                _compositions(pair, "vertical", paths, bases, cmap, positions),
            )
        )
    vsindex, model = _append_var_data(top, locations)
    _append_glyphs(font, top, glyphs, model, vsindex, cmap[0x3042])
    for codepoint, (horizontal, _) in small.items():
        add_unicode_mapping(font, codepoint, horizontal)
        cmap[codepoint] = horizontal
    all_outputs = dict(native)
    all_outputs.update(outputs)
    for offset, pair in enumerate(KOBURI_PUA_MARK_PAIRS):
        add_unicode_mapping(font, KOBURI_PUA_START + offset, all_outputs[pair])
    add_unicode_mapping(font, CHOON_DAKUTEN_PUA, all_outputs[CHOON_DAKUTEN_PAIR])
    ccmp = {(cmap[base], cmap[mark]): outputs[(base, mark)] for base, mark in generated}
    liga = {
        (cmap[base], cmap[_SPACING[mark]]): all_outputs[(base, mark)]
        for base, mark in pairs
    }
    for pair in pairs:
        base, mark = pair
        if pair in vertical_outputs:
            vertical_base = bases[(base, "vertical")]
            vertical_output = vertical_outputs[pair]
            vertical_mark = vertical_glyph_or_self(font, cmap[mark])
            vertical_ccmp = (vertical_base, vertical_mark)
            if vertical_ccmp != (cmap[base], cmap[mark]):
                ccmp[vertical_ccmp] = vertical_output
        else:
            vertical_base = vertical_glyph_or_self(font, cmap[base])
            vertical_output = vertical_glyph_or_self(font, all_outputs[pair])
        vertical_spacing = vertical_glyph_or_self(font, cmap[_SPACING[mark]])
        vertical_liga = (vertical_base, vertical_spacing)
        if vertical_liga != (cmap[base], cmap[_SPACING[mark]]):
            liga[vertical_liga] = vertical_output
    vertical = {
        **{h: v for h, v in small.values()},
        **{outputs[p]: vertical_outputs[p] for p in generated},
    }
    if ccmp:
        _append_lookup(font, {"ccmp"}, buildLigatureSubstSubtable(ccmp))
    _append_lookup(font, {"liga"}, buildLigatureSubstSubtable(liga))
    _append_heart_mark_composites(font, top, cmap, paths, model, vsindex)
    _append_lookup(font, {"vert", "vrt2"}, buildSingleSubstSubtable(vertical))
    source_vertical = {
        **feature_single_substitutions(font, "vert"),
        **feature_single_substitutions(font, "vrt2"),
    }
    if any(output not in source_vertical for output in native.values()):
        raise ValueError("Native ccmp mark outputs lack source vertical forms")
    remove_repeated_ligatures(font, "ccmp", cmap[0x2015])
    _append_symbols(font, top, cmap, paths, vertical_sources, model, vsindex)
    _append_punctuation(font, top, cmap, model, vsindex, punctuation_fonts)
    _append_punctuation_mark_composites(font, top, cmap, model, vsindex)
    if original_order != font.getGlyphOrder()[: len(original_order)]:
        raise AssertionError("Existing glyph order changed while adding variable marks")
    compact_auxiliary_single_substitutions(font)
    consolidate_vrt2_lookups(font)
    rename_variable_font(font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path)
