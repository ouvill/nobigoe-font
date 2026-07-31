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
PUNCTUATION_ITALIC_COUNT = len(PUNCTUATION_VARIANT_SEQUENCES)
PUNCTUATION_SLANT_ANGLE = 12

_VARIABLE_SERIF_DOT_SCALE_MASTERS = (0.84, 0.87, 0.90)
_FIVE_EXCLAMATION_CENTERS = (100, 300, 500, 700, 900)


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


def _original_punctuation_dot(weight: float, *, sans: bool) -> pathops.Path:
    center_x = 500
    radius = (
        _master_value(weight, 37, 43, 70) if sans else _master_value(weight, 35, 41, 61)
    )
    bottom = -30
    center_y = bottom + radius
    top = bottom + radius * 2
    control = radius * 0.55228475
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((center_x, top))
    pen.curveTo(
        (center_x + control, top),
        (center_x + radius, center_y + control),
        (center_x + radius, center_y),
    )
    pen.curveTo(
        (center_x + radius, center_y - control),
        (center_x + control, bottom),
        (center_x, bottom),
    )
    pen.curveTo(
        (center_x - control, bottom),
        (center_x - radius, center_y - control),
        (center_x - radius, center_y),
    )
    pen.curveTo(
        (center_x - radius, center_y + control),
        (center_x - control, top),
        (center_x, top),
    )
    pen.closePath()
    return path


def _original_exclamation_body(
    weight: float, *, sans: bool, compression: float = 1.0
) -> pathops.Path:
    center_x = 500
    if sans:
        top_half = _master_value(weight, 34, 45, 78)
        terminal_half = _master_value(weight, 20, 28, 54)
        top_round = _master_value(weight, 20, 26, 40)
        terminal_round = _master_value(weight, 9, 12, 20)
        shoulder = 650
        lower_control = 305
        stem_bottom = 190
    else:
        top_half = _master_value(weight, 36, 48, 82)
        terminal_half = _master_value(weight, 13, 19, 34)
        top_round = _master_value(weight, 25, 34, 56)
        terminal_round = _master_value(weight, 10, 14, 24)
        shoulder = _master_value(weight, 620, 610, 590)
        lower_control = _master_value(weight, 340, 350, 365)
        stem_bottom = _master_value(weight, 160, 170, 200)
        if compression < 1:
            stroke_gain = min(1.3, 1 + 0.3 * (1 - compression) / compression)
            terminal_half *= stroke_gain
    top = 790
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((center_x, top))
    pen.curveTo(
        (center_x + top_half * 0.55228475, top),
        (center_x + top_half, top - top_round * 0.44771525),
        (center_x + top_half, top - top_round),
    )
    pen.curveTo(
        (center_x + top_half, shoulder),
        (center_x + terminal_half, lower_control),
        (center_x + terminal_half, stem_bottom + terminal_round),
    )
    pen.curveTo(
        (center_x + terminal_half, stem_bottom + terminal_round * 0.45),
        (center_x + terminal_half * 0.55, stem_bottom),
        (center_x, stem_bottom),
    )
    pen.curveTo(
        (center_x - terminal_half * 0.55, stem_bottom),
        (center_x - terminal_half, stem_bottom + terminal_round * 0.45),
        (center_x - terminal_half, stem_bottom + terminal_round),
    )
    pen.curveTo(
        (center_x - terminal_half, lower_control),
        (center_x - top_half, shoulder),
        (center_x - top_half, top - top_round),
    )
    pen.curveTo(
        (center_x - top_half, top - top_round * 0.44771525),
        (center_x - top_half * 0.55228475, top),
        (center_x, top),
    )
    pen.closePath()
    return path


def _original_question_body(
    weight: float, *, sans: bool, compression: float = 1.0
) -> pathops.Path:
    center_x = 500
    if sans:
        outer_left = _master_value(weight, 298, 288, 240)
        outer_right = _master_value(weight, 702, 712, 760)
        inner_left = _master_value(weight, 348, 356, 380)
        inner_right = _master_value(weight, 652, 644, 620)
        inner_top = _master_value(weight, 732, 718, 650)
        terminal_left = _master_value(weight, 483, 475, 438)
        terminal_right = _master_value(weight, 517, 525, 562)
        cap_round = _master_value(weight, 8, 11, 18)
        terminal_round = cap_round
        cap_y = 596
        terminal_bottom = 190
        outer_left_top_x = 374
        outer_right_top_x = 632
        outer_turn_x = 680
        outer_turn_end_x = 610
        hook_control_x = 552
        inner_turn_x = 490
        inner_turn_mid_x = 544
        inner_turn_end_x = 596
        inner_right_shoulder_y = 652
        inner_left_shoulder_y = 655
    else:
        outer_left = _master_value(weight, 302, 296, 250)
        outer_right = _master_value(weight, 702, 708, 752)
        inner_left = _master_value(weight, 350, 358, 374)
        inner_right = _master_value(weight, 646, 638, 607)
        inner_top = _master_value(weight, 752, 750, 705)
        terminal_left = _master_value(weight, 485, 477, 455)
        terminal_right = _master_value(weight, 515, 523, 545)
        cap_round = _master_value(weight, 18, 28, 48)
        terminal_round = _master_value(weight, 10, 15, 30)
        cap_y = _master_value(weight, 596, 600, 610)
        terminal_bottom = _master_value(weight, 160, 170, 200)
        outer_left_top_x = _master_value(weight, 374, 368, 340)
        outer_right_top_x = _master_value(weight, 632, 638, 660)
        outer_turn_x = _master_value(weight, 680, 690, 720)
        outer_turn_end_x = _master_value(weight, 610, 618, 642)
        hook_control_x = _master_value(weight, 552, 558, 580)
        inner_turn_x = _master_value(weight, 490, 486, 468)
        inner_turn_mid_x = _master_value(weight, 544, 548, 565)
        inner_turn_end_x = _master_value(weight, 596, 602, 620)
        inner_right_shoulder_y = _master_value(weight, 652, 660, 675)
        inner_left_shoulder_y = _master_value(weight, 655, 663, 678)
        if compression < 1:
            stroke_gain = min(1.3, 1 + 0.3 * (1 - compression) / compression)
            inner_left = outer_left + (inner_left - outer_left) * stroke_gain
            inner_right = outer_right - (outer_right - inner_right) * stroke_gain
            terminal_half = (terminal_right - terminal_left) * stroke_gain / 2
            terminal_left = center_x - terminal_half
            terminal_right = center_x + terminal_half
    top = 790
    terminal_side_y = terminal_bottom + terminal_round * 2
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((outer_left, cap_y))
    pen.curveTo((outer_left, 700), (outer_left_top_x, top), (center_x, top))
    pen.curveTo((outer_right_top_x, top), (outer_right, 708), (outer_right, 590))
    pen.curveTo((outer_right, 500), (outer_turn_x, 438), (outer_turn_end_x, 396))
    pen.curveTo(
        (hook_control_x, 357),
        (terminal_right, 290),
        (terminal_right, terminal_side_y),
    )
    pen.curveTo(
        (terminal_right, terminal_bottom + terminal_round * 0.45),
        (center_x + (terminal_right - center_x) * 0.55, terminal_bottom),
        (center_x, terminal_bottom),
    )
    pen.curveTo(
        (center_x - (center_x - terminal_left) * 0.55, terminal_bottom),
        (terminal_left, terminal_bottom + terminal_round * 0.45),
        (terminal_left, terminal_side_y),
    )
    pen.curveTo(
        (terminal_left, 306),
        (inner_turn_x, 382),
        (inner_turn_mid_x, 425),
    )
    pen.curveTo(
        (inner_turn_end_x, 467),
        (inner_right, 520),
        (inner_right, 584),
    )
    pen.curveTo(
        (inner_right, inner_right_shoulder_y),
        (568, inner_top),
        (center_x, inner_top),
    )
    pen.curveTo(
        (420, inner_top),
        (inner_left, inner_left_shoulder_y),
        (inner_left, cap_y),
    )
    pen.curveTo(
        (inner_left, cap_y - cap_round),
        (outer_left, cap_y - cap_round),
        (outer_left, cap_y),
    )
    pen.closePath()
    return path


def _original_punctuation_body(
    mark: str,
    weight: float,
    *,
    sans: bool,
    compression: float = 1.0,
) -> pathops.Path:
    if mark == "!":
        return _original_exclamation_body(weight, sans=sans, compression=compression)
    if mark == "?":
        return _original_question_body(weight, sans=sans, compression=compression)
    raise ValueError(f"Unknown punctuation mark: {mark!r}")


def make_original_punctuation_mark(
    mark: str, weight: float, *, sans: bool = False
) -> pathops.Path:
    """Construct an original, interpolation-compatible full-width mark."""

    path = _original_punctuation_body(mark, weight, sans=sans)
    path.addPath(_original_punctuation_dot(weight, sans=sans))
    return path


def make_original_punctuation_ligature(
    sequence: str,
    weight: float,
    *,
    sans: bool = False,
    advance: int = 1000,
) -> pathops.Path:
    """Fit original punctuation components into one full-width cell."""

    if not sequence or any(mark not in "!?" for mark in sequence):
        raise ValueError(f"Invalid punctuation sequence: {sequence!r}")
    if len(sequence) == 1:
        return make_original_punctuation_mark(sequence, weight, sans=sans)
    if sans:
        components = [
            make_original_punctuation_mark(mark, weight, sans=True) for mark in sequence
        ]
        metrics = [
            (outline, outline.bounds[0], outline.bounds[2] - outline.bounds[0])
            for outline in components
        ]
        gap = _master_value(weight, 38, 34, 24)
        total_width = sum(width for _, _, width in metrics) + gap * (len(metrics) - 1)
        scale_x = min(1.0, (advance - 56) / total_width)
        cursor = (advance - total_width * scale_x) / 2
        combined = pathops.Path()
        for outline, x_min, width in metrics:
            combined.addPath(
                geometry.transform_path(
                    outline,
                    Transform(scale_x, 0, 0, 1, cursor - scale_x * x_min, 0),
                )
            )
            cursor += (width + gap) * scale_x
        return combined

    bodies = [_original_punctuation_body(mark, weight, sans=sans) for mark in sequence]
    body_lefts = [500 - body.bounds[0] for body in bodies]
    body_rights = [body.bounds[2] - 500 for body in bodies]
    dot = _original_punctuation_dot(weight, sans=sans)
    dot_radius = (dot.bounds[2] - dot.bounds[0]) / 2
    optical_widths = [184 if mark == "!" else 500 for mark in sequence]
    body_gap = _master_value(weight, 24, 20, 14)
    dot_gap = 24
    available = advance - 56

    def fitted_span(scale_x: float) -> tuple[float, list[float]]:
        distances = [
            max(
                scale_x * (optical_widths[index] + optical_widths[index + 1]) / 2,
                scale_x * (body_rights[index] + body_lefts[index + 1]) + body_gap,
                dot_radius * 2 + dot_gap,
            )
            for index in range(len(sequence) - 1)
        ]
        left_extent = max(scale_x * body_lefts[0], dot_radius)
        right_extent = max(scale_x * body_rights[-1], dot_radius)
        span = left_extent + sum(distances) + right_extent
        return span, distances

    scale_x = 1.0
    span, distances = fitted_span(scale_x)
    if span > available:
        low, high = 0.0, 1.0
        for _ in range(32):
            scale_x = (low + high) / 2
            span, distances = fitted_span(scale_x)
            if span <= available:
                low = scale_x
            else:
                high = scale_x
        scale_x = low
        span, distances = fitted_span(scale_x)

    left_extent = max(scale_x * body_lefts[0], dot_radius)
    centers = [(advance - span) / 2 + left_extent]
    centers.extend(
        centers[0] + sum(distances[: index + 1]) for index in range(len(distances))
    )
    if scale_x < 1:
        bodies = [
            _original_punctuation_body(mark, weight, sans=False, compression=scale_x)
            for mark in sequence
        ]
    combined = pathops.Path()
    for body, center in zip(bodies, centers, strict=True):
        combined.addPath(
            geometry.transform_path(
                body,
                Transform(scale_x, 0, 0, 1, center - scale_x * 500, 0),
            )
        )
        combined.addPath(
            geometry.transform_path(
                dot,
                Transform(1, 0, 0, 1, center - 500, 0),
            )
        )
    return combined


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


def make_variable_shippori_punctuation_ligature(
    font: TTFont,
    sequence: str,
    weight: float,
    weight_adjustment: float,
) -> pathops.Path:
    """Build smooth, interpolation-compatible Shippori punctuation."""

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


def make_sans_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    cmap = font.getBestCmap()
    components = [
        geometry.glyph_path(font, cmap[0xFF01 if mark == "!" else 0xFF1F])
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
            geometry.transform_path(
                outline,
                Transform(scale, 0, 0, 1, cursor - scale * x_min, 0),
            )
        )
        cursor += (width + gap) * scale
    return combined


def slant_punctuation_outline(outline: pathops.Path) -> pathops.Path:
    shear = math.tan(math.radians(PUNCTUATION_SLANT_ANGLE))
    slanted = geometry.transform_path(outline, Transform(1, 0, shear, 1, 0, 0))
    x_min, _, x_max, _ = slanted.bounds
    return geometry.transform_path(
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
        f"  sub {' '.join(inputs[mark] for mark in sequence)} by {name};\n"
        for sequence, name in ligatures
    )
