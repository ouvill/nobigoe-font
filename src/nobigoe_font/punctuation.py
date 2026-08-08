"""Manga punctuation outline construction and ligature rules."""

from __future__ import annotations

import math

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from . import geometry

SHIPPORI_PRECOMPOSED_LIGATURES = {
    "!!": 0x203C,
    "??": 0x2047,
    "?!": 0x2048,
    "!?": 0x2049,
}
SHIPPORI_UPRIGHT_PUNCTUATION = {
    "!": 0xE000,
    "?": 0xFF1F,
}
SHIPPORI_UPRIGHT_EXCLAMATIONS = {
    "!": SHIPPORI_UPRIGHT_PUNCTUATION["!"],
    "!!": 0xE002,
    "!!!": 0xE007,
    "!!!!": 0xE0E3,
}
SHIPPORI_COMPONENT_LIGATURES = {
    "!": SHIPPORI_UPRIGHT_EXCLAMATIONS["!!"],
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
PUNCTUATION_ROTATED_COUNT = len(PUNCTUATION_VARIANT_SEQUENCES)
PUNCTUATION_ROTATION_ANGLE = 10

_VARIABLE_SERIF_DOT_SCALE_MASTERS = (0.84, 0.87, 0.90)
_FIVE_EXCLAMATION_CENTERS = (100, 300, 500, 700, 900)
_PUNCTUATION_ROTATED_MAX_BODY_SPAN = 960
_PUNCTUATION_ROTATED_MIN_BODY_GAP = 20


def _master_value(
    weight: float, extra_light: float, regular: float, black: float
) -> float:
    if not 200 <= weight <= 900:
        raise ValueError(
            f"Punctuation weight must be between 200 and 900, got {weight}"
        )
    if weight <= 400:
        factor = (weight - 200) / 200
        return extra_light + factor * (regular - extra_light)
    factor = (weight - 400) / 500
    return regular + factor * (black - regular)














def shippori_upright_punctuation_paths(
    font: TTFont,
) -> dict[str, pathops.Path]:
    cmap = font.getBestCmap()
    return {
        mark: geometry.glyph_path(font, cmap[codepoint])
        for mark, codepoint in SHIPPORI_UPRIGHT_PUNCTUATION.items()
    }


def make_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    components: list[tuple[pathops.Path, float, float]] = []
    total_width = gap * (len(sequence) - 1)
    cmap = font.getBestCmap()
    upright_codepoint = SHIPPORI_UPRIGHT_EXCLAMATIONS.get(sequence)
    if upright_codepoint is not None:
        return geometry.glyph_path(font, cmap[upright_codepoint])
    precomposed_codepoint = SHIPPORI_PRECOMPOSED_LIGATURES.get(sequence)
    if precomposed_codepoint is not None:
        return geometry.glyph_path(font, cmap[precomposed_codepoint])

    for mark in sequence:
        source_codepoint = SHIPPORI_COMPONENT_LIGATURES[mark]
        source = geometry.glyph_path(font, cmap[source_codepoint])
        contours = list(source.contours)
        if len(contours) != 4:
            raise ValueError(f"Expected four contours in U+{source_codepoint:04X}")
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
        transform = Transform(scale, 0, 0, 1, cursor - scale * x_min, 0)
        outline.draw(TransformPen(combined.getPen(), transform))
        cursor += (width + gap) * scale
    return combined


type _Point = tuple[float, float]
type _Cubic = tuple[_Point, _Point, _Point, _Point]


_QUESTION_START = (492.0, 176.0)
_QUESTION_SEGMENTS = (
    ((496.0, 178.0), (500.0, 184.0), (500.0, 198.0)),
    ((500.0, 235.0), (505.0, 270.0), (515.0, 302.0)),
    ((528.0, 342.0), (548.0, 377.0), (570.0, 410.0)),
    ((610.0, 468.0), (676.0, 520.0), (676.0, 629.0)),
    ((676.0, 700.0), (610.0, 783.0), (510.0, 783.0)),
    ((415.0, 783.0), (343.0, 715.0), (343.0, 651.0)),
    ((343.0, 620.0), (362.0, 590.0), (399.0, 590.0)),
    ((424.0, 590.0), (436.0, 607.0), (436.0, 633.0)),
    ((436.0, 664.0), (397.0, 671.0), (397.0, 703.0)),
    ((397.0, 726.0), (430.0, 766.0), (490.0, 766.0)),
    ((558.0, 766.0), (614.0, 709.0), (614.0, 639.0)),
    ((614.0, 626.0), (613.2, 613.0), (612.0, 600.0)),
    ((609.54, 573.33), (605.38, 546.67), (590.0, 520.0)),
    ((574.62, 493.33), (548.03, 466.67), (530.0, 440.0)),
    ((511.97, 413.33), (502.51, 386.67), (496.0, 360.0)),
    ((488.59, 329.67), (485.0, 299.33), (485.0, 269.0)),
    ((485.0, 230.0), (486.0, 199.0), (488.0, 184.0)),
    ((489.0, 178.0), (491.0, 176.0), (492.0, 176.0)),
)
_QUESTION_HORIZONTAL_DIRECTIONS = (
    (1, 1, 1),
    (1, 1, 1),
    (1, 1, 1),
    (1, 1, 1),
    (1, 1, 0),
    (-1, -1, -1),
    (-1, -1, -1),
    (1, 1, 1),
    (1, 1, 1),
    (1, 1, 0),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, 0),
)
_QUESTION_INNER_KNOTS = (
    (485.0, 269.0),
    (496.0, 360.0),
    (530.0, 440.0),
    (590.0, 520.0),
    (612.0, 600.0),
    (614.0, 639.0),
)

_EXCLAMATION_START = (500.0, 178.0)
_EXCLAMATION_SEGMENTS = (
    ((505.0, 178.0), (507.0, 186.0), (507.0, 205.0)),
    ((510.0, 380.0), (528.0, 580.0), (532.0, 718.0)),
    ((533.0, 758.0), (520.0, 783.0), (500.0, 783.0)),
    ((480.0, 783.0), (467.0, 758.0), (468.0, 718.0)),
    ((472.0, 580.0), (490.0, 380.0), (493.0, 205.0)),
    ((493.0, 186.0), (495.0, 178.0), (500.0, 178.0)),
)
_EXCLAMATION_HORIZONTAL_DIRECTIONS = (
    (1, 1, 1),
    (1, 1, 1),
    (1, 1, 0),
    (-1, -1, -1),
    (-1, -1, -1),
    (-1, -1, 0),
)

# Median vertical-stem widths measured from Noto Serif JP 川・目・田 at
# y=350/450/550/650 are 44.0, 53.6, 65.2, 80.1, 95.0, 117.0, and
# 144.0 units. These reviewed profiles remove only the ink exceeding
# the wght 200 mark-to-kanji optical relationship.
_PUNCTUATION_MASTER_WEIGHTS = (200, 300, 400, 500, 600, 700, 900)
_QUESTION_THINNING_Y = (269, 350, 400, 450, 500, 550, 600, 650, 700, 760, 810)
_QUESTION_INNER_THINNING = {
    200: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    300: (0, 4.5, 10, 17, 24, 19, 10, 8, 6, 0, 0),
    400: (0, 0, 5, 12, 19, 14, 4, 2.5, 0, 0, 0),
    500: (0, 0, 0, 4.5, 14, 10, 1, 0, 0, 0, 0),
    600: (0, 0, 0, 0, 9, 7, 0, 0, 0, 0, 0),
    700: (0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0),
    900: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
}
_EXCLAMATION_NARROWING_Y = (178, 400, 450, 500, 550, 600, 650, 700, 760, 810)
_EXCLAMATION_HALF_NARROWING = {
    200: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    300: (0, 0, 1, 4, 8, 11, 14, 14, 7, 0),
    400: (0, 0, 0, 1.5, 5, 8, 11, 11.5, 6, 0),
    500: (0, 0, 0, 0, 4, 8, 10.5, 11.5, 6, 0),
    600: (0, 0, 0, 0, 3, 7, 10.5, 11.5, 6, 0),
    700: (0, 0, 0, 0, 0, 5, 8.5, 10, 5, 0),
    900: (0, 0, 0, 0, 0, 2.5, 6, 8, 4, 0),
}


def _align_cubic_joins(
    start: tuple[float, float],
    segments: list[list[tuple[float, float]]],
    skipped: frozenset[int] | None = None,
) -> None:
    for index, segment in enumerate(segments):
        if skipped is not None and index in skipped:
            continue
        previous = segments[index - 1]
        anchor = start if index == 0 else previous[2]
        incoming = (anchor[0] - previous[1][0], anchor[1] - previous[1][1])
        outgoing = (segment[0][0] - anchor[0], segment[0][1] - anchor[1])
        incoming_length = math.hypot(*incoming)
        outgoing_length = math.hypot(*outgoing)
        if incoming_length == 0 or outgoing_length == 0:
            continue
        direction = (
            incoming[0] / incoming_length + outgoing[0] / outgoing_length,
            incoming[1] / incoming_length + outgoing[1] / outgoing_length,
        )
        direction_length = math.hypot(*direction)
        if direction_length == 0:
            continue
        direction = (
            direction[0] / direction_length,
            direction[1] / direction_length,
        )
        previous[1] = (
            anchor[0] - direction[0] * incoming_length,
            anchor[1] - direction[1] * incoming_length,
        )
        segment[0] = (
            anchor[0] + direction[0] * outgoing_length,
            anchor[1] + direction[1] * outgoing_length,
        )


def _clamped_x_spline(
    knots: tuple[tuple[float, float], ...],
) -> list[
    tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]
]:
    count = len(knots)
    lower = [0.0] * count
    diagonal = [0.0] * count
    upper = [0.0] * count
    values = [0.0] * count
    diagonal[0] = diagonal[-1] = 1
    for index in range(1, count - 1):
        previous_height = knots[index][1] - knots[index - 1][1]
        next_height = knots[index + 1][1] - knots[index][1]
        lower[index] = next_height
        diagonal[index] = 2 * (previous_height + next_height)
        upper[index] = previous_height
        values[index] = 3 * (
            next_height * (knots[index][0] - knots[index - 1][0]) / previous_height
            + previous_height * (knots[index + 1][0] - knots[index][0]) / next_height
        )
    for index in range(1, count):
        factor = lower[index] / diagonal[index - 1]
        diagonal[index] -= factor * upper[index - 1]
        values[index] -= factor * values[index - 1]
    derivatives = [0.0] * count
    derivatives[-1] = values[-1] / diagonal[-1]
    for index in range(count - 2, -1, -1):
        derivatives[index] = (
            values[index] - upper[index] * derivatives[index + 1]
        ) / diagonal[index]
    curves = []
    for index in range(count - 1):
        start = knots[index]
        end = knots[index + 1]
        height = end[1] - start[1]
        curves.append(
            (
                start,
                (start[0] + derivatives[index] * height / 3, start[1] + height / 3),
                (
                    end[0] - derivatives[index + 1] * height / 3,
                    end[1] - height / 3,
                ),
                end,
            )
        )
    return curves


def _cubic_contour(
    start: tuple[float, float],
    segments: list[list[tuple[float, float]]],
) -> pathops.Path:
    result = pathops.Path()
    pen = result.getPen()
    pen.moveTo(start)
    for segment in segments:
        pen.curveTo(*segment)
    pen.closePath()
    return result


def _thin_question_body() -> pathops.Path:
    segments = [list(segment) for segment in _QUESTION_SEGMENTS]
    for index, curve in enumerate(
        reversed(_clamped_x_spline(_QUESTION_INNER_KNOTS)), start=11
    ):
        start_point, control_1, control_2, _ = curve
        segments[index] = [control_2, control_1, start_point]
    segments[10][1] = (segments[10][2][0], segments[10][1][1])
    segments[16][0] = (segments[15][2][0], segments[16][0][1])
    _align_cubic_joins(_QUESTION_START, segments, frozenset(range(11, 17)))
    return _cubic_contour(_QUESTION_START, segments)


def _thin_exclamation_body() -> pathops.Path:
    segments = [list(segment) for segment in _EXCLAMATION_SEGMENTS]
    _align_cubic_joins(_EXCLAMATION_START, segments)
    return _cubic_contour(_EXCLAMATION_START, segments)


def _cubic_contour_segments(
    contour: pathops.Path,
) -> tuple[_Point, list[_Cubic]]:
    recording = RecordingPen()
    contour.draw(recording)
    start = None
    current = None
    segments = []
    for operation, points in recording.value:
        if operation == "moveTo":
            start = current = points[0]
        elif operation == "curveTo":
            if current is None:
                raise ValueError("Cubic contour has no start point")
            control_1, control_2, end = points
            segments.append((current, control_1, control_2, end))
            current = end
        elif operation != "closePath":
            raise ValueError(f"Expected a cubic Shippori contour, found {operation}")
    if start is None:
        raise ValueError("Shippori contour is empty")
    return start, segments


def _interpolate_point(start: _Point, end: _Point, factor: float) -> _Point:
    return (
        start[0] + factor * (end[0] - start[0]),
        start[1] + factor * (end[1] - start[1]),
    )


def _split_cubic(segment: _Cubic, factor: float) -> tuple[_Cubic, _Cubic]:
    start, control_1, control_2, end = segment
    start_control = _interpolate_point(start, control_1, factor)
    controls = _interpolate_point(control_1, control_2, factor)
    control_end = _interpolate_point(control_2, end, factor)
    left_control = _interpolate_point(start_control, controls, factor)
    right_control = _interpolate_point(controls, control_end, factor)
    split = _interpolate_point(left_control, right_control, factor)
    return (
        (start, start_control, left_control, split),
        (split, right_control, control_end, end),
    )


def _split_question_inner_cubic(segment: _Cubic) -> list[_Cubic]:
    """Match the five semantic spans of the approved thin inner curve."""

    result = []
    remaining = segment
    for numerator, denominator in (
        (39, 370),
        (80, 331),
        (80, 251),
        (80, 171),
    ):
        first, remaining = _split_cubic(
            remaining,
            numerator / denominator,
        )
        result.append(first)
    result.append(remaining)
    return result


def _interpolate_profile(
    position: float,
    positions: tuple[int, ...],
    values: tuple[float, ...],
) -> float:
    if position <= positions[0]:
        return values[0]
    for index in range(1, len(positions)):
        start_position = positions[index - 1]
        end_position = positions[index]
        if position <= end_position:
            factor = (position - start_position) / (end_position - start_position)
            return values[index - 1] + factor * (values[index] - values[index - 1])
    return values[-1]


def _interpolate_correction_master(
    weight: float,
    masters: dict[int, tuple[float, ...]],
) -> tuple[float, ...]:
    if weight <= _PUNCTUATION_MASTER_WEIGHTS[0]:
        return masters[_PUNCTUATION_MASTER_WEIGHTS[0]]
    for index in range(1, len(_PUNCTUATION_MASTER_WEIGHTS)):
        lower_weight = _PUNCTUATION_MASTER_WEIGHTS[index - 1]
        upper_weight = _PUNCTUATION_MASTER_WEIGHTS[index]
        if weight <= upper_weight:
            factor = (weight - lower_weight) / (upper_weight - lower_weight)
            return tuple(
                lower + factor * (upper - lower)
                for lower, upper in zip(
                    masters[lower_weight],
                    masters[upper_weight],
                    strict=True,
                )
            )
    return masters[_PUNCTUATION_MASTER_WEIGHTS[-1]]


def _compatible_shippori_body(
    font: TTFont,
    mark: str,
    weight: float,
    weight_adjustment: float,
) -> pathops.Path:
    source = shippori_upright_punctuation_paths(font)[mark]
    source_body = max(source.contours, key=lambda contour: contour.bounds[3])
    start, segments = _cubic_contour_segments(source_body)
    if mark == "?":
        if len(segments) != 14:
            raise ValueError(
                f"Expected 14 cubic question-mark segments, found {len(segments)}"
            )
        segments = [
            *segments[:11],
            *_split_question_inner_cubic(segments[11]),
            *segments[12:],
        ]
        directions = _QUESTION_HORIZONTAL_DIRECTIONS
    elif mark == "!":
        if len(segments) != 6:
            raise ValueError(
                f"Expected 6 cubic exclamation-mark segments, found {len(segments)}"
            )
        directions = _EXCLAMATION_HORIZONTAL_DIRECTIONS
    else:
        raise ValueError(f"Unknown punctuation mark: {mark!r}")

    if mark == "?":
        correction_positions = _QUESTION_THINNING_Y
        correction_values = _interpolate_correction_master(
            weight,
            _QUESTION_INNER_THINNING,
        )
    else:
        correction_positions = _EXCLAMATION_NARROWING_Y
        correction_values = _interpolate_correction_master(
            weight,
            _EXCLAMATION_HALF_NARROWING,
        )

    y_min, y_max = source_body.bounds[1], source_body.bounds[3]
    center_y = (y_min + y_max) / 2
    vertical_scale = (y_max - y_min + 2 * weight_adjustment) / (y_max - y_min)

    def corrected(
        point: _Point,
        direction: int,
        segment_index: int,
    ) -> _Point:
        x, y = point
        corrected_y = center_y + (y - center_y) * vertical_scale
        narrowing = _interpolate_profile(
            corrected_y,
            correction_positions,
            correction_values,
        )
        horizontal_shift = weight_adjustment * direction
        if mark == "?" and segment_index >= 10:
            horizontal_shift += narrowing
        elif mark == "!":
            horizontal_shift -= direction * narrowing
        return x + horizontal_shift, corrected_y

    corrected_segments = [
        [
            corrected(point, direction, segment_index)
            for point, direction in zip(segment[1:], segment_directions, strict=True)
        ]
        for segment_index, (segment, segment_directions) in enumerate(
            zip(segments, directions, strict=True)
        )
    ]
    corrected_start = corrected(start, 0, 0)
    if mark == "?":
        _align_cubic_joins(
            corrected_start,
            corrected_segments,
            frozenset(range(11)),
        )
    else:
        _align_cubic_joins(corrected_start, corrected_segments)
    return _cubic_contour(corrected_start, corrected_segments)


def _circle_from_contour_bounds(
    contour: pathops.Path,
    scale: float,
) -> pathops.Path:
    x_min, y_min, x_max, y_max = contour.bounds
    center_x = (x_min + x_max) / 2
    radius = min(x_max - x_min, y_max - y_min) * scale / 2
    center_y = y_max - radius
    control = radius * 0.55228475
    result = pathops.Path()
    pen = result.getPen()
    pen.moveTo((center_x, center_y + radius))
    pen.curveTo(
        (center_x + control, center_y + radius),
        (center_x + radius, center_y + control),
        (center_x + radius, center_y),
    )
    pen.curveTo(
        (center_x + radius, center_y - control),
        (center_x + control, center_y - radius),
        (center_x, center_y - radius),
    )
    pen.curveTo(
        (center_x - control, center_y - radius),
        (center_x - radius, center_y - control),
        (center_x - radius, center_y),
    )
    pen.curveTo(
        (center_x - radius, center_y + control),
        (center_x - control, center_y + radius),
        (center_x, center_y + radius),
    )
    pen.closePath()
    return result


def _make_shippori_punctuation_ligature(
    font: TTFont,
    sequence: str,
    weight: float,
    weight_adjustment: float,
    compatible_marks: frozenset[str],
) -> pathops.Path:
    source = (
        shippori_upright_punctuation_paths(font)[sequence]
        if len(sequence) == 1
        else make_punctuation_ligature(font, sequence)
    )
    adjusted = geometry.adjust_outline_weight(source, weight_adjustment)
    bodies = sorted(
        (contour for contour in adjusted.contours if contour.bounds[3] >= 200),
        key=lambda contour: (contour.bounds[0] + contour.bounds[2]) / 2,
    )
    dots = sorted(
        (contour for contour in adjusted.contours if contour.bounds[3] < 200),
        key=lambda contour: (contour.bounds[0] + contour.bounds[2]) / 2,
    )
    if len(bodies) != len(sequence) or len(dots) != len(sequence):
        raise ValueError(f"Expected one Shippori body and dot per mark in {sequence!r}")

    if sequence == "!!!!!":
        centers = _FIVE_EXCLAMATION_CENTERS
    else:
        centers = tuple((body.bounds[0] + body.bounds[2]) / 2 for body in bodies)
    body_templates = {}
    for mark in dict.fromkeys(sequence):
        if mark not in compatible_marks:
            continue
        if weight == 200:
            body_templates[mark] = (
                _thin_question_body() if mark == "?" else _thin_exclamation_body()
            )
        else:
            body_templates[mark] = _compatible_shippori_body(
                font,
                mark,
                weight,
                weight_adjustment,
            )

    dot_scale = _master_value(weight, *_VARIABLE_SERIF_DOT_SCALE_MASTERS)
    result = pathops.Path()
    for mark, source_body, source_dot, center in zip(
        sequence, bodies, dots, centers, strict=True
    ):
        if mark not in compatible_marks:
            result.addPath(source_body)
            result.addPath(source_dot)
            continue
        body = body_templates[mark]
        body_center = (body.bounds[0] + body.bounds[2]) / 2
        scale_x = 1.0
        if len(sequence) > 1 and sequence != "!!!!!":
            source_width = source_body.bounds[2] - source_body.bounds[0]
            body_width = body.bounds[2] - body.bounds[0]
            scale_x = min(1.0, source_width / body_width)
        dot_target_x = center
        if mark == "?":
            terminal_start, _ = _cubic_contour_segments(body)
            dot_target_x += scale_x * (terminal_start[0] - body_center)
        result.addPath(
            geometry.transform_path(
                body,
                Transform(scale_x, 0, 0, 1, center - scale_x * body_center, 0),
            )
        )
        dot = _circle_from_contour_bounds(source_dot, dot_scale)
        dot_center = (dot.bounds[0] + dot.bounds[2]) / 2
        result.addPath(
            geometry.transform_path(
                dot,
                Transform(1, 0, 0, 1, dot_target_x - dot_center, 0),
            )
        )
    return result


def make_variable_shippori_punctuation_ligature(
    font: TTFont,
    sequence: str,
    weight: float,
    weight_adjustment: float,
) -> pathops.Path:
    """Build fully interpolation-compatible Shippori punctuation."""

    return _make_shippori_punctuation_ligature(
        font,
        sequence,
        weight,
        weight_adjustment,
        frozenset(("!", "?")),
    )


def make_fixed_shippori_punctuation_ligature(
    font: TTFont,
    sequence: str,
    weight: float,
    weight_adjustment: float,
) -> pathops.Path:
    """Apply the variable exclamation design without changing question marks."""

    return _make_shippori_punctuation_ligature(
        font,
        sequence,
        weight,
        weight_adjustment,
        frozenset(("!",)),
    )


def rotate_punctuation_outline(outline: pathops.Path) -> pathops.Path:
    """Rotate and align marks, then restore their horizontal ink spacing."""
    bodies = sorted(
        (contour for contour in outline.contours if contour.bounds[3] >= 140),
        key=lambda contour: (contour.bounds[0] + contour.bounds[2]) / 2,
    )
    dots = sorted(
        (contour for contour in outline.contours if contour.bounds[3] < 140),
        key=lambda contour: (contour.bounds[0] + contour.bounds[2]) / 2,
    )
    if len(bodies) != len(dots):
        raise ValueError("Punctuation outline must contain one dot per body")

    target_gaps = [
        max(0.0, following.bounds[0] - previous.bounds[2])
        for previous, following in zip(bodies, bodies[1:])
    ]

    def rotated_components(angle_degrees: float):
        angle = math.radians(-angle_degrees)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        components = []
        for body, dot in zip(bodies, dots, strict=True):
            pivot_x = (dot.bounds[0] + dot.bounds[2]) / 2
            pivot_y = (dot.bounds[1] + dot.bounds[3]) / 2
            transform = Transform(
                cosine,
                sine,
                -sine,
                cosine,
                pivot_x - cosine * pivot_x + sine * pivot_y,
                pivot_y - sine * pivot_x - cosine * pivot_y,
            )
            rotated_body = geometry.transform_path(body, transform)
            rotated_dot = geometry.transform_path(dot, transform)
            rotated_body = geometry.transform_path(
                rotated_body,
                Transform(
                    1,
                    0,
                    0,
                    1,
                    0,
                    body.bounds[3] - rotated_body.bounds[3],
                ),
            )
            rotated_dot = geometry.transform_path(
                rotated_dot,
                Transform(1, 0, 0, 1, 0, dot.bounds[1] - rotated_dot.bounds[1]),
            )
            components.append((rotated_body, rotated_dot))
        return components

    minimum_gap_total = _PUNCTUATION_ROTATED_MIN_BODY_GAP * len(target_gaps)
    components = rotated_components(PUNCTUATION_ROTATION_ANGLE)
    body_width = sum(body.bounds[2] - body.bounds[0] for body, _ in components)
    if body_width + minimum_gap_total > _PUNCTUATION_ROTATED_MAX_BODY_SPAN:
        lower_angle = 0.0
        upper_angle = float(PUNCTUATION_ROTATION_ANGLE)
        components = rotated_components(lower_angle)
        for _ in range(16):
            candidate_angle = (lower_angle + upper_angle) / 2
            candidate = rotated_components(candidate_angle)
            candidate_width = sum(
                body.bounds[2] - body.bounds[0] for body, _ in candidate
            )
            if (
                candidate_width + minimum_gap_total
                <= _PUNCTUATION_ROTATED_MAX_BODY_SPAN
            ):
                lower_angle = candidate_angle
                components = candidate
            else:
                upper_angle = candidate_angle
        body_width = sum(body.bounds[2] - body.bounds[0] for body, _ in components)

    available_gap = max(0.0, _PUNCTUATION_ROTATED_MAX_BODY_SPAN - body_width)
    if target_gaps:
        minimum_gap = min(
            _PUNCTUATION_ROTATED_MIN_BODY_GAP,
            available_gap / len(target_gaps),
        )
        extra_targets = [max(0.0, gap - minimum_gap) for gap in target_gaps]
        extra_budget = max(0.0, available_gap - minimum_gap * len(target_gaps))
        extra_total = sum(extra_targets)
        extra_scale = min(1.0, extra_budget / extra_total) if extra_total else 0.0
        target_gaps = [
            minimum_gap + extra * extra_scale for extra in extra_targets
        ]

    rotated = pathops.Path()
    cursor = 0.0
    for index, (body, dot) in enumerate(components):
        x_shift = cursor - body.bounds[0]
        transform = Transform(1, 0, 0, 1, x_shift, 0)
        rotated.addPath(geometry.transform_path(body, transform))
        rotated.addPath(geometry.transform_path(dot, transform))
        cursor = body.bounds[2] + x_shift
        if index < len(target_gaps):
            cursor += target_gaps[index]

    x_min, _, x_max, _ = rotated.bounds
    return geometry.transform_path(
        rotated,
        Transform(1, 0, 0, 1, 500 - (x_min + x_max) / 2, 0),
    )


def punctuation_ligature_rules(
    exclamation: str,
    question: str,
    ligatures: list[tuple[str, str]],
) -> str:
    inputs = {"!": exclamation, "?": question}
    return "".join(
        f"  sub {' '.join(inputs[mark] for mark in sequence)} by {name};\n"
        for sequence, name in ligatures
    )
