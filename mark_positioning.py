"""Typed kana combining-mark positions and configuration loading."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, cast

from fontTools.misc.transform import Transform

from font_profiles import BaseType, KOBURI_TTF_MEMBER, KOBURI_TTF_SHA256


Orientation: TypeAlias = Literal["horizontal", "vertical"]
KanaScript: TypeAlias = Literal["hiragana", "katakana"]
MarkPair: TypeAlias = tuple[int, int]

class MarkPosition(TypedDict):
    horizontal: Transform
    vertical: Transform

MarkPositionMap: TypeAlias = dict[MarkPair, MarkPosition]
JsonObject: TypeAlias = dict[str, object]

ORIENTATIONS: tuple[Orientation, ...] = ("horizontal", "vertical")

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
MANGA_RUBY_HANDAKUTEN_PAIRS: tuple[MarkPair, ...] = tuple(
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
MANGA_MARK_PAIRS: tuple[MarkPair, ...] = tuple(
    [(base, 0x3099) for base in MANGA_DAKUTEN_BASES]
    + [(base, 0x309A) for base in MANGA_HANDAKUTEN_BASES]
)
KOBURI_PUA_START = 0xE082
KOBURI_PUA_MARK_PAIRS: tuple[MarkPair, ...] = tuple(
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
KOBURI_HEART_MARK_PAIRS: tuple[MarkPair, ...] = (
    (0x2661, 0x3099),
    (0x2665, 0x3099),
)
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
MANGA_VERTICAL_MARK_PAIRS: frozenset[MarkPair] = frozenset(
    [(base, 0x3099) for base in MANGA_VERTICAL_DAKUTEN_BASES]
    + [(base, 0x309A) for base in MANGA_VERTICAL_HANDAKUTEN_BASES]
)
MANGA_SMALL_KANA_BASES = frozenset(
    MANGA_VERTICAL_DAKUTEN_BASES + MANGA_VERTICAL_HANDAKUTEN_BASES
)
DEFAULT_MARK_TRANSFORM = Transform(1, 0, 0, 1, 1000, 0)
MARK_POSITION_GROUPS: tuple[tuple[str, int, KanaScript], ...] = (
    ("hiragana_dakuten.json", 0x3099, "hiragana"),
    ("hiragana_handakuten.json", 0x309A, "hiragana"),
    ("katakana_dakuten.json", 0x3099, "katakana"),
    ("katakana_handakuten.json", 0x309A, "katakana"),
)
MARK_POSITION_DIRECTORY = Path(__file__).resolve().parent / "mark_positions"
MANGA_MISSING_SMALL_KANA = (0x1B132, 0x1B155)
KOBURI_MARK_POSITION_FILENAME = "koburi.json"
KOBURI_NATIVE_MARK_PAIRS: frozenset[MarkPair] = frozenset(
    KOBURI_PUA_MARK_PAIRS
)
KOBURI_GENERATED_MARK_PAIRS: frozenset[MarkPair] = frozenset(
    MANGA_MARK_PAIRS
) - KOBURI_NATIVE_MARK_PAIRS
KOBURI_MARK_POSITION_SOURCE: JsonObject = {
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


def small_kana_script(codepoint: int) -> KanaScript:
    if 0x3040 <= codepoint <= 0x309F or codepoint == 0x1B132:
        return "hiragana"
    return "katakana"


def _require_json_object(path: Path, label: str, value: object) -> JsonObject:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise ValueError(f"{path}: {label} must be an object")
    return cast(JsonObject, value)


def _load_mark_position_json(path: Path) -> JsonObject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{path}: missing configuration file") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error
    return _require_json_object(path, "root", data)


def _require_object_keys(
    path: Path,
    label: str,
    value: object,
    expected_keys: set[str],
) -> JsonObject:
    value = _require_json_object(path, label, value)
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
    path: Path,
    label: str,
    value: object,
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


def _parse_mark_position_pair(path: Path, value: object) -> MarkPair:
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
    path: Path,
    label: str,
    value: object,
    length: int,
    description: str,
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
    return cast(list[float | int], value)


def _mark_position_transform(
    path: Path,
    label: str,
    value: object,
) -> Transform:
    scale, x_offset, y_offset = _finite_mark_position_values(
        path, label, value, 3, "[scale, x, y]"
    )
    if scale <= 0:
        raise ValueError(f"{path}: {label} scale must be positive")
    return Transform(scale, 0, 0, scale, x_offset, y_offset)


def _parse_mark_position(
    path: Path,
    label: str,
    value: object,
) -> MarkPosition:
    orientations = _require_object_keys(
        path, label, value, set(ORIENTATIONS)
    )
    return MarkPosition(
        horizontal=_mark_position_transform(
            path, f"{label} horizontal", orientations["horizontal"]
        ),
        vertical=_mark_position_transform(
            path, f"{label} vertical", orientations["vertical"]
        ),
    )


def _load_common_mark_position_overrides(directory: Path) -> MarkPositionMap:
    expected_pairs: set[MarkPair] = set(MANGA_MARK_PAIRS)
    loaded: MarkPositionMap = {}
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
        positions = _require_json_object(path, "positions", data["positions"])
        parsed_positions: dict[int, object] = {
            _parse_mark_position_codepoint(path, "base key", base_hex): orientations
            for base_hex, orientations in positions.items()
        }
        expected_bases = {
            base
            for base, pair_mark in expected_pairs
            if pair_mark == mark and small_kana_script(base) == expected_script
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
        for base, raw_orientations in parsed_positions.items():
            pair: MarkPair = (base, mark)
            loaded[pair] = _parse_mark_position(
                path,
                f"U+{base:04X}",
                raw_orientations,
            )
    if loaded.keys() != expected_pairs:
        raise AssertionError("Mark position files must cover all 191 sequences")
    return loaded


def _validate_koburi_measurement(path: Path, value: object) -> None:
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
        set(ORIENTATIONS),
    )
    for orientation in ORIENTATIONS:
        orientation_deltas = _require_object_keys(
            path,
            f"measurement.relative_bbox_delta.{orientation}",
            deltas[orientation],
            KOBURI_MEASUREMENT_GROUPS,
        )
        for group, values in orientation_deltas.items():
            _finite_mark_position_values(
                path,
                f"measurement.relative_bbox_delta.{orientation}.{group}",
                values,
                4,
                "[center_x, center_y, width, height]",
            )
    clearance = _require_json_object(
        path,
        "measurement.vertical_contact_clearance",
        measurement["vertical_contact_clearance"],
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


def _load_koburi_mark_position_overrides(directory: Path) -> MarkPositionMap:
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
    positions = _require_json_object(path, "positions", data["positions"])
    parsed_positions: dict[MarkPair, object] = {
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
    loaded: MarkPositionMap = {}
    for pair, raw_orientations in parsed_positions.items():
        base, mark = pair
        loaded[pair] = _parse_mark_position(
            path,
            f"U+{base:04X}+U+{mark:04X}",
            raw_orientations,
        )
    return loaded


def load_mark_position_overrides(
    directory: Path = MARK_POSITION_DIRECTORY,
    *,
    base: BaseType = "noto",
) -> MarkPositionMap:
    if base not in {"noto", "koburi"}:
        raise ValueError(f"Unknown mark position base {base!r}")
    loaded = _load_common_mark_position_overrides(directory)
    if base == "koburi":
        for pair, orientations in _load_koburi_mark_position_overrides(
            directory
        ).items():
            loaded[pair].update(orientations)
    return loaded
