#!/usr/bin/env python3
"""Build a Noto Serif JP derivative with Adobe-Manga1-style extensible choon marks."""

from __future__ import annotations

import argparse
import copy
import math
import tempfile
import urllib.request
from pathlib import Path

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

SOURCE_URL = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/main/"
    "Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf"
)
DEFAULT_OUTPUT = Path("dist/NotoSerifJPChoon-Regular.otf")
FAMILY = "Noto Serif JP Choon"
FULL_NAME = f"{FAMILY} Regular"
POSTSCRIPT_NAME = "NotoSerifJPChoon-Regular"
VERSION = "Version 1.000"
NEW_GLYPH_COUNT = 6
OVERLAP = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add automatically joining ー glyphs to Noto Serif JP. "
            "Two or more consecutive ー characters join through the calt feature."
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
    raise ValueError("The source font has no vertical substitution for U+30FC")


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
    outline: pathops.Path, advance: int
) -> tuple[pathops.Path, pathops.Path, pathops.Path]:
    seam = advance * 0.4
    x_min, x_max = stroke_band(outline, "vertical", seam)
    clip_top = rectangle(-4096, seam, 4096, 4096)
    clip_bottom = rectangle(-4096, -4096, 4096, seam)
    top_cap = pathops.op(outline, clip_top, pathops.PathOp.INTERSECTION)
    bottom_cap = pathops.op(outline, clip_bottom, pathops.PathOp.INTERSECTION)

    start_bar = rectangle(x_min, -advance - OVERLAP, x_max, seam + OVERLAP)
    middle = rectangle(x_min, -OVERLAP, x_max, advance + OVERLAP)
    end_bar = rectangle(x_min, seam - OVERLAP, x_max, advance + OVERLAP)
    start = pathops.op(top_cap, start_bar, pathops.PathOp.UNION)
    end = pathops.op(end_bar, bottom_cap, pathops.PathOp.UNION)
    return start, middle, end


def append_cff_glyphs(
    font: TTFont,
    paths: list[pathops.Path],
    names: list[str],
    source_glyph: str,
    vertical_origin: int,
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

    for name, outline in zip(names, paths, strict=True):
        pen = T2CharStringPen(advance, None)
        outline.draw(pen)
        char_string = pen.getCharString(private=private, globalSubrs=cff.GlobalSubrs)
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


def feature_source(base: str, vertical: str, names: list[str]) -> str:
    h_start, h_middle, h_end, v_start, v_middle, v_end = names
    return f"""
languagesystem DFLT dflt;

feature calt {{
  lookup choon_start {{
    ignore sub {base} [{base} {h_middle} {h_end} {h_start}]';
    sub {base}' [{base} {h_start} {h_middle} {h_end}] by {h_start};
  }} choon_start;

  lookup choon_end {{
    sub [{base} {h_start} {h_middle} {h_end}] {base}' by {h_end};
  }} choon_end;

  sub [{h_start} {h_middle}] {h_start}' by {h_middle};

  lookup choon_vertical_start {{
    ignore sub {vertical} [{vertical} {v_middle} {v_end} {v_start}]';
    sub {vertical}' [{vertical} {v_start} {v_middle} {v_end}] by {v_start};
  }} choon_vertical_start;

  lookup choon_vertical_end {{
    sub [{vertical} {v_start} {v_middle} {v_end}] {vertical}' by {v_end};
  }} choon_vertical_end;

  sub [{v_start} {v_middle}] {v_start}' by {v_middle};
}} calt;

feature vert {{
  lookup choon_vert_start {{
    ignore sub {base} [{base} {v_middle} {v_end} {v_start}]';
    sub {base}' [{base} {v_start} {v_middle} {v_end}] by {v_start};
  }} choon_vert_start;
  lookup choon_vert_end {{
    sub [{base} {v_start} {v_middle} {v_end}] {base}' by {v_end};
  }} choon_vert_end;
  sub [{v_start} {v_middle}] {v_start}' by {v_middle};

  sub {h_start} by {v_start};
  sub {h_middle} by {v_middle};
  sub {h_end} by {v_end};
}} vert;

feature vrt2 {{
  lookup choon_vrt2_start {{
    ignore sub {base} [{base} {v_middle} {v_end} {v_start}]';
    sub {base}' [{base} {v_start} {v_middle} {v_end}] by {v_start};
  }} choon_vrt2_start;
  lookup choon_vrt2_end {{
    sub [{base} {v_start} {v_middle} {v_end}] {base}' by {v_end};
  }} choon_vrt2_end;
  sub [{v_start} {v_middle}] {v_start}' by {v_middle};

  sub {h_start} by {v_start};
  sub {h_middle} by {v_middle};
  sub {h_end} by {v_end};
}} vrt2;
"""


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
    set_name(font, 3, f"1.000;CHOON;{POSTSCRIPT_NAME}")
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
    if 0x30FC not in cmap:
        raise ValueError("The source font does not contain U+30FC KATAKANA-HIRAGANA PROLONGED SOUND MARK")

    base = cmap[0x30FC]
    vertical = find_vertical_glyph(font, base)
    advance = font["hmtx"].metrics[base][0]
    if advance != 1000:
        raise ValueError(f"Expected a 1000-unit full-width choon mark, got {advance}")

    horizontal_parts = make_horizontal_parts(glyph_path(font, base), advance)
    vertical_parts = make_vertical_parts(glyph_path(font, vertical), advance)
    names = allocate_cid_names(font, NEW_GLYPH_COUNT)

    _, _, _, vertical_y_max = bounds(font, vertical)
    vertical_origin = round(font["vmtx"].metrics[vertical][1] + vertical_y_max)
    append_cff_glyphs(
        font,
        list(horizontal_parts + vertical_parts),
        names,
        base,
        vertical_origin,
    )
    merge_features(font, feature_source(base, vertical, names))
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
