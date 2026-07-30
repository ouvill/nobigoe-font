"""Inventory and convex tapering for Noto-derived kana stroke terminals.

The detector is geometric rather than glyph-name based. It records every
one-to-three segment hard cap it can identify, including caps that cannot be
changed safely. Static ``pathops`` outlines may replace a cap with a cubic;
TrueType ``glyf`` outlines are edited by moving existing points and handles
only, so their interpolation topology remains unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import math
from typing import Iterable, Literal, Protocol, TypeAlias

import pathops
from fontTools.pens.recordingPen import RecordingPen

Point: TypeAlias = tuple[float, float]
TerminalCandidateId: TypeAlias = tuple[int, tuple[int, ...]]
TerminalStatus: TypeAlias = Literal["eligible", "adjusted", "rejected", "unresolved"]
TerminalDirection: TypeAlias = Literal["unknown"]

_MIN_CAP_LENGTH = 2.0
_MAX_CAP_LENGTH = 160.0
_MAX_CAP_SEGMENTS = 3
_MAX_CAP_POLYLINE_RATIO = 1.08
_MAX_TANGENT_DOT = -0.50
_MAX_AXIS_DOT = 0.70
_BOUNDARY_HANDLE_RATIO = 0.30
_TAPER_DEPTH_RATIO = 0.18
_GEOMETRY_EPSILON = 1e-9
_LEGACY_MIN_CAP_LENGTH = 3.0
_LEGACY_MAX_CAP_LENGTH = 45.0
_LEGACY_MAX_TANGENT_DOT = -0.65
_LEGACY_MAX_AXIS_DOT = 0.55
_LEGACY_LONG_SWEEP_HANDLE_RATIO = 4.0
_LEGACY_REGULAR_NOSE_RATIO = 0.18
_LEGACY_LONG_SWEEP_NOSE_RATIO = 0.14
_ON_CURVE = 0x01
_UNION_OVERRIDABLE_REASONS = frozenset(
    {
        "cap-length-out-of-range",
        "side-tangents-not-opposed",
        "cap-parallel-to-stroke",
        "non-monotonic-taper-projection",
        "non-convex-taper-curvature",
    }
)


class SimpleGlyfGlyph(Protocol):
    """Simple-glyph data needed by :func:`taper_glyf_terminals`."""

    numberOfContours: int
    coordinates: object
    flags: Iterable[int]
    endPtsOfContours: Iterable[int]


@dataclass(frozen=True)
class TerminalCandidate:
    """Stable public metadata for one structurally detected hard cap.

    ``contour_index`` and ``segment_index`` are zero-based. ``point_indices``
    are the cap's existing on-curve points (or path segment indices) in
    contour order and, with the contour, form the cross-master identity.
    ``normalized_midpoint`` is normalized to the outline bounds, while
    ``normalized_axis`` is a unit vector in contour order. A closed outline
    cannot reveal brush traversal, so ``entry_or_exit`` is deliberately and
    truthfully ``"unknown"``.

    ``status`` is ``"eligible"`` for a safe inventory-only candidate,
    ``"adjusted"`` after tapering, ``"rejected"`` for geometry known not to
    be an exterior stroke cap, or ``"unresolved"`` when a safety proof fails.
    """

    contour_index: int
    segment_index: int
    segment_count: int
    point_indices: tuple[int, ...]
    normalized_midpoint: Point
    normalized_axis: Point
    entry_or_exit: TerminalDirection
    status: TerminalStatus
    reason: str | None

    @property
    def candidate_id(self) -> TerminalCandidateId:
        """Return the topology-stable identity used to union variable masters."""

        return self.contour_index, self.point_indices


@dataclass(frozen=True)
class TerminalInventory:
    """Ordered terminal candidates, including every unsafe candidate."""

    candidates: tuple[TerminalCandidate, ...]

    @property
    def adjusted(self) -> tuple[TerminalCandidate, ...]:
        """Return candidates whose outlines were changed."""

        return tuple(item for item in self.candidates if item.status == "adjusted")

    @property
    def rejected(self) -> tuple[TerminalCandidate, ...]:
        """Return candidates proven not to be safe exterior terminals."""

        return tuple(item for item in self.candidates if item.status == "rejected")

    @property
    def unresolved(self) -> tuple[TerminalCandidate, ...]:
        """Return candidates retained because a geometry gate was inconclusive."""

        return tuple(item for item in self.candidates if item.status == "unresolved")

    @property
    def eligible(self) -> tuple[TerminalCandidate, ...]:
        """Return safe candidates from a non-mutating inventory pass."""

        return tuple(item for item in self.candidates if item.status == "eligible")

    @property
    def detected_count(self) -> int:
        """Number of structurally detected hard-cap candidates."""

        return len(self.candidates)

    @property
    def adjusted_count(self) -> int:
        """Number of adjusted terminals."""

        return len(self.adjusted)

    @property
    def rejected_count(self) -> int:
        """Number of rejected terminals."""

        return len(self.rejected)

    @property
    def unresolved_count(self) -> int:
        """Number of unresolved terminals."""

        return len(self.unresolved)

    @property
    def safe_count(self) -> int:
        """Number of eligible or already adjusted terminals."""

        return len(self.eligible) + len(self.adjusted)

    @property
    def unsafe_count(self) -> int:
        """Number of rejected or unresolved terminals."""

        return len(self.rejected) + len(self.unresolved)


@dataclass(frozen=True)
class PathTerminalResult:
    """A copied static outline and the disposition of all detected caps."""

    path: pathops.Path
    inventory: TerminalInventory

    @property
    def outline(self) -> pathops.Path:
        """Alias for callers that describe a path as an outline."""

        return self.path

    @property
    def adjusted_count(self) -> int:
        """Number of terminals changed in :attr:`path`."""

        return self.inventory.adjusted_count

    @property
    def rejected_count(self) -> int:
        """Number of detected candidates rejected as non-terminals."""

        return self.inventory.rejected_count

    @property
    def unresolved_count(self) -> int:
        """Number of detected candidates left unchanged for safety."""

        return self.inventory.unresolved_count

    @property
    def detected_count(self) -> int:
        """Number of structurally detected candidates."""

        return self.inventory.detected_count

    @property
    def safe_count(self) -> int:
        """Number of adjusted terminals."""

        return self.inventory.safe_count

    @property
    def unsafe_count(self) -> int:
        """Number of rejected or unresolved terminals."""

        return self.inventory.unsafe_count


@dataclass(frozen=True)
class GlyfTerminalResult:
    """A point-compatible glyph clone and its complete terminal inventory."""

    glyph: SimpleGlyfGlyph
    inventory: TerminalInventory

    @property
    def adjusted_count(self) -> int:
        """Number of terminals changed in :attr:`glyph`."""

        return self.inventory.adjusted_count

    @property
    def rejected_count(self) -> int:
        """Number of detected candidates rejected as non-terminals."""

        return self.inventory.rejected_count

    @property
    def unresolved_count(self) -> int:
        """Number of detected candidates left unchanged for safety."""

        return self.inventory.unresolved_count

    @property
    def detected_count(self) -> int:
        """Number of structurally detected candidates."""

        return self.inventory.detected_count

    @property
    def safe_count(self) -> int:
        """Number of adjusted terminals."""

        return self.inventory.safe_count

    @property
    def unsafe_count(self) -> int:
        """Number of rejected or unresolved terminals."""

        return self.inventory.unsafe_count


@dataclass(frozen=True)
class _Geometry:
    record: TerminalCandidate
    cap_points: tuple[Point, ...]
    previous_control: Point
    next_control: Point
    outward: Point | None
    cubic: tuple[Point, Point, Point, Point] | None
    source_indices: tuple[int, ...]


@dataclass(frozen=True)
class _PathContour:
    command_indices: tuple[int, ...]
    closed: bool
    signed_area: float


def _subtract(left: Point, right: Point) -> Point:
    return left[0] - right[0], left[1] - right[1]


def _add(left: Point, right: Point) -> Point:
    return left[0] + right[0], left[1] + right[1]


def _scale(point: Point, factor: float) -> Point:
    return point[0] * factor, point[1] * factor


def _dot(left: Point, right: Point) -> float:
    return left[0] * right[0] + left[1] * right[1]


def _cross(left: Point, right: Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _unit(vector: Point) -> Point | None:
    length = math.hypot(*vector)
    if not math.isfinite(length) or length <= _GEOMETRY_EPSILON:
        return None
    return vector[0] / length, vector[1] / length


def _all_finite(points: Iterable[Point]) -> bool:
    return all(math.isfinite(value) for point in points for value in point)


def _signed_area(points: Iterable[Point]) -> float:
    values = tuple(points)
    if len(values) < 3 or not _all_finite(values):
        return math.nan
    shifted = (*values[1:], values[0])
    return (
        sum(
            left[0] * right[1] - right[0] * left[1]
            for left, right in zip(values, shifted, strict=True)
        )
        / 2
    )


def _bounds(points: Iterable[Point]) -> tuple[float, float, float, float]:
    values = tuple(points)
    finite = tuple(point for point in values if _all_finite((point,)))
    if not finite:
        return 0.0, 0.0, 0.0, 0.0
    return (
        min(point[0] for point in finite),
        min(point[1] for point in finite),
        max(point[0] for point in finite),
        max(point[1] for point in finite),
    )


def _normalize_midpoint(
    midpoint: Point, bounds: tuple[float, float, float, float]
) -> Point:
    x_min, y_min, x_max, y_max = bounds
    width = x_max - x_min
    height = y_max - y_min
    return (
        (midpoint[0] - x_min) / width if width > _GEOMETRY_EPSILON else 0.5,
        (midpoint[1] - y_min) / height if height > _GEOMETRY_EPSILON else 0.5,
    )


def _polyline_is_near_straight(points: tuple[Point, ...]) -> bool:
    direct = math.dist(points[0], points[-1])
    if not math.isfinite(direct) or direct <= _GEOMETRY_EPSILON:
        return False
    length = sum(math.dist(left, right) for left, right in zip(points, points[1:]))
    return math.isfinite(length) and length <= direct * _MAX_CAP_POLYLINE_RATIO


def _quadratic_values_at_extrema(
    quadratic: float, linear: float, constant: float
) -> tuple[float, ...]:
    values = [constant, quadratic + linear + constant]
    if abs(quadratic) > _GEOMETRY_EPSILON:
        extremum = -linear / (2 * quadratic)
        if 0.0 < extremum < 1.0:
            values.append(
                quadratic * extremum * extremum + linear * extremum + constant
            )
    return tuple(values)


def _cubic_has_monotonic_projection(cubic: tuple[Point, Point, Point, Point]) -> bool:
    """Prove monotonic cap-axis projection from exact derivative extrema."""

    start, control_1, control_2, end = cubic
    axis = _unit(_subtract(end, start))
    if axis is None:
        return False
    projections = tuple(_dot(point, axis) for point in cubic)
    derivative_quadratic = 3 * (
        -projections[0] + 3 * projections[1] - 3 * projections[2] + projections[3]
    )
    derivative_linear = 6 * (projections[0] - 2 * projections[1] + projections[2])
    derivative_constant = 3 * (projections[1] - projections[0])
    values = _quadratic_values_at_extrema(
        derivative_quadratic,
        derivative_linear,
        derivative_constant,
    )
    return (
        _all_finite(((value, 0.0) for value in values))
        and min(values) >= -_GEOMETRY_EPSILON
    )


def _cubic_has_single_curvature_sign(cubic: tuple[Point, Point, Point, Point]) -> bool:
    """Prove analytically that the cubic has no inflection on ``[0, 1]``."""

    point_0, point_1, point_2, point_3 = cubic
    coefficient_a = (
        -point_0[0] + 3 * point_1[0] - 3 * point_2[0] + point_3[0],
        -point_0[1] + 3 * point_1[1] - 3 * point_2[1] + point_3[1],
    )
    coefficient_b = (
        3 * point_0[0] - 6 * point_1[0] + 3 * point_2[0],
        3 * point_0[1] - 6 * point_1[1] + 3 * point_2[1],
    )
    coefficient_c = (
        -3 * point_0[0] + 3 * point_1[0],
        -3 * point_0[1] + 3 * point_1[1],
    )
    curvature_quadratic = -6 * _cross(coefficient_a, coefficient_b)
    curvature_linear = 6 * _cross(coefficient_c, coefficient_a)
    curvature_constant = 2 * _cross(coefficient_c, coefficient_b)
    values = _quadratic_values_at_extrema(
        curvature_quadratic,
        curvature_linear,
        curvature_constant,
    )
    if not all(math.isfinite(value) for value in values):
        return False
    return min(values) > _GEOMETRY_EPSILON or max(values) < -_GEOMETRY_EPSILON


def _classify_geometry(
    *,
    contour_index: int,
    segment_index: int,
    point_indices: tuple[int, ...],
    cap_points: tuple[Point, ...],
    previous_control: Point,
    next_control: Point,
    contour_area: float,
    outline_bounds: tuple[float, float, float, float],
    source_indices: tuple[int, ...],
) -> _Geometry:
    midpoint = (
        (cap_points[0][0] + cap_points[-1][0]) / 2,
        (cap_points[0][1] + cap_points[-1][1]) / 2,
    )
    axis = _unit(_subtract(cap_points[-1], cap_points[0]))
    base = TerminalCandidate(
        contour_index=contour_index,
        segment_index=segment_index,
        segment_count=len(cap_points) - 1,
        point_indices=point_indices,
        normalized_midpoint=_normalize_midpoint(midpoint, outline_bounds),
        normalized_axis=axis if axis is not None else (0.0, 0.0),
        entry_or_exit="unknown",
        status="unresolved",
        reason=None,
    )
    all_points = (*cap_points, previous_control, next_control)
    if not _all_finite(all_points):
        return _Geometry(
            replace(base, reason="non-finite-geometry"),
            cap_points,
            previous_control,
            next_control,
            None,
            None,
            source_indices,
        )
    if axis is None:
        return _Geometry(
            replace(base, reason="degenerate-cap-axis"),
            cap_points,
            previous_control,
            next_control,
            None,
            None,
            source_indices,
        )
    if not _polyline_is_near_straight(cap_points):
        return _Geometry(
            replace(base, status="rejected", reason="cap-is-not-near-straight"),
            cap_points,
            previous_control,
            next_control,
            None,
            None,
            source_indices,
        )

    incoming = _unit(_subtract(cap_points[0], previous_control))
    outgoing = _unit(_subtract(next_control, cap_points[-1]))
    if incoming is None or outgoing is None:
        return _Geometry(
            replace(base, reason="degenerate-side-tangent"),
            cap_points,
            previous_control,
            next_control,
            None,
            None,
            source_indices,
        )
    tangent_dot = _dot(incoming, outgoing)
    outward = _unit(_subtract(incoming, outgoing))
    if outward is None:
        return _Geometry(
            replace(base, reason="ambiguous-outward-direction"),
            cap_points,
            previous_control,
            next_control,
            None,
            None,
            source_indices,
        )
    axis_dot = abs(_dot(outward, axis))
    if not math.isfinite(contour_area) or abs(contour_area) <= _GEOMETRY_EPSILON:
        return _Geometry(
            replace(base, reason="ambiguous-contour-orientation"),
            cap_points,
            previous_control,
            next_control,
            outward,
            None,
            source_indices,
        )
    left_normal = (-axis[1], axis[0])
    material_normal = _scale(left_normal, math.copysign(1.0, contour_area))
    outward_projection = _dot(outward, material_normal)
    if outward_projection >= _GEOMETRY_EPSILON:
        return _Geometry(
            replace(base, status="rejected", reason="inward-counter-seam"),
            cap_points,
            previous_control,
            next_control,
            outward,
            None,
            source_indices,
        )
    if outward_projection > -_GEOMETRY_EPSILON:
        return _Geometry(
            replace(base, reason="ambiguous-fill-side"),
            cap_points,
            previous_control,
            next_control,
            outward,
            None,
            source_indices,
        )

    cap_length = math.dist(cap_points[0], cap_points[-1])
    handle_length = cap_length * _BOUNDARY_HANDLE_RATIO
    cubic = (
        cap_points[0],
        _add(cap_points[0], _scale(incoming, handle_length)),
        _subtract(cap_points[-1], _scale(outgoing, handle_length)),
        cap_points[-1],
    )
    if not _all_finite(cubic):
        status = replace(base, reason="non-finite-taper")
    elif not _cubic_has_monotonic_projection(cubic):
        status = replace(base, reason="non-monotonic-taper-projection")
    elif not _cubic_has_single_curvature_sign(cubic):
        status = replace(base, reason="non-convex-taper-curvature")
    elif not _MIN_CAP_LENGTH <= cap_length <= _MAX_CAP_LENGTH:
        status = replace(base, status="rejected", reason="cap-length-out-of-range")
    elif tangent_dot >= _MAX_TANGENT_DOT:
        status = replace(base, status="rejected", reason="side-tangents-not-opposed")
    elif axis_dot >= _MAX_AXIS_DOT:
        status = replace(base, status="rejected", reason="cap-parallel-to-stroke")
    else:
        status = replace(base, status="eligible", reason=None)
    return _Geometry(
        status,
        cap_points,
        previous_control,
        next_control,
        outward,
        cubic,
        source_indices,
    )


def _record_path(
    outline: pathops.Path,
) -> tuple[list[tuple[str, tuple[Point, ...]]], tuple[_PathContour, ...], set[int]]:
    recording = RecordingPen()
    outline.draw(recording)
    commands = list(recording.value)
    contours: list[_PathContour] = []
    open_indices: set[int] = set()
    command_indices: list[int] = []
    endpoints: list[Point] = []
    subpath_start: int | None = None
    for index, (operator, operands) in enumerate(commands):
        if operator == "moveTo":
            if subpath_start is not None:
                open_indices.update(range(subpath_start, index))
            command_indices = []
            endpoints = [operands[-1]]
            subpath_start = index
        elif operator in ("closePath", "endPath"):
            closed = operator == "closePath"
            if command_indices:
                contours.append(
                    _PathContour(
                        tuple(command_indices),
                        closed,
                        _signed_area(endpoints) if closed else math.nan,
                    )
                )
            if not closed and subpath_start is not None:
                open_indices.update(range(subpath_start, index + 1))
            command_indices = []
            endpoints = []
            subpath_start = None
        elif subpath_start is not None:
            command_indices.append(index)
            endpoints.append(operands[-1])
    if command_indices:
        contours.append(_PathContour(tuple(command_indices), False, math.nan))
    if subpath_start is not None:
        open_indices.update(range(subpath_start, len(commands)))
    return commands, tuple(contours), open_indices


def _path_geometries(
    outline: pathops.Path,
) -> tuple[
    list[tuple[str, tuple[Point, ...]]],
    tuple[_Geometry, ...],
    set[int],
]:
    commands, contours, open_indices = _record_path(outline)
    all_points = tuple(
        point
        for _, operands in commands
        for point in operands
        if isinstance(point, tuple) and len(point) == 2
    )
    outline_bounds = _bounds(all_points)
    geometries: list[_Geometry] = []
    for contour_index, contour in enumerate(contours):
        if not contour.closed:
            continue
        indices = contour.command_indices
        count = len(indices)
        for position, command_index in enumerate(indices):
            operator, operands = commands[command_index]
            if operator != "curveTo":
                continue
            line_positions: list[int] = []
            cursor = (position + 1) % count
            while cursor != position and commands[indices[cursor]][0] == "lineTo":
                line_positions.append(cursor)
                cursor = (cursor + 1) % count
            if (
                not line_positions
                or len(line_positions) > _MAX_CAP_SEGMENTS
                or commands[indices[cursor]][0] != "curveTo"
            ):
                continue
            line_indices = tuple(indices[item] for item in line_positions)
            cap_points = (operands[-1],) + tuple(
                commands[index][1][-1] for index in line_indices
            )
            next_operands = commands[indices[cursor]][1]
            cap_point_positions = (
                position,
                *line_positions,
            )
            geometries.append(
                _classify_geometry(
                    contour_index=contour_index,
                    segment_index=line_positions[0],
                    point_indices=cap_point_positions,
                    cap_points=cap_points,
                    previous_control=operands[-2],
                    next_control=next_operands[0],
                    contour_area=contour.signed_area,
                    outline_bounds=outline_bounds,
                    source_indices=line_indices,
                )
            )
    geometries.sort(
        key=lambda item: (item.record.contour_index, item.record.segment_index)
    )
    return commands, tuple(geometries), open_indices


def inventory_path_terminals(outline: pathops.Path) -> TerminalInventory:
    """Return a non-mutating inventory of static-outline cap candidates."""

    _, geometries, _ = _path_geometries(outline)
    return TerminalInventory(tuple(item.record for item in geometries))


def taper_path_terminals(outline: pathops.Path) -> PathTerminalResult:
    """Return a copied path whose safe hard caps are single convex cubics.

    Replacing a line chain is appropriate for static CFF production. The
    analytic gates guarantee finite geometry, monotonic projection along the
    cap axis, and curvature with one strict sign. Rejected and unresolved
    candidates remain geometrically unchanged and remain visible in metadata.
    """

    commands, geometries, open_indices = _path_geometries(outline)
    adjusted = tuple(
        geometry for geometry in geometries if geometry.record.status == "eligible"
    )
    records = tuple(
        (
            replace(geometry.record, status="adjusted")
            if geometry.record.status == "eligible"
            else geometry.record
        )
        for geometry in geometries
    )
    if not adjusted:
        return PathTerminalResult(pathops.Path(outline), TerminalInventory(records))

    replacements = {
        geometry.source_indices[0]: geometry.cubic[1:]
        for geometry in adjusted
        if geometry.cubic is not None
    }
    skipped = {index for geometry in adjusted for index in geometry.source_indices[1:]}
    tapered = pathops.Path()
    pen = tapered.getPen()
    for index, (operator, operands) in enumerate(commands):
        if index in replacements:
            pen.curveTo(*replacements[index])
        elif index not in skipped and index not in open_indices:
            getattr(pen, operator)(*operands)
    return PathTerminalResult(tapered, TerminalInventory(records))


def _glyf_contours(glyph: SimpleGlyfGlyph) -> tuple[tuple[int, ...], ...]:
    if getattr(glyph, "numberOfContours", 0) <= 0:
        return ()
    contours: list[tuple[int, ...]] = []
    start = 0
    for raw_end in glyph.endPtsOfContours:
        end = int(raw_end)
        contours.append(tuple(range(start, end + 1)))
        start = end + 1
    return tuple(contours)


def _glyf_geometries(glyph: SimpleGlyfGlyph) -> tuple[_Geometry, ...]:
    contours = _glyf_contours(glyph)
    if not contours:
        return ()
    coordinates = tuple(
        (float(point[0]), float(point[1])) for point in glyph.coordinates
    )
    flags = tuple(int(flag) for flag in glyph.flags)
    if len(coordinates) != len(flags):
        return ()
    outline_bounds = _bounds(coordinates)
    geometries: list[_Geometry] = []
    for contour_index, contour in enumerate(contours):
        count = len(contour)
        if count < 4:
            continue
        contour_points = tuple(coordinates[index] for index in contour)
        contour_area = _signed_area(contour_points)
        for position, point_index in enumerate(contour):
            previous_position = (position - 1) % count
            if (
                not flags[point_index] & _ON_CURVE
                or flags[contour[previous_position]] & _ON_CURVE
            ):
                continue
            on_curve_positions = [position]
            cursor = (position + 1) % count
            while (
                cursor != position
                and flags[contour[cursor]] & _ON_CURVE
                and len(on_curve_positions) <= _MAX_CAP_SEGMENTS
            ):
                on_curve_positions.append(cursor)
                cursor = (cursor + 1) % count
            segment_count = len(on_curve_positions) - 1
            if (
                not 1 <= segment_count <= _MAX_CAP_SEGMENTS
                or flags[contour[cursor]] & _ON_CURVE
            ):
                continue
            cap_indices = tuple(contour[item] for item in on_curve_positions)
            cap_points = tuple(coordinates[index] for index in cap_indices)
            geometries.append(
                _classify_geometry(
                    contour_index=contour_index,
                    segment_index=position,
                    point_indices=cap_indices,
                    cap_points=cap_points,
                    previous_control=coordinates[contour[previous_position]],
                    next_control=coordinates[contour[cursor]],
                    contour_area=contour_area,
                    outline_bounds=outline_bounds,
                    source_indices=(
                        contour[previous_position],
                        *cap_indices,
                        contour[cursor],
                    ),
                )
            )
    geometries.sort(
        key=lambda item: (item.record.contour_index, item.record.segment_index)
    )
    return tuple(geometries)


def inventory_glyf_terminals(glyph: SimpleGlyfGlyph) -> TerminalInventory:
    """Return a non-mutating inventory of simple ``glyf`` cap candidates."""

    return TerminalInventory(tuple(item.record for item in _glyf_geometries(glyph)))


def _rounded(point: Point) -> Point:
    return float(round(point[0])), float(round(point[1]))


def _glyf_taper_points(
    geometry: _Geometry,
    taper_depth_ratio: float,
) -> dict[int, Point] | None:
    if geometry.outward is None:
        return None
    cap_indices = geometry.source_indices[1:-1]
    start = geometry.cap_points[0]
    end = geometry.cap_points[-1]
    axis = _unit(_subtract(end, start))
    if axis is None:
        return None
    transverse = _unit(
        _subtract(geometry.outward, _scale(axis, _dot(geometry.outward, axis)))
    )
    if transverse is None:
        return None
    cap_length = math.dist(start, end)
    midpoint = _scale(_add(start, end), 0.5)
    depth = max(cap_length * taper_depth_ratio, 1.0)
    tip = _rounded(_add(midpoint, _scale(transverse, depth)))
    segment_count = len(cap_indices) - 1
    if segment_count == 1:
        # A duplicate on-curve endpoint is an interpolation-compatible cusp.
        # Adjacent quadratic controls stay untouched, avoiding cross-terminal
        # handle ownership and preserving the source sides exactly.
        updates = {
            cap_indices[0]: tip,
            cap_indices[1]: tip,
        }
    else:
        # Keep both shoulders and converge every compatible interior point to
        # one tip, rather than replacing a long cut with a shorter flat cut.
        updates = {point_index: tip for point_index in cap_indices[1:-1]}

    if not _all_finite(updates.values()):
        return None
    adjusted_points = tuple(
        updates.get(index, point)
        for index, point in zip(cap_indices, geometry.cap_points, strict=True)
    )
    projections = tuple(_dot(point, axis) for point in adjusted_points)
    if any(
        right < left - _GEOMETRY_EPSILON
        for left, right in zip(projections, projections[1:])
    ):
        return None
    if segment_count >= 2:
        convex_points: list[Point] = []
        for point in adjusted_points:
            if not convex_points or convex_points[-1] != point:
                convex_points.append(point)
        turns = tuple(
            _cross(_subtract(middle, left), _subtract(right, middle))
            for left, middle, right in zip(
                convex_points,
                convex_points[1:],
                convex_points[2:],
            )
        )
        if not turns or not (
            min(turns) > _GEOMETRY_EPSILON or max(turns) < -_GEOMETRY_EPSILON
        ):
            return None
    return updates


def taper_glyf_terminals(
    glyph: SimpleGlyfGlyph,
    selected_candidate_ids: Iterable[TerminalCandidateId] | None = None,
    taper_depth_ratio: float = _TAPER_DEPTH_RATIO,
) -> GlyfTerminalResult:
    """Clone and taper a simple TrueType glyph without changing point topology.

    Existing on-curve points and adjacent quadratic handles are moved in
    place. Point count, contour endpoints, point flags, and point order are
    never changed, making the result suitable for corresponding edits in
    variable-font masters.

    When ``selected_candidate_ids`` is supplied, its topology identities can
    be the union of inventories from several masters. Selection may override
    only a narrowly missed heuristic threshold; finite, monotonic, curvature,
    and exterior-fill gates still apply independently in every master. This
    makes threshold-dependent membership reportable without varying topology.
    """

    tapered = deepcopy(glyph)
    geometries = _glyf_geometries(glyph)
    selected = (
        None if selected_candidate_ids is None else frozenset(selected_candidate_ids)
    )
    records_by_id: dict[TerminalCandidateId, TerminalCandidate] = {}
    proposals: dict[
        TerminalCandidateId,
        tuple[_Geometry, dict[int, Point], bool],
    ] = {}
    found_ids: set[TerminalCandidateId] = set()
    for geometry in geometries:
        candidate_id = geometry.record.candidate_id
        found_ids.add(candidate_id)
        explicitly_selected = selected is not None and candidate_id in selected
        normally_eligible = geometry.record.status == "eligible"
        threshold_override = (
            explicitly_selected
            and geometry.record.status in ("rejected", "unresolved")
            and geometry.record.reason in _UNION_OVERRIDABLE_REASONS
        )
        should_adjust = (
            normally_eligible if selected is None else explicitly_selected
        ) and (normally_eligible or threshold_override)
        if not should_adjust:
            if selected is not None and normally_eligible and not explicitly_selected:
                records_by_id[candidate_id] = replace(
                    geometry.record,
                    status="unresolved",
                    reason="not-selected-by-master-union",
                )
            else:
                records_by_id[candidate_id] = geometry.record
            continue
        updates = _glyf_taper_points(geometry, taper_depth_ratio)
        if updates is None:
            records_by_id[candidate_id] = replace(
                geometry.record,
                status="unresolved",
                reason="point-compatible-taper-gate-failed",
            )
            continue
        proposals[candidate_id] = (geometry, updates, threshold_override)

    point_updates: dict[int, tuple[Point, set[TerminalCandidateId]]] = {}
    conflicts: set[TerminalCandidateId] = set()
    for candidate_id, (_, updates, _) in proposals.items():
        for point_index, point in updates.items():
            existing = point_updates.get(point_index)
            if existing is None:
                point_updates[point_index] = (point, {candidate_id})
                continue
            existing_point, owners = existing
            owners.add(candidate_id)
            if existing_point != point:
                conflicts.update(owners)

    for candidate_id, (geometry, updates, threshold_override) in proposals.items():
        if candidate_id in conflicts:
            records_by_id[candidate_id] = replace(
                geometry.record,
                status="unresolved",
                reason="point-compatible-update-conflict",
            )
            continue
        for point_index, point in updates.items():
            tapered.coordinates[point_index] = point
        records_by_id[candidate_id] = replace(
            geometry.record,
            status="adjusted",
            reason="selected-by-master-union" if threshold_override else None,
        )

    if selected is not None:
        for contour_index, point_indices in selected.difference(found_ids):
            records_by_id[(contour_index, point_indices)] = TerminalCandidate(
                contour_index=contour_index,
                segment_index=point_indices[0] if point_indices else 0,
                segment_count=max(0, len(point_indices) - 1),
                point_indices=point_indices,
                normalized_midpoint=(0.0, 0.0),
                normalized_axis=(0.0, 0.0),
                entry_or_exit="unknown",
                status="unresolved",
                reason="selected-candidate-not-found",
            )
    records = tuple(
        records_by_id[candidate_id]
        for candidate_id in sorted(
            records_by_id,
            key=lambda item: (item[0], item[1]),
        )
    )
    return GlyfTerminalResult(tapered, TerminalInventory(records))


def _legacy_terminal_curves(
    geometry: _Geometry,
) -> tuple[tuple[Point, Point, Point], tuple[Point, Point, Point]] | None:
    """Return the established two-cubic static cap used by legacy builds."""

    start = geometry.cap_points[0]
    end = geometry.cap_points[-1]
    axis = _unit(_subtract(end, start))
    incoming = _unit(_subtract(start, geometry.previous_control))
    outgoing = _unit(_subtract(geometry.next_control, end))
    if axis is None or incoming is None or outgoing is None:
        return None
    cap_length = math.dist(start, end)
    if not _LEGACY_MIN_CAP_LENGTH <= cap_length <= _LEGACY_MAX_CAP_LENGTH:
        return None
    if _dot(incoming, outgoing) >= _LEGACY_MAX_TANGENT_DOT:
        return None
    outward = _unit(_subtract(incoming, outgoing))
    if outward is None or abs(_dot(outward, axis)) >= _LEGACY_MAX_AXIS_DOT:
        return None
    if geometry.record.status != "eligible":
        return None

    midpoint = _scale(_add(start, end), 0.5)
    boundary_handle = cap_length * _BOUNDARY_HANDLE_RATIO
    long_sweep = (
        min(
            math.dist(start, geometry.previous_control),
            math.dist(end, geometry.next_control),
        )
        >= cap_length * _LEGACY_LONG_SWEEP_HANDLE_RATIO
    )
    nose_ratio = (
        _LEGACY_LONG_SWEEP_NOSE_RATIO if long_sweep else _LEGACY_REGULAR_NOSE_RATIO
    )
    nose_handle = cap_length * nose_ratio
    curves = (
        (
            _add(start, _scale(outward, boundary_handle)),
            _subtract(midpoint, _scale(axis, nose_handle)),
            midpoint,
        ),
        (
            _add(midpoint, _scale(axis, nose_handle)),
            _add(end, _scale(outward, boundary_handle)),
            end,
        ),
    )
    return curves if _all_finite(point for curve in curves for point in curve) else None


def _soften_legacy_path(outline: pathops.Path) -> tuple[pathops.Path, int]:
    commands, geometries, open_indices = _path_geometries(outline)
    replacements: dict[
        int,
        tuple[tuple[Point, Point, Point], tuple[Point, Point, Point]],
    ] = {}
    skipped: set[int] = set()
    for geometry in geometries:
        curves = _legacy_terminal_curves(geometry)
        if curves is None:
            continue
        replacements[geometry.source_indices[0]] = curves
        skipped.update(geometry.source_indices[1:])
    if not replacements:
        return pathops.Path(outline), 0

    softened = pathops.Path()
    pen = softened.getPen()
    for index, (operator, operands) in enumerate(commands):
        curves = replacements.get(index)
        if curves is not None:
            for curve in curves:
                pen.curveTo(*curve)
        elif index not in skipped and index not in open_indices:
            getattr(pen, operator)(*operands)
    return softened, len(replacements)


def soften_kana_terminals(outline: pathops.Path) -> tuple[pathops.Path, int]:
    """Preserve the established static CFF taper used by existing Novel builds."""

    return _soften_legacy_path(outline)


__all__ = (
    "GlyfTerminalResult",
    "PathTerminalResult",
    "SimpleGlyfGlyph",
    "TerminalCandidate",
    "TerminalCandidateId",
    "TerminalDirection",
    "TerminalInventory",
    "TerminalStatus",
    "inventory_glyf_terminals",
    "inventory_path_terminals",
    "soften_kana_terminals",
    "taper_glyf_terminals",
    "taper_path_terminals",
)
