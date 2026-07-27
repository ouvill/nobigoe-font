#!/usr/bin/env python3
"""Build a Noto Serif JP derivative with extensible manga punctuation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

NOTO_COMMIT = "9b0f1436e455d902de067a2501422e5dc71ad16b"
NOTO_SOURCE_URL = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/"
    f"{NOTO_COMMIT}/Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf"
)
NOTO_SOURCE_SHA256 = (
    "2c9a12dbd4f2408c4610c7ee84a108b62d7236c3775baed618c64d9cb44b2f04"
)
SHIPPORI_ARCHIVE_URL = "https://fontdasu.com/download/shippori3.zip"
SHIPPORI_ARCHIVE_SHA256 = (
    "dbdcab920d82238bda26296bccd9630906b427ee91b31f5da2dde8e47b0b202e"
)
SHIPPORI_OTF_MEMBER = "ShipporiMincho-OTF-Regular.otf"
SHIPPORI_OTF_SHA256 = (
    "f597e65ce1e686ad36b63e0c82e4931e9d815187ff2311705dcf1b751ecae804"
)
SHIPPORI_COPYRIGHT = (
    "Copyright (c) 2021, The Shippori Mincho Project Authors "
    "(https://github.com/fontdasu/ShipporiMincho)"
)
DEFAULT_OUTPUT = Path("dist/NobigoeMincho-Regular.otf")
FAMILY = "Nobigoe Mincho"
JAPANESE_FAMILY = "のびごえ明朝"
FULL_NAME = f"{FAMILY} Regular"
JAPANESE_FULL_NAME = f"{JAPANESE_FAMILY} Regular"
POSTSCRIPT_NAME = "NobigoeMincho-Regular"
VERSION_NUMBER = "1.016"
WAVE_GLYPH_COUNT = 10
MANGA_WAVE_GLYPH_COUNT = 7
WAVE_TERMINAL_EXTENSION_HALF_WAVES = 0.15
VERSION = f"Version {VERSION_NUMBER}"
NEW_GLYPH_COUNT = 6
OVERLAP = 0
SHIPPORI_PRECOMPOSED_LIGATURES = {
    "!!": 0x203C,
    "??": 0x2047,
    "?!": 0x2048,
    "!?": 0x2049,
}
SHIPPORI_COMPONENT_LIGATURES = {
    "!": 0x203C,
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

MANGA_DAKUTEN_BASES = tuple(
    int(value, 16)
    for value in """
3042 3041 3044 3043 3045 3048 3047 304A
3049 3095 3096 1B132 3063 306A 306B 306C
306D 306E 307E 307F 3080 3081 3082 3084
3083 3086 3085 3088 3087 3089 308A 308B
308C 308D 308F 308E 3090 3091 3092 3093
309F 30A2 30A1 30A4 30A3 30A5 30A8 30A7
30AA 30A9 30F5 30F6 1B155 30C3 30CA 30CB
30CC 30CD 30CE 30DE 30DF 30E0 30E1 30E2
30E4 30E3 30E6 30E5 30E8 30E7 30E9 30EA
30EB 30EC 30ED 30EE 30F3
""".split()
)
MANGA_HANDAKUTEN_BASES = tuple(
    int(value, 16)
    for value in """
304B 304D 304F 3051 3053 30AB 30AD 30AF
30B1 30B3 30BB 30C4 30C8 31F7 3042 3041
3044 3043 3046 3045 3048 3047 304A 3049
3095 3096 1B132 3055 3057 3059 305B 305D
305F 3061 3064 3063 3066 3068 306A 306B
306C 306D 306E 307E 307F 3080 3081 3082
3084 3083 3086 3085 3088 3087 3089 308A
308B 308C 308D 308F 308E 3090 3091 3092
3093 309F 30A2 30A1 30A4 30A3 30A6 30A5
30A8 30A7 30AA 30A9 30F5 30F6 1B155 30B5
30B7 30B9 30BD 30BF 30C1 30C3 30C6 30CA
30CB 30CC 30CD 30CE 30DE 30DF 30E0 30E1
30E2 30E4 30E3 30E6 30E5 30E8 30E7 30E9
30EA 30EB 30EC 30ED 30EF 30EE 30F0 30F1
30F2 30F3
""".split()
)
MANGA_MARK_PAIRS = tuple(
    [(base, 0x3099) for base in MANGA_DAKUTEN_BASES]
    + [(base, 0x309A) for base in MANGA_HANDAKUTEN_BASES]
)
MANGA_VERTICAL_DAKUTEN_BASES = tuple(
    int(value, 16)
    for value in """
3041 3043 3045 3047 3049 3095 3096 1B132
3063 3083 3085 3087 308E 30A1 30A3 30A5
30A7 30A9 30F5 30F6 1B155 30C3 30E3 30E5
30E7 30EE
""".split()
)
MANGA_VERTICAL_HANDAKUTEN_BASES = tuple(
    int(value, 16)
    for value in """
31F7 3041 3043 3045 3047 3049 3095 3096
1B132 3063 3083 3085 3087 308E 30A1 30A3
30A5 30A7 30A9 30F5 30F6 1B155 30C3 30E3
30E5 30E7 30EE
""".split()
)
MANGA_VERTICAL_MARK_PAIRS = frozenset(
    [(base, 0x3099) for base in MANGA_VERTICAL_DAKUTEN_BASES]
    + [
        (base, 0x309A)
        for base in MANGA_VERTICAL_HANDAKUTEN_BASES
    ]
)
MANGA_SMALL_KANA_BASES = frozenset(
    MANGA_VERTICAL_DAKUTEN_BASES
    + MANGA_VERTICAL_HANDAKUTEN_BASES
)
DEFAULT_MARK_TRANSFORM = Transform(1, 0, 0, 1, 1000, 0)
MARK_POSITION_GROUPS = (
    ("hiragana_dakuten.json", 0x3099, "hiragana"),
    ("hiragana_handakuten.json", 0x309A, "hiragana"),
    ("katakana_dakuten.json", 0x3099, "katakana"),
    ("katakana_handakuten.json", 0x309A, "katakana"),
)
MARK_POSITION_DIRECTORY = Path(__file__).resolve().parent / "mark_positions"
MANGA_MISSING_SMALL_KANA = (0x1B132, 0x1B155)


def small_kana_script(codepoint: int) -> str:
    if 0x3040 <= codepoint <= 0x309F or codepoint == 0x1B132:
        return "hiragana"
    return "katakana"


def load_mark_position_overrides(
    directory: Path = MARK_POSITION_DIRECTORY,
) -> dict[tuple[int, int], dict[str, Transform]]:
    expected_pairs = set(MANGA_MARK_PAIRS)
    loaded: dict[tuple[int, int], dict[str, Transform]] = {}
    for filename, expected_mark, expected_script in MARK_POSITION_GROUPS:
        path = directory / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        mark = int(data["mark"], 16)
        if mark != expected_mark:
            raise ValueError(
                f"{path}: expected mark U+{expected_mark:04X}, "
                f"got U+{mark:04X}"
            )
        positions = data["positions"]
        expected_bases = {
            base
            for base, pair_mark in expected_pairs
            if pair_mark == mark
            and small_kana_script(base) == expected_script
        }
        actual_bases = {int(value, 16) for value in positions}
        if actual_bases != expected_bases:
            missing = expected_bases - actual_bases
            extra = actual_bases - expected_bases
            details = [
                *(f"missing U+{value:04X}" for value in sorted(missing)),
                *(f"extra U+{value:04X}" for value in sorted(extra)),
            ]
            raise ValueError(f"{path}: {', '.join(details)}")
        for base_hex, orientations in positions.items():
            base = int(base_hex, 16)
            pair = (base, mark)
            loaded[pair] = {}
            for orientation in ("horizontal", "vertical"):
                values = orientations[orientation]
                if len(values) != 3:
                    raise ValueError(
                        f"{path}: U+{base:04X} {orientation} "
                        "must be [scale, x, y]"
                    )
                scale, x_offset, y_offset = values
                if scale <= 0:
                    raise ValueError(
                        f"{path}: U+{base:04X} {orientation} "
                        "scale must be positive"
                    )
                loaded[pair][orientation] = Transform(
                    scale,
                    0,
                    0,
                    scale,
                    x_offset,
                    y_offset,
                )
    if loaded.keys() != expected_pairs:
        raise AssertionError("Mark position files must cover all 191 sequences")
    return loaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add automatically joining ー, ―, 〜, ～, and 〰 glyphs to "
            "Noto Serif JP. Consecutive marks join through the calt feature."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        help=(
            "Noto Serif JP OTF/TTC source "
            "(the official JP SubsetOTF is recommended)"
        ),
    )
    parser.add_argument(
        "--punctuation-source",
        type=Path,
        help=(
            "Shippori Mincho Regular OTF/TTF used for Manga1 "
            "exclamation/question ligatures (OTF is recommended)"
        ),
    )
    parser.add_argument(
        "--face", type=int, default=0, help="TTC face index"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def verify_sha256(path: Path, expected: str) -> None:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}: {digest} != {expected}"
        )


def rectangle(x_min: float, y_min: float, x_max: float, y_max: float) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_min))
    pen.lineTo((x_max, y_max))
    pen.lineTo((x_min, y_max))
    pen.closePath()
    return path




def glyph_path(font: TTFont, glyph_name: str) -> pathops.Path:
    path = pathops.Path()
    font.getGlyphSet()[glyph_name].draw(path.getPen())
    return path


def bounds(font: TTFont, glyph_name: str) -> tuple[float, float, float, float]:
    pen = BoundsPen(font.getGlyphSet())
    font.getGlyphSet()[glyph_name].draw(pen)
    if pen.bounds is None:
        raise ValueError(f"Glyph {glyph_name} has no outline")
    return pen.bounds


def find_vertical_glyph(font: TTFont, base_name: str) -> str:
    table = font["GSUB"].table
    lookup_indices: list[int] = []
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag in {"vert", "vrt2"}:
            lookup_indices.extend(record.Feature.LookupListIndex)

    for index in dict.fromkeys(lookup_indices):
        lookup = table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            if lookup.LookupType == 7:
                subtable = subtable.ExtSubTable
            mapping = getattr(subtable, "mapping", None)
            if mapping and base_name in mapping:
                return mapping[base_name]
    raise ValueError(f"The source font has no vertical substitution for {base_name}")


def vertical_glyph_or_self(font: TTFont, base_name: str) -> str:
    try:
        return find_vertical_glyph(font, base_name)
    except ValueError:
        return base_name


def feature_ligatures(
    font: TTFont, feature_tag: str
) -> dict[tuple[str, ...], str]:
    lookup_indices: list[int] = []
    for record in font["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag == feature_tag:
            lookup_indices.extend(record.Feature.LookupListIndex)

    substitutions: dict[tuple[str, ...], str] = {}
    for index in dict.fromkeys(lookup_indices):
        lookup = font["GSUB"].table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            if lookup.LookupType == 7:
                subtable = subtable.ExtSubTable
            ligatures = getattr(subtable, "ligatures", None)
            if ligatures is None:
                continue
            for first, records in ligatures.items():
                for ligature in records:
                    substitutions[
                        (first, *ligature.Component)
                    ] = ligature.LigGlyph
    return substitutions


def add_unicode_mapping(font: TTFont, codepoint: int, name: str) -> None:
    mapped = False
    for table in font["cmap"].tables:
        if not table.isUnicode():
            continue
        if codepoint > 0xFFFF and table.format not in {12, 13}:
            continue
        table.cmap[codepoint] = name
        mapped = True
    if not mapped:
        raise ValueError(f"No cmap subtable supports U+{codepoint:04X}")


def centered_scaled_path(
    outline: pathops.Path,
    scale: float,
    target_x: float,
    target_y: float,
) -> pathops.Path:
    x_min, y_min, x_max, y_max = outline.bounds
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    return transform_path(
        outline,
        Transform(
            scale,
            0,
            0,
            scale,
            target_x - scale * center_x,
            target_y - scale * center_y,
        ),
    )


def compose_mark_glyph(
    base: pathops.Path,
    mark: pathops.Path,
    mark_transform: Transform = DEFAULT_MARK_TRANSFORM,
) -> pathops.Path:
    combined = pathops.Path()
    combined.addPath(base)
    combined.addPath(transform_path(mark, mark_transform))
    return combined


def allocate_cid_names(font: TTFont, count: int) -> list[str]:
    existing = set(font.getGlyphOrder())
    available = [
        f"cid{cid:05d}"
        for cid in range(65534, -1, -1)
        if f"cid{cid:05d}" not in existing
    ]
    if len(available) < count:
        raise ValueError("The source CFF has no free CID values for the added glyphs")
    return list(reversed(available[:count]))


def stroke_band(
    outline: pathops.Path, axis: str, seam: float
) -> tuple[int, int]:
    if axis == "horizontal":
        sample = rectangle(seam - 0.5, -4096, seam + 0.5, 4096)
        clipped = pathops.op(outline, sample, pathops.PathOp.INTERSECTION)
        low, high = clipped.bounds[1], clipped.bounds[3]
    else:
        sample = rectangle(-4096, seam - 0.5, 4096, seam + 0.5)
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
    clip_left = rectangle(-4096, -4096, seam, 4096)
    clip_right = rectangle(seam, -4096, 4096, 4096)
    left_cap = pathops.op(outline, clip_left, pathops.PathOp.INTERSECTION)
    right_cap = pathops.op(outline, clip_right, pathops.PathOp.INTERSECTION)

    start_bar = rectangle(seam - OVERLAP, y_min, advance + OVERLAP, y_max)
    middle = rectangle(-OVERLAP, y_min, advance + OVERLAP, y_max)
    end_bar = rectangle(-OVERLAP, y_min, seam + OVERLAP, y_max)
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
    return transform_path(
        outline,
        Transform(1, -slope, 0, 1, 0, slope * seam),
    )


def make_vertical_parts(
    outline: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance * 0.4
    x_min, x_max = stroke_band(outline, "vertical", seam)
    clip_top = rectangle(-4096, seam, 4096, 4096)
    clip_bottom = rectangle(-4096, -4096, 4096, seam)
    top_cap = pathops.op(outline, clip_top, pathops.PathOp.INTERSECTION)
    bottom_cap = pathops.op(outline, clip_bottom, pathops.PathOp.INTERSECTION)

    cell_top = vertical_origin
    cell_bottom = vertical_origin - advance
    start_bar = rectangle(
        x_min, cell_bottom - OVERLAP, x_max, seam + OVERLAP
    )
    middle = rectangle(
        x_min, cell_bottom - OVERLAP, x_max, cell_top + OVERLAP
    )
    end_bar = rectangle(x_min, seam - OVERLAP, x_max, cell_top + OVERLAP)
    start = pathops.op(top_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, bottom_cap, pathops.PathOp.UNION)
    return start, middle, end


def transform_path(outline: pathops.Path, transform: Transform) -> pathops.Path:
    transformed = pathops.Path()
    outline.draw(TransformPen(transformed.getPen(), transform))
    return transformed


def make_sine_wave_tile(
    source: pathops.Path,
    advance: int,
    *,
    inverted: bool = False,
    taper_start: bool = False,
    taper_end: bool = False,
    half_waves: float = 3,
    taper_fraction: float = 1 / 4,
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
            progress = min(1.0, max(0.0, position / taper_length))
            scale *= smoothstep(progress)
        if taper_end:
            progress = min(
                1.0, max(0.0, (advance - position) / taper_length)
            )
            scale *= smoothstep(progress)
        return half_stroke * scale


    breakpoints = {0.0, float(advance)}
    if taper_start:
        breakpoints.add(taper_length)
    if taper_end:
        breakpoints.add(advance - taper_length)
    phase_start, _ = phase_at(0)
    phase_end, _ = phase_at(advance)
    for index in range(-8, 16):
        target = math.pi / 2 + index * math.pi
        if not phase_start < target < phase_end:
            continue
        lower = 0.0
        upper = float(advance)
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
    pen.moveTo((0, points[0][1] + width_at(0)))
    for control_1, control_2, endpoint in segments:
        pen.curveTo(
            (control_1[0], control_1[1] + width_at(control_1[0])),
            (control_2[0], control_2[1] + width_at(control_2[0])),
            (endpoint[0], endpoint[1] + width_at(endpoint[0])),
        )
    pen.lineTo((advance, points[-1][1] - width_at(advance)))
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
    horizontal = (
        make_sine_wave_tile(source, advance, taper_start=True),
        make_sine_wave_tile(source, advance),
        make_sine_wave_tile(source, advance, inverted=True),
        make_sine_wave_tile(source, advance, taper_end=True),
        make_sine_wave_tile(
            source, advance, inverted=True, taper_end=True
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
        transform_path(outline, vertical_phase_flip)
        for outline in horizontal
    )
    return horizontal + vertical


def make_manga_wave_parts(
    source: pathops.Path, advance: int, vertical_origin: int
) -> tuple[pathops.Path, tuple[pathops.Path, ...]]:
    parameters = {
        "half_waves": 4,
        "taper_fraction": 1 / 6,
    }
    horizontal_isolated = make_sine_wave_tile(
        source,
        advance,
        taper_start=True,
        taper_end=True,
        **parameters,
    )
    horizontal_start = make_sine_wave_tile(
        source, advance, taper_start=True, **parameters
    )
    horizontal_middle = make_sine_wave_tile(
        source, advance, **parameters
    )
    horizontal_end = make_sine_wave_tile(
        source, advance, taper_end=True, **parameters
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
        transform_path(outline, vertical_rotation)
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


def make_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    components: list[tuple[pathops.Path, float, float]] = []
    total_width = gap * (len(sequence) - 1)
    cmap = font.getBestCmap()
    precomposed_codepoint = SHIPPORI_PRECOMPOSED_LIGATURES.get(
        sequence
    )
    if precomposed_codepoint is not None:
        return glyph_path(font, cmap[precomposed_codepoint])

    for mark in sequence:
        if mark == "!" and "?" in sequence:
            source_codepoint = SHIPPORI_PRECOMPOSED_LIGATURES["!?"]
        else:
            source_codepoint = SHIPPORI_COMPONENT_LIGATURES[mark]
        source = glyph_path(font, cmap[source_codepoint])
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


def append_cff_glyphs(
    font: TTFont,
    paths: list[pathops.Path],
    names: list[str],
    source_glyph: str,
    vertical_origin: int,
    add_stem_hints: bool = True,
    advance_override: int | None = None,
) -> None:
    if "CFF " not in font:
        raise ValueError("Only OpenType/CFF Noto Serif JP sources are supported")
    if len(font.getGlyphOrder()) + len(names) > 65535:
        raise ValueError(
            "The source already fills the OpenType glyph limit; use Noto Serif JP SubsetOTF"
        )

    cff = font["CFF "].cff
    top = cff.topDictIndex[0]
    char_strings = top.CharStrings
    source_gid = font.getGlyphID(source_glyph)
    fd_index = top.FDSelect[source_gid]
    private = top.FDArray[fd_index].Private
    advance = (
        font["hmtx"].metrics[source_glyph][0]
        if advance_override is None
        else advance_override
    )
    hints: list[tuple[int, int, str]] = []
    if add_stem_hints:
        horizontal_bounds = paths[1].bounds
        vertical_bounds = paths[4].bounds
        hints = [
            (
                round(horizontal_bounds[1]),
                round(horizontal_bounds[3] - horizontal_bounds[1]),
                "hstem",
            ),
            (
                round(vertical_bounds[0]),
                round(vertical_bounds[2] - vertical_bounds[0]),
                "vstem",
            ),
        ]

    for index, (name, outline) in enumerate(zip(names, paths, strict=True)):
        pen = T2CharStringPen(advance, None)
        outline.draw(pen)
        char_string = pen.getCharString(private=private, globalSubrs=cff.GlobalSubrs)
        if add_stem_hints:
            if not char_string.program or char_string.program[0] != advance:
                raise ValueError("Could not locate the Type 2 width operand")
            stem_start, stem_width, operator = hints[index // 3]
            char_string.program[1:1] = [stem_start, stem_width, operator]
        char_strings.charStrings[name] = len(char_strings.charStringsIndex)
        char_strings.charStringsIndex.append(char_string)
        top.FDSelect.gidArray.append(fd_index)

        x_min, _, _, y_max = outline.bounds
        font["hmtx"].metrics[name] = (advance, math.floor(x_min))
        if "vmtx" in font:
            font["vmtx"].metrics[name] = (advance, math.floor(vertical_origin - y_max))

    glyph_order = font.getGlyphOrder() + names
    font.setGlyphOrder(glyph_order)
    top.charset = glyph_order
    top.numGlyphs = len(glyph_order)
    font["maxp"].numGlyphs = len(glyph_order)


def replace_cff_glyph(
    font: TTFont,
    name: str,
    outline: pathops.Path,
    vertical_origin: int,
) -> None:
    cff = font["CFF "].cff
    top = cff.topDictIndex[0]
    char_strings = top.CharStrings
    glyph_id = font.getGlyphID(name)
    fd_index = top.FDSelect[glyph_id]
    private = top.FDArray[fd_index].Private
    advance = font["hmtx"].metrics[name][0]
    pen = T2CharStringPen(advance, None)
    outline.draw(pen)
    char_string = pen.getCharString(
        private=private, globalSubrs=cff.GlobalSubrs
    )
    char_strings.charStringsIndex[char_strings.charStrings[name]] = char_string
    x_min, _, _, y_max = outline.bounds
    font["hmtx"].metrics[name] = (advance, math.floor(x_min))
    if "vmtx" in font:
        font["vmtx"].metrics[name] = (
            font["vmtx"].metrics[name][0],
            math.floor(vertical_origin - y_max),
        )


def add_linear_extension(
    font: TTFont,
    base: str,
    names: list[str],
    *,
    flatten_horizontal: bool = False,
) -> tuple[str, list[str]]:
    vertical = find_vertical_glyph(font, base)
    advance = font["hmtx"].metrics[base][0]
    if advance != 1000:
        raise ValueError(f"Expected a 1000-unit full-width glyph, got {advance}")

    horizontal_outline = glyph_path(font, base)
    if flatten_horizontal:
        horizontal_outline = flatten_horizontal_centerline(
            horizontal_outline, advance
        )
    horizontal_parts = make_horizontal_parts(horizontal_outline, advance)
    _, _, _, vertical_y_max = bounds(font, vertical)
    vertical_origin = round(font["vmtx"].metrics[vertical][1] + vertical_y_max)
    vertical_parts = make_vertical_parts(
        glyph_path(font, vertical), advance, vertical_origin
    )
    append_cff_glyphs(
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




def feature_source(
    extensions: list[tuple[str, str, str, list[str]]],
    wave: tuple[str, str, str, list[str]],
    manga_wave: tuple[str, str, list[str]],
    punctuation: tuple[str, str, list[tuple[str, str]]],
    kana_marks: list[tuple[str, str, str]],
    kana_vertical_maps: list[tuple[str, str]],
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

    exclamation, question, ligatures = punctuation
    ccmp_rules = punctuation_ligature_rules(
        exclamation, question, ligatures
    )
    ccmp_rules += "".join(
        f"  sub {base} {mark} by {output};\n"
        for base, mark, output in kana_marks
    )

    return (
        "languagesystem DFLT dflt;\n\n"
        f"feature ccmp {{\n{ccmp_rules}}} ccmp;\n\n"
        f"feature calt {{\n{''.join(calt_rules)}}} calt;\n\n"
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
    font: TTFont, copyright_notice: str, font_notice: str
) -> None:
    set_name(font, 0, copyright_notice)
    set_name(font, 1, FAMILY)
    set_name(font, 2, "Regular")
    set_name(font, 3, f"{VERSION_NUMBER};NOBIGOE;{POSTSCRIPT_NAME}")
    set_name(font, 4, FULL_NAME)
    set_name(font, 5, VERSION)
    set_name(font, 6, POSTSCRIPT_NAME)
    set_name(font, 16, FAMILY)
    set_name(font, 17, "Regular")
    set_japanese_name(font, 1, JAPANESE_FAMILY)
    set_japanese_name(font, 4, JAPANESE_FULL_NAME)
    set_japanese_name(font, 16, JAPANESE_FAMILY)

    cff = font["CFF "].cff
    cff.fontNames = [POSTSCRIPT_NAME]
    top = cff.topDictIndex[0]
    top.Notice = font_notice
    top.FamilyName = FAMILY
    top.FullName = FULL_NAME


def build(
    source_path: Path,
    punctuation_source_path: Path,
    output_path: Path,
    face: int,
) -> None:
    font = TTFont(source_path, fontNumber=face, recalcTimestamp=True)
    punctuation_font = TTFont(punctuation_source_path)
    cmap = font.getBestCmap()
    punctuation_cmap = punctuation_font.getBestCmap()
    punctuation_missing = [
        f"U+{codepoint:04X}"
        for codepoint in SHIPPORI_PRECOMPOSED_LIGATURES.values()
        if codepoint not in punctuation_cmap
    ]
    if punctuation_missing:
        raise ValueError(
            "The punctuation source does not contain "
            + ", ".join(punctuation_missing)
        )
    if (
        punctuation_font["head"].unitsPerEm
        != font["head"].unitsPerEm
    ):
        raise ValueError(
            "The base and punctuation sources must use the same "
            "units per em"
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
        for base, _ in MANGA_MARK_PAIRS
        if base not in MANGA_MISSING_SMALL_KANA
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

    if len(MANGA_MARK_PAIRS) != 191:
        raise AssertionError("Expected 191 Manga1 kana mark sequences")
    if len(MANGA_VERTICAL_MARK_PAIRS) != 53:
        raise AssertionError("Expected 53 vertical Manga1 kana mark sequences")
    mark_position_overrides = load_mark_position_overrides()
    source_ccmp_ligatures = feature_ligatures(font, "ccmp")
    native_mark_outputs: dict[tuple[int, int], str] = {}
    for base, mark in MANGA_MARK_PAIRS:
        if base not in cmap:
            continue
        output = source_ccmp_ligatures.get((cmap[base], cmap[mark]))
        if output is not None:
            native_mark_outputs[(base, mark)] = output
    generated_mark_pairs = [
        pair for pair in MANGA_MARK_PAIRS if pair not in native_mark_outputs
    ]
    generated_vertical_mark_pairs = list(generated_mark_pairs)

    allocated_names = allocate_cid_names(
        font,
        NEW_GLYPH_COUNT * len(linear_codepoints)
        + WAVE_GLYPH_COUNT
        + MANGA_WAVE_GLYPH_COUNT
        + len(MANGA_PUNCTUATION_SEQUENCES)
        + 2 * len(MANGA_MISSING_SMALL_KANA)
        + len(generated_mark_pairs)
        + len(generated_vertical_mark_pairs),
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
    wave_vertical = find_vertical_glyph(font, wave_base)
    _, _, _, wave_vertical_y_max = bounds(font, wave_vertical)
    wave_vertical_origin = round(
        font["vmtx"].metrics[wave_vertical][1] + wave_vertical_y_max
    )
    wave_start = len(linear_codepoints) * NEW_GLYPH_COUNT
    wave_names = allocated_names[
        wave_start : wave_start + WAVE_GLYPH_COUNT
    ]
    wave_parts = make_wave_parts(
        glyph_path(font, wave_base), 1000, wave_vertical_origin
    )
    append_cff_glyphs(
        font,
        list(wave_parts),
        wave_names,
        wave_base,
        wave_vertical_origin,
        add_stem_hints=False,
    )
    wave = ("wave", wave_base, wave_vertical, wave_names)

    manga_wave_base = cmap[0x3030]
    _, _, _, manga_wave_y_max = bounds(font, manga_wave_base)
    manga_wave_vertical_origin = round(
        font["vmtx"].metrics[manga_wave_base][1] + manga_wave_y_max
    )
    manga_wave_start = wave_start + WAVE_GLYPH_COUNT
    manga_wave_names = allocated_names[
        manga_wave_start : manga_wave_start + MANGA_WAVE_GLYPH_COUNT
    ]
    manga_wave_isolated, manga_wave_parts = make_manga_wave_parts(
        glyph_path(font, wave_base),
        1000,
        manga_wave_vertical_origin,
    )
    replace_cff_glyph(
        font,
        manga_wave_base,
        manga_wave_isolated,
        manga_wave_vertical_origin,
    )
    append_cff_glyphs(
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
    punctuation_paths = [
        make_punctuation_ligature(punctuation_font, sequence)
        for sequence in MANGA_PUNCTUATION_SEQUENCES
    ]
    punctuation_vertical_origin = round(
        font["vmtx"].metrics[cmap[0xFF01]][1]
        + bounds(font, cmap[0xFF01])[3]
    )
    append_cff_glyphs(
        font,
        punctuation_paths,
        punctuation_names,
        cmap[0x21],
        punctuation_vertical_origin,
        add_stem_hints=False,
        advance_override=1000,
    )
    punctuation = (
        cmap[0xFF01],
        cmap[0xFF1F],
        list(
            zip(
                MANGA_PUNCTUATION_SEQUENCES,
                punctuation_names,
                strict=True,
            )
        ),
    )

    kana_start = punctuation_start + len(MANGA_PUNCTUATION_SEQUENCES)
    small_kana_names = allocated_names[
        kana_start : kana_start + 2 * len(MANGA_MISSING_SMALL_KANA)
    ]
    small_hiragana = centered_scaled_path(
        glyph_path(font, cmap[0x3053]), 0.775, 500, 253
    )
    small_katakana = centered_scaled_path(
        glyph_path(font, cmap[0x30B3]), 0.775, 500, 253
    )
    small_hiragana_vertical = centered_scaled_path(
        glyph_path(
            font, find_vertical_glyph(font, cmap[0x3053])
        ),
        0.78,
        654,
        397,
    )
    small_katakana_vertical = centered_scaled_path(
        glyph_path(
            font, find_vertical_glyph(font, cmap[0x30B3])
        ),
        0.78,
        654,
        397,
    )
    append_cff_glyphs(
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
        add_unicode_mapping(font, codepoint, horizontal)
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
        codepoint: glyph_path(font, cmap[codepoint])
        for codepoint in (0x3099, 0x309A)
    }
    horizontal_mark_paths = [
        compose_mark_glyph(
            glyph_path(font, cmap[base]),
            mark_paths[mark],
            mark_position_overrides[(base, mark)]["horizontal"],
        )
        for base, mark in generated_mark_pairs
    ]
    append_cff_glyphs(
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
            vertical_base = vertical_glyph_or_self(font, cmap[base])
        vertical_mark_paths.append(
            compose_mark_glyph(
                glyph_path(font, vertical_base),
                mark_paths[mark],
                mark_position_overrides[(base, mark)]["vertical"],
            )
        )
    append_cff_glyphs(
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
            (horizontal, find_vertical_glyph(font, horizontal))
        )

    mark_outputs = native_mark_outputs | generated_mark_outputs
    kana_marks = [
        (cmap[base], cmap[mark], mark_outputs[(base, mark)])
        for base, mark in MANGA_MARK_PAIRS
    ]

    copyright_notices = [
        notice
        for notice in (
            font["name"].getDebugName(0),
            SHIPPORI_COPYRIGHT,
        )
        if notice
    ]
    copyright_notice = " / ".join(dict.fromkeys(copyright_notices))
    font_notices = [
        notice
        for notice in (
            font["CFF "].cff.topDictIndex[0].Notice,
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
            punctuation,
            kana_marks,
            kana_vertical_maps,
        ),
    )
    rename_font(font, copyright_notice, font_notice)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path, reorderTables=True)


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(
        prefix="noto-serif-choon-"
    ) as directory:
        temporary_directory = Path(directory)
        source_path = args.source
        if source_path is None:
            source_path = (
                temporary_directory / "NotoSerifJP-Regular.otf"
            )
            print(f"Downloading {NOTO_SOURCE_URL}")
            urllib.request.urlretrieve(NOTO_SOURCE_URL, source_path)
            verify_sha256(source_path, NOTO_SOURCE_SHA256)

        punctuation_source_path = args.punctuation_source
        if punctuation_source_path is None:
            punctuation_archive_path = (
                temporary_directory / "shippori3.zip"
            )
            punctuation_source_path = (
                temporary_directory / SHIPPORI_OTF_MEMBER
            )
            print(f"Downloading {SHIPPORI_ARCHIVE_URL}")
            urllib.request.urlretrieve(
                SHIPPORI_ARCHIVE_URL, punctuation_archive_path
            )
            verify_sha256(
                punctuation_archive_path, SHIPPORI_ARCHIVE_SHA256
            )
            with zipfile.ZipFile(punctuation_archive_path) as archive:
                punctuation_source_path.write_bytes(
                    archive.read(SHIPPORI_OTF_MEMBER)
                )
            verify_sha256(
                punctuation_source_path, SHIPPORI_OTF_SHA256
            )

        build(
            source_path,
            punctuation_source_path,
            args.output,
            args.face,
        )


if __name__ == "__main__":
    main()
