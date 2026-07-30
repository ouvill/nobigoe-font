from __future__ import annotations

import unittest

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

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
            {200: 16, 400: 18, 900: 22},
        )
        self.assertEqual(NOVEL_KA_CODEPOINT, ord("か"))
        expected = {
            200: 16,
            300: 17,
            400: 18,
            500: 18.8,
            600: 19.6,
            700: 20.4,
            900: 22,
        }
        for weight, amount in expected.items():
            self.assertAlmostEqual(novel_ka_terminal_raise(weight), amount)

    def test_ka_terminal_correction_is_smooth_and_local(self) -> None:
        outline = pathops.Path()
        pen = outline.getPen()
        pen.moveTo((140, 7))
        pen.lineTo((250, 120))
        pen.lineTo((350, 250))
        pen.lineTo((300, 450))
        pen.lineTo((390, 17))
        pen.closePath()

        shortened = shorten_novel_ka_terminal(outline, 18)
        before = list(outline.points)
        after = list(shortened.points)
        self.assertEqual([point[0] for point in after], [point[0] for point in before])
        self.assertEqual(after[0][1] - before[0][1], 18)
        self.assertEqual(after[1][1] - before[1][1], 18)
        self.assertGreater(after[2][1] - before[2][1], 0)
        self.assertLess(after[2][1] - before[2][1], 18)
        self.assertEqual(after[3], before[3])
        self.assertEqual(after[4], before[4])
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            shorten_novel_ka_terminal(outline, -1)

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

        self.assertEqual(lower_left(ka_path) - lower_left(reference_path), 18)

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
