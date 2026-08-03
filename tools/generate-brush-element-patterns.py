from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from nobigoe_font import geometry
from nobigoe_font.brush import BrushElementStyle, apply_brush_elements


@dataclass(frozen=True)
class Pattern:
    key: str
    label: str
    note: str


@dataclass(frozen=True)
class ElementSpec:
    key: str
    label: str
    codepoint: int
    crop: tuple[float, float, float, float]
    description: str

    reference_contour: int | None = None


DESIGN_DIR = Path(__file__).with_name("brush-element-designs")
SELECTION_PATH = DESIGN_DIR / "selection.json"

PATTERNS = (
    Pattern("noto", "Noto", "編集前"),
    Pattern(
        "a",
        "A 簡潔構造",
        "少ない節点で、丸みだけを局所的に加える。",
    ),
    Pattern(
        "b",
        "B 源流構造",
        "源流明朝の節点構成と非対称な筆圧を写した案。",
    ),
    Pattern(
        "c",
        "C 荒筆構造",
        "節点を増やし、置きと抜きの方向変化を強調する。",
    ),
    Pattern(
        "d",
        "D 穏健構造",
        "接線を連続させ、張り出しと角の変化を抑える。",
    ),
    Pattern("genryu", "源流明朝", "実輪郭の参照形"),
)

ELEMENTS = (
    ElementSpec(
        "start",
        "起筆",
        0x4E28,
        (410.0, 540.0, 590.0, 860.0),
        "縦画上端。中央の直線へ接続するまでを拡大。",
    ),
    ElementSpec(
        "end",
        "終筆",
        0x4E28,
        (410.0, -100.0, 580.0, 260.0),
        "縦画下端。直線から収筆へ移る区間を拡大。",
    ),
    ElementSpec(
        "uroko",
        "ウロコ",
        0x4E00,
        (750.0, 370.0, 985.0, 545.0),
        "横画右端。輪郭節点、曲線数、制御点の配置を比較。",
    ),
    ElementSpec(
        "horizontal-start",
        "横画起筆",
        0x4E00,
        (20.0, 360.0, 280.0, 480.0),
        "横画左端。ヒゲを足さず、筆圧だけで起筆を表す。",
    ),
    ElementSpec(
        "dot",
        "点",
        0x6C38,
        (300.0, 780.0, 390.0, 850.0),
        "永字上部の点。左上の裁ち落としだけを拡大して比較。",
        0,
    ),
    ElementSpec(
        "left-sweep",
        "左払い筆端",
        0x4E3F,
        (200.0, -100.0, 300.0, 0.0),
        "丿の形を保ち、左下の裁ち落としだけを比較。",
    ),
    ElementSpec(
        "right-sweep",
        "右払い筆端",
        0x4E40,
        (900.0, -90.0, 980.0, 30.0),
        "乀の形を保ち、右下の裁ち落としだけを比較。",
    ),
    ElementSpec(
        "hook",
        "はね",
        0x4E85,
        (250.0, -100.0, 600.0, 180.0),
        "Notoの亅を保ち、左端の裁ち落としと下部のえぐりだけを比較。",
    ),
    ElementSpec(
        "fold",
        "折れ",
        0x53E3,
        (640.0, 480.0, 900.0, 760.0),
        "口字右上。ウロコ形の折れと斜画起点の小さな丸みを比較。",
    ),
    ElementSpec(
        "box-left-bottom",
        "囲み左下",
        0x53E3,
        (120.0, -80.0, 280.0, 180.0),
        "口字左下。外側の縦画から底辺内側へ戻る筆運びと、角の溜めを比較。",
    ),
    ElementSpec(
        "box-right-bottom",
        "囲み右下",
        0x53E3,
        (720.0, -80.0, 890.0, 270.0),
        "口字右下。底辺内側から外側の縦画へ立ち上がる筆運びと、角の溜めを比較。",
    ),
    ElementSpec(
        "box-left-top",
        "囲み左上",
        0x53E3,
        (110.0, 570.0, 285.0, 760.0),
        "口字左上。横画との接続を保ち、縦画起筆の筆圧を左縦画上端へ写す。",
    ),
    ElementSpec(
        "left-sweep-start",
        "左払い上部",
        0x53F3,
        (320.0, 570.0, 545.0, 875.0),
        "右・左・区・有などの右上から左下へ払う斜画上部。起筆の置きと左下への流れを比較。",
    ),
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate enlarged SVG comparisons for Han brush elements."
    )
    parser.add_argument("--noto", type=Path, required=True)
    parser.add_argument("--genryu", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/brush-element-patterns.html"),
    )
    parser.add_argument(
        "--export-svg-dir",
        type=Path,
        help="directory for standalone editable SVG files",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=SELECTION_PATH,
        help="JSON file containing the confirmed choice for each element",
    )
    return parser.parse_args()


def _load_selection(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("selected"), dict):
        raise ValueError(f"{path} must contain version 1 and a selected object")
    element_keys = {element.key for element in ELEMENTS}
    selected: dict[str, str] = {}
    for element, choice in data["selected"].items():
        if element not in element_keys:
            raise ValueError(f"Unknown element {element!r} in {path}")
        if not isinstance(choice, str):
            raise ValueError(f"Unknown choice {choice!r} for {element!r} in {path}")
        normalized_choice = choice.lower()
        if normalized_choice not in {"a", "b", "c"} and not (
            element == "end" and normalized_choice == "d"
        ):
            raise ValueError(f"Unknown choice {choice!r} for {element!r} in {path}")
        selected[element] = normalized_choice
    return selected


def _glyph_path(
    font: TTFont,
    codepoint: int,
    contour_index: int | None = None,
):
    cmap = font.getBestCmap()
    if cmap is None or codepoint not in cmap:
        raise ValueError(f"Missing U+{codepoint:04X} in comparison font")
    outline = geometry.glyph_path(font, cmap[codepoint])
    if contour_index is None:
        return outline
    contours = tuple(outline.contours)
    if contour_index >= len(contours):
        raise ValueError(f"Missing contour {contour_index} in U+{codepoint:04X}")
    selected = pathops.Path()
    selected.addPath(contours[contour_index])
    return selected


def _lerp(
    start: tuple[float, float],
    end: tuple[float, float],
    factor: float,
) -> tuple[float, float]:
    return (
        start[0] + (end[0] - start[0]) * factor,
        start[1] + (end[1] - start[1]) * factor,
    )


def _split_cubic(
    start: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
    end: tuple[float, float],
    factor: float,
) -> tuple[
    tuple[tuple[float, float], ...],
    tuple[tuple[float, float], ...],
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


def _prototype_start(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        pen.moveTo((460, 540))
        pen.lineTo((460, 630))
        pen.curveTo((460, 720), (458, 790), (452, 818))
        pen.curveTo((500, 812), (540, 792), (552, 782))
        pen.lineTo((528, 760))
        pen.lineTo((528, 540))
    elif variant == "b":
        pen.moveTo((460, 540))
        pen.lineTo((460, 627.9473775300144))
        pen.curveTo(
            (460, 694.906889112866),
            (455.29398557410025, 761.7836122842157),
            (445.9167388793148, 828.0832611206853),
        )
        pen.curveTo(
            (508.65278981321916, 828.0832611206853),
            (556.1665222413704, 795.5559406896788),
            (556.1665222413704, 780),
        )
        pen.curveTo(
            (556.1665222413704, 772.9583694396574),
            (528, 767.1248916810279),
            (528, 760.0832611206853),
        )
        pen.lineTo((528, 540))
    else:
        pen.moveTo((462, 540))
        pen.lineTo((462, 620))
        pen.curveTo((462, 690), (455, 760), (438, 828))
        pen.curveTo((475, 826), (525, 810), (558, 780))
        pen.curveTo((555, 765), (541, 749), (525, 746))
        pen.lineTo((525, 540))
    pen.closePath()
    return outline


def _prototype_end(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        pen.moveTo((461, 260))
        pen.lineTo((461, 170))
        pen.curveTo((460, 80), (458, -30), (456, -62))
        pen.curveTo((460, -74), (512, -78), (532, -45))
        pen.curveTo((530, 30), (528, 100), (527, 170))
        pen.lineTo((527, 260))
        pen.closePath()
        return outline

    if variant == "d":
        width = 68.0
        ratio = math.sqrt(2.0)
        pressure = width * (1.0 - 1.0 / ratio)
        total_extension = pressure / 3.0
        left_extension = total_extension * ratio / (1.0 + ratio)
        right_extension = total_extension / (1.0 + ratio)
        left_height = pressure
        right_height = pressure * ratio
        left_run = width * (3.0 * ratio - 2.0)
        right_run = 2.0 * width
        kappa = 4.0 * (ratio - 1.0) / 3.0

        left_stem_x = 460.0
        right_stem_x = left_stem_x + width
        baseline_y = -77.0
        left_outer = (
            left_stem_x - left_extension,
            baseline_y + left_height,
        )
        right_outer = (
            right_stem_x + right_extension,
            baseline_y + right_height,
        )
        cap_width = width + total_extension
        bottom = (
            left_outer[0] + cap_width / (1.0 + ratio),
            baseline_y,
        )
        left_body = (left_stem_x, left_outer[1] + left_run)
        right_body = (right_stem_x, right_outer[1] + right_run)

        # The side transitions are cubic smoothsteps: their vertical controls
        # are equally spaced, while lateral pressure reaches zero velocity at
        # both ends. The two cap halves use the quarter-ellipse kappa, so every
        # join is tangent-continuous: vertical at the shoulders, horizontal at
        # the bottom.
        pen.moveTo((left_stem_x, 260.0))
        pen.lineTo(left_body)
        pen.curveTo(
            (left_stem_x, left_body[1] - left_run / 3.0),
            (left_outer[0], left_outer[1] + left_run / 3.0),
            left_outer,
        )
        pen.curveTo(
            (
                left_outer[0],
                left_outer[1] + kappa * (bottom[1] - left_outer[1]),
            ),
            (
                bottom[0] - kappa * (bottom[0] - left_outer[0]),
                bottom[1],
            ),
            bottom,
        )
        pen.curveTo(
            (
                bottom[0] + kappa * (right_outer[0] - bottom[0]),
                bottom[1],
            ),
            (
                right_outer[0],
                right_outer[1] - kappa * (right_outer[1] - bottom[1]),
            ),
            right_outer,
        )
        pen.curveTo(
            (
                right_outer[0],
                right_outer[1] + right_run / 3.0,
            ),
            (
                right_stem_x,
                right_body[1] - right_run / 3.0,
            ),
            right_body,
        )
        pen.lineTo((right_stem_x, 260.0))
        pen.closePath()
        return outline

    pen.moveTo((460, 260))
    pen.lineTo((460, -77))
    pen.lineTo((474, -77))
    pen.curveTo((499, -77), (528, -60), (528, -49))
    pen.lineTo((528, 260))
    pen.closePath()
    profile = "silver" if variant == "b" else "traditional"
    return apply_brush_elements(
        outline,
        BrushElementStyle(vertical_end_profile=profile),
    ).path


def _prototype_uroko(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        pen.moveTo((830, 514))
        pen.lineTo((795, 472))
        pen.lineTo((750, 431))
        pen.lineTo((750, 398))
        pen.lineTo((916, 398))
        pen.curveTo((932, 398), (946, 403), (948, 414))
        pen.curveTo((930, 442), (870, 500), (830, 514))
    elif variant == "b":
        pen.moveTo((750, 431))
        pen.lineTo((764, 431))
        pen.curveTo((770, 431), (774, 435), (778, 441))
        pen.lineTo((820, 505))
        pen.curveTo((826, 514), (836, 518), (846, 510))
        pen.curveTo((882, 482), (941, 438), (941, 413))
        pen.curveTo((941, 401), (926, 398), (911, 398))
        pen.lineTo((750, 398))
    else:
        pen.moveTo((785, 468))
        pen.lineTo((750, 431))
        pen.lineTo((750, 398))
        pen.lineTo((905, 398))
        pen.curveTo((928, 398), (946, 401), (950, 412))
        pen.curveTo((954, 424), (950, 432), (944, 439))
        pen.curveTo((918, 474), (858, 524), (840, 526))
        pen.curveTo((822, 526), (802, 495), (785, 468))
    pen.closePath()
    return outline


def _prototype_horizontal_start(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        pen.moveTo((280, 431))
        pen.lineTo((82, 431))
        pen.curveTo((62, 431), (52, 426), (52, 417))
        pen.curveTo((52, 407), (63, 398), (83, 398))
        pen.lineTo((280, 398))
    elif variant == "b":
        pen.moveTo((280, 431))
        pen.lineTo((157.457505, 431))
        pen.curveTo(
            (124.962448, 431),
            (92.507568, 433.283801),
            (60.332738, 437.834524),
        )
        pen.lineTo((83.667262, 391.165476))
        pen.curveTo(
            (108.000927, 395.712095),
            (132.702728, 398),
            (157.457505, 398),
        )
        pen.lineTo((280, 398))
    else:
        pen.moveTo((280, 431))
        pen.lineTo((104, 431))
        pen.curveTo((79, 431), (58, 426), (47, 414))
        pen.curveTo((58, 397), (79, 388), (106, 395))
        pen.curveTo((154, 405), (205, 398), (280, 398))
    pen.closePath()
    return outline


def _prototype_dot(variant: str) -> pathops.Path:
    if variant == "a":
        incoming_factor, outgoing_factor = 0.985, 0.015
    elif variant == "b":
        incoming_factor, outgoing_factor = 0.97, 0.03
    else:
        incoming_factor, outgoing_factor = 0.94, 0.06
    incoming, _ = _split_cubic(
        (588, 667),
        (666, 639),
        (681, 807),
        (328, 834),
        incoming_factor,
    )
    _, outgoing = _split_cubic(
        (324, 819),
        (454, 780),
        (551, 714),
        (588, 667),
        outgoing_factor,
    )
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((588, 667))
    pen.curveTo(*incoming[1:])
    pen.curveTo((328, 834), (324, 819), outgoing[0])
    pen.curveTo(*outgoing[1:])
    pen.closePath()
    return outline


def _prototype_left_sweep(variant: str) -> pathops.Path:
    if variant == "a":
        incoming_factor, outgoing_factor = 0.985, 0.015
    elif variant == "b":
        incoming_factor, outgoing_factor = 0.97, 0.03
    else:
        incoming_factor, outgoing_factor = 0.94, 0.06
    incoming, _ = _split_cubic(
        (515, 497),
        (515, 273),
        (469, 70),
        (230, -62),
        incoming_factor,
    )
    _, outgoing = _split_cubic(
        (242, -77),
        (525, 43),
        (581, 264),
        (582, 497),
        outgoing_factor,
    )
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((617, 808))
    pen.lineTo((515, 819))
    pen.lineTo((515, 497))
    pen.curveTo(*incoming[1:])
    pen.curveTo((230, -62), (242, -77), outgoing[0])
    pen.curveTo(*outgoing[1:])
    pen.lineTo((582, 781))
    pen.curveTo((607, 784), (614, 794), (617, 808))
    pen.closePath()
    return outline


def _prototype_right_sweep(variant: str) -> pathops.Path:
    if variant == "a":
        incoming_factor, outgoing_factor = 0.94, 0.006
    elif variant == "b":
        incoming_factor, outgoing_factor = 0.88, 0.012
    else:
        incoming_factor, outgoing_factor = 0.8, 0.022
    incoming, _ = _split_cubic(
        (871, -79),
        (887, -47),
        (916, -29),
        (950, -29),
        incoming_factor,
    )
    _, outgoing = _split_cubic(
        (954, -18),
        (612, 95),
        (369, 351),
        (289, 733),
        outgoing_factor,
    )
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((289, 733))
    pen.lineTo((336, 787))
    pen.lineTo((293, 805))
    pen.lineTo((269, 742))
    pen.curveTo((228, 705), (162, 655), (122, 629))
    pen.lineTo((181, 556))
    pen.curveTo((190, 564), (194, 574), (186, 588))
    pen.curveTo((209, 616), (244, 667), (272, 708))
    pen.curveTo((345, 312), (552, 52), (871, -79))
    pen.curveTo(*incoming[1:])
    pen.curveTo((950, -29), (954, -18), outgoing[0])
    pen.curveTo(*outgoing[1:])
    pen.closePath()
    return outline


def _prototype_hook(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        left_in = (290, 17)
        cap_first = ((286, 17), (284, 15), (284, 11))
        cap_second = ((284, 6), (287, 2), (292, 1))
        lower_curves = (
            ((344, -6), (380, -14), (398, -24)),
            ((414, -36), (422, -55), (423, -78)),
            ((525, -67), (542, -31), (542, 25)),
        )
    elif variant == "b":
        left_in = (290, 17)
        cap_first = ((286, 17), (284, 15), (284, 11))
        cap_second = ((284, 6), (287, 2), (292, 1))
        lower_curves = (
            ((344, -7), (374, -15), (392, -25)),
            ((404, -33), (415, -40), (419, -54)),
            ((425, -74), (427, -78), (447, -75)),
            ((528, -61), (542, -26), (542, 25)),
        )
    else:
        left_in = (296, 17)
        cap_first = ((286, 18), (280, 14), (280, 9))
        cap_second = ((280, 3), (288, -1), (300, 0))
        lower_curves = (
            ((360, -4), (405, -5), (423, -14)),
            ((440, -24), (445, -49), (438, -72)),
            ((527, -68), (542, -28), (542, 25)),
        )
    pen.moveTo((474, 820))
    pen.lineTo((474, 31))
    pen.curveTo((474, 14), (468, 7), (446, 7))
    pen.curveTo((420, 7), (320, 16), left_in)
    pen.curveTo(*cap_first)
    pen.curveTo(*cap_second)
    for curve in lower_curves:
        pen.curveTo(*curve)
    pen.lineTo((542, 782))
    pen.curveTo((566, 785), (576, 795), (578, 809))
    pen.closePath()
    return outline


def _prototype_fold(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    if variant == "a":
        pen.moveTo((640, 687))
        pen.lineTo((747, 687))
        pen.curveTo((751, 687), (754, 689), (757, 693))
        pen.lineTo((795, 735))
        pen.curveTo((820, 716), (840, 684), (850, 650))
        pen.lineTo((832, 638))
        pen.lineTo((832, 480))
        pen.lineTo((767, 480))
        pen.lineTo((767, 657))
        pen.lineTo((640, 657))
    elif variant == "b":
        _, genryu_right = _split_cubic(
            (795, 735),
            (884, 667),
            (884, 657),
            (858, 647),
            0.05,
        )
        pen.moveTo((640, 687))
        pen.lineTo((744, 687))
        pen.curveTo((750, 687), (755, 687), (761, 692))
        pen.lineTo((788, 724))
        pen.curveTo((794, 731), (800, 731), genryu_right[0])
        pen.curveTo(*genryu_right[1:])
        pen.lineTo((832, 638))
        pen.lineTo((832, 480))
        pen.lineTo((767, 480))
        pen.lineTo((767, 657))
        pen.lineTo((640, 657))
    else:
        pen.moveTo((640, 690))
        pen.lineTo((736, 690))
        pen.curveTo((748, 688), (756, 694), (763, 704))
        pen.lineTo((790, 748))
        pen.curveTo((828, 727), (862, 688), (875, 642))
        pen.lineTo((842, 628))
        pen.lineTo((842, 480))
        pen.lineTo((760, 480))
        pen.lineTo((760, 652))
        pen.lineTo((640, 652))
    pen.closePath()
    return outline


def _prototype_box(
    *,
    left_variant: str | None = None,
    right_variant: str | None = None,
    left_top_variant: str | None = None,
) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((778, 111))
    pen.lineTo((225, 111))
    pen.lineTo((225, 657))
    pen.lineTo((778, 657))
    pen.closePath()
    pen.moveTo((225, 82))
    pen.lineTo((778, 82))
    if right_variant == "a":
        pen.lineTo((778, 12))
        pen.curveTo((778, -13), (784, -27), (796, -27))
        pen.curveTo((815, -27), (840, -15), (846, -6))
        pen.lineTo((846, 638))
    elif right_variant == "b":
        pen.lineTo((778, 45))
        pen.curveTo((777, 32), (777, 16), (776, -7))
        pen.curveTo((776, -17), (782, -27), (788, -27))
        pen.curveTo((812, -27), (843, -12), (849, -4))
        pen.curveTo((847, 74), (846, 134), (845, 234))
        pen.lineTo((845, 638))
    elif right_variant == "c":
        pen.lineTo((778, 58))
        pen.curveTo((775, 22), (769, 1), (770, -11))
        pen.curveTo((771, -29), (783, -37), (800, -35))
        pen.curveTo((825, -32), (854, -15), (858, -1))
        pen.curveTo((850, 70), (845, 146), (842, 250))
        pen.lineTo((842, 638))
    else:
        pen.lineTo((778, -27))
        pen.lineTo((788, -27))
        pen.curveTo((812, -27), (844, -12), (846, -6))
        pen.lineTo((846, 638))
    pen.curveTo((871, 643), (891, 652), (900, 662))
    pen.lineTo((807, 735))
    pen.lineTo((766, 687))
    if left_top_variant == "a":
        pen.lineTo((232, 687))
        pen.curveTo((210, 697), (174, 714), (158, 722))
        pen.lineTo((158, 180))
    elif left_top_variant == "b":
        pen.lineTo((242, 687))
        pen.lineTo((151.5, 727))
        pen.curveTo((156, 704), (158, 657), (158, 620))
        pen.lineTo((158, 180))
    elif left_top_variant == "c":
        pen.lineTo((254, 690))
        pen.curveTo((270, 705), (220, 729), (134, 734))
        pen.curveTo((145, 700), (158, 655), (158, 610))
        pen.lineTo((158, 180))
    else:
        pen.lineTo((232, 687))
        pen.lineTo((158, 722))
    if left_variant == "a":
        pen.lineTo((158, -8))
        pen.curveTo((158, -27), (168, -40), (183, -40))
        pen.curveTo((205, -40), (225, -24), (225, -8))
        pen.curveTo((225, 8), (225, 27), (225, 50))
        pen.lineTo((225, 82))
    elif left_variant == "b":
        pen.lineTo((158, 180))
        pen.curveTo((158, 100), (155, 48), (151, -20))
        pen.curveTo((151, -30), (162, -40), (175, -40))
        pen.curveTo((204, -40), (225, -23), (229, -9))
        pen.curveTo((227, 7), (225, 18), (225, 50))
        pen.lineTo((225, 82))
    elif left_variant == "c":
        pen.lineTo((158, 190))
        pen.curveTo((158, 95), (150, 25), (143, -23))
        pen.curveTo((143, -38), (160, -50), (181, -47))
        pen.curveTo((213, -45), (238, -24), (239, -5))
        pen.curveTo((237, 17), (228, 37), (225, 58))
        pen.lineTo((225, 82))
    else:
        pen.lineTo((158, -40))
        pen.lineTo((170, -40))
        pen.curveTo((200, -40), (225, -23), (225, -14))
        pen.lineTo((225, 82))
    pen.closePath()
    return outline


def _prototype_box_left_bottom(variant: str) -> pathops.Path:
    return _prototype_box(left_variant=variant)


def _prototype_box_right_bottom(variant: str) -> pathops.Path:
    return _prototype_box(right_variant=variant)


def _prototype_box_left_top(variant: str) -> pathops.Path:
    return _prototype_box(left_top_variant=variant)


def _prototype_left_sweep_start(variant: str) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((347, 560))
    pen.lineTo((347, 616))
    if variant == "a":
        pen.curveTo((373, 691), (393, 767), (406, 839))
        pen.curveTo((440, 838), (486, 828), (516, 814))
        pen.curveTo((512, 801), (504, 794), (476, 793))
    elif variant == "b":
        pen.curveTo((350, 626), (353, 636), (356, 645))
        pen.curveTo((376, 708), (391, 791), (392, 846))
        pen.curveTo((509, 819), (509, 809), (490, 801))
        pen.lineTo((471, 793))
    else:
        pen.curveTo((346, 635), (348, 649), (351, 662))
        pen.curveTo((368, 727), (379, 813), (380, 852))
        pen.curveTo((443, 844), (507, 827), (526, 809))
        pen.curveTo((516, 796), (497, 789), (472, 790))
    pen.curveTo((461, 736), (443, 676), (420, 616))
    pen.lineTo((420, 560))
    pen.closePath()
    return outline


PROTOTYPES = {
    "start": _prototype_start,
    "end": _prototype_end,
    "uroko": _prototype_uroko,
    "horizontal-start": _prototype_horizontal_start,
    "dot": _prototype_dot,
    "left-sweep": _prototype_left_sweep,
    "right-sweep": _prototype_right_sweep,
    "hook": _prototype_hook,
    "fold": _prototype_fold,
    "box-left-bottom": _prototype_box_left_bottom,
    "box-right-bottom": _prototype_box_right_bottom,
    "box-left-top": _prototype_box_left_top,
    "left-sweep-start": _prototype_left_sweep_start,
}


LOCAL_EDIT_LABELS = {
    "a": "A 小丸め",
    "b": "B 指定案",
    "c": "C 強丸め",
}
LOCAL_EDIT_NOTES = {
    "dot": {
        "a": "Noto輪郭を保ち、左上の裁ち落としだけを小さく丸める。",
        "b": "Noto輪郭を保ち、左上の二点だけへ中程度の丸みを加える。",
        "c": "Noto輪郭を保ち、左上の裁ち落としを強く丸める。",
    },
    "left-sweep": {
        "a": "丿の曲率を保ち、左下の裁ち落としだけを小さく丸める。",
        "b": "丿の曲率を保ち、左下の筆端だけへ中程度の丸みを加える。",
        "c": "丿の曲率を保ち、左下の筆端を強く丸める。",
    },
    "right-sweep": {
        "a": "乀の曲率を保ち、右下の裁ち落としだけを小さく丸める。",
        "b": "乀の曲率を保ち、右下の筆端だけへ中程度の丸みを加える。",
        "c": "乀の曲率を保ち、右下の筆端を強く丸める。",
    },
    "hook": {
        "a": "Noto構造を保ち、左端と下部へ控えめな丸みを加える。",
        "b": "参考SVGの流れを整理し、左端の丸みから深いえぐり、右の立ち上がりまでを連続する曲線にした指定案。",
        "c": "左端を強く丸め、下部のえぐりと曲率を大きくする。",
    },
    "fold": {
        "a": "ウロコ形を保ち、右斜めへ立ち上がる起点だけを小さく丸める。",
        "b": "源流明朝の折れを基礎に、左上の斜画起点と上端を確定ウロコBと同じ二段の丸みにした指定案。",
        "c": "ウロコ形を保ち、斜画起点と折れの曲率を強くする。",
    },
    "box-left-bottom": {
        "a": "Notoの長い左縦画を保ち、三つの曲線で小さく溜めて底辺内側へ戻す案。",
        "b": "源流明朝の四曲線構造をNotoの幅へ正規化し、左へわずかに膨らんでから底辺内側へ戻す案。",
        "c": "左への膨らみ、底の沈み、内側への戻りを強くした荒筆案。",
    },
    "box-right-bottom": {
        "b": "源流明朝の四曲線構造を使い、内外の輪郭位置をNotoと源流明朝の中間へ置いて右脚の幅を整えた確定案。",
        "c": "内側へのくびれ、底の沈み、右への張りと縦画への立ち上がりを強くした荒筆案。",
    },
    "box-left-top": {
        "a": "Notoの斜めの接続を一曲線へ替え、縦画上端を控えめに丸める簡潔案。",
        "b": "源流明朝と同じく横画から張り出し点までは直線とし、左外辺だけを一曲線で縦画へ戻す。左への張り出しは従来案の半分。",
        "c": "縦画起筆Cの張りを強調し、左への膨らみと横画へ戻る流れを大きくした荒筆案。",
    },
    "left-sweep-start": {
        "a": "Notoの斜画両辺を保ち、直線だった上端だけを一曲線で控えめに丸める簡潔案。",
        "b": "源流明朝の二段の左辺、深く戻る上端曲線、短い接続直線を正規化した源流構造案。",
        "c": "左への張りと上端の置きを強くし、右辺へ戻るまでを二曲線にした荒筆案。",
    },
}


def _prototype_outline(element: str, variant: str) -> pathops.Path:
    prototype = PROTOTYPES.get(element)
    if prototype is None:
        raise ValueError(f"No prototype registered for element {element!r}")
    return prototype(variant)


def _design_filename(element: str, variant: str) -> str:
    suffix = {"noto": "Noto", "genryu": "Genryu"}.get(variant, variant.upper())
    return f"{element}-{suffix}.svg"


def _write_editable_svg(
    outline,
    crop: tuple[float, float, float, float],
    path: Path,
) -> None:
    x_min, y_min, x_max, y_max = crop
    width = x_max - x_min
    height = y_max - y_min
    svg_pen = SVGPathPen(None)
    to_svg = Transform(1, 0, 0, -1, -x_min, y_max)
    outline.draw(TransformPen(svg_pen, to_svg))
    path.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width:g}" height="{height:g}" '
            f'viewBox="0 0 {width:g} {height:g}">\n'
            f'  <path id="outline" d="{svg_pen.getCommands()}" '
            'fill="#171512"/>\n'
            "</svg>\n"
        ),
        encoding="utf-8",
    )


def _outline_terms(outline, *, reference: bool) -> str:
    if reference:
        return "青: オンカーブ点 / 赤: オフカーブ制御点"
    recording = RecordingPen()
    outline.draw(recording)
    line_count = sum(operator == "lineTo" for operator, _ in recording.value)
    cubic_count = sum(operator == "curveTo" for operator, _ in recording.value)
    contour_count = sum(operator == "moveTo" for operator, _ in recording.value)
    on_curve_count = contour_count + line_count + cubic_count
    off_curve_count = cubic_count * 2
    return (
        f"直線セグメント {line_count} / "
        f"三次ベジェセグメント {cubic_count} / "
        f"オンカーブ点 {on_curve_count} / "
        f"オフカーブ制御点 {off_curve_count}"
    )


def _svg(outline, crop: tuple[float, float, float, float]) -> str:
    x_min, y_min, x_max, y_max = crop
    width = x_max - x_min
    height = y_max - y_min
    svg_pen = SVGPathPen(None)
    outline.draw(svg_pen)
    recording = RecordingPen()
    outline.draw(recording)
    overlays: list[str] = []
    current = None
    for operator, operands in recording.value:
        if operator == "moveTo":
            current = operands[-1]
            overlays.append(
                f'<circle class="anchor" cx="{current[0]}" cy="{current[1]}" r="2.4"/>'
            )
        elif operator == "lineTo" and current is not None:
            current = operands[-1]
            overlays.append(
                f'<circle class="anchor" cx="{current[0]}" cy="{current[1]}" r="2.4"/>'
            )
        elif operator == "curveTo" and current is not None:
            first, second, end = operands
            overlays.extend(
                (
                    f'<line x1="{current[0]}" y1="{current[1]}" x2="{first[0]}" y2="{first[1]}"/>',
                    f'<line x1="{end[0]}" y1="{end[1]}" x2="{second[0]}" y2="{second[1]}"/>',
                    f'<circle class="control" cx="{first[0]}" cy="{first[1]}" r="2"/>',
                    f'<circle class="control" cx="{second[0]}" cy="{second[1]}" r="2"/>',
                    f'<circle class="anchor" cx="{end[0]}" cy="{end[1]}" r="2.4"/>',
                )
            )
            current = end
    transform = f"translate({-x_min:g} {y_max:g}) scale(1 -1)"
    return (
        f'<svg viewBox="0 0 {width:g} {height:g}" role="img" '
        'aria-label="拡大した輪郭と制御点">'
        f'<g transform="{transform}"><path d="{svg_pen.getCommands()}"/>'
        f'<g class="handles">{"".join(overlays)}</g></g></svg>'
    )


def _pattern_outline(
    pattern: Pattern,
    noto: TTFont,
    genryu: TTFont,
    element: str,
    codepoint: int,
    reference_contour: int | None,
):
    if pattern.key == "noto":
        return _glyph_path(noto, codepoint, reference_contour)
    if pattern.key == "genryu":
        return _glyph_path(genryu, codepoint, reference_contour)
    return _prototype_outline(element, pattern.key)


def _box_combination_section(noto: TTFont, genryu: TTFont) -> str:
    crop = (100.0, -90.0, 920.0, 770.0)
    cards = [
        (
            "Noto",
            _glyph_path(noto, 0x53E3),
            "編集前。左右下隅とも直線主体。",
        ),
        (
            "源流明朝",
            _glyph_path(genryu, 0x53E3),
            "実輪郭。左右下隅とも四つの曲線で筆圧をつなぐ。",
        ),
    ]
    cards.extend(
        (
            f"左{left.upper()}・右{right.upper()}",
            _prototype_box(left_variant=left, right_variant=right),
            "左右下隅を同時に適用した組み合わせ。",
        )
        for left in ("a", "b", "c")
        for right in ("a", "b", "c")
    )
    cards.extend(
        (
            f"左上{top.upper()}・下隅B/B",
            _prototype_box(
                left_variant="b",
                right_variant="b",
                left_top_variant=top,
            ),
            "確定した左右下隅Bへ、左上候補を同時に適用。",
        )
        for top in ("a", "b", "c")
    )
    rendered = "".join(
        f'<article class="card"><h3>{label}</h3>{_svg(outline, crop)}'
        f"<p>{note}</p></article>"
        for label, outline, note in cards
    )
    return (
        '<section id="box-combinations"><header>'
        '<p class="eyebrow">COMBINATION</p><h2>囲み角 組み合わせ</h2>'
        "<p>左右下隅の9通りと、確定下隅B/Bへ左上A/B/Cを"
        "適用した3通りで、口全体の重心と筆圧の流れを比較。</p></header>"
        f'<div class="cards combination-cards">{rendered}</div></section>'
    )


def _left_sweep_context_section(noto: TTFont, genryu: TTFont) -> str:
    references = (
        ("右", 0x53F3, (320.0, 570.0, 545.0, 875.0)),
        ("左", 0x5DE6, (315.0, 570.0, 535.0, 875.0)),
        ("区", 0x533A, (620.0, 550.0, 825.0, 735.0)),
        ("有", 0x6709, (330.0, 610.0, 555.0, 880.0)),
    )
    rendered = "".join(
        f'<article class="card"><h3>{char}・{family}</h3>'
        f"{_svg(_glyph_path(font, codepoint), crop)}"
        "<p>実輪郭の払い上部。</p></article>"
        for char, codepoint, crop in references
        for family, font in (("Noto", noto), ("源流明朝", genryu))
    )
    return (
        '<section id="left-sweep-contexts"><header>'
        '<p class="eyebrow">CONTEXT</p><h2>左払い上部 実字形</h2>'
        "<p>右・左・区・有で、右上から左下へ向かう斜画の"
        "上端構造と周囲の接続を比較。</p></header>"
        f'<div class="cards">{rendered}</div></section>'
    )


def _page(
    noto: TTFont,
    genryu: TTFont,
    export_dir: Path,
    export_href: str,
    selection: dict[str, str],
) -> str:
    sections: list[str] = []
    for element in ELEMENTS:
        element_key = element.key
        title = element.label
        codepoint = element.codepoint
        crop = element.crop
        description = element.description
        confirmed_choice = selection.get(element_key)
        cards: list[str] = []
        for pattern in PATTERNS:
            if pattern.key == "d" and element_key != "end":
                continue
            outline = _pattern_outline(
                pattern,
                noto,
                genryu,
                element_key,
                codepoint,
                element.reference_contour,
            )
            choice = pattern.key.upper()
            selectable = pattern.key in {"a", "b", "c"} or (
                element_key == "end" and pattern.key == "d"
            )
            filename = _design_filename(element_key, pattern.key)
            _write_editable_svg(
                outline,
                crop,
                export_dir / filename,
            )
            if selectable:
                control = (
                    '<div class="card-actions">'
                    f'<label class="pick"><input type="radio" '
                    f'name="{element_key}" value="{choice}"'
                    f'{" checked" if pattern.key == confirmed_choice else ""}>'
                    f"{choice}を選ぶ</label>"
                    f'<a href="{export_href}/{filename}" download>'
                    "参考SVGを書き出す</a>"
                    '<label class="upload">参考SVGを一時プレビュー'
                    f'<input type="file" accept=".svg,image/svg+xml" '
                    f'data-preview="{element_key}-{choice}"></label>'
                    "</div>"
                )
            else:
                control = (
                    '<div class="card-actions">'
                    f'<a href="{export_href}/{filename}" download>'
                    "参考SVGを書き出す</a></div>"
                )
            selected = " selected" if pattern.key == confirmed_choice else ""
            note = pattern.note
            card_label = pattern.label
            local_notes = LOCAL_EDIT_NOTES.get(element_key)
            if local_notes is not None and pattern.key in local_notes:
                card_label = LOCAL_EDIT_LABELS[pattern.key]
                note = local_notes[pattern.key]
            if element_key in {
                "box-left-bottom",
                "box-right-bottom",
                "box-left-top",
                "left-sweep-start",
            }:
                card_label = pattern.label
            terms = _outline_terms(
                outline,
                reference=pattern.key in {"noto", "genryu"},
            )
            if element_key == "uroko" and pattern.key == "b":
                note = "右斜めへ立ち上がる起点と天頂だけへ" "小さな丸みを加えた確定案。"
            if element_key == "start" and pattern.key == "b":
                note = (
                    "左辺は白銀比から求めた仮想円弧で長く収束し、"
                    "右辺は独立した短い筆置き曲線で戻す。"
                    "左右の収束位置は揃えない。"
                )
            if element_key == "end" and pattern.key == "b":
                card_label = "B 白銀比"
                note = (
                    "縦画幅と一つの基準点から全節点を導出する。"
                    "左右の長い収束と、左寄りの最下点から右へ返す筆圧を持つ。"
                )
            if element_key == "end" and pattern.key == "c":
                card_label = "C 伝統的"
                note = (
                    "白銀比と共通の節点順を使いながら、"
                    "張り出しと収束長を抑えた古典的な留め。"
                )
            if element_key == "end" and pattern.key == "d":
                card_label = "D 穏健"
                note = (
                    "側面を三次smoothstep、底部を四分楕円として接線を連続させ、"
                    "張り出しを白銀比圧力の3分の1へ抑えた静かな留め。"
                )
            if element_key == "horizontal-start" and pattern.key == "b":
                note = (
                    "横画幅に対する白銀比で上下頂点を置き、"
                    "下側接点へ上側接点を揃えた二つの仮想円弧。"
                    "上側は接続距離に応じて大きい半径を使う。"
                )
            cards.append(
                f'<article id="card-{element_key}-{choice}" '
                f'class="card {pattern.key}{selected}" '
                f'data-element="{element_key}" data-choice="{choice}">'
                f"<h3>{card_label}</h3>{_svg(outline, crop)}"
                f'<p>{note}</p><p class="topology">{terms}</p>'
                f"{control}</article>"
            )
        sections.append(
            f'<section id="{element_key}"><header><p class="eyebrow">ELEMENT</p>'
            f"<h2>{title}</h2><p>{description}</p></header>"
            f'<div class="cards">{"".join(cards)}</div></section>'
        )
    sections.append(_box_combination_section(noto, genryu))
    sections.append(_left_sweep_context_section(noto, genryu))
    labels = {element.key: element.label for element in ELEMENTS}
    initial_selection = "・".join(
        f"{element.label}{selection.get(element.key, '未選択').upper()}"
        for element in ELEMENTS
    )
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>漢字毛筆エレメント デザインパターン</title>
<style>
:root{{--ink:#171512;--paper:#f3efe7;--card:#fffdf8;--line:#d7ccbb;--accent:#8f2d20}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Noto Sans JP",sans-serif}}
main{{max-width:1640px;margin:auto;padding:48px 36px 80px}}h1{{font:700 38px/1.2 serif;margin:0 0 12px}}.lead{{max-width:900px;font-size:17px;line-height:1.8;margin:0 0 52px}}
section{{border-top:1px solid var(--line);padding:34px 0 46px}}section>header{{display:grid;grid-template-columns:120px 120px 1fr;align-items:baseline;gap:12px;margin-bottom:20px}}h2{{font:700 28px serif;margin:0}}.eyebrow{{font:700 11px monospace;letter-spacing:.14em;color:var(--accent)}}section header p{{margin:0;line-height:1.6}}
        .cards{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}}#end .cards{{grid-template-columns:repeat(6,minmax(0,1fr))}}.card{{background:var(--card);border:1px solid var(--line);padding:16px;min-width:0}}.card.selected{{border:3px solid var(--accent);padding:14px}}h3{{margin:0 0 10px;font-size:16px}}svg{{display:block;width:100%;height:360px;background:#fff;border:1px solid #eee}}svg path{{fill:var(--ink)}}.card p{{font-size:13px;line-height:1.6;min-height:42px;margin:10px 0;color:#554d43}}.choice{{display:inline-block;padding:4px 8px;background:var(--accent);color:white;font:700 12px monospace;margin-left:8px}}.pick{{display:block;border-top:1px solid var(--line);padding-top:10px;font-weight:700;cursor:pointer}}.pick input{{margin-right:8px}}.selection{{position:sticky;top:12px;z-index:2;display:flex;gap:14px;align-items:center;background:#171512;color:#fff;padding:12px 16px;margin:0 0 36px;font:700 13px/1.5 monospace}}.selection output{{flex:1}}button{{font:inherit;cursor:pointer}}.combination-cards .card p{{min-height:0}}
svg{{overflow:hidden}}
.handles line{{stroke:#3478a8;stroke-width:.8;vector-effect:non-scaling-stroke}}.handles .anchor{{fill:#1677b8;stroke:white;stroke-width:.6;vector-effect:non-scaling-stroke}}.handles .control{{fill:#d4422f;stroke:white;stroke-width:.6;vector-effect:non-scaling-stroke}}.hide-handles .handles{{display:none}}.topology{{font-family:monospace;color:var(--accent)!important;min-height:0!important}}#nodes{{border:1px solid #fff;background:transparent!important}}
.card-actions{{display:grid;gap:8px;border-top:1px solid var(--line);padding-top:10px}}.card-actions .pick{{border:0;padding:0}}.card-actions a,.upload{{display:block;padding:7px 9px;border:1px solid var(--line);background:#fff;color:var(--ink);font-size:12px;font-weight:700;text-decoration:none;cursor:pointer}}.upload input{{display:block;width:100%;margin-top:6px;font-size:10px}}.card.custom{{outline:3px dashed #3478a8;outline-offset:-7px}}.card.custom .topology{{color:#3478a8!important}}
        @media(max-width:1000px){{.cards,#end .cards{{grid-template-columns:repeat(2,1fr)}}section>header{{grid-template-columns:1fr}}}}@media(max-width:600px){{main{{padding:24px 14px}}.cards,#end .cards{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>漢字毛筆エレメント デザインパターン</h1>
        <p class="lead">フォント全体をビルドせず、コードで定義したエレメント単体の輪郭トポロジーをSVGで比較します。A / B / Cは比率違いではなく、輪郭セグメントとオンカーブ点・オフカーブ制御点の構成自体が異なります。終筆Dは、角のない穏やかな別構造を追加比較します。書き出したSVGと保管済みSVGは判断・指示用の参考データであり、コードへ再入力しません。Inkscapeで試作した輪郭は、同じカードのファイル入力へ読み込むとその場だけでプレビューできます。<span class="choice">確定選択はselection.jsonから読込</span></p>
<div class="selection"><output id="selection">{initial_selection}</output><button id="nodes" type="button">制御点を隠す</button><button id="copy" type="button">選択をコピー</button><button id="save" type="button">選択JSONを保存</button></div>
{"".join(sections)}</main><script>
const labels={json.dumps(labels, ensure_ascii=False)};
const update=()=>{{
  const choices=Object.keys(labels).map(name=>{{
    const checked=document.querySelector(`input[name="${{name}}"]:checked`);
    document.querySelectorAll(`[data-element="${{name}}"]`).forEach(card=>card.classList.remove("selected"));
    checked?.closest(".card")?.classList.add("selected");
    return `${{labels[name]}}${{checked?.value ?? "未選択"}}`;
  }});
  document.querySelector("#selection").textContent=choices.join("・");
}};
document.querySelectorAll('input[type="radio"]').forEach(input=>input.addEventListener("change",update));
document.querySelector("#copy").addEventListener("click",async()=>{{
  const text=document.querySelector("#selection").textContent;
  await navigator.clipboard.writeText(text);
  document.querySelector("#copy").textContent="コピー済み";
}});
document.querySelector("#save").addEventListener("click",()=>{{
  const selected=Object.fromEntries(Object.keys(labels).flatMap(name=>{{
    const choice=document.querySelector(`input[name="${{name}}"]:checked`)?.value;
    return choice ? [[name,choice]] : [];
  }}));
  const pending=Object.keys(labels).filter(name=>
    !document.querySelector(`input[name="${{name}}"]:checked`)
  );
  const blob=new Blob([JSON.stringify({{version:1,selected,pending}},null,2)+"\\n"],{{type:"application/json"}});
  const link=document.createElement("a");
  link.href=URL.createObjectURL(blob);
  link.download="selection.json";
  link.click();
  URL.revokeObjectURL(link.href);
}});
document.querySelector("#nodes").addEventListener("click",()=>{{
  document.body.classList.toggle("hide-handles");
  document.querySelector("#nodes").textContent=
    document.body.classList.contains("hide-handles") ? "制御点を表示" : "制御点を隠す";
}});
document.querySelectorAll("[data-preview]").forEach(input=>{{
  input.addEventListener("change",async()=>{{
    const file=input.files?.[0];
    if(!file)return;
    const documentSvg=new DOMParser().parseFromString(await file.text(),"image/svg+xml");
    const sourceSvg=documentSvg.querySelector("svg");
    const sourcePath=documentSvg.querySelector("path#outline")??documentSvg.querySelector("path");
    if(!sourceSvg||!sourcePath)throw new Error("SVGにpath#outlineがありません");
    const card=input.closest(".card");
    const target=card.querySelector("svg");
    target.setAttribute("viewBox",sourceSvg.getAttribute("viewBox")??target.getAttribute("viewBox"));
    target.replaceChildren(sourcePath.cloneNode(true));
    card.classList.add("custom");
    card.querySelector(".topology").textContent="編集SVGを一時プレビュー中";
  }});
}});
update();
</script></body></html>"""


def main() -> None:
    args = _args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_dir = (
        args.export_svg_dir
        if args.export_svg_dir is not None
        else args.output.parent / "brush-element-designs"
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    export_href = os.path.relpath(
        export_dir,
        args.output.parent,
    ).replace(os.sep, "/")
    selection = _load_selection(args.selection)
    noto = TTFont(args.noto, recalcTimestamp=False)
    genryu = TTFont(args.genryu, recalcTimestamp=False)
    page = _page(
        noto,
        genryu,
        export_dir,
        export_href,
        selection,
    )
    args.output.write_text(page, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
