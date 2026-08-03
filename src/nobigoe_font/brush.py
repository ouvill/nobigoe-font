"""Optional calligraphic stroke flow for Noto-derived Han outlines."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Literal, TypeAlias, cast

import pathops
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from . import geometry, operations
from .novel_han import collect_novel_han_glyphs

Point: TypeAlias = tuple[float, float]
Command: TypeAlias = tuple[str, tuple[Point, ...]]

_MIN_SIDE_LENGTH = 140.0
_MIN_SIDE_SLOPE = 0.5
_MAX_PARALLEL_DOT = -0.94
_MIN_STROKE_WIDTH = 20.0
_MAX_STROKE_WIDTH = 180.0
_MIN_AXIS_OVERLAP_RATIO = 0.7
_GEOMETRY_EPSILON = 1e-9
_MIN_TERMINAL_CAP_LENGTH = 8.0
_MAX_TERMINAL_CAP_LENGTH = 40.0
_MIN_TERMINAL_CURVE_SPAN = 50.0
_MAX_TERMINAL_TANGENT_DOT = -0.55
_MAX_RIGHT_SWEEP_SHORT_TO_LONG_RATIO = 0.35
_MAX_RIGHT_SWEEP_CAP_TO_SHORT_SIDE_RATIO = 0.35
_MIN_CLOSED_DOT_SIDE_TO_CAP_RATIO = 10.0
_MIN_HOOK_OUTWARD_HORIZONTAL_RATIO = 0.75
_MAX_HOOK_BASIS_DOT = 0.05
_MAX_HORIZONTAL_STROKE_WIDTH = 80.0
_HORIZONTAL_START_REFERENCE_WIDTH = 33.0
_SILVER_RATIO = math.sqrt(2.0)


@dataclass(frozen=True)
class BrushElementStyle:
    """Editable proportions for matched curved terminal elements."""

    left_sweep_rounding_ratio: float = 0.06
    right_sweep_incoming_ratio: float = 0.20
    right_sweep_outgoing_ratio: float = 0.022
    hook_rounding_ratio: float = 0.03


DEFAULT_BRUSH_ELEMENT_STYLE = BrushElementStyle()


@dataclass(frozen=True)
class BrushElementResult:
    """A copied outline and the number of edited brush elements."""

    path: pathops.Path
    adjusted_stroke_count: int
    adjusted_uroko_count: int
    adjusted_terminal_count: int
    adjusted_corner_count: int

    @property
    def adjusted_element_count(self) -> int:
        return (
            self.adjusted_stroke_count
            + self.adjusted_uroko_count
            + self.adjusted_terminal_count
            + self.adjusted_corner_count
        )


@dataclass(frozen=True)
class HanBrushResult:
    """Summary of Han outlines changed in one static font."""

    target_count: int
    modified_count: int
    adjusted_stroke_count: int
    adjusted_uroko_count: int
    adjusted_terminal_count: int
    adjusted_corner_count: int


TerminalRole: TypeAlias = Literal["left-sweep", "right-sweep", "hook", "closed-dot"]


@dataclass(frozen=True)
class _LineSide:
    command_index: int
    start: Point
    end: Point
    direction: Point
    length: float


@dataclass(frozen=True)
class _StrokePair:
    width: float
    left: _LineSide
    right: _LineSide
    axis: Point
    leftward: Point
    overlap_ratio: float


@dataclass(frozen=True)
class _UrokoElement:
    preceding_line_index: int
    first_curve_index: int
    second_curve_index: int
    following_line_index: int
    contour_move_index: int | None
    start: Point
    tip: Point
    end: Point
    lower_join: Point


@dataclass(frozen=True)
class _HorizontalStartElement:
    incoming_line_index: int
    cap_line_index: int
    outgoing_line_index: int
    incoming_start: Point
    cap_start: Point
    cap_end: Point
    outgoing_end: Point
    axis: Point
    incoming_outward: Point
    width: float


@dataclass(frozen=True)
class _VerticalStartElement:
    first_cap_index: int
    cap_command_count: int
    contour_move_index: int | None
    post_move_cap_count: int
    down_side: _LineSide
    up_side: _LineSide
    axis: Point
    across: Point
    width: float

    @property
    def side_command_indices(self) -> frozenset[int]:
        return frozenset((self.down_side.command_index, self.up_side.command_index))


@dataclass(frozen=True)
class _VerticalEndElement:
    first_cap_index: int
    cap_command_count: int
    down_side: _LineSide
    up_side: _LineSide
    axis: Point
    across: Point
    width: float

    @property
    def side_command_indices(self) -> frozenset[int]:
        return frozenset((self.down_side.command_index, self.up_side.command_index))


@dataclass(frozen=True)
class _VerticalStartDesign:
    left_apex: Point
    left_first_control: Point
    left_second_control: Point
    left_body: Point
    right_top: Point
    shoulder: Point
    cap_first_control: Point
    cap_second_control: Point


@dataclass(frozen=True)
class _VerticalEndDesign:
    left_body: Point
    left_first_control: Point
    left_second_control: Point
    left_bottom: Point
    first_cap_first_control: Point
    first_cap_second_control: Point
    first_cap_end: Point
    second_cap_first_control: Point
    second_cap_second_control: Point
    right_bottom: Point
    right_first_control: Point
    right_second_control: Point
    right_body: Point


@dataclass(frozen=True)
class _LeftSweepStartElement:
    contour_move_index: int
    contour_close_index: int
    first_curve_index: int
    inner_curve_index: int
    shoulder_curve_index: int
    outer_top: Point
    outer_join: Point
    inner_join: Point
    inner_top: Point

    @property
    def command_indices(self) -> frozenset[int]:
        return frozenset(range(self.contour_move_index, self.contour_close_index + 1))


@dataclass(frozen=True)
class _FoldElement:
    incoming_curve_index: int
    first_line_index: int
    second_line_index: int
    horizontal_line_index: int
    incoming_start: Point
    outer: Point
    apex: Point
    base: Point
    horizontal_end: Point


@dataclass(frozen=True)
class _BoxLeftCandidate:
    contour_start: int
    contour_end: int
    top_horizontal_index: int
    top_corner_index: int
    side_index: int
    bottom_line_index: int
    bottom_curve_index: int
    side_start: Point
    top_inner: Point
    outer_top: Point
    outer_bottom: Point
    inner_bottom: Point
    axis: Point
    across: Point
    width: float

    @property
    def command_indices(self) -> frozenset[int]:
        indices = {
            self.top_horizontal_index,
            self.top_corner_index,
            self.side_index,
            self.bottom_line_index,
            self.bottom_curve_index,
        }
        if self.top_corner_index > self.side_index:
            indices.add(self.contour_start)
        if self.bottom_curve_index == self.contour_end - 1:
            indices.add(self.contour_start)
        return frozenset(indices)


@dataclass(frozen=True)
class _BoxRightCandidate:
    contour_start: int
    contour_end: int
    bottom_horizontal_index: int
    inner_side_index: int
    bottom_line_index: int
    bottom_curve_index: int
    outer_side_index: int
    inner_top: Point
    inner_bottom: Point
    outer_bottom: Point
    outer_top: Point
    axis: Point
    across: Point
    width: float

    @property
    def command_indices(self) -> frozenset[int]:
        return frozenset(
            (
                self.inner_side_index,
                self.bottom_line_index,
                self.bottom_curve_index,
                self.outer_side_index,
            )
        )


@dataclass(frozen=True)
class _BoxElement:
    left: _BoxLeftCandidate
    right: _BoxRightCandidate

    @property
    def command_indices(self) -> frozenset[int]:
        return self.left.command_indices | self.right.command_indices


@dataclass(frozen=True)
class _TerminalElement:
    incoming_curve_index: int
    cap_line_index: int
    outgoing_curve_index: int
    start: Point
    cap_start: Point
    cap_end: Point
    end: Point
    role: TerminalRole
    outgoing_curve_count: int = 1


@dataclass(frozen=True)
class _TerminalGeometry:
    start: Point
    cap_start: Point
    cap_end: Point
    end: Point
    incoming_span: float
    outgoing_span: float
    cap_length: float
    incoming_direction: Point
    outgoing_direction: Point


@dataclass(frozen=True)
class _CommandEdit:
    """A localized edit produced by a geometric element matcher.

    Replacing zero source commands inserts commands; an empty replacement
    deletes commands. Matchers create these indices for each outline rather
    than persisting glyph-specific point numbers.
    """

    command_index: int
    delete_count: int
    replacement: tuple[Command, ...]


def _subtract(left: Point, right: Point) -> Point:
    return left[0] - right[0], left[1] - right[1]


def _add(left: Point, right: Point) -> Point:
    return left[0] + right[0], left[1] + right[1]


def _scale(point: Point, factor: float) -> Point:
    return point[0] * factor, point[1] * factor


def _dot(left: Point, right: Point) -> float:
    return left[0] * right[0] + left[1] * right[1]


def _lerp(start: Point, end: Point, factor: float) -> Point:
    return _add(start, _scale(_subtract(end, start), factor))


def _unit(vector: Point) -> Point | None:
    length = math.hypot(*vector)
    if not math.isfinite(length) or length <= _GEOMETRY_EPSILON:
        return None
    return vector[0] / length, vector[1] / length


def _first_unit(*vectors: Point) -> Point | None:
    for vector in vectors:
        if (direction := _unit(vector)) is not None:
            return direction
    return None


def _midpoint(first: Point, second: Point) -> Point:
    return (first[0] + second[0]) / 2, (first[1] + second[1]) / 2


def _split_cubic(
    start: Point,
    first: Point,
    second: Point,
    end: Point,
    factor: float,
) -> tuple[
    tuple[Point, Point, Point, Point],
    tuple[Point, Point, Point, Point],
]:
    start_first = _lerp(start, first, factor)
    first_second = _lerp(first, second, factor)
    second_end = _lerp(second, end, factor)
    left_second = _lerp(start_first, first_second, factor)
    right_first = _lerp(first_second, second_end, factor)
    split = _lerp(left_second, right_first, factor)
    return (
        (start, start_first, left_second, split),
        (split, right_first, second_end, end),
    )


def _contour_ranges(commands: list[Command]) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, (operator, _) in enumerate(commands):
        if operator == "moveTo":
            start = index
        elif operator in {"closePath", "endPath"} and start is not None:
            ranges.append((start, index))
            start = None
    return tuple(ranges)


def _axis_interval(side: _LineSide, axis: Point) -> tuple[float, float]:
    low, high = sorted((_dot(side.start, axis), _dot(side.end, axis)))
    return low, high


def _stroke_pair(
    first: _LineSide,
    second: _LineSide,
    *,
    min_aspect_ratio: float,
) -> _StrokePair | None:
    if _dot(first.direction, second.direction) > _MAX_PARALLEL_DOT:
        return None
    axis = first.direction
    if axis[1] > 0:
        axis = _scale(axis, -1)
    leftward = (axis[1], -axis[0])
    first_middle = _midpoint(first.start, first.end)
    second_middle = _midpoint(second.start, second.end)
    width = abs(_dot(_subtract(first_middle, second_middle), leftward))
    if not _MIN_STROKE_WIDTH <= width <= _MAX_STROKE_WIDTH:
        return None
    if min(first.length, second.length) < min_aspect_ratio * width:
        return None
    first_low, first_high = _axis_interval(first, axis)
    second_low, second_high = _axis_interval(second, axis)
    overlap = max(0.0, min(first_high, second_high) - max(first_low, second_low))
    shorter_span = min(first_high - first_low, second_high - second_low)
    if shorter_span <= _GEOMETRY_EPSILON:
        return None
    overlap_ratio = overlap / shorter_span
    if overlap_ratio < _MIN_AXIS_OVERLAP_RATIO:
        return None
    if _dot(first_middle, leftward) >= _dot(second_middle, leftward):
        left, right = first, second
    else:
        left, right = second, first
    return _StrokePair(width, left, right, axis, leftward, overlap_ratio)


def _vertical_start_command_indices(
    element: _VerticalStartElement,
) -> frozenset[int]:
    indices = set(element.side_command_indices)
    indices.update(
        range(
            element.first_cap_index,
            element.first_cap_index + element.cap_command_count,
        )
    )
    if element.contour_move_index is not None:
        indices.add(element.contour_move_index)
        indices.update(
            range(
                element.contour_move_index + 1,
                element.contour_move_index + 1 + element.post_move_cap_count,
            )
        )
    return frozenset(indices)


def _terminal_command_indices(element: _TerminalElement) -> frozenset[int]:
    return frozenset(
        (
            element.incoming_curve_index,
            element.cap_line_index,
            *range(
                element.outgoing_curve_index,
                element.outgoing_curve_index + element.outgoing_curve_count,
            ),
        )
    )


def _supported_start_terminal_overlap(
    commands: list[Command],
    start: _VerticalStartElement,
    terminal: _TerminalElement,
) -> bool:
    intersection = _vertical_start_command_indices(start).intersection(
        _terminal_command_indices(terminal)
    )
    return intersection == frozenset((start.down_side.command_index,)) and (
        start.down_side.command_index == terminal.incoming_curve_index
        and commands[start.down_side.command_index][0] == "curveTo"
        and terminal.role != "hook"
        and terminal.incoming_curve_index + 1 == terminal.cap_line_index
    )


_VERTICAL_REFERENCE_WIDTH = 68.0


def _vertical_design_point(
    anchor: Point,
    axis: Point,
    across: Point,
    width: float,
    across_units: float,
    down_units: float,
    axial_scale: float,
) -> Point:
    unit_scale = width / _VERTICAL_REFERENCE_WIDTH
    return _add(
        _add(anchor, _scale(across, across_units * unit_scale)),
        _scale(axis, down_units * unit_scale * axial_scale),
    )


def _vertical_design_scales(
    start: _VerticalStartElement | None,
    end: _VerticalEndElement | None,
) -> tuple[float, float]:
    element = start if start is not None else end
    if element is None:
        raise ValueError("Vertical design needs a start or end element")
    unit_scale = element.width / _VERTICAL_REFERENCE_WIDTH

    # Keep a visible straight body between an exposed endpoint treatment and
    # the next contour junction.  A fixed percentage alone leaves almost no
    # stem on short components and when start and end share the same sides.
    def available_design_span(side: _LineSide) -> float:
        straight_body = min(element.width, 0.25 * side.length)
        return max(0.0, side.length - straight_body)

    start_scale = (
        min(
            1.0,
            available_design_span(element.down_side) / (200.0 * unit_scale),
            available_design_span(element.up_side) / (20.0 * unit_scale),
        )
        if start is not None
        else 0.0
    )
    end_scale = (
        min(
            1.0,
            available_design_span(element.down_side) / (280.0 * unit_scale),
            available_design_span(element.up_side) / (240.0 * unit_scale),
        )
        if end is not None
        else 0.0
    )
    if start is not None and end is not None:
        joint_scale = min(
            1.0,
            available_design_span(element.down_side) / (480.0 * unit_scale),
            available_design_span(element.up_side) / (260.0 * unit_scale),
        )
        start_scale = min(start_scale, joint_scale)
        end_scale = min(end_scale, joint_scale)
    return start_scale, end_scale


def _vertical_start_design(
    element: _VerticalStartElement,
    axial_scale: float,
) -> _VerticalStartDesign:
    # Source-space offsets reproduce the selected Genryu-based B recipe for
    # Noto Serif JP U+4E28, normalized by its 68-unit source stem width.
    def point(
        anchor: Point,
        across: float,
        down: float,
    ) -> Point:
        return _vertical_design_point(
            anchor,
            element.axis,
            element.across,
            element.width,
            across,
            down,
            axial_scale,
        )

    left_anchor = element.down_side.start
    right_anchor = element.up_side.end
    return _VerticalStartDesign(
        left_apex=point(left_anchor, -11, -5),
        left_first_control=point(left_anchor, -2, 50),
        left_second_control=point(left_anchor, 2, 134),
        left_body=point(left_anchor, 2, 200),
        right_top=point(right_anchor, -1, 20),
        shoulder=point(right_anchor, 16, 9),
        cap_first_control=point(right_anchor, 34, -3),
        cap_second_control=point(right_anchor, 34, -13),
    )


def _vertical_end_design(
    element: _VerticalEndElement,
    axial_scale: float,
) -> _VerticalEndDesign:
    def point(
        anchor: Point,
        across: float,
        down: float,
    ) -> Point:
        return _vertical_design_point(
            anchor,
            element.axis,
            element.across,
            element.width,
            across,
            down,
            axial_scale,
        )

    left_anchor = element.down_side.end
    right_anchor = element.up_side.start
    return _VerticalEndDesign(
        left_body=point(left_anchor, 2, -280),
        left_first_control=point(left_anchor, 0, -150),
        left_second_control=point(left_anchor, -3, -106),
        left_bottom=point(left_anchor, -9, -20),
        first_cap_first_control=point(left_anchor, -9, -10),
        first_cap_second_control=point(left_anchor, 2, 0),
        first_cap_end=point(left_anchor, 15, 0),
        second_cap_first_control=point(left_anchor, 39, 0),
        second_cap_second_control=point(right_anchor, -1, 11),
        right_bottom=point(right_anchor, 7, -5),
        right_first_control=point(right_anchor, 3, -80),
        right_second_control=point(right_anchor, 1, -120),
        right_body=point(right_anchor, -1, -240),
    )


def _vertical_stroke_side_edits(
    element: _VerticalStartElement | _VerticalEndElement,
    start_design: _VerticalStartDesign | None,
    end_design: _VerticalEndDesign | None,
    commands: list[Command],
) -> tuple[_CommandEdit, _CommandEdit]:
    down_operator, down_operands = commands[element.down_side.command_index]
    up_operator, up_operands = commands[element.up_side.command_index]

    down_replacement: list[Command] = []
    preserved_down_curve = False
    if start_design is not None:
        down_replacement.append(
            (
                "curveTo",
                (
                    start_design.left_first_control,
                    start_design.left_second_control,
                    start_design.left_body,
                ),
            )
        )
        down_current = start_design.left_body
        if down_operator == "curveTo" and end_design is None:
            target_depth = max(
                0.0,
                _dot(
                    _subtract(start_design.left_body, element.down_side.start),
                    element.axis,
                ),
            )
            lower = 0.0
            upper = 0.5
            for _ in range(24):
                factor = (lower + upper) / 2
                split_point = _split_cubic(
                    element.down_side.start,
                    down_operands[0],
                    down_operands[1],
                    down_operands[2],
                    factor,
                )[0][-1]
                depth = _dot(
                    _subtract(split_point, element.down_side.start),
                    element.axis,
                )
                if depth < target_depth:
                    lower = factor
                else:
                    upper = factor
            _, preserved = _split_cubic(
                element.down_side.start,
                down_operands[0],
                down_operands[1],
                down_operands[2],
                (lower + upper) / 2,
            )
            join_offset = _subtract(start_design.left_body, preserved[0])
            down_replacement.append(
                (
                    "curveTo",
                    (
                        _add(preserved[1], join_offset),
                        preserved[2],
                        preserved[3],
                    ),
                )
            )
            down_current = preserved[3]
            preserved_down_curve = True
    else:
        down_current = element.down_side.start
    if end_design is not None:
        if math.dist(down_current, end_design.left_body) > _GEOMETRY_EPSILON:
            down_replacement.append(("lineTo", (end_design.left_body,)))
        down_replacement.append(
            (
                "curveTo",
                (
                    end_design.left_first_control,
                    end_design.left_second_control,
                    end_design.left_bottom,
                ),
            )
        )
    elif (
        not preserved_down_curve
        and math.dist(down_current, element.down_side.end) > _GEOMETRY_EPSILON
    ):
        down_replacement.append(("lineTo", (element.down_side.end,)))

    up_replacement: list[Command] = []
    if up_operator == "curveTo" and start_design is not None and end_design is None:
        endpoint_offset = _subtract(start_design.right_top, up_operands[2])
        up_replacement.append(
            (
                "curveTo",
                (
                    up_operands[0],
                    _add(up_operands[1], endpoint_offset),
                    start_design.right_top,
                ),
            )
        )
    else:
        if end_design is not None:
            up_replacement.append(
                (
                    "curveTo",
                    (
                        end_design.right_first_control,
                        end_design.right_second_control,
                        end_design.right_body,
                    ),
                )
            )
            up_current = end_design.right_body
        else:
            up_current = element.up_side.start
        up_target = (
            start_design.right_top if start_design is not None else element.up_side.end
        )
        if math.dist(up_current, up_target) > _GEOMETRY_EPSILON:
            up_replacement.append(("lineTo", (up_target,)))

    return (
        _CommandEdit(
            element.down_side.command_index,
            1,
            tuple(down_replacement),
        ),
        _CommandEdit(
            element.up_side.command_index,
            1,
            tuple(up_replacement),
        ),
    )


def _edit_vertical_start_cap(
    design: _VerticalStartDesign,
) -> tuple[Command, ...]:
    return (
        ("lineTo", (design.shoulder,)),
        (
            "curveTo",
            (
                design.cap_first_control,
                design.cap_second_control,
                design.left_apex,
            ),
        ),
    )


def _edit_vertical_end_cap(
    design: _VerticalEndDesign,
) -> tuple[Command, ...]:
    return (
        (
            "curveTo",
            (
                design.first_cap_first_control,
                design.first_cap_second_control,
                design.first_cap_end,
            ),
        ),
        (
            "curveTo",
            (
                design.second_cap_first_control,
                design.second_cap_second_control,
                design.right_bottom,
            ),
        ),
    )


def _command_starts(commands: list[Command]) -> tuple[Point | None, ...]:
    starts: list[Point | None] = []
    current: Point | None = None
    contour_start: Point | None = None
    for operator, operands in commands:
        starts.append(current)
        if operator == "moveTo":
            current = operands[-1]
            contour_start = current
        elif operator in {"lineTo", "curveTo"}:
            current = operands[-1]
        elif operator == "closePath":
            current = contour_start
    return tuple(starts)


def _match_horizontal_start(
    incoming_line_index: int,
    cap_line_index: int,
    outgoing_line_index: int,
    incoming_start: Point,
    cap_start: Point,
    cap_end: Point,
    outgoing_end: Point,
) -> _HorizontalStartElement | None:
    incoming_vector = _subtract(cap_start, incoming_start)
    outgoing_vector = _subtract(outgoing_end, cap_end)
    incoming_direction = _unit(incoming_vector)
    outgoing_direction = _unit(outgoing_vector)
    if (
        incoming_direction is None
        or outgoing_direction is None
        or math.hypot(*incoming_vector) < _MIN_SIDE_LENGTH
        or math.hypot(*outgoing_vector) < _MIN_SIDE_LENGTH
        or incoming_direction[0] >= -0.95
        or outgoing_direction[0] <= 0.95
        or _dot(incoming_direction, outgoing_direction) > _MAX_PARALLEL_DOT
    ):
        return None
    normal = (-outgoing_direction[1], outgoing_direction[0])
    separation = _subtract(cap_start, cap_end)
    width = _dot(separation, normal)
    cap_advance = abs(_dot(separation, outgoing_direction))
    if (
        not _MIN_STROKE_WIDTH <= width <= _MAX_HORIZONTAL_STROKE_WIDTH
        or cap_advance > 1.5 * width
    ):
        # An exposed left cap descends from the incoming upper edge to the
        # outgoing lower edge.  The opposite winding is an internal join or
        # counter edge, not another horizontal-stroke start.
        return None
    incoming_outward = normal
    return _HorizontalStartElement(
        incoming_line_index,
        cap_line_index,
        outgoing_line_index,
        incoming_start,
        cap_start,
        cap_end,
        outgoing_end,
        outgoing_direction,
        incoming_outward,
        width,
    )


def _horizontal_start_elements(
    commands: list[Command],
) -> tuple[_HorizontalStartElement, ...]:
    starts = _command_starts(commands)
    elements: list[_HorizontalStartElement] = []
    for cap_index in range(1, len(commands) - 1):
        incoming_operator, _ = commands[cap_index - 1]
        cap_operator, cap_operands = commands[cap_index]
        outgoing_operator, outgoing_operands = commands[cap_index + 1]
        incoming_start = starts[cap_index - 1]
        cap_start = starts[cap_index]
        if (
            incoming_operator != "lineTo"
            or cap_operator != "lineTo"
            or outgoing_operator != "lineTo"
            or incoming_start is None
            or cap_start is None
        ):
            continue
        element = _match_horizontal_start(
            cap_index - 1,
            cap_index,
            cap_index + 1,
            incoming_start,
            cap_start,
            cap_operands[-1],
            outgoing_operands[-1],
        )
        if element is not None:
            elements.append(element)
    for contour_start, contour_end in _contour_ranges(commands):
        cap_index = contour_start + 1
        outgoing_index = contour_start + 2
        if outgoing_index >= contour_end:
            continue
        cap_operator, cap_operands = commands[cap_index]
        outgoing_operator, outgoing_operands = commands[outgoing_index]
        incoming_start = starts[contour_end]
        if (
            cap_operator != "lineTo"
            or outgoing_operator != "lineTo"
            or incoming_start is None
        ):
            continue
        element = _match_horizontal_start(
            contour_end,
            cap_index,
            outgoing_index,
            incoming_start,
            commands[contour_start][1][-1],
            cap_operands[-1],
            outgoing_operands[-1],
        )
        if element is not None:
            elements.append(element)
    return tuple(elements)


def _edit_horizontal_start(
    element: _HorizontalStartElement,
    outgoing_end_override: Point | None = None,
) -> tuple[Command, ...]:
    outgoing_end = outgoing_end_override or element.outgoing_end
    axis = element.axis
    outward = element.incoming_outward
    unit = element.width / _HORIZONTAL_START_REFERENCE_WIDTH
    incoming_axis = _unit(_subtract(element.incoming_start, element.cap_start)) or axis

    # Preserve design B's horizontal center while replacing its arbitrary
    # apex and handle positions with a stroke-width-relative silver-ratio
    # construction.
    previous_top = _add(
        _add(element.cap_start, _scale(incoming_axis, 10.0 * unit)),
        _scale(outward, 4.0 * unit),
    )
    previous_bottom = _add(
        _add(element.cap_end, _scale(axis, 28.0 * unit)),
        _scale(outward, -7.0 * unit),
    )
    midpoint_along = (_dot(previous_top, axis) + _dot(previous_bottom, axis)) / 2.0

    expanded_height = _SILVER_RATIO * element.width
    extension = (expanded_height - element.width) / 2.0
    apex_separation = element.width / _SILVER_RATIO
    top_along = midpoint_along - apex_separation / 2.0
    bottom_along = midpoint_along + apex_separation / 2.0
    top_base = _dot(element.cap_start, outward)
    bottom_base = _dot(element.cap_end, outward)

    def local(along: float, away: float) -> Point:
        return _add(_scale(axis, along), _scale(outward, away))

    top_apex = local(top_along, top_base + extension)
    bottom_apex = local(bottom_along, bottom_base - extension)
    cap_length = math.hypot(expanded_height, apex_separation)
    bottom_run = _SILVER_RATIO * cap_length
    shared_join_along = bottom_along + bottom_run
    top_run = shared_join_along - top_along

    def circular_arc(
        apex_along: float,
        base_away: float,
        run: float,
        side: float,
    ) -> tuple[Point, Point, Point, Point]:
        radius = (run * run + extension * extension) / (2.0 * extension)
        handle = 4.0 * radius * extension / (3.0 * (math.hypot(run, extension) + run))
        tangent_along = (radius - extension) / radius
        tangent_away = run / radius
        apex = local(apex_along, base_away + side * extension)
        first_control = local(
            apex_along + handle * tangent_along,
            base_away + side * extension - side * handle * tangent_away,
        )
        second_control = local(
            apex_along + run - handle,
            base_away,
        )
        body = local(apex_along + run, base_away)
        return apex, first_control, second_control, body

    top_apex, top_first, top_second, top_body = circular_arc(
        top_along,
        top_base,
        top_run,
        1.0,
    )
    bottom_apex, bottom_first, bottom_second, bottom_body = circular_arc(
        bottom_along,
        bottom_base,
        bottom_run,
        -1.0,
    )
    return (
        ("lineTo", (top_body,)),
        ("curveTo", (top_second, top_first, top_apex)),
        ("lineTo", (bottom_apex,)),
        ("curveTo", (bottom_first, bottom_second, bottom_body)),
        ("lineTo", (outgoing_end,)),
    )


def _horizontal_start_command_edits(
    element: _HorizontalStartElement,
    outgoing_end_override: Point | None = None,
) -> tuple[_CommandEdit, ...]:
    replacement = _edit_horizontal_start(element, outgoing_end_override)
    if element.incoming_line_index + 1 == element.cap_line_index:
        return (
            _CommandEdit(
                element.incoming_line_index,
                3,
                replacement,
            ),
        )
    move_index = element.cap_line_index - 1
    return (
        _CommandEdit(
            move_index,
            3,
            (("moveTo", (element.incoming_start,)), *replacement),
        ),
    )


_MIN_VERTICAL_BODY_ASPECT_RATIO = 0.25
_MIN_VERTICAL_START_CAP_REACH = 18.0


def _vertical_body_side(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    command_index: int,
    *,
    from_start: bool,
) -> _LineSide | None:
    operator, operands = commands[command_index]
    command_start = starts[command_index]
    if command_start is None:
        return None
    if operator == "lineTo":
        start, end = command_start, operands[-1]
    elif operator == "curveTo":
        if from_start:
            start, end = command_start, operands[0]
        else:
            start, end = operands[1], operands[2]
    else:
        return None
    vector = _subtract(end, start)
    direction = _unit(vector)
    length = math.hypot(*vector)
    if direction is None or abs(vector[1]) < _MIN_SIDE_SLOPE * abs(vector[0]):
        return None
    return _LineSide(command_index, start, end, direction, length)


def _match_vertical_start_curve(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    contour_start: int,
    segment_indices: tuple[int, ...],
    curve_position: int,
    *,
    include_preceding_line: bool,
    include_following_line: bool,
) -> _VerticalStartElement | None:
    curve_index = segment_indices[curve_position]
    curve_start = starts[curve_index]
    curve_operator, curve_operands = commands[curve_index]
    if curve_operator != "curveTo" or curve_start is None:
        return None

    segment_count = len(segment_indices)
    previous_position = (curve_position - 1) % segment_count
    if include_preceding_line:
        preceding_cap_index = segment_indices[previous_position]
        if commands[preceding_cap_index][0] != "lineTo":
            return None
        up_position = (previous_position - 1) % segment_count
    else:
        up_position = previous_position

    following_position = (curve_position + 1) % segment_count
    if include_following_line:
        following_index = segment_indices[following_position]
        if commands[following_index][0] != "lineTo":
            return None
        down_position = (following_position + 1) % segment_count
    elif curve_position == segment_count - 1:
        down_position = 0
    else:
        return None
    if down_position in {up_position, curve_position}:
        return None

    cap_positions: list[int] = []
    position = (up_position + 1) % segment_count
    while position != down_position and len(cap_positions) <= 3:
        cap_positions.append(position)
        position = (position + 1) % segment_count
    if (
        not 1 <= len(cap_positions) <= 3
        or curve_position not in cap_positions
        or sum(
            commands[segment_indices[position]][0] == "curveTo"
            for position in cap_positions
        )
        != 1
    ):
        return None

    up_side = _vertical_body_side(
        commands,
        starts,
        segment_indices[up_position],
        from_start=False,
    )
    down_side = _vertical_body_side(
        commands,
        starts,
        segment_indices[down_position],
        from_start=True,
    )
    if up_side is None or down_side is None:
        return None
    pair = _stroke_pair(
        down_side,
        up_side,
        min_aspect_ratio=_MIN_VERTICAL_BODY_ASPECT_RATIO,
    )
    if pair is None or abs(pair.axis[1]) < 0.9:
        return None

    across = (-pair.axis[1], pair.axis[0])
    if _dot(_subtract(curve_operands[0], curve_start), across) < 0:
        across = _scale(across, -1)
    upward = _scale(pair.axis, -1)

    def normalized(point: Point) -> Point:
        offset = _subtract(point, curve_start)
        return (
            _dot(offset, across) / pair.width,
            _dot(offset, upward) / pair.width,
        )

    # Noto keeps this cap's point-to-point progression across weights even
    # though its body-width ratios change substantially from ExtraLight to
    # Black. Match the left return and both controls against the curve end.
    left_top, first_control, second_control, cap_end = (
        normalized(down_side.start),
        *(normalized(point) for point in curve_operands),
    )
    if (
        not -1.25 <= left_top[0] <= -0.75
        or cap_end[0] <= _GEOMETRY_EPSILON
        or cap_end[1] <= _GEOMETRY_EPSILON
        or cap_end[0] * pair.width < _MIN_VERTICAL_START_CAP_REACH
        or not 0.45 <= first_control[0] / cap_end[0] <= 0.90
        or not 0.75 <= second_control[0] / cap_end[0] <= 1.05
        or not -0.05 <= first_control[1] / cap_end[1] <= 0.25
        or not 0.30 <= second_control[1] / cap_end[1] <= 0.70
        or not 1.10 <= left_top[1] / cap_end[1] <= 1.80
        or not 1.00 <= cap_end[0] / cap_end[1] <= 1.80
    ):
        return None

    if include_preceding_line:
        cap_lead = normalized(up_side.end)
        if not (abs(cap_lead[0]) <= 0.25 and -0.45 <= cap_lead[1] <= 0):
            return None
    elif math.dist(up_side.end, curve_start) > _GEOMETRY_EPSILON:
        return None

    wraps = up_position >= down_position
    if wraps:
        before_close_positions = tuple(
            position for position in cap_positions if position > up_position
        )
        after_move_positions = tuple(
            position for position in cap_positions if position < down_position
        )
        if not before_close_positions:
            return None
    else:
        before_close_positions = tuple(cap_positions)
        after_move_positions = ()
    before_close_indices = tuple(
        segment_indices[position] for position in before_close_positions
    )
    return _VerticalStartElement(
        before_close_indices[0],
        len(before_close_indices),
        contour_start if wraps else None,
        len(after_move_positions),
        down_side,
        up_side,
        pair.axis,
        across,
        pair.width,
    )


def _vertical_start_elements(
    commands: list[Command],
) -> tuple[_VerticalStartElement, ...]:
    starts = _command_starts(commands)
    elements: list[_VerticalStartElement] = []
    for contour_start, contour_end in _contour_ranges(commands):
        segment_indices = tuple(
            index
            for index in range(contour_start + 1, contour_end)
            if commands[index][0] in {"lineTo", "curveTo"}
        )
        for curve_position, curve_index in enumerate(segment_indices):
            if commands[curve_index][0] != "curveTo":
                continue
            following_line_options = (
                (False, True) if curve_position == len(segment_indices) - 1 else (True,)
            )
            for include_preceding_line in (False, True):
                for include_following_line in following_line_options:
                    element = _match_vertical_start_curve(
                        commands,
                        starts,
                        contour_start,
                        segment_indices,
                        curve_position,
                        include_preceding_line=include_preceding_line,
                        include_following_line=include_following_line,
                    )
                    if element is not None:
                        elements.append(element)

    ranked = sorted(
        enumerate(elements),
        key=lambda item: (
            -min(item[1].down_side.length, item[1].up_side.length) / item[1].width,
            item[0],
        ),
    )
    used_commands: set[int] = set()
    selected_positions: set[int] = set()
    for position, element in ranked:
        command_indices = _vertical_start_command_indices(element)
        if used_commands.intersection(command_indices):
            continue
        used_commands.update(command_indices)
        selected_positions.add(position)
    return tuple(
        element
        for position, element in enumerate(elements)
        if position in selected_positions
    )


def _match_vertical_end_curve(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    segment_indices: tuple[int, ...],
    line_position: int,
) -> _VerticalEndElement | None:
    segment_count = len(segment_indices)
    curve_position = line_position + 1
    if curve_position >= segment_count:
        return None

    line_index = segment_indices[line_position]
    curve_index = segment_indices[curve_position]
    line_operator, line_operands = commands[line_index]
    curve_operator, curve_operands = commands[curve_index]
    if line_operator != "lineTo" or curve_operator != "curveTo":
        return None

    down_position = line_position - 1
    up_position = curve_position + 1
    if down_position < 0 or up_position >= segment_count:
        return None
    down_side = _vertical_body_side(
        commands,
        starts,
        segment_indices[down_position],
        from_start=False,
    )
    up_side = _vertical_body_side(
        commands,
        starts,
        segment_indices[up_position],
        from_start=True,
    )
    if down_side is None or up_side is None:
        return None
    pair = _stroke_pair(
        down_side,
        up_side,
        min_aspect_ratio=_MIN_VERTICAL_BODY_ASPECT_RATIO,
    )
    if pair is None or abs(pair.axis[1]) < 0.9:
        return None

    across = (-pair.axis[1], pair.axis[0])
    if _dot(_subtract(up_side.start, down_side.end), across) < 0:
        across = _scale(across, -1)

    def normalized(point: Point) -> Point:
        offset = _subtract(point, down_side.end)
        return (
            _dot(offset, across) / pair.width,
            _dot(offset, pair.axis) / pair.width,
        )

    # Noto preserves this line-and-cubic progression across weights even
    # though the body width varies substantially. Match the short lead and
    # both controls against the curve end before accepting the adjacent sides.
    line_end = normalized(line_operands[-1])
    first_control, second_control, cap_end = (
        normalized(point) for point in curve_operands
    )
    if (
        cap_end[0] <= _GEOMETRY_EPSILON
        or cap_end[1] >= -_GEOMETRY_EPSILON
        or not 0.12 <= line_end[0] / cap_end[0] <= 0.32
        or abs(line_end[1]) > 0.12
        or not 0.40 <= first_control[0] / cap_end[0] <= 0.75
        or abs(first_control[1]) > 0.12
        or not 0.85 <= second_control[0] / cap_end[0] <= 1.15
        or not 0.35 <= second_control[1] / cap_end[1] <= 0.85
        or not 0.85 <= cap_end[0] <= 1.15
        or not -0.65 <= cap_end[1] <= -0.20
    ):
        return None

    return _VerticalEndElement(
        line_index,
        2,
        down_side,
        up_side,
        pair.axis,
        across,
        pair.width,
    )


def _vertical_end_elements(
    commands: list[Command],
) -> tuple[_VerticalEndElement, ...]:
    starts = _command_starts(commands)
    elements: list[_VerticalEndElement] = []
    for contour_start, contour_end in _contour_ranges(commands):
        segment_indices = tuple(
            index
            for index in range(contour_start + 1, contour_end)
            if commands[index][0] in {"lineTo", "curveTo"}
        )
        for line_position in range(len(segment_indices) - 1):
            element = _match_vertical_end_curve(
                commands,
                starts,
                segment_indices,
                line_position,
            )
            if element is not None:
                elements.append(element)
    return tuple(elements)


def _fold_elements(commands: list[Command]) -> tuple[_FoldElement, ...]:
    starts = _command_starts(commands)
    elements: list[_FoldElement] = []
    for first_line_index in range(1, len(commands) - 2):
        previous_operator, _ = commands[first_line_index - 1]
        first_operator, first_operands = commands[first_line_index]
        second_operator, second_operands = commands[first_line_index + 1]
        horizontal_operator, horizontal_operands = commands[first_line_index + 2]
        incoming_start = starts[first_line_index - 1]
        outer = starts[first_line_index]
        if (
            previous_operator != "curveTo"
            or first_operator != "lineTo"
            or second_operator != "lineTo"
            or horizontal_operator != "lineTo"
            or incoming_start is None
            or outer is None
        ):
            continue
        apex = first_operands[-1]
        base = second_operands[-1]
        horizontal_end = horizontal_operands[-1]
        first_length = math.dist(outer, apex)
        second_length = math.dist(apex, base)
        horizontal_vector = _subtract(horizontal_end, base)
        horizontal_length = math.hypot(*horizontal_vector)
        if (
            not 70 <= first_length <= 180
            or not 30 <= second_length <= 100
            or horizontal_length < 40
            or horizontal_vector[0] >= -0.95 * horizontal_length
            or abs(horizontal_vector[1]) > 0.1 * horizontal_length
            or not outer[0] > apex[0] > base[0]
            or not outer[0] > incoming_start[0] > base[0]
            or not 20 <= base[1] - incoming_start[1] <= 100
            or apex[1] - max(outer[1], base[1]) < 20
        ):
            continue
        elements.append(
            _FoldElement(
                first_line_index - 1,
                first_line_index,
                first_line_index + 1,
                first_line_index + 2,
                incoming_start,
                outer,
                apex,
                base,
                horizontal_end,
            )
        )
    return tuple(elements)


def _edit_fold(element: _FoldElement) -> tuple[Command, ...]:
    # Reverse the selected fold B recipe into Noto's contour direction.
    # Its reference endpoints (832, 638) and (744, 687) map to the
    # unmodified vertical side and horizontal body of each matched fold.
    x_scale = (element.incoming_start[0] - element.base[0]) / 88.0
    y_scale = (element.base[1] - element.incoming_start[1]) / 49.0

    def point(x: float, y: float) -> Point:
        return (
            element.base[0] + (x - 744.0) * x_scale,
            element.base[1] + (y - 687.0) * y_scale,
        )

    return (
        ("lineTo", (point(858, 647),)),
        (
            "curveTo",
            (
                point(882.7, 656.5),
                point(883.935, 666),
                point(807.690375, 725.22775),
            ),
        ),
        (
            "curveTo",
            (
                point(800, 731),
                point(794, 731),
                point(788, 724),
            ),
        ),
        ("lineTo", (point(761, 692),)),
        (
            "curveTo",
            (
                point(755, 687),
                point(750, 687),
                element.base,
            ),
        ),
    )


def _box_left_candidates(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    contour_start: int,
    contour_end: int,
) -> tuple[_BoxLeftCandidate, ...]:
    segment_indices = tuple(range(contour_start + 1, contour_end))
    candidates: list[_BoxLeftCandidate] = []
    for position, side_index in enumerate(segment_indices):
        side_operator, side_operands = commands[side_index]
        side_start = starts[side_index]
        if side_operator != "lineTo" or side_start is None:
            continue
        side_end = side_operands[-1]
        side_vector = _subtract(side_end, side_start)
        axis = _unit(side_vector)
        if (
            axis is None
            or side_vector[1] >= -_MIN_SIDE_LENGTH
            or abs(side_vector[0]) > 0.12 * abs(side_vector[1])
        ):
            continue
        top_horizontal_index = segment_indices[(position - 2) % len(segment_indices)]
        top_corner_index = segment_indices[(position - 1) % len(segment_indices)]
        bottom_line_index = segment_indices[(position + 1) % len(segment_indices)]
        bottom_curve_index = segment_indices[(position + 2) % len(segment_indices)]
        top_horizontal_operator, top_horizontal_operands = commands[
            top_horizontal_index
        ]
        top_corner_operator, top_corner_operands = commands[top_corner_index]
        bottom_line_operator, bottom_line_operands = commands[bottom_line_index]
        bottom_curve_operator, bottom_curve_operands = commands[bottom_curve_index]
        top_horizontal_start = starts[top_horizontal_index]
        top_corner_start = starts[top_corner_index]
        bottom_line_start = starts[bottom_line_index]
        bottom_curve_start = starts[bottom_curve_index]
        if (
            top_horizontal_operator != "lineTo"
            or top_corner_operator != "lineTo"
            or bottom_line_operator != "lineTo"
            or bottom_curve_operator != "curveTo"
            or top_horizontal_start is None
            or top_corner_start is None
            or bottom_line_start is None
            or bottom_curve_start is None
        ):
            continue
        top_horizontal_vector = _subtract(
            top_horizontal_operands[-1], top_horizontal_start
        )
        top_corner_vector = _subtract(top_corner_operands[-1], top_corner_start)
        bottom_line_vector = _subtract(bottom_line_operands[-1], bottom_line_start)
        inner_bottom = bottom_curve_operands[-1]
        bottom_curve_vector = _subtract(inner_bottom, bottom_curve_start)
        across = (-axis[1], axis[0])
        width = _dot(_subtract(inner_bottom, side_end), across)
        corner_tip = top_corner_operands[-1]
        top_bridge = _subtract(side_start, corner_tip)
        top_bridge_axial = _dot(top_bridge, axis)
        top_bridge_across = _dot(top_bridge, across)
        if (
            top_horizontal_vector[0] >= -100
            or abs(top_horizontal_vector[1]) > 0.15 * abs(top_horizontal_vector[0])
            or top_corner_vector[0] >= -20
            or top_corner_vector[1] <= 0
            or not 20 <= math.hypot(*top_corner_vector) <= 150
            or not 0 < bottom_line_vector[0] <= 100
            or abs(bottom_line_vector[1]) > 30
            or bottom_curve_vector[0] <= 20
            or not 35 <= width <= 120
            or top_bridge_axial < -_GEOMETRY_EPSILON
            or top_bridge_axial > 2.5 * width
            or abs(top_bridge_across) > 0.25 * width
        ):
            continue
        candidates.append(
            _BoxLeftCandidate(
                contour_start,
                contour_end,
                top_horizontal_index,
                top_corner_index,
                side_index,
                bottom_line_index,
                bottom_curve_index,
                side_start,
                top_corner_start,
                corner_tip,
                side_end,
                inner_bottom,
                axis,
                across,
                width,
            )
        )
    return tuple(candidates)


def _box_right_candidates(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    contour_start: int,
    contour_end: int,
) -> tuple[_BoxRightCandidate, ...]:
    segment_indices = tuple(range(contour_start + 1, contour_end))
    candidates: list[_BoxRightCandidate] = []
    for position, inner_side_index in enumerate(segment_indices):
        inner_operator, inner_operands = commands[inner_side_index]
        inner_top = starts[inner_side_index]
        if inner_operator != "lineTo" or inner_top is None:
            continue
        inner_bottom = inner_operands[-1]
        inner_vector = _subtract(inner_bottom, inner_top)
        axis = _unit(inner_vector)
        if (
            axis is None
            or inner_vector[1] >= -20
            or abs(inner_vector[0]) > 0.15 * abs(inner_vector[1])
        ):
            continue
        bottom_horizontal_index = segment_indices[(position - 1) % len(segment_indices)]
        bottom_line_index = segment_indices[(position + 1) % len(segment_indices)]
        bottom_curve_index = segment_indices[(position + 2) % len(segment_indices)]
        outer_side_index = segment_indices[(position + 3) % len(segment_indices)]
        bottom_horizontal_operator, bottom_horizontal_operands = commands[
            bottom_horizontal_index
        ]
        bottom_line_operator, bottom_line_operands = commands[bottom_line_index]
        bottom_curve_operator, bottom_curve_operands = commands[bottom_curve_index]
        outer_operator, outer_operands = commands[outer_side_index]
        bottom_horizontal_start = starts[bottom_horizontal_index]
        bottom_line_start = starts[bottom_line_index]
        bottom_curve_start = starts[bottom_curve_index]
        outer_bottom = starts[outer_side_index]
        if (
            bottom_horizontal_operator != "lineTo"
            or bottom_line_operator != "lineTo"
            or bottom_curve_operator != "curveTo"
            or outer_operator != "lineTo"
            or bottom_horizontal_start is None
            or bottom_line_start is None
            or bottom_curve_start is None
            or outer_bottom is None
        ):
            continue
        bottom_horizontal_vector = _subtract(
            bottom_horizontal_operands[-1], bottom_horizontal_start
        )
        bottom_line_vector = _subtract(bottom_line_operands[-1], bottom_line_start)
        bottom_curve_vector = _subtract(bottom_curve_operands[-1], bottom_curve_start)
        outer_top = outer_operands[-1]
        outer_vector = _subtract(outer_top, outer_bottom)
        outer_direction = _unit(outer_vector)
        across = (-axis[1], axis[0])
        width = _dot(_subtract(outer_bottom, inner_bottom), across)
        if (
            bottom_horizontal_vector[0] <= 100
            or abs(bottom_horizontal_vector[1])
            > 0.15 * abs(bottom_horizontal_vector[0])
            or not 0 < bottom_line_vector[0] <= 100
            or abs(bottom_line_vector[1]) > 30
            or bottom_curve_vector[0] <= 20
            or outer_direction is None
            or outer_vector[1] <= _MIN_SIDE_LENGTH
            or abs(outer_vector[0]) > 0.15 * abs(outer_vector[1])
            or _dot(axis, outer_direction) > _MAX_PARALLEL_DOT
            or not 35 <= width <= 120
        ):
            continue
        candidates.append(
            _BoxRightCandidate(
                contour_start,
                contour_end,
                bottom_horizontal_index,
                inner_side_index,
                bottom_line_index,
                bottom_curve_index,
                outer_side_index,
                inner_top,
                inner_bottom,
                outer_bottom,
                outer_top,
                axis,
                across,
                width,
            )
        )
    return tuple(candidates)


def _contour_geometry(
    commands: list[Command],
    contour_start: int,
    contour_end: int,
) -> tuple[float, tuple[float, float, float, float]]:
    first: Point | None = None
    previous: Point | None = None
    twice_area = 0.0
    x_min = y_min = math.inf
    x_max = y_max = -math.inf
    for command_index in range(contour_start, contour_end):
        _, operands = commands[command_index]
        if not operands:
            continue
        for x, y in operands:
            x_min = min(x_min, x)
            y_min = min(y_min, y)
            x_max = max(x_max, x)
            y_max = max(y_max, y)
        endpoint = operands[-1]
        if first is None:
            first = endpoint
        elif previous is not None:
            twice_area += previous[0] * endpoint[1] - endpoint[0] * previous[1]
        previous = endpoint
    if first is None or previous is None:
        return 0.0, (0.0, 0.0, 0.0, 0.0)
    twice_area += previous[0] * first[1] - first[0] * previous[1]
    return twice_area / 2.0, (x_min, y_min, x_max, y_max)


def _contour_has_counter(
    contour: tuple[int, int],
    geometries: Mapping[
        tuple[int, int],
        tuple[float, tuple[float, float, float, float]],
    ],
) -> bool:
    outer_area, (x_min, y_min, x_max, y_max) = geometries[contour]
    bounds_area = (x_max - x_min) * (y_max - y_min)
    for inner_contour, (
        inner_area,
        (inner_x_min, inner_y_min, inner_x_max, inner_y_max),
    ) in geometries.items():
        inner_bounds_area = (inner_x_max - inner_x_min) * (inner_y_max - inner_y_min)
        if (
            inner_contour != contour
            and outer_area * inner_area < 0
            and inner_x_min >= x_min
            and inner_y_min >= y_min
            and inner_x_max <= x_max
            and inner_y_max <= y_max
            and inner_bounds_area > 0.015 * bounds_area
        ):
            return True
    return False


def _box_elements(commands: list[Command]) -> tuple[_BoxElement, ...]:
    starts = _command_starts(commands)
    contour_ranges = _contour_ranges(commands)
    contour_geometries = {
        contour: _contour_geometry(commands, *contour) for contour in contour_ranges
    }
    matches: list[tuple[float, _BoxElement]] = []
    for contour_start, contour_end in contour_ranges:
        if commands[contour_end][0] != "closePath":
            continue
        if not _contour_has_counter((contour_start, contour_end), contour_geometries):
            continue
        left_candidates = _box_left_candidates(
            commands, starts, contour_start, contour_end
        )
        right_candidates = _box_right_candidates(
            commands, starts, contour_start, contour_end
        )
        for left in left_candidates:
            for right in right_candidates:
                if (
                    not left.command_indices.isdisjoint(right.command_indices)
                    or _dot(left.axis, right.axis) < 0.94
                ):
                    continue
                span = _dot(_subtract(right.inner_top, left.outer_top), left.across)
                width = max(left.width, right.width)
                if (
                    span <= 2 * width
                    or not 0.5 <= left.width / right.width <= 2
                    or abs(
                        _dot(
                            _subtract(right.outer_top, left.top_inner),
                            left.axis,
                        )
                    )
                    > 2.0 * width
                    or abs(
                        _dot(
                            _subtract(right.inner_top, left.inner_bottom),
                            left.axis,
                        )
                    )
                    > 2.0 * width
                ):
                    continue
                matches.append((span, _BoxElement(left, right)))
    used: set[int] = set()
    selected: list[_BoxElement] = []
    for _, element in sorted(matches, key=lambda item: item[0], reverse=True):
        if not element.command_indices.isdisjoint(used):
            continue
        used.update(element.command_indices)
        selected.append(element)
    return tuple(selected)


def _box_local_point(
    anchor: Point,
    axis: Point,
    across: Point,
    width: float,
    reference_width: float,
    x_units: float,
    down_units: float,
    axial_scale: float,
) -> Point:
    unit_scale = width / reference_width
    return _add(
        _add(anchor, _scale(across, x_units * unit_scale)),
        _scale(axis, down_units * unit_scale * axial_scale),
    )


def _box_command_edits(element: _BoxElement) -> tuple[_CommandEdit, ...]:
    left = element.left
    right = element.right
    left_unit_scale = left.width / 67.0
    left_length = math.dist(left.side_start, left.outer_bottom)
    top_scale = min(1.0, 0.45 * left_length / (107.0 * left_unit_scale))
    bottom_scale = min(1.0, 0.45 * left_length / (220.0 * left_unit_scale))

    def top_point(x: float, y: float) -> Point:
        return _box_local_point(
            left.outer_top,
            left.axis,
            left.across,
            left.width,
            67.0,
            x - 158.0,
            722.0 - y,
            top_scale,
        )

    def bottom_point(x: float, y: float) -> Point:
        return _box_local_point(
            left.outer_bottom,
            left.axis,
            left.across,
            left.width,
            67.0,
            x - 158.0,
            -40.0 - y,
            bottom_scale,
        )

    left_inner_bottom = bottom_point(225, 50)
    top_horizontal_end = _add(
        left.top_inner,
        _scale(left.across, 10.0 * left_unit_scale),
    )
    edits: list[_CommandEdit] = [
        _CommandEdit(
            left.top_horizontal_index,
            1,
            (("lineTo", (top_horizontal_end,)),),
        ),
        _CommandEdit(
            left.top_corner_index,
            1,
            (
                (
                    "lineTo",
                    (top_point(151.5, 727),),
                ),
                (
                    "curveTo",
                    (
                        top_point(156, 704),
                        top_point(158, 657),
                        top_point(158, 620),
                    ),
                ),
            ),
        ),
        _CommandEdit(
            left.side_index,
            1,
            (("lineTo", (bottom_point(158, 180),)),),
        ),
        _CommandEdit(
            left.bottom_line_index,
            2,
            (
                (
                    "curveTo",
                    (
                        bottom_point(158, 100),
                        bottom_point(155, 48),
                        bottom_point(151, -20),
                    ),
                ),
                (
                    "curveTo",
                    (
                        bottom_point(151, -30),
                        bottom_point(162, -40),
                        bottom_point(175, -40),
                    ),
                ),
                (
                    "curveTo",
                    (
                        bottom_point(204, -40),
                        bottom_point(225, -23),
                        bottom_point(229, -9),
                    ),
                ),
                (
                    "curveTo",
                    (
                        bottom_point(227, 7),
                        bottom_point(225, 18),
                        left_inner_bottom,
                    ),
                ),
            ),
        ),
    ]
    if left.top_corner_index > left.side_index:
        edits.append(
            _CommandEdit(
                left.contour_start,
                1,
                (("moveTo", (top_point(158, 620),)),),
            )
        )
    if left.bottom_curve_index == left.contour_end - 1:
        edits.append(
            _CommandEdit(
                left.contour_start,
                1,
                (("moveTo", (left_inner_bottom,)),),
            )
        )
    right_unit_scale = right.width / 68.0
    inner_length = math.dist(right.inner_top, right.inner_bottom)
    right_scale = min(1.0, inner_length / (109.0 * right_unit_scale))

    def right_point(x: float, y: float) -> Point:
        return _box_local_point(
            right.inner_top,
            right.axis,
            right.across,
            right.width,
            68.0,
            x - 778.0,
            82.0 - y,
            right_scale,
        )

    edits.extend(
        (
            _CommandEdit(
                right.inner_side_index,
                1,
                (("lineTo", (right_point(778, 45),)),),
            ),
            _CommandEdit(
                right.bottom_line_index,
                2,
                (
                    (
                        "curveTo",
                        (
                            right_point(777, 32),
                            right_point(777, 16),
                            right_point(776, -7),
                        ),
                    ),
                    (
                        "curveTo",
                        (
                            right_point(776, -17),
                            right_point(782, -27),
                            right_point(788, -27),
                        ),
                    ),
                    (
                        "curveTo",
                        (
                            right_point(812, -27),
                            right_point(843, -12),
                            right_point(849, -4),
                        ),
                    ),
                    (
                        "curveTo",
                        (
                            right_point(847, 74),
                            right_point(846, 134),
                            right_point(845, 234),
                        ),
                    ),
                ),
            ),
            _CommandEdit(
                right.outer_side_index,
                1,
                (
                    (
                        "lineTo",
                        (
                            _add(
                                right.outer_top, _scale(right.across, -right_unit_scale)
                            ),
                        ),
                    ),
                ),
            ),
        )
    )

    return tuple(edits)


def _is_right_sweep_terminal(
    start: Point,
    cap_start: Point,
    cap_end: Point,
    end: Point,
    incoming_span: float,
    outgoing_span: float,
    cap_length: float,
    incoming_direction: Point,
    outgoing_direction: Point,
) -> bool:
    short_span = min(incoming_span, outgoing_span)
    long_span = max(incoming_span, outgoing_span)
    if (
        short_span >= _MAX_RIGHT_SWEEP_SHORT_TO_LONG_RATIO * long_span
        or cap_length > _MAX_RIGHT_SWEEP_CAP_TO_SHORT_SIDE_RATIO * short_span
    ):
        return False
    if min(cap_start[0], cap_end[0]) <= max(start[0], end[0]):
        return False
    return (
        incoming_direction[0] > _GEOMETRY_EPSILON
        and outgoing_direction[0] < -_GEOMETRY_EPSILON
    )


def _is_left_sweep_terminal(
    start: Point,
    cap_start: Point,
    cap_end: Point,
    end: Point,
) -> bool:
    return (
        max(cap_start[0], cap_end[0]) < min(start[0], end[0]) - _GEOMETRY_EPSILON
        and max(cap_start[1], cap_end[1]) < min(start[1], end[1]) - _GEOMETRY_EPSILON
    )


def _classify_terminal_role(geometry: _TerminalGeometry) -> TerminalRole | None:
    if _is_right_sweep_terminal(
        geometry.start,
        geometry.cap_start,
        geometry.cap_end,
        geometry.end,
        geometry.incoming_span,
        geometry.outgoing_span,
        geometry.cap_length,
        geometry.incoming_direction,
        geometry.outgoing_direction,
    ):
        return "right-sweep"
    if math.dist(geometry.start, geometry.end) <= _GEOMETRY_EPSILON:
        if (
            min(geometry.incoming_span, geometry.outgoing_span)
            < _MIN_CLOSED_DOT_SIDE_TO_CAP_RATIO * geometry.cap_length
        ):
            return None
        return "closed-dot"
    if geometry.incoming_span < 300 and geometry.outgoing_span < 300:
        if (
            geometry.start[0] - geometry.cap_start[0]
            < _MIN_HOOK_OUTWARD_HORIZONTAL_RATIO * geometry.incoming_span
            or geometry.end[0] - geometry.cap_end[0]
            < _MIN_HOOK_OUTWARD_HORIZONTAL_RATIO * geometry.outgoing_span
        ):
            return None
        return "hook"
    if _is_left_sweep_terminal(
        geometry.start,
        geometry.cap_start,
        geometry.cap_end,
        geometry.end,
    ):
        return "left-sweep"
    return None


def _hook_curve_run(
    commands: list[Command],
    contour_end: int,
    incoming_index: int,
    outgoing_index: int,
    geometry: _TerminalGeometry,
) -> tuple[int, Point] | None:
    outgoing_curve_count = 1
    end = geometry.end
    next_index = outgoing_index + 1
    while (
        outgoing_curve_count < 3
        and next_index < contour_end
        and next_index != incoming_index
        and commands[next_index][0] == "curveTo"
    ):
        outgoing_curve_count += 1
        end = commands[next_index][1][-1]
        next_index += 1
    if outgoing_curve_count != 3:
        return None
    down_direction = _unit(_subtract(geometry.cap_end, geometry.cap_start))
    across_direction = _unit(
        _add(
            _subtract(end, geometry.cap_start),
            _scale(_subtract(geometry.cap_end, geometry.cap_start), 0.5),
        )
    )
    if (
        down_direction is None
        or across_direction is None
        or abs(_dot(down_direction, across_direction)) > _MAX_HOOK_BASIS_DOT
    ):
        return None
    return outgoing_curve_count, end


def _match_terminal_candidate(
    commands: list[Command],
    starts: tuple[Point | None, ...],
    contour_start: int,
    contour_end: int,
    segment_indices: tuple[int, ...],
    position: int,
) -> _TerminalElement | None:
    cap_index = segment_indices[position]
    incoming_index = segment_indices[position - 1]
    outgoing_index = segment_indices[(position + 1) % len(segment_indices)]
    linear = incoming_index + 1 == cap_index and cap_index + 1 == outgoing_index
    wraps_at_start = (
        cap_index == contour_start + 1
        and outgoing_index == cap_index + 1
        and incoming_index == contour_end - 1
    )
    if not linear and not wraps_at_start:
        return None

    incoming_operator, incoming_operands = commands[incoming_index]
    cap_operator, cap_operands = commands[cap_index]
    outgoing_operator, outgoing_operands = commands[outgoing_index]
    start = starts[incoming_index]
    cap_start = starts[cap_index]
    if (
        incoming_operator != "curveTo"
        or cap_operator != "lineTo"
        or outgoing_operator != "curveTo"
        or start is None
        or cap_start is None
    ):
        return None

    cap_end = cap_operands[-1]
    end = outgoing_operands[-1]
    cap_length = math.dist(cap_start, cap_end)
    cap_vector = _subtract(cap_end, cap_start)
    incoming_span = math.dist(start, cap_start)
    outgoing_span = math.dist(cap_end, end)
    incoming_direction = _first_unit(
        _subtract(cap_start, incoming_operands[-2]),
        _subtract(cap_start, incoming_operands[0]),
        _subtract(cap_start, start),
    )
    outgoing_direction = _first_unit(
        _subtract(outgoing_operands[0], cap_end),
        _subtract(outgoing_operands[1], cap_end),
        _subtract(end, cap_end),
    )
    if (
        not _MIN_TERMINAL_CAP_LENGTH <= cap_length <= _MAX_TERMINAL_CAP_LENGTH
        or abs(cap_vector[1]) < 0.35 * cap_length
        or incoming_span < _MIN_TERMINAL_CURVE_SPAN
        or outgoing_span < _MIN_TERMINAL_CURVE_SPAN
        or incoming_direction is None
        or outgoing_direction is None
        or _dot(incoming_direction, outgoing_direction) > _MAX_TERMINAL_TANGENT_DOT
    ):
        return None

    geometry = _TerminalGeometry(
        start,
        cap_start,
        cap_end,
        end,
        incoming_span,
        outgoing_span,
        cap_length,
        incoming_direction,
        outgoing_direction,
    )
    role = _classify_terminal_role(geometry)
    if role is None:
        return None

    outgoing_curve_count = 1
    if role == "hook":
        hook_run = _hook_curve_run(
            commands,
            contour_end,
            incoming_index,
            outgoing_index,
            geometry,
        )
        if hook_run is None:
            return None
        outgoing_curve_count, end = hook_run

    return _TerminalElement(
        incoming_index,
        cap_index,
        outgoing_index,
        start,
        cap_start,
        cap_end,
        end,
        role,
        outgoing_curve_count,
    )


def _select_non_overlapping_terminals(
    candidates: list[_TerminalElement],
) -> tuple[_TerminalElement, ...]:
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (item[1].role == "left-sweep", item[0]),
    )
    used_commands: set[int] = set()
    selected_positions: set[int] = set()
    for position, element in ranked:
        command_indices = _terminal_command_indices(element)
        if used_commands.intersection(command_indices):
            continue
        used_commands.update(command_indices)
        selected_positions.add(position)
    return tuple(
        element
        for position, element in enumerate(candidates)
        if position in selected_positions
    )


def _terminal_elements(commands: list[Command]) -> tuple[_TerminalElement, ...]:
    starts = _command_starts(commands)
    candidates: list[_TerminalElement] = []
    for contour_start, contour_end in _contour_ranges(commands):
        segment_indices = tuple(range(contour_start + 1, contour_end))
        for position in range(len(segment_indices)):
            candidate = _match_terminal_candidate(
                commands,
                starts,
                contour_start,
                contour_end,
                segment_indices,
                position,
            )
            if candidate is not None:
                candidates.append(candidate)
    return _select_non_overlapping_terminals(candidates)


def _edit_hook_terminal(
    element: _TerminalElement,
    commands: list[Command],
) -> tuple[Command, ...]:
    _, incoming_operands = commands[element.incoming_curve_index]
    down = _subtract(element.cap_end, element.cap_start)
    across = _add(
        _subtract(element.end, element.cap_start),
        _scale(down, 0.5),
    )
    down_direction = _unit(down)
    if down_direction is None:
        raise ValueError("Hook cap must have a nonzero length")
    cap_length = math.hypot(*down)
    source_down_limit = max(
        _dot(_subtract(point, element.cap_start), down_direction) / cap_length
        for command_index in range(
            element.outgoing_curve_index,
            element.outgoing_curve_index + element.outgoing_curve_count,
        )
        for point in commands[command_index][1]
    )
    recipe_down_limit = 95 / 16
    down_scale = max(
        0.0,
        min(1.0, (source_down_limit - 1) / (recipe_down_limit - 1)),
    )

    def point(across_units: float, down_units: float) -> Point:
        if down_units > 1:
            down_units = 1 + (down_units - 1) * down_scale
        return _add(
            _add(element.cap_start, _scale(across, across_units)),
            _scale(down, down_units),
        )

    return (
        (
            "curveTo",
            (
                incoming_operands[0],
                point(34 / 256, 1 / 16),
                point(4 / 256, 0),
            ),
        ),
        (
            "curveTo",
            (
                point(0, 0),
                point(-2 / 256, 2 / 16),
                point(-2 / 256, 6 / 16),
            ),
        ),
        (
            "curveTo",
            (
                point(-2 / 256, 11 / 16),
                point(1 / 256, 15 / 16),
                point(6 / 256, 16 / 16),
            ),
        ),
        (
            "curveTo",
            (
                point(58 / 256, 24 / 16),
                point(88 / 256, 32 / 16),
                point(106 / 256, 42 / 16),
            ),
        ),
        (
            "curveTo",
            (
                point(118 / 256, 50 / 16),
                point(129 / 256, 57 / 16),
                point(133 / 256, 71 / 16),
            ),
        ),
        (
            "curveTo",
            (
                point(139 / 256, 91 / 16),
                point(141 / 256, 95 / 16),
                point(161 / 256, 92 / 16),
            ),
        ),
        (
            "curveTo",
            (
                point(242 / 256, 78 / 16),
                point(256 / 256, 43 / 16),
                element.end,
            ),
        ),
    )


def _terminal_rounding_ratios(
    element: _TerminalElement,
    style: BrushElementStyle,
) -> tuple[float, float]:
    if element.role == "right-sweep":
        incoming_is_short_side = math.dist(
            element.start, element.cap_start
        ) < math.dist(element.cap_end, element.end)
        if incoming_is_short_side:
            return style.right_sweep_incoming_ratio, style.right_sweep_outgoing_ratio
        return style.right_sweep_outgoing_ratio, style.right_sweep_incoming_ratio
    if element.role == "closed-dot":
        return style.hook_rounding_ratio, style.hook_rounding_ratio
    return style.left_sweep_rounding_ratio, style.left_sweep_rounding_ratio


def _edit_terminal(
    element: _TerminalElement,
    commands: list[Command],
    style: BrushElementStyle,
) -> tuple[Command, ...]:
    if element.role == "hook":
        return _edit_hook_terminal(element, commands)
    _, incoming_operands = commands[element.incoming_curve_index]
    _, outgoing_operands = commands[element.outgoing_curve_index]
    incoming_ratio, outgoing_ratio = _terminal_rounding_ratios(element, style)
    incoming, _ = _split_cubic(
        element.start,
        incoming_operands[0],
        incoming_operands[1],
        element.cap_start,
        1 - incoming_ratio,
    )
    _, outgoing = _split_cubic(
        element.cap_end,
        outgoing_operands[0],
        outgoing_operands[1],
        element.end,
        outgoing_ratio,
    )
    return (
        ("curveTo", incoming[1:]),
        (
            "curveTo",
            (element.cap_start, element.cap_end, outgoing[0]),
        ),
        ("curveTo", outgoing[1:]),
    )


def _terminal_command_edits(
    element: _TerminalElement,
    commands: list[Command],
    style: BrushElementStyle,
) -> tuple[_CommandEdit, ...]:
    replacement = _edit_terminal(element, commands, style)
    source_command_count = 2 + element.outgoing_curve_count
    if element.incoming_curve_index + 1 == element.cap_line_index:
        return (
            _CommandEdit(
                element.incoming_curve_index,
                source_command_count,
                replacement,
            ),
        )
    move_index = element.cap_line_index - 1
    return (
        _CommandEdit(
            move_index,
            source_command_count,
            (("moveTo", (element.end,)), *replacement),
        ),
        _CommandEdit(element.incoming_curve_index, 1, ()),
    )


def _combined_vertical_start_terminal_edit(
    down_edit: _CommandEdit,
    terminal: _TerminalElement,
    commands: list[Command],
    style: BrushElementStyle,
) -> _CommandEdit:
    if (
        terminal.role == "hook"
        or terminal.incoming_curve_index + 1 != terminal.cap_line_index
        or down_edit.command_index != terminal.incoming_curve_index
        or len(down_edit.replacement) < 2
    ):
        raise ValueError("Unsupported overlapping vertical start and terminal")
    preserved_operator, preserved_operands = down_edit.replacement[-1]
    preserved_start = down_edit.replacement[-2][1][-1]
    if preserved_operator != "curveTo":
        raise ValueError("Curved vertical start must preserve a cubic body")
    incoming_ratio, _ = _terminal_rounding_ratios(terminal, style)
    incoming, _ = _split_cubic(
        preserved_start,
        preserved_operands[0],
        preserved_operands[1],
        preserved_operands[2],
        1 - incoming_ratio,
    )
    terminal_replacement = _edit_terminal(terminal, commands, style)
    replacement = (
        *down_edit.replacement[:-1],
        ("curveTo", incoming[1:]),
        *terminal_replacement[1:],
    )
    return _CommandEdit(
        terminal.incoming_curve_index,
        2 + terminal.outgoing_curve_count,
        replacement,
    )


def _uroko_elements(commands: list[Command]) -> tuple[_UrokoElement, ...]:
    starts = _command_starts(commands)
    contours = _contour_ranges(commands)
    elements: list[_UrokoElement] = []
    for index in range(1, len(commands) - 1):
        operator, operands = commands[index]
        next_operator, next_operands = commands[index + 1]
        previous_operator, _ = commands[index - 1]
        line_start = starts[index - 1]
        start = starts[index]
        if (
            operator != "curveTo"
            or next_operator != "curveTo"
            or previous_operator != "lineTo"
            or line_start is None
            or start is None
        ):
            continue
        line_vector = _subtract(start, line_start)
        tip = operands[-1]
        end = next_operands[-1]
        rise = end[1] - tip[1]
        if (
            line_vector[0] < _MIN_SIDE_LENGTH
            or abs(line_vector[1]) > 0.1 * line_vector[0]
            or not 10.0 <= tip[0] - start[0] <= 100.0
            or not 0.0 <= tip[1] - start[1] <= 80.0
            or end[0] >= tip[0] - 40.0
            or not 40.0 <= rise <= 180.0
        ):
            continue
        contour = next(
            (item for item in contours if item[0] < index < item[1]),
            None,
        )
        if contour is None:
            continue
        following_line_index = index + 2
        contour_move_index: int | None = None
        if commands[following_line_index][0] == "closePath":
            contour_move_index = contour[0]
            following_line_index = contour_move_index + 1
        if (
            commands[following_line_index][0] != "lineTo"
            or starts[following_line_index] != end
        ):
            continue
        lower_join = commands[following_line_index][1][-1]
        lower_body_index = following_line_index + 1
        if lower_body_index < contour[1] and commands[lower_body_index][0] == "lineTo":
            lower_body_end = commands[lower_body_index][1][-1]
        elif (
            lower_body_index == contour[1]
            and commands[lower_body_index][0] == "closePath"
        ):
            lower_body_end = commands[contour[0]][1][-1]
        else:
            continue
        lower_body_vector = _subtract(lower_body_end, lower_join)
        required_lower_body = max(
            5.0,
            (element_span := start[0] - lower_join[0]) * 28.0 / 150.0,
        )
        if (
            element_span <= 0
            or lower_body_vector[0] > -required_lower_body
            or abs(lower_body_vector[1]) > 0.1 * abs(lower_body_vector[0])
        ):
            continue
        elements.append(
            _UrokoElement(
                index - 1,
                index,
                index + 1,
                following_line_index,
                contour_move_index,
                start,
                tip,
                end,
                lower_join,
            )
        )
    return tuple(elements)


def _uroko_design(
    element: _UrokoElement,
) -> tuple[Point, Point, tuple[Command, ...]]:
    # Map the selected U+4E00 uroko B recipe from its Noto reference
    # coordinates. Separate x/y scales preserve the local stroke thickness
    # and the available horizontal length in each matched glyph.
    x_scale = (element.start[0] - element.lower_join[0]) / 150.0
    y_scale = (element.end[1] - element.start[1]) / 116.0

    def point(x: float, y: float) -> Point:
        return (
            element.start[0] + (x - 928.0) * x_scale,
            element.start[1] + (y - 398.0) * y_scale,
        )

    upper_cut = point(750, 398)
    lower_cut = point(750, 431)
    replacement: tuple[Command, ...] = (
        ("lineTo", (point(911, 398),)),
        (
            "curveTo",
            (point(926, 398), point(941, 401), point(941, 413)),
        ),
        (
            "curveTo",
            (point(941, 438), point(882, 482), point(846, 510)),
        ),
        (
            "curveTo",
            (point(836, 518), point(826, 514), point(820, 505)),
        ),
        ("lineTo", (point(778, 441),)),
        (
            "curveTo",
            (point(774, 435), point(770, 431), point(764, 431)),
        ),
        ("lineTo", (lower_cut,)),
    )
    return upper_cut, lower_cut, replacement


def _left_sweep_start_elements(
    commands: list[Command],
) -> tuple[_LeftSweepStartElement, ...]:
    """Find the opening contour seam of a broad descending-left sweep."""

    starts = _command_starts(commands)
    elements: list[_LeftSweepStartElement] = []
    for contour_start, contour_end in _contour_ranges(commands):
        first_curve_index = contour_start + 1
        inner_curve_index = contour_end - 2
        shoulder_curve_index = contour_end - 1
        if first_curve_index >= inner_curve_index:
            continue
        first_operator, first_operands = commands[first_curve_index]
        inner_operator, inner_operands = commands[inner_curve_index]
        shoulder_operator, shoulder_operands = commands[shoulder_curve_index]
        body_commands = commands[first_curve_index + 1 : inner_curve_index]
        if (
            first_operator != "curveTo"
            or inner_operator != "curveTo"
            or shoulder_operator != "curveTo"
            or len(first_operands) != 3
            or len(inner_operands) != 3
            or len(shoulder_operands) != 3
            or not body_commands
            or any(
                (operator == "lineTo" and len(operands) != 1)
                or (operator == "curveTo" and len(operands) != 3)
                or operator not in {"lineTo", "curveTo"}
                for operator, operands in body_commands
            )
        ):
            continue

        outer_top = commands[contour_start][1][-1]
        outer_join = first_operands[-1]
        inner_join = starts[inner_curve_index]
        inner_top = inner_operands[-1]
        cap_end = shoulder_operands[-1]
        if inner_join is None:
            continue

        outer_vector = _subtract(outer_join, outer_top)
        inner_vector = _subtract(inner_top, inner_join)
        outer_direction = _unit(outer_vector)
        inner_direction = _unit(inner_vector)
        lower_vector = _subtract(inner_join, outer_join)
        across = _unit(lower_vector)
        outer_length = math.hypot(*outer_vector)
        inner_length = math.hypot(*inner_vector)
        width = math.hypot(*lower_vector)
        upper_cap_length = math.dist(cap_end, outer_top)
        shoulder_length = math.dist(inner_top, cap_end)
        first_tangent = _unit(_subtract(first_operands[0], outer_top))
        inner_tangent = _unit(_subtract(inner_top, inner_operands[1]))
        shoulder_tangent = _unit(_subtract(shoulder_operands[0], inner_top))
        cap_direction = _unit(_subtract(outer_top, cap_end))
        if (
            outer_direction is None
            or inner_direction is None
            or across is None
            or first_tangent is None
            or inner_tangent is None
            or shoulder_tangent is None
            or cap_direction is None
            or not 40 <= width <= 140
            or outer_length < 120
            or inner_length < 120
            or outer_direction[0] > -0.12
            or outer_direction[1] > -0.55
            or _dot(outer_direction, _scale(inner_direction, -1)) < 0.72
            or across[0] < 0.55
            or not 45 <= upper_cap_length <= 180
            or not 15 <= shoulder_length <= 1.5 * width
            or abs(outer_join[1] - inner_join[1]) > 0.6 * width
            or abs(outer_top[1] - cap_end[1]) > 0.9 * width
            or _dot(first_tangent, outer_direction) < 0.55
            or _dot(inner_tangent, inner_direction) < 0.45
            or _dot(shoulder_tangent, across) < 0.25
            or _dot(cap_direction, across) > -0.45
        ):
            continue
        elements.append(
            _LeftSweepStartElement(
                contour_start,
                contour_end,
                first_curve_index,
                inner_curve_index,
                shoulder_curve_index,
                outer_top,
                outer_join,
                inner_join,
                inner_top,
            )
        )
    return tuple(elements)


def _left_sweep_start_command_edits(
    commands: list[Command],
    element: _LeftSweepStartElement,
) -> tuple[_CommandEdit, ...]:
    """Split the selected B cap from the preserved lower contour body."""

    starts = _command_starts(commands)
    outer_axis = _subtract(element.outer_top, element.outer_join)
    inner_axis = _subtract(element.inner_top, element.inner_join)

    def point(x: float, y: float) -> Point:
        outer_height = (y - 616.0) / 223.0
        inner_height = (y - 616.0) / 177.0
        reference_outer_x = 347.0 + 59.0 * outer_height
        reference_inner_x = 420.0 + 56.0 * inner_height
        across = (x - reference_outer_x) / (reference_inner_x - reference_outer_x)
        outer_point = _add(element.outer_join, _scale(outer_axis, outer_height))
        inner_point = _add(element.inner_join, _scale(inner_axis, inner_height))
        return _lerp(outer_point, inner_point, across)

    outer_base = point(347, 560)
    inner_base = point(420, 560)
    selected_b: tuple[Command, ...] = (
        ("moveTo", (outer_base,)),
        ("lineTo", (point(347, 616),)),
        (
            "curveTo",
            (point(350, 626), point(353, 636), point(356, 645)),
        ),
        (
            "curveTo",
            (point(376, 708), point(391, 791), point(392, 846)),
        ),
        (
            "curveTo",
            (point(509, 819), point(509, 809), point(490, 801)),
        ),
        ("lineTo", (point(471, 793),)),
        (
            "curveTo",
            (point(461, 736), point(443, 676), point(420, 616)),
        ),
        ("lineTo", (inner_base,)),
        ("closePath", ()),
    )

    reversed_body: list[Command] = []
    for command_index in range(
        element.inner_curve_index - 1,
        element.first_curve_index,
        -1,
    ):
        operator, operands = commands[command_index]
        start = starts[command_index]
        if start is None:
            raise ValueError("Closed left-sweep body command has no start")
        if operator == "lineTo":
            reversed_body.append(("lineTo", (start,)))
        else:
            reversed_body.append(("curveTo", (operands[1], operands[0], start)))

    inner_offset = _subtract(inner_base, element.inner_join)
    first_operator, first_operands = reversed_body[0]
    if first_operator == "curveTo":
        reversed_body[0] = (
            first_operator,
            (
                _add(first_operands[0], inner_offset),
                first_operands[1],
                first_operands[2],
            ),
        )

    outer_offset = _subtract(outer_base, element.outer_join)
    last_operator, last_operands = reversed_body[-1]
    if last_operator == "curveTo":
        reversed_body[-1] = (
            last_operator,
            (
                last_operands[0],
                _add(last_operands[1], outer_offset),
                outer_base,
            ),
        )
    else:
        reversed_body[-1] = (last_operator, (outer_base,))

    replacement = selected_b + (
        ("moveTo", (inner_base,)),
        *reversed_body,
        ("closePath", ()),
    )
    return (
        _CommandEdit(
            element.contour_move_index,
            element.contour_close_index - element.contour_move_index + 1,
            replacement,
        ),
    )


def _apply_command_edits(
    commands: list[Command],
    edits: tuple[_CommandEdit, ...],
) -> pathops.Path:
    """Apply non-overlapping insertion, deletion, and replacement recipes."""

    ordered = sorted(edits, key=lambda edit: edit.command_index)
    edited = pathops.Path()
    pen = edited.getPen()
    cursor = 0
    for edit in ordered:
        end = edit.command_index + edit.delete_count
        if (
            edit.command_index < cursor
            or edit.command_index > len(commands)
            or edit.delete_count < 0
            or end > len(commands)
        ):
            raise ValueError(
                "Brush element command edits overlap or exceed the outline"
            )
        for operator, operands in commands[cursor : edit.command_index]:
            getattr(pen, operator)(*operands)
        for operator, operands in edit.replacement:
            getattr(pen, operator)(*operands)
        cursor = end
    for operator, operands in commands[cursor:]:
        getattr(pen, operator)(*operands)
    return edited


def apply_brush_elements(
    outline: pathops.Path,
    style: BrushElementStyle = DEFAULT_BRUSH_ELEMENT_STYLE,
) -> BrushElementResult:
    """Match and edit localized stem, uroko, and curved terminal elements.

    Stem bodies remain straight. Independently recognized start and end regions
    receive pressure curves; recognizing one never implies the other. Recognized
    horizontal starts receive pressure transitions, uroko curves are softened,
    sweep caps are rounded by splitting their existing adjacent curves, and
    hook caps receive the selected B curve recipe in their local basis.
    """

    recording = RecordingPen()
    outline.draw(recording)
    commands: list[Command] = list(recording.value)
    vertical_start_elements = _vertical_start_elements(commands)
    edits: list[_CommandEdit] = []
    uroko_elements = _uroko_elements(commands)
    terminal_elements = _terminal_elements(commands)
    horizontal_start_elements = _horizontal_start_elements(commands)
    fold_elements = _fold_elements(commands)
    box_elements = _box_elements(commands)
    vertical_end_elements = _vertical_end_elements(commands)
    left_sweep_start_candidates = _left_sweep_start_elements(commands)
    left_sweep_start_command_indices = frozenset(
        command_index
        for element in left_sweep_start_candidates
        for command_index in element.command_indices
    )
    box_command_indices = frozenset(
        command_index
        for element in box_elements
        for command_index in element.command_indices
    )
    vertical_excluded_command_indices = (
        box_command_indices | left_sweep_start_command_indices
    )

    vertical_start_elements = tuple(
        element
        for element in vertical_start_elements
        if vertical_excluded_command_indices.isdisjoint(
            element.side_command_indices
            | frozenset(
                range(
                    element.first_cap_index,
                    element.first_cap_index + element.cap_command_count,
                )
            )
        )
    )
    vertical_start_elements = tuple(
        start
        for start in vertical_start_elements
        if all(
            _vertical_start_command_indices(start).isdisjoint(
                _terminal_command_indices(terminal)
            )
            or _supported_start_terminal_overlap(commands, start, terminal)
            for terminal in terminal_elements
        )
    )
    vertical_start_elements = tuple(
        start
        for start in vertical_start_elements
        if all(
            start.side_command_indices == end.side_command_indices
            or start.side_command_indices.isdisjoint(end.side_command_indices)
            for end in vertical_end_elements
        )
    )
    vertical_end_elements = tuple(
        element
        for element in vertical_end_elements
        if vertical_excluded_command_indices.isdisjoint(
            element.side_command_indices
            | frozenset(
                range(
                    element.first_cap_index,
                    element.first_cap_index + element.cap_command_count,
                )
            )
        )
    )
    vertical_start_by_pair = {
        element.side_command_indices: element for element in vertical_start_elements
    }
    vertical_end_by_pair = {
        element.side_command_indices: element for element in vertical_end_elements
    }
    vertical_pair_command_indices = tuple(
        dict.fromkeys((*vertical_start_by_pair, *vertical_end_by_pair))
    )
    uroko_command_indices = {
        command_index
        for element in uroko_elements
        for command_index in (element.first_curve_index, element.second_curve_index)
    }
    terminal_elements = tuple(
        element
        for element in terminal_elements
        if uroko_command_indices.isdisjoint(
            {
                element.incoming_curve_index,
                element.cap_line_index,
                element.outgoing_curve_index,
            }
        )
    )
    shared_terminal_by_down_command = {
        start.down_side.command_index: terminal
        for start in vertical_start_elements
        for terminal in terminal_elements
        if _supported_start_terminal_overlap(commands, start, terminal)
    }
    for element in fold_elements:
        edits.append(
            _CommandEdit(
                element.incoming_curve_index,
                3,
                _edit_fold(element),
            )
        )
    for element in box_elements:
        edits.extend(_box_command_edits(element))
    uroko_designs = {element: _uroko_design(element) for element in uroko_elements}
    uroko_preceding_lines = {
        element.preceding_line_index: uroko_designs[element][0]
        for element in uroko_elements
    }
    horizontal_start_outgoing_lines = {
        element.outgoing_line_index for element in horizontal_start_elements
    }
    for element in horizontal_start_elements:
        edits.extend(
            _horizontal_start_command_edits(
                element,
                uroko_preceding_lines.get(element.outgoing_line_index),
            )
        )
    for element in terminal_elements:
        if element.incoming_curve_index not in shared_terminal_by_down_command:
            edits.extend(_terminal_command_edits(element, commands, style))
    for element in uroko_elements:
        upper_cut, lower_cut, replacement = uroko_designs[element]
        if element.preceding_line_index not in horizontal_start_outgoing_lines:
            edits.append(
                _CommandEdit(
                    element.preceding_line_index,
                    1,
                    (("lineTo", (upper_cut,)),),
                )
            )
        delete_count = 2 if element.contour_move_index is not None else 3
        edits.append(
            _CommandEdit(
                element.first_curve_index,
                delete_count,
                replacement,
            )
        )
        if element.contour_move_index is not None:
            edits.append(
                _CommandEdit(
                    element.contour_move_index,
                    1,
                    (("moveTo", (lower_cut,)),),
                )
            )
            edits.append(_CommandEdit(element.following_line_index, 1, ()))
    adjusted_vertical_stroke_count = 0
    for side_command_indices in vertical_pair_command_indices:
        start = vertical_start_by_pair.get(side_command_indices)
        end = vertical_end_by_pair.get(side_command_indices)
        if start is None and end is None:
            continue
        element = start if start is not None else end
        if element is None:
            raise AssertionError("Matched vertical element unexpectedly missing")
        start_scale, end_scale = _vertical_design_scales(start, end)
        start_design = (
            _vertical_start_design(start, start_scale) if start is not None else None
        )
        end_design = _vertical_end_design(end, end_scale) if end is not None else None
        side_edits = _vertical_stroke_side_edits(
            element,
            start_design,
            end_design,
            commands,
        )
        shared_terminal = (
            shared_terminal_by_down_command.get(start.down_side.command_index)
            if start is not None
            else None
        )
        if shared_terminal is None:
            edits.extend(side_edits)
        else:
            assert start is not None
            down_edit = next(
                edit
                for edit in side_edits
                if edit.command_index == start.down_side.command_index
            )
            edits.extend(edit for edit in side_edits if edit is not down_edit)
            edits.append(
                _combined_vertical_start_terminal_edit(
                    down_edit,
                    shared_terminal,
                    commands,
                    style,
                )
            )
        if start is not None and start_design is not None:
            if start.contour_move_index is not None:
                edits.append(
                    _CommandEdit(
                        start.contour_move_index,
                        1,
                        (("moveTo", (start_design.left_apex,)),),
                    )
                )
                if start.post_move_cap_count:
                    edits.append(
                        _CommandEdit(
                            start.contour_move_index + 1,
                            start.post_move_cap_count,
                            (),
                        )
                    )
            edits.append(
                _CommandEdit(
                    start.first_cap_index,
                    start.cap_command_count,
                    _edit_vertical_start_cap(start_design),
                )
            )
        if end is not None and end_design is not None:
            edits.append(
                _CommandEdit(
                    end.first_cap_index,
                    end.cap_command_count,
                    _edit_vertical_end_cap(end_design),
                )
            )
        adjusted_vertical_stroke_count += 1
    occupied_command_indices = {
        command_index
        for edit in edits
        for command_index in range(
            edit.command_index,
            edit.command_index + max(1, edit.delete_count),
        )
    }
    left_sweep_start_elements: list[_LeftSweepStartElement] = []
    for element in left_sweep_start_candidates:
        if occupied_command_indices.isdisjoint(element.command_indices):
            edits.extend(_left_sweep_start_command_edits(commands, element))
            left_sweep_start_elements.append(element)
            occupied_command_indices.update(element.command_indices)
    if not edits:
        return BrushElementResult(pathops.Path(outline), 0, 0, 0, 0)
    return BrushElementResult(
        _apply_command_edits(commands, tuple(edits)),
        adjusted_vertical_stroke_count + len(horizontal_start_elements),
        len(uroko_elements),
        len(terminal_elements),
        len(fold_elements) + 3 * len(box_elements) + len(left_sweep_start_elements),
    )


def apply_han_brush_elements(font: TTFont) -> HanBrushResult:
    """Apply matched brush-element edits to every encoded or reachable Han form."""

    if "CFF " not in font:
        raise ValueError("Han brush elements require an OpenType/CFF source")
    plan = collect_novel_han_glyphs(font)
    modified_count = 0
    adjusted_stroke_count = adjusted_uroko_count = 0
    adjusted_terminal_count = adjusted_corner_count = 0
    for name in plan.target_glyphs:
        outline = geometry.glyph_path(font, name)
        if not outline.verbs:
            raise ValueError(f"Han glyph {name!r} has an empty outline")
        result = apply_brush_elements(outline)
        if result.adjusted_element_count == 0:
            continue
        vertical_origin = 0
        if "vmtx" in font:
            vertical_metrics = cast(
                Mapping[str, tuple[int, int]],
                getattr(font["vmtx"], "metrics"),
            )
            vertical_origin = round(vertical_metrics[name][1] + outline.bounds[3])
        operations.replace_cff_glyph(
            font,
            name,
            result.path,
            vertical_origin,
            left_side_bearing_override=font["hmtx"].metrics[name][1],
        )
        modified_count += 1
        adjusted_stroke_count += result.adjusted_stroke_count
        adjusted_uroko_count += result.adjusted_uroko_count
        adjusted_terminal_count += result.adjusted_terminal_count
        adjusted_corner_count += result.adjusted_corner_count
    return HanBrushResult(
        target_count=len(plan.target_glyphs),
        modified_count=modified_count,
        adjusted_stroke_count=adjusted_stroke_count,
        adjusted_uroko_count=adjusted_uroko_count,
        adjusted_terminal_count=adjusted_terminal_count,
        adjusted_corner_count=adjusted_corner_count,
    )
