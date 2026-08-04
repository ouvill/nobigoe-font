"""Generate and merge OpenType feature rules."""

from __future__ import annotations

import copy
from collections.abc import Iterator, Sequence

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


def phased_wave_rules(prefix: str, base: str, names: list[str]) -> str:
    (
        start,
        middle_0,
        middle_1,
        middle_2,
        middle_3,
        end_0,
        end_1,
        end_2,
        end_3,
    ) = names
    glyphs = " ".join((base, *names))
    return f"""
  lookup {prefix}_start {{
    ignore sub {base} [{glyphs}]';
    sub {base}' [{glyphs}] by {start};
  }} {prefix}_start;
  lookup {prefix}_end {{
    sub [{glyphs}] {base}' by {end_0};
  }} {prefix}_end;
  lookup {prefix}_cycle {{
    sub {start} {start}' by {middle_1};
    sub {middle_1} {start}' by {middle_2};
    sub {middle_2} {start}' by {middle_3};
    sub {middle_3} {start}' by {middle_0};
    sub {middle_0} {start}' by {middle_1};
  }} {prefix}_cycle;
  lookup {prefix}_end_phase {{
    sub [{start} {middle_0}] {end_0}' by {end_1};
    sub {middle_1} {end_0}' by {end_2};
    sub {middle_2} {end_0}' by {end_3};
  }} {prefix}_end_phase;
"""


def repeated_glyph_rules(prefix: str, base: str, replacement: str) -> str:
    glyphs = f"{base} {replacement}"
    return f"""
  lookup {prefix}_forward {{
    sub {base}' [{glyphs}] by {replacement};
  }} {prefix}_forward;
  lookup {prefix}_backward {{
    sub [{glyphs}] {base}' by {replacement};
  }} {prefix}_backward;
"""


def mixed_wave_scan_rules(
    prefix: str,
    manga_base: str,
    manga_names: Sequence[str],
    wave_base: str,
    wave_names: Sequence[str],
    manga_to_wave_names: Sequence[str],
    wave_to_manga_names: Sequence[str],
) -> str:
    manga_start, manga_middle, manga_end, manga_inverted_middle, manga_inverted_end = (
        manga_names
    )
    wave_start, wave_middle_a, wave_middle_b, wave_end_a, wave_end_b = wave_names
    (
        manga_to_wave_middle,
        manga_to_wave_end,
        manga_to_wave_inverted_middle,
        manga_to_wave_inverted_end,
    ) = manga_to_wave_names
    (
        wave_to_manga_rising_middle,
        wave_to_manga_rising_end,
        wave_to_manga_falling_middle,
        wave_to_manga_falling_end,
    ) = wave_to_manga_names
    manga_rising = f"[{manga_start} {manga_middle} {wave_to_manga_rising_middle}]"
    manga_falling = f"[{manga_inverted_middle} {wave_to_manga_falling_middle}]"
    wave_peak = f"[{wave_start} {wave_middle_a} {manga_to_wave_inverted_middle}]"
    wave_trough = f"[{wave_middle_b} {manga_to_wave_middle}]"
    middle_names = (
        manga_middle,
        manga_inverted_middle,
        wave_to_manga_rising_middle,
        wave_to_manga_falling_middle,
        wave_middle_a,
        wave_middle_b,
        manga_to_wave_middle,
        manga_to_wave_inverted_middle,
    )
    end_names = (
        manga_end,
        manga_inverted_end,
        wave_to_manga_rising_end,
        wave_to_manga_falling_end,
        wave_end_a,
        wave_end_b,
        manga_to_wave_end,
        manga_to_wave_inverted_end,
    )
    terminal_rules = "".join(
        f"    sub {middle} by {end};\n"
        for middle, end in zip(middle_names, end_names, strict=True)
    )
    connected = " ".join((manga_start, wave_start, *end_names))
    repair_rules = "".join(
        f"    sub {end}' [{connected}] by {middle};\n"
        for middle, end in zip(middle_names, end_names, strict=True)
    )
    return f"""
  lookup {prefix}_scan {{
    sub {manga_rising} {manga_base}' by {manga_middle};
    sub {manga_rising} {wave_base}' by {manga_to_wave_middle};
    sub {manga_falling} {manga_base}' by {manga_inverted_middle};
    sub {manga_falling} {wave_base}' by {manga_to_wave_inverted_middle};
    sub {wave_peak} {wave_base}' by {wave_middle_b};
    sub {wave_peak} {manga_base}' by {wave_to_manga_rising_middle};
    sub {wave_trough} {wave_base}' by {wave_middle_a};
    sub {wave_trough} {manga_base}' by {wave_to_manga_falling_middle};
    sub {manga_base}' [{manga_base} {wave_base}] by {manga_start};
    sub {wave_base}' [{manga_base} {wave_base}] by {wave_start};
  }} {prefix}_scan;
  lookup {prefix}_terminal {{
{terminal_rules}  }} {prefix}_terminal;
  lookup {prefix}_repair {{
{repair_rules}  }} {prefix}_repair;
"""


def _symbol_feature_rules(
    extensions: list[tuple[str, str, str, list[str]]],
    wave: tuple[str, str, str, list[str]],
    relaxed_wave: tuple[str, str, str, list[str]],
    one_cycle_wave: tuple[str, str, str, list[str]],
    manga_wave: tuple[str, str, list[str]],
    manga_to_wave_transition: tuple[str, list[str]],
    wave_to_manga_transition: tuple[str, list[str]],
) -> tuple[str, str, str, str, str]:
    calt_rules: list[str] = []
    vert_rules: list[str] = []
    vrt2_rules: list[str] = []
    for prefix, base, vertical, names in extensions:
        h_start, h_middle, h_end, v_start, v_middle, v_end = names
        calt_rules.append(
            contextual_extension_rules(f"{prefix}_h", base, h_start, h_middle, h_end)
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
            contextual_extension_rules(f"{prefix}_vert", base, v_start, v_middle, v_end)
            + vertical_maps
        )
        vrt2_rules.append(
            contextual_extension_rules(f"{prefix}_vrt2", base, v_start, v_middle, v_end)
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

    (
        relaxed_wave_prefix,
        relaxed_wave_source,
        relaxed_wave_vertical_source,
        relaxed_wave_names,
    ) = relaxed_wave
    relaxed_horizontal_names = relaxed_wave_names[:10]
    relaxed_vertical_names = relaxed_wave_names[10:]
    relaxed_horizontal_base = relaxed_horizontal_names[0]
    relaxed_vertical_base = relaxed_vertical_names[0]
    relaxed_horizontal_parts = relaxed_horizontal_names[1:]
    relaxed_vertical_parts = relaxed_vertical_names[1:]
    calt_rules.append(
        phased_wave_rules(
            f"{relaxed_wave_prefix}_h",
            relaxed_horizontal_base,
            relaxed_horizontal_parts,
        )
    )
    calt_rules.append(
        phased_wave_rules(
            f"{relaxed_wave_prefix}_v",
            relaxed_vertical_base,
            relaxed_vertical_parts,
        )
    )
    relaxed_vertical_maps = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in zip(
            relaxed_horizontal_names, relaxed_vertical_names, strict=True
        )
    )
    vert_rules.append(
        phased_wave_rules(
            f"{relaxed_wave_prefix}_vert",
            relaxed_horizontal_base,
            relaxed_vertical_parts,
        )
        + relaxed_vertical_maps
    )
    vrt2_rules.append(
        phased_wave_rules(
            f"{relaxed_wave_prefix}_vrt2",
            relaxed_horizontal_base,
            relaxed_vertical_parts,
        )
        + relaxed_vertical_maps
    )
    ss04_rules = repeated_glyph_rules(
        f"{relaxed_wave_prefix}_h_style",
        relaxed_wave_source,
        relaxed_horizontal_base,
    ) + repeated_glyph_rules(
        f"{relaxed_wave_prefix}_v_style",
        relaxed_wave_vertical_source,
        relaxed_vertical_base,
    )

    (
        one_cycle_prefix,
        one_cycle_source,
        one_cycle_vertical_source,
        one_cycle_names,
    ) = one_cycle_wave
    one_cycle_horizontal_names = one_cycle_names[:4]
    one_cycle_vertical_names = one_cycle_names[4:]
    (
        one_cycle_horizontal_base,
        one_cycle_horizontal_start,
        one_cycle_horizontal_middle,
        one_cycle_horizontal_end,
    ) = one_cycle_horizontal_names
    (
        one_cycle_vertical_base,
        one_cycle_vertical_start,
        one_cycle_vertical_middle,
        one_cycle_vertical_end,
    ) = one_cycle_vertical_names
    calt_rules.append(
        contextual_extension_rules(
            f"{one_cycle_prefix}_h",
            one_cycle_horizontal_base,
            one_cycle_horizontal_start,
            one_cycle_horizontal_middle,
            one_cycle_horizontal_end,
        )
    )
    calt_rules.append(
        contextual_extension_rules(
            f"{one_cycle_prefix}_v",
            one_cycle_vertical_base,
            one_cycle_vertical_start,
            one_cycle_vertical_middle,
            one_cycle_vertical_end,
        )
    )
    one_cycle_vertical_maps = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in zip(
            one_cycle_horizontal_names,
            one_cycle_vertical_names,
            strict=True,
        )
    )
    vert_rules.append(
        contextual_extension_rules(
            f"{one_cycle_prefix}_vert",
            one_cycle_horizontal_base,
            one_cycle_vertical_start,
            one_cycle_vertical_middle,
            one_cycle_vertical_end,
        )
        + one_cycle_vertical_maps
    )
    vrt2_rules.append(
        contextual_extension_rules(
            f"{one_cycle_prefix}_vrt2",
            one_cycle_horizontal_base,
            one_cycle_vertical_start,
            one_cycle_vertical_middle,
            one_cycle_vertical_end,
        )
        + one_cycle_vertical_maps
    )
    ss05_rules = repeated_glyph_rules(
        f"{one_cycle_prefix}_h_style",
        one_cycle_source,
        one_cycle_horizontal_base,
    ) + repeated_glyph_rules(
        f"{one_cycle_prefix}_v_style",
        one_cycle_vertical_source,
        one_cycle_vertical_base,
    )

    manga_wave_prefix, manga_wave_base, manga_wave_names = manga_wave
    (
        manga_wave_start,
        manga_wave_middle,
        manga_wave_end,
        manga_wave_inverted_middle,
        manga_wave_inverted_end,
        manga_wave_vertical_isolated,
        manga_wave_vertical_start,
        manga_wave_vertical_middle,
        manga_wave_vertical_end,
        manga_wave_vertical_inverted_middle,
        manga_wave_vertical_inverted_end,
    ) = manga_wave_names
    transition_prefix, transition_names = manga_to_wave_transition
    horizontal_transition_names = transition_names[:4]
    vertical_transition_names = transition_names[4:]
    reverse_transition_prefix, reverse_transition_names = wave_to_manga_transition
    horizontal_reverse_transition_names = reverse_transition_names[:4]
    vertical_reverse_transition_names = reverse_transition_names[4:]
    calt_rules.insert(
        0,
        mixed_wave_scan_rules(
            f"{transition_prefix}_h",
            manga_wave_base,
            (
                manga_wave_start,
                manga_wave_middle,
                manga_wave_end,
                manga_wave_inverted_middle,
                manga_wave_inverted_end,
            ),
            wave_base,
            horizontal_wave_names,
            horizontal_transition_names,
            horizontal_reverse_transition_names,
        ),
    )
    transition_vertical_maps = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in zip(
            (*horizontal_transition_names, *horizontal_reverse_transition_names),
            (*vertical_transition_names, *vertical_reverse_transition_names),
            strict=True,
        )
    )
    vertical_scan_arguments = (
        manga_wave_base,
        (
            manga_wave_vertical_start,
            manga_wave_vertical_middle,
            manga_wave_vertical_end,
            manga_wave_vertical_inverted_middle,
            manga_wave_vertical_inverted_end,
        ),
        wave_base,
        vertical_wave_names,
        vertical_transition_names,
        vertical_reverse_transition_names,
    )
    vert_rules.insert(
        0,
        mixed_wave_scan_rules(
            f"{reverse_transition_prefix}_vert", *vertical_scan_arguments
        )
        + transition_vertical_maps,
    )
    vrt2_rules.insert(
        0,
        mixed_wave_scan_rules(
            f"{reverse_transition_prefix}_vrt2", *vertical_scan_arguments
        )
        + transition_vertical_maps,
    )
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
        f"  sub {manga_wave_inverted_middle} by {manga_wave_vertical_inverted_middle};\n"
        f"  sub {manga_wave_inverted_end} by {manga_wave_vertical_inverted_end};\n"
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
    return (
        ss04_rules,
        ss05_rules,
        "".join(calt_rules),
        "".join(vert_rules),
        "".join(vrt2_rules),
    )


def symbol_feature_source(
    extensions: list[tuple[str, str, str, list[str]]],
    wave: tuple[str, str, str, list[str]],
    relaxed_wave: tuple[str, str, str, list[str]],
    manga_wave: tuple[str, str, list[str]],
    one_cycle_wave: tuple[str, str, str, list[str]],
    manga_to_wave_transition: tuple[str, list[str]],
    wave_to_manga_transition: tuple[str, list[str]],
) -> str:
    ss04, ss05, calt, vert, vrt2 = _symbol_feature_rules(
        extensions,
        wave,
        relaxed_wave,
        one_cycle_wave,
        manga_wave,
        manga_to_wave_transition,
        wave_to_manga_transition,
    )
    return (
        "languagesystem DFLT dflt;\n\n"
        f"feature ss04 {{\n{ss04}}} ss04;\n\n"
        f"feature ss05 {{\n{ss05}}} ss05;\n\n"
        f"feature calt {{\n{calt}}} calt;\n\n"
        f"feature vert {{\n{vert}}} vert;\n\n"
        f"feature vrt2 {{\n{vrt2}}} vrt2;\n"
    )


def punctuation_feature_source(
    punctuation_variants: Sequence[tuple[str, tuple[str, str, str, str]]],
) -> str:
    """Return GSUB rules for variable original punctuation and its alternates."""

    names = dict(punctuation_variants)
    ccmp_rules = punctuation_ligature_rules(
        names["!"][0],
        names["?"][0],
        [
            (sequence, variants[0])
            for sequence, variants in punctuation_variants
            if len(sequence) > 1
        ],
    )
    alternate_rules = "".join(
        f"  sub {variants[0]} from [{' '.join(variants[1:])}];\n"
        for _, variants in punctuation_variants
    )
    stylistic_rules = [
        "".join(
            f"  sub {variants[0]} by {variants[index]};\n"
            for _, variants in punctuation_variants
        )
        for index in range(1, 4)
    ]
    return (
        "languagesystem DFLT dflt;\n\n"
        f"feature ccmp {{\n{ccmp_rules}}} ccmp;\n\n"
        f"feature aalt {{\n{alternate_rules}}} aalt;\n\n"
        f"feature ss01 {{\n{stylistic_rules[0]}}} ss01;\n\n"
        f"feature ss02 {{\n{stylistic_rules[1]}}} ss02;\n\n"
        f"feature ss03 {{\n{stylistic_rules[2]}}} ss03;\n"
    )


def feature_source(
    extensions: list[tuple[str, str, str, list[str]]],
    wave: tuple[str, str, str, list[str]],
    relaxed_wave: tuple[str, str, str, list[str]],
    manga_wave: tuple[str, str, list[str]],
    one_cycle_wave: tuple[str, str, str, list[str]],
    manga_to_wave_transition: tuple[str, list[str]],
    wave_to_manga_transition: tuple[str, list[str]],
    punctuation_variants: list[tuple[str, tuple[str, str, str, str]]],
    kana_marks: list[tuple[str, str, str]],
    spacing_marks: Sequence[tuple[str, str, str]],
    kana_vertical_maps: list[tuple[str, str]],
    punctuation_marks: Sequence[tuple[str, str, str]] = (),
) -> str:
    (
        ss04_rules,
        ss05_rules,
        calt_rules,
        vert_rules,
        vrt2_rules,
    ) = _symbol_feature_rules(
        extensions,
        wave,
        relaxed_wave,
        one_cycle_wave,
        manga_wave,
        manga_to_wave_transition,
        wave_to_manga_transition,
    )

    kana_vertical_rules = "".join(
        f"  sub {horizontal} by {vertical};\n"
        for horizontal, vertical in kana_vertical_maps
    )
    vert_rules += kana_vertical_rules
    vrt2_rules += kana_vertical_rules

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
        for base, mark, output in (*kana_marks, *punctuation_marks)
    )
    liga_rules = "".join(
        f"  sub {base} {mark} by {output};\n" for base, mark, output in spacing_marks
    )
    alternate_rules = "".join(
        f"  sub {names[0]} from [{' '.join(names[1:])}];\n"
        for _, names in punctuation_variants
    )
    ss01_rules = "".join(
        f"  sub {names[0]} by {names[1]};\n" for _, names in punctuation_variants
    )

    return (
        "languagesystem DFLT dflt;\n\n"
        f"feature ccmp {{\n{ccmp_rules}}} ccmp;\n\n"
        f"feature liga {{\n{liga_rules}}} liga;\n\n"
        f"feature ss04 {{\n{ss04_rules}}} ss04;\n\n"
        f"feature ss05 {{\n{ss05_rules}}} ss05;\n\n"
        f"feature calt {{\n{calt_rules}}} calt;\n\n"
        f"feature aalt {{\n{alternate_rules}}} aalt;\n\n"
        f"feature ss01 {{\n{ss01_rules}}} ss01;\n\n"
        f"feature vert {{\n{vert_rules}}} vert;\n\n"
        f"feature vrt2 {{\n{vrt2_rules}}} vrt2;\n"
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

    for tag, lookup_indices in patch_by_tag.items():
        feature_records = old.FeatureList.FeatureRecord
        matching_records = [
            record for record in feature_records if record.FeatureTag == tag
        ]
        for record in matching_records:
            record.Feature.LookupListIndex = (
                lookup_indices + record.Feature.LookupListIndex
            )
            record.Feature.LookupCount = len(record.Feature.LookupListIndex)

        missing_langsys = []
        for langsys in all_langsys(old.ScriptList):
            referenced_indices = list(langsys.FeatureIndex)
            if langsys.ReqFeatureIndex != 0xFFFF:
                referenced_indices.append(langsys.ReqFeatureIndex)
            if not any(
                feature_records[index].FeatureTag == tag for index in referenced_indices
            ):
                missing_langsys.append(langsys)
        if not missing_langsys:
            continue

        patch_record = next(
            record
            for record in patch.FeatureList.FeatureRecord
            if record.FeatureTag == tag
        )
        feature_index = next(
            (
                index
                for index, record in enumerate(feature_records)
                if record.FeatureTag > tag
            ),
            len(feature_records),
        )
        missing_ids = {id(langsys) for langsys in missing_langsys}
        for langsys in all_langsys(old.ScriptList):
            shifted_indices = [
                index + 1 if index >= feature_index else index
                for index in langsys.FeatureIndex
            ]
            if id(langsys) in missing_ids:
                shifted_indices.append(feature_index)
            langsys.FeatureIndex = sorted(shifted_indices)
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
        feature_records.insert(feature_index, copy.deepcopy(patch_record))
        old.FeatureList.FeatureCount = len(feature_records)
