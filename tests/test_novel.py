from __future__ import annotations

from io import BytesIO
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pathops
from fontTools.cffLib import FDArrayIndex, FDSelect, FontDict
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from nobigoe_font.cli import parse_args
from nobigoe_font.geometry import glyph_path
from nobigoe_font.novel import (
    COUNTER_HIRAGANA_CODEPOINTS,
    HIRAGANA_CODEPOINTS,
    ITERATION_HIRAGANA_CODEPOINTS,
    NOVEL_KA_CODEPOINT,
    NOVEL_KA_TERMINAL_MASTER_RAISES,
    NOVEL_MASTER_PROFILES,
    NOVEL_VERTICAL_MASTER_PROFILES,
    NOVEL_VERTICAL_STEM_GROUPS,
    NOVEL_VERTICAL_STEM_MASTER_PROFILES,
    NOVEL_SMALL_KO_CODEPOINT,
    SMALL_HIRAGANA_CODEPOINTS,
    _KA_OVERLAP_SLIVER_MAX_AREA,
    _round_terminal_path_for_cff,
    apply_novel_hiragana,
    novel_group_for_codepoint,
    novel_ka_terminal_raise,
    novel_vertical_transform,
    novel_vertical_stem_adjustment,
    novel_vertical_stem_group,
    novel_transform,
    shorten_novel_ka_terminal,
)
from nobigoe_font.novel_metrics import _glyph_metrics


def _rectangle_glyph() -> object:
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((900, 0))
    pen.lineTo((900, 800))
    pen.lineTo((100, 800))
    pen.closePath()
    return pen.glyph()


def _ka_topology_path() -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((250, 350))
    pen.lineTo((130, 100))
    pen.lineTo((100, 0))
    pen.lineTo((140, 0))
    pen.lineTo((200, 100))
    pen.lineTo((300, 350))
    pen.lineTo((360, 80))
    pen.lineTo((330, 50))
    pen.lineTo((500, 500))
    pen.closePath()
    pen.moveTo((134, 104))
    pen.lineTo((244, 316))
    pen.curveTo((208, 240), (176, 174), (134, 104))
    pen.closePath()
    pen.moveTo((330, 320))
    pen.lineTo((350, 370))
    pen.lineTo((370, 350))
    pen.closePath()
    pen.moveTo((350, 340))
    pen.lineTo((390, 450))
    pen.lineTo((430, 410))
    pen.closePath()
    return path


def _contained_sliver_indices(outline: pathops.Path) -> tuple[int, ...]:
    contours = tuple(outline.contours)
    main_index = min(
        range(len(contours)),
        key=lambda index: contours[index].bounds[1],
    )
    main_contour = pathops.Path()
    contours[main_index].draw(main_contour.getPen())
    return tuple(
        index
        for index, contour in enumerate(contours)
        if index != main_index
        and contour.clockwise
        and contour.area <= _KA_OVERLAP_SLIVER_MAX_AREA
        and main_contour.contains(
            (
                sum(x for x, _ in contour.points) / len(contour.points),
                sum(y for _, y in contour.points) / len(contour.points),
            )
        )
    )


def _ka_topology_charstring():
    pen = T2CharStringPen(1000, None)
    _ka_topology_path().draw(pen)
    return pen.getCharString()


_CFF_TARGET = "cid00001"


def _novel_cff_test_font() -> TTFont:
    builder = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", _CFF_TARGET]
    builder.setupGlyphOrder(glyph_order)
    builder.setupHorizontalMetrics({name: (1000, 100) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupVerticalMetrics({name: (1000, 80) for name in glyph_order})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    builder.setupCharacterMap({ord("か"): _CFF_TARGET})
    builder.setupNameTable(
        {
            "familyName": "Test",
            "styleName": "Regular",
            "psName": "Test-Regular",
        }
    )
    builder.setupOS2()
    builder.setupPost()
    builder.setupCFF(
        "Test-Regular",
        {},
        {name: _ka_topology_charstring() for name in glyph_order},
        {},
    )
    font = builder.font
    top = font["CFF "].cff.topDictIndex[0]
    private = top.Private
    fd_array = FDArrayIndex()
    fd_array.strings = None
    fd_array.GlobalSubrs = top.GlobalSubrs
    font_dict = FontDict()
    font_dict.setCFF2(False)
    font_dict.FontName = "Test-Regular-Kana"
    font_dict.Private = private
    fd_array.append(font_dict)
    fd_select = FDSelect()
    fd_select.format = 3
    fd_select.gidArray = [0] * len(glyph_order)
    top.FDArray = fd_array
    top.FDSelect = fd_select
    top.ROS = ("Adobe", "Identity", 0)
    top.CIDCount = len(glyph_order)
    del top.Private
    top.CharStrings.fdArray = fd_array
    top.CharStrings.fdSelect = fd_select
    for charstring in top.CharStrings.values():
        charstring.fdSelectIndex = 0
    buffer = BytesIO()
    font.save(buffer)
    buffer.seek(0)
    return TTFont(buffer)


def _novel_test_font():
    builder = FontBuilder(1000, isTTF=True)
    glyph_order = [".notdef", "horizontal", "vertical"]
    builder.setupGlyphOrder(glyph_order)
    builder.setupGlyf({name: _rectangle_glyph() for name in glyph_order})
    builder.setupHorizontalMetrics({name: (1000, 100) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupVerticalMetrics({name: (1000, 80) for name in glyph_order})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    builder.setupCharacterMap({0x3042: "horizontal"})
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


class NovelDesignTests(unittest.TestCase):
    def test_contracted_hiragana_set_and_groups_are_complete(self) -> None:
        self.assertEqual(len(HIRAGANA_CODEPOINTS), 89)
        self.assertEqual(min(HIRAGANA_CODEPOINTS), 0x3041)
        self.assertEqual(max(HIRAGANA_CODEPOINTS), 0x309F)
        self.assertEqual(novel_group_for_codepoint(ord("あ")), "counter")
        self.assertEqual(novel_group_for_codepoint(ord("が")), "normal")
        self.assertEqual(novel_group_for_codepoint(ord("ゔ")), "normal")
        self.assertEqual(novel_group_for_codepoint(ord("ょ")), "small")
        self.assertEqual(novel_group_for_codepoint(ord("ゞ")), "iteration")
        self.assertEqual(novel_group_for_codepoint(NOVEL_SMALL_KO_CODEPOINT), "small")
        self.assertIn(ord("ゐ"), COUNTER_HIRAGANA_CODEPOINTS)
        self.assertIn(ord("ゕ"), SMALL_HIRAGANA_CODEPOINTS)
        self.assertEqual(ITERATION_HIRAGANA_CODEPOINTS, {ord("ゝ"), ord("ゞ")})

    def test_three_masters_interpolate_all_seven_weights(self) -> None:
        self.assertEqual(tuple(NOVEL_MASTER_PROFILES), (200, 400, 900))
        self.assertEqual(novel_transform(200, "normal").sx, 0.95)
        self.assertEqual(novel_transform(400, "counter").sx, 0.94)
        self.assertEqual(novel_transform(900, "counter").sx, 0.925)
        light = novel_transform(300, "normal")
        self.assertAlmostEqual(light.sx, 0.945)
        self.assertAlmostEqual(light.sy, 0.955)
        self.assertEqual(light.stem_adjustment, 1.0)
        self.assertEqual(novel_transform(700, "normal").stem_adjustment, 0.0)
        self.assertEqual(novel_transform(500, "normal").stem_adjustment, 0.4)
        self.assertEqual(novel_transform(600, "normal").stem_adjustment, 0.3)
        for weight in (200, 300, 400, 500, 600, 700, 900):
            for group in ("normal", "counter", "small", "iteration"):
                transform = novel_transform(weight, group)
                self.assertGreater(transform.sx, 0)
                self.assertGreater(transform.sy, 0)

    def test_ka_terminal_correction_interpolates_three_optical_masters(
        self,
    ) -> None:
        self.assertEqual(
            NOVEL_KA_TERMINAL_MASTER_RAISES,
            {200: 32, 400: 36, 900: 44},
        )
        self.assertEqual(NOVEL_KA_CODEPOINT, ord("か"))
        expected = {
            200: 32,
            300: 34,
            400: 36,
            500: 37.6,
            600: 39.2,
            700: 40.8,
            900: 44,
        }
        for weight, amount in expected.items():
            self.assertAlmostEqual(novel_ka_terminal_raise(weight), amount)

    def test_ka_terminal_removes_overlap_sliver_and_preserves_other_arcs(
        self,
    ) -> None:
        outline = _ka_topology_path()
        shortened = shorten_novel_ka_terminal(outline, 36)
        before_contours = tuple(outline.contours)
        after_contours = tuple(shortened.contours)

        self.assertEqual(
            len(after_contours),
            len(before_contours) - len(_contained_sliver_indices(outline)),
        )
        main_recording = RecordingPen()
        after_contours[0].draw(main_recording)
        curve_indices = tuple(
            index
            for index, (operator, _) in enumerate(main_recording.value)
            if operator == "curveTo"
        )
        self.assertEqual(len(curve_indices), 1)
        curve_index = curve_indices[0]
        commands = main_recording.value
        before_start = commands[curve_index - 2][1][-1]
        start = commands[curve_index - 1][1][-1]
        first_control, second_control, end = commands[curve_index][1]
        after_end = commands[curve_index + 1][1][-1]

        def normalized_cross(
            first: tuple[float, float],
            second: tuple[float, float],
        ) -> float:
            return abs(first[0] * second[1] - first[1] * second[0]) / (
                math.hypot(*first) * math.hypot(*second)
            )

        self.assertLess(
            normalized_cross(
                (start[0] - before_start[0], start[1] - before_start[1]),
                (
                    first_control[0] - start[0],
                    first_control[1] - start[1],
                ),
            ),
            0.00001,
        )
        self.assertLess(
            normalized_cross(
                (end[0] - second_control[0], end[1] - second_control[1]),
                (after_end[0] - end[0], after_end[1] - end[1]),
            ),
            0.00001,
        )
        for index in (0, 5, 6, 7, 8):
            self.assertIn(
                before_contours[0].points[index],
                after_contours[0].points,
            )
        self.assertEqual(after_contours[1].points, before_contours[3].points)
        self.assertEqual(
            after_contours[1].clockwise,
            before_contours[3].clockwise,
        )
        self.assertEqual(_contained_sliver_indices(shortened), ())

        cap_deltas = tuple(
            (
                after_contours[0].points[index][0]
                - before_contours[0].points[index][0],
                after_contours[0].points[index][1]
                - before_contours[0].points[index][1],
            )
            for index in (2, 3)
        )
        self.assertEqual(cap_deltas[0], cap_deltas[1])
        self.assertGreater(cap_deltas[0][0], 0)
        self.assertEqual(cap_deltas[0][1], 36)
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            shorten_novel_ka_terminal(outline, -1)

    def test_ka_cff_normalization_does_not_reveal_subpixel_segments(
        self,
    ) -> None:
        outline = pathops.Path()
        pen = outline.getPen()
        pen.moveTo((250, 350))
        pen.lineTo((130, 280))
        pen.lineTo((130, 185))
        pen.lineTo((130.49, 185.49))
        pen.lineTo((130, 100))
        pen.lineTo((100, 0))
        pen.lineTo((140, 0))
        pen.lineTo((200, 100))
        pen.lineTo((220, 185))
        pen.lineTo((220, 280))
        pen.lineTo((300, 350))
        pen.lineTo((360, 80))
        pen.lineTo((330, 50))
        pen.lineTo((500, 500))
        pen.closePath()

        stored_before = _round_terminal_path_for_cff(outline)
        unprepared_after = _round_terminal_path_for_cff(
            shorten_novel_ka_terminal(outline, 44)
        )
        prepared_after = _round_terminal_path_for_cff(
            shorten_novel_ka_terminal(stored_before, 44)
        )

        reprepared_after = _round_terminal_path_for_cff(prepared_after)
        self.assertEqual(len(stored_before.verbs), len(outline.verbs) - 1)
        self.assertNotEqual(unprepared_after.verbs, prepared_after.verbs)
        self.assertEqual(reprepared_after.verbs, prepared_after.verbs)
        self.assertEqual(reprepared_after.points, prepared_after.points)
        self.assertTrue(
            all(
                coordinate == round(coordinate)
                for point in prepared_after.points
                for coordinate in point
            )
        )

    def test_ka_sliver_removal_and_protected_arcs_survive_cff_storage(
        self,
    ) -> None:
        reference_font = _novel_cff_test_font()
        corrected_font = _novel_cff_test_font()
        apply_novel_hiragana(
            reference_font,
            400,
            {_CFF_TARGET: "normal"},
            {},
            horizontal_codepoints={_CFF_TARGET: ord("き")},
        )
        apply_novel_hiragana(
            corrected_font,
            400,
            {_CFF_TARGET: "normal"},
            {},
            horizontal_codepoints={_CFF_TARGET: ord("か")},
        )

        with TemporaryDirectory() as temporary_directory:
            reference_path = Path(temporary_directory) / "reference.otf"
            corrected_path = Path(temporary_directory) / "corrected.otf"
            reference_font.save(reference_path)
            corrected_font.save(corrected_path)
            stored_reference = TTFont(reference_path)
            stored_corrected = TTFont(corrected_path)
            before = glyph_path(stored_reference, _CFF_TARGET)
            after = glyph_path(stored_corrected, _CFF_TARGET)

            before_contours = tuple(before.contours)
            after_contours = tuple(after.contours)
            expected = _round_terminal_path_for_cff(
                shorten_novel_ka_terminal(before, 36)
            )
            self.assertEqual(after.verbs, expected.verbs)
            self.assertEqual(after.points, expected.points)
            for index in (0, 5, 6, 7, 8):
                self.assertIn(
                    before_contours[0].points[index],
                    after_contours[0].points,
                )
            sliver_indices = _contained_sliver_indices(before)
            protected_index = next(
                index
                for index in range(1, len(before_contours))
                if index not in sliver_indices
            )
            self.assertEqual(
                len(after_contours),
                len(before_contours) - len(sliver_indices),
            )
            self.assertEqual(_contained_sliver_indices(after), ())
            protected_after = next(
                contour
                for contour in after_contours[1:]
                if contour.area > _KA_OVERLAP_SLIVER_MAX_AREA
            )
            self.assertEqual(
                protected_after.points,
                before_contours[protected_index].points,
            )
            self.assertEqual(
                min(y for _, y in after_contours[0].points)
                - min(y for _, y in before_contours[0].points),
                36,
            )
            self.assertEqual(
                stored_corrected["hmtx"].metrics[_CFF_TARGET],
                stored_reference["hmtx"].metrics[_CFF_TARGET],
            )
            self.assertEqual(
                stored_corrected["vmtx"].metrics[_CFF_TARGET],
                stored_reference["vmtx"].metrics[_CFF_TARGET],
            )
            stored_reference.close()
            stored_corrected.close()

    def test_vertical_masters_and_glyph_corrections_are_independent(self) -> None:
        self.assertEqual(tuple(NOVEL_VERTICAL_MASTER_PROFILES), (200, 400, 900))

        regular_he = novel_vertical_transform(400, "normal", ord("へ"))
        self.assertAlmostEqual(regular_he.sx, 1.03)
        self.assertAlmostEqual(regular_he.sy, 0.88)

        regular_nu = novel_vertical_transform(400, "counter", ord("ぬ"))
        self.assertAlmostEqual(regular_nu.sx, 1.03 * 1.03)
        self.assertAlmostEqual(regular_nu.sy, 0.965)

        for weight in (200, 300, 400, 500, 600, 700, 900):
            low_a = novel_vertical_transform(weight, "counter", ord("あ"))
            small_yo = novel_vertical_transform(weight, "small", ord("ょ"))
            self.assertEqual(low_a.sy, 1)
            self.assertEqual(small_yo.sx, 1)
            self.assertEqual(small_yo.sy, 1)

        self.assertAlmostEqual(
            novel_vertical_transform(200, "normal", ord("へ")).sy,
            0.892,
        )
        self.assertAlmostEqual(
            novel_vertical_transform(900, "normal", ord("へ")).sy,
            0.892,
        )

    def test_vertical_stem_groups_interpolate_and_protect_marks(self) -> None:
        self.assertEqual(
            tuple(NOVEL_VERTICAL_STEM_MASTER_PROFILES),
            (200, 400, 900),
        )
        self.assertEqual(
            NOVEL_VERTICAL_STEM_GROUPS["strong"],
            frozenset(map(ord, "かきけせはも")),
        )
        self.assertEqual(novel_vertical_stem_group(ord("が")), "strong")
        self.assertEqual(novel_vertical_stem_group(ord("ば")), "strong")
        self.assertEqual(novel_vertical_stem_group(ord("な")), "fragile")
        self.assertEqual(novel_vertical_stem_group(ord("た")), "moderate")
        self.assertIsNone(novel_vertical_stem_group(ord("あ")))

        self.assertEqual(novel_vertical_stem_adjustment(200, ord("か")), -0.75)
        self.assertEqual(novel_vertical_stem_adjustment(400, ord("か")), -1.5)
        self.assertEqual(novel_vertical_stem_adjustment(900, ord("か")), -0.75)
        self.assertEqual(novel_vertical_stem_adjustment(300, ord("か")), -1.125)
        self.assertEqual(novel_vertical_stem_adjustment(500, ord("か")), -1.35)
        self.assertEqual(novel_vertical_stem_adjustment(400, ord("な")), -1.0)
        self.assertEqual(novel_vertical_stem_adjustment(400, ord("た")), -0.75)

        self.assertEqual(novel_vertical_stem_adjustment(400, ord("が")), -1.0)
        self.assertEqual(
            novel_vertical_stem_adjustment(400, ord("か"), marked=True),
            -1.0,
        )
        self.assertEqual(
            novel_vertical_transform(
                400,
                "normal",
                ord("か"),
                marked=True,
            ).stem_adjustment,
            -1.0,
        )

    def test_vertical_stem_adjustment_does_not_mutate_horizontal_outline(
        self,
    ) -> None:
        unmarked_font = _novel_test_font()
        marked_font = _novel_test_font()

        apply_novel_hiragana(
            unmarked_font,
            400,
            {"horizontal": "normal"},
            {"vertical": "normal"},
            {"vertical": ord("か")},
        )
        apply_novel_hiragana(
            marked_font,
            400,
            {"horizontal": "normal"},
            {"vertical": "normal"},
            {"vertical": ord("か")},
            {"vertical"},
        )

        unmarked_horizontal = glyph_path(unmarked_font, "horizontal")
        marked_horizontal = glyph_path(marked_font, "horizontal")
        self.assertEqual(unmarked_horizontal.verbs, marked_horizontal.verbs)
        self.assertEqual(unmarked_horizontal.points, marked_horizontal.points)
        self.assertEqual(
            unmarked_font["hmtx"].metrics["horizontal"],
            marked_font["hmtx"].metrics["horizontal"],
        )

        unmarked_vertical = glyph_path(unmarked_font, "vertical")
        marked_vertical = glyph_path(marked_font, "vertical")
        unmarked_vertical.simplify(
            fix_winding=True,
            keep_starting_points=False,
            clockwise=False,
        )
        marked_vertical.simplify(
            fix_winding=True,
            keep_starting_points=False,
            clockwise=False,
        )
        unmarked_metrics = _glyph_metrics(unmarked_vertical, 1000)
        marked_metrics = _glyph_metrics(marked_vertical, 1000)
        self.assertLess(
            unmarked_metrics.signed_ink_area,
            marked_metrics.signed_ink_area,
        )
        self.assertAlmostEqual(
            unmarked_metrics.bbox_height,
            marked_metrics.bbox_height,
            places=3,
        )
        for font in (unmarked_font, marked_font):
            bounds = glyph_path(font, "vertical").bounds
            self.assertLessEqual(
                abs(font["vmtx"].metrics["vertical"][1] + bounds[3] - 880),
                1,
            )

    def test_transform_preserves_advances_and_vertical_origin(self) -> None:
        font = _novel_test_font()
        result = apply_novel_hiragana(
            font,
            400,
            {"horizontal": "counter"},
            {"vertical": "counter"},
            {"vertical": ord("ぬ")},
        )

        self.assertEqual(result.horizontal_glyphs, ("horizontal",))
        self.assertEqual(result.vertical_glyphs, ("vertical",))
        self.assertEqual(font["hmtx"].metrics["horizontal"][0], 1000)
        self.assertEqual(font["vmtx"].metrics["vertical"][0], 1000)
        vertical_bounds = glyph_path(font, "vertical").bounds
        vertical_origin = font["vmtx"].metrics["vertical"][1] + vertical_bounds[3]
        self.assertEqual(vertical_origin, 880)
        horizontal_bounds = glyph_path(font, "horizontal").bounds
        self.assertLess(horizontal_bounds[2] - horizontal_bounds[0], 800)
        self.assertLess(horizontal_bounds[3] - horizontal_bounds[1], 800)
        self.assertGreater(
            vertical_bounds[2] - vertical_bounds[0],
            horizontal_bounds[2] - horizontal_bounds[0],
        )
        self.assertLess(
            vertical_bounds[3] - vertical_bounds[1],
            horizontal_bounds[3] - horizontal_bounds[1],
        )

    def test_ka_correction_is_codepoint_specific_and_alias_safe(self) -> None:
        ka_font = _novel_test_font()
        alias_font = _novel_test_font()
        ki_font = _novel_test_font()
        reference_font = _novel_test_font()

        apply_novel_hiragana(
            ka_font,
            400,
            {"horizontal": "normal"},
            {},
            horizontal_codepoints={"horizontal": ord("か")},
        )
        apply_novel_hiragana(
            alias_font,
            400,
            {"horizontal": "normal"},
            {"horizontal": "normal"},
            {"horizontal": ord("か")},
            horizontal_codepoints={"horizontal": ord("か")},
        )
        apply_novel_hiragana(
            ki_font,
            400,
            {"horizontal": "normal"},
            {},
            horizontal_codepoints={"horizontal": ord("き")},
        )
        apply_novel_hiragana(
            reference_font,
            400,
            {"horizontal": "normal"},
            {},
        )

        ka_path = glyph_path(ka_font, "horizontal")
        alias_path = glyph_path(alias_font, "horizontal")
        ki_path = glyph_path(ki_font, "horizontal")
        reference_path = glyph_path(reference_font, "horizontal")
        self.assertEqual(alias_path.verbs, ka_path.verbs)
        self.assertEqual(alias_path.points, ka_path.points)
        self.assertEqual(ki_path.verbs, reference_path.verbs)
        self.assertEqual(ki_path.points, reference_path.points)

        def lower_left(path: pathops.Path) -> float:
            return min(y for x, y in path.points if x < 200)

        self.assertEqual(lower_left(ka_path) - lower_left(reference_path), 36)

    def test_conflicting_alias_groups_fail_before_mutation(self) -> None:
        font = _novel_test_font()
        original_bounds = glyph_path(font, "horizontal").bounds
        with self.assertRaisesRegex(ValueError, "conflicting novel hiragana groups"):
            apply_novel_hiragana(
                font,
                400,
                {"horizontal": "normal"},
                {"horizontal": "small"},
            )
        self.assertEqual(glyph_path(font, "horizontal").bounds, original_bounds)

    def test_counter_metric_uses_contour_direction(self) -> None:
        outline = pathops.Path()
        pen = outline.getPen()
        pen.moveTo((0, 0))
        pen.lineTo((100, 0))
        pen.lineTo((100, 100))
        pen.lineTo((0, 100))
        pen.closePath()
        pen.moveTo((25, 25))
        pen.lineTo((25, 75))
        pen.lineTo((75, 75))
        pen.lineTo((75, 25))
        pen.closePath()

        metrics = _glyph_metrics(outline, 100)
        self.assertEqual(metrics.signed_ink_area, 0.75)
        self.assertEqual(metrics.counter_area, 0.25)

    def test_cli_keeps_noto_default_and_requires_explicit_novel(self) -> None:
        self.assertEqual(parse_args([]).kana_style, "noto")
        self.assertEqual(parse_args(["--kana-style", "novel"]).kana_style, "novel")


if __name__ == "__main__":
    unittest.main()
