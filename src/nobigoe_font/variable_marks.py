"""CFF2 variable-font kana and combining-mark generation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path

import pathops
from fontTools.cffLib import TopDict
from fontTools.misc.fixedTools import floatToFixedToFloat
from fontTools.otlLib.builder import (
    buildLigatureSubstSubtable,
    buildLookup,
    buildSingleSubstSubtable,
)
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.varLib.cff import CFF2CharStringMergePen
from fontTools.varLib.models import normalizeValue, piecewiseLinearMap

from . import geometry
from .marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    CHOON_DAKUTEN_PUA,
    KOBURI_PUA_MARK_PAIRS,
    KOBURI_PUA_START,
    MANGA_MARK_PAIRS,
    MANGA_MISSING_SMALL_KANA,
    MarkPair,
    MarkPositionMap,
    load_mark_position_overrides,
)
from .metadata import set_japanese_name, set_name
from .operations import (
    add_unicode_mapping,
    allocate_cid_names,
    feature_ligatures,
    feature_single_substitutions,
    vertical_glyph_or_self,
)
from .profiles import NOTO_WEIGHT_CLASSES
from .version import VERSION, VERSION_NUMBER

_STYLES = tuple(NOTO_WEIGHT_CLASSES.items())
_WEIGHTS = tuple(value for _, value in _STYLES)
_SPACING = {0x3099: 0x309B, 0x309A: 0x309C}


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
        font["vmtx"].metrics[name] = (vertical_advance, math.floor(880 - y_max))
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


def _rename_font(font: TTFont) -> None:
    family = "Nobigoe Variable Marks"
    style = "ExtraLight"
    postscript_prefix = "NobigoeVariableMarks"
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
    for name_id, value in ((1, family), (4, full_name), (16, family), (17, style)):
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


def build_variable_marks(source_path: Path, output_path: Path, face: int = 0) -> None:
    """Write a Noto Serif JP CFF2 VF with reviewed kana mark outputs."""
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
        0x3099,
        0x309A,
        0x309B,
        0x309C,
        0x30FC,
        *(base for base, _ in MANGA_MARK_PAIRS if base not in MANGA_MISSING_SMALL_KANA),
    }
    missing = sorted(required - cmap.keys())
    if missing:
        raise ValueError(
            "The variable source lacks " + ", ".join(f"U+{cp:04X}" for cp in missing)
        )
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
    vertical_sources = {name: vertical_glyph_or_self(font, name) for name in names}
    names.update(vertical_sources.values())
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
    _append_lookup(font, {"vert", "vrt2"}, buildSingleSubstSubtable(vertical))
    source_vertical = {
        **feature_single_substitutions(font, "vert"),
        **feature_single_substitutions(font, "vrt2"),
    }
    if any(output not in source_vertical for output in native.values()):
        raise ValueError("Native ccmp mark outputs lack source vertical forms")
    if original_order != font.getGlyphOrder()[: len(original_order)]:
        raise AssertionError("Existing glyph order changed while adding variable marks")
    _rename_font(font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path)
