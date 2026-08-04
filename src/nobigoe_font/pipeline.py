"""Build Nobigoe font families with extensible punctuation."""

from __future__ import annotations
from dataclasses import dataclass

from collections.abc import Mapping, Sequence
import math
from io import BytesIO
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
import statistics
from tempfile import TemporaryDirectory

from .profiles import (
    BaseType,
    FontIdentity,
    KanaStyle,
    LatinBuildProfile,
    SHIPPORI_COPYRIGHT,
    SHIPPORI_STROKE_ADJUSTMENTS,
)
from . import geometry as _font_geometry
from . import operations as _font_operations
from . import marks as _mark_positioning
from .brush import (
    DEFAULT_VERTICAL_END_PROFILE,
    VERTICAL_END_PROFILES,
    BrushElementStyle,
    VerticalEndProfile,
    apply_han_brush_elements,
)
from .features import feature_source, merge_features
from .hinting import autohint_latin_glyphs
from .metadata import rename_font
from .variable_stix import instantiate_stix_latin_font
from .novel import (
    HIRAGANA_CODEPOINTS,
    NOVEL_SMALL_KO_CODEPOINT,
    apply_novel_hiragana,
    novel_base_codepoint,
    novel_group_for_codepoint,
)
from .novel_katakana import (
    KATAKANA_CODEPOINTS,
    KATAKANA_SOURCE_CODEPOINTS,
    apply_novel_katakana,
    katakana_base_codepoint,
    novel_katakana_group_for_codepoint,
)
from .novel_han import apply_novel_han
from .punctuation import (
    MANGA_PUNCTUATION_SEQUENCES,
    PUNCTUATION_ROTATED_COUNT,
    PUNCTUATION_VARIANT_SEQUENCES,
    SHIPPORI_PRECOMPOSED_LIGATURES,
    SHIPPORI_UPRIGHT_EXCLAMATIONS,
    SHIPPORI_UPRIGHT_PUNCTUATION,
    make_punctuation_ligature,
    shippori_upright_punctuation_paths,
    rotate_punctuation_outline,
)

import pathops
from fontTools.cffLib.CFF2ToCFF import convertCFF2ToCFF
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.varLib.instancer import instantiateVariableFont

WAVE_GLYPH_COUNT = 10
RELAXED_WAVE_GLYPH_COUNT = 20
ONE_CYCLE_WAVE_GLYPH_COUNT = 8
LINEAR_WAVE_TRANSITION_GLYPH_COUNT = 12
LINEAR_MANGA_TRANSITION_GLYPH_COUNT = 10
MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT = 8
WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT = 8
MANGA_WAVE_GLYPH_COUNT = 11
WAVE_TERMINAL_EXTENSION_HALF_WAVES = 0.3
LINEAR_WAVE_TRANSITION_SEGMENTS = 24
WAVE_STROKE_MODULATION = 0.3
NEW_GLYPH_COUNT = 6

CONNECTED_STROKE_REFERENCE_CODEPOINTS = tuple(
    ord(character)
    for character in "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "はひふへほまみむめもやゆよらりるれろわをん"
)


@dataclass(frozen=True)
class ConnectedStrokeWidths:
    horizontal: float
    vertical: float


@dataclass(frozen=True)
class OrientedStrokeScales:
    horizontal: float
    vertical: float


@dataclass(frozen=True)
class WaveStrokeModel:
    default: OrientedStrokeScales
    relaxed: OrientedStrokeScales
    one_cycle: OrientedStrokeScales
    manga: OrientedStrokeScales


OVERLAP = 8


COMBINING_MARK_INPUTS = {
    0x3099: 0x3099,
    0x309A: 0x309A,
}
SPACING_MARK_INPUTS = {
    0x3099: 0x309B,
    0x309A: 0x309C,
}


def _add_novel_glyph_group(
    mapping: dict[str, str],
    glyph_name: str,
    group: str,
    *,
    codepoint: int | None = None,
    codepoints: dict[str, int] | None = None,
    base_codepoint: Callable[[int], int] = novel_base_codepoint,
    script: str = "hiragana",
) -> None:
    previous = mapping.setdefault(glyph_name, group)
    if previous != group:
        raise ValueError(
            f"Conflicting novel {script} groups for {glyph_name!r}: "
            f"{previous!r} and {group!r}"
        )
    if codepoint is not None and codepoints is not None:
        previous_codepoint = codepoints.setdefault(glyph_name, codepoint)
        if base_codepoint(previous_codepoint) != base_codepoint(codepoint):
            raise ValueError(
                f"Conflicting novel {script} vertical bases for {glyph_name!r}"
            )


def _native_novel_ccmp_outputs(
    font: TTFont,
    cmap: dict[int, str],
    ligatures: dict[tuple[str, ...], str],
    codepoints: Iterable[int],
) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], str]]:
    horizontal_outputs: dict[tuple[int, int], str] = {}
    vertical_outputs: dict[tuple[int, int], str] = {}
    for base in codepoints:
        base_name = cmap.get(base)
        if base_name is None:
            continue
        vertical_base_name = _font_operations.vertical_glyph_or_self(font, base_name)
        for mark in (0x3099, 0x309A):
            mark_name = cmap.get(mark)
            if mark_name is None:
                continue
            pair = (base, mark)
            horizontal_output = ligatures.get((base_name, mark_name))
            if horizontal_output is not None:
                horizontal_outputs[pair] = horizontal_output
            vertical_output = ligatures.get((vertical_base_name, mark_name))
            if vertical_output is not None:
                vertical_outputs[pair] = vertical_output
    return horizontal_outputs, vertical_outputs


def _novel_hiragana_mappings(
    font: TTFont,
    cmap: dict[int, str],
    mark_outputs: dict[tuple[int, int], str],
    vertical_mark_outputs: dict[tuple[int, int], str],
    missing_small_glyphs: dict[int, tuple[str, str]],
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, int],
    frozenset[str],
    dict[str, int],
]:
    horizontal: dict[str, str] = {}
    horizontal_codepoints: dict[str, int] = {}
    vertical: dict[str, str] = {}
    vertical_codepoints: dict[str, int] = {}
    vertical_marked_glyphs: set[str] = set()
    hiragana_bases = frozenset(HIRAGANA_CODEPOINTS) | {NOVEL_SMALL_KO_CODEPOINT}

    for codepoint in HIRAGANA_CODEPOINTS:
        glyph_name = cmap.get(codepoint)
        if glyph_name is None:
            continue
        group = novel_group_for_codepoint(codepoint)
        _add_novel_glyph_group(
            horizontal,
            glyph_name,
            group,
            codepoint=codepoint,
            codepoints=horizontal_codepoints,
        )
        vertical_name = _font_operations.vertical_glyph_or_self(font, glyph_name)
        if vertical_name != glyph_name:
            _add_novel_glyph_group(
                vertical,
                vertical_name,
                group,
                codepoint=codepoint,
                codepoints=vertical_codepoints,
            )
            if novel_base_codepoint(codepoint) != codepoint:
                vertical_marked_glyphs.add(vertical_name)

    generated_small = missing_small_glyphs.get(NOVEL_SMALL_KO_CODEPOINT)
    if generated_small is not None:
        horizontal_name, vertical_name = generated_small
        _add_novel_glyph_group(
            horizontal,
            horizontal_name,
            "small",
            codepoint=NOVEL_SMALL_KO_CODEPOINT,
            codepoints=horizontal_codepoints,
        )
        _add_novel_glyph_group(
            vertical,
            vertical_name,
            "small",
            codepoint=NOVEL_SMALL_KO_CODEPOINT,
            codepoints=vertical_codepoints,
        )

    for pair, horizontal_name in mark_outputs.items():
        base, _ = pair
        if base not in hiragana_bases:
            continue
        group = novel_group_for_codepoint(base)
        _add_novel_glyph_group(
            horizontal,
            horizontal_name,
            group,
            codepoint=base,
            codepoints=horizontal_codepoints,
        )
        vertical_name = vertical_mark_outputs.get(pair)
        if vertical_name is None:
            vertical_name = _font_operations.vertical_glyph_or_self(
                font, horizontal_name
            )
        if vertical_name != horizontal_name:
            _add_novel_glyph_group(
                vertical,
                vertical_name,
                group,
                codepoint=base,
                codepoints=vertical_codepoints,
            )
            vertical_marked_glyphs.add(vertical_name)

    return (
        horizontal,
        vertical,
        vertical_codepoints,
        frozenset(vertical_marked_glyphs),
        horizontal_codepoints,
    )


def _novel_katakana_mappings(
    font: TTFont,
    cmap: dict[int, str],
    mark_outputs: dict[tuple[int, int], str],
    vertical_mark_outputs: dict[tuple[int, int], str],
    missing_small_glyphs: dict[int, tuple[str, str]],
) -> tuple[dict[str, str], dict[str, str], dict[str, int], frozenset[str]]:
    horizontal: dict[str, str] = {}
    vertical: dict[str, str] = {}
    vertical_codepoints: dict[str, int] = {}
    vertical_marked_glyphs: set[str] = set()

    def add(
        mapping: dict[str, str],
        glyph_name: str,
        group: str,
        *,
        codepoint: int | None = None,
        codepoints: dict[str, int] | None = None,
    ) -> None:
        _add_novel_glyph_group(
            mapping,
            glyph_name,
            group,
            codepoint=codepoint,
            codepoints=codepoints,
            base_codepoint=katakana_base_codepoint,
            script="katakana",
        )

    for codepoint in KATAKANA_SOURCE_CODEPOINTS:
        glyph_name = cmap.get(codepoint)
        if glyph_name is None:
            continue
        group = novel_katakana_group_for_codepoint(codepoint)
        add(horizontal, glyph_name, group)
        vertical_name = _font_operations.vertical_glyph_or_self(font, glyph_name)
        if vertical_name != glyph_name:
            add(
                vertical,
                vertical_name,
                group,
                codepoint=codepoint,
                codepoints=vertical_codepoints,
            )
            if katakana_base_codepoint(codepoint) != codepoint:
                vertical_marked_glyphs.add(vertical_name)

    generated_small = missing_small_glyphs.get(0x1B155)
    if generated_small is not None:
        horizontal_name, vertical_name = generated_small
        add(horizontal, horizontal_name, "small")
        add(
            vertical,
            vertical_name,
            "small",
            codepoint=0x1B155,
            codepoints=vertical_codepoints,
        )

    for pair, horizontal_name in mark_outputs.items():
        base, _ = pair
        if base not in KATAKANA_CODEPOINTS:
            continue
        group = novel_katakana_group_for_codepoint(base)
        add(horizontal, horizontal_name, group)
        vertical_name = vertical_mark_outputs.get(pair)
        if vertical_name is None:
            vertical_name = _font_operations.vertical_glyph_or_self(
                font, horizontal_name
            )
        if vertical_name != horizontal_name:
            add(
                vertical,
                vertical_name,
                group,
                codepoint=base,
                codepoints=vertical_codepoints,
            )
            vertical_marked_glyphs.add(vertical_name)

    for glyph_name in horizontal.keys() & vertical.keys():
        if horizontal[glyph_name] != vertical[glyph_name]:
            raise ValueError(
                f"Conflicting novel katakana groups for {glyph_name!r}: "
                f"{horizontal[glyph_name]!r} and {vertical[glyph_name]!r}"
            )
        del vertical[glyph_name]
        vertical_codepoints.pop(glyph_name, None)
        vertical_marked_glyphs.discard(glyph_name)

    return (
        horizontal,
        vertical,
        vertical_codepoints,
        frozenset(vertical_marked_glyphs),
    )


def _apply_novel_style(
    font: TTFont,
    weight_class: int,
    kana_style: KanaStyle,
    hiragana_mappings: (
        tuple[
            dict[str, str],
            dict[str, str],
            dict[str, int],
            frozenset[str],
            dict[str, int],
        ]
        | None
    ) = None,
    katakana_mappings: (
        tuple[dict[str, str], dict[str, str], dict[str, int], frozenset[str]] | None
    ) = None,
) -> None:
    if kana_style != "novel":
        return
    if hiragana_mappings is None or katakana_mappings is None:
        raise ValueError("Novel kana mappings are required for the novel style")
    (
        horizontal,
        vertical,
        vertical_codepoints,
        vertical_marked_glyphs,
        horizontal_codepoints,
    ) = hiragana_mappings
    apply_novel_hiragana(
        font,
        weight_class,
        horizontal,
        vertical,
        vertical_codepoints,
        vertical_marked_glyphs,
        horizontal_codepoints=horizontal_codepoints,
    )
    apply_novel_katakana(font, weight_class, *katakana_mappings)
    apply_novel_han(font)


def stroke_band(outline: pathops.Path, axis: str, seam: float) -> tuple[int, int]:
    if axis == "horizontal":
        sample = _font_geometry.rectangle(seam - 0.5, -4096, seam + 0.5, 4096)
        clipped = pathops.op(outline, sample, pathops.PathOp.INTERSECTION)
        low, high = clipped.bounds[1], clipped.bounds[3]
    else:
        sample = _font_geometry.rectangle(-4096, seam - 0.5, 4096, seam + 0.5)
        clipped = pathops.op(outline, sample, pathops.PathOp.INTERSECTION)
        low, high = clipped.bounds[0], clipped.bounds[2]
    inner_low, inner_high = math.ceil(low), math.floor(high)
    if inner_low >= inner_high:
        raise ValueError("Could not derive a non-empty center stroke")
    return inner_low, inner_high


def connected_stroke_widths(
    horizontal_outlines: Sequence[pathops.Path],
    vertical_outlines: Sequence[pathops.Path],
) -> ConnectedStrokeWidths:
    if not horizontal_outlines or not vertical_outlines:
        raise ValueError("Connected stroke references cannot be empty")
    return ConnectedStrokeWidths(
        statistics.median(
            _font_geometry.optical_stroke_width(outline)
            for outline in horizontal_outlines
        ),
        statistics.median(
            _font_geometry.optical_stroke_width(outline)
            for outline in vertical_outlines
        ),
    )


def normalize_linear_stroke_width(
    outline: pathops.Path,
    axis: str,
    seam: float,
    advance: int,
    target: float,
) -> pathops.Path:
    if not 0 < target < advance:
        raise ValueError("Connected stroke width must be between zero and the advance")
    low, high = stroke_band(outline, axis, seam)
    width = high - low
    center = (low + high) / 2
    ideal_width = target * advance / (advance - target)
    candidates: list[tuple[float, pathops.Path]] = []
    for candidate_width in range(
        max(1, math.floor(ideal_width) - 3),
        math.ceil(ideal_width) + 4,
    ):
        scale = candidate_width / width
        if axis == "horizontal":
            transform = Transform(1, 0, 0, scale, 0, center * (1 - scale))
        elif axis == "vertical":
            transform = Transform(scale, 0, 0, 1, center * (1 - scale), 0)
        else:
            raise ValueError(f"Unsupported linear stroke axis {axis!r}")
        candidate = _font_geometry.transform_path(outline, transform)
        candidate_low, candidate_high = stroke_band(candidate, axis, seam)
        actual_width = candidate_high - candidate_low
        optical_width = advance * actual_width / (advance + actual_width)
        candidates.append((abs(optical_width - target), candidate))
    return min(candidates, key=lambda item: item[0])[1]


def make_horizontal_parts(
    outline: pathops.Path, advance: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance / 2
    y_min, y_max = stroke_band(outline, "horizontal", seam)
    clip_left = _font_geometry.rectangle(-4096, -4096, seam, 4096)
    clip_right = _font_geometry.rectangle(seam, -4096, 4096, 4096)
    left_cap = pathops.op(outline, clip_left, pathops.PathOp.INTERSECTION)
    right_cap = pathops.op(outline, clip_right, pathops.PathOp.INTERSECTION)

    start_bar = _font_geometry.rectangle(
        seam - OVERLAP, y_min, advance + OVERLAP, y_max
    )
    middle = _font_geometry.rectangle(-OVERLAP, y_min, advance + OVERLAP, y_max)
    end_bar = _font_geometry.rectangle(-OVERLAP, y_min, seam + OVERLAP, y_max)
    start = pathops.op(left_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, right_cap, pathops.PathOp.UNION)
    return start, middle, end


def flatten_horizontal_centerline(outline: pathops.Path, advance: int) -> pathops.Path:
    sample_start = advance * 0.3
    sample_end = advance * 0.7
    start_low, start_high = stroke_band(outline, "horizontal", sample_start)
    end_low, end_high = stroke_band(outline, "horizontal", sample_end)
    start_center = (start_low + start_high) / 2
    end_center = (end_low + end_high) / 2
    slope = (end_center - start_center) / (sample_end - sample_start)
    seam = advance / 2
    return _font_geometry.transform_path(
        outline,
        Transform(1, -slope, 0, 1, 0, slope * seam),
    )


def make_vertical_parts(
    outline: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance * 0.4
    x_min, x_max = stroke_band(outline, "vertical", seam)
    clip_top = _font_geometry.rectangle(-4096, seam, 4096, 4096)
    clip_bottom = _font_geometry.rectangle(-4096, -4096, 4096, seam)
    top_cap = pathops.op(outline, clip_top, pathops.PathOp.INTERSECTION)
    bottom_cap = pathops.op(outline, clip_bottom, pathops.PathOp.INTERSECTION)

    cell_top = vertical_origin
    cell_bottom = vertical_origin - advance
    start_bar = _font_geometry.rectangle(
        x_min, cell_bottom - OVERLAP, x_max, seam + OVERLAP
    )
    middle = _font_geometry.rectangle(
        x_min, cell_bottom - OVERLAP, x_max, cell_top + OVERLAP
    )
    end_bar = _font_geometry.rectangle(x_min, seam - OVERLAP, x_max, cell_top + OVERLAP)
    start = pathops.op(top_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, bottom_cap, pathops.PathOp.UNION)
    return start, middle, end


def _stroke_profile(outline: pathops.Path, position: float) -> tuple[float, float]:
    def sample(sample_position: float) -> tuple[float, float]:
        half_slice = 0.01
        clip = _font_geometry.rectangle(
            sample_position - half_slice,
            -4096,
            sample_position + half_slice,
            4096,
        )
        clipped = pathops.op(outline, clip, pathops.PathOp.INTERSECTION)
        _, low, _, high = clipped.bounds
        if high <= low:
            raise ValueError("Could not derive a non-empty stroke profile")
        return (low + high) / 2, (high - low) / 2

    try:
        return sample(position)
    except ValueError:
        x_min, _, x_max, _ = outline.bounds
        start_distance = position - x_min
        end_distance = x_max - position
        edge_distance = min(start_distance, end_distance)
        if not 0 <= edge_distance < 20:
            raise
        direction = 1 if start_distance <= end_distance else -1
        center, half_width = sample(position + direction * (20 - edge_distance))
        progress = edge_distance / 20
        width_scale = progress * progress * (3 - 2 * progress)
        return center, half_width * width_scale


def _blend_connected_outlines(
    start: pathops.Path,
    end: pathops.Path,
    advance: int,
    *,
    middle: pathops.Path | None = None,
) -> pathops.Path:
    outlines = (start, end) if middle is None else (start, middle, end)
    core_start = max(0.0, *(outline.bounds[0] for outline in outlines))
    core_end = min(float(advance), *(outline.bounds[2] for outline in outlines))
    if core_end <= core_start:
        raise ValueError("Connected transition outlines do not overlap")
    drawing_start = core_start - OVERLAP if core_start == 0 else core_start
    drawing_end = core_end + OVERLAP if core_end == advance else core_end

    def smoothstep(progress: float) -> float:
        return progress * progress * (3 - 2 * progress)

    def profile_at(position: float) -> tuple[float, float]:
        progress = (position - core_start) / (core_end - core_start)
        if middle is None:
            first, second = start, end
            blend = smoothstep(progress)
        elif progress <= 0.5:
            first, second = start, middle
            blend = smoothstep(progress * 2)
        else:
            first, second = middle, end
            blend = smoothstep((progress - 0.5) * 2)
        first_center, first_width = _stroke_profile(first, position)
        second_center, second_width = _stroke_profile(second, position)
        return (
            first_center + (second_center - first_center) * blend,
            first_width + (second_width - first_width) * blend,
        )

    derivative_step = min(0.25, (core_end - core_start) / 1000)

    def core_edge(position: float, side: int) -> float:
        center, half_width = profile_at(position)
        return center + side * half_width

    def core_slope(position: float, side: int) -> float:
        before = max(core_start, position - derivative_step)
        after = min(core_end, position + derivative_step)
        if after == before:
            return 0
        return (core_edge(after, side) - core_edge(before, side)) / (after - before)

    def edge_at(position: float, side: int) -> tuple[float, float]:
        if position < core_start:
            slope = core_slope(core_start, side)
            return (
                core_edge(core_start, side) + slope * (position - core_start),
                slope,
            )
        if position > core_end:
            slope = core_slope(core_end, side)
            return (
                core_edge(core_end, side) + slope * (position - core_end),
                slope,
            )
        return core_edge(position, side), core_slope(position, side)

    positions = [
        core_start + (core_end - core_start) * index / LINEAR_WAVE_TRANSITION_SEGMENTS
        for index in range(LINEAR_WAVE_TRANSITION_SEGMENTS + 1)
    ]
    if drawing_start < core_start:
        positions.insert(0, drawing_start)
    if drawing_end > core_end:
        positions.append(drawing_end)

    def edge_points(side: int) -> list[tuple[int, int, float]]:
        points = []
        for position in positions:
            value, slope = edge_at(position, side)
            points.append((round(position), round(value), slope))
        return points

    upper = edge_points(1)
    lower = edge_points(-1)
    transition = pathops.Path()
    pen = transition.getPen()
    pen.moveTo(upper[0][:2])
    for first, second in zip(upper, upper[1:]):
        handle = max(1, round((second[0] - first[0]) / 3))
        pen.curveTo(
            (first[0] + handle, first[1] + round(first[2] * handle)),
            (second[0] - handle, second[1] - round(second[2] * handle)),
            second[:2],
        )
    pen.lineTo(lower[-1][:2])
    for first, second in zip(reversed(lower), reversed(lower[:-1])):
        handle = max(1, round((first[0] - second[0]) / 3))
        pen.curveTo(
            (first[0] - handle, first[1] - round(first[2] * handle)),
            (second[0] + handle, second[1] + round(second[2] * handle)),
            second[:2],
        )
    pen.closePath()
    return transition


def _vertical_transition_transform(vertical_origin: int) -> Transform:
    return Transform(0, 1, -1, 0, vertical_origin, 0)


def _transition_family_parts(
    linear_middle: pathops.Path,
    wave_start: pathops.Path,
    wave_middles: Sequence[pathops.Path],
    wave_end: pathops.Path,
    advance: int,
) -> tuple[pathops.Path, ...]:
    return (
        _blend_connected_outlines(linear_middle, wave_middles[0], advance),
        _blend_connected_outlines(linear_middle, wave_end, advance),
        _blend_connected_outlines(
            linear_middle,
            linear_middle,
            advance,
            middle=wave_middles[0],
        ),
        _blend_connected_outlines(wave_start, linear_middle, advance),
        *(
            _blend_connected_outlines(wave_middle, linear_middle, advance)
            for wave_middle in wave_middles
        ),
    )


def make_linear_wave_transition_parts(
    linear_parts: Sequence[pathops.Path],
    wave_parts: Sequence[pathops.Path],
    advance: int,
    vertical_origin: int,
) -> tuple[pathops.Path, ...]:
    if len(linear_parts) != NEW_GLYPH_COUNT:
        raise ValueError("Linear transition input must contain six parts")

    horizontal_linear = linear_parts[1]
    horizontal = _transition_family_parts(
        horizontal_linear,
        wave_parts[0],
        wave_parts[1:3],
        wave_parts[3],
        advance,
    )
    vertical_transform = _vertical_transition_transform(vertical_origin)
    vertical_linear = _font_geometry.transform_path(linear_parts[4], vertical_transform)
    vertical_family = tuple(
        _font_geometry.transform_path(wave_parts[5 + index], vertical_transform)
        for index in range(5)
    )
    vertical = _transition_family_parts(
        vertical_linear,
        vertical_family[0],
        vertical_family[1:3],
        vertical_family[3],
        advance,
    )
    inverse_vertical_transform = vertical_transform.inverse()
    vertical = tuple(
        _font_geometry.transform_path(part, inverse_vertical_transform)
        for part in vertical
    )
    parts = (*horizontal, *vertical)
    if len(parts) != LINEAR_WAVE_TRANSITION_GLYPH_COUNT:
        raise AssertionError("Unexpected linear-wave transition glyph count")
    return parts


def make_linear_manga_transition_parts(
    linear_parts: Sequence[pathops.Path],
    manga_parts: Sequence[pathops.Path],
    advance: int,
    vertical_origin: int,
) -> tuple[pathops.Path, ...]:
    if len(linear_parts) != NEW_GLYPH_COUNT:
        raise ValueError("Linear transition input must contain six parts")
    if len(manga_parts) != MANGA_WAVE_GLYPH_COUNT:
        raise ValueError("Manga wave transition input must contain eleven parts")

    horizontal = _transition_family_parts(
        linear_parts[1],
        manga_parts[0],
        manga_parts[1:2],
        manga_parts[2],
        advance,
    )
    vertical_transform = _vertical_transition_transform(vertical_origin)
    vertical_linear = _font_geometry.transform_path(linear_parts[4], vertical_transform)
    vertical_family = tuple(
        _font_geometry.transform_path(manga_parts[index], vertical_transform)
        for index in (6, 7, 8)
    )
    vertical = _transition_family_parts(
        vertical_linear,
        vertical_family[0],
        vertical_family[1:2],
        vertical_family[2],
        advance,
    )
    inverse_vertical_transform = vertical_transform.inverse()
    vertical = tuple(
        _font_geometry.transform_path(part, inverse_vertical_transform)
        for part in vertical
    )
    parts = (*horizontal, *vertical)
    if len(parts) != LINEAR_MANGA_TRANSITION_GLYPH_COUNT:
        raise AssertionError("Unexpected linear-manga transition glyph count")
    return parts


def make_sine_wave_tile(
    source: pathops.Path,
    advance: int,
    *,
    inverted: bool = False,
    taper_start: bool = False,
    taper_end: bool = False,
    half_waves: float = 3,
    phase_offset_half_waves: float = 0,
    end_half_waves: float | None = None,
    amplitude_scale: float = 1,
    terminal_phase_extension_half_waves: float = (WAVE_TERMINAL_EXTENSION_HALF_WAVES),
    taper_fraction: float = 1 / 4,
    start_margin: float = 0,
    end_margin: float = 0,
    sample_peak_position: float | None = None,
    sample_trough_position: float | None = None,
    start_stroke_scale: float = 1,
    end_stroke_scale: float | None = None,
) -> pathops.Path:
    if sample_peak_position is None:
        sample_peak_position = advance / 4
    if sample_trough_position is None:
        sample_trough_position = 3 * advance / 4
    sample_peak_min, sample_peak_max = stroke_band(
        source, "horizontal", sample_peak_position
    )
    sample_trough_min, sample_trough_max = stroke_band(
        source, "horizontal", sample_trough_position
    )
    sample_crossing_min, sample_crossing_max = stroke_band(
        source,
        "horizontal",
        (sample_peak_position + sample_trough_position) / 2,
    )
    peak_center = (sample_peak_min + sample_peak_max) / 2
    trough_center = (sample_trough_min + sample_trough_max) / 2
    baseline = (peak_center + trough_center) / 2
    amplitude = (peak_center - trough_center) / 2 * amplitude_scale
    thickness = (
        (sample_peak_max - sample_peak_min) + (sample_trough_max - sample_trough_min)
    ) / 2
    crossing_thickness = sample_crossing_max - sample_crossing_min
    direction = -1 if inverted else 1
    final_stroke_scale = (
        start_stroke_scale if end_stroke_scale is None else end_stroke_scale
    )
    if start_stroke_scale <= 0 or final_stroke_scale <= 0:
        raise ValueError("Wave stroke scales must be positive")
    final_half_waves = half_waves if end_half_waves is None else end_half_waves
    taper_length = advance * taper_fraction
    core_start = start_margin if taper_start else 0.0
    core_end = advance - end_margin if taper_end else float(advance)
    drawing_start = core_start if taper_start else core_start - OVERLAP
    drawing_end = core_end if taper_end else core_end + OVERLAP
    start_taper_length = taper_length - core_start
    end_taper_length = core_end - (advance - taper_length)

    terminal_phase_extension = terminal_phase_extension_half_waves * math.pi

    def smoothstep(progress: float) -> float:
        return progress * progress * (3 - 2 * progress)

    def smootherstep(progress: float) -> float:
        return 6 * progress**5 - 15 * progress**4 + 10 * progress**3

    def smootherstep_derivative(progress: float) -> float:
        return 30 * progress**2 * (progress - 1) ** 2

    def phase_at(position: float) -> tuple[float, float]:
        progress = position / advance
        transition_integral = progress**3 - progress**4 / 2
        phase = phase_offset_half_waves * math.pi + math.pi * (
            half_waves * progress
            + (final_half_waves - half_waves) * transition_integral
        )
        phase_velocity = (
            math.pi
            / advance
            * (half_waves + (final_half_waves - half_waves) * smoothstep(progress))
        )
        correction_start = taper_length
        correction_end = advance - taper_length
        correction_length = correction_end - correction_start
        if taper_start:
            if position <= correction_start:
                phase -= terminal_phase_extension
            elif position < correction_end:
                progress = (position - correction_start) / correction_length
                phase -= terminal_phase_extension * (1 - smootherstep(progress))
                phase_velocity += (
                    terminal_phase_extension
                    * smootherstep_derivative(progress)
                    / correction_length
                )
        if taper_end:
            if position >= correction_end:
                phase += terminal_phase_extension
            elif position > correction_start:
                progress = (position - correction_start) / correction_length
                phase += terminal_phase_extension * smootherstep(progress)
                phase_velocity += (
                    terminal_phase_extension
                    * smootherstep_derivative(progress)
                    / correction_length
                )
        return phase, phase_velocity

    def width_at(position: float) -> float:
        progress = min(1.0, max(0.0, position / advance))
        stroke_scale = start_stroke_scale + (
            final_stroke_scale - start_stroke_scale
        ) * smoothstep(progress)
        scale = stroke_scale
        if taper_start:
            progress = min(
                1.0,
                max(
                    0.0,
                    (position - drawing_start) / start_taper_length,
                ),
            )
            scale *= smoothstep(progress)
        if taper_end:
            progress = min(
                1.0,
                max(0.0, (drawing_end - position) / end_taper_length),
            )
            scale *= smoothstep(progress)
        phase, _ = phase_at(position)
        phase_thickness = thickness + (
            crossing_thickness - thickness
        ) * WAVE_STROKE_MODULATION * abs(math.cos(phase))
        return phase_thickness / 2 * scale

    breakpoints = {drawing_start, drawing_end}
    if taper_start:
        breakpoints.add(taper_length)
    if taper_end:
        breakpoints.add(advance - taper_length)
    phase_start, _ = phase_at(drawing_start)
    phase_end, _ = phase_at(drawing_end)
    quarter_wave = math.pi / 2
    first_quarter = math.floor(phase_start / quarter_wave) + 1
    last_quarter = math.ceil(phase_end / quarter_wave)
    for index in range(first_quarter, last_quarter):
        target = index * quarter_wave
        lower = drawing_start
        upper = drawing_end
        for _ in range(32):
            middle = (lower + upper) / 2
            middle_phase, _ = phase_at(middle)
            if middle_phase < target:
                lower = middle
            else:
                upper = middle
        breakpoints.add((lower + upper) / 2)

    points: list[tuple[float, float, float, bool]] = []
    for position in sorted(breakpoints):
        phase, phase_velocity = phase_at(position)
        center = baseline + direction * amplitude * math.sin(phase)
        sine_slope = direction * amplitude * phase_velocity * math.cos(phase)
        points.append((position, center, sine_slope, abs(sine_slope) < 1e-9))

    segments = []
    for start, end in zip(points, points[1:]):
        length = end[0] - start[0]
        start_handle = length * (0.42 if start[3] else 1 / 3)
        end_handle = length * (0.42 if end[3] else 1 / 3)
        control_1 = (
            start[0] + start_handle,
            start[1] + start[2] * start_handle,
        )
        control_2 = (
            end[0] - end_handle,
            end[1] - end[2] * end_handle,
        )
        segments.append((control_1, control_2, (end[0], end[1])))

    tile = pathops.Path()
    pen = tile.getPen()
    pen.moveTo((drawing_start, points[0][1] + width_at(drawing_start)))
    for control_1, control_2, endpoint in segments:
        pen.curveTo(
            (control_1[0], control_1[1] + width_at(control_1[0])),
            (control_2[0], control_2[1] + width_at(control_2[0])),
            (endpoint[0], endpoint[1] + width_at(endpoint[0])),
        )
    pen.lineTo((drawing_end, points[-1][1] - width_at(drawing_end)))
    for index in range(len(segments) - 1, -1, -1):
        control_1, control_2, _ = segments[index]
        start = points[index]
        pen.curveTo(
            (control_2[0], control_2[1] - width_at(control_2[0])),
            (control_1[0], control_1[1] - width_at(control_1[0])),
            (start[0], start[1] - width_at(start[0])),
        )
    pen.closePath()
    return tile


def _wave_stroke_scale(
    source: pathops.Path,
    advance: int,
    target: float,
    *,
    half_waves: float,
    phase_offset_half_waves: float,
    amplitude_scale: float = 1,
) -> float:
    lower, upper = 0.25, 4.0
    for _ in range(24):
        scale = (lower + upper) / 2
        outline = make_sine_wave_tile(
            source,
            advance,
            half_waves=half_waves,
            phase_offset_half_waves=phase_offset_half_waves,
            amplitude_scale=amplitude_scale,
            terminal_phase_extension_half_waves=0,
            start_stroke_scale=scale,
        )
        if _font_geometry.optical_stroke_width(outline) < target:
            lower = scale
        else:
            upper = scale
    return (lower + upper) / 2


def _oriented_wave_stroke_scales(
    source: pathops.Path,
    advance: int,
    widths: ConnectedStrokeWidths,
    *,
    half_waves: float,
    phase_offset_half_waves: float,
    amplitude_scale: float = 1,
) -> OrientedStrokeScales:
    return OrientedStrokeScales(
        *(
            _wave_stroke_scale(
                source,
                advance,
                target,
                half_waves=half_waves,
                phase_offset_half_waves=phase_offset_half_waves,
                amplitude_scale=amplitude_scale,
            )
            for target in (widths.horizontal, widths.vertical)
        )
    )


def make_wave_stroke_model(
    source: pathops.Path,
    advance: int,
    widths: ConnectedStrokeWidths,
) -> WaveStrokeModel:
    return WaveStrokeModel(
        default=_oriented_wave_stroke_scales(
            source,
            advance,
            widths,
            half_waves=3,
            phase_offset_half_waves=-0.5,
        ),
        relaxed=_oriented_wave_stroke_scales(
            source,
            advance,
            widths,
            half_waves=2.5,
            phase_offset_half_waves=-0.25,
        ),
        one_cycle=_oriented_wave_stroke_scales(
            source,
            advance,
            widths,
            half_waves=2,
            phase_offset_half_waves=-0.5,
            amplitude_scale=1.2,
        ),
        manga=_oriented_wave_stroke_scales(
            source,
            advance,
            widths,
            half_waves=4,
            phase_offset_half_waves=0,
        ),
    )


def _vertical_wave_parts(
    outlines: Sequence[pathops.Path],
    advance: int,
    vertical_origin: int,
    center_y: float,
) -> tuple[pathops.Path, ...]:
    rotation = Transform(
        0,
        -1,
        -1,
        0,
        advance / 2 + center_y,
        vertical_origin,
    )
    return tuple(
        _font_geometry.transform_path(outline, rotation) for outline in outlines
    )


def make_wave_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, ...]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)

    def variants(scale: float) -> tuple[pathops.Path, ...]:
        def tile(
            *,
            inverted: bool = False,
            taper_start: bool = False,
            taper_end: bool = False,
        ) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                half_waves=3,
                phase_offset_half_waves=-0.5,
                terminal_phase_extension_half_waves=0,
                start_stroke_scale=scale,
                inverted=inverted,
                taper_start=taper_start,
                taper_end=taper_end,
                start_margin=start_margin,
                end_margin=end_margin,
            )

        return (
            tile(taper_start=True),
            tile(),
            tile(inverted=True),
            tile(taper_end=True),
            tile(inverted=True, taper_end=True),
        )

    scales = (
        stroke_model.default if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(scales.horizontal)
    vertical_source = (
        horizontal
        if scales.vertical == scales.horizontal
        else variants(scales.vertical)
    )
    center_y = (horizontal[1].bounds[1] + horizontal[1].bounds[3]) / 2
    return horizontal + _vertical_wave_parts(
        vertical_source, advance, vertical_origin, center_y
    )


def make_manga_to_wave_transition_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, ...]:
    _, _, source_x_max, _ = source.bounds
    end_margin = max(0.0, advance - source_x_max)

    def variants(start_scale: float, end_scale: float) -> tuple[pathops.Path, ...]:
        def transition(*, inverted: bool, taper_end: bool) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                inverted=inverted,
                taper_end=taper_end,
                end_margin=end_margin if taper_end else 0,
                half_waves=4,
                end_half_waves=3,
                terminal_phase_extension_half_waves=0,
                start_stroke_scale=start_scale,
                end_stroke_scale=end_scale,
            )

        return (
            transition(inverted=False, taper_end=False),
            transition(inverted=False, taper_end=True),
            transition(inverted=True, taper_end=False),
            transition(inverted=True, taper_end=True),
        )

    manga_scales = (
        stroke_model.manga if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    wave_scales = (
        stroke_model.default if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(manga_scales.horizontal, wave_scales.horizontal)
    vertical_source = variants(manga_scales.vertical, wave_scales.vertical)
    center_y = (horizontal[0].bounds[1] + horizontal[0].bounds[3]) / 2
    return horizontal + _vertical_wave_parts(
        vertical_source, advance, vertical_origin, center_y
    )


def make_wave_to_manga_transition_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, ...]:
    _, _, source_x_max, _ = source.bounds
    end_margin = max(0.0, advance - source_x_max)

    def variants(start_scale: float, end_scale: float) -> tuple[pathops.Path, ...]:
        def transition(phase_offset: float, *, taper_end: bool) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                taper_end=taper_end,
                end_margin=end_margin if taper_end else 0,
                half_waves=3,
                end_half_waves=4,
                phase_offset_half_waves=phase_offset,
                taper_fraction=1 / 6,
                start_stroke_scale=start_scale,
                end_stroke_scale=end_scale,
            )

        return (
            transition(0.5, taper_end=False),
            transition(0.5, taper_end=True),
            transition(-0.5, taper_end=False),
            transition(-0.5, taper_end=True),
        )

    wave_scales = (
        stroke_model.default if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    manga_scales = (
        stroke_model.manga if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(wave_scales.horizontal, manga_scales.horizontal)
    vertical_source = variants(wave_scales.vertical, manga_scales.vertical)
    center_y = (horizontal[0].bounds[1] + horizontal[0].bounds[3]) / 2
    return horizontal + _vertical_wave_parts(
        vertical_source, advance, vertical_origin, center_y
    )


def make_relaxed_wave_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, ...]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)
    phase_offsets = (-0.25, 0.25, 0.75, 1.25)

    def variants(scale: float) -> tuple[pathops.Path, ...]:
        def wave(
            phase_offset: float,
            *,
            taper_start: bool = False,
            taper_end: bool = False,
        ) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                taper_start=taper_start,
                taper_end=taper_end,
                start_margin=start_margin if taper_start else 0,
                end_margin=end_margin if taper_end else 0,
                half_waves=2.5,
                phase_offset_half_waves=phase_offset,
                terminal_phase_extension_half_waves=0,
                start_stroke_scale=scale,
            )

        return (
            wave(phase_offsets[0], taper_start=True, taper_end=True),
            wave(phase_offsets[0], taper_start=True),
            *(wave(phase_offset) for phase_offset in phase_offsets),
            *(wave(phase_offset, taper_end=True) for phase_offset in phase_offsets),
        )

    scales = (
        stroke_model.relaxed if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(scales.horizontal)
    vertical_source = (
        horizontal
        if scales.vertical == scales.horizontal
        else variants(scales.vertical)
    )
    center_y = (horizontal[2].bounds[1] + horizontal[2].bounds[3]) / 2
    return horizontal + _vertical_wave_parts(
        vertical_source, advance, vertical_origin, center_y
    )


def make_one_cycle_wave_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, ...]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)

    def variants(scale: float) -> tuple[pathops.Path, ...]:
        def wave(
            *,
            taper_start: bool = False,
            taper_end: bool = False,
        ) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                taper_start=taper_start,
                taper_end=taper_end,
                start_margin=start_margin if taper_start else 0,
                end_margin=end_margin if taper_end else 0,
                half_waves=2,
                amplitude_scale=1.2,
                phase_offset_half_waves=-0.5,
                terminal_phase_extension_half_waves=0,
                taper_fraction=1 / 6,
                start_stroke_scale=scale,
            )

        return (
            wave(taper_start=True, taper_end=True),
            wave(taper_start=True),
            wave(),
            wave(taper_end=True),
        )

    scales = (
        stroke_model.one_cycle
        if stroke_model is not None
        else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(scales.horizontal)
    vertical_source = (
        horizontal
        if scales.vertical == scales.horizontal
        else variants(scales.vertical)
    )
    center_y = (horizontal[2].bounds[1] + horizontal[2].bounds[3]) / 2
    return horizontal + _vertical_wave_parts(
        vertical_source, advance, vertical_origin, center_y
    )


def make_manga_wave_parts(
    source: pathops.Path,
    advance: int,
    vertical_origin: int,
    stroke_model: WaveStrokeModel | None = None,
) -> tuple[pathops.Path, tuple[pathops.Path, ...]]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)

    def variants(scale: float) -> tuple[pathops.Path, ...]:
        def wave(
            *,
            inverted: bool = False,
            taper_start: bool = False,
            taper_end: bool = False,
        ) -> pathops.Path:
            return make_sine_wave_tile(
                source,
                advance,
                inverted=inverted,
                taper_start=taper_start,
                taper_end=taper_end,
                start_margin=start_margin if taper_start else 0,
                end_margin=end_margin if taper_end else 0,
                half_waves=4,
                taper_fraction=1 / 6,
                start_stroke_scale=scale,
            )

        return (
            wave(taper_start=True, taper_end=True),
            wave(taper_start=True),
            wave(),
            wave(taper_end=True),
            wave(inverted=True),
            wave(inverted=True, taper_end=True),
        )

    scales = (
        stroke_model.manga if stroke_model is not None else OrientedStrokeScales(1, 1)
    )
    horizontal = variants(scales.horizontal)
    vertical_source = (
        horizontal
        if scales.vertical == scales.horizontal
        else variants(scales.vertical)
    )
    center_y = (horizontal[2].bounds[1] + horizontal[2].bounds[3]) / 2
    vertical = _vertical_wave_parts(vertical_source, advance, vertical_origin, center_y)
    added = (*horizontal[1:], *vertical)
    return horizontal[0], added


def add_linear_extension(
    font: TTFont,
    base: str,
    names: list[str],
    stroke_widths: ConnectedStrokeWidths,
    *,
    flatten_horizontal: bool = False,
) -> tuple[str, list[str], tuple[pathops.Path, ...]]:
    vertical = _font_operations.find_vertical_glyph(font, base)
    advance = font["hmtx"].metrics[base][0]
    if advance != 1000:
        raise ValueError(f"Expected a 1000-unit full-width glyph, got {advance}")

    horizontal_outline = _font_geometry.glyph_path(font, base)
    if flatten_horizontal:
        horizontal_outline = flatten_horizontal_centerline(horizontal_outline, advance)
    horizontal_outline = normalize_linear_stroke_width(
        horizontal_outline,
        "horizontal",
        advance / 2,
        advance,
        stroke_widths.horizontal,
    )
    horizontal_parts = make_horizontal_parts(horizontal_outline, advance)
    _, _, _, vertical_y_max = _font_geometry.bounds(font, vertical)
    vertical_origin = round(font["vmtx"].metrics[vertical][1] + vertical_y_max)
    vertical_outline = normalize_linear_stroke_width(
        _font_geometry.glyph_path(font, vertical),
        "vertical",
        advance * 0.4,
        advance,
        stroke_widths.vertical,
    )
    vertical_parts = make_vertical_parts(vertical_outline, advance, vertical_origin)
    _font_operations.append_glyphs(
        font,
        list(horizontal_parts + vertical_parts),
        names,
        base,
        vertical_origin,
    )
    return vertical, names, horizontal_parts + vertical_parts


def mark_ligature_rules(
    cmap: Mapping[int, str],
    pairs: Sequence[_mark_positioning.MarkPair],
    outputs: Mapping[_mark_positioning.MarkPair, str],
    mark_inputs: Mapping[int, int],
) -> list[tuple[str, str, str]]:
    return [
        (cmap[base], cmap[mark_inputs[mark]], outputs[(base, mark)])
        for base, mark in pairs
    ]


def autohint_latin_glyphs(
    output_path: Path,
    glyph_names: tuple[str, ...],
    executable: str | None = None,
) -> None:
    """Autohint imported CFF glyphs without touching native Japanese glyphs."""

    if not glyph_names:
        return
    command = executable or shutil.which("otfautohint")
    if command is None:
        raise RuntimeError("--autohint requires the AFDKO otfautohint command on PATH")
    with TemporaryDirectory(
        prefix=f".{output_path.stem}-autohint-",
        dir=output_path.parent,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        glyph_list_path = temporary_path / "glyphs.txt"
        hinted_path = temporary_path / output_path.name
        glyph_list_path.write_text(",".join(glyph_names), encoding="utf-8")
        subprocess.run(
            [
                command,
                "--glyphs-file",
                str(glyph_list_path),
                "--output",
                str(hinted_path),
                str(output_path),
            ],
            check=True,
        )
        hinted_path.replace(output_path)


def _rename_release_font(
    font: TTFont,
    latin_font: TTFont | None,
    latin_profile: LatinBuildProfile,
    identity: FontIdentity,
) -> None:
    """Apply release naming and notices after all source outlines are present."""

    latin_copyright = (
        (latin_font["name"].getDebugName(0) or latin_profile.copyright)
        if latin_font
        else None
    )
    latin_license = latin_font["name"].getDebugName(13) if latin_font else None
    copyright_notices = [
        notice
        for notice in (
            font["name"].getDebugName(0),
            latin_copyright,
            SHIPPORI_COPYRIGHT,
        )
        if notice
    ]
    copyright_notice = " / ".join(dict.fromkeys(copyright_notices))
    source_notice = (
        getattr(font["CFF "].cff.topDictIndex[0], "Notice", None)
        if "CFF " in font
        else font["name"].getDebugName(13)
    )
    font_notices = [
        notice
        for notice in (
            source_notice,
            latin_license,
            SHIPPORI_COPYRIGHT,
        )
        if notice
    ]
    font_notice = " / ".join(dict.fromkeys(font_notices))
    rename_font(font, copyright_notice, font_notice, identity)


def _normalize_cff_blue_zones(font: TTFont) -> None:
    """Keep instantiated CFF hint zones valid when variable pairs cross."""

    top = font["CFF "].cff.topDictIndex[0]
    for font_dict in top.FDArray:
        private = font_dict.Private
        for attribute in (
            "BlueValues",
            "OtherBlues",
            "FamilyBlues",
            "FamilyOtherBlues",
        ):
            values = getattr(private, attribute, None)
            if values is None:
                continue
            if len(values) % 2:
                raise ValueError(f"CFF {attribute} must contain coordinate pairs")
            normalized = [
                coordinate
                for index in range(0, len(values), 2)
                for coordinate in sorted(values[index : index + 2])
            ]
            setattr(private, attribute, normalized)


def build_static_instance(
    variable_source_path: Path,
    latin_source_path: Path | None,
    output_path: Path,
    identity: FontIdentity,
    latin_profile: LatinBuildProfile,
    autohint: bool = False,
    customize: Callable[[TTFont], None] | None = None,
) -> None:
    """Instance customized CFF2, then apply work that remains static-only."""

    font = TTFont(
        variable_source_path,
        recalcTimestamp=True,
        recalcBBoxes=False,
    )
    if "CFF2" not in font or "fvar" not in font:
        raise ValueError("Static instances require a customized CFF2 variable source")
    axes = font["fvar"].axes
    if len(axes) != 1 or axes[0].axisTag != "wght":
        raise ValueError("Static instances require exactly one wght axis")
    axis = axes[0]
    if not axis.minValue <= identity.weight_class <= axis.maxValue:
        raise ValueError(
            f"Weight {identity.weight_class} is outside the source wght range "
            f"{axis.minValue:g}–{axis.maxValue:g}"
        )
    if autohint and latin_source_path is None:
        raise ValueError("--autohint requires an imported Latin source")

    instantiateVariableFont(
        font,
        {"wght": identity.weight_class},
        inplace=True,
    )
    convertCFF2ToCFF(font)
    _normalize_cff_blue_zones(font)
    static_data = BytesIO()
    font.save(static_data, reorderTables=True)
    static_data.seek(0)
    font = TTFont(static_data, recalcTimestamp=True)
    if customize is not None:
        customize(font)

    latin_font = TTFont(latin_source_path) if latin_source_path else None
    if latin_font and latin_profile.variations:
        if "fvar" not in latin_font:
            raise ValueError(f"{latin_profile.family} requires a variable Latin source")
        instantiateVariableFont(
            latin_font,
            dict(latin_profile.variations),
            inplace=True,
        )
    if latin_font and latin_font["head"].unitsPerEm != font["head"].unitsPerEm:
        scale_upem(latin_font, font["head"].unitsPerEm)
    latin_import = (
        _font_operations.import_latin_font(font, latin_font, latin_profile)
        if latin_font is not None
        else None
    )
    _rename_release_font(font, latin_font, latin_profile, identity)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path, reorderTables=True)
    if autohint and latin_import is not None:
        autohint_latin_glyphs(output_path, latin_import.glyph_names)


def build_novel_static_instance(
    variable_source_path: Path,
    latin_source_path: Path | None,
    output_path: Path,
    identity: FontIdentity,
    latin_profile: LatinBuildProfile,
    autohint: bool = False,
) -> None:
    """Instance a Novel CFF2 source, then apply its remaining static work."""

    if identity.family != "Nobigoe Novel Mincho":
        raise ValueError("Novel static instances require a Novel font identity")

    build_static_instance(
        variable_source_path,
        latin_source_path,
        output_path,
        identity,
        latin_profile,
        autohint,
        apply_novel_han,
    )


def build(
    source_path: Path,
    latin_source_path: Path | None,
    punctuation_source_path: Path,
    output_path: Path,
    identity: FontIdentity,
    latin_profile: LatinBuildProfile,
    face: int,
    base_type: BaseType,
    autohint: bool = False,
    kana_style: KanaStyle = "noto",
    han_brush_elements: bool = False,
    han_brush_end_profile: VerticalEndProfile = DEFAULT_VERTICAL_END_PROFILE,
) -> None:
    if kana_style not in {"noto", "novel"}:
        raise ValueError(f"Unknown kana style {kana_style!r}")
    if han_brush_end_profile not in VERTICAL_END_PROFILES:
        raise ValueError(f"Unknown Han brush end profile {han_brush_end_profile!r}")
    if not han_brush_elements and han_brush_end_profile != DEFAULT_VERTICAL_END_PROFILE:
        raise ValueError("--han-brush-end-profile requires --han-brush-elements")
    if kana_style == "novel" and base_type != "noto":
        raise ValueError("--kana-style novel requires --base noto")
    if han_brush_elements and base_type != "noto":
        raise ValueError("--han-brush-elements requires --base noto")
    if autohint and latin_source_path is None:
        raise ValueError("--autohint requires an imported Latin source")
    font = TTFont(source_path, fontNumber=face, recalcTimestamp=True)
    if font["head"].unitsPerEm != 1000:
        scale_upem(font, 1000)
    latin_font = TTFont(latin_source_path) if latin_source_path else None
    if latin_font and latin_profile.family == "stix-two-text":
        stix_source = latin_font
        try:
            latin_font = instantiate_stix_latin_font(
                stix_source,
                identity.weight_class,
            )
        finally:
            stix_source.close()
        if "fvar" in latin_font or any(
            getattr(latin_font[tag].table, "FeatureVariations", None) is not None
            for tag in ("GSUB", "GPOS")
            if tag in latin_font
        ):
            raise ValueError(
                "STIX Latin instantiation must produce a static font without "
                "fvar or FeatureVariations"
            )
    elif latin_font and latin_profile.variations:
        if "fvar" not in latin_font:
            raise ValueError(
                f"{latin_profile.family} requires a variable --latin-source"
            )
        instantiateVariableFont(
            latin_font,
            dict(latin_profile.variations),
            inplace=True,
        )
    if latin_font and latin_font["head"].unitsPerEm != 1000:
        scale_upem(latin_font, 1000)
    punctuation_font = TTFont(punctuation_source_path)
    cmap = font.getBestCmap()
    punctuation_cmap = punctuation_font.getBestCmap()
    punctuation_missing = [
        f"U+{codepoint:04X}"
        for codepoint in (
            *SHIPPORI_UPRIGHT_PUNCTUATION.values(),
            *SHIPPORI_UPRIGHT_EXCLAMATIONS.values(),
            *SHIPPORI_PRECOMPOSED_LIGATURES.values(),
        )
        if codepoint not in punctuation_cmap
    ]
    if punctuation_missing:
        raise ValueError(
            "The punctuation source does not contain " + ", ".join(punctuation_missing)
        )
    upright_punctuation = shippori_upright_punctuation_paths(punctuation_font)
    if punctuation_font["head"].unitsPerEm != font["head"].unitsPerEm:
        raise ValueError(
            "The base and punctuation sources must use the same " "units per em"
        )
    linear_codepoints = [("choon", 0x30FC), ("dash", 0x2015)]
    required_codepoints = [codepoint for _, codepoint in linear_codepoints]
    required_codepoints.extend(
        [
            0x21,
            0x3F,
            0x301C,
            0x3030,
            0x3099,
            0x309A,
            0x309B,
            0x309C,
            0xFF01,
            0xFF1F,
            0xFF5E,
        ]
    )
    required_codepoints.extend(
        base
        for base, _ in _mark_positioning.MANGA_MARK_PAIRS
        if base not in _mark_positioning.MANGA_MISSING_SMALL_KANA
    )
    required_codepoints.extend(
        base for base, _ in _mark_positioning.KOBURI_HEART_MARK_PAIRS
    )
    missing = [
        f"U+{codepoint:04X}"
        for codepoint in dict.fromkeys(required_codepoints)
        if codepoint not in cmap
    ]
    if missing:
        raise ValueError(f"The source font does not contain {', '.join(missing)}")
    if cmap[0x301C] != cmap[0xFF5E]:
        raise ValueError("U+301C and U+FF5E must share a source glyph")

    if len(_mark_positioning.MANGA_MARK_PAIRS) != 191:
        raise AssertionError("Expected 191 Manga1 kana mark sequences")
    if len(_mark_positioning.MANGA_VERTICAL_MARK_PAIRS) != 53:
        raise AssertionError("Expected 53 vertical Manga1 kana mark sequences")
    if len(_mark_positioning.KOBURI_PUA_MARK_PAIRS) != 88:
        raise AssertionError("Expected 88 Koburi Mincho PUA mappings")
    if not set(_mark_positioning.KOBURI_PUA_MARK_PAIRS) <= set(
        _mark_positioning.MANGA_MARK_PAIRS
    ):
        raise AssertionError("Koburi Mincho PUA mappings must use Manga1 sequences")
    if len(_mark_positioning.KOBURI_GENERATED_MARK_PAIRS) != 103:
        raise AssertionError("Expected 103 generated Koburi mark sequences")
    if len(_mark_positioning.KOBURI_HEART_MARK_PAIRS) != 2:
        raise AssertionError("Expected two Koburi Mincho heart mappings")
    if len(_mark_positioning.PUNCTUATION_MARK_PAIRS) != 4:
        raise AssertionError("Expected four fullwidth punctuation mark sequences")

    latin_import = (
        _font_operations.import_latin_font(font, latin_font, latin_profile)
        if latin_font is not None
        else None
    )

    source_ccmp_ligatures = _font_operations.feature_ligatures(font, "ccmp")
    native_hiragana_ccmp_outputs: dict[tuple[int, int], str] = {}
    native_hiragana_vertical_ccmp_outputs: dict[tuple[int, int], str] = {}
    native_katakana_ccmp_outputs: dict[tuple[int, int], str] = {}
    native_katakana_vertical_ccmp_outputs: dict[tuple[int, int], str] = {}
    if kana_style == "novel":
        (
            native_hiragana_ccmp_outputs,
            native_hiragana_vertical_ccmp_outputs,
        ) = _native_novel_ccmp_outputs(
            font,
            cmap,
            source_ccmp_ligatures,
            HIRAGANA_CODEPOINTS,
        )
        (
            native_katakana_ccmp_outputs,
            native_katakana_vertical_ccmp_outputs,
        ) = _native_novel_ccmp_outputs(
            font,
            cmap,
            source_ccmp_ligatures,
            KATAKANA_SOURCE_CODEPOINTS,
        )
    supported_mark_pairs = (
        *_mark_positioning.MANGA_MARK_PAIRS,
        _mark_positioning.CHOON_DAKUTEN_PAIR,
    )
    native_mark_outputs: dict[tuple[int, int], str] = {}
    for base, mark in supported_mark_pairs:
        if base not in cmap:
            continue
        output = source_ccmp_ligatures.get((cmap[base], cmap[mark]))
        if output is not None:
            native_mark_outputs[(base, mark)] = output
    native_heart_outputs: dict[tuple[int, int], str] = {}
    for base, mark in _mark_positioning.KOBURI_HEART_MARK_PAIRS:
        output = source_ccmp_ligatures.get((cmap[base], cmap[mark]))
        if output is not None:
            native_heart_outputs[(base, mark)] = output
    if base_type == "koburi":
        actual_native_pairs = frozenset(native_mark_outputs) & frozenset(
            _mark_positioning.MANGA_MARK_PAIRS
        )
        if actual_native_pairs != _mark_positioning.KOBURI_NATIVE_MARK_PAIRS:
            missing = _mark_positioning.KOBURI_NATIVE_MARK_PAIRS - actual_native_pairs
            extra = actual_native_pairs - _mark_positioning.KOBURI_NATIVE_MARK_PAIRS
            details = [
                *(
                    f"missing U+{pair_base:04X}+U+{pair_mark:04X}"
                    for pair_base, pair_mark in sorted(missing)
                ),
                *(
                    f"extra U+{pair_base:04X}+U+{pair_mark:04X}"
                    for pair_base, pair_mark in sorted(extra)
                ),
            ]
            raise ValueError(
                "GenEi Koburi Mincho ccmp mappings must contain the "
                "expected 88 native mark sequences: " + ", ".join(details)
            )
        if _mark_positioning.CHOON_DAKUTEN_PAIR not in native_mark_outputs:
            raise ValueError(
                "GenEi Koburi Mincho ccmp mappings must contain " "U+30FC+U+3099"
            )
        if set(native_heart_outputs) != set(_mark_positioning.KOBURI_HEART_MARK_PAIRS):
            raise ValueError(
                "GenEi Koburi Mincho ccmp mappings must contain its "
                "two native heart-dakuten sequences"
            )
        for base_pua, output_pua, pair in zip(
            _mark_positioning.KOBURI_HEART_BASE_PUA,
            _mark_positioning.KOBURI_HEART_OUTPUT_PUA,
            _mark_positioning.KOBURI_HEART_MARK_PAIRS,
            strict=True,
        ):
            _, mark = pair
            native_output = native_heart_outputs[pair]
            if (
                base_pua not in cmap
                or output_pua not in cmap
                or source_ccmp_ligatures.get((cmap[base_pua], cmap[mark]))
                != native_output
                or cmap[output_pua] != native_output
            ):
                raise ValueError(
                    "GenEi Koburi Mincho heart PUA mappings must remain "
                    f"compatible for U+{base_pua:04X} and U+{output_pua:04X}"
                )
    mark_position_overrides = _mark_positioning.load_mark_position_overrides(
        base=base_type,
        weight=identity.style,
    )
    punctuation_mark_positions = _mark_positioning.load_punctuation_mark_positions(
        base=base_type,
        weight=identity.style,
    )
    generated_mark_pairs = [
        pair for pair in supported_mark_pairs if pair not in native_mark_outputs
    ]
    generated_vertical_mark_pairs = list(generated_mark_pairs)
    generated_heart_pairs = [
        pair
        for pair in _mark_positioning.KOBURI_HEART_MARK_PAIRS
        if pair not in native_heart_outputs
    ]
    reference_names = [
        cmap[codepoint] for codepoint in CONNECTED_STROKE_REFERENCE_CODEPOINTS
    ]
    reference_vertical_names = [
        _font_operations.vertical_glyph_or_self(font, name) for name in reference_names
    ]
    stroke_widths = connected_stroke_widths(
        [_font_geometry.glyph_path(font, name) for name in reference_names],
        [_font_geometry.glyph_path(font, name) for name in reference_vertical_names],
    )

    allocated_names = _font_operations.allocate_cid_names(
        font,
        NEW_GLYPH_COUNT * len(linear_codepoints)
        + WAVE_GLYPH_COUNT
        + RELAXED_WAVE_GLYPH_COUNT
        + ONE_CYCLE_WAVE_GLYPH_COUNT
        + LINEAR_WAVE_TRANSITION_GLYPH_COUNT * len(linear_codepoints)
        + LINEAR_MANGA_TRANSITION_GLYPH_COUNT * len(linear_codepoints)
        + MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT
        + WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
        + MANGA_WAVE_GLYPH_COUNT
        + len(MANGA_PUNCTUATION_SEQUENCES)
        + PUNCTUATION_ROTATED_COUNT
        + 2 * len(_mark_positioning.MANGA_MISSING_SMALL_KANA)
        + len(generated_mark_pairs)
        + len(generated_vertical_mark_pairs)
        + len(generated_heart_pairs)
        + 2 * len(_mark_positioning.PUNCTUATION_MARK_PAIRS),
    )
    extensions: list[tuple[str, str, str, list[str]]] = []
    linear_parts: list[tuple[pathops.Path, ...]] = []
    for index, (prefix, codepoint) in enumerate(linear_codepoints):
        base = cmap[codepoint]
        start = index * NEW_GLYPH_COUNT
        names = allocated_names[start : start + NEW_GLYPH_COUNT]
        vertical, names, parts = add_linear_extension(
            font,
            base,
            names,
            stroke_widths,
            flatten_horizontal=codepoint == 0x30FC,
        )
        linear_parts.append(parts)
        extensions.append((prefix, base, vertical, names))

    wave_base = cmap[0x301C]
    wave_vertical = _font_operations.find_vertical_glyph(font, wave_base)
    _, _, _, wave_vertical_y_max = _font_geometry.bounds(font, wave_vertical)
    wave_vertical_origin = round(
        font["vmtx"].metrics[wave_vertical][1] + wave_vertical_y_max
    )
    wave_outline = _font_geometry.glyph_path(font, wave_base)
    wave_stroke_model = make_wave_stroke_model(wave_outline, 1000, stroke_widths)
    wave_start = len(linear_codepoints) * NEW_GLYPH_COUNT
    wave_names = allocated_names[wave_start : wave_start + WAVE_GLYPH_COUNT]
    wave_parts = make_wave_parts(
        wave_outline, 1000, wave_vertical_origin, wave_stroke_model
    )
    _font_operations.append_glyphs(
        font,
        list(wave_parts),
        wave_names,
        wave_base,
        wave_vertical_origin,
        add_stem_hints=False,
    )
    wave = ("wave", wave_base, wave_vertical, wave_names)

    relaxed_wave_start = wave_start + WAVE_GLYPH_COUNT
    relaxed_wave_names = allocated_names[
        relaxed_wave_start : relaxed_wave_start + RELAXED_WAVE_GLYPH_COUNT
    ]
    relaxed_wave_parts = make_relaxed_wave_parts(
        wave_outline, 1000, wave_vertical_origin, wave_stroke_model
    )
    _font_operations.append_glyphs(
        font,
        list(relaxed_wave_parts),
        relaxed_wave_names,
        wave_base,
        wave_vertical_origin,
        add_stem_hints=False,
    )

    one_cycle_wave_start = relaxed_wave_start + RELAXED_WAVE_GLYPH_COUNT
    one_cycle_wave_names = allocated_names[
        one_cycle_wave_start : one_cycle_wave_start + ONE_CYCLE_WAVE_GLYPH_COUNT
    ]
    one_cycle_wave_parts = make_one_cycle_wave_parts(
        wave_outline, 1000, wave_vertical_origin, wave_stroke_model
    )
    _font_operations.append_glyphs(
        font,
        list(one_cycle_wave_parts),
        one_cycle_wave_names,
        wave_base,
        wave_vertical_origin,
        add_stem_hints=False,
    )
    one_cycle_wave = (
        "one_cycle_wave",
        wave_base,
        wave_vertical,
        one_cycle_wave_names,
    )

    relaxed_wave = (
        "relaxed_wave",
        wave_base,
        wave_vertical,
        relaxed_wave_names,
    )

    linear_transition_start = one_cycle_wave_start + ONE_CYCLE_WAVE_GLYPH_COUNT
    linear_wave_transitions = []
    for index, ((prefix, base, _, _), parts) in enumerate(
        zip(extensions, linear_parts, strict=True)
    ):
        start = linear_transition_start + index * LINEAR_WAVE_TRANSITION_GLYPH_COUNT
        names = allocated_names[start : start + LINEAR_WAVE_TRANSITION_GLYPH_COUNT]
        transition_parts = make_linear_wave_transition_parts(
            parts,
            wave_parts,
            1000,
            wave_vertical_origin,
        )
        _font_operations.append_glyphs(
            font,
            list(transition_parts),
            names,
            base,
            wave_vertical_origin,
            add_stem_hints=False,
        )
        linear_wave_transitions.append((f"{prefix}_wave", names))

    manga_wave_base = cmap[0x3030]
    _, _, _, manga_wave_y_max = _font_geometry.bounds(font, manga_wave_base)
    manga_wave_vertical_origin = round(
        font["vmtx"].metrics[manga_wave_base][1] + manga_wave_y_max
    )
    transition_start = (
        linear_transition_start
        + LINEAR_WAVE_TRANSITION_GLYPH_COUNT * len(linear_codepoints)
    )
    transition_names = allocated_names[
        transition_start : transition_start + MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT
    ]
    transition_parts = make_manga_to_wave_transition_parts(
        wave_outline, 1000, manga_wave_vertical_origin, wave_stroke_model
    )
    _font_operations.append_glyphs(
        font,
        list(transition_parts),
        transition_names,
        wave_base,
        manga_wave_vertical_origin,
        add_stem_hints=False,
    )
    manga_to_wave_transition = ("manga_to_wave", transition_names)
    reverse_transition_start = transition_start + MANGA_TO_WAVE_TRANSITION_GLYPH_COUNT
    reverse_transition_names = allocated_names[
        reverse_transition_start : reverse_transition_start
        + WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
    ]
    reverse_transition_parts = make_wave_to_manga_transition_parts(
        wave_outline, 1000, manga_wave_vertical_origin, wave_stroke_model
    )
    _font_operations.append_glyphs(
        font,
        list(reverse_transition_parts),
        reverse_transition_names,
        manga_wave_base,
        manga_wave_vertical_origin,
        add_stem_hints=False,
    )
    wave_to_manga_transition = ("wave_to_manga", reverse_transition_names)

    manga_wave_start = reverse_transition_start + WAVE_TO_MANGA_TRANSITION_GLYPH_COUNT
    manga_wave_names = allocated_names[
        manga_wave_start : manga_wave_start + MANGA_WAVE_GLYPH_COUNT
    ]
    manga_wave_isolated, manga_wave_parts = make_manga_wave_parts(
        wave_outline, 1000, manga_wave_vertical_origin, wave_stroke_model
    )
    _font_operations.replace_glyph(
        font,
        manga_wave_base,
        manga_wave_isolated,
        manga_wave_vertical_origin,
    )
    _font_operations.append_glyphs(
        font,
        list(manga_wave_parts),
        manga_wave_names,
        manga_wave_base,
        manga_wave_vertical_origin,
        add_stem_hints=False,
    )
    manga_wave = ("manga_wave", manga_wave_base, manga_wave_names)

    linear_manga_transition_start = manga_wave_start + MANGA_WAVE_GLYPH_COUNT
    linear_manga_transitions = []
    for index, ((prefix, base, _, _), parts) in enumerate(
        zip(extensions, linear_parts, strict=True)
    ):
        start = (
            linear_manga_transition_start + index * LINEAR_MANGA_TRANSITION_GLYPH_COUNT
        )
        names = allocated_names[start : start + LINEAR_MANGA_TRANSITION_GLYPH_COUNT]
        transition_parts = make_linear_manga_transition_parts(
            parts,
            manga_wave_parts,
            1000,
            manga_wave_vertical_origin,
        )
        _font_operations.append_glyphs(
            font,
            list(transition_parts),
            names,
            base,
            manga_wave_vertical_origin,
            add_stem_hints=False,
        )
        linear_manga_transitions.append((f"{prefix}_manga", names))

    punctuation_start = (
        linear_manga_transition_start
        + LINEAR_MANGA_TRANSITION_GLYPH_COUNT * len(linear_codepoints)
    )
    punctuation_names = allocated_names[
        punctuation_start : punctuation_start + len(MANGA_PUNCTUATION_SEQUENCES)
    ]
    punctuation_vertical_origin = round(
        font["vmtx"].metrics[cmap[0xFF01]][1]
        + _font_geometry.bounds(font, cmap[0xFF01])[3]
    )
    shippori_punctuation_paths = {
        "!": upright_punctuation["!"],
        "?": upright_punctuation["?"],
        **dict(
            zip(
                MANGA_PUNCTUATION_SEQUENCES,
                (
                    make_punctuation_ligature(punctuation_font, sequence)
                    for sequence in MANGA_PUNCTUATION_SEQUENCES
                ),
                strict=True,
            )
        ),
    }
    mincho_punctuation_paths = {
        sequence: _font_geometry.adjust_outline_weight(
            outline,
            SHIPPORI_STROKE_ADJUSTMENTS[identity.style],
        )
        for sequence, outline in shippori_punctuation_paths.items()
    }
    upright_exclamation = mincho_punctuation_paths["!"]
    upright_question = mincho_punctuation_paths["?"]
    _font_operations.replace_glyph(
        font,
        cmap[0xFF01],
        upright_exclamation,
        punctuation_vertical_origin,
        advance_override=1000,
    )
    _font_operations.replace_glyph(
        font,
        cmap[0xFF1F],
        upright_question,
        punctuation_vertical_origin,
        advance_override=1000,
    )
    punctuation_paths = [
        mincho_punctuation_paths[sequence] for sequence in MANGA_PUNCTUATION_SEQUENCES
    ]
    _font_operations.append_glyphs(
        font,
        punctuation_paths,
        punctuation_names,
        cmap[0x21],
        punctuation_vertical_origin,
        add_stem_hints=False,
        advance_override=1000,
    )
    default_punctuation_names = {
        "!": cmap[0xFF01],
        "?": cmap[0xFF1F],
        **dict(
            zip(
                MANGA_PUNCTUATION_SEQUENCES,
                punctuation_names,
                strict=True,
            )
        ),
    }
    punctuation_rotated_start = punctuation_start + len(MANGA_PUNCTUATION_SEQUENCES)
    punctuation_rotated_names = allocated_names[
        punctuation_rotated_start : punctuation_rotated_start
        + PUNCTUATION_ROTATED_COUNT
    ]
    punctuation_rotated_paths: list[pathops.Path] = []
    punctuation_variants: list[tuple[str, tuple[str, str]]] = []
    for sequence, rotated_name in zip(
        PUNCTUATION_VARIANT_SEQUENCES,
        punctuation_rotated_names,
        strict=True,
    ):
        punctuation_rotated_paths.append(
            rotate_punctuation_outline(mincho_punctuation_paths[sequence])
        )
        punctuation_variants.append(
            (
                sequence,
                (default_punctuation_names[sequence], rotated_name),
            )
        )
    _font_operations.append_glyphs(
        font,
        punctuation_rotated_paths,
        punctuation_rotated_names,
        cmap[0xFF01],
        punctuation_vertical_origin,
        add_stem_hints=False,
        advance_override=1000,
    )

    punctuation_mark_start = punctuation_rotated_start + PUNCTUATION_ROTATED_COUNT
    punctuation_mark_count = len(_mark_positioning.PUNCTUATION_MARK_PAIRS)
    punctuation_mark_names = allocated_names[
        punctuation_mark_start : punctuation_mark_start + 2 * punctuation_mark_count
    ]
    punctuation_mark_horizontal_names = punctuation_mark_names[:punctuation_mark_count]
    punctuation_mark_vertical_names = punctuation_mark_names[punctuation_mark_count:]
    mark_paths = {
        codepoint: _font_geometry.glyph_path(font, cmap[codepoint])
        for codepoint in (0x3099, 0x309A)
    }
    punctuation_mark_horizontal_paths = []
    punctuation_mark_vertical_paths = []
    for pair in _mark_positioning.PUNCTUATION_MARK_PAIRS:
        base, mark = pair
        punctuation_mark_horizontal_paths.append(
            _font_geometry.compose_mark_glyph(
                _font_geometry.glyph_path(font, cmap[base]),
                mark_paths[mark],
                _font_geometry.mark_placement_transform(
                    mark_paths[mark],
                    punctuation_mark_positions[pair]["horizontal"],
                ),
            )
        )
        punctuation_mark_vertical_paths.append(
            _font_geometry.compose_mark_glyph(
                _font_geometry.glyph_path(
                    font,
                    _font_operations.vertical_glyph_or_self(font, cmap[base]),
                ),
                mark_paths[mark],
                _font_geometry.mark_placement_transform(
                    mark_paths[mark],
                    punctuation_mark_positions[pair]["vertical"],
                ),
            )
        )
    _font_operations.append_glyphs(
        font,
        punctuation_mark_horizontal_paths + punctuation_mark_vertical_paths,
        punctuation_mark_names,
        cmap[0xFF01],
        punctuation_vertical_origin,
        add_stem_hints=False,
        advance_override=1000,
    )
    punctuation_mark_outputs = dict(
        zip(
            _mark_positioning.PUNCTUATION_MARK_PAIRS,
            punctuation_mark_horizontal_names,
            strict=True,
        )
    )
    punctuation_mark_vertical_maps = list(
        zip(
            punctuation_mark_horizontal_names,
            punctuation_mark_vertical_names,
            strict=True,
        )
    )

    kana_start = punctuation_mark_start + len(punctuation_mark_names)
    small_kana_names = allocated_names[
        kana_start : kana_start + 2 * len(_mark_positioning.MANGA_MISSING_SMALL_KANA)
    ]
    small_hiragana = _font_geometry.centered_scaled_path(
        _font_geometry.glyph_path(font, cmap[0x3053]), 0.775, 500, 253
    )
    small_katakana = _font_geometry.centered_scaled_path(
        _font_geometry.glyph_path(font, cmap[0x30B3]), 0.775, 500, 253
    )
    small_hiragana_vertical = _font_geometry.centered_scaled_path(
        _font_geometry.glyph_path(
            font, _font_operations.vertical_glyph_or_self(font, cmap[0x3053])
        ),
        0.78,
        654,
        397,
    )
    small_katakana_vertical = _font_geometry.centered_scaled_path(
        _font_geometry.glyph_path(
            font, _font_operations.vertical_glyph_or_self(font, cmap[0x30B3])
        ),
        0.78,
        654,
        397,
    )
    _font_operations.append_glyphs(
        font,
        [
            small_hiragana,
            small_katakana,
            small_hiragana_vertical,
            small_katakana_vertical,
        ],
        small_kana_names,
        cmap[0x3053],
        880,
        add_stem_hints=False,
    )
    missing_small_glyphs = {
        0x1B132: (small_kana_names[0], small_kana_names[2]),
        0x1B155: (small_kana_names[1], small_kana_names[3]),
    }
    kana_vertical_maps = [
        *punctuation_mark_vertical_maps,
        *missing_small_glyphs.values(),
    ]
    for codepoint, (horizontal, _) in missing_small_glyphs.items():
        _font_operations.add_unicode_mapping(font, codepoint, horizontal)
        cmap[codepoint] = horizontal

    mark_horizontal_start = kana_start + len(small_kana_names)
    generated_mark_names = allocated_names[
        mark_horizontal_start : mark_horizontal_start + len(generated_mark_pairs)
    ]
    generated_mark_outputs = dict(
        zip(generated_mark_pairs, generated_mark_names, strict=True)
    )
    horizontal_mark_paths = []
    for base, mark in generated_mark_pairs:
        base_path = _font_geometry.glyph_path(font, cmap[base])
        if (base, mark) == _mark_positioning.CHOON_DAKUTEN_PAIR:
            target_x, target_y = _mark_positioning.CHOON_DAKUTEN_MARK_CENTERS[
                "horizontal"
            ]
            mark_transform = _font_geometry.centered_transform(
                mark_paths[mark], 1, target_x, target_y
            )
        else:
            mark_transform = _font_geometry.mark_placement_transform(
                mark_paths[mark],
                mark_position_overrides[(base, mark)]["horizontal"],
            )
        horizontal_mark_paths.append(
            _font_geometry.compose_mark_glyph(
                base_path, mark_paths[mark], mark_transform
            )
        )
    _font_operations.append_glyphs(
        font,
        horizontal_mark_paths,
        generated_mark_names,
        cmap[0x3042],
        880,
        add_stem_hints=False,
    )

    mark_vertical_start = mark_horizontal_start + len(generated_mark_pairs)
    generated_vertical_mark_names = allocated_names[
        mark_vertical_start : mark_vertical_start + len(generated_vertical_mark_pairs)
    ]
    generated_vertical_mark_outputs = dict(
        zip(
            generated_vertical_mark_pairs,
            generated_vertical_mark_names,
            strict=True,
        )
    )
    vertical_mark_paths = []
    for base, mark in generated_vertical_mark_pairs:
        if base in missing_small_glyphs:
            vertical_base = missing_small_glyphs[base][1]
        else:
            vertical_base = _font_operations.vertical_glyph_or_self(font, cmap[base])
        base_path = _font_geometry.glyph_path(font, vertical_base)
        if (base, mark) == _mark_positioning.CHOON_DAKUTEN_PAIR:
            target_x, target_y = _mark_positioning.CHOON_DAKUTEN_MARK_CENTERS[
                "vertical"
            ]
            mark_transform = _font_geometry.centered_transform(
                mark_paths[mark], 1, target_x, target_y
            )
        else:
            mark_transform = _font_geometry.mark_placement_transform(
                mark_paths[mark],
                mark_position_overrides[(base, mark)]["vertical"],
            )
        vertical_mark_paths.append(
            _font_geometry.compose_mark_glyph(
                base_path, mark_paths[mark], mark_transform
            )
        )
    _font_operations.append_glyphs(
        font,
        vertical_mark_paths,
        generated_vertical_mark_names,
        cmap[0x3042],
        880,
        add_stem_hints=False,
    )
    kana_vertical_maps.extend(
        zip(
            (generated_mark_outputs[pair] for pair in generated_vertical_mark_pairs),
            generated_vertical_mark_names,
            strict=True,
        )
    )
    for horizontal in native_mark_outputs.values():
        kana_vertical_maps.append(
            (horizontal, _font_operations.vertical_glyph_or_self(font, horizontal))
        )

    heart_start = mark_vertical_start + len(generated_vertical_mark_pairs)
    heart_names = allocated_names[
        heart_start : heart_start + len(generated_heart_pairs)
    ]
    heart_paths = [
        _font_geometry.compose_heart_dakuten_glyph(
            _font_geometry.glyph_path(font, cmap[base]),
            mark_paths[mark],
        )
        for base, mark in generated_heart_pairs
    ]
    if heart_paths:
        _font_operations.append_glyphs(
            font,
            heart_paths,
            heart_names,
            cmap[0x2661],
            880,
            add_stem_hints=False,
        )
    heart_outputs = dict(native_heart_outputs)
    heart_outputs.update(zip(generated_heart_pairs, heart_names, strict=True))
    for codepoint, (base, _) in zip(
        _mark_positioning.KOBURI_HEART_BASE_PUA,
        _mark_positioning.KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        _font_operations.add_unicode_mapping_if_missing(font, codepoint, cmap[base])
    for codepoint, pair in zip(
        _mark_positioning.KOBURI_HEART_OUTPUT_PUA,
        _mark_positioning.KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        output = heart_outputs[pair]
        if cmap.get(codepoint) != output:
            _font_operations.add_unicode_mapping(font, codepoint, output)

    mark_outputs = native_mark_outputs | generated_mark_outputs
    for offset, pair in enumerate(_mark_positioning.KOBURI_PUA_MARK_PAIRS):
        _font_operations.add_unicode_mapping(
            font,
            _mark_positioning.KOBURI_PUA_START + offset,
            mark_outputs[pair],
        )
    _font_operations.add_unicode_mapping(
        font,
        _mark_positioning.CHOON_DAKUTEN_PUA,
        mark_outputs[_mark_positioning.CHOON_DAKUTEN_PAIR],
    )
    kana_marks = mark_ligature_rules(
        cmap,
        supported_mark_pairs,
        mark_outputs,
        COMBINING_MARK_INPUTS,
    )
    spacing_marks = mark_ligature_rules(
        cmap,
        supported_mark_pairs,
        mark_outputs,
        SPACING_MARK_INPUTS,
    )
    kana_marks.extend(
        mark_ligature_rules(
            cmap,
            _mark_positioning.KOBURI_HEART_MARK_PAIRS,
            heart_outputs,
            COMBINING_MARK_INPUTS,
        )
    )
    spacing_marks.extend(
        mark_ligature_rules(
            cmap,
            _mark_positioning.KOBURI_HEART_MARK_PAIRS,
            heart_outputs,
            SPACING_MARK_INPUTS,
        )
    )
    punctuation_marks = mark_ligature_rules(
        cmap,
        _mark_positioning.PUNCTUATION_MARK_PAIRS,
        punctuation_mark_outputs,
        COMBINING_MARK_INPUTS,
    )
    spacing_marks.extend(
        mark_ligature_rules(
            cmap,
            _mark_positioning.PUNCTUATION_MARK_PAIRS,
            punctuation_mark_outputs,
            SPACING_MARK_INPUTS,
        )
    )
    punctuation_marks = [
        (cmap[base], cmap[mark], punctuation_mark_outputs[(base, mark)])
        for base, mark in _mark_positioning.PUNCTUATION_MARK_PAIRS
    ]
    hiragana_mappings = None
    katakana_mappings = None
    if kana_style == "novel":
        hiragana_mappings = _novel_hiragana_mappings(
            font,
            cmap,
            native_hiragana_ccmp_outputs | mark_outputs,
            native_hiragana_vertical_ccmp_outputs | generated_vertical_mark_outputs,
            missing_small_glyphs,
        )
        katakana_mappings = _novel_katakana_mappings(
            font,
            cmap,
            native_katakana_ccmp_outputs | mark_outputs,
            native_katakana_vertical_ccmp_outputs | generated_vertical_mark_outputs,
            missing_small_glyphs,
        )
    if han_brush_elements:
        apply_han_brush_elements(
            font,
            BrushElementStyle(vertical_end_profile=han_brush_end_profile),
        )
    _apply_novel_style(
        font,
        identity.weight_class,
        kana_style,
        hiragana_mappings,
        katakana_mappings,
    )

    if base_type == "noto":
        _font_operations.remove_repeated_ligatures(font, "ccmp", cmap[0x2015])

    merge_features(
        font,
        feature_source(
            extensions,
            wave,
            relaxed_wave,
            manga_wave,
            one_cycle_wave,
            manga_to_wave_transition,
            wave_to_manga_transition,
            punctuation_variants,
            linear_wave_transitions,
            linear_manga_transitions,
            kana_marks,
            spacing_marks,
            kana_vertical_maps,
            punctuation_marks,
        ),
    )
    _rename_release_font(font, latin_font, latin_profile, identity)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path, reorderTables=True)
    if autohint:
        autohint_latin_glyphs(output_path, latin_import.glyph_names)
