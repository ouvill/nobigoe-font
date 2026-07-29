"""Generate and merge OpenType feature rules."""

from __future__ import annotations

import copy
from collections.abc import Iterator

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from .punctuation import punctuation_ligature_rules


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


def alternating_wave_rules(prefix: str, base: str, names: list[str]) -> str:
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
        alternating_wave_rules(f"{wave_prefix}_h", wave_base, horizontal_wave_names)
    )
    calt_rules.append(
        alternating_wave_rules(f"{wave_prefix}_v", wave_vertical, vertical_wave_names)
    )
    wave_vertical_maps = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in zip(
            horizontal_wave_names, vertical_wave_names, strict=True
        )
    )
    vert_rules.append(
        alternating_wave_rules(f"{wave_prefix}_vert", wave_base, vertical_wave_names)
        + wave_vertical_maps
    )
    vrt2_rules.append(
        alternating_wave_rules(f"{wave_prefix}_vrt2", wave_base, vertical_wave_names)
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
        f"  sub {normal} by {ruby};\n" for normal, ruby in ruby_substitutions
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


def all_langsys(script_list: object) -> Iterator[object]:
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
            record
            for record in patch.FeatureList.FeatureRecord
            if record.FeatureTag == tag
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
            if (
                langsys.ReqFeatureIndex != 0xFFFF
                and langsys.ReqFeatureIndex >= feature_index
            ):
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
