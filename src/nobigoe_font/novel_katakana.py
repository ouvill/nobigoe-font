"""Same-weight Noto Serif JP derivation for novel-style katakana."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import AbstractSet, Literal, TypeAlias

from fontTools.ttLib import TTFont

from .novel import (
    NovelGlyphResult,
    NovelTransform,
    NovelVerticalTransform,
    transform_novel_glyph,
)

NovelKatakanaGroup: TypeAlias = Literal["straight", "curve", "small", "iteration"]

NOVEL_SMALL_KATAKANA_KO_CODEPOINT = 0x1B155
KATAKANA_SOURCE_CODEPOINTS = frozenset(
    (*range(0x30A1, 0x30FB), *range(0x30FD, 0x3100), *range(0x31F0, 0x3200))
)
KATAKANA_CODEPOINTS = frozenset(
    (*KATAKANA_SOURCE_CODEPOINTS, NOVEL_SMALL_KATAKANA_KO_CODEPOINT)
)

_SMALL_SOURCE_CODEPOINTS = frozenset(
    codepoint
    for codepoint in KATAKANA_SOURCE_CODEPOINTS
    if "SMALL" in unicodedata.name(chr(codepoint), "")
)
SMALL_KATAKANA_CODEPOINTS = frozenset(
    (*_SMALL_SOURCE_CODEPOINTS, NOVEL_SMALL_KATAKANA_KO_CODEPOINT)
)
ITERATION_KATAKANA_CODEPOINTS = frozenset(map(ord, "ヽヾヿ"))
_CURVE_BASE_CODEPOINTS = frozenset(
    map(ord, "アウエオカクシスソツナヌネノフムメモラリルレロワヲン")
)
CURVE_KATAKANA_CODEPOINTS = frozenset(
    codepoint
    for codepoint in KATAKANA_SOURCE_CODEPOINTS
    if codepoint not in SMALL_KATAKANA_CODEPOINTS
    and codepoint not in ITERATION_KATAKANA_CODEPOINTS
    and ord(unicodedata.normalize("NFD", chr(codepoint))[0]) in _CURVE_BASE_CODEPOINTS
)
STRAIGHT_KATAKANA_CODEPOINTS = KATAKANA_CODEPOINTS.difference(
    CURVE_KATAKANA_CODEPOINTS,
    SMALL_KATAKANA_CODEPOINTS,
    ITERATION_KATAKANA_CODEPOINTS,
)

_GROUPS: tuple[NovelKatakanaGroup, ...] = (
    "straight",
    "curve",
    "small",
    "iteration",
)
_WEIGHT_CLASSES = frozenset((200, 300, 400, 500, 600, 700, 900))
KATAKANA_HORIZONTAL_ANCHORS: Mapping[NovelKatakanaGroup, tuple[float, float]] = {
    group: (500, 370) for group in _GROUPS
}
KATAKANA_VERTICAL_ANCHORS: Mapping[NovelKatakanaGroup, tuple[float, float]] = {
    "straight": (500, 370),
    "curve": (500, 370),
    "small": (650, 395),
    "iteration": (500, 370),
}

KATAKANA_MASTER_PROFILES: Mapping[int, Mapping[NovelKatakanaGroup, NovelTransform]] = {
    200: {
        "straight": NovelTransform(0.95, 0.96, 1.5, 10, 8),
        "curve": NovelTransform(0.95, 0.96, 1, 10, 8),
        "small": NovelTransform(0.96, 0.97, 0.75, 3, -7),
        "iteration": NovelTransform(1.01, 0.97, 0.5, -18, 4),
    },
    400: {
        "straight": NovelTransform(0.94, 0.95, 0.5, 10, 7),
        "curve": NovelTransform(0.94, 0.95, 0, 10, 7),
        "small": NovelTransform(0.95, 0.96, 0.5, 3, -8),
        "iteration": NovelTransform(1, 0.96, 0, -18, 4),
    },
    900: {
        "straight": NovelTransform(0.935, 0.95, 0, 10, 5),
        "curve": NovelTransform(0.93, 0.95, 0, 10, 5),
        "small": NovelTransform(0.945, 0.955, 0, 3, -10),
        "iteration": NovelTransform(0.99, 0.96, 0, -18, 3),
    },
}

KATAKANA_VERTICAL_MASTER_PROFILES: Mapping[
    int, Mapping[NovelKatakanaGroup, NovelVerticalTransform]
] = {
    200: {
        "straight": NovelVerticalTransform(1.025, 1, 3, 0, 0.9),
        "curve": NovelVerticalTransform(1.025, 1, 3, 0, 0.9),
        "small": NovelVerticalTransform(0.965, 0.965, -25, -1, 0.9),
        "iteration": NovelVerticalTransform(1.015, 1, 7, 0, 0.9),
    },
    400: {
        "straight": NovelVerticalTransform(1.03, 1, 3, 0, 1),
        "curve": NovelVerticalTransform(1.03, 1, 3, 0, 1),
        "small": NovelVerticalTransform(0.96, 0.96, -25, -1, 1),
        "iteration": NovelVerticalTransform(1.02, 1, 7, 0, 1),
    },
    900: {
        "straight": NovelVerticalTransform(1.035, 1, 3, 0, 0.9),
        "curve": NovelVerticalTransform(1.035, 1, 3, 0, 0.9),
        "small": NovelVerticalTransform(0.955, 0.96, -25, -1, 0.9),
        "iteration": NovelVerticalTransform(1.02, 1, 7, 0, 0.9),
    },
}

KATAKANA_VERTICAL_HEIGHT_CORRECTIONS: Mapping[int, float] = {
    codepoint: 0.99 for codepoint in map(ord, "ハシンチワネケ")
}


@dataclass(frozen=True)
class _MappedKatakanaGlyph:
    name: str
    group: NovelKatakanaGroup
    vertical: bool
    codepoint: int | None = None
    marked: bool = False


@dataclass
class _KatakanaGlyphCollection:
    by_name: dict[str, _MappedKatakanaGlyph] = field(default_factory=dict)

    def add(
        self,
        glyphs: Mapping[str, str],
        *,
        vertical: bool,
        codepoints: Mapping[str, int] | None = None,
        marked_glyphs: AbstractSet[str] = frozenset(),
    ) -> None:
        for name, group in glyphs.items():
            if not isinstance(name, str) or not name:
                raise ValueError("Novel katakana glyph names must be non-empty strings")
            if group not in _GROUPS:
                raise ValueError(f"Unknown novel katakana group {group!r}")

            codepoint = codepoints.get(name) if codepoints is not None else None
            base = katakana_base_codepoint(codepoint) if codepoint is not None else None
            mapped = _MappedKatakanaGlyph(
                name,
                group,  # type: ignore[arg-type]
                vertical,
                codepoint,
                name in marked_glyphs or (codepoint is not None and base != codepoint),
            )
            existing = self.by_name.get(name)
            if existing is None:
                self.by_name[name] = mapped
            elif existing.group != mapped.group:
                raise ValueError(
                    f"Glyph {name!r} has conflicting novel katakana groups "
                    f"{existing.group!r} and {group!r}"
                )
            elif (
                existing.vertical
                and mapped.vertical
                and existing.codepoint is not None
                and mapped.codepoint is not None
                and katakana_base_codepoint(existing.codepoint)
                != katakana_base_codepoint(mapped.codepoint)
            ):
                raise ValueError(
                    f"Glyph {name!r} has conflicting vertical base codepoints"
                )
            elif (
                existing.vertical
                and mapped.vertical
                and mapped.marked
                and not existing.marked
            ):
                self.by_name[name] = _MappedKatakanaGlyph(
                    existing.name,
                    existing.group,
                    True,
                    existing.codepoint,
                    True,
                )
            # A cross-orientation alias has no distinct vertical outline. The
            # horizontal mapping was collected first and owns that outline.

    def ordered(self) -> tuple[_MappedKatakanaGlyph, ...]:
        return tuple(self.by_name[name] for name in sorted(self.by_name))


def _interpolate_transform(
    lower: NovelTransform, upper: NovelTransform, position: float
) -> NovelTransform:
    def value(lower_value: float, upper_value: float) -> float:
        return lower_value + position * (upper_value - lower_value)

    return NovelTransform(
        value(lower.sx, upper.sx),
        value(lower.sy, upper.sy),
        value(lower.stem_adjustment, upper.stem_adjustment),
        value(lower.dx, upper.dx),
        value(lower.dy, upper.dy),
    )


def _interpolate_vertical_transform(
    lower: NovelVerticalTransform,
    upper: NovelVerticalTransform,
    position: float,
) -> NovelVerticalTransform:
    def value(lower_value: float, upper_value: float) -> float:
        return lower_value + position * (upper_value - lower_value)

    return NovelVerticalTransform(
        value(lower.sx, upper.sx),
        value(lower.sy, upper.sy),
        value(lower.dx, upper.dx),
        value(lower.dy, upper.dy),
        value(lower.correction_strength, upper.correction_strength),
    )


def katakana_base_codepoint(codepoint: int) -> int:
    """Return the decomposed katakana base used by grouping and corrections."""
    if codepoint == NOVEL_SMALL_KATAKANA_KO_CODEPOINT:
        return codepoint
    try:
        return ord(unicodedata.normalize("NFD", chr(codepoint))[0])
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid katakana codepoint {codepoint!r}") from error


def novel_katakana_group_for_codepoint(
    codepoint: int,
) -> NovelKatakanaGroup:
    """Classify an encoded or decomposable katakana by its design group."""
    if codepoint in SMALL_KATAKANA_CODEPOINTS:
        return "small"
    base = katakana_base_codepoint(codepoint)
    if base in ITERATION_KATAKANA_CODEPOINTS:
        return "iteration"
    if base in _CURVE_BASE_CODEPOINTS:
        return "curve"
    return "straight"


def katakana_transform(weight_class: int, group: NovelKatakanaGroup) -> NovelTransform:
    """Return the canonical master or linear interpolation for one weight."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel katakana weight class {weight_class!r}")
    if group not in _GROUPS:
        raise ValueError(f"Unknown novel katakana group {group!r}")
    if weight_class in KATAKANA_MASTER_PROFILES:
        return KATAKANA_MASTER_PROFILES[weight_class][group]

    lower_weight = max(
        master for master in KATAKANA_MASTER_PROFILES if master < weight_class
    )
    upper_weight = min(
        master for master in KATAKANA_MASTER_PROFILES if master > weight_class
    )
    position = (weight_class - lower_weight) / (upper_weight - lower_weight)
    return _interpolate_transform(
        KATAKANA_MASTER_PROFILES[lower_weight][group],
        KATAKANA_MASTER_PROFILES[upper_weight][group],
        position,
    )


def katakana_vertical_transform(
    weight_class: int,
    group: NovelKatakanaGroup,
    codepoint: int | None,
) -> NovelTransform:
    """Return the vertical-only profile, including the base height correction."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel katakana weight class {weight_class!r}")
    if group not in _GROUPS:
        raise ValueError(f"Unknown novel katakana group {group!r}")
    if weight_class in KATAKANA_VERTICAL_MASTER_PROFILES:
        profile = KATAKANA_VERTICAL_MASTER_PROFILES[weight_class][group]
    else:
        lower_weight = max(
            master
            for master in KATAKANA_VERTICAL_MASTER_PROFILES
            if master < weight_class
        )
        upper_weight = min(
            master
            for master in KATAKANA_VERTICAL_MASTER_PROFILES
            if master > weight_class
        )
        position = (weight_class - lower_weight) / (upper_weight - lower_weight)
        profile = _interpolate_vertical_transform(
            KATAKANA_VERTICAL_MASTER_PROFILES[lower_weight][group],
            KATAKANA_VERTICAL_MASTER_PROFILES[upper_weight][group],
            position,
        )

    base = katakana_base_codepoint(codepoint) if codepoint is not None else None
    height = KATAKANA_VERTICAL_HEIGHT_CORRECTIONS.get(base, 1)
    corrected_height = 1 + (height - 1) * profile.correction_strength
    return NovelTransform(
        profile.sx,
        profile.sy * corrected_height,
        0,
        profile.dx,
        profile.dy,
    )


def apply_novel_katakana(
    font: TTFont,
    weight_class: int,
    horizontal_glyphs: Mapping[str, str],
    vertical_glyphs: Mapping[str, str],
    vertical_codepoints: Mapping[str, int] | None = None,
    vertical_marked_glyphs: AbstractSet[str] = frozenset(),
) -> NovelGlyphResult:
    """Apply canonical transforms once to each complete katakana outline."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel katakana weight class {weight_class!r}")

    collected = _KatakanaGlyphCollection()
    collected.add(horizontal_glyphs, vertical=False)
    collected.add(
        vertical_glyphs,
        vertical=True,
        codepoints=vertical_codepoints,
        marked_glyphs=vertical_marked_glyphs,
    )
    ordered = collected.ordered()

    if "CFF " not in font and "glyf" not in font:
        raise ValueError("Only OpenType/CFF and TrueType outlines are supported")
    glyph_set = font.getGlyphSet()
    missing = tuple(mapped.name for mapped in ordered if mapped.name not in glyph_set)
    if missing:
        raise ValueError(f"Novel katakana mappings contain missing glyphs: {missing!r}")

    for mapped in ordered:
        anchors = (
            KATAKANA_VERTICAL_ANCHORS
            if mapped.vertical
            else KATAKANA_HORIZONTAL_ANCHORS
        )
        vertical_profile = (
            katakana_vertical_transform(
                weight_class,
                mapped.group,
                mapped.codepoint,
            )
            if mapped.vertical
            else None
        )
        transform_novel_glyph(
            font,
            mapped.name,
            katakana_transform(weight_class, mapped.group),
            anchors[mapped.group],
            vertical_profile,
            error_label="novel katakana",
        )

    return NovelGlyphResult(
        tuple(mapped.name for mapped in ordered if not mapped.vertical),
        tuple(mapped.name for mapped in ordered if mapped.vertical),
    )


__all__ = (
    "CURVE_KATAKANA_CODEPOINTS",
    "ITERATION_KATAKANA_CODEPOINTS",
    "KATAKANA_CODEPOINTS",
    "KATAKANA_HORIZONTAL_ANCHORS",
    "KATAKANA_MASTER_PROFILES",
    "KATAKANA_SOURCE_CODEPOINTS",
    "KATAKANA_VERTICAL_ANCHORS",
    "KATAKANA_VERTICAL_HEIGHT_CORRECTIONS",
    "KATAKANA_VERTICAL_MASTER_PROFILES",
    "NOVEL_SMALL_KATAKANA_KO_CODEPOINT",
    "NovelKatakanaGroup",
    "SMALL_KATAKANA_CODEPOINTS",
    "STRAIGHT_KATAKANA_CODEPOINTS",
    "apply_novel_katakana",
    "katakana_base_codepoint",
    "katakana_transform",
    "katakana_vertical_transform",
    "novel_katakana_group_for_codepoint",
)
