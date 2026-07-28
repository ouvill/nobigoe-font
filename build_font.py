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

from font_profiles import (
    FontIdentity,
    LIBERTINUS_ARCHIVE_SHA256,
    LIBERTINUS_ARCHIVE_URL,
    LIBERTINUS_COPYRIGHT,
    LIBERTINUS_STROKE_ADJUSTMENTS,
    KOBURI_ARCHIVE_SHA256,
    KOBURI_ARCHIVE_URL,
    KOBURI_TTF_MEMBER,
    KOBURI_TTF_SHA256,
    NOTO_WEIGHT_CLASSES,
    SHIPPORI_ARCHIVE_SHA256,
    SHIPPORI_ARCHIVE_URL,
    SHIPPORI_COPYRIGHT,
    VERSION,
    VERSION_NUMBER,
    default_output_path,
    font_identity,
    libertinus_serif_source,
    shippori_source,
    noto_sans_source,
    noto_serif_source,
)

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem


WAVE_GLYPH_COUNT = 10
MANGA_WAVE_GLYPH_COUNT = 7
WAVE_TERMINAL_EXTENSION_HALF_WAVES = 0.15
NEW_GLYPH_COUNT = 6
OVERLAP = 0
MARK_COLLISION_AREA_EPSILON = 0.01
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
PUNCTUATION_VARIANT_SEQUENCES = (
    "!",
    "?",
    *MANGA_PUNCTUATION_SEQUENCES,
)
PUNCTUATION_ALTERNATE_COUNT = 3 * len(PUNCTUATION_VARIANT_SEQUENCES)
LATIN_REPLACEMENT_RANGES = (
    (0x0020, 0x024F),
    (0x1E00, 0x1EFF),
)
LATIN_TYPOGRAPHIC_CODEPOINTS = (
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
PUNCTUATION_SLANT_ANGLE = 12
MANGA_RUBY_HANDAKUTEN_BASES = (
    0x31F7,
    0x304B,
    0x304D,
    0x304F,
    0x3051,
    0x3053,
    0x30AB,
    0x30AD,
    0x30AF,
    0x30B1,
    0x30B3,
    0x30BB,
    0x30C4,
    0x30C8,
)
MANGA_RUBY_HANDAKUTEN_PAIRS = tuple(
    (base, 0x309A) for base in MANGA_RUBY_HANDAKUTEN_BASES
)
RUBY_SCALE = 0.5
RUBY_GLYPH_COUNT = len(MANGA_RUBY_HANDAKUTEN_PAIRS) + 1

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
KOBURI_PUA_START = 0xE082
KOBURI_PUA_MARK_PAIRS = tuple(
    [
        (int(value, 16), 0x3099)
        for value in """
3042 3044 3048 304A 3093 30A2 30A4 30A8
30AA 30F3
""".split()
    ]
    + [
        (int(value, 16), 0x309A)
        for value in """
304B 304D 304F 3051 3053 30AB 30AD 30AF
30B1 30B3 30BB 30C4 30C8 31F7
""".split()
    ]
    + [
        (int(value, 16), 0x3099)
        for value in """
306A 306B 306C 306D 306E 307E 307F 3080
3081 3082 3084 3086 3088 3089 308A 308B
308C 308D 308F 3090 3091 3092 3041 3043
3045 3047 3049 3095 3096 3063 3083 3085
3087 308E 30CA 30CB 30CC 30CD 30CE 30DE
30DF 30E0 30E1 30E2 30E4 30E6 30E8 30E9
30EA 30EB 30EC 30ED 30A1 30A3 30A5 30A7
30A9 30F5 30F6 30C3 30E3 30E5 30E7 30EE
""".split()
    ]
)
KOBURI_HEART_MARK_PAIRS = ((0x2661, 0x3099), (0x2665, 0x3099))
KOBURI_HEART_BASE_PUA = (0xE064, 0xE065)
KOBURI_HEART_OUTPUT_PUA = (0xE0DC, 0xE0DD)
HEART_DAKUTEN_MARK_TRANSFORMS = (
    Transform(0.96, 0, 0, 0.96, 971, 61),
    Transform(0.96, 0, 0, 0.96, 1002, 32),
)
HEART_DAKUTEN_CLEARANCE_RATIO = 1 / 3
HEART_DAKUTEN_CLEARANCE_STEPS = 16
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
KOBURI_MARK_POSITION_FILENAME = "koburi.json"
KOBURI_NATIVE_MARK_PAIRS = frozenset(KOBURI_PUA_MARK_PAIRS)
KOBURI_GENERATED_MARK_PAIRS = frozenset(MANGA_MARK_PAIRS) - (
    KOBURI_NATIVE_MARK_PAIRS
)
KOBURI_MARK_POSITION_SOURCE = {
    "file": Path(KOBURI_TTF_MEMBER).name,
    "sha256": KOBURI_TTF_SHA256,
    "source_upem": 1024,
    "working_upem": 1000,
    "native_ccmp_pairs": len(KOBURI_NATIVE_MARK_PAIRS),
    "generated_pairs": len(KOBURI_GENERATED_MARK_PAIRS),
    "gpos_features": ["halt", "palt", "vhal", "vkrn", "vpal"],
    "gpos_mark_to_base_lookups": 0,
}
KOBURI_MEASUREMENT_GROUPS = {
    "dakuten_normal",
    "dakuten_small",
    "handakuten_normal",
    "handakuten_small",
}



def small_kana_script(codepoint: int) -> str:
    if 0x3040 <= codepoint <= 0x309F or codepoint == 0x1B132:
        return "hiragana"
    return "katakana"


def _load_mark_position_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{path}: missing configuration file") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def _require_object_keys(
    path: Path, label: str, value: object, expected_keys: set[str]
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {label} must be an object")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        unknown = actual_keys - expected_keys
        details = [
            *(f"missing {key}" for key in sorted(missing)),
            *(f"unknown {key!r}" for key in sorted(unknown)),
        ]
        raise ValueError(f"{path}: {label} {', '.join(details)}")
    return value


def _parse_mark_position_codepoint(
    path: Path, label: str, value: object
) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{path}: {label} must be uppercase hexadecimal")
    try:
        codepoint = int(value, 16)
    except ValueError as error:
        raise ValueError(
            f"{path}: {label} must be uppercase hexadecimal"
        ) from error
    if not 0 <= codepoint <= 0x10FFFF:
        raise ValueError(f"{path}: {label} is outside the Unicode range")
    if value != f"{codepoint:04X}":
        raise ValueError(f"{path}: {label} must be uppercase hexadecimal")
    return codepoint


def _parse_mark_position_pair(path: Path, value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError(f"{path}: pair key must be a string")
    parts = value.split("+")
    if len(parts) != 2:
        raise ValueError(f"{path}: pair key {value!r} must be BASE+MARK")
    base = _parse_mark_position_codepoint(path, "pair base", parts[0])
    mark = _parse_mark_position_codepoint(path, "pair mark", parts[1])
    if value != f"{base:04X}+{mark:04X}":
        raise ValueError(f"{path}: pair key {value!r} must be BASE+MARK")
    return base, mark


def _finite_mark_position_values(
    path: Path, label: str, value: object, length: int, description: str
) -> list[float | int]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{path}: {label} must be {description}")
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(item)
        for item in value
    ):
        raise ValueError(
            f"{path}: {label} must contain finite numeric values"
        )
    return value


def _mark_position_transform(
    path: Path, label: str, value: object
) -> Transform:
    scale, x_offset, y_offset = _finite_mark_position_values(
        path, label, value, 3, "[scale, x, y]"
    )
    if scale <= 0:
        raise ValueError(f"{path}: {label} scale must be positive")
    return Transform(scale, 0, 0, scale, x_offset, y_offset)


def _load_common_mark_position_overrides(
    directory: Path,
) -> dict[tuple[int, int], dict[str, Transform]]:
    expected_pairs = set(MANGA_MARK_PAIRS)
    loaded: dict[tuple[int, int], dict[str, Transform]] = {}
    for filename, expected_mark, expected_script in MARK_POSITION_GROUPS:
        path = directory / filename
        data = _require_object_keys(
            path,
            "root",
            _load_mark_position_json(path),
            {"mark", "positions"},
        )
        mark = _parse_mark_position_codepoint(path, "mark", data["mark"])
        if mark != expected_mark:
            raise ValueError(
                f"{path}: expected mark U+{expected_mark:04X}, "
                f"got U+{mark:04X}"
            )
        positions = data["positions"]
        if not isinstance(positions, dict):
            raise ValueError(f"{path}: positions must be an object")
        parsed_positions = {
            _parse_mark_position_codepoint(path, "base key", base_hex):
            orientations
            for base_hex, orientations in positions.items()
        }
        expected_bases = {
            base
            for base, pair_mark in expected_pairs
            if pair_mark == mark
            and small_kana_script(base) == expected_script
        }
        actual_bases = set(parsed_positions)
        if actual_bases != expected_bases:
            missing = expected_bases - actual_bases
            extra = actual_bases - expected_bases
            details = [
                *(f"missing U+{value:04X}" for value in sorted(missing)),
                *(f"extra U+{value:04X}" for value in sorted(extra)),
            ]
            raise ValueError(f"{path}: {', '.join(details)}")
        for base, orientations in parsed_positions.items():
            orientations = _require_object_keys(
                path,
                f"U+{base:04X}",
                orientations,
                {"horizontal", "vertical"},
            )
            pair = (base, mark)
            loaded[pair] = {
                orientation: _mark_position_transform(
                    path,
                    f"U+{base:04X} {orientation}",
                    orientations[orientation],
                )
                for orientation in ("horizontal", "vertical")
            }
    if loaded.keys() != expected_pairs:
        raise AssertionError("Mark position files must cover all 191 sequences")
    return loaded


def _validate_koburi_measurement(
    path: Path, value: object
) -> None:
    measurement = _require_object_keys(
        path,
        "measurement",
        value,
        {"relative_bbox_delta", "vertical_contact_clearance"},
    )
    deltas = _require_object_keys(
        path,
        "measurement.relative_bbox_delta",
        measurement["relative_bbox_delta"],
        {"horizontal", "vertical"},
    )
    for orientation in ("horizontal", "vertical"):
        orientation_deltas = _require_object_keys(
            path,
            f"measurement.relative_bbox_delta.{orientation}",
            deltas[orientation],
            KOBURI_MEASUREMENT_GROUPS,
        )
        for group, values in orientation_deltas.items():
            _finite_mark_position_values(
                path,
                (
                    "measurement.relative_bbox_delta."
                    f"{orientation}.{group}"
                ),
                values,
                4,
                "[center_x, center_y, width, height]",
            )
    clearance = measurement["vertical_contact_clearance"]
    if not isinstance(clearance, dict):
        raise ValueError(
            f"{path}: measurement.vertical_contact_clearance "
            "must be an object"
        )
    for pair_key, offsets in clearance.items():
        pair = _parse_mark_position_pair(path, pair_key)
        if pair not in KOBURI_GENERATED_MARK_PAIRS:
            raise ValueError(
                f"{path}: measurement.vertical_contact_clearance "
                f"has unknown pair {pair_key!r}"
            )
        offsets = _finite_mark_position_values(
            path,
            f"measurement.vertical_contact_clearance.{pair_key}",
            offsets,
            2,
            "[x, y]",
        )
        if any(value < 0 for value in offsets):
            raise ValueError(
                f"{path}: measurement.vertical_contact_clearance."
                f"{pair_key} must be nonnegative"
            )


def _load_koburi_mark_position_overrides(
    directory: Path,
) -> dict[tuple[int, int], dict[str, Transform]]:
    path = directory / KOBURI_MARK_POSITION_FILENAME
    data = _require_object_keys(
        path,
        "root",
        _load_mark_position_json(path),
        {"source", "measurement", "positions"},
    )
    source = _require_object_keys(
        path,
        "source",
        data["source"],
        set(KOBURI_MARK_POSITION_SOURCE),
    )
    if source != KOBURI_MARK_POSITION_SOURCE:
        raise ValueError(
            f"{path}: source metadata does not match GenEi Koburi Mincho "
            "v6.1"
        )
    _validate_koburi_measurement(path, data["measurement"])
    positions = data["positions"]
    if not isinstance(positions, dict):
        raise ValueError(f"{path}: positions must be an object")
    parsed_positions = {
        _parse_mark_position_pair(path, pair_key): orientations
        for pair_key, orientations in positions.items()
    }
    actual_pairs = set(parsed_positions)
    if actual_pairs != KOBURI_GENERATED_MARK_PAIRS:
        native = actual_pairs & KOBURI_NATIVE_MARK_PAIRS
        missing = KOBURI_GENERATED_MARK_PAIRS - actual_pairs
        extra = actual_pairs - KOBURI_GENERATED_MARK_PAIRS
        details = [
            *(
                f"native ccmp pair U+{base:04X}+U+{mark:04X}"
                for base, mark in sorted(native)
            ),
            *(
                f"missing U+{base:04X}+U+{mark:04X}"
                for base, mark in sorted(missing)
            ),
            *(
                f"extra U+{base:04X}+U+{mark:04X}"
                for base, mark in sorted(extra - native)
            ),
        ]
        raise ValueError(f"{path}: {', '.join(details)}")
    loaded: dict[tuple[int, int], dict[str, Transform]] = {}
    for pair, orientations in parsed_positions.items():
        base, mark = pair
        orientations = _require_object_keys(
            path,
            f"U+{base:04X}+U+{mark:04X}",
            orientations,
            {"horizontal", "vertical"},
        )
        loaded[pair] = {
            orientation: _mark_position_transform(
                path,
                f"U+{base:04X}+U+{mark:04X} {orientation}",
                orientations[orientation],
            )
            for orientation in ("horizontal", "vertical")
        }
    return loaded


def load_mark_position_overrides(
    directory: Path = MARK_POSITION_DIRECTORY, *, base: str = "noto"
) -> dict[tuple[int, int], dict[str, Transform]]:
    if base not in {"noto", "koburi"}:
        raise ValueError(f"Unknown mark position base {base!r}")
    loaded = _load_common_mark_position_overrides(directory)
    if base == "koburi":
        for pair, orientations in _load_koburi_mark_position_overrides(
            directory
        ).items():
            loaded[pair].update(orientations)
    return loaded


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
        "--source",
        type=Path,
        help="local Noto Serif JP OTF/TTC or GenEi Koburi Mincho TTF",
    )
    parser.add_argument(
        "--latin-source",
        type=Path,
        help="local Libertinus Serif OTF used for Noto-based Latin glyphs",
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
        "--face", type=int, default=0, help="TTC face index"
    )
    parser.add_argument("--output", type=Path)
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


def mark_collision_free_transform(
    base: pathops.Path,
    mark: pathops.Path,
    mark_transform: Transform,
    maximum_y: float,
) -> Transform:
    """Move a combining mark by the shortest outward collision escape."""
    placed_mark = transform_path(mark, mark_transform)
    if placed_mark.bounds[3] > maximum_y:
        raise ValueError("Combining mark exceeds vertical metrics")

    def is_clear(outline: pathops.Path) -> bool:
        intersection = pathops.op(
            base, outline, pathops.PathOp.INTERSECTION
        )
        return (
            not intersection.verbs
            or abs(intersection.area) <= MARK_COLLISION_AREA_EPSILON
        )

    if is_clear(placed_mark):
        return mark_transform

    base_x_min, base_y_min, base_x_max, base_y_max = base.bounds
    mark_x_min, mark_y_min, mark_x_max, mark_y_max = placed_mark.bounds
    x_direction = (
        1
        if mark_x_min + mark_x_max >= base_x_min + base_x_max
        else -1
    )
    y_direction = (
        1
        if mark_y_min + mark_y_max >= base_y_min + base_y_max
        else -1
    )
    x_limit = max(
        1,
        math.ceil(
            base_x_max - mark_x_min
            if x_direction > 0
            else mark_x_max - base_x_min
        )
        + 1,
    )
    y_limit = max(
        1,
        math.ceil(
            base_y_max - mark_y_min
            if y_direction > 0
            else mark_y_max - base_y_min
        )
        + 1,
    )
    rays = (
        (x_direction, 0, x_limit),
        (0, y_direction, y_limit),
        (x_direction, y_direction, min(x_limit, y_limit)),
    )
    candidates: list[tuple[int, int, int, Transform]] = []
    for x_step, y_step, limit in rays:
        for distance in range(1, limit + 1):
            x_offset = x_step * distance
            y_offset = y_step * distance
            adjusted_transform = Transform(
                mark_transform.xx,
                mark_transform.xy,
                mark_transform.yx,
                mark_transform.yy,
                mark_transform.dx + x_offset,
                mark_transform.dy + y_offset,
            )
            adjusted_mark = transform_path(mark, adjusted_transform)
            if adjusted_mark.bounds[3] > maximum_y:
                if y_step > 0:
                    break
                continue
            if is_clear(adjusted_mark):
                candidates.append(
                    (
                        x_offset * x_offset + y_offset * y_offset,
                        abs(y_offset),
                        abs(x_offset),
                        adjusted_transform,
                    )
                )
                break
    if not candidates:
        raise ValueError(
            "Could not place combining mark without collision "
            "within vertical metrics"
        )
    return min(candidates, key=lambda candidate: candidate[:3])[3]


def compose_mark_glyph(
    base: pathops.Path,
    mark: pathops.Path,
    mark_transform: Transform = DEFAULT_MARK_TRANSFORM,
) -> pathops.Path:
    combined = pathops.Path()
    combined.addPath(base)
    combined.addPath(transform_path(mark, mark_transform))
    return combined


def expand_outline(
    outline: pathops.Path, radius: float, steps: int
) -> pathops.Path:
    expanded = outline
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        shifted = transform_path(
            outline,
            Transform(
                1,
                0,
                0,
                1,
                radius * math.cos(angle),
                radius * math.sin(angle),
            ),
        )
        expanded = pathops.op(expanded, shifted, pathops.PathOp.UNION)
    return expanded


def compose_heart_dakuten_glyph(
    base: pathops.Path, mark: pathops.Path
) -> pathops.Path:
    mark_contours = list(mark.contours)
    if len(mark_contours) != len(HEART_DAKUTEN_MARK_TRANSFORMS):
        raise ValueError("Expected a two-contour combining dakuten glyph")
    placed_contours = [
        transform_path(contour, transform)
        for contour, transform in zip(
            mark_contours, HEART_DAKUTEN_MARK_TRANSFORMS, strict=True
        )
    ]
    placed_mark = pathops.Path()
    for contour in placed_contours:
        placed_mark.addPath(contour)
    centers = [
        ((x_min + x_max) / 2, (y_min + y_max) / 2)
        for x_min, y_min, x_max, y_max in (
            contour.bounds for contour in placed_contours
        )
    ]
    clearance_radius = math.dist(*centers) * HEART_DAKUTEN_CLEARANCE_RATIO
    clearance = expand_outline(
        placed_mark,
        clearance_radius,
        HEART_DAKUTEN_CLEARANCE_STEPS,
    )
    notched_base = pathops.op(
        base, clearance, pathops.PathOp.DIFFERENCE
    )
    combined = pathops.Path()
    combined.addPath(notched_base)
    combined.addPath(placed_mark)
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


def make_sans_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    cmap = font.getBestCmap()
    components = [
        glyph_path(font, cmap[0xFF01 if mark == "!" else 0xFF1F])
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
            transform_path(
                outline,
                Transform(scale, 0, 0, 1, cursor - scale * x_min, 0),
            )
        )
        cursor += (width + gap) * scale
    return combined


def slant_punctuation_outline(
    outline: pathops.Path,
) -> pathops.Path:
    shear = math.tan(math.radians(PUNCTUATION_SLANT_ANGLE))
    slanted = transform_path(outline, Transform(1, 0, shear, 1, 0, 0))
    x_min, _, x_max, _ = slanted.bounds
    return transform_path(
        slanted,
        Transform(1, 0, 0, 1, 500 - (x_min + x_max) / 2, 0),
    )


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


def tt_glyph(outline: pathops.Path, units_per_em: int):
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


def adjust_outline_weight(
    outline: pathops.Path, amount: float
) -> pathops.Path:
    if amount == 0 or not outline.verbs:
        return outline
    boundary = pathops.Path()
    boundary.addPath(outline)
    boundary.stroke(
        2 * abs(amount),
        pathops.LineCap.BUTT_CAP,
        pathops.LineJoin.MITER_JOIN,
        4,
    )
    operation = (
        pathops.PathOp.UNION
        if amount > 0
        else pathops.PathOp.DIFFERENCE
    )
    adjusted = pathops.op(outline, boundary, operation)
    if outline.verbs and not adjusted.verbs:
        raise ValueError("Latin weight adjustment removed an entire glyph")
    return adjusted


def replace_glyph_from_source(
    font: TTFont,
    target_name: str,
    source_font: TTFont,
    source_name: str,
    weight_adjustment: float = 0,
) -> None:
    try:
        _, _, _, target_y_max = bounds(font, target_name)
    except ValueError:
        target_y_max = 0
    vertical_origin = (
        font["vmtx"].metrics[target_name][1] + target_y_max
        if "vmtx" in font
        else 0
    )
    source_advance, source_lsb = source_font["hmtx"].metrics[source_name]
    outline = adjust_outline_weight(
        glyph_path(source_font, source_name), weight_adjustment
    )
    left_side_bearing = (
        math.floor(outline.bounds[0])
        if weight_adjustment and outline.verbs
        else source_lsb
    )
    replace_glyph(
        font,
        target_name,
        outline,
        round(vertical_origin),
        advance_override=source_advance,
        left_side_bearing_override=left_side_bearing,
    )


def replace_latin_glyphs(
    font: TTFont,
    latin_font: TTFont,
    weight_adjustment: float = 0,
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
        for start, end in LATIN_REPLACEMENT_RANGES
        for codepoint in range(start, end + 1)
    }
    candidates.update(LATIN_TYPOGRAPHIC_CODEPOINTS)
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
            weight_adjustment,
        )
        replaced.append(codepoint)
        replaced_names.add(target_name)
    return tuple(replaced)


def replace_latin_gsub_glyphs(
    font: TTFont,
    latin_font: TTFont,
    replaced_codepoints: tuple[int, ...],
    weight_adjustment: float = 0,
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
        target_defaults.update(
            feature_single_substitutions(font, feature_tag)
        )
        target_defaults.update(
            {
                components[0]: output
                for components, output in feature_ligatures(
                    font, feature_tag
                ).items()
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
                weight_adjustment,
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
            weight_adjustment,
        )
        replaced_outputs.add(target_output)
    return tuple(sorted(replaced_outputs))


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
    append_glyphs(
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
        top.Notice = font_notice
        top.FamilyName = identity.family
        top.FullName = identity.full_name


def build(
    source_path: Path,
    latin_source_path: Path | None,
    punctuation_source_path: Path,
    sans_source_path: Path,
    output_path: Path,
    identity: FontIdentity,
    face: int,
    base_type: str,
) -> None:
    font = TTFont(source_path, fontNumber=face, recalcTimestamp=True)
    if font["head"].unitsPerEm != 1000:
        scale_upem(font, 1000)
    latin_font = TTFont(latin_source_path) if latin_source_path else None
    if latin_font and latin_font["head"].unitsPerEm != 1000:
        scale_upem(latin_font, 1000)
    punctuation_font = TTFont(punctuation_source_path)
    sans_font = TTFont(sans_source_path)
    cmap = font.getBestCmap()
    punctuation_cmap = punctuation_font.getBestCmap()
    sans_cmap = sans_font.getBestCmap()
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
        for base, _ in MANGA_MARK_PAIRS
        if base not in MANGA_MISSING_SMALL_KANA
    )
    required_codepoints.extend(
        base for base, _ in KOBURI_HEART_MARK_PAIRS
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
    if len(KOBURI_PUA_MARK_PAIRS) != 88:
        raise AssertionError("Expected 88 Koburi Mincho PUA mappings")
    if not set(KOBURI_PUA_MARK_PAIRS) <= set(MANGA_MARK_PAIRS):
        raise AssertionError("Koburi Mincho PUA mappings must use Manga1 sequences")
    if len(KOBURI_GENERATED_MARK_PAIRS) != 103:
        raise AssertionError("Expected 103 generated Koburi mark sequences")
    if len(KOBURI_HEART_MARK_PAIRS) != 2:
        raise AssertionError("Expected two Koburi Mincho heart mappings")
    if latin_font is not None:
        weight_adjustment = LIBERTINUS_STROKE_ADJUSTMENTS[identity.style]
        replaced_latin = replace_latin_glyphs(
            font, latin_font, weight_adjustment
        )
        replace_latin_gsub_glyphs(
            font, latin_font, replaced_latin, weight_adjustment
        )

    source_ccmp_ligatures = feature_ligatures(font, "ccmp")
    native_mark_outputs: dict[tuple[int, int], str] = {}
    for base, mark in MANGA_MARK_PAIRS:
        if base not in cmap:
            continue
        output = source_ccmp_ligatures.get((cmap[base], cmap[mark]))
        if output is not None:
            native_mark_outputs[(base, mark)] = output
    if base_type == "koburi":
        actual_native_pairs = frozenset(native_mark_outputs)
        if actual_native_pairs != KOBURI_NATIVE_MARK_PAIRS:
            missing = KOBURI_NATIVE_MARK_PAIRS - actual_native_pairs
            extra = actual_native_pairs - KOBURI_NATIVE_MARK_PAIRS
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
    mark_position_overrides = load_mark_position_overrides(base=base_type)
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
        + PUNCTUATION_ALTERNATE_COUNT
        + 2 * len(MANGA_MISSING_SMALL_KANA)
        + len(generated_mark_pairs)
        + len(generated_vertical_mark_pairs)
        + len(KOBURI_HEART_MARK_PAIRS)
        + RUBY_GLYPH_COUNT,
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
    append_glyphs(
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
    replace_glyph(
        font,
        manga_wave_base,
        manga_wave_isolated,
        manga_wave_vertical_origin,
    )
    append_glyphs(
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
    append_glyphs(
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
        "!": glyph_path(font, cmap[0xFF01]),
        "?": glyph_path(font, cmap[0xFF1F]),
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
            sans_path = glyph_path(
                sans_font,
                sans_cmap[0xFF01 if sequence == "!" else 0xFF1F],
            )
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
    append_glyphs(
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
            font, vertical_glyph_or_self(font, cmap[0x3053])
        ),
        0.78,
        654,
        397,
    )
    small_katakana_vertical = centered_scaled_path(
        glyph_path(
            font, vertical_glyph_or_self(font, cmap[0x30B3])
        ),
        0.78,
        654,
        397,
    )
    append_glyphs(
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
    noto_mark_metric_ceiling = (
        font["hhea"].ascent if base_type == "noto" else None
    )
    horizontal_mark_paths = []
    for base, mark in generated_mark_pairs:
        base_path = glyph_path(font, cmap[base])
        mark_transform = mark_position_overrides[(base, mark)]["horizontal"]
        if noto_mark_metric_ceiling is not None:
            mark_transform = mark_collision_free_transform(
                base_path,
                mark_paths[mark],
                mark_transform,
                noto_mark_metric_ceiling,
            )
        horizontal_mark_paths.append(
            compose_mark_glyph(base_path, mark_paths[mark], mark_transform)
        )
    append_glyphs(
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
        base_path = glyph_path(font, vertical_base)
        mark_transform = mark_position_overrides[(base, mark)]["vertical"]
        if noto_mark_metric_ceiling is not None:
            mark_transform = mark_collision_free_transform(
                base_path,
                mark_paths[mark],
                mark_transform,
                noto_mark_metric_ceiling,
            )
        vertical_mark_paths.append(
            compose_mark_glyph(base_path, mark_paths[mark], mark_transform)
        )
    append_glyphs(
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
            (horizontal, vertical_glyph_or_self(font, horizontal))
        )

    heart_start = mark_vertical_start + len(generated_vertical_mark_pairs)
    heart_names = allocated_names[
        heart_start : heart_start + len(KOBURI_HEART_MARK_PAIRS)
    ]
    heart_paths = [
        compose_heart_dakuten_glyph(
            glyph_path(font, cmap[base]),
            mark_paths[mark],
        )
        for base, mark in KOBURI_HEART_MARK_PAIRS
    ]
    append_glyphs(
        font,
        heart_paths,
        heart_names,
        cmap[0x2661],
        880,
        add_stem_hints=False,
    )
    for codepoint, (base, _) in zip(
        KOBURI_HEART_BASE_PUA,
        KOBURI_HEART_MARK_PAIRS,
        strict=True,
    ):
        add_unicode_mapping(font, codepoint, cmap[base])
    for codepoint, output in zip(
        KOBURI_HEART_OUTPUT_PUA, heart_names, strict=True
    ):
        add_unicode_mapping(font, codepoint, output)

    mark_outputs = native_mark_outputs | generated_mark_outputs
    ruby_start = heart_start + len(KOBURI_HEART_MARK_PAIRS)
    ruby_names = allocated_names[
        ruby_start : ruby_start + RUBY_GLYPH_COUNT
    ]
    ruby_normal_names = [
        mark_outputs[pair] for pair in MANGA_RUBY_HANDAKUTEN_PAIRS
    ]
    ruby_paths = [
        transform_path(
            glyph_path(font, name),
            Transform(RUBY_SCALE, 0, 0, RUBY_SCALE, 0, 0),
        )
        for name in ruby_normal_names
    ]
    ruby_vertical_source = dict(kana_vertical_maps)[ruby_normal_names[0]]
    ruby_vertical_path = transform_path(
        glyph_path(font, ruby_vertical_source),
        Transform(RUBY_SCALE, 0, 0, RUBY_SCALE, 0, 0),
    )
    append_glyphs(
        font,
        [*ruby_paths, ruby_vertical_path],
        ruby_names,
        ruby_normal_names[0],
        440,
        add_stem_hints=False,
        advance_override=500,
    )
    kana_vertical_maps.append((ruby_names[0], ruby_names[-1]))
    ruby_substitutions = list(
        zip(
            ruby_normal_names,
            ruby_names[: len(ruby_normal_names)],
            strict=True,
        )
    )
    for offset, pair in enumerate(KOBURI_PUA_MARK_PAIRS):
        add_unicode_mapping(
            font,
            KOBURI_PUA_START + offset,
            mark_outputs[pair],
        )
    kana_marks = [
        (cmap[base], cmap[mark], mark_outputs[(base, mark)])
        for base, mark in MANGA_MARK_PAIRS
    ]
    kana_marks.extend(
        (cmap[base], cmap[mark], output)
        for (base, mark), output in zip(
            KOBURI_HEART_MARK_PAIRS, heart_names, strict=True
        )
    )

    latin_copyright = (
        (latin_font["name"].getDebugName(0) or LIBERTINUS_COPYRIGHT)
        if latin_font
        else None
    )
    latin_license = (
        latin_font["name"].getDebugName(13) if latin_font else None
    )
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
        font["CFF "].cff.topDictIndex[0].Notice
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


def main() -> None:
    args = parse_args()
    if args.base == "koburi" and args.weight != "Regular":
        raise ValueError("GenEi Koburi Mincho is available in Regular only")
    if args.base == "koburi" and args.latin_source is not None:
        raise ValueError("--latin-source is available for the Noto base only")
    identity = font_identity(args.base, args.weight)
    output_path = args.output or default_output_path(identity, args.base)

    with tempfile.TemporaryDirectory(
        prefix="nobigoe-mincho-"
    ) as directory:
        temporary_directory = Path(directory)
        source_path = args.source
        if source_path is None and args.base == "noto":
            source_filename, source_url, source_sha256 = (
                noto_serif_source(args.weight)
            )
            source_path = temporary_directory / source_filename
            print(f"Downloading {source_url}")
            urllib.request.urlretrieve(source_url, source_path)
            verify_sha256(source_path, source_sha256)
        elif source_path is None:
            source_archive_path = (
                temporary_directory / "GenEiKoburiMin_v6.1.zip"
            )
            source_path = temporary_directory / "GenEiKoburiMin6-R.ttf"
            print(f"Downloading {KOBURI_ARCHIVE_URL}")
            urllib.request.urlretrieve(
                KOBURI_ARCHIVE_URL, source_archive_path
            )
            verify_sha256(
                source_archive_path, KOBURI_ARCHIVE_SHA256
            )
            with zipfile.ZipFile(source_archive_path) as archive:
                source_path.write_bytes(
                    archive.read(KOBURI_TTF_MEMBER)
                )
            verify_sha256(source_path, KOBURI_TTF_SHA256)

        latin_source_path = args.latin_source
        if args.base == "noto" and latin_source_path is None:
            latin_archive_path = (
                temporary_directory / "Libertinus.zip"
            )
            latin_member, latin_sha256 = libertinus_serif_source(args.weight)
            latin_source_path = temporary_directory / Path(latin_member).name
            print(f"Downloading {LIBERTINUS_ARCHIVE_URL}")
            urllib.request.urlretrieve(
                LIBERTINUS_ARCHIVE_URL, latin_archive_path
            )
            verify_sha256(
                latin_archive_path, LIBERTINUS_ARCHIVE_SHA256
            )
            with zipfile.ZipFile(latin_archive_path) as archive:
                latin_source_path.write_bytes(archive.read(latin_member))
            verify_sha256(latin_source_path, latin_sha256)

        sans_source_path = args.sans_source
        if sans_source_path is None:
            sans_profile_weight = (
                "Regular" if args.base == "koburi" else args.weight
            )
            sans_filename, sans_source_url, sans_sha256 = (
                noto_sans_source(sans_profile_weight)
            )
            sans_source_path = temporary_directory / sans_filename
            print(f"Downloading {sans_source_url}")
            urllib.request.urlretrieve(
                sans_source_url, sans_source_path
            )
            verify_sha256(sans_source_path, sans_sha256)

        punctuation_source_path = args.punctuation_source
        if punctuation_source_path is None:
            punctuation_archive_path = (
                temporary_directory / "shippori3.zip"
            )
            shippori_profile_weight = (
                "Regular" if args.base == "koburi" else args.weight
            )
            shippori_member, shippori_sha256 = shippori_source(
                shippori_profile_weight
            )
            punctuation_source_path = (
                temporary_directory / shippori_member
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
                    archive.read(shippori_member)
                )
            verify_sha256(punctuation_source_path, shippori_sha256)

        build(
            source_path,
            latin_source_path,
            punctuation_source_path,
            sans_source_path,
            output_path,
            identity,
            args.face,
            args.base,
        )


if __name__ == "__main__":
    main()
