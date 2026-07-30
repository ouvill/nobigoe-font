"""Same-weight Noto Serif JP derivation for the novel hiragana family.

Anisotropic anchor scaling retains the source gesture and counters; restrained
pathops stem adjustment and position shifts refine it without a second geometry
convention. Full-width advances and source vertical origins remain invariant.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import AbstractSet, Literal, TypeAlias

import pathops
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont

from . import geometry, operations

NovelGlyphGroup: TypeAlias = Literal["normal", "counter", "small", "iteration"]
NovelVerticalStemGroup: TypeAlias = Literal["strong", "fragile", "moderate"]

NOVEL_SMALL_KO_CODEPOINT = 0x1B132
HIRAGANA_CODEPOINTS = frozenset((*range(0x3041, 0x3097), *range(0x309D, 0x30A0)))
COUNTER_HIRAGANA_CODEPOINTS = frozenset(map(ord, "あおのぬねはほまみむめよゐゑ"))
SMALL_HIRAGANA_CODEPOINTS = frozenset(
    (*map(ord, "ぁぃぅぇぉっゃゅょゎゕゖ"), NOVEL_SMALL_KO_CODEPOINT)
)
ITERATION_HIRAGANA_CODEPOINTS = frozenset(map(ord, "ゝゞ"))
NORMAL_HIRAGANA_CODEPOINTS = HIRAGANA_CODEPOINTS.difference(
    COUNTER_HIRAGANA_CODEPOINTS,
    SMALL_HIRAGANA_CODEPOINTS,
    ITERATION_HIRAGANA_CODEPOINTS,
)

_GROUPS: tuple[NovelGlyphGroup, ...] = (
    "normal",
    "counter",
    "small",
    "iteration",
)
_WEIGHT_CLASSES = frozenset((200, 300, 400, 500, 600, 700, 900))
_HORIZONTAL_ANCHORS: Mapping[NovelGlyphGroup, tuple[float, float]] = {
    group: (500, 370) for group in _GROUPS
}
_VERTICAL_ANCHORS: Mapping[NovelGlyphGroup, tuple[float, float]] = {
    "normal": (500, 370),
    "counter": (500, 370),
    "small": (650, 395),
    "iteration": (500, 370),
}


@dataclass(frozen=True)
class NovelTransform:
    """One interpolated optical transform derived from a same-weight Noto glyph."""

    sx: float
    sy: float
    stem_adjustment: float
    dx: float
    dy: float


@dataclass(frozen=True)
class NovelVerticalTransform:
    """A second optical layer applied only to an already transformed vertical glyph."""

    sx: float
    sy: float
    dx: float
    dy: float
    correction_strength: float


NOVEL_MASTER_PROFILES: Mapping[int, Mapping[NovelGlyphGroup, NovelTransform]] = {
    200: {
        "normal": NovelTransform(0.95, 0.96, 1.5, 4, 9),
        "counter": NovelTransform(0.95, 0.96, 1, 4, 9),
        "small": NovelTransform(1, 1, 0.5, 5, 15),
        "iteration": NovelTransform(1.01, 1, 0.5, 0, 5),
    },
    400: {
        "normal": NovelTransform(0.94, 0.95, 0.5, 4, 8),
        "counter": NovelTransform(0.94, 0.95, 0, 4, 8),
        "small": NovelTransform(0.99, 0.99, 0, 5, 15),
        "iteration": NovelTransform(1, 1, 0, 0, 5),
    },
    900: {
        "normal": NovelTransform(0.935, 0.95, 0, 4, 5),
        "counter": NovelTransform(0.925, 0.95, 0, 4, 5),
        "small": NovelTransform(0.97, 0.98, 0, 4, 10),
        "iteration": NovelTransform(0.99, 0.99, 0, 0, 4),
    },
}

# Vertical masters are deliberately separate from NOVEL_MASTER_PROFILES. The
# canonical horizontal transform is applied first; this layer restores roundness
# and vertical white space without changing horizontal outlines or advances.
NOVEL_VERTICAL_MASTER_PROFILES: Mapping[
    int, Mapping[NovelGlyphGroup, NovelVerticalTransform]
] = {
    200: {
        "normal": NovelVerticalTransform(1.025, 1, 0, 0, 0.9),
        "counter": NovelVerticalTransform(1.025, 1, 0, 0, 0.9),
        "small": NovelVerticalTransform(1, 1, 0, 0, 0.9),
        "iteration": NovelVerticalTransform(1.015, 0.995, 0, 0, 0.9),
    },
    400: {
        "normal": NovelVerticalTransform(1.03, 1, 0, 0, 1),
        "counter": NovelVerticalTransform(1.03, 1, 0, 0, 1),
        "small": NovelVerticalTransform(1, 1, 0, 0, 1),
        "iteration": NovelVerticalTransform(1.02, 0.995, 0, 0, 1),
    },
    900: {
        "normal": NovelVerticalTransform(1.035, 1, 0, 0, 0.9),
        "counter": NovelVerticalTransform(1.03, 1, 0, 0, 0.9),
        "small": NovelVerticalTransform(1, 1, 0, 0, 0.9),
        "iteration": NovelVerticalTransform(1.02, 0.995, 0, 0, 0.9),
    },
}

# Regular vertical bounds measured against GenEi Koburi Mincho. Only glyphs
# taller than the reference are shortened; already low あ・す・ゆ・る remain
# at 1.0. Values are rounded optical corrections, not copied source geometry.
NOVEL_VERTICAL_HEIGHT_CORRECTIONS: Mapping[int, float] = {
    ord("へ"): 0.88,
    ord("ほ"): 0.94,
    ord("め"): 0.96,
    ord("ぬ"): 0.965,
    ord("せ"): 0.965,
    ord("り"): 0.97,
    ord("こ"): 0.975,
    ord("み"): 0.975,
    ord("お"): 0.98,
    ord("に"): 0.98,
    ord("つ"): 0.98,
    ord("の"): 0.98,
    ord("は"): 0.985,
    ord("い"): 0.985,
    ord("し"): 0.985,
    ord("た"): 0.985,
    ord("か"): 0.99,
    ord("や"): 0.99,
    ord("を"): 0.99,
    ord("よ"): 0.99,
    ord("ひ"): 0.995,
    ord("ん"): 0.995,
    ord("わ"): 0.995,
    ord("ね"): 0.995,
    ord("れ"): 0.995,
}

# Extra width multipliers sit on top of each vertical master. Narrow ぬ・り・
# ひ・け need more restoration; already broad forms receive less than the
# default. Every unlisted normal/counter glyph uses 1.0.
NOVEL_VERTICAL_WIDTH_CORRECTIONS: Mapping[int, float] = {
    **{ord(character): 1.03 for character in "ぬりひけ"},
    **{ord(character): 1.015 for character in "やわねそろ"},
    **{ord(character): 0.98 for character in "ほはよもまうさとき"},
}

# Regular relative ink prominence against Koburi determines two reproducible
# thresholds: >= 1.040 is strong and >= 1.025 is moderate. な exceeds the
# strong threshold but uses a topology-safe profile because erosion beyond
# 1.15 units removes small contours. Marks inherit the base group at 2/3
# strength so a composed dakuten/handakuten is not disproportionately thinned.
NOVEL_VERTICAL_STEM_GROUPS: Mapping[NovelVerticalStemGroup, frozenset[int]] = {
    "strong": frozenset(map(ord, "かきけせはも")),
    "fragile": frozenset(map(ord, "な")),
    "moderate": frozenset(map(ord, "たちにみむ")),
}
NOVEL_VERTICAL_STEM_MASTER_PROFILES: Mapping[
    int, Mapping[NovelVerticalStemGroup, float]
] = {
    200: {"strong": -0.75, "fragile": -0.5, "moderate": -0.5},
    400: {"strong": -1.5, "fragile": -1.0, "moderate": -0.75},
    900: {"strong": -0.75, "fragile": -0.5, "moderate": -0.5},
}
NOVEL_VERTICAL_MARK_STEM_FACTOR = 2 / 3


@dataclass(frozen=True)
class NovelGlyphResult:
    """Deterministically ordered, disjoint glyph names transformed in place."""

    horizontal_glyphs: tuple[str, ...]
    vertical_glyphs: tuple[str, ...]


@dataclass(frozen=True)
class _MappedGlyph:
    name: str
    group: NovelGlyphGroup
    vertical: bool
    codepoint: int | None = None
    marked: bool = False


@dataclass
class _NovelGlyphCollection:
    """Collect mappings before mutation, deduplicating aliases without hiding conflicts."""

    by_name: dict[str, _MappedGlyph] = field(default_factory=dict)

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
                raise ValueError("Novel glyph names must be non-empty strings")
            if group not in _GROUPS:
                raise ValueError(f"Unknown novel hiragana group {group!r}")

            codepoint = codepoints.get(name) if codepoints is not None else None
            base = novel_base_codepoint(codepoint) if codepoint is not None else None
            mapped = _MappedGlyph(
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
                    f"Glyph {name!r} has conflicting novel hiragana groups "
                    f"{existing.group!r} and {group!r}"
                )
            elif (
                existing.vertical
                and mapped.vertical
                and existing.codepoint is not None
                and mapped.codepoint is not None
                and novel_base_codepoint(existing.codepoint)
                != novel_base_codepoint(mapped.codepoint)
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
                self.by_name[name] = _MappedGlyph(
                    existing.name,
                    existing.group,
                    True,
                    existing.codepoint,
                    True,
                )
            # An identical cross-orientation alias has no distinct vertical outline.
            # Horizontal mappings are collected first and therefore own that outline.

    def ordered(self) -> tuple[_MappedGlyph, ...]:
        return tuple(self.by_name[name] for name in sorted(self.by_name))


def _interpolate(
    lower: NovelTransform, upper: NovelTransform, position: float
) -> NovelTransform:
    def interpolate(lower_value: float, upper_value: float) -> float:
        return lower_value + position * (upper_value - lower_value)

    # Preserve the existing fractional optical offsets; only values below a
    # quarter unit are both visually inert and unstable on dense composites.
    interpolated_stem = interpolate(lower.stem_adjustment, upper.stem_adjustment)
    stem_adjustment = (
        0 if abs(interpolated_stem) < 0.25 else round(interpolated_stem, 9)
    )
    return NovelTransform(
        interpolate(lower.sx, upper.sx),
        interpolate(lower.sy, upper.sy),
        stem_adjustment,
        interpolate(lower.dx, upper.dx),
        interpolate(lower.dy, upper.dy),
    )


def novel_base_codepoint(codepoint: int) -> int:
    """Return the base used by vertical corrections and design grouping."""
    if codepoint == NOVEL_SMALL_KO_CODEPOINT:
        return codepoint
    try:
        return ord(unicodedata.normalize("NFD", chr(codepoint))[0])
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid hiragana codepoint {codepoint!r}") from error


def novel_group_for_codepoint(codepoint: int) -> NovelGlyphGroup:
    """Classify an encoded or decomposable hiragana by its design group."""
    base = novel_base_codepoint(codepoint)
    if base in COUNTER_HIRAGANA_CODEPOINTS:
        return "counter"
    if base in SMALL_HIRAGANA_CODEPOINTS:
        return "small"
    if base in ITERATION_HIRAGANA_CODEPOINTS:
        return "iteration"
    return "normal"


def novel_vertical_stem_group(
    codepoint: int | None,
) -> NovelVerticalStemGroup | None:
    """Classify Regular relative-ink outliers into a small optical set."""
    if codepoint is None:
        return None
    base = novel_base_codepoint(codepoint)
    for stem_group, codepoints in NOVEL_VERTICAL_STEM_GROUPS.items():
        if base in codepoints:
            return stem_group
    return None


def novel_vertical_stem_adjustment(
    weight_class: int,
    codepoint: int | None,
    *,
    marked: bool = False,
) -> float:
    """Return a vertical-only stem correction with protected kana marks."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")
    stem_group = novel_vertical_stem_group(codepoint)
    if stem_group is None:
        return 0

    if weight_class in NOVEL_VERTICAL_STEM_MASTER_PROFILES:
        adjustment = NOVEL_VERTICAL_STEM_MASTER_PROFILES[weight_class][stem_group]
    else:
        lower_weight = max(
            master
            for master in NOVEL_VERTICAL_STEM_MASTER_PROFILES
            if master < weight_class
        )
        upper_weight = min(
            master
            for master in NOVEL_VERTICAL_STEM_MASTER_PROFILES
            if master > weight_class
        )
        position = (weight_class - lower_weight) / (upper_weight - lower_weight)
        lower = NOVEL_VERTICAL_STEM_MASTER_PROFILES[lower_weight][stem_group]
        upper = NOVEL_VERTICAL_STEM_MASTER_PROFILES[upper_weight][stem_group]
        adjustment = lower + position * (upper - lower)

    base = novel_base_codepoint(codepoint) if codepoint is not None else None
    if marked or (codepoint is not None and base != codepoint):
        adjustment *= NOVEL_VERTICAL_MARK_STEM_FACTOR
    return round(adjustment, 9)


def novel_transform(weight_class: int, group: NovelGlyphGroup) -> NovelTransform:
    """Return the master or linear optical interpolation for one build weight."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")
    if group not in _GROUPS:
        raise ValueError(f"Unknown novel hiragana group {group!r}")
    if weight_class in NOVEL_MASTER_PROFILES:
        return NOVEL_MASTER_PROFILES[weight_class][group]

    lower_weight = max(
        master for master in NOVEL_MASTER_PROFILES if master < weight_class
    )
    upper_weight = min(
        master for master in NOVEL_MASTER_PROFILES if master > weight_class
    )
    position = (weight_class - lower_weight) / (upper_weight - lower_weight)
    return _interpolate(
        NOVEL_MASTER_PROFILES[lower_weight][group],
        NOVEL_MASTER_PROFILES[upper_weight][group],
        position,
    )


def _interpolate_vertical(
    lower: NovelVerticalTransform,
    upper: NovelVerticalTransform,
    position: float,
) -> NovelVerticalTransform:
    def interpolate(lower_value: float, upper_value: float) -> float:
        return lower_value + position * (upper_value - lower_value)

    return NovelVerticalTransform(
        interpolate(lower.sx, upper.sx),
        interpolate(lower.sy, upper.sy),
        interpolate(lower.dx, upper.dx),
        interpolate(lower.dy, upper.dy),
        interpolate(lower.correction_strength, upper.correction_strength),
    )


def novel_vertical_transform(
    weight_class: int,
    group: NovelGlyphGroup,
    codepoint: int | None,
    *,
    marked: bool = False,
) -> NovelTransform:
    """Return the correction applied after the canonical vertical transform."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")
    if group not in _GROUPS:
        raise ValueError(f"Unknown novel hiragana group {group!r}")
    if weight_class in NOVEL_VERTICAL_MASTER_PROFILES:
        profile = NOVEL_VERTICAL_MASTER_PROFILES[weight_class][group]
    else:
        lower_weight = max(
            master for master in NOVEL_VERTICAL_MASTER_PROFILES if master < weight_class
        )
        upper_weight = min(
            master for master in NOVEL_VERTICAL_MASTER_PROFILES if master > weight_class
        )
        position = (weight_class - lower_weight) / (upper_weight - lower_weight)
        profile = _interpolate_vertical(
            NOVEL_VERTICAL_MASTER_PROFILES[lower_weight][group],
            NOVEL_VERTICAL_MASTER_PROFILES[upper_weight][group],
            position,
        )

    base = novel_base_codepoint(codepoint) if codepoint is not None else None
    height = NOVEL_VERTICAL_HEIGHT_CORRECTIONS.get(base, 1)
    width = NOVEL_VERTICAL_WIDTH_CORRECTIONS.get(base, 1)
    strength = profile.correction_strength
    return NovelTransform(
        profile.sx * (1 + (width - 1) * strength),
        profile.sy * (1 + (height - 1) * strength),
        novel_vertical_stem_adjustment(
            weight_class,
            codepoint,
            marked=marked,
        ),
        profile.dx,
        profile.dy,
    )


def _outline_transform(
    profile: NovelTransform, anchor: tuple[float, float]
) -> Transform:
    anchor_x, anchor_y = anchor
    return Transform(
        profile.sx,
        0,
        0,
        profile.sy,
        anchor_x + profile.dx - profile.sx * anchor_x,
        anchor_y + profile.dy - profile.sy * anchor_y,
    )


def transform_novel_glyph(
    font: TTFont,
    glyph_name: str,
    profile: NovelTransform,
    anchor: tuple[float, float],
    vertical_profile: NovelTransform | None = None,
    *,
    error_label: str = "novel hiragana",
) -> None:
    """Transform one outline while preserving full-width metrics and vertical origin."""
    outline = geometry.glyph_path(font, glyph_name)
    vertical_origin = 0.0
    if outline.verbs and "vmtx" in font:
        vertical_origin = font["vmtx"].metrics[glyph_name][1] + outline.bounds[3]

    transformed = geometry.transform_path(outline, _outline_transform(profile, anchor))
    try:
        transformed = geometry.adjust_outline_horizontal_weight(
            transformed, profile.stem_adjustment
        )
    except pathops.PathOpsError as error:
        raise ValueError(
            f"Could not adjust {error_label} glyph {glyph_name!r} "
            f"by {profile.stem_adjustment:g} units"
        ) from error
    if vertical_profile is not None:
        transformed = geometry.transform_path(
            transformed,
            _outline_transform(vertical_profile, anchor),
        )
        if vertical_profile.stem_adjustment:
            try:
                transformed.simplify(
                    fix_winding=True,
                    keep_starting_points=False,
                    clockwise=False,
                )
                transformed = geometry.adjust_outline_horizontal_weight(
                    transformed, vertical_profile.stem_adjustment
                )
            except (pathops.PathOpsError, ValueError) as error:
                raise ValueError(
                    f"Could not adjust vertical {error_label} glyph "
                    f"{glyph_name!r} by "
                    f"{vertical_profile.stem_adjustment:g} units"
                ) from error

    if transformed.verbs:
        operations.replace_glyph(
            font,
            glyph_name,
            transformed,
            vertical_origin,
            advance_override=1000,
        )
    else:
        _, left_side_bearing = font["hmtx"].metrics[glyph_name]
        font["hmtx"].metrics[glyph_name] = (1000, left_side_bearing)

    if "vmtx" in font:
        _, top_side_bearing = font["vmtx"].metrics[glyph_name]
        font["vmtx"].metrics[glyph_name] = (1000, top_side_bearing)


def apply_novel_hiragana(
    font: TTFont,
    weight_class: int,
    horizontal_glyphs: Mapping[str, str],
    vertical_glyphs: Mapping[str, str],
    vertical_codepoints: Mapping[str, int] | None = None,
    vertical_marked_glyphs: AbstractSet[str] = frozenset(),
) -> NovelGlyphResult:
    """Apply canonical transforms plus the vertical-only optical correction."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")

    collected = _NovelGlyphCollection()
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
        raise ValueError(f"Novel hiragana mappings contain missing glyphs: {missing!r}")

    for mapped in ordered:
        vertical_profile = (
            novel_vertical_transform(
                weight_class,
                mapped.group,
                mapped.codepoint,
                marked=mapped.marked,
            )
            if mapped.vertical
            else None
        )
        anchors = _VERTICAL_ANCHORS if mapped.vertical else _HORIZONTAL_ANCHORS
        transform_novel_glyph(
            font,
            mapped.name,
            novel_transform(weight_class, mapped.group),
            anchors[mapped.group],
            vertical_profile,
        )

    return NovelGlyphResult(
        tuple(mapped.name for mapped in ordered if not mapped.vertical),
        tuple(mapped.name for mapped in ordered if mapped.vertical),
    )


__all__ = (
    "COUNTER_HIRAGANA_CODEPOINTS",
    "HIRAGANA_CODEPOINTS",
    "ITERATION_HIRAGANA_CODEPOINTS",
    "NORMAL_HIRAGANA_CODEPOINTS",
    "NOVEL_VERTICAL_MARK_STEM_FACTOR",
    "NOVEL_VERTICAL_STEM_GROUPS",
    "NOVEL_VERTICAL_STEM_MASTER_PROFILES",
    "NOVEL_VERTICAL_HEIGHT_CORRECTIONS",
    "NOVEL_VERTICAL_MASTER_PROFILES",
    "NOVEL_VERTICAL_WIDTH_CORRECTIONS",
    "NOVEL_MASTER_PROFILES",
    "NOVEL_SMALL_KO_CODEPOINT",
    "NovelGlyphGroup",
    "NovelGlyphResult",
    "NovelTransform",
    "NovelVerticalTransform",
    "NovelVerticalStemGroup",
    "SMALL_HIRAGANA_CODEPOINTS",
    "apply_novel_hiragana",
    "novel_base_codepoint",
    "novel_vertical_stem_adjustment",
    "novel_vertical_stem_group",
    "novel_vertical_transform",
    "novel_transform",
    "novel_group_for_codepoint",
    "transform_novel_glyph",
)
