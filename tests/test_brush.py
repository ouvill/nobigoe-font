from __future__ import annotations

from pathlib import Path
import math
import unittest
from unittest.mock import Mock

import pathops
from fontTools.pens.recordingPen import RecordingPen

from nobigoe_font import geometry
from nobigoe_font.brush import (
    BrushElementStyle,
    _CommandEdit,
    _apply_command_edits,
    _box_elements,
    _edit_terminal,
    _edit_horizontal_start,
    _horizontal_start_elements,
    _vertical_end_elements,
    _terminal_elements,
    _vertical_start_elements,
    apply_brush_elements,
)
from nobigoe_font.cli import parse_args
from nobigoe_font.pipeline import build

Point = tuple[float, float]
Command = tuple[str, tuple[Point, ...]]


def _commands(outline: pathops.Path) -> tuple[Command, ...]:
    recording = RecordingPen()
    outline.draw(recording)
    return tuple(recording.value)


def _stroke_width(outline: pathops.Path, y: float) -> float:
    band = geometry.rectangle(-1000, y - 0.5, 2000, y + 0.5)
    ink = pathops.op(outline, band, pathops.PathOp.INTERSECTION)
    return ink.bounds[2] - ink.bounds[0]


def _longest_line_length(outline: pathops.Path) -> float:
    current: Point | None = None
    longest = 0.0
    for operator, operands in _commands(outline):
        if operator == "moveTo":
            current = operands[-1]
        elif operator in {"lineTo", "curveTo"} and current is not None:
            end = operands[-1]
            if operator == "lineTo":
                longest = max(longest, math.dist(current, end))
            current = end
    return longest


def _noto_horizontal_stroke() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((841, 514))
    pen.lineTo((778, 431))
    pen.lineTo((48, 431))
    pen.lineTo((58, 398))
    pen.lineTo((928, 398))
    pen.curveTo((944, 398), (956, 401), (959, 413))
    pen.curveTo((914, 455), (841, 514), (841, 514))
    pen.closePath()
    return outline


def _selected_horizontal_start_b() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((841, 514))
    pen.lineTo((778, 431))
    pen.lineTo((191, 431))
    pen.curveTo((146, 432), (102, 434), (58, 435))
    pen.lineTo((86, 391))
    pen.curveTo((136, 393), (184, 397), (236, 398))
    pen.lineTo((928, 398))
    pen.curveTo((944, 398), (956, 401), (959, 413))
    pen.curveTo((914, 455), (841, 514), (841, 514))
    pen.closePath()
    return outline


def _selected_uroko_b() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((750, 431))
    pen.lineTo((764, 431))
    pen.curveTo((770, 431), (774, 435), (778, 441))
    pen.lineTo((820, 505))
    pen.curveTo((826, 514), (836, 518), (846, 510))
    pen.curveTo((882, 482), (941, 438), (941, 413))
    pen.curveTo((941, 401), (926, 398), (911, 398))
    pen.lineTo((750, 398))
    pen.closePath()
    return outline


def _noto_vertical_stroke() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((460, 819))
    pen.lineTo((460, -77))
    pen.lineTo((474, -77))
    pen.curveTo((499, -77), (528, -60), (528, -49))
    pen.lineTo((528, 780))
    pen.curveTo((554, 784), (562, 794), (565, 808))
    pen.closePath()
    return outline


def _selected_vertical_stroke_b() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((449, 824))
    pen.curveTo((458, 769), (462, 685), (462, 619))
    pen.lineTo((462, 203))
    pen.curveTo((460, 73), (457, 29), (451, -57))
    pen.curveTo((451, -67), (462, -77), (475, -77))
    pen.curveTo((499, -77), (527, -60), (535, -44))
    pen.curveTo((531, 31), (529, 71), (527, 191))
    pen.lineTo((527, 760))
    pen.lineTo((544, 771))
    pen.curveTo((562, 783), (562, 793), (449, 824))
    pen.closePath()
    return outline


def _noto_crossed_vertical_stroke() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((44, 472))
    pen.lineTo((53, 443))
    pen.lineTo((464, 443))
    pen.lineTo((464, -76))
    pen.lineTo((477, -76))
    pen.curveTo((499, -76), (532, -60), (532, -49))
    pen.lineTo((532, 443))
    pen.lineTo((932, 443))
    pen.curveTo((932, 443), (958, 459), (958, 459))
    pen.curveTo((958, 459), (861, 541), (861, 541))
    pen.lineTo((808, 472))
    pen.lineTo((532, 472))
    pen.lineTo((532, 793))
    pen.curveTo((556, 797), (564, 807), (567, 821))
    pen.lineTo((464, 834))
    pen.lineTo((464, 472))
    pen.closePath()
    return outline


def _noto_left_sweep() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((515, 497))
    pen.curveTo((515, 273), (469, 70), (230, -62))
    pen.lineTo((242, -77))
    pen.curveTo((525, 43), (581, 264), (582, 497))
    pen.curveTo((560, 520), (537, 520), (515, 497))
    pen.closePath()
    return outline


def _synthetic_right_sweep_terminal(
    *,
    reverse: bool = False,
    short_curve: bool = False,
    long_cap: bool = False,
) -> pathops.Path:
    short_body = (936, -38) if short_curve else (900, -76)
    short_first = (943, -31) if short_curve else (910, -44)
    short_second = (952, -22) if short_curve else (934, -23)
    cap_lower = (964, -20)
    cap_upper = (964, 15) if long_cap else (966, -9)
    long_first = (806, 22)
    long_second = (659, 78)
    long_body = (543, 162)
    shoulder = (600, 220)

    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo(short_body)
    if reverse:
        pen.lineTo(shoulder)
        pen.lineTo(long_body)
        pen.curveTo(long_second, long_first, cap_upper)
        pen.lineTo(cap_lower)
        pen.curveTo(short_second, short_first, short_body)
    else:
        pen.curveTo(short_first, short_second, cap_lower)
        pen.lineTo(cap_upper)
        pen.curveTo(long_first, long_second, long_body)
        pen.lineTo(shoulder)
        pen.lineTo(short_body)
    pen.closePath()
    return outline


def _synthetic_hook_terminal() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((446, 7))
    pen.curveTo((420, 7), (286, 17), (286, 17))
    pen.lineTo((286, 1))
    pen.curveTo((343, -6), (374, -14), (393, -26))
    pen.lineTo((450, -20))
    pen.lineTo((446, 7))
    pen.closePath()
    return outline


def _noto_hook(*, shallow: bool = False) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((474, 820))
    pen.lineTo((474, 31))
    pen.curveTo((474, 14), (468, 7), (446, 7))
    pen.curveTo((420, 7), (286, 17), (286, 17))
    pen.lineTo((286, 1))
    pen.curveTo((343, -6), (374, -14), (393, -26))
    if shallow:
        pen.curveTo((411, -34), (418, -43), (421, -50))
        pen.curveTo((529, -45), (542, -20), (542, 25))
    else:
        pen.curveTo((411, -39), (418, -55), (421, -78))
        pen.curveTo((529, -67), (542, -31), (542, 25))
    pen.lineTo((542, 782))
    pen.curveTo((566, 785), (576, 795), (578, 809))
    pen.closePath()
    return outline


def _slanted_internal_hook_basis() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((721, 105))
    pen.curveTo((654, 37), (575, -13), (494, -46))
    pen.lineTo((502, -64))
    pen.curveTo((589, -39), (674, 3), (746, 62))
    pen.curveTo((774, 20), (808, -14), (849, -40))
    pen.curveTo((890, -69), (944, -91), (961, -61))
    pen.curveTo((967, -51), (965, -39), (939, -9))
    pen.lineTo((952, 138))
    pen.lineTo((721, 105))
    pen.closePath()
    return outline


def _ki_like_internal_curve_caps() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((751, 415))
    pen.lineTo((742, 406))
    pen.curveTo((766, 390), (792, 361), (801, 335))
    pen.curveTo((854, 303), (895, 404), (751, 415))
    pen.closePath()
    pen.moveTo((563, 390))
    pen.curveTo((615, 345), (671, 452), (519, 532))
    pen.lineTo((506, 526))
    pen.curveTo((519, 508), (532, 485), (543, 461))
    pen.lineTo((563, 390))
    pen.closePath()
    pen.moveTo((355, 696))
    pen.lineTo((343, 689))
    pen.curveTo((374, 662), (410, 614), (420, 577))
    pen.curveTo((465, 547), (502, 613), (427, 664))
    pen.curveTo((453, 699), (480, 743), (504, 781))
    pen.curveTo((523, 780), (535, 789), (540, 801))
    pen.lineTo((451, 831))
    pen.curveTo((436, 779), (419, 722), (403, 678))
    pen.curveTo((390, 684), (374, 691), (355, 696))
    pen.closePath()
    pen.moveTo((904, 415))
    pen.curveTo((956, 367), (1013, 484), (852, 571))
    pen.lineTo((840, 565))
    pen.curveTo((855, 545), (870, 520), (882, 493))
    pen.lineTo((904, 415))
    pen.closePath()
    return outline


def _synthetic_left_sweep_start(
    axis: Point = (59, 223),
    across: Point = (73, 0),
) -> pathops.Path:
    outer_join = (347.0, 616.0)

    def point(x: float, y: float) -> Point:
        axis_units = (y - 616.0) / 223.0
        across_units = (x - 347.0 - 59.0 * axis_units) / 73.0
        return (
            outer_join[0] + axis[0] * axis_units + across[0] * across_units,
            outer_join[1] + axis[1] * axis_units + across[1] * across_units,
        )

    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo(point(406, 839))
    pen.curveTo(point(393, 767), point(373, 691), point(347, 616))
    pen.lineTo(point(347, 520))
    pen.lineTo(point(420, 520))
    pen.lineTo(point(420, 616))
    pen.curveTo(point(443, 676), point(461, 736), point(476, 793))
    pen.curveTo(point(504, 794), point(512, 801), point(516, 814))
    pen.closePath()
    pen.moveTo((800, -100))
    pen.lineTo((825, -50))
    pen.lineTo((850, -100))
    pen.closePath()
    return outline


def _selected_left_sweep_start_b() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((347, 560))
    pen.lineTo((347, 616))
    pen.curveTo((350, 626), (353, 636), (356, 645))
    pen.curveTo((376, 708), (391, 791), (392, 846))
    pen.curveTo((509, 819), (509, 809), (490, 801))
    pen.lineTo((471, 793))
    pen.curveTo((461, 736), (443, 676), (420, 616))
    pen.lineTo((420, 560))
    pen.closePath()
    return outline


def _selected_left_sweep_body() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((420, 560))
    pen.lineTo((420, 520))
    pen.lineTo((347, 520))
    pen.lineTo((347, 560))
    pen.closePath()
    return outline


def _synthetic_box_corners(
    *,
    selected: bool = False,
    counter: bool = True,
) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if counter:
        pen.moveTo((778, 111))
        pen.lineTo((225, 111))
        pen.lineTo((225, 657))
        pen.lineTo((778, 657))
        pen.closePath()
    pen.moveTo((225, 82))
    pen.lineTo((778, 82))
    if selected:
        pen.lineTo((778, 45))
        pen.curveTo((777, 32), (777, 16), (776, -7))
        pen.curveTo((776, -17), (782, -27), (788, -27))
        pen.curveTo((812, -27), (843, -12), (849, -4))
        pen.curveTo((847, 74), (846, 134), (845, 234))
        pen.lineTo((845, 638))
    else:
        pen.lineTo((778, -27))
        pen.lineTo((788, -27))
        pen.curveTo((812, -27), (844, -12), (846, -6))
        pen.lineTo((846, 638))
    pen.lineTo((900, 662))
    pen.lineTo((807, 735))
    pen.lineTo((766, 687))
    if selected:
        pen.lineTo((242, 687))
        pen.lineTo((151.5, 727))
        pen.curveTo((156, 704), (158, 657), (158, 620))
        pen.lineTo((158, 180))
        pen.curveTo((158, 100), (155, 48), (151, -20))
        pen.curveTo((151, -30), (162, -40), (175, -40))
        pen.curveTo((204, -40), (225, -23), (229, -9))
        pen.curveTo((227, 7), (225, 18), (225, 50))
        pen.lineTo((225, 82))
    else:
        pen.lineTo((232, 687))
        pen.lineTo((158, 722))
        pen.lineTo((158, -40))
        pen.lineTo((170, -40))
        pen.curveTo((200, -40), (225, -23), (225, -14))
        pen.lineTo((225, 82))
    pen.closePath()
    return outline


def _split_box_corners(
    *,
    height_scale: float = 1.0,
    grid: bool = False,
    open_outer: bool = False,
) -> pathops.Path:
    """A 日/田-derived box whose contour boundary splits the left-top side."""

    def point(x: float, y: float) -> Point:
        return (x, -40.0 + (y + 40.0) * height_scale)

    outline = pathops.Path()
    pen = outline.getPen()

    def counter(left: float, bottom: float, right: float, top: float) -> None:
        pen.moveTo(point(right, bottom))
        pen.lineTo(point(left, bottom))
        pen.lineTo(point(left, top))
        pen.lineTo(point(right, top))
        pen.closePath()

    if grid:
        counter(225, 111, 490, 375)
        counter(525, 111, 778, 375)
        counter(225, 410, 490, 657)
        counter(525, 410, 778, 657)
    else:
        counter(225, 111, 778, 657)

    pen.moveTo(point(158, 700))
    pen.lineTo(point(158, -40))
    pen.lineTo(point(170, -40))
    pen.curveTo(point(200, -40), point(225, -23), point(225, -14))
    pen.lineTo(point(225, 82))
    pen.lineTo(point(778, 82))
    pen.lineTo(point(778, -27))
    pen.lineTo(point(788, -27))
    pen.curveTo(point(812, -27), point(844, -12), point(846, -6))
    pen.lineTo(point(846, 638))
    pen.curveTo(point(871, 643), point(891, 652), point(900, 662))
    pen.lineTo(point(807, 735))
    pen.lineTo(point(766, 687))
    pen.lineTo(point(232, 687))
    pen.lineTo(point(158, 722))
    if open_outer:
        pen.endPath()
    else:
        pen.closePath()
    return outline


def _non_box_counter() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((150, 750))
    pen.lineTo((150, -50))
    pen.lineTo((850, -50))
    pen.lineTo((850, 750))
    pen.closePath()
    pen.moveTo((775, 50))
    pen.lineTo((225, 50))
    pen.lineTo((225, 650))
    pen.lineTo((775, 650))
    pen.closePath()
    return outline


def _crossed_box_corners() -> pathops.Path:
    """A closed box route interrupted by a through-running centre stem."""

    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((822, 334))
    pen.lineTo((530, 334))
    pen.lineTo((530, 599))
    pen.lineTo((822, 599))
    pen.closePath()
    pen.moveTo((567, 827))
    pen.lineTo((463, 838))
    pen.lineTo((463, 628))
    pen.lineTo((179, 628))
    pen.lineTo((106, 662))
    pen.lineTo((106, 210))
    pen.lineTo((117, 210))
    pen.curveTo((145, 210), (172, 226), (172, 233))
    pen.lineTo((172, 305))
    pen.lineTo((463, 305))
    pen.lineTo((463, -78))
    pen.lineTo((476, -78))
    pen.curveTo((502, -78), (530, -62), (530, -51))
    pen.lineTo((530, 305))
    pen.lineTo((822, 305))
    pen.lineTo((822, 222))
    pen.lineTo((832, 222))
    pen.curveTo((854, 222), (888, 237), (889, 243))
    pen.lineTo((889, 586))
    pen.curveTo((909, 590), (925, 598), (932, 606))
    pen.lineTo((849, 670))
    pen.lineTo((812, 628))
    pen.lineTo((530, 628))
    pen.lineTo((530, 799))
    pen.curveTo((556, 803), (564, 813), (567, 827))
    pen.closePath()
    return outline


def _noto_fold() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((846, 480))
    pen.lineTo((846, 638))
    pen.curveTo((871, 643), (891, 652), (900, 662))
    pen.lineTo((807, 735))
    pen.lineTo((766, 687))
    pen.lineTo((640, 687))
    pen.lineTo((640, 657))
    pen.lineTo((778, 657))
    pen.lineTo((778, 480))
    pen.closePath()
    return outline


def _selected_fold_b() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    x_scale = 10 / 11

    def point(x: float, y: float) -> Point:
        return (766 + (x - 744) * x_scale, y)

    pen.moveTo((846, 480))
    pen.lineTo((846, 638))
    pen.lineTo(point(858, 647))
    pen.curveTo(
        point(882.7, 656.5),
        point(883.935, 666),
        point(807.690375, 725.22775),
    )
    pen.curveTo(point(800, 731), point(794, 731), point(788, 724))
    pen.lineTo(point(761, 692))
    pen.curveTo(point(755, 687), point(750, 687), (766, 687))
    pen.lineTo((640, 687))
    pen.lineTo((640, 657))
    pen.lineTo((778, 657))
    pen.lineTo((778, 480))
    pen.closePath()
    return outline


def _noto_dot() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((328, 834))
    pen.lineTo((324, 819))
    pen.curveTo((454, 780), (551, 714), (588, 667))
    pen.curveTo((666, 639), (681, 807), (328, 834))
    pen.closePath()
    return outline


def _implicit_horizontal_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((49, 555))
    pen.lineTo((58, 525))
    pen.lineTo((314, 525))
    pen.lineTo((314, 400))
    pen.lineTo((310, 555))
    pen.closePath()
    return outline


def _exposed_horizontal_start_cap() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((570, 140))
    pen.lineTo((160, 140))
    pen.lineTo((169, 110))
    pen.lineTo((570, 110))
    pen.closePath()
    return outline


def _sho_like_internal_horizontal_edges() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    # A horizontal connection within a larger joined contour.
    pen.moveTo((570, 60))
    pen.lineTo((160, 60))
    pen.lineTo((160, 130))
    pen.lineTo((470, 130))
    pen.lineTo((470, 180))
    pen.lineTo((570, 180))
    pen.closePath()
    # A short inner contour with the same local winding seen in a counter.
    pen.moveTo((540, 240))
    pen.lineTo((190, 240))
    pen.lineTo((190, 315))
    pen.lineTo((540, 315))
    pen.closePath()
    return outline


def _horizontal_curve_join() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((597, 426))
    pen.curveTo((500, 600), (300, 759), (172, 759))
    pen.lineTo((154, 759))
    pen.curveTo((158, 683), (121, 610), (82, 582))
    pen.curveTo((160, 500), (400, 400), (597, 426))
    pen.closePath()
    return outline


def _embedded_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((531, 604))
    pen.lineTo((531, 800))
    pen.curveTo((557, 804), (565, 813), (567, 827))
    pen.lineTo((465, 839))
    pen.lineTo((465, 604))
    pen.closePath()
    return outline


def _wrapped_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((567, 827))
    pen.lineTo((463, 838))
    pen.lineTo((463, 628))
    pen.lineTo((530, 628))
    pen.lineTo((530, 799))
    pen.curveTo((556, 803), (564, 813), (567, 827))
    pen.closePath()
    return outline


def _split_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((488, -7))
    pen.lineTo((555, -7))
    pen.lineTo((555, 427))
    pen.lineTo((750, 427))
    pen.lineTo((750, 456))
    pen.lineTo((555, 456))
    pen.lineTo((555, 783))
    pen.curveTo((580, 787), (588, 797), (591, 811))
    pen.lineTo((488, 823))
    pen.lineTo((488, -7))
    pen.closePath()
    return outline


def _vertical_end_without_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((465, 400))
    pen.lineTo((465, -78))
    pen.lineTo((478, -78))
    pen.curveTo((500, -78), (525, -65), (531, -51))
    pen.lineTo((531, 400))
    pen.closePath()
    return outline


def _segmented_vertical_end() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((0, 120))
    pen.lineTo((0, 0))
    pen.lineTo((13, 0))
    pen.curveTo((38, 0), (65, 14), (65, 23))
    pen.lineTo((65, 80))
    pen.lineTo((300, 80))
    pen.lineTo((300, 120))
    pen.closePath()
    return outline


def _vertical_end_lookalike() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((0, 400))
    pen.lineTo((0, 0))
    pen.lineTo((13, 0))
    pen.curveTo((15, 0), (65, 25), (65, 25))
    pen.lineTo((65, 400))
    pen.closePath()
    return outline


def _short_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((66, 0))
    pen.lineTo((66, 84))
    pen.curveTo((86, 87), (94, 97), (102, 111))
    pen.lineTo((0, 122))
    pen.lineTo((0, 0))
    pen.closePath()
    return outline


def _segmented_short_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((67, 0))
    pen.lineTo((67, 74))
    pen.curveTo((84, 78), (97, 87), (102, 101))
    pen.lineTo((0, 110))
    pen.lineTo((0, 0))
    pen.closePath()
    return outline


def _crossbar_split_vertical_start() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((300, 0))
    pen.lineTo((65, 0))
    pen.lineTo((65, 51))
    pen.curveTo((82, 55), (96, 65), (101, 79))
    pen.lineTo((0, 88))
    pen.lineTo((0, 0))
    pen.lineTo((-220, 0))
    pen.closePath()
    return outline


def _curved_vertical_start_with_sweep_terminal() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((820, 655))
    pen.curveTo((769, 574), (668, 454), (577, 371))
    pen.curveTo((539, 482), (522, 615), (514, 776))
    pen.lineTo((514, 792))
    pen.curveTo((538, 795), (547, 806), (550, 820))
    pen.lineTo((444, 832))
    pen.curveTo((443, 421), (464, 135), (39, -59))
    pen.lineTo((50, -77))
    pen.curveTo((424, 65), (493, 278), (508, 555))
    pen.curveTo((540, 248), (631, 46), (893, -76))
    pen.curveTo((903, -39), (928, -23), (963, -20))
    pen.lineTo((965, -9))
    pen.curveTo((759, 70), (646, 185), (584, 353))
    pen.curveTo((697, 421), (810, 520), (876, 590))
    pen.curveTo((898, 584), (907, 588), (914, 598))
    pen.closePath()
    return outline


def _squat_vertical_start_lookalike() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((40, 0))
    pen.lineTo((40, 100))
    pen.curveTo((48, 102), (54, 106), (60, 112))
    pen.lineTo((0, 116))
    pen.lineTo((0, 0))
    pen.closePath()
    return outline


def _short_complete_vertical_stroke() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((0, 240))
    pen.lineTo((0, 0))
    pen.lineTo((8, 0))
    pen.curveTo((20, 0), (36, 8), (40, 18))
    pen.lineTo((40, 220))
    pen.curveTo((54, 223), (60, 229), (62, 237))
    pen.closePath()
    return outline


def _overlapping_vertical_starts() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((0, 300))
    pen.lineTo((0, 153))
    pen.lineTo((0, 68))
    pen.lineTo((65, 68))
    pen.lineTo((65, 151))
    pen.lineTo((65, 263))
    pen.curveTo((80, 270), (90, 285), (98, 295))
    pen.closePath()
    return outline


class BrushElementTests(unittest.TestCase):
    def test_command_recipe_can_insert_delete_and_replace(self) -> None:
        commands: list[Command] = [
            ("moveTo", ((0.0, 0.0),)),
            ("lineTo", ((10.0, 0.0),)),
            ("lineTo", ((10.0, 10.0),)),
            ("lineTo", ((0.0, 10.0),)),
            ("closePath", ()),
        ]
        edited = _apply_command_edits(
            commands,
            (
                _CommandEdit(
                    1,
                    1,
                    (
                        (
                            "curveTo",
                            ((3.0, 0.0), (7.0, 0.0), (10.0, 0.0)),
                        ),
                    ),
                ),
                _CommandEdit(2, 0, (("lineTo", ((12.0, 5.0),)),)),
                _CommandEdit(3, 1, ()),
            ),
        )

        self.assertEqual(
            _commands(edited),
            (
                ("moveTo", ((0.0, 0.0),)),
                (
                    "curveTo",
                    ((3.0, 0.0), (7.0, 0.0), (10.0, 0.0)),
                ),
                ("lineTo", ((12.0, 5.0),)),
                ("lineTo", ((10.0, 10.0),)),
                ("closePath", ()),
            ),
        )

    def test_horizontal_start_matches_selected_b_normalized_recipe(self) -> None:
        source = _noto_horizontal_stroke()
        source_commands = _commands(source)
        elements = _horizontal_start_elements(list(source_commands))

        self.assertEqual(len(elements), 1)
        element = elements[0]
        replacement = _edit_horizontal_start(element)
        edited = _apply_command_edits(
            list(source_commands),
            (
                _CommandEdit(
                    element.incoming_line_index,
                    3,
                    replacement,
                ),
            ),
        )
        edited_commands = _commands(edited)
        expected_commands = _commands(_selected_horizontal_start_b())
        difference = pathops.op(
            edited,
            _selected_horizontal_start_b(),
            pathops.PathOp.XOR,
        )

        self.assertEqual(
            tuple(operator for operator, _ in replacement),
            ("lineTo", "curveTo", "lineTo", "curveTo", "lineTo"),
        )
        self.assertEqual(edited_commands, expected_commands)
        self.assertFalse(difference.verbs)
        self.assertEqual(
            edited_commands[: element.incoming_line_index],
            source_commands[: element.incoming_line_index],
        )
        self.assertEqual(
            edited_commands[element.incoming_line_index + len(replacement) :],
            source_commands[element.outgoing_line_index + 1 :],
        )
        self.assertTrue(
            all(
                math.isfinite(coordinate)
                for _, operands in replacement
                for point in operands
                for coordinate in point
            )
        )
        self.assertEqual(_commands(source), source_commands)

    def test_horizontal_start_and_uroko_are_matched_independently(self) -> None:
        source = _noto_horizontal_stroke()
        source_commands = _commands(source)

        result = apply_brush_elements(source)
        crop = geometry.rectangle(750, 370, 985, 545)
        actual_uroko = pathops.op(
            result.path,
            crop,
            pathops.PathOp.INTERSECTION,
        )
        difference = pathops.op(
            actual_uroko,
            _selected_uroko_b(),
            pathops.PathOp.XOR,
        )

        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertEqual(result.adjusted_uroko_count, 1)
        self.assertEqual(result.adjusted_terminal_count, 0)
        self.assertFalse(difference.verbs)
        self.assertEqual(_commands(source), source_commands)

    def test_sweep_terminal_is_detected_without_glyph_coordinates(self) -> None:
        source = _noto_left_sweep()
        source_commands = _commands(source)

        result = apply_brush_elements(source)

        result_commands = _commands(result.path)
        self.assertEqual(result.adjusted_terminal_count, 1)
        self.assertEqual(result.adjusted_stroke_count, 0)
        self.assertEqual(result.adjusted_uroko_count, 0)
        self.assertEqual(result_commands[:1], source_commands[:1])
        self.assertEqual(result_commands[4:], source_commands[4:])
        self.assertEqual(
            tuple(command[0] for command in result_commands[1:4]),
            ("curveTo", "curveTo", "curveTo"),
        )
        self.assertEqual(_commands(source), source_commands)

    def test_hook_matches_selected_b_in_local_basis(self) -> None:
        source = _noto_hook()
        source_commands = _commands(source)
        elements = _terminal_elements(list(source_commands))

        self.assertEqual(len(elements), 1)
        element = elements[0]
        self.assertEqual(element.role, "hook")
        self.assertEqual(element.outgoing_curve_count, 3)

        replacement = _edit_terminal(
            element,
            list(source_commands),
            BrushElementStyle(),
        )
        edited = _apply_command_edits(
            list(source_commands),
            (
                _CommandEdit(
                    element.incoming_curve_index,
                    2 + element.outgoing_curve_count,
                    replacement,
                ),
            ),
        )
        edited_commands = _commands(edited)

        self.assertEqual(
            edited_commands[: element.incoming_curve_index],
            source_commands[: element.incoming_curve_index],
        )
        self.assertEqual(
            edited_commands[
                element.incoming_curve_index : element.incoming_curve_index + 7
            ],
            replacement,
        )
        self.assertEqual(
            edited_commands[element.incoming_curve_index + 7 :],
            source_commands[
                element.outgoing_curve_index + element.outgoing_curve_count :
            ],
        )

        self.assertEqual(
            tuple(command[0] for command in replacement),
            ("curveTo",) * 7,
        )
        self.assertEqual(
            replacement[0][1][0],
            source_commands[element.incoming_curve_index][1][0],
        )

        down = (
            element.cap_end[0] - element.cap_start[0],
            element.cap_end[1] - element.cap_start[1],
        )
        across = (
            element.end[0] - element.cap_start[0] + 0.5 * down[0],
            element.end[1] - element.cap_start[1] + 0.5 * down[1],
        )
        determinant = across[0] * down[1] - across[1] * down[0]

        def local_coordinates(point: Point) -> Point:
            delta = (
                point[0] - element.cap_start[0],
                point[1] - element.cap_start[1],
            )
            return (
                (delta[0] * down[1] - delta[1] * down[0]) / determinant,
                (across[0] * delta[1] - across[1] * delta[0]) / determinant,
            )

        expected_controls = (
            (34 / 256, 1 / 16),
            (4 / 256, 0),
            (0, 0),
            (-2 / 256, 2 / 16),
            (-2 / 256, 6 / 16),
            (-2 / 256, 11 / 16),
            (1 / 256, 15 / 16),
            (6 / 256, 16 / 16),
            (58 / 256, 24 / 16),
            (88 / 256, 32 / 16),
            (106 / 256, 42 / 16),
            (118 / 256, 50 / 16),
            (129 / 256, 57 / 16),
            (133 / 256, 71 / 16),
            (139 / 256, 91 / 16),
            (141 / 256, 95 / 16),
            (161 / 256, 92 / 16),
            (242 / 256, 78 / 16),
            (256 / 256, 43 / 16),
            (1, -0.5),
        )
        edited_controls = (
            replacement[0][1][1:],
            *(command[1] for command in replacement[1:]),
        )
        actual_controls = tuple(
            local_coordinates(point)
            for controls in edited_controls
            for point in controls
        )
        for actual, expected in zip(
            actual_controls,
            expected_controls,
            strict=True,
        ):
            self.assertAlmostEqual(actual[0], expected[0])
            self.assertAlmostEqual(actual[1], expected[1])

        result = apply_brush_elements(source)
        self.assertEqual(result.adjusted_terminal_count, 1)
        self.assertEqual(_commands(source), source_commands)

    def test_hook_recipe_does_not_exceed_source_terminal_depth(self) -> None:
        source = _noto_hook(shallow=True)
        source_bounds = source.bounds

        result = apply_brush_elements(source)

        self.assertEqual(result.adjusted_terminal_count, 1)
        self.assertGreaterEqual(result.path.bounds[1], source_bounds[1])

    def test_internal_curve_caps_require_exposed_hook_or_dot_sides(self) -> None:
        for source in (
            _ki_like_internal_curve_caps(),
            _slanted_internal_hook_basis(),
        ):
            with self.subTest(source=source.bounds):
                source_commands = _commands(source)
                self.assertEqual(_terminal_elements(list(source_commands)), ())
                result = apply_brush_elements(source)
                self.assertEqual(result.adjusted_element_count, 0)
                self.assertEqual(_commands(result.path), source_commands)
                self.assertEqual(_commands(source), source_commands)

        true_hooks = _terminal_elements(list(_commands(_noto_hook())))
        self.assertEqual(len(true_hooks), 1)
        self.assertEqual(true_hooks[0].role, "hook")

    def test_right_sweep_rounds_only_terminal_in_either_contour_direction(
        self,
    ) -> None:
        def cubic_point(
            start: Point,
            first: Point,
            second: Point,
            end: Point,
            factor: float,
        ) -> Point:
            inverse = 1 - factor
            return (
                inverse**3 * start[0]
                + 3 * inverse**2 * factor * first[0]
                + 3 * inverse * factor**2 * second[0]
                + factor**3 * end[0],
                inverse**3 * start[1]
                + 3 * inverse**2 * factor * first[1]
                + 3 * inverse * factor**2 * second[1]
                + factor**3 * end[1],
            )

        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                source = _synthetic_right_sweep_terminal(reverse=reverse)
                source_commands = _commands(source)
                element = _terminal_elements(list(source_commands))[0]
                incoming_operands = source_commands[element.incoming_curve_index][1]
                outgoing_operands = source_commands[element.outgoing_curve_index][1]
                incoming_is_short = math.dist(
                    element.start, element.cap_start
                ) < math.dist(element.cap_end, element.end)
                incoming_ratio = 0.20 if incoming_is_short else 0.022
                outgoing_ratio = 0.022 if incoming_is_short else 0.20

                result = apply_brush_elements(source)
                result_commands = _commands(result.path)
                incoming = result_commands[element.incoming_curve_index]
                terminal = result_commands[element.cap_line_index]
                outgoing = result_commands[element.outgoing_curve_index]

                self.assertEqual(element.role, "right-sweep")
                self.assertEqual(result.adjusted_terminal_count, 1)
                self.assertEqual(
                    result_commands[: element.incoming_curve_index],
                    source_commands[: element.incoming_curve_index],
                )
                self.assertEqual(
                    result_commands[element.outgoing_curve_index + 1 :],
                    source_commands[element.outgoing_curve_index + 1 :],
                )
                self.assertEqual(
                    (incoming[0], terminal[0], outgoing[0]),
                    ("curveTo", "curveTo", "curveTo"),
                )
                expected_incoming_join = cubic_point(
                    element.start,
                    incoming_operands[0],
                    incoming_operands[1],
                    element.cap_start,
                    1 - incoming_ratio,
                )
                expected_outgoing_join = cubic_point(
                    element.cap_end,
                    outgoing_operands[0],
                    outgoing_operands[1],
                    element.end,
                    outgoing_ratio,
                )
                for actual, expected in zip(
                    (incoming[1][-1], terminal[1][-1]),
                    (expected_incoming_join, expected_outgoing_join),
                    strict=True,
                ):
                    self.assertAlmostEqual(actual[0], expected[0], places=4)
                    self.assertAlmostEqual(actual[1], expected[1], places=4)

                first_incoming_tangent = (
                    incoming[1][-1][0] - incoming[1][-2][0],
                    incoming[1][-1][1] - incoming[1][-2][1],
                )
                first_terminal_tangent = (
                    terminal[1][0][0] - incoming[1][-1][0],
                    terminal[1][0][1] - incoming[1][-1][1],
                )
                last_terminal_tangent = (
                    terminal[1][-1][0] - terminal[1][-2][0],
                    terminal[1][-1][1] - terminal[1][-2][1],
                )
                first_outgoing_tangent = (
                    outgoing[1][0][0] - terminal[1][-1][0],
                    outgoing[1][0][1] - terminal[1][-1][1],
                )
                for before, after in (
                    (first_incoming_tangent, first_terminal_tangent),
                    (last_terminal_tangent, first_outgoing_tangent),
                ):
                    self.assertGreater(
                        before[0] * after[0] + before[1] * after[1],
                        0,
                    )
                self.assertEqual(_commands(source), source_commands)

    def test_short_curve_is_not_a_right_sweep_terminal(self) -> None:
        commands = list(_commands(_synthetic_right_sweep_terminal(short_curve=True)))

        self.assertEqual(_terminal_elements(commands), ())

    def test_hook_left_sweep_and_long_edge_are_not_right_sweeps(self) -> None:
        candidates = {
            "hook": (_noto_hook(), "hook"),
            "left sweep": (_noto_left_sweep(), "left-sweep"),
            "edge too long for a cap": (
                _synthetic_right_sweep_terminal(long_cap=True),
                "left-sweep",
            ),
        }

        for label, (source, expected_role) in candidates.items():
            with self.subTest(label):
                elements = _terminal_elements(list(_commands(source)))

                self.assertEqual(len(elements), 1)
                self.assertEqual(elements[0].role, expected_role)

    def test_left_sweep_start_matches_selected_b_in_affine_basis(self) -> None:
        source = _synthetic_left_sweep_start()
        source_commands = _commands(source)
        source_contours = tuple(source.contours)

        result = apply_brush_elements(source)
        result_contours = tuple(result.path.contours)
        selected_b = _selected_left_sweep_start_b()
        selected_body = _selected_left_sweep_body()
        cap_difference = pathops.op(
            result_contours[0],
            selected_b,
            pathops.PathOp.XOR,
        )
        body_difference = pathops.op(
            result_contours[1],
            selected_body,
            pathops.PathOp.XOR,
        )

        self.assertEqual(result.adjusted_corner_count, 1)
        self.assertEqual(result.adjusted_stroke_count, 0)
        self.assertEqual(result.adjusted_uroko_count, 0)
        self.assertEqual(result.adjusted_terminal_count, 0)
        self.assertFalse(cap_difference.verbs)
        self.assertFalse(body_difference.verbs)
        self.assertEqual(
            _commands(result_contours[0]),
            _commands(selected_b),
        )
        self.assertEqual(
            result_contours[0].clockwise,
            result_contours[1].clockwise,
        )
        self.assertEqual(len(result_contours), len(source_contours) + 1)
        self.assertEqual(
            _commands(result_contours[2]),
            _commands(source_contours[1]),
        )

        simplified = pathops.Path(result.path)
        before_bounds = result.path.bounds
        before_area = math.fsum(abs(contour.area) for contour in result_contours)
        simplified.simplify(
            fix_winding=True,
            keep_starting_points=False,
            clockwise=result_contours[0].clockwise,
        )
        self.assertEqual(len(tuple(simplified.contours)), len(result_contours) - 1)
        for actual, expected in zip(simplified.bounds, before_bounds):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(
            math.fsum(abs(contour.area) for contour in simplified.contours),
            before_area,
        )
        self.assertEqual(_commands(source), source_commands)

    def test_left_sweep_start_rejects_wrong_direction_short_and_horizontal(
        self,
    ) -> None:
        candidates = {
            "wrong direction": _synthetic_left_sweep_start(axis=(-59, 223)),
            "short sides": _synthetic_left_sweep_start(axis=(25, 90)),
            "horizontal stroke": _synthetic_left_sweep_start(axis=(220, 50)),
        }

        for label, source in candidates.items():
            with self.subTest(label):
                source_commands = _commands(source)
                result = apply_brush_elements(source)

                self.assertEqual(result.adjusted_element_count, 0)
                self.assertEqual(_commands(result.path), source_commands)
                self.assertEqual(_commands(source), source_commands)

    def test_box_corners_match_selected_b_recipes(self) -> None:
        source = _synthetic_box_corners()
        source_commands = _commands(source)

        result = apply_brush_elements(source)
        difference = pathops.op(
            result.path,
            _synthetic_box_corners(selected=True),
            pathops.PathOp.XOR,
        )

        self.assertEqual(result.adjusted_corner_count, 3)
        self.assertEqual(result.adjusted_stroke_count, 0)
        self.assertEqual(result.adjusted_uroko_count, 0)
        self.assertEqual(result.adjusted_terminal_count, 0)
        self.assertFalse(difference.verbs)
        self.assertEqual(_commands(source), source_commands)

    def test_box_corners_require_an_enclosed_counter(self) -> None:
        source = _synthetic_box_corners(counter=False)
        source_commands = _commands(source)

        self.assertEqual(_box_elements(list(source_commands)), ())
        self.assertEqual(_commands(source), source_commands)

    def test_box_left_top_joins_across_the_contour_boundary(self) -> None:
        fixtures = (
            ("short", _split_box_corners(height_scale=0.55)),
            ("tall", _split_box_corners(height_scale=1.4)),
            ("grid", _split_box_corners(grid=True)),
        )
        for label, source in fixtures:
            with self.subTest(label):
                source_commands = _commands(source)
                result = apply_brush_elements(source)
                commands = _commands(result.path)

                joined_top_indices: list[int] = []
                contour_start = -1
                for index, command in enumerate(commands):
                    if command[0] == "moveTo":
                        contour_start = index
                    if (
                        index >= 2
                        and command[0] == "closePath"
                        and commands[index - 1][0] == "curveTo"
                        and commands[index - 2][0] == "lineTo"
                        and commands[index - 3][0] == "lineTo"
                        and commands[index - 1][1][-1] == commands[contour_start][1][-1]
                    ):
                        joined_top_indices.append(index - 1)

                self.assertEqual(result.adjusted_corner_count, 4)
                self.assertEqual(len(joined_top_indices), 1)
                top_curve_index = joined_top_indices[0]
                top_curve = commands[top_curve_index][1]
                top_join = top_curve[-1]
                top_control = top_curve[-2]
                move_index = max(
                    index
                    for index in range(top_curve_index)
                    if commands[index][0] == "moveTo"
                )
                side_end = commands[move_index + 1][1][-1]
                incoming = (
                    top_join[0] - top_control[0],
                    top_join[1] - top_control[1],
                )
                outgoing = (
                    side_end[0] - top_join[0],
                    side_end[1] - top_join[1],
                )
                cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
                self.assertAlmostEqual(cross, 0.0, places=7)
                self.assertGreater(
                    incoming[0] * outgoing[0] + incoming[1] * outgoing[1],
                    0.0,
                )
                self.assertTrue(commands)
                self.assertTrue(
                    all(
                        math.isfinite(coordinate)
                        for _, operands in commands
                        for point in operands
                        for coordinate in point
                    )
                )
                self.assertEqual(_commands(source), source_commands)

    def test_box_left_top_rejects_open_and_non_box_outlines(self) -> None:
        fixtures = {
            "open outer": _split_box_corners(open_outer=True),
            "non-box counter": _non_box_counter(),
        }
        for label, source in fixtures.items():
            with self.subTest(label):
                source_commands = _commands(source)
                self.assertEqual(_box_elements(list(source_commands)), ())
                self.assertEqual(_commands(source), source_commands)

    def test_box_corners_keep_a_through_running_centre_stem(self) -> None:
        source = _crossed_box_corners()
        source_commands = _commands(source)
        source_y_min = min(y for _, operands in source_commands for _, y in operands)

        result = apply_brush_elements(source)
        result_commands = _commands(result.path)
        result_y_min = min(y for _, operands in result_commands for _, y in operands)

        self.assertEqual(result.adjusted_corner_count, 4)
        self.assertEqual(result_y_min, source_y_min)
        self.assertTrue(result_commands)
        self.assertTrue(
            all(
                math.isfinite(coordinate)
                for _, operands in result_commands
                for point in operands
                for coordinate in point
            )
        )
        self.assertEqual(_commands(source), source_commands)

    def test_fold_matches_selected_b_recipe_from_local_topology(self) -> None:
        source = _noto_fold()
        source_commands = _commands(source)

        result = apply_brush_elements(source)
        difference = pathops.op(
            result.path,
            _selected_fold_b(),
            pathops.PathOp.XOR,
        )

        self.assertEqual(result.adjusted_corner_count, 1)
        self.assertFalse(difference.verbs)
        self.assertEqual(_commands(source), source_commands)

    def test_closed_dot_cap_is_detected_across_contour_boundary(self) -> None:
        source = _noto_dot()
        source_commands = _commands(source)

        result = apply_brush_elements(source)

        self.assertEqual(result.adjusted_terminal_count, 1)
        self.assertEqual(
            tuple(command[0] for command in _commands(result.path)),
            ("moveTo", "curveTo", "curveTo", "curveTo", "closePath"),
        )
        self.assertEqual(_commands(source), source_commands)

    def test_horizontal_start_is_detected_across_implicit_close(self) -> None:
        source = _implicit_horizontal_start()
        commands = list(_commands(source))

        elements = _horizontal_start_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(elements), 1)
        self.assertGreater(elements[0].incoming_line_index, elements[0].cap_line_index)
        self.assertEqual(result.adjusted_stroke_count, 1)

    def test_exposed_left_cap_is_a_horizontal_start(self) -> None:
        source = _exposed_horizontal_start_cap()
        source_commands = _commands(source)

        elements = _horizontal_start_elements(list(source_commands))
        result = apply_brush_elements(source)

        self.assertEqual(len(elements), 1)
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertEqual(result.adjusted_uroko_count, 0)
        self.assertEqual(result.adjusted_terminal_count, 0)
        self.assertEqual(result.adjusted_corner_count, 0)
        self.assertEqual(_commands(source), source_commands)

    def test_sho_like_internal_horizontal_edges_are_not_starts(self) -> None:
        source = _sho_like_internal_horizontal_edges()
        source_commands = _commands(source)

        elements = _horizontal_start_elements(list(source_commands))
        result = apply_brush_elements(source)

        self.assertEqual(elements, ())
        self.assertEqual(result.adjusted_element_count, 0)
        self.assertEqual(_commands(result.path), source_commands)
        self.assertEqual(_commands(source), source_commands)

    def test_horizontal_curve_join_is_not_a_brush_terminal(self) -> None:
        commands = list(_commands(_horizontal_curve_join()))

        self.assertEqual(_terminal_elements(commands), ())

    def test_vertical_start_does_not_imply_end_pressure(self) -> None:
        source = _embedded_vertical_start()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        ends = _vertical_end_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0].cap_command_count, 2)
        self.assertEqual(ends, ())
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertLessEqual(
            _stroke_width(result.path, 620),
            _stroke_width(source, 620),
        )

    def test_vertical_end_does_not_imply_start_pressure(self) -> None:
        source = _vertical_end_without_start()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        ends = _vertical_end_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(starts, ())
        self.assertEqual(len(ends), 1)
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertLessEqual(
            _stroke_width(result.path, 380),
            _stroke_width(source, 380),
        )

    def test_segmented_vertical_end_is_found_from_cap_marker(self) -> None:
        source = _segmented_vertical_end()
        commands = list(_commands(source))

        ends = _vertical_end_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(ends), 1)
        self.assertLess(
            min(ends[0].down_side.length, ends[0].up_side.length) / ends[0].width,
            1.2,
        )
        self.assertEqual(result.adjusted_stroke_count, 1)

    def test_vertical_end_requires_noto_control_point_relationship(self) -> None:
        source = _vertical_end_lookalike()
        commands = list(_commands(source))

        ends = _vertical_end_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(ends, ())
        self.assertEqual(result.adjusted_stroke_count, 0)

    def test_vertical_start_is_detected_across_contour_boundary(self) -> None:
        source = _wrapped_vertical_start()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0].post_move_cap_count, 1)
        self.assertEqual(result.adjusted_stroke_count, 1)

    def test_exposed_start_pair_wins_over_attached_lower_fragment(self) -> None:
        source = _split_vertical_start()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0].up_side.command_index, 6)
        self.assertEqual(result.adjusted_stroke_count, 1)

    def test_short_exposed_vertical_start_uses_relative_side_length(self) -> None:
        source = _short_vertical_start()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertIn(("lineTo", ((0.0, 0.0),)), _commands(result.path))

    def test_segmented_vertical_starts_are_found_from_the_cap_marker(self) -> None:
        fixtures = {
            "病・水・草・読型": _segmented_short_vertical_start(),
            "唐・書型": _crossbar_split_vertical_start(),
        }
        for label, source in fixtures.items():
            with self.subTest(label):
                commands = list(_commands(source))
                starts = _vertical_start_elements(commands)

                self.assertEqual(len(starts), 1)
                self.assertLess(
                    min(starts[0].down_side.length, starts[0].up_side.length)
                    / starts[0].width,
                    1.2,
                )
                self.assertGreaterEqual(
                    apply_brush_elements(source).adjusted_stroke_count,
                    1,
                )

    def test_curved_vertical_start_preserves_its_sweep_terminal(self) -> None:
        source = _curved_vertical_start_with_sweep_terminal()
        source_commands = _commands(source)
        starts = _vertical_start_elements(list(source_commands))

        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertEqual(result.adjusted_terminal_count, 2)
        self.assertEqual(_commands(source), source_commands)

    def test_overlapping_vertical_starts_keep_stronger_local_pair(self) -> None:
        commands = list(_commands(_overlapping_vertical_starts()))

        starts = _vertical_start_elements(commands)

        self.assertEqual(len(starts), 1)
        self.assertGreater(
            min(starts[0].down_side.length, starts[0].up_side.length) / starts[0].width,
            1.5,
        )
        self.assertEqual(starts[0].cap_command_count, 1)
        self.assertEqual(starts[0].post_move_cap_count, 0)

    def test_short_complete_vertical_stroke_keeps_a_straight_body(self) -> None:
        source = _short_complete_vertical_stroke()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        ends = _vertical_end_elements(commands)
        result = apply_brush_elements(source)
        result_commands = _commands(result.path)
        body_line_index = next(
            index
            for index in range(1, len(result_commands) - 1)
            if result_commands[index - 1][0] == "curveTo"
            and result_commands[index][0] == "lineTo"
            and result_commands[index + 1][0] == "curveTo"
        )
        body_start = result_commands[body_line_index - 1][1][-1]
        body_end = result_commands[body_line_index][1][-1]

        self.assertEqual(len(starts), 1)
        self.assertEqual(len(ends), 1)
        self.assertEqual(
            starts[0].side_command_indices,
            ends[0].side_command_indices,
        )
        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertGreaterEqual(math.dist(body_start, body_end), 0.99 * 40)

    def test_vertical_start_requires_noto_control_point_relationship(self) -> None:
        source = _squat_vertical_start_lookalike()
        commands = list(_commands(source))

        starts = _vertical_start_elements(commands)
        result = apply_brush_elements(source)

        self.assertEqual(starts, ())
        self.assertEqual(result.adjusted_stroke_count, 0)

    def test_vertical_stroke_matches_selected_b_recipe(self) -> None:
        source = _noto_vertical_stroke()
        source_commands = _commands(source)

        result = apply_brush_elements(source)
        difference = pathops.op(
            result.path,
            _selected_vertical_stroke_b(),
            pathops.PathOp.XOR,
        )

        self.assertEqual(result.adjusted_stroke_count, 1)
        self.assertFalse(difference.verbs)
        self.assertEqual(_commands(source), source_commands)

    def test_crossbar_fragments_only_receive_exposed_endpoint_designs(
        self,
    ) -> None:
        source = _noto_crossed_vertical_stroke()
        commands = list(_commands(source))
        starts = _vertical_start_elements(commands)
        ends = _vertical_end_elements(commands)

        result = apply_brush_elements(source)

        self.assertEqual(len(starts), 1)
        self.assertEqual(len(ends), 1)
        self.assertTrue(
            starts[0].side_command_indices.isdisjoint(ends[0].side_command_indices)
        )
        self.assertEqual(result.adjusted_stroke_count, 3)
        result_endpoints = {
            operands[-1]
            for operator, operands in _commands(result.path)
            if operator in {"moveTo", "lineTo", "curveTo"}
        }
        self.assertTrue(
            {
                (464.0, 443.0),
                (532.0, 443.0),
                (532.0, 472.0),
                (464.0, 472.0),
            }.issubset(result_endpoints)
        )
        self.assertAlmostEqual(
            _stroke_width(result.path, 560),
            _stroke_width(source, 560),
            delta=3,
        )
        self.assertAlmostEqual(
            _stroke_width(result.path, 400),
            _stroke_width(source, 400),
            delta=3,
        )
        self.assertNotEqual(
            _stroke_width(result.path, 700),
            _stroke_width(source, 700),
        )
        self.assertGreater(
            _stroke_width(result.path, 0),
            _stroke_width(source, 0),
        )

    def test_cli_requires_explicit_opt_in(self) -> None:
        self.assertFalse(parse_args([]).han_brush_elements)
        self.assertTrue(parse_args(["--han-brush-elements"]).han_brush_elements)

    def test_koburi_base_rejects_han_brush_elements_before_loading_sources(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "--han-brush-elements requires --base noto",
        ):
            build(
                Path("source.ttf"),
                None,
                Path("punctuation.otf"),
                Path("output.ttf"),
                Mock(),
                Mock(),
                0,
                "koburi",
                han_brush_elements=True,
            )


if __name__ == "__main__":
    unittest.main()
