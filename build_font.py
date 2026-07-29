#!/usr/bin/env python3
"""Build Nobigoe font families with extensible punctuation."""

from __future__ import annotations

import argparse
import copy
import math
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from font_profiles import (
    BaseType,
    FontIdentity,
    KOBURI_RUBY_STROKE_ADJUSTMENTS,
    LATIN_FAMILIES,
    LatinBuildProfile,
    NOTO_WEIGHT_CLASSES,
    SHIPPORI_COPYRIGHT,
    SHIPPORI_STROKE_ADJUSTMENTS,
    VERSION,
    VERSION_NUMBER,
    default_output_path,
    font_identity,
    latin_build_profile,
)
from font_sources import DEFAULT_CACHE_DIR, SourceCache, SourceOverrides
import font_geometry as _font_geometry
import font_operations as _font_operations
import mark_positioning as _mark_positioning

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.transform import Transform
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.varLib.instancer import instantiateVariableFont


WAVE_GLYPH_COUNT = 10
MANGA_WAVE_GLYPH_COUNT = 7
WAVE_TERMINAL_EXTENSION_HALF_WAVES = 0.3
NEW_GLYPH_COUNT = 6
OVERLAP = 0
KOBURI_RUBY_RULE_COUNT = 289
KOBURI_RUBY_OUTPUT_COUNT = 288
KOBURI_RUBY_VERTICAL_ORIGIN = 880
SHIPPORI_PRECOMPOSED_LIGATURES = {
    "!!": 0x203C,
    "??": 0x2047,
    "?!": 0x2048,
    "!?": 0x2049,
}
SHIPPORI_UPRIGHT_PUNCTUATION = {
    "!": 0xE000,
    "?": 0xFF1F,
}
SHIPPORI_UPRIGHT_EXCLAMATIONS = {
    "!": SHIPPORI_UPRIGHT_PUNCTUATION["!"],
    "!!": 0xE002,
    "!!!": 0xE007,
    "!!!!": 0xE0E3,
}
SHIPPORI_COMPONENT_LIGATURES = {
    "!": SHIPPORI_UPRIGHT_EXCLAMATIONS["!!"],
    "?": 0x2047,
}
MANGA_PUNCTUATION_SEQUENCES = (
    "!!!!!",
    "!!!!",
    "!!??",
    "??!!",
    "!!!",
    "???",
    "!!?",
    "??!",
    "?!?",
    "!??",
    "!?!",
    "?!!",
    "?!",
    "!?",
    "!!",
    "??",
)
PUNCTUATION_VARIANT_SEQUENCES = (
    "!",
    "?",
    *MANGA_PUNCTUATION_SEQUENCES,
)
PUNCTUATION_ALTERNATE_COUNT = 3 * len(PUNCTUATION_VARIANT_SEQUENCES)
PUNCTUATION_SLANT_ANGLE = 12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add automatically joining ー, ―, 〜, ～, and 〰 glyphs to "
            "Noto Serif JP or GenEi Koburi Mincho."
        )
    )
    parser.add_argument(
        "--base",
        choices=("noto", "koburi"),
        default="noto",
        help="base typeface; Koburi is available in Regular only",
    )
    parser.add_argument(
        "--weight",
        choices=tuple(NOTO_WEIGHT_CLASSES),
        default="Regular",
        help="Noto Serif JP weight",
    )
    parser.add_argument(
        "--latin-family",
        choices=LATIN_FAMILIES,
        default="libertinus",
        help=(
            "Latin glyph source for the Noto base; "
            "the existing Libertinus profile remains the default"
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="local Noto Serif JP OTF/TTC or GenEi Koburi Mincho TTF",
    )
    parser.add_argument(
        "--latin-source",
        type=Path,
        help="local font overriding the selected Noto-based Latin source",
    )
    parser.add_argument(
        "--ruby-source",
        type=Path,
        help="GenEi Koburi Mincho TTF used for Noto-based ruby glyphs",
    )
    parser.add_argument(
        "--punctuation-source",
        type=Path,
        help=(
            "Shippori Mincho OTF/TTF used for Manga1 "
            "exclamation/question ligatures (matching OTF weight by default)"
        ),
    )
    parser.add_argument(
        "--sans-source",
        type=Path,
        help="local Noto Sans JP OTF used for sans punctuation variants",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="directory for the persistent verified font-source cache",
    )
    parser.add_argument(
        "--face", type=int, default=0, help="TTC face index"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--autohint",
        action="store_true",
        help=(
            "run AFDKO otfautohint on imported Latin glyphs after building; "
            "requires the otfautohint command"
        ),
    )
    return parser.parse_args()


def stroke_band(
    outline: pathops.Path, axis: str, seam: float
) -> tuple[int, int]:
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


def make_horizontal_parts(
    outline: pathops.Path, advance: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance / 2
    y_min, y_max = stroke_band(outline, "horizontal", seam)
    clip_left = _font_geometry.rectangle(-4096, -4096, seam, 4096)
    clip_right = _font_geometry.rectangle(seam, -4096, 4096, 4096)
    left_cap = pathops.op(outline, clip_left, pathops.PathOp.INTERSECTION)
    right_cap = pathops.op(outline, clip_right, pathops.PathOp.INTERSECTION)

    start_bar = _font_geometry.rectangle(seam - OVERLAP, y_min, advance + OVERLAP, y_max)
    middle = _font_geometry.rectangle(-OVERLAP, y_min, advance + OVERLAP, y_max)
    end_bar = _font_geometry.rectangle(-OVERLAP, y_min, seam + OVERLAP, y_max)
    start = pathops.op(left_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, right_cap, pathops.PathOp.UNION)
    return start, middle, end


def flatten_horizontal_centerline(
    outline: pathops.Path, advance: int
) -> pathops.Path:
    sample_start = advance * 0.3
    sample_end = advance * 0.7
    start_low, start_high = stroke_band(
        outline, "horizontal", sample_start
    )
    end_low, end_high = stroke_band(outline, "horizontal", sample_end)
    start_center = (start_low + start_high) / 2
    end_center = (end_low + end_high) / 2
    slope = (end_center - start_center) / (sample_end - sample_start)
    seam = advance / 2
    return _font_geometry.transform_path(outline,
    Transform(1, -slope, 0, 1, 0, slope * seam),)


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
    start_bar = _font_geometry.rectangle(x_min, cell_bottom - OVERLAP, x_max, seam + OVERLAP)
    middle = _font_geometry.rectangle(x_min, cell_bottom - OVERLAP, x_max, cell_top + OVERLAP)
    end_bar = _font_geometry.rectangle(x_min, seam - OVERLAP, x_max, cell_top + OVERLAP)
    start = pathops.op(top_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, bottom_cap, pathops.PathOp.UNION)
    return start, middle, end




def make_sine_wave_tile(
    source: pathops.Path,
    advance: int,
    *,
    inverted: bool = False,
    taper_start: bool = False,
    taper_end: bool = False,
    half_waves: float = 3,
    taper_fraction: float = 1 / 4,
    start_margin: float = 0,
    end_margin: float = 0,
    sample_peak_position: float | None = None,
    sample_trough_position: float | None = None,
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
    peak_center = (sample_peak_min + sample_peak_max) / 2
    trough_center = (sample_trough_min + sample_trough_max) / 2
    baseline = (peak_center + trough_center) / 2
    amplitude = (peak_center - trough_center) / 2
    thickness = (
        (sample_peak_max - sample_peak_min)
        + (sample_trough_max - sample_trough_min)
    ) / 2
    half_stroke = thickness / 2
    direction = -1 if inverted else 1
    normal_phase_velocity = half_waves * math.pi / advance
    taper_length = advance * taper_fraction
    drawing_start = start_margin if taper_start else 0.0
    drawing_end = advance - end_margin if taper_end else float(advance)
    start_taper_length = taper_length - drawing_start
    end_taper_length = drawing_end - (advance - taper_length)

    terminal_phase_extension = (
        WAVE_TERMINAL_EXTENSION_HALF_WAVES * math.pi
    )

    def smoothstep(progress: float) -> float:
        return progress * progress * (3 - 2 * progress)

    def smootherstep(progress: float) -> float:
        return (
            6 * progress**5
            - 15 * progress**4
            + 10 * progress**3
        )

    def smootherstep_derivative(progress: float) -> float:
        return 30 * progress**2 * (progress - 1) ** 2

    def phase_at(position: float) -> tuple[float, float]:
        phase = normal_phase_velocity * position
        phase_velocity = normal_phase_velocity
        correction_start = taper_length
        correction_end = advance - taper_length
        correction_length = correction_end - correction_start
        if taper_start:
            if position <= correction_start:
                phase -= terminal_phase_extension
            elif position < correction_end:
                progress = (
                    position - correction_start
                ) / correction_length
                phase -= terminal_phase_extension * (
                    1 - smootherstep(progress)
                )
                phase_velocity += (
                    terminal_phase_extension
                    * smootherstep_derivative(progress)
                    / correction_length
                )
        if taper_end:
            if position >= correction_end:
                phase += terminal_phase_extension
            elif position > correction_start:
                progress = (
                    position - correction_start
                ) / correction_length
                phase += terminal_phase_extension * smootherstep(
                    progress
                )
                phase_velocity += (
                    terminal_phase_extension
                    * smootherstep_derivative(progress)
                    / correction_length
                )
        return phase, phase_velocity


    def width_at(position: float) -> float:
        scale = 1.0
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
        return half_stroke * scale


    breakpoints = {drawing_start, drawing_end}
    if taper_start:
        breakpoints.add(taper_length)
    if taper_end:
        breakpoints.add(advance - taper_length)
    phase_start, _ = phase_at(drawing_start)
    phase_end, _ = phase_at(drawing_end)
    for index in range(-8, 16):
        target = math.pi / 2 + index * math.pi
        if not phase_start < target < phase_end:
            continue
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
        sine_slope = (
            direction
            * amplitude
            * phase_velocity
            * math.cos(phase)
        )
        points.append(
            (position, center, sine_slope, abs(sine_slope) < 1e-9)
        )


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


def make_wave_parts(
    source: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, ...]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)
    horizontal = (
        make_sine_wave_tile(
            source,
            advance,
            taper_start=True,
            start_margin=start_margin,
        ),
        make_sine_wave_tile(source, advance),
        make_sine_wave_tile(source, advance, inverted=True),
        make_sine_wave_tile(
            source,
            advance,
            taper_end=True,
            end_margin=end_margin,
        ),
        make_sine_wave_tile(
            source,
            advance,
            inverted=True,
            taper_end=True,
            end_margin=end_margin,
        ),
    )
    tile_center_y = (
        horizontal[1].bounds[1] + horizontal[1].bounds[3]
    ) / 2
    vertical_phase_flip = Transform(
        0,
        -1,
        -1,
        0,
        advance / 2 + tile_center_y,
        vertical_origin,
    )
    vertical = tuple(
        _font_geometry.transform_path(outline, vertical_phase_flip)
        for outline in horizontal
    )
    return horizontal + vertical


def make_manga_wave_parts(
    source: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, tuple[pathops.Path, ...]]:
    source_x_min, _, source_x_max, _ = source.bounds
    start_margin = max(0.0, source_x_min)
    end_margin = max(0.0, advance - source_x_max)
    parameters = {
        "half_waves": 4,
        "taper_fraction": 1 / 6,
    }
    horizontal_isolated = make_sine_wave_tile(
        source,
        advance,
        taper_start=True,
        taper_end=True,
        start_margin=start_margin,
        end_margin=end_margin,
        **parameters,
    )
    horizontal_start = make_sine_wave_tile(
        source,
        advance,
        taper_start=True,
        start_margin=start_margin,
        **parameters,
    )
    horizontal_middle = make_sine_wave_tile(
        source, advance, **parameters
    )
    horizontal_end = make_sine_wave_tile(
        source,
        advance,
        taper_end=True,
        end_margin=end_margin,
        **parameters,
    )
    tile_center_y = (
        horizontal_middle.bounds[1] + horizontal_middle.bounds[3]
    ) / 2
    vertical_rotation = Transform(
        0,
        -1,
        -1,
        0,
        advance / 2 + tile_center_y,
        vertical_origin,
    )
    vertical = tuple(
        _font_geometry.transform_path(outline, vertical_rotation)
        for outline in (
            horizontal_isolated,
            horizontal_start,
            horizontal_middle,
            horizontal_end,
        )
    )
    added = (
        horizontal_start,
        horizontal_middle,
        horizontal_end,
        vertical[0],
        vertical[1],
        vertical[2],
        vertical[3],
    )
    return horizontal_isolated, added




def shippori_upright_punctuation_paths(
    font: TTFont,
) -> dict[str, pathops.Path]:
    cmap = font.getBestCmap()
    return {
        mark: _font_geometry.glyph_path(font, cmap[codepoint])
        for mark, codepoint in SHIPPORI_UPRIGHT_PUNCTUATION.items()
    }


def make_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    components: list[tuple[pathops.Path, float, float]] = []
    total_width = gap * (len(sequence) - 1)
    cmap = font.getBestCmap()
    upright_codepoint = SHIPPORI_UPRIGHT_EXCLAMATIONS.get(sequence)
    if upright_codepoint is not None:
        return _font_geometry.glyph_path(font, cmap[upright_codepoint])
    precomposed_codepoint = SHIPPORI_PRECOMPOSED_LIGATURES.get(
        sequence
    )
    if precomposed_codepoint is not None:
        return _font_geometry.glyph_path(font, cmap[precomposed_codepoint])

    for mark in sequence:
        source_codepoint = SHIPPORI_COMPONENT_LIGATURES[mark]
        source = _font_geometry.glyph_path(font, cmap[source_codepoint])
        contours = list(source.contours)
        if len(contours) != 4:
            raise ValueError(
                f"Expected four contours in U+{source_codepoint:04X}"
            )
        outline = pathops.Path()
        outline.addPath(contours[0])
        outline.addPath(contours[2])
        x_min, _, x_max, _ = outline.bounds
        width = x_max - x_min
        components.append((outline, x_min, width))
        total_width += width

    scale = min(1.0, (advance - 40) / total_width)
    combined = pathops.Path()
    cursor = (advance - total_width * scale) / 2
    for outline, x_min, width in components:
        transform = Transform(
            scale, 0, 0, 1, cursor - scale * x_min, 0
        )
        outline.draw(TransformPen(combined.getPen(), transform))
        cursor += (width + gap) * scale
    return combined


def make_sans_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    cmap = font.getBestCmap()
    components = [
        _font_geometry.glyph_path(font, cmap[0xFF01 if mark == "!" else 0xFF1F])
        for mark in sequence
    ]
    component_metrics = [
        (outline, outline.bounds[0], outline.bounds[2] - outline.bounds[0])
        for outline in components
    ]
    total_width = sum(width for _, _, width in component_metrics)
    total_width += gap * (len(sequence) - 1)
    scale = min(1.0, (advance - 40) / total_width)
    combined = pathops.Path()
    cursor = (advance - total_width * scale) / 2
    for outline, x_min, width in component_metrics:
        combined.addPath(
            _font_geometry.transform_path(outline,
            Transform(scale, 0, 0, 1, cursor - scale * x_min, 0),)
        )
        cursor += (width + gap) * scale
    return combined


def slant_punctuation_outline(
    outline: pathops.Path,
) -> pathops.Path:
    shear = math.tan(math.radians(PUNCTUATION_SLANT_ANGLE))
    slanted = _font_geometry.transform_path(outline, Transform(1, 0, shear, 1, 0, 0))
    x_min, _, x_max, _ = slanted.bounds
    return _font_geometry.transform_path(slanted,
    Transform(1, 0, 0, 1, 500 - (x_min + x_max) / 2, 0),)


def punctuation_ligature_rules(
    exclamation: str,
    question: str,
    ligatures: list[tuple[str, str]],
) -> str:
    inputs = {"!": exclamation, "?": question}
    return "".join(
        f"  sub {' '.join(inputs[mark] for mark in sequence)}"
        f" by {name};\n"
        for sequence, name in ligatures
    )


def add_linear_extension(
    font: TTFont,
    base: str,
    names: list[str],
    *,
    flatten_horizontal: bool = False,
) -> tuple[str, list[str]]:
    vertical = _font_operations.find_vertical_glyph(font, base)
    advance = font["hmtx"].metrics[base][0]
    if advance != 1000:
        raise ValueError(f"Expected a 1000-unit full-width glyph, got {advance}")

    horizontal_outline = _font_geometry.glyph_path(font, base)
    if flatten_horizontal:
        horizontal_outline = flatten_horizontal_centerline(
            horizontal_outline, advance
        )
    horizontal_parts = make_horizontal_parts(horizontal_outline, advance)
    _, _, _, vertical_y_max = _font_geometry.bounds(font, vertical)
    vertical_origin = round(font["vmtx"].metrics[vertical][1] + vertical_y_max)
    vertical_parts = make_vertical_parts(
        _font_geometry.glyph_path(font, vertical), advance, vertical_origin
    )
    _font_operations.append_glyphs(
        font,
        list(horizontal_parts + vertical_parts),
        names,
        base,
        vertical_origin,
    )
    return vertical, names


def contextual_extension_rules(
    prefix: str, base: str, start: str, middle: str, end: str
) -> str:
    return f"""
  lookup {prefix}_start {{
    ignore sub {base} [{base} {middle} {end} {start}]';
    sub {base}' [{base} {start} {middle} {end}] by {start};
  }} {prefix}_start;
  lookup {prefix}_end {{
    sub [{base} {start} {middle} {end}] {base}' by {end};
  }} {prefix}_end;
  sub [{start} {middle}] {start}' by {middle};
"""


def alternating_wave_rules(
    prefix: str, base: str, names: list[str]
) -> str:
    start, middle_a, middle_b, end_a, end_b = names
    glyphs = f"{base} {start} {middle_a} {middle_b} {end_a} {end_b}"
    return f"""
  lookup {prefix}_start {{
    ignore sub {base} [{glyphs}]';
    sub {base}' [{glyphs}] by {start};
  }} {prefix}_start;
  lookup {prefix}_end {{
    sub [{glyphs}] {base}' by {end_a};
  }} {prefix}_end;
  sub [{start} {middle_a}] {start}' by {middle_b};
  sub {middle_b} {start}' by {middle_a};
  sub [{start} {middle_a}] {end_a}' by {end_b};
"""


def import_koburi_ruby(
    font: TTFont,
    ruby_font: TTFont,
    cmap: dict[int, str],
    mark_outputs: dict[tuple[int, int], str],
    missing_small_glyphs: dict[int, tuple[str, str]],
    names: list[str],
    *,
    weight_adjustment: float = 0,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    source_substitutions = _font_operations.feature_single_substitutions(
        ruby_font, "ruby"
    )
    if len(source_substitutions) != KOBURI_RUBY_RULE_COUNT:
        raise ValueError(
            "The ruby source must contain "
            f"{KOBURI_RUBY_RULE_COUNT} ruby substitutions"
        )
    source_outputs = list(dict.fromkeys(source_substitutions.values()))
    if len(source_outputs) != KOBURI_RUBY_OUTPUT_COUNT:
        raise ValueError(
            "The ruby source must contain "
            f"{KOBURI_RUBY_OUTPUT_COUNT} ruby glyphs"
        )
    if len(names) != len(source_outputs):
        raise ValueError("Ruby glyph allocation does not match the source")

    source_cmap = ruby_font.getBestCmap()
    source_reverse_cmap: dict[str, list[int]] = {}
    for codepoint, glyph_name in source_cmap.items():
        source_reverse_cmap.setdefault(glyph_name, []).append(codepoint)

    source_vertical: dict[str, str] = {}
    for feature_tag in ("vert", "vrt2"):
        for horizontal, vertical in (
            _font_operations.feature_single_substitutions(
                ruby_font, feature_tag
            ).items()
        ):
            if (
                horizontal not in source_substitutions
                or vertical not in source_substitutions
            ):
                continue
            previous = source_vertical.setdefault(horizontal, vertical)
            if previous != vertical:
                raise ValueError(
                    f"Ambiguous vertical mapping for {horizontal!r}"
                )
    vertical_to_horizontal = {
        vertical: horizontal
        for horizontal, vertical in source_vertical.items()
    }
    if len(vertical_to_horizontal) != len(source_vertical):
        raise ValueError("Vertical ruby inputs are not one-to-one")

    source_fwid = _font_operations.feature_single_substitutions(
        ruby_font, "fwid"
    )
    target_fwid = _font_operations.feature_single_substitutions(font, "fwid")
    source_bullet = source_fwid[source_cmap[0x2022]]
    target_bullet = target_fwid.get(cmap[0x2022], cmap[0x2022])

    unencoded_horizontal = [
        glyph_name
        for glyph_name in source_substitutions
        if glyph_name not in source_reverse_cmap
        and glyph_name not in vertical_to_horizontal
        and glyph_name != source_bullet
    ]
    if len(unencoded_horizontal) != len(
        _mark_positioning.MANGA_MISSING_SMALL_KANA
    ):
        raise ValueError(
            "The ruby source must contain the two unencoded small-ko glyphs"
        )
    unencoded_small_ko = dict(
        zip(
            sorted(unencoded_horizontal, key=ruby_font.getGlyphID),
            _mark_positioning.MANGA_MISSING_SMALL_KANA,
            strict=True,
        )
    )
    pua_mark_pairs = dict(
        zip(
            range(
                _mark_positioning.KOBURI_PUA_START,
                _mark_positioning.KOBURI_PUA_START
                + len(_mark_positioning.KOBURI_PUA_MARK_PAIRS),
            ),
            _mark_positioning.KOBURI_PUA_MARK_PAIRS,
            strict=True,
        )
    )

    def horizontal_target(source_name: str) -> str:
        if source_name == source_bullet:
            return target_bullet
        small_ko = unencoded_small_ko.get(source_name)
        if small_ko is not None:
            return missing_small_glyphs[small_ko][0]
        for codepoint in source_reverse_cmap.get(source_name, []):
            pair = pua_mark_pairs.get(codepoint)
            if pair is not None:
                return mark_outputs[pair]
            target_name = cmap.get(codepoint)
            if target_name is not None:
                return target_name
        raise ValueError(f"Could not map ruby input {source_name!r}")

    def target_input(source_name: str) -> str:
        horizontal = vertical_to_horizontal.get(source_name)
        if horizontal is None:
            return horizontal_target(source_name)
        small_ko = unencoded_small_ko.get(horizontal)
        if small_ko is not None:
            return missing_small_glyphs[small_ko][1]
        target_horizontal = horizontal_target(horizontal)
        return _font_operations.find_vertical_glyph(font, target_horizontal)

    output_names = dict(zip(source_outputs, names, strict=True))
    paths = [
        _font_geometry.adjust_outline_weight(
            _font_geometry.glyph_path(ruby_font, source_name),
            weight_adjustment,
        )
        for source_name in source_outputs
    ]
    _font_operations.append_glyphs(
        font,
        paths,
        names,
        cmap[0x3042],
        KOBURI_RUBY_VERTICAL_ORIGIN,
        add_stem_hints=False,
        advance_override=1000,
    )

    substitutions: dict[str, str] = {}
    for source_input, source_output in source_substitutions.items():
        target_name = target_input(source_input)
        output_name = output_names[source_output]
        previous = substitutions.setdefault(target_name, output_name)
        if previous != output_name:
            raise ValueError(f"Conflicting ruby substitutions for {target_name!r}")

    vertical_maps = list(
        dict.fromkeys(
            (
                output_names[source_substitutions[horizontal]],
                output_names[source_substitutions[vertical]],
            )
            for horizontal, vertical in source_vertical.items()
        )
    )
    return list(substitutions.items()), vertical_maps


def feature_source(
    extensions: list[tuple[str, str, str, list[str]]],
    wave: tuple[str, str, str, list[str]],
    manga_wave: tuple[str, str, list[str]],
    punctuation_variants: list[tuple[str, tuple[str, str, str, str]]],
    kana_marks: list[tuple[str, str, str]],
    kana_vertical_maps: list[tuple[str, str]],
    ruby_substitutions: list[tuple[str, str]],
) -> str:
    calt_rules: list[str] = []
    vert_rules: list[str] = []
    vrt2_rules: list[str] = []
    for prefix, base, vertical, names in extensions:
        h_start, h_middle, h_end, v_start, v_middle, v_end = names
        calt_rules.append(
            contextual_extension_rules(
                f"{prefix}_h", base, h_start, h_middle, h_end
            )
        )
        calt_rules.append(
            contextual_extension_rules(
                f"{prefix}_v", vertical, v_start, v_middle, v_end
            )
        )
        vertical_maps = (
            f"  sub {h_start} by {v_start};\n"
            f"  sub {h_middle} by {v_middle};\n"
            f"  sub {h_end} by {v_end};\n"
        )
        vert_rules.append(
            contextual_extension_rules(
                f"{prefix}_vert", base, v_start, v_middle, v_end
            )
            + vertical_maps
        )
        vrt2_rules.append(
            contextual_extension_rules(
                f"{prefix}_vrt2", base, v_start, v_middle, v_end
            )
            + vertical_maps
        )

    wave_prefix, wave_base, wave_vertical, wave_names = wave
    horizontal_wave_names = wave_names[:5]
    vertical_wave_names = wave_names[5:]
    calt_rules.append(
        alternating_wave_rules(
            f"{wave_prefix}_h", wave_base, horizontal_wave_names
        )
    )
    calt_rules.append(
        alternating_wave_rules(
            f"{wave_prefix}_v", wave_vertical, vertical_wave_names
        )
    )
    wave_vertical_maps = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in zip(
            horizontal_wave_names, vertical_wave_names, strict=True
        )
    )
    vert_rules.append(
        alternating_wave_rules(
            f"{wave_prefix}_vert", wave_base, vertical_wave_names
        )
        + wave_vertical_maps
    )
    vrt2_rules.append(
        alternating_wave_rules(
            f"{wave_prefix}_vrt2", wave_base, vertical_wave_names
        )
        + wave_vertical_maps
    )

    manga_wave_prefix, manga_wave_base, manga_wave_names = manga_wave
    (
        manga_wave_start,
        manga_wave_middle,
        manga_wave_end,
        manga_wave_vertical_isolated,
        manga_wave_vertical_start,
        manga_wave_vertical_middle,
        manga_wave_vertical_end,
    ) = manga_wave_names
    calt_rules.append(
        contextual_extension_rules(
            f"{manga_wave_prefix}_h",
            manga_wave_base,
            manga_wave_start,
            manga_wave_middle,
            manga_wave_end,
        )
    )
    manga_wave_vertical_maps = (
        f"  sub {manga_wave_base} by {manga_wave_vertical_isolated};\n"
        f"  sub {manga_wave_start} by {manga_wave_vertical_start};\n"
        f"  sub {manga_wave_middle} by {manga_wave_vertical_middle};\n"
        f"  sub {manga_wave_end} by {manga_wave_vertical_end};\n"
    )
    vert_rules.append(
        contextual_extension_rules(
            f"{manga_wave_prefix}_vert",
            manga_wave_base,
            manga_wave_vertical_start,
            manga_wave_vertical_middle,
            manga_wave_vertical_end,
        )
        + manga_wave_vertical_maps
    )
    vrt2_rules.append(
        contextual_extension_rules(
            f"{manga_wave_prefix}_vrt2",
            manga_wave_base,
            manga_wave_vertical_start,
            manga_wave_vertical_middle,
            manga_wave_vertical_end,
        )
        + manga_wave_vertical_maps
    )

    kana_vertical_rules = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in kana_vertical_maps
    )
    vert_rules.append(kana_vertical_rules)
    vrt2_rules.append(kana_vertical_rules)

    punctuation_names = dict(punctuation_variants)
    ccmp_rules = punctuation_ligature_rules(
        punctuation_names["!"][0],
        punctuation_names["?"][0],
        [
            (sequence, names[0])
            for sequence, names in punctuation_variants
            if len(sequence) > 1
        ],
    )
    ccmp_rules += "".join(
        f"  sub {base} {mark} by {output};\n"
        for base, mark, output in kana_marks
    )
    alternate_rules = "".join(
        f"  sub {names[0]} from [{' '.join(names[1:])}];\n"
        for _, names in punctuation_variants
    )
    stylistic_set_rules = [
        "".join(
            f"  sub {names[0]} by {names[index]};\n"
            for _, names in punctuation_variants
        )
        for index in range(1, 4)
    ]
    ruby_rules = "".join(
        f"  sub {normal} by {ruby};\n"
        for normal, ruby in ruby_substitutions
    )

    return (
        "languagesystem DFLT dflt;\n\n"
        f"feature ccmp {{\n{ccmp_rules}}} ccmp;\n\n"
        f"feature calt {{\n{''.join(calt_rules)}}} calt;\n\n"
        f"feature aalt {{\n{alternate_rules}}} aalt;\n\n"
        f"feature ss01 {{\n{stylistic_set_rules[0]}}} ss01;\n\n"
        f"feature ss02 {{\n{stylistic_set_rules[1]}}} ss02;\n\n"
        f"feature ss03 {{\n{stylistic_set_rules[2]}}} ss03;\n\n"
        f"feature ruby {{\n{ruby_rules}}} ruby;\n\n"
        f"feature vert {{\n{''.join(vert_rules)}}} vert;\n\n"
        f"feature vrt2 {{\n{''.join(vrt2_rules)}}} vrt2;\n"
    )


def shift_nested_lookup_indices(value: object, amount: int, seen: set[int]) -> None:
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)

    if value.__class__.__name__ in {"SubstLookupRecord", "PosLookupRecord"}:
        value.LookupListIndex += amount
    if isinstance(value, (list, tuple)):
        for item in value:
            shift_nested_lookup_indices(item, amount, seen)
    elif hasattr(value, "__dict__"):
        for item in vars(value).values():
            shift_nested_lookup_indices(item, amount, seen)


def all_langsys(script_list: object):
    for script_record in script_list.ScriptRecord:
        script = script_record.Script
        if script.DefaultLangSys is not None:
            yield script.DefaultLangSys
        for lang_record in script.LangSysRecord:
            yield lang_record.LangSys


def merge_features(font: TTFont, source: str) -> None:
    patch_font = TTFont()
    patch_font.setGlyphOrder(font.getGlyphOrder())
    addOpenTypeFeaturesFromString(patch_font, source, tables={"GSUB"})

    old = font["GSUB"].table
    patch = patch_font["GSUB"].table
    new_lookups = patch.LookupList.Lookup
    shift = len(new_lookups)

    for lookup in old.LookupList.Lookup:
        shift_nested_lookup_indices(lookup, shift, set())
    for record in old.FeatureList.FeatureRecord:
        record.Feature.LookupListIndex = [
            index + shift for index in record.Feature.LookupListIndex
        ]
    if getattr(old, "FeatureVariations", None) is not None:
        for variation in old.FeatureVariations.FeatureVariationRecord:
            substitutions = variation.FeatureTableSubstitution.SubstitutionRecord
            for substitution in substitutions:
                substitution.Feature.LookupListIndex = [
                    index + shift for index in substitution.Feature.LookupListIndex
                ]

    old.LookupList.Lookup = new_lookups + old.LookupList.Lookup
    old.LookupList.LookupCount = len(old.LookupList.Lookup)

    patch_by_tag = {
        record.FeatureTag: record.Feature.LookupListIndex
        for record in patch.FeatureList.FeatureRecord
    }
    old_by_tag: dict[str, list[object]] = {}
    for record in old.FeatureList.FeatureRecord:
        old_by_tag.setdefault(record.FeatureTag, []).append(record)

    for tag, lookup_indices in patch_by_tag.items():
        if tag in old_by_tag:
            for record in old_by_tag[tag]:
                record.Feature.LookupListIndex = (
                    lookup_indices + record.Feature.LookupListIndex
                )
                record.Feature.LookupCount = len(record.Feature.LookupListIndex)
            continue

        patch_record = next(
            record for record in patch.FeatureList.FeatureRecord if record.FeatureTag == tag
        )
        feature_index = next(
            (
                index
                for index, record in enumerate(old.FeatureList.FeatureRecord)
                if record.FeatureTag > tag
            ),
            len(old.FeatureList.FeatureRecord),
        )
        for langsys in all_langsys(old.ScriptList):
            langsys.FeatureIndex = sorted(
                [
                    index + 1 if index >= feature_index else index
                    for index in langsys.FeatureIndex
                ]
                + [feature_index]
            )
            langsys.FeatureCount = len(langsys.FeatureIndex)
            if langsys.ReqFeatureIndex != 0xFFFF and langsys.ReqFeatureIndex >= feature_index:
                langsys.ReqFeatureIndex += 1
        if getattr(old, "FeatureVariations", None) is not None:
            for variation in old.FeatureVariations.FeatureVariationRecord:
                substitutions = variation.FeatureTableSubstitution.SubstitutionRecord
                for substitution in substitutions:
                    if substitution.FeatureIndex >= feature_index:
                        substitution.FeatureIndex += 1
        old.FeatureList.FeatureRecord.insert(
            feature_index, copy.deepcopy(patch_record)
        )
        old.FeatureList.FeatureCount = len(old.FeatureList.FeatureRecord)


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name_table = font["name"]
    matching = [record for record in name_table.names if record.nameID == name_id]
    if matching:
        for record in matching:
            name_table.setName(
                value,
                name_id,
                record.platformID,
                record.platEncID,
                record.langID,
            )
    else:
        name_table.setName(value, name_id, 3, 1, 0x409)


def set_japanese_name(font: TTFont, name_id: int, value: str) -> None:
    font["name"].setName(value, name_id, 3, 1, 0x411)


def rename_font(
    font: TTFont,
    copyright_notice: str,
    font_notice: str,
    identity: FontIdentity,
) -> None:
    legacy_style = "Bold" if identity.style == "Bold" else "Regular"
    set_name(font, 0, copyright_notice)
    set_name(font, 1, identity.legacy_family)
    set_name(font, 2, legacy_style)
    set_name(
        font,
        3,
        f"{VERSION_NUMBER};NOBIGOE;{identity.postscript_name}",
    )
    set_name(font, 4, identity.full_name)
    set_name(font, 5, VERSION)
    set_name(font, 6, identity.postscript_name)
    set_name(font, 16, identity.family)
    set_name(font, 17, identity.style)
    set_japanese_name(font, 1, identity.japanese_legacy_family)
    set_japanese_name(font, 4, identity.japanese_full_name)
    set_japanese_name(font, 16, identity.japanese_family)
    set_japanese_name(font, 17, identity.style)

    font["OS/2"].usWeightClass = identity.weight_class
    font["OS/2"].fsSelection &= ~((1 << 5) | (1 << 6))
    if identity.style == "Regular":
        font["OS/2"].fsSelection |= 1 << 6
    elif identity.style == "Bold":
        font["OS/2"].fsSelection |= 1 << 5
    font["head"].macStyle &= ~1
    if identity.style == "Bold":
        font["head"].macStyle |= 1

    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames = [identity.postscript_name]
        top = cff.topDictIndex[0]
        top.Notice = font_notice.encode("latin-1", "replace").decode("latin-1")
        top.FamilyName = identity.family
        top.FullName = identity.full_name


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
        raise RuntimeError(
            "--autohint requires the AFDKO otfautohint command on PATH"
        )
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


def build(
    source_path: Path,
    latin_source_path: Path | None,
    ruby_source_path: Path,
    punctuation_source_path: Path,
    sans_source_path: Path,
    output_path: Path,
    identity: FontIdentity,
    latin_profile: LatinBuildProfile,
    face: int,
    base_type: BaseType,
    autohint: bool = False,
) -> None:
    if autohint and latin_source_path is None:
        raise ValueError("--autohint requires an imported Latin source")
    font = TTFont(source_path, fontNumber=face, recalcTimestamp=True)
    if font["head"].unitsPerEm != 1000:
        scale_upem(font, 1000)
    latin_font = TTFont(latin_source_path) if latin_source_path else None
    if latin_font and latin_profile.variations:
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
    ruby_font = TTFont(ruby_source_path) if base_type == "noto" else None
    if ruby_font and ruby_font["head"].unitsPerEm != 1000:
        scale_upem(ruby_font, 1000)
    punctuation_font = TTFont(punctuation_source_path)
    sans_font = TTFont(sans_source_path)
    cmap = font.getBestCmap()
    punctuation_cmap = punctuation_font.getBestCmap()
    sans_cmap = sans_font.getBestCmap()
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
            "The punctuation source does not contain "
            + ", ".join(punctuation_missing)
        )
    upright_punctuation = shippori_upright_punctuation_paths(
        punctuation_font
    )
    if (
        punctuation_font["head"].unitsPerEm
        != font["head"].unitsPerEm
    ):
        raise ValueError(
            "The base and punctuation sources must use the same "
            "units per em"
        )
    sans_missing = [
        f"U+{codepoint:04X}"
        for codepoint in (0xFF01, 0xFF1F)
        if codepoint not in sans_cmap
    ]
    if sans_missing:
        raise ValueError(
            "The sans source does not contain " + ", ".join(sans_missing)
        )
    if sans_font["head"].unitsPerEm != font["head"].unitsPerEm:
        raise ValueError(
            "The base and sans sources must use the same units per em"
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
    if not set(_mark_positioning.KOBURI_PUA_MARK_PAIRS) <= set(_mark_positioning.MANGA_MARK_PAIRS):
        raise AssertionError("Koburi Mincho PUA mappings must use Manga1 sequences")
    if len(_mark_positioning.KOBURI_GENERATED_MARK_PAIRS) != 103:
        raise AssertionError("Expected 103 generated Koburi mark sequences")
    if len(_mark_positioning.KOBURI_HEART_MARK_PAIRS) != 2:
        raise AssertionError("Expected two Koburi Mincho heart mappings")
    latin_import = (
        _font_operations.import_latin_font(font, latin_font, latin_profile)
        if latin_font is not None
        else None
    )

    source_ccmp_ligatures = _font_operations.feature_ligatures(font, "ccmp")
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
                "GenEi Koburi Mincho ccmp mappings must contain "
                "U+30FC+U+3099"
            )
        if set(native_heart_outputs) != set(
            _mark_positioning.KOBURI_HEART_MARK_PAIRS
        ):
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
                or source_ccmp_ligatures.get(
                    (cmap[base_pua], cmap[mark])
                )
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
    generated_mark_pairs = [
        pair for pair in supported_mark_pairs if pair not in native_mark_outputs
    ]
    generated_vertical_mark_pairs = list(generated_mark_pairs)
    generated_heart_pairs = [
        pair
        for pair in _mark_positioning.KOBURI_HEART_MARK_PAIRS
        if pair not in native_heart_outputs
    ]

    allocated_names = _font_operations.allocate_cid_names(
        font,
        NEW_GLYPH_COUNT * len(linear_codepoints)
        + WAVE_GLYPH_COUNT
        + MANGA_WAVE_GLYPH_COUNT
        + len(MANGA_PUNCTUATION_SEQUENCES)
        + PUNCTUATION_ALTERNATE_COUNT
        + 2 * len(_mark_positioning.MANGA_MISSING_SMALL_KANA)
        + len(generated_mark_pairs)
        + len(generated_vertical_mark_pairs)
        + len(generated_heart_pairs)
        + (KOBURI_RUBY_OUTPUT_COUNT if ruby_font else 0),
    )
    extensions: list[tuple[str, str, str, list[str]]] = []
    for index, (prefix, codepoint) in enumerate(linear_codepoints):
        base = cmap[codepoint]
        start = index * NEW_GLYPH_COUNT
        names = allocated_names[start : start + NEW_GLYPH_COUNT]
        vertical, names = add_linear_extension(
            font,
            base,
            names,
            flatten_horizontal=codepoint == 0x30FC,
        )
        extensions.append((prefix, base, vertical, names))

    wave_base = cmap[0x301C]
    wave_vertical = _font_operations.find_vertical_glyph(font, wave_base)
    _, _, _, wave_vertical_y_max = _font_geometry.bounds(font, wave_vertical)
    wave_vertical_origin = round(
        font["vmtx"].metrics[wave_vertical][1] + wave_vertical_y_max
    )
    wave_start = len(linear_codepoints) * NEW_GLYPH_COUNT
    wave_names = allocated_names[
        wave_start : wave_start + WAVE_GLYPH_COUNT
    ]
    wave_parts = make_wave_parts(
        _font_geometry.glyph_path(font, wave_base), 1000, wave_vertical_origin
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

    manga_wave_base = cmap[0x3030]
    _, _, _, manga_wave_y_max = _font_geometry.bounds(font, manga_wave_base)
    manga_wave_vertical_origin = round(
        font["vmtx"].metrics[manga_wave_base][1] + manga_wave_y_max
    )
    manga_wave_start = wave_start + WAVE_GLYPH_COUNT
    manga_wave_names = allocated_names[
        manga_wave_start : manga_wave_start + MANGA_WAVE_GLYPH_COUNT
    ]
    manga_wave_isolated, manga_wave_parts = make_manga_wave_parts(
        _font_geometry.glyph_path(font, wave_base),
        1000,
        manga_wave_vertical_origin,
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

    punctuation_start = manga_wave_start + MANGA_WAVE_GLYPH_COUNT
    punctuation_names = allocated_names[
        punctuation_start : punctuation_start
        + len(MANGA_PUNCTUATION_SEQUENCES)
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
        mincho_punctuation_paths[sequence]
        for sequence in MANGA_PUNCTUATION_SEQUENCES
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
    default_punctuation_paths = {
        "!": upright_exclamation,
        "?": upright_question,
        **dict(
            zip(
                MANGA_PUNCTUATION_SEQUENCES,
                punctuation_paths,
                strict=True,
            )
        ),
    }
    punctuation_alternate_start = (
        punctuation_start + len(MANGA_PUNCTUATION_SEQUENCES)
    )
    punctuation_alternate_names = allocated_names[
        punctuation_alternate_start
        : punctuation_alternate_start + PUNCTUATION_ALTERNATE_COUNT
    ]
    punctuation_alternate_paths: list[pathops.Path] = []
    punctuation_variants: list[
        tuple[str, tuple[str, str, str, str]]
    ] = []
    for index, sequence in enumerate(PUNCTUATION_VARIANT_SEQUENCES):
        default_path = default_punctuation_paths[sequence]
        if len(sequence) == 1:
            sans_path = _font_geometry.glyph_path(sans_font,
            sans_cmap[0xFF01 if sequence == "!" else 0xFF1F],)
        else:
            sans_path = make_sans_punctuation_ligature(
                sans_font, sequence
            )
        alternate_paths = (
            slant_punctuation_outline(default_path),
            sans_path,
            slant_punctuation_outline(sans_path),
        )
        punctuation_alternate_paths.extend(alternate_paths)
        name_start = index * 3
        alternate_names = tuple(
            punctuation_alternate_names[name_start : name_start + 3]
        )
        punctuation_variants.append(
            (
                sequence,
                (
                    default_punctuation_names[sequence],
                    *alternate_names,
                ),
            )
        )
    _font_operations.append_glyphs(
        font,
        punctuation_alternate_paths,
        punctuation_alternate_names,
        cmap[0xFF01],
        punctuation_vertical_origin,
        add_stem_hints=False,
        advance_override=1000,
    )

    kana_start = punctuation_alternate_start + PUNCTUATION_ALTERNATE_COUNT
    small_kana_names = allocated_names[
        kana_start : kana_start + 2 * len(_mark_positioning.MANGA_MISSING_SMALL_KANA)
    ]
    small_hiragana = _font_geometry.centered_scaled_path(_font_geometry.glyph_path(font, cmap[0x3053]), 0.775, 500, 253)
    small_katakana = _font_geometry.centered_scaled_path(_font_geometry.glyph_path(font, cmap[0x30B3]), 0.775, 500, 253)
    small_hiragana_vertical = _font_geometry.centered_scaled_path(_font_geometry.glyph_path(font, _font_operations.vertical_glyph_or_self(font, cmap[0x3053])),
    0.78,
    654,
    397,)
    small_katakana_vertical = _font_geometry.centered_scaled_path(_font_geometry.glyph_path(font, _font_operations.vertical_glyph_or_self(font, cmap[0x30B3])),
    0.78,
    654,
    397,)
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
        glyphs for glyphs in missing_small_glyphs.values()
    ]
    for codepoint, (horizontal, _) in missing_small_glyphs.items():
        _font_operations.add_unicode_mapping(font, codepoint, horizontal)
        cmap[codepoint] = horizontal

    mark_horizontal_start = kana_start + len(small_kana_names)
    generated_mark_names = allocated_names[
        mark_horizontal_start
        : mark_horizontal_start + len(generated_mark_pairs)
    ]
    generated_mark_outputs = dict(
        zip(generated_mark_pairs, generated_mark_names, strict=True)
    )
    mark_paths = {
        codepoint: _font_geometry.glyph_path(font, cmap[codepoint])
        for codepoint in (0x3099, 0x309A)
    }
    horizontal_mark_paths = []
    for base, mark in generated_mark_pairs:
        base_path = _font_geometry.glyph_path(font, cmap[base])
        if (base, mark) == _mark_positioning.CHOON_DAKUTEN_PAIR:
            target_x, target_y = (
                _mark_positioning.CHOON_DAKUTEN_MARK_CENTERS["horizontal"]
            )
            mark_transform = _font_geometry.centered_transform(
                mark_paths[mark], 1, target_x, target_y
            )
        else:
            mark_transform = mark_position_overrides[(base, mark)]["horizontal"]
        horizontal_mark_paths.append(
            _font_geometry.compose_mark_glyph(base_path, mark_paths[mark], mark_transform)
        )
    _font_operations.append_glyphs(
        font,
        horizontal_mark_paths,
        generated_mark_names,
        cmap[0x3042],
        880,
        add_stem_hints=False,
    )

    mark_vertical_start = mark_horizontal_start + len(
        generated_mark_pairs
    )
    generated_vertical_mark_names = allocated_names[
        mark_vertical_start
        : mark_vertical_start + len(generated_vertical_mark_pairs)
    ]
    vertical_mark_paths = []
    for base, mark in generated_vertical_mark_pairs:
        if base in missing_small_glyphs:
            vertical_base = missing_small_glyphs[base][1]
        else:
            vertical_base = _font_operations.vertical_glyph_or_self(font, cmap[base])
        base_path = _font_geometry.glyph_path(font, vertical_base)
        if (base, mark) == _mark_positioning.CHOON_DAKUTEN_PAIR:
            target_x, target_y = (
                _mark_positioning.CHOON_DAKUTEN_MARK_CENTERS["vertical"]
            )
            mark_transform = _font_geometry.centered_transform(
                mark_paths[mark], 1, target_x, target_y
            )
        else:
            mark_transform = mark_position_overrides[(base, mark)]["vertical"]
        vertical_mark_paths.append(
            _font_geometry.compose_mark_glyph(base_path, mark_paths[mark], mark_transform)
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
            (
                generated_mark_outputs[pair]
                for pair in generated_vertical_mark_pairs
            ),
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
    heart_outputs.update(
        zip(generated_heart_pairs, heart_names, strict=True)
    )
    for codepoint, (base, _) in zip(
        _mark_positioning.KOBURI_HEART_BASE_PUA,
        _mark_positioning.KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        _font_operations.add_unicode_mapping_if_missing(
            font, codepoint, cmap[base]
        )
    for codepoint, pair in zip(
        _mark_positioning.KOBURI_HEART_OUTPUT_PUA,
        _mark_positioning.KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        output = heart_outputs[pair]
        if cmap.get(codepoint) != output:
            _font_operations.add_unicode_mapping(font, codepoint, output)

    mark_outputs = native_mark_outputs | generated_mark_outputs
    ruby_start = heart_start + len(generated_heart_pairs)
    ruby_names = allocated_names[
        ruby_start : ruby_start
        + (KOBURI_RUBY_OUTPUT_COUNT if ruby_font else 0)
    ]
    ruby_substitutions: list[tuple[str, str]] = []
    if ruby_font is not None:
        ruby_substitutions, ruby_vertical_maps = import_koburi_ruby(
            font,
            ruby_font,
            cmap,
            mark_outputs,
            missing_small_glyphs,
            ruby_names,
            weight_adjustment=KOBURI_RUBY_STROKE_ADJUSTMENTS[identity.style],
        )
        kana_vertical_maps.extend(ruby_vertical_maps)
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
    kana_marks = [
        (cmap[base], cmap[mark], mark_outputs[(base, mark)])
        for base, mark in supported_mark_pairs
    ]
    kana_marks.extend(
        (cmap[base], cmap[mark], heart_outputs[(base, mark)])
        for base, mark in _mark_positioning.KOBURI_HEART_MARK_PAIRS
    )

    latin_copyright = (
        (latin_font["name"].getDebugName(0) or latin_profile.copyright)
        if latin_font
        else None
    )
    ruby_copyright = (
        ruby_font["name"].getDebugName(0) if ruby_font else None
    )
    ruby_license = (
        ruby_font["name"].getDebugName(13) if ruby_font else None
    )
    latin_license = (
        latin_font["name"].getDebugName(13) if latin_font else None
    )
    copyright_notices = [
        notice
        for notice in (
            font["name"].getDebugName(0),
            latin_copyright,
            ruby_copyright,
            SHIPPORI_COPYRIGHT,
        )
        if notice
    ]
    copyright_notice = " / ".join(dict.fromkeys(copyright_notices))
    source_notice = (
        font["CFF "].cff.topDictIndex[0].Notice
        if "CFF " in font
        else font["name"].getDebugName(13)
    )
    font_notices = [
        notice
        for notice in (
            source_notice,
            ruby_license,
            latin_license,
            SHIPPORI_COPYRIGHT,
        )
        if notice
    ]
    font_notice = " / ".join(dict.fromkeys(font_notices))

    merge_features(
        font,
        feature_source(
            extensions,
            wave,
            manga_wave,
            punctuation_variants,
            kana_marks,
            kana_vertical_maps,
            ruby_substitutions,
        ),
    )
    rename_font(font, copyright_notice, font_notice, identity)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path, reorderTables=True)
    if autohint:
        autohint_latin_glyphs(output_path, latin_import.glyph_names)


def main() -> None:
    args = parse_args()
    if args.base == "koburi" and args.weight != "Regular":
        raise ValueError("GenEi Koburi Mincho is available in Regular only")
    if args.base == "koburi" and args.latin_source is not None:
        raise ValueError("--latin-source is available for the Noto base only")
    if args.base == "koburi" and args.ruby_source is not None:
        raise ValueError("--ruby-source is available for the Noto base only")
    if args.base == "koburi" and args.latin_family != "libertinus":
        raise ValueError("--latin-family is available for the Noto base only")
    if (
        args.base == "noto"
        and args.latin_family == "noto"
        and args.latin_source is not None
    ):
        raise ValueError("--latin-source cannot be combined with --latin-family noto")
    identity = font_identity(args.base, args.weight)
    latin_profile = latin_build_profile(
        args.latin_family if args.base == "noto" else "noto",
        args.weight,
    )
    if args.output is not None:
        output_path = args.output
    elif args.base == "noto" and args.latin_family != "libertinus":
        output_path = (
            Path("dist")
            / "comparison"
            / f"{identity.postscript_name}-{args.latin_family}.otf"
        )
    else:
        output_path = default_output_path(identity, args.base)
    sources = SourceCache(args.cache_dir).resolve(
        args.base,
        args.weight,
        SourceOverrides(
            source=args.source,
            latin_source=args.latin_source,
            ruby_source=args.ruby_source,
            punctuation_source=args.punctuation_source,
            sans_source=args.sans_source,
        ),
        latin_family=args.latin_family,
    )

    build(
        sources.source,
        sources.latin_source,
        sources.ruby_source,
        sources.punctuation_source,
        sources.sans_source,
        output_path,
        identity,
        latin_profile,
        args.face,
        args.base,
        args.autohint,
    )


if __name__ == "__main__":
    main()
