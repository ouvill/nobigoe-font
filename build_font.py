#!/usr/bin/env python3
"""Build a Noto Serif JP derivative with extensible manga punctuation."""

from __future__ import annotations

import argparse
import copy
import math
import tempfile
import urllib.request
from pathlib import Path

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

SOURCE_URL = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/main/"
    "Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf"
)
DEFAULT_OUTPUT = Path("dist/NotoSerifJPChoon-Regular.otf")
FAMILY = "Noto Serif JP Choon"
FULL_NAME = f"{FAMILY} Regular"
POSTSCRIPT_NAME = "NotoSerifJPChoon-Regular"
VERSION_NUMBER = "1.002"
WAVE_GLYPH_COUNT = 10
VERSION = f"Version {VERSION_NUMBER}"
NEW_GLYPH_COUNT = 6
OVERLAP = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add automatically joining ー, ―, 〜, and ～ glyphs to "
            "Noto Serif JP. Consecutive marks join through the calt feature."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Noto Serif JP OTF/TTC source (the official JP SubsetOTF is recommended)",
    )
    parser.add_argument("--face", type=int, default=0, help="TTC face index")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


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
    end_tile: bool = False,
) -> pathops.Path:
    sample_peak_min, sample_peak_max = stroke_band(
        source, "horizontal", advance / 4
    )
    sample_trough_min, sample_trough_max = stroke_band(
        source, "horizontal", 3 * advance / 4
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
    normal_phase_velocity = 3 * math.pi / advance
    taper_length = advance / 4

    source_x_min, _, source_x_max, _ = source.bounds
    left_min, left_max = stroke_band(
        source, "horizontal", source_x_min + 2
    )
    right_min, right_max = stroke_band(
        source, "horizontal", source_x_max - 2
    )
    source_left_center = (left_min + left_max) / 2
    source_right_center = (right_min + right_max) / 2
    phase_ratio = (
        source_left_center - source_right_center
    ) / (2 * amplitude)
    phase_offset = math.asin(min(1.0, max(-1.0, phase_ratio)))
    if not end_tile:
        phase_span = 3 * math.pi
    elif inverted:
        phase_span = 2 * math.pi - 2 * phase_offset
    else:
        phase_span = 3 * math.pi - 2 * phase_offset

    def phase_at(position: float) -> tuple[float, float]:
        progress = position / advance
        if not end_tile:
            return (
                phase_offset + phase_span * progress,
                normal_phase_velocity,
            )
        h01 = -2 * progress**3 + 3 * progress**2
        h10 = progress**3 - 2 * progress**2 + progress
        h11 = progress**3 - progress**2
        phase_progress = (
            phase_span * h01
            + 3 * math.pi * h10
            + 3 * math.pi * h11
        )
        h01_derivative = -6 * progress**2 + 6 * progress
        h10_derivative = 3 * progress**2 - 4 * progress + 1
        h11_derivative = 3 * progress**2 - 2 * progress
        phase_velocity = (
            phase_span * h01_derivative
            + 3 * math.pi * h10_derivative
            + 3 * math.pi * h11_derivative
        ) / advance
        return phase_offset + phase_progress, phase_velocity


    def smoothstep(progress: float) -> float:
        return progress * progress * (3 - 2 * progress)


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
    for index in range(-8, 16):
        target = math.pi / 2 + index * math.pi - phase_offset
        if not 0 < target < phase_span:
            continue
        if not end_tile:
            breakpoints.add(target / normal_phase_velocity)
            continue
        lower = 0.0
        upper = float(advance)
        for _ in range(32):
            middle = (lower + upper) / 2
            middle_phase, _ = phase_at(middle)
            if middle_phase - phase_offset < target:
                lower = middle
            else:
                upper = middle
        breakpoints.add((lower + upper) / 2)

    points: list[tuple[float, float, float, bool]] = []
    for position in sorted(breakpoints):
        phase, phase_velocity = phase_at(position)
        center = baseline + direction * amplitude * math.sin(phase)
        sine_slope = (
            direction * amplitude * phase_velocity * math.cos(phase)
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
        make_sine_wave_tile(
            source, advance, taper_end=True, end_tile=True
        ),
        make_sine_wave_tile(
            source,
            advance,
            inverted=True,
            taper_end=True,
            end_tile=True,
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


def append_cff_glyphs(
    font: TTFont,
    paths: list[pathops.Path],
    names: list[str],
    source_glyph: str,
    vertical_origin: int,
    add_stem_hints: bool = True,
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
    advance = font["hmtx"].metrics[source_glyph][0]
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


def add_linear_extension(
    font: TTFont, base: str, names: list[str]
) -> tuple[str, list[str]]:
    vertical = find_vertical_glyph(font, base)
    advance = font["hmtx"].metrics[base][0]
    if advance != 1000:
        raise ValueError(f"Expected a 1000-unit full-width glyph, got {advance}")

    horizontal_parts = make_horizontal_parts(glyph_path(font, base), advance)
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

    return (
        "languagesystem DFLT dflt;\n\n"
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


def rename_font(font: TTFont) -> None:
    set_name(font, 1, FAMILY)
    set_name(font, 2, "Regular")
    set_name(font, 3, f"{VERSION_NUMBER};CHOON;{POSTSCRIPT_NAME}")
    set_name(font, 4, FULL_NAME)
    set_name(font, 5, VERSION)
    set_name(font, 6, POSTSCRIPT_NAME)
    set_name(font, 16, FAMILY)
    set_name(font, 17, "Regular")

    cff = font["CFF "].cff
    cff.fontNames = [POSTSCRIPT_NAME]
    top = cff.topDictIndex[0]
    top.FamilyName = FAMILY
    top.FullName = FULL_NAME


def build(source_path: Path, output_path: Path, face: int) -> None:
    font = TTFont(source_path, fontNumber=face, recalcTimestamp=True)
    cmap = font.getBestCmap()
    linear_codepoints = [("choon", 0x30FC), ("dash", 0x2015)]
    required_codepoints = [codepoint for _, codepoint in linear_codepoints]
    required_codepoints.extend([0x301C, 0xFF5E])
    missing = [
        f"U+{codepoint:04X}"
        for codepoint in required_codepoints
        if codepoint not in cmap
    ]
    if missing:
        raise ValueError(f"The source font does not contain {', '.join(missing)}")
    if cmap[0x301C] != cmap[0xFF5E]:
        raise ValueError("U+301C and U+FF5E must share a source glyph")

    allocated_names = allocate_cid_names(
        font,
        NEW_GLYPH_COUNT * len(linear_codepoints) + WAVE_GLYPH_COUNT,
    )
    extensions: list[tuple[str, str, str, list[str]]] = []
    for index, (prefix, codepoint) in enumerate(linear_codepoints):
        base = cmap[codepoint]
        start = index * NEW_GLYPH_COUNT
        names = allocated_names[start : start + NEW_GLYPH_COUNT]
        vertical, names = add_linear_extension(font, base, names)
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

    merge_features(font, feature_source(extensions, wave))
    rename_font(font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path, reorderTables=True)


def main() -> None:
    args = parse_args()
    if args.source is not None:
        build(args.source, args.output, args.face)
        return

    with tempfile.TemporaryDirectory(prefix="noto-serif-choon-") as directory:
        source_path = Path(directory) / "NotoSerifJP-Regular.otf"
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, source_path)
        build(source_path, args.output, 0)


if __name__ == "__main__":
    main()
