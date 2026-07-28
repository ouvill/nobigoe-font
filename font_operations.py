"""Font table inspection and glyph mutation operations."""

from __future__ import annotations

from collections.abc import Iterable
import math
from typing import Protocol

import font_geometry as _font_geometry
import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


class TrueTypeGlyph(Protocol):
    """Observable TrueType glyph data returned by ``TTGlyphPen``."""

    numberOfContours: int
    coordinates: object
    flags: Iterable[int]


_LATIN_REPLACEMENT_RANGES = (
    (0x0020, 0x024F),
    (0x1E00, 0x1EFF),
)
_LATIN_TYPOGRAPHIC_CODEPOINTS = (
    0x2010,
    0x2011,
    0x2012,
    0x2013,
    0x2014,
    0x2018,
    0x2019,
    0x201A,
    0x201B,
    0x201C,
    0x201D,
    0x201E,
    0x201F,
    0x2020,
    0x2021,
    0x2022,
    0x2026,
    0x2030,
    0x2031,
    0x2039,
    0x203A,
)


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


def feature_single_substitutions(
    font: TTFont, feature_tag: str
) -> dict[str, str]:
    lookup_indices: list[int] = []
    for record in font["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag == feature_tag:
            lookup_indices.extend(record.Feature.LookupListIndex)

    substitutions: dict[str, str] = {}
    for index in dict.fromkeys(lookup_indices):
        lookup = font["GSUB"].table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            if lookup.LookupType == 7:
                subtable = subtable.ExtSubTable
            mapping = getattr(subtable, "mapping", None)
            if mapping is not None:
                substitutions.update(mapping)
    return substitutions


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


def add_unicode_mapping_if_missing(
    font: TTFont, codepoint: int, fallback_name: str
) -> str:
    existing_name = font.getBestCmap().get(codepoint)
    if existing_name is not None:
        return existing_name
    add_unicode_mapping(font, codepoint, fallback_name)
    return fallback_name


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
    *,
    advance_override: int | None = None,
    left_side_bearing_override: int | None = None,
) -> None:
    cff = font["CFF "].cff
    top = cff.topDictIndex[0]
    char_strings = top.CharStrings
    glyph_id = font.getGlyphID(name)
    fd_index = top.FDSelect[glyph_id]
    private = top.FDArray[fd_index].Private
    advance = (
        font["hmtx"].metrics[name][0]
        if advance_override is None
        else advance_override
    )
    pen = T2CharStringPen(advance, None)
    outline.draw(pen)
    char_string = pen.getCharString(
        private=private, globalSubrs=cff.GlobalSubrs
    )
    char_strings.charStringsIndex[char_strings.charStrings[name]] = char_string
    x_min, _, _, y_max = outline.bounds
    left_side_bearing = (
        math.floor(x_min)
        if left_side_bearing_override is None
        else left_side_bearing_override
    )
    font["hmtx"].metrics[name] = (advance, left_side_bearing)
    if "vmtx" in font:
        font["vmtx"].metrics[name] = (
            font["vmtx"].metrics[name][0],
            math.floor(vertical_origin - y_max),
        )


def tt_glyph(outline: pathops.Path, units_per_em: int) -> TrueTypeGlyph:
    pen = TTGlyphPen(None)
    outline.draw(Cu2QuPen(pen, max_err=units_per_em / 1000))
    return pen.glyph()


def append_ttf_glyphs(
    font: TTFont,
    paths: list[pathops.Path],
    names: list[str],
    source_glyph: str,
    vertical_origin: int,
    advance_override: int | None = None,
) -> None:
    if len(font.getGlyphOrder()) + len(names) > 65535:
        raise ValueError("The source already fills the OpenType glyph limit")
    glyph_order = font.getGlyphOrder() + names
    advance = (
        font["hmtx"].metrics[source_glyph][0]
        if advance_override is None
        else advance_override
    )
    glyf = font["glyf"]
    units_per_em = font["head"].unitsPerEm
    for name, outline in zip(names, paths, strict=True):
        glyf[name] = tt_glyph(outline, units_per_em)
        x_min, _, _, y_max = outline.bounds
        font["hmtx"].metrics[name] = (advance, math.floor(x_min))
        if "vmtx" in font:
            font["vmtx"].metrics[name] = (
                advance,
                math.floor(vertical_origin - y_max),
            )

    font.setGlyphOrder(glyph_order)
    glyf.glyphOrder = glyph_order
    font["maxp"].numGlyphs = len(glyph_order)


def replace_ttf_glyph(
    font: TTFont,
    name: str,
    outline: pathops.Path,
    vertical_origin: int,
    *,
    advance_override: int | None = None,
    left_side_bearing_override: int | None = None,
) -> None:
    font["glyf"][name] = tt_glyph(outline, font["head"].unitsPerEm)
    advance = (
        font["hmtx"].metrics[name][0]
        if advance_override is None
        else advance_override
    )
    x_min, _, _, y_max = outline.bounds
    left_side_bearing = (
        math.floor(x_min)
        if left_side_bearing_override is None
        else left_side_bearing_override
    )
    font["hmtx"].metrics[name] = (advance, left_side_bearing)
    if "vmtx" in font:
        font["vmtx"].metrics[name] = (
            font["vmtx"].metrics[name][0],
            math.floor(vertical_origin - y_max),
        )


def append_glyphs(
    font: TTFont,
    paths: list[pathops.Path],
    names: list[str],
    source_glyph: str,
    vertical_origin: int,
    add_stem_hints: bool = True,
    advance_override: int | None = None,
) -> None:
    if "CFF " in font:
        append_cff_glyphs(
            font,
            paths,
            names,
            source_glyph,
            vertical_origin,
            add_stem_hints,
            advance_override,
        )
        return
    if "glyf" in font:
        append_ttf_glyphs(
            font,
            paths,
            names,
            source_glyph,
            vertical_origin,
            advance_override,
        )
        return
    raise ValueError("Only OpenType/CFF and TrueType outlines are supported")


def replace_glyph(
    font: TTFont,
    name: str,
    outline: pathops.Path,
    vertical_origin: int,
    *,
    advance_override: int | None = None,
    left_side_bearing_override: int | None = None,
) -> None:
    replace = replace_cff_glyph if "CFF " in font else replace_ttf_glyph
    if "CFF " not in font and "glyf" not in font:
        raise ValueError("Only OpenType/CFF and TrueType outlines are supported")
    replace(
        font,
        name,
        outline,
        vertical_origin,
        advance_override=advance_override,
        left_side_bearing_override=left_side_bearing_override,
    )


def replace_glyph_from_source(
    font: TTFont,
    target_name: str,
    source_font: TTFont,
    source_name: str,
    horizontal_weight_adjustment: float = 0,
    scale_factor: float = 1,
) -> None:
    if scale_factor <= 0:
        raise ValueError("Latin scale factor must be positive")
    try:
        _, _, _, target_y_max = _font_geometry.bounds(font, target_name)
    except ValueError:
        target_y_max = 0
    vertical_origin = (
        font["vmtx"].metrics[target_name][1] + target_y_max
        if "vmtx" in font
        else 0
    )
    source_advance, source_lsb = source_font["hmtx"].metrics[source_name]
    outline = _font_geometry.glyph_path(source_font, source_name)
    if scale_factor != 1:
        outline = _font_geometry.transform_path(
            outline,
            Transform(scale_factor, 0, 0, scale_factor, 0, 0),
        )
    outline = _font_geometry.adjust_outline_horizontal_weight(
        outline,
        horizontal_weight_adjustment,
    )
    left_side_bearing = (
        math.floor(outline.bounds[0])
        if (scale_factor != 1 or horizontal_weight_adjustment) and outline.verbs
        else round(source_lsb * scale_factor)
    )
    replace_glyph(
        font,
        target_name,
        outline,
        round(vertical_origin),
        advance_override=round(source_advance * scale_factor),
        left_side_bearing_override=left_side_bearing,
    )


def replace_latin_glyphs(
    font: TTFont,
    latin_font: TTFont,
    horizontal_weight_adjustment: float = 0,
    scale_factor: float = 1,
) -> tuple[int, ...]:
    target_cmap = font.getBestCmap()
    latin_cmap = latin_font.getBestCmap()
    required = range(0x0020, 0x007F)
    missing = [
        f"U+{codepoint:04X}"
        for codepoint in required
        if codepoint not in target_cmap or codepoint not in latin_cmap
    ]
    if missing:
        raise ValueError(
            "The base and Latin sources must contain Basic Latin: "
            + ", ".join(missing)
        )

    candidates = {
        codepoint
        for start, end in _LATIN_REPLACEMENT_RANGES
        for codepoint in range(start, end + 1)
    }
    candidates.update(_LATIN_TYPOGRAPHIC_CODEPOINTS)
    replaced: list[int] = []
    replaced_names: set[str] = set()
    for codepoint in sorted(candidates):
        if codepoint not in target_cmap or codepoint not in latin_cmap:
            continue
        target_name = target_cmap[codepoint]
        if target_name in replaced_names:
            continue
        source_name = latin_cmap[codepoint]
        replace_glyph_from_source(
            font,
            target_name,
            latin_font,
            source_name,
            horizontal_weight_adjustment,
            scale_factor,
        )
        replaced.append(codepoint)
        replaced_names.add(target_name)
    return tuple(replaced)


def replace_latin_gsub_glyphs(
    font: TTFont,
    latin_font: TTFont,
    replaced_codepoints: tuple[int, ...],
    horizontal_weight_adjustment: float = 0,
    scale_factor: float = 1,
) -> tuple[str, ...]:
    target_cmap = font.getBestCmap()
    latin_cmap = latin_font.getBestCmap()
    replaced_outputs: set[str] = set()
    replaced_set = set(replaced_codepoints)
    protected_names = {
        glyph_name
        for codepoint, glyph_name in target_cmap.items()
        if codepoint not in replaced_set
    }

    target_defaults: dict[str, str] = {}
    for feature_tag in ("ccmp", "locl"):
        target_defaults.update(feature_single_substitutions(font, feature_tag))
        target_defaults.update(
            {
                components[0]: output
                for components, output in feature_ligatures(font, feature_tag).items()
                if len(components) == 1
            }
        )
    for codepoint in replaced_codepoints:
        target_name = target_cmap[codepoint]
        source_name = latin_cmap[codepoint]
        while target_name in target_defaults:
            replacement_name = target_defaults[target_name]
            if replacement_name in protected_names:
                break
            target_name = replacement_name
            if target_name in replaced_outputs:
                break
            replace_glyph_from_source(
                font,
                target_name,
                latin_font,
                source_name,
                horizontal_weight_adjustment,
                scale_factor,
            )
            replaced_outputs.add(target_name)

    source_codepoints = {
        glyph_name: codepoint
        for codepoint, glyph_name in latin_cmap.items()
        if codepoint in replaced_codepoints
    }
    target_ligatures = feature_ligatures(font, "liga")
    source_ligatures = feature_ligatures(latin_font, "liga")
    for source_components, source_output in source_ligatures.items():
        if not all(component in source_codepoints for component in source_components):
            continue
        codepoints = tuple(
            source_codepoints[component] for component in source_components
        )
        target_components = tuple(target_cmap[codepoint] for codepoint in codepoints)
        target_output = target_ligatures.get(target_components)
        if target_output is None or target_output in replaced_outputs:
            continue
        replace_glyph_from_source(
            font,
            target_output,
            latin_font,
            source_output,
            horizontal_weight_adjustment,
            scale_factor,
        )
        replaced_outputs.add(target_output)
    return tuple(sorted(replaced_outputs))
