"""Same-weight Noto Serif JP derivation for the novel hiragana family.

Anisotropic anchor scaling retains the source gesture and counters; restrained
pathops stem adjustment and position shifts refine it without a second geometry
convention. Full-width advances and source vertical origins remain invariant.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import AbstractSet, Literal, TypeAlias

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
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
NOVEL_KA_CODEPOINT = ord("か")
NOVEL_KA_TERMINAL_MASTER_RAISES: Mapping[int, float] = {
    200: 32,
    400: 36,
    900: 44,
}
_KA_TERMINAL_AXIS_SAMPLE_RISE = 90
_KA_TERMINAL_FULL_PROJECTION = 90
_KA_TERMINAL_FADE_PROJECTION = 280
_KA_TERMINAL_COMPANION_CLEARANCE = 16
_KA_TERMINAL_FADE_HANDLE_RATIO = 0.22
_KA_TERMINAL_MIN_Y_TOLERANCE = 0.001
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


def novel_ka_terminal_raise(weight_class: int) -> float:
    """Return the interpolated upward correction for the second-stroke terminal."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")
    if weight_class in NOVEL_KA_TERMINAL_MASTER_RAISES:
        return NOVEL_KA_TERMINAL_MASTER_RAISES[weight_class]

    lower_weight = max(
        master for master in NOVEL_KA_TERMINAL_MASTER_RAISES if master < weight_class
    )
    upper_weight = min(
        master for master in NOVEL_KA_TERMINAL_MASTER_RAISES if master > weight_class
    )
    position = (weight_class - lower_weight) / (upper_weight - lower_weight)
    lower = NOVEL_KA_TERMINAL_MASTER_RAISES[lower_weight]
    upper = NOVEL_KA_TERMINAL_MASTER_RAISES[upper_weight]
    return lower + position * (upper - lower)


def _smootherstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * value * (value * (value * 6 - 15) + 10)


@dataclass(frozen=True)
class _KaTerminalArc:
    contour_index: int
    strengths: dict[int, float]
    translation: tuple[float, float]
    centerline_origin: tuple[float, float]
    axis_unit: tuple[float, float]
    companion_lateral_limit: float
    omitted_contours: frozenset[int]

    def companion_strength(self, point: tuple[float, float]) -> float:
        """Return the deformation shared by a separate overlap-seam contour."""
        delta_x = point[0] - self.centerline_origin[0]
        delta_y = point[1] - self.centerline_origin[1]
        axial_projection = (
            delta_x * self.axis_unit[0] + delta_y * self.axis_unit[1]
        ) * self.axis_unit[1]
        lateral_distance = abs(
            delta_x * self.axis_unit[1] - delta_y * self.axis_unit[0]
        )
        if (
            axial_projection >= _KA_TERMINAL_FADE_PROJECTION
            or lateral_distance > self.companion_lateral_limit
        ):
            return 0
        return _smootherstep(
            (_KA_TERMINAL_FADE_PROJECTION - axial_projection)
            / (_KA_TERMINAL_FADE_PROJECTION - _KA_TERMINAL_FULL_PROJECTION)
        )


@dataclass
class _TransformedCommand:
    operator: str
    operands: tuple[tuple[float, float], ...]
    contour_index: int
    point_indices: tuple[int, ...]


def _round_terminal_path_for_cff(outline: pathops.Path) -> pathops.Path:
    """Match reachable Type 2 topology before computing local arc strengths."""
    type_2_pen = T2CharStringPen(1000, None)
    outline.draw(type_2_pen)
    private = SimpleNamespace(nominalWidthX=0, defaultWidthX=1000, Subrs=[])
    char_string = type_2_pen.getCharString(private=private, globalSubrs=[])
    recording = RecordingPen()
    char_string.draw(recording)
    rounded = pathops.Path()
    pen = rounded.getPen()
    for operator, operands in recording.value:
        getattr(pen, operator)(*operands)
    return rounded


def _ka_terminal_arc(outline: pathops.Path, amount: float) -> _KaTerminalArc:
    """Select only the connected boundary arc surrounding the lower-left cap."""
    contours = tuple(outline.contours)
    contour_index = min(
        range(len(contours)),
        key=lambda index: contours[index].bounds[1],
    )
    points = tuple(contours[contour_index].points)
    minimum_y = min(y for _, y in points)
    minimum_indices = frozenset(
        index
        for index, (_, y) in enumerate(points)
        if y <= minimum_y + _KA_TERMINAL_MIN_Y_TOLERANCE
    )
    cap_starts = tuple(
        index
        for index in minimum_indices
        if (index - 1) % len(points) not in minimum_indices
    )
    cap_ends = tuple(
        index
        for index in minimum_indices
        if (index + 1) % len(points) not in minimum_indices
    )
    if len(cap_starts) != 1 or len(cap_ends) != 1:
        raise ValueError("Novel ka terminal cap is not one connected boundary arc")
    cap_start = cap_starts[0]
    cap_end = cap_ends[0]
    cap_points = tuple(points[index] for index in minimum_indices)
    cap_center = (
        sum(x for x, _ in cap_points) / len(cap_points),
        sum(y for _, y in cap_points) / len(cap_points),
    )

    def axis_sample(direction: int, start: int) -> tuple[float, float]:
        index = start
        for _ in points:
            point = points[index]
            if point[1] >= minimum_y + _KA_TERMINAL_AXIS_SAMPLE_RISE:
                return point
            index = (index + direction) % len(points)
        raise ValueError("Novel ka terminal side has no centerline sample")

    negative_sample = axis_sample(-1, (cap_start - 1) % len(points))
    positive_sample = axis_sample(1, (cap_end + 1) % len(points))
    sample_midpoint = (
        (negative_sample[0] + positive_sample[0]) / 2,
        (negative_sample[1] + positive_sample[1]) / 2,
    )
    axis = (
        sample_midpoint[0] - cap_center[0],
        sample_midpoint[1] - cap_center[1],
    )
    axis_length = math.hypot(*axis)
    if not axis_length:
        raise ValueError("Novel ka terminal centerline has zero length")
    axis_unit = (axis[0] / axis_length, axis[1] / axis_length)
    if axis_unit[1] <= 0.75 or abs(axis_unit[0]) >= 0.66:
        raise ValueError(
            f"Novel ka terminal centerline is outside its design corridor: {axis_unit!r}"
        )
    translation = (
        amount * axis_unit[0] / axis_unit[1],
        amount,
    )

    def axial_projection(point: tuple[float, float]) -> float:
        delta_x = point[0] - cap_center[0]
        delta_y = point[1] - cap_center[1]
        return (delta_x * axis_unit[0] + delta_y * axis_unit[1]) * axis_unit[1]

    strengths = {index: 1.0 for index in minimum_indices}
    for direction, start in (
        (-1, (cap_start - 1) % len(points)),
        (1, (cap_end + 1) % len(points)),
    ):
        index = start
        for _ in points:
            projection = axial_projection(points[index])
            if projection >= _KA_TERMINAL_FADE_PROJECTION:
                break
            if index in strengths:
                raise ValueError("Novel ka terminal boundary arc overlaps itself")
            strengths[index] = _smootherstep(
                (_KA_TERMINAL_FADE_PROJECTION - projection)
                / (_KA_TERMINAL_FADE_PROJECTION - _KA_TERMINAL_FULL_PROJECTION)
            )
            index = (index + direction) % len(points)
        else:
            raise ValueError("Novel ka terminal boundary arc has no fade endpoint")

    companion_lateral_limit = (
        max(
            abs(
                (points[index][0] - cap_center[0]) * axis_unit[1]
                - (points[index][1] - cap_center[1]) * axis_unit[0]
            )
            for index in strengths
        )
        + _KA_TERMINAL_COMPANION_CLEARANCE
    )
    candidate = _KaTerminalArc(
        contour_index,
        strengths,
        translation,
        cap_center,
        axis_unit,
        companion_lateral_limit,
        frozenset(),
    )
    omitted_contours = frozenset(
        index
        for index, contour in enumerate(contours)
        if index != contour_index
        and contour.clockwise
        and any(candidate.companion_strength(point) for point in contour.points)
    )
    return _KaTerminalArc(
        contour_index,
        strengths,
        translation,
        cap_center,
        axis_unit,
        companion_lateral_limit,
        omitted_contours,
    )


def _smooth_ka_terminal_fade_lines(
    commands: list[_TransformedCommand],
    arc: _KaTerminalArc,
) -> None:
    """Replace fade-crossing line joins with tangent-continuous curves."""
    for index, command in enumerate(commands):
        if (
            command.contour_index != arc.contour_index
            or command.operator != "lineTo"
            or len(command.operands) != 1
            or index < 2
            or index + 1 >= len(commands)
        ):
            continue
        previous = commands[index - 1]
        following = commands[index + 1]
        if (
            previous.contour_index != command.contour_index
            or following.contour_index != command.contour_index
            or not previous.point_indices
            or not command.point_indices
        ):
            continue
        start_strength = arc.strengths.get(previous.point_indices[-1], 0)
        end_strength = arc.strengths.get(command.point_indices[-1], 0)
        if (start_strength == 0) == (end_strength == 0):
            continue

        if previous.operator == "curveTo":
            incoming_origin = previous.operands[-2]
        elif previous.operator == "lineTo":
            incoming_origin = commands[index - 2].operands[-1]
        else:
            continue
        if following.operator == "curveTo":
            outgoing_target = following.operands[0]
        elif following.operator == "lineTo":
            outgoing_target = following.operands[-1]
        else:
            continue

        start = previous.operands[-1]
        end = command.operands[-1]
        incoming = (start[0] - incoming_origin[0], start[1] - incoming_origin[1])
        outgoing = (outgoing_target[0] - end[0], outgoing_target[1] - end[1])
        incoming_length = math.hypot(*incoming)
        outgoing_length = math.hypot(*outgoing)
        if not incoming_length or not outgoing_length:
            continue
        handle_length = math.dist(start, end) * _KA_TERMINAL_FADE_HANDLE_RATIO
        first_control = (
            start[0] + incoming[0] / incoming_length * handle_length,
            start[1] + incoming[1] / incoming_length * handle_length,
        )
        second_control = (
            end[0] - outgoing[0] / outgoing_length * handle_length,
            end[1] - outgoing[1] / outgoing_length * handle_length,
        )
        command.operator = "curveTo"
        command.operands = (first_control, second_control, end)


def shorten_novel_ka_terminal(
    outline: pathops.Path,
    amount: float,
) -> pathops.Path:
    """Shorten only the connected second-stroke terminal along its centerline."""
    if amount < 0:
        raise ValueError("Novel ka terminal correction must not be negative")
    if not outline.verbs or amount == 0:
        return outline

    arc = _ka_terminal_arc(outline, amount)
    recording = RecordingPen()
    outline.draw(recording)
    commands: list[_TransformedCommand] = []
    contour_index = -1
    local_index = 0
    for operator, operands in recording.value:
        if operator == "moveTo":
            contour_index += 1
            local_index = 0
        point_indices = tuple(range(local_index, local_index + len(operands)))
        if contour_index in arc.omitted_contours:
            continue
        transformed = []
        for point in operands:
            if contour_index == arc.contour_index:
                strength = arc.strengths.get(local_index, 0)
            else:
                strength = arc.companion_strength(point)
            transformed.append(
                (
                    point[0] + arc.translation[0] * strength,
                    point[1] + arc.translation[1] * strength,
                )
            )
            local_index += 1
        commands.append(
            _TransformedCommand(
                operator,
                tuple(transformed),
                contour_index,
                point_indices,
            )
        )

    _smooth_ka_terminal_fade_lines(commands, arc)
    shortened = pathops.Path()
    pen = shortened.getPen()
    for command in commands:
        getattr(pen, command.operator)(*command.operands)
    return shortened


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
    terminal_raise: float = 0,
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

    terminal_left_side_bearing = (
        math.floor(transformed.bounds[0])
        if terminal_raise and transformed.verbs
        else None
    )
    terminal_top_side_bearing = (
        math.floor(vertical_origin - transformed.bounds[3])
        if terminal_raise and transformed.verbs and "vmtx" in font
        else None
    )

    if terminal_raise:
        if "CFF " in font:
            transformed = _round_terminal_path_for_cff(transformed)
        try:
            transformed = shorten_novel_ka_terminal(transformed, terminal_raise)
        except ValueError as error:
            raise ValueError(
                f"Could not correct novel ka terminal glyph {glyph_name!r}"
            ) from error

    if transformed.verbs:
        operations.replace_glyph(
            font,
            glyph_name,
            transformed,
            vertical_origin,
            advance_override=1000,
            left_side_bearing_override=terminal_left_side_bearing,
        )
    else:
        _, left_side_bearing = font["hmtx"].metrics[glyph_name]
        font["hmtx"].metrics[glyph_name] = (1000, left_side_bearing)

    if "vmtx" in font:
        if terminal_top_side_bearing is None:
            _, top_side_bearing = font["vmtx"].metrics[glyph_name]
        else:
            top_side_bearing = terminal_top_side_bearing
        font["vmtx"].metrics[glyph_name] = (1000, top_side_bearing)


def apply_novel_hiragana(
    font: TTFont,
    weight_class: int,
    horizontal_glyphs: Mapping[str, str],
    vertical_glyphs: Mapping[str, str],
    vertical_codepoints: Mapping[str, int] | None = None,
    vertical_marked_glyphs: AbstractSet[str] = frozenset(),
    horizontal_codepoints: Mapping[str, int] | None = None,
) -> NovelGlyphResult:
    """Apply canonical transforms plus the vertical-only optical correction."""
    if weight_class not in _WEIGHT_CLASSES:
        raise ValueError(f"Unsupported novel hiragana weight class {weight_class!r}")

    collected = _NovelGlyphCollection()
    collected.add(
        horizontal_glyphs,
        vertical=False,
        codepoints=horizontal_codepoints,
    )
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
        base_codepoint = (
            novel_base_codepoint(mapped.codepoint)
            if mapped.codepoint is not None
            else None
        )
        anchors = _VERTICAL_ANCHORS if mapped.vertical else _HORIZONTAL_ANCHORS
        transform_novel_glyph(
            font,
            mapped.name,
            novel_transform(weight_class, mapped.group),
            anchors[mapped.group],
            vertical_profile,
            terminal_raise=(
                novel_ka_terminal_raise(weight_class)
                if base_codepoint == NOVEL_KA_CODEPOINT
                else 0
            ),
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
    "NOVEL_KA_CODEPOINT",
    "NOVEL_KA_TERMINAL_MASTER_RAISES",
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
    "novel_ka_terminal_raise",
    "novel_vertical_stem_adjustment",
    "novel_vertical_stem_group",
    "novel_vertical_transform",
    "novel_transform",
    "novel_group_for_codepoint",
    "shorten_novel_ka_terminal",
    "transform_novel_glyph",
)
