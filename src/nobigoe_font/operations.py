"""Font table inspection and glyph mutation operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from io import BytesIO
import math
import unicodedata
from typing import Protocol

from .profiles import LatinBuildProfile, LatinGlyphClass, LatinTransform
from . import geometry as _font_geometry
import pathops
from fontTools import subset
from fontTools.merge import Merger
from fontTools.merge.layout import layoutPostMerge, layoutPreMerge
from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttVisitor import TTVisitor
from fontTools.ttLib import TTFont, getTableClass
from fontTools.ttLib.scaleUpem import ScalerVisitor


class TrueTypeGlyph(Protocol):
    """Observable TrueType glyph data returned by ``TTGlyphPen``."""

    numberOfContours: int
    coordinates: object
    flags: Iterable[int]


_LATIN_REPLACEMENT_RANGES = (
    (0x0020, 0x024F),
    (0x0300, 0x036F),
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
    0x2044,
    0x2212,
)
_LATIN_REPLACEMENT_CODEPOINTS = frozenset(
    {
        codepoint
        for start, end in _LATIN_REPLACEMENT_RANGES
        for codepoint in range(start, end + 1)
    }
    | set(_LATIN_TYPOGRAPHIC_CODEPOINTS)
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
    baseline_shift: float = 0,
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
    if scale_factor != 1 or baseline_shift:
        outline = _font_geometry.transform_path(
            outline,
            Transform(
                scale_factor,
                0,
                0,
                scale_factor,
                0,
                baseline_shift,
            ),
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
    transform_for_codepoint: Callable[[int], LatinTransform] | None = None,
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

    replaced: list[int] = []
    replaced_names: set[str] = set()
    for codepoint in sorted(_LATIN_REPLACEMENT_CODEPOINTS):
        if codepoint not in target_cmap or codepoint not in latin_cmap:
            continue
        target_name = target_cmap[codepoint]
        if target_name in replaced_names:
            continue
        source_name = latin_cmap[codepoint]
        transform = (
            transform_for_codepoint(codepoint)
            if transform_for_codepoint is not None
            else LatinTransform(scale_factor, horizontal_weight_adjustment)
        )
        replace_glyph_from_source(
            font,
            target_name,
            latin_font,
            source_name,
            transform.horizontal_stroke_adjustment,
            transform.scale_factor,
            transform.baseline_shift,
        )
        replaced.append(codepoint)
        replaced_names.add(target_name)
    return tuple(replaced)



@dataclass(frozen=True)
class LatinImportResult:
    """Glyphs replaced or appended while importing one Latin source."""

    codepoints: tuple[int, ...]
    glyph_names: tuple[str, ...]


def latin_glyph_class(codepoint: int) -> LatinGlyphClass:
    """Return the reusable transform class for a Unicode codepoint."""

    category = unicodedata.category(chr(codepoint))
    if category.startswith("L"):
        return "letters"
    if category.startswith("N"):
        return "figures"
    if category.startswith("M"):
        return "marks"
    if category.startswith("P"):
        return "punctuation"
    if category.startswith("S"):
        return "symbols"
    return "spacing"


class _AnchorShiftVisitor(TTVisitor):
    def __init__(self, amount: float):
        self.amount = amount


@_AnchorShiftVisitor.register_attr(otTables.Anchor, "YCoordinate")
def visit(
    visitor: _AnchorShiftVisitor,
    anchor: otTables.Anchor,
    attribute: str,
    value: int,
) -> None:
    setattr(anchor, attribute, round(value + visitor.amount))


def _copy_font(font: TTFont) -> TTFont:
    data = BytesIO()
    font.save(data)
    data.seek(0)
    return TTFont(data)


def _subset_latin_font(
    font: TTFont,
    codepoints: tuple[int, ...],
    layout_features: tuple[str, ...],
    common_layout_features: tuple[str, ...],
) -> TTFont:
    subset_font = _copy_font(font)
    options = subset.Options()
    options.layout_features = list(layout_features)
    options.layout_scripts = ["*"]
    options.name_IDs = []
    options.name_legacy = False
    options.name_languages = []
    options.glyph_names = True
    options.bidi_closure = False
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(subset_font)
    common_tags = set(common_layout_features)
    for tag in ("GSUB", "GPOS"):
        if tag not in subset_font:
            continue
        table = subset_font[tag].table
        if getattr(table, "FeatureVariations", None) is not None:
            raise ValueError(
                f"Latin {tag} FeatureVariations must be instantiated before import"
            )
        latin_scripts = [
            record
            for record in table.ScriptList.ScriptRecord
            if record.ScriptTag == "latn"
        ]
        if not latin_scripts:
            raise ValueError(f"The Latin source {tag} has no latn script")
        common_scripts = [
            record
            for record in table.ScriptList.ScriptRecord
            if record.ScriptTag == "DFLT"
        ]
        for script_record in common_scripts:
            script = script_record.Script
            lang_systems = [
                script.DefaultLangSys,
                *(record.LangSys for record in script.LangSysRecord),
            ]
            for lang_system in lang_systems:
                if lang_system is None:
                    continue
                lang_system.FeatureIndex = [
                    index
                    for index in lang_system.FeatureIndex
                    if table.FeatureList.FeatureRecord[index].FeatureTag
                    in common_tags
                ]
                lang_system.FeatureCount = len(lang_system.FeatureIndex)
        common_scripts = [
            record
            for record in common_scripts
            if any(
                lang_system is not None and lang_system.FeatureIndex
                for lang_system in (
                    record.Script.DefaultLangSys,
                    *(
                        language.LangSys
                        for language in record.Script.LangSysRecord
                    ),
                )
            )
        ]
        kept_scripts = [*common_scripts, *latin_scripts]
        table.ScriptList.ScriptRecord = kept_scripts
        table.ScriptList.ScriptCount = len(kept_scripts)
        for script_record in kept_scripts:
            script = script_record.Script
            lang_systems = [
                script.DefaultLangSys,
                *(record.LangSys for record in script.LangSysRecord),
            ]
            if any(
                lang_system is not None
                and lang_system.ReqFeatureIndex != 0xFFFF
                for lang_system in lang_systems
            ):
                raise ValueError(
                    f"Latin {tag} required features are not supported"
                )
    return subset_font


def _source_glyph_classes(
    font: TTFont,
) -> dict[str, LatinGlyphClass]:
    classes: dict[str, set[LatinGlyphClass]] = {}
    for codepoint, glyph_name in font.getBestCmap().items():
        classes.setdefault(glyph_name, set()).add(latin_glyph_class(codepoint))

    if "GSUB" in font:
        changed = True
        while changed:
            changed = False
            for lookup in font["GSUB"].table.LookupList.Lookup:
                for subtable in lookup.SubTable:
                    while hasattr(subtable, "ExtSubTable"):
                        subtable = subtable.ExtSubTable
                    mappings: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
                    mapping = getattr(subtable, "mapping", None)
                    if mapping is not None:
                        for source_name, outputs in mapping.items():
                            if isinstance(outputs, str):
                                outputs = (outputs,)
                            mappings.append(((source_name,), tuple(outputs)))
                    alternates = getattr(subtable, "alternates", None)
                    if alternates is not None:
                        mappings.extend(
                            ((source_name,), tuple(outputs))
                            for source_name, outputs in alternates.items()
                        )
                    ligatures = getattr(subtable, "ligatures", None)
                    if ligatures is not None:
                        for first, records in ligatures.items():
                            for ligature in records:
                                mappings.append(
                                    (
                                        (first, *ligature.Component),
                                        (ligature.LigGlyph,),
                                    )
                                )
                    for inputs, outputs in mappings:
                        input_classes = set().union(
                            *(classes.get(name, set()) for name in inputs)
                        )
                        if len(input_classes) != 1:
                            continue
                        glyph_class = next(iter(input_classes))
                        for output in outputs:
                            output_classes = classes.setdefault(output, set())
                            if glyph_class not in output_classes:
                                output_classes.add(glyph_class)
                                changed = True

    return {
        glyph_name: next(iter(glyph_classes))
        for glyph_name, glyph_classes in classes.items()
        if len(glyph_classes) == 1
    }


def _append_glyph_from_source(
    font: TTFont,
    target_name: str,
    source_font: TTFont,
    source_name: str,
    donor_name: str,
    transform: LatinTransform,
) -> None:
    if transform.scale_factor <= 0:
        raise ValueError("Latin scale factor must be positive")
    outline = _font_geometry.glyph_path(source_font, source_name)
    if transform.scale_factor != 1 or transform.baseline_shift:
        outline = _font_geometry.transform_path(
            outline,
            Transform(
                transform.scale_factor,
                0,
                0,
                transform.scale_factor,
                0,
                transform.baseline_shift,
            ),
        )
    outline = _font_geometry.adjust_outline_horizontal_weight(
        outline,
        transform.horizontal_stroke_adjustment,
    )
    try:
        _, _, _, donor_y_max = _font_geometry.bounds(font, donor_name)
    except ValueError:
        donor_y_max = 0
    vertical_origin = (
        font["vmtx"].metrics[donor_name][1] + donor_y_max
        if "vmtx" in font
        else 0
    )
    source_advance = source_font["hmtx"].metrics[source_name][0]
    append_glyphs(
        font,
        [outline],
        [target_name],
        donor_name,
        round(vertical_origin),
        add_stem_hints=False,
        advance_override=round(source_advance * transform.scale_factor),
    )


def _layout_glyph_mapping(
    font: TTFont,
    source_font: TTFont,
    replaced_codepoints: tuple[int, ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    target_cmap = font.getBestCmap()
    source_names_by_codepoint = source_font.getBestCmap()
    source_codepoints_by_name: dict[str, set[int]] = {}
    for codepoint, glyph_name in source_names_by_codepoint.items():
        if codepoint in replaced_codepoints:
            source_codepoints_by_name.setdefault(glyph_name, set()).add(codepoint)

    source_order = source_font.getGlyphOrder()
    mapping = {source_order[0]: font.getGlyphOrder()[0]}
    used_names = set(mapping.values())
    extras: list[str] = []
    for source_name in source_order[1:]:
        target_names = {
            target_cmap[codepoint]
            for codepoint in source_codepoints_by_name.get(source_name, ())
            if codepoint in target_cmap
        }
        if len(target_names) == 1:
            target_name = next(iter(target_names))
            if target_name not in used_names:
                mapping[source_name] = target_name
                used_names.add(target_name)
                continue
        extras.append(source_name)

    allocated = allocate_cid_names(font, len(extras))
    mapping.update(zip(extras, allocated, strict=True))
    return mapping, tuple(extras)


def _remap_source_mark_attachment_classes(
    font: TTFont,
    source_font: TTFont,
) -> None:
    if "GDEF" not in source_font:
        return
    target_definition = (
        font["GDEF"].table.MarkAttachClassDef
        if "GDEF" in font
        else None
    )
    source_definition = source_font["GDEF"].table.MarkAttachClassDef
    if source_definition is None:
        return
    target_classes = (
        target_definition.classDefs if target_definition is not None else {}
    )
    source_classes = source_definition.classDefs
    first_available = max(target_classes.values(), default=0) + 1
    class_mapping = {
        old: first_available + index
        for index, old in enumerate(sorted(set(source_classes.values())))
    }
    if class_mapping and max(class_mapping.values()) > 255:
        raise ValueError("Latin mark attachment classes exceed the OpenType limit")
    source_definition.classDefs = {
        glyph_name: class_mapping[class_id]
        for glyph_name, class_id in source_classes.items()
    }
    conflicts = {
        glyph_name
        for glyph_name, class_id in source_definition.classDefs.items()
        if glyph_name in target_classes and target_classes[glyph_name] != class_id
    }
    if conflicts:
        raise ValueError(
            "Latin mark attachment classes conflict for "
            + ", ".join(sorted(conflicts))
        )
    for tag in ("GSUB", "GPOS"):
        if tag not in source_font:
            continue
        for lookup in source_font[tag].table.LookupList.Lookup:
            old_class = lookup.LookupFlag >> 8
            if old_class:
                lookup.LookupFlag = (
                    lookup.LookupFlag & 0x00FF
                ) | (class_mapping[old_class] << 8)


def _validate_glyph_class_conflicts(
    font: TTFont,
    source_font: TTFont,
) -> None:
    if "GDEF" not in font or "GDEF" not in source_font:
        return
    target_definition = font["GDEF"].table.GlyphClassDef
    source_definition = source_font["GDEF"].table.GlyphClassDef
    if target_definition is None or source_definition is None:
        return
    conflicts = {
        glyph_name
        for glyph_name, class_id in source_definition.classDefs.items()
        if glyph_name in target_definition.classDefs
        and target_definition.classDefs[glyph_name] != class_id
    }
    if conflicts:
        raise ValueError(
            "Latin glyph classes conflict for " + ", ".join(sorted(conflicts))
        )


def _script_lang_systems(script: object) -> dict[str | None, object]:
    systems: dict[str | None, object] = {}
    if script.DefaultLangSys is not None:
        systems[None] = script.DefaultLangSys
    systems.update(
        (record.LangSysTag, record.LangSys)
        for record in script.LangSysRecord
    )
    return systems


def _replace_target_latin_feature_assignments(
    font: TTFont,
    source_font: TTFont,
) -> None:
    for tag in ("GSUB", "GPOS"):
        if tag not in source_font or tag not in font:
            continue
        target_records = font[tag].table.ScriptList.ScriptRecord
        source_records = source_font[tag].table.ScriptList.ScriptRecord
        target_script = next(
            (record.Script for record in target_records if record.ScriptTag == "latn"),
            None,
        )
        source_script = next(
            (record.Script for record in source_records if record.ScriptTag == "latn"),
            None,
        )
        if target_script is None or source_script is None:
            continue
        target_systems = _script_lang_systems(target_script)
        source_systems = _script_lang_systems(source_script)
        source_default = source_systems.get(None)
        for language, target_system in target_systems.items():
            source_system = source_systems.get(language, source_default)
            if source_system is None:
                continue
            source_by_tag = {
                feature.FeatureTag: feature
                for feature in source_system.FeatureIndex
            }
            target_system.FeatureIndex = [
                feature
                for feature in target_system.FeatureIndex
                if feature.FeatureTag not in source_by_tag
            ]
            if language not in source_systems:
                target_system.FeatureIndex.extend(source_by_tag.values())


def _sort_layout_records(font: TTFont) -> None:
    for tag in ("GSUB", "GPOS"):
        if tag not in font:
            continue
        table = font[tag].table
        feature_records = table.FeatureList.FeatureRecord
        feature_order = sorted(
            range(len(feature_records)),
            key=lambda index: feature_records[index].FeatureTag,
        )
        feature_mapping = {
            old_index: new_index
            for new_index, old_index in enumerate(feature_order)
        }
        table.FeatureList.FeatureRecord = [
            feature_records[index] for index in feature_order
        ]
        table.FeatureList.FeatureCount = len(feature_records)
        table.ScriptList.ScriptRecord.sort(
            key=lambda record: record.ScriptTag
        )
        for script_record in table.ScriptList.ScriptRecord:
            script = script_record.Script
            script.LangSysRecord.sort(key=lambda record: record.LangSysTag)
            for lang_system in (
                script.DefaultLangSys,
                *(record.LangSys for record in script.LangSysRecord),
            ):
                if lang_system is None:
                    continue
                lang_system.FeatureIndex = sorted(
                    feature_mapping[index]
                    for index in lang_system.FeatureIndex
                )
                lang_system.FeatureCount = len(lang_system.FeatureIndex)
                if lang_system.ReqFeatureIndex != 0xFFFF:
                    lang_system.ReqFeatureIndex = feature_mapping[
                        lang_system.ReqFeatureIndex
                    ]


def _merge_latin_layout(
    font: TTFont,
    source_font: TTFont,
    mapping: dict[str, str],
    profile: LatinBuildProfile,
) -> None:
    data = BytesIO()
    source_font.save(data)
    data.seek(0)
    layout_source = TTFont(data, lazy=True)
    old_order = layout_source.getGlyphOrder()
    layout_source.setGlyphOrder([mapping[name] for name in old_order])
    for tag in ("GDEF", "GSUB", "GPOS"):
        if tag in layout_source:
            layout_source[tag].table.ensureDecompiled(recurse=True)
            layout_source[tag].compile(layout_source)
    for tag in list(layout_source.keys()):
        if tag not in {"GlyphOrder", "GDEF", "GSUB", "GPOS"}:
            del layout_source[tag]

    scaler = ScalerVisitor(profile.scale_factor)
    for tag in ("GDEF", "GPOS"):
        if tag in layout_source:
            scaler.visit(layout_source[tag].table)
    if profile.baseline_shift and "GPOS" in layout_source:
        _AnchorShiftVisitor(profile.baseline_shift).visit(
            layout_source["GPOS"].table
        )
    _remap_source_mark_attachment_classes(font, layout_source)
    _validate_glyph_class_conflicts(font, layout_source)

    merger = Merger()
    merger.duplicateGlyphsPerFont = [{}, {}]
    merger.fonts = [font, layout_source]
    layoutPreMerge(font)
    layoutPreMerge(layout_source)
    _replace_target_latin_feature_assignments(font, layout_source)
    for tag in ("GDEF", "GSUB", "GPOS"):
        tables = [font.get(tag, NotImplemented), layout_source.get(tag, NotImplemented)]
        if all(candidate is NotImplemented for candidate in tables):
            continue
        table = getTableClass(tag)(tag).merge(merger, tables)
        if table is not NotImplemented and table is not False:
            font[tag] = table
    layoutPostMerge(font)
    _sort_layout_records(font)
    font.reorderGlyphs(font.getGlyphOrder())


def import_latin_font(
    font: TTFont,
    latin_font: TTFont,
    profile: LatinBuildProfile,
) -> LatinImportResult:
    """Import transformed Latin outlines and their source OpenType layout."""

    target_codepoints = set(font.getBestCmap())
    latin_codepoints = set(latin_font.getBestCmap())
    replaced_codepoints = replace_latin_glyphs(
        font,
        latin_font,
        transform_for_codepoint=lambda codepoint: profile.transform_for(
            latin_glyph_class(codepoint)
        ),
    )
    imported_codepoints = tuple(
        sorted(_LATIN_REPLACEMENT_CODEPOINTS & latin_codepoints)
    )
    added_codepoints = tuple(
        codepoint
        for codepoint in imported_codepoints
        if codepoint not in target_codepoints
    )
    subset_font = _subset_latin_font(
        latin_font,
        imported_codepoints,
        profile.layout_features,
        profile.common_layout_features,
    )
    glyph_classes = _source_glyph_classes(subset_font)
    mapping, extras = _layout_glyph_mapping(
        font,
        subset_font,
        imported_codepoints,
    )
    donor_name = font.getBestCmap()[0x0041]
    default_transform = LatinTransform(
        profile.scale_factor,
        profile.horizontal_stroke_adjustment,
        profile.baseline_shift,
    )
    for source_name in extras:
        glyph_class = glyph_classes.get(source_name)
        transform = (
            profile.transform_for(glyph_class)
            if glyph_class is not None
            else default_transform
        )
        _append_glyph_from_source(
            font,
            mapping[source_name],
            subset_font,
            source_name,
            donor_name,
            transform,
        )
    subset_cmap = subset_font.getBestCmap()
    for codepoint in added_codepoints:
        add_unicode_mapping(font, codepoint, mapping[subset_cmap[codepoint]])
    _merge_latin_layout(font, subset_font, mapping, profile)
    imported_names = tuple(
        dict.fromkeys(
            mapping[source_name]
            for source_name in subset_font.getGlyphOrder()[1:]
        )
    )
    return LatinImportResult(imported_codepoints, imported_names)
