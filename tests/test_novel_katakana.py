from __future__ import annotations

import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from nobigoe_font.geometry import glyph_path
from nobigoe_font.novel_katakana import (
    CURVE_KATAKANA_CODEPOINTS,
    ITERATION_KATAKANA_CODEPOINTS,
    KATAKANA_CODEPOINTS,
    KATAKANA_HORIZONTAL_ANCHORS,
    KATAKANA_MASTER_PROFILES,
    KATAKANA_SOURCE_CODEPOINTS,
    KATAKANA_VERTICAL_ANCHORS,
    KATAKANA_VERTICAL_HEIGHT_CORRECTIONS,
    KATAKANA_VERTICAL_MASTER_PROFILES,
    NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
    SMALL_KATAKANA_CODEPOINTS,
    STRAIGHT_KATAKANA_CODEPOINTS,
    apply_novel_katakana,
    katakana_base_codepoint,
    katakana_transform,
    katakana_vertical_transform,
    novel_katakana_group_for_codepoint,
)


def _two_part_glyph() -> object:
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((700, 0))
    pen.lineTo((700, 600))
    pen.lineTo((100, 600))
    pen.closePath()
    pen.moveTo((750, 700))
    pen.lineTo((850, 700))
    pen.lineTo((850, 800))
    pen.lineTo((750, 800))
    pen.closePath()
    return pen.glyph()


def _katakana_test_font():
    builder = FontBuilder(1000, isTTF=True)
    glyph_order = [".notdef", "horizontal", "vertical"]
    builder.setupGlyphOrder(glyph_order)
    builder.setupGlyf({name: _two_part_glyph() for name in glyph_order})
    builder.setupHorizontalMetrics({name: (1000, 100) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupVerticalMetrics({name: (1000, 80) for name in glyph_order})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    builder.setupCharacterMap({0x30B7: "horizontal", 0x30B8: "vertical"})
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def _profile_tuple(profile: object) -> tuple[float, ...]:
    names = ("sx", "sy", "stem_adjustment", "dx", "dy")
    return tuple(getattr(profile, name) for name in names)


def _vertical_profile_tuple(profile: object) -> tuple[float, ...]:
    names = ("sx", "sy", "dx", "dy", "correction_strength")
    return tuple(getattr(profile, name) for name in names)


class NovelKatakanaContractTests(unittest.TestCase):
    def test_exact_source_and_delivered_sets_exclude_non_letters(self) -> None:
        expected_source = frozenset(
            (*range(0x30A1, 0x30FB), *range(0x30FD, 0x3100), *range(0x31F0, 0x3200))
        )
        self.assertEqual(KATAKANA_SOURCE_CODEPOINTS, expected_source)
        self.assertEqual(len(KATAKANA_SOURCE_CODEPOINTS), 109)
        self.assertEqual(
            KATAKANA_CODEPOINTS,
            expected_source | {NOVEL_SMALL_KATAKANA_KO_CODEPOINT},
        )
        self.assertEqual(len(KATAKANA_CODEPOINTS), 110)

        excluded = {
            0x3000,
            0x3001,
            0x3002,
            0x300C,
            0x300D,
            0x30FB,
            0x30FC,
            *range(0xFF65, 0xFFA0),
            0x1B000,
            *range(0x1AFF0, 0x1AFFF),
            *range(0x1B120, 0x1B123),
            *range(0x1B164, 0x1B168),
        }
        self.assertTrue(KATAKANA_CODEPOINTS.isdisjoint(excluded))

    def test_measured_groups_are_exact_disjoint_and_complete(self) -> None:
        expected_curve = frozenset(
            map(
                ord,
                "アウエオカガクグシジスズソゾツヅナヌネノフブプムメモラリルレロワヲンヴヷヺ",
            )
        )
        expected_straight = frozenset(
            map(
                ord,
                "イキギケゲコゴサザセゼタダチヂテデトドニハバパヒビピヘベペホボポマミヤユヨヰヱヸヹ",
            )
        )
        expected_small = frozenset(
            (
                *map(ord, "ァィゥェォッャュョヮヵヶㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ"),
                NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
            )
        )
        expected_iteration = frozenset(map(ord, "ヽヾヿ"))

        self.assertEqual(CURVE_KATAKANA_CODEPOINTS, expected_curve)
        self.assertEqual(STRAIGHT_KATAKANA_CODEPOINTS, expected_straight)
        self.assertEqual(SMALL_KATAKANA_CODEPOINTS, expected_small)
        self.assertEqual(ITERATION_KATAKANA_CODEPOINTS, expected_iteration)
        self.assertEqual(
            tuple(
                map(
                    len,
                    (
                        STRAIGHT_KATAKANA_CODEPOINTS,
                        CURVE_KATAKANA_CODEPOINTS,
                        SMALL_KATAKANA_CODEPOINTS,
                        ITERATION_KATAKANA_CODEPOINTS,
                    ),
                )
            ),
            (41, 37, 29, 3),
        )
        groups = (
            STRAIGHT_KATAKANA_CODEPOINTS,
            CURVE_KATAKANA_CODEPOINTS,
            SMALL_KATAKANA_CODEPOINTS,
            ITERATION_KATAKANA_CODEPOINTS,
        )
        for index, group in enumerate(groups):
            self.assertTrue(
                all(group.isdisjoint(other) for other in groups[index + 1 :])
            )
        self.assertEqual(frozenset().union(*groups), KATAKANA_CODEPOINTS)

    def test_precomposed_forms_inherit_their_decomposed_base_group(self) -> None:
        expected_bases = {
            "ガ": "カ",
            "ジ": "シ",
            "ヴ": "ウ",
            "ヷ": "ワ",
            "ヸ": "ヰ",
            "ヹ": "ヱ",
            "ヺ": "ヲ",
        }
        for composed, base in expected_bases.items():
            with self.subTest(composed=composed):
                self.assertEqual(katakana_base_codepoint(ord(composed)), ord(base))
                self.assertEqual(
                    novel_katakana_group_for_codepoint(ord(composed)),
                    novel_katakana_group_for_codepoint(ord(base)),
                )
        self.assertEqual(novel_katakana_group_for_codepoint(ord("ガ")), "curve")
        self.assertEqual(novel_katakana_group_for_codepoint(ord("ヸ")), "straight")
        self.assertEqual(novel_katakana_group_for_codepoint(ord("ァ")), "small")
        self.assertEqual(novel_katakana_group_for_codepoint(ord("ヾ")), "iteration")
        self.assertEqual(
            novel_katakana_group_for_codepoint(NOVEL_SMALL_KATAKANA_KO_CODEPOINT),
            "small",
        )

    def test_exact_three_horizontal_masters(self) -> None:
        expected = {
            200: {
                "straight": (0.95, 0.96, 1.5, 10, 8),
                "curve": (0.95, 0.96, 1, 10, 8),
                "small": (0.96, 0.97, 0.75, 3, -7),
                "iteration": (1.01, 0.97, 0.5, -18, 4),
            },
            400: {
                "straight": (0.94, 0.95, 0.5, 10, 7),
                "curve": (0.94, 0.95, 0, 10, 7),
                "small": (0.95, 0.96, 0.5, 3, -8),
                "iteration": (1, 0.96, 0, -18, 4),
            },
            900: {
                "straight": (0.935, 0.95, 0, 10, 5),
                "curve": (0.93, 0.95, 0, 10, 5),
                "small": (0.945, 0.955, 0, 3, -10),
                "iteration": (0.99, 0.96, 0, -18, 3),
            },
        }
        self.assertEqual(tuple(KATAKANA_MASTER_PROFILES), (200, 400, 900))
        for weight, groups in expected.items():
            for group, profile in groups.items():
                with self.subTest(weight=weight, group=group):
                    self.assertEqual(
                        _profile_tuple(KATAKANA_MASTER_PROFILES[weight][group]),
                        profile,
                    )

    def test_all_seven_weights_are_linear_master_interpolations(self) -> None:
        weights = (200, 300, 400, 500, 600, 700, 900)
        groups = ("straight", "curve", "small", "iteration")
        masters = tuple(KATAKANA_MASTER_PROFILES)
        for weight in weights:
            for group in groups:
                with self.subTest(weight=weight, group=group):
                    actual = _profile_tuple(katakana_transform(weight, group))
                    if weight in masters:
                        expected = _profile_tuple(
                            KATAKANA_MASTER_PROFILES[weight][group]
                        )
                    else:
                        lower = max(master for master in masters if master < weight)
                        upper = min(master for master in masters if master > weight)
                        position = (weight - lower) / (upper - lower)
                        expected = tuple(
                            low + position * (high - low)
                            for low, high in zip(
                                _profile_tuple(KATAKANA_MASTER_PROFILES[lower][group]),
                                _profile_tuple(KATAKANA_MASTER_PROFILES[upper][group]),
                            )
                        )
                    for actual_value, expected_value in zip(actual, expected):
                        self.assertAlmostEqual(actual_value, expected_value)
        self.assertAlmostEqual(
            katakana_transform(700, "straight").stem_adjustment,
            0.2,
        )

    def test_all_seven_vertical_profiles_interpolate_independently(self) -> None:
        weights = (200, 300, 400, 500, 600, 700, 900)
        groups = ("straight", "curve", "small", "iteration")
        masters = tuple(KATAKANA_VERTICAL_MASTER_PROFILES)
        for weight in weights:
            for group in groups:
                with self.subTest(weight=weight, group=group):
                    if weight in masters:
                        expected = _vertical_profile_tuple(
                            KATAKANA_VERTICAL_MASTER_PROFILES[weight][group]
                        )
                    else:
                        lower = max(master for master in masters if master < weight)
                        upper = min(master for master in masters if master > weight)
                        position = (weight - lower) / (upper - lower)
                        expected = tuple(
                            low + position * (high - low)
                            for low, high in zip(
                                _vertical_profile_tuple(
                                    KATAKANA_VERTICAL_MASTER_PROFILES[lower][group]
                                ),
                                _vertical_profile_tuple(
                                    KATAKANA_VERTICAL_MASTER_PROFILES[upper][group]
                                ),
                            )
                        )
                    actual = katakana_vertical_transform(weight, group, None)
                    self.assertAlmostEqual(actual.sx, expected[0])
                    self.assertAlmostEqual(actual.sy, expected[1])
                    self.assertEqual(actual.stem_adjustment, 0)
                    self.assertAlmostEqual(actual.dx, expected[2])
                    self.assertAlmostEqual(actual.dy, expected[3])

            curve_profile = (
                _vertical_profile_tuple(
                    KATAKANA_VERTICAL_MASTER_PROFILES[weight]["curve"]
                )
                if weight in masters
                else None
            )
            if curve_profile is None:
                lower = max(master for master in masters if master < weight)
                upper = min(master for master in masters if master > weight)
                position = (weight - lower) / (upper - lower)
                lower_profile = _vertical_profile_tuple(
                    KATAKANA_VERTICAL_MASTER_PROFILES[lower]["curve"]
                )
                upper_profile = _vertical_profile_tuple(
                    KATAKANA_VERTICAL_MASTER_PROFILES[upper]["curve"]
                )
                curve_profile = tuple(
                    low + position * (high - low)
                    for low, high in zip(lower_profile, upper_profile)
                )
            self.assertAlmostEqual(
                katakana_vertical_transform(weight, "curve", ord("シ")).sy,
                curve_profile[1] * (1 - 0.01 * curve_profile[4]),
            )

    def test_exact_vertical_masters_anchors_and_height_corrections(self) -> None:
        expected = {
            200: {
                "straight": (1.025, 1, 3, 0, 0.9),
                "curve": (1.025, 1, 3, 0, 0.9),
                "small": (0.965, 0.965, -25, -1, 0.9),
                "iteration": (1.015, 1, 7, 0, 0.9),
            },
            400: {
                "straight": (1.03, 1, 3, 0, 1),
                "curve": (1.03, 1, 3, 0, 1),
                "small": (0.96, 0.96, -25, -1, 1),
                "iteration": (1.02, 1, 7, 0, 1),
            },
            900: {
                "straight": (1.035, 1, 3, 0, 0.9),
                "curve": (1.035, 1, 3, 0, 0.9),
                "small": (0.955, 0.96, -25, -1, 0.9),
                "iteration": (1.02, 1, 7, 0, 0.9),
            },
        }
        self.assertEqual(tuple(KATAKANA_VERTICAL_MASTER_PROFILES), (200, 400, 900))
        for weight, groups in expected.items():
            for group, profile in groups.items():
                with self.subTest(weight=weight, group=group):
                    self.assertEqual(
                        _vertical_profile_tuple(
                            KATAKANA_VERTICAL_MASTER_PROFILES[weight][group]
                        ),
                        profile,
                    )

        self.assertEqual(
            KATAKANA_HORIZONTAL_ANCHORS,
            {
                "straight": (500, 370),
                "curve": (500, 370),
                "small": (500, 370),
                "iteration": (500, 370),
            },
        )
        self.assertEqual(KATAKANA_VERTICAL_ANCHORS["small"], (650, 395))
        self.assertEqual(KATAKANA_VERTICAL_ANCHORS["curve"], (500, 370))
        self.assertEqual(
            KATAKANA_VERTICAL_HEIGHT_CORRECTIONS,
            {codepoint: 0.99 for codepoint in map(ord, "ハシンチワネケ")},
        )
        self.assertEqual(
            _profile_tuple(katakana_vertical_transform(400, "small", ord("ァ"))),
            (0.96, 0.96, 0, -25, -1),
        )
        self.assertAlmostEqual(
            katakana_vertical_transform(400, "curve", ord("ジ")).sy,
            0.99,
        )
        self.assertAlmostEqual(
            katakana_vertical_transform(200, "curve", ord("ジ")).sy,
            0.991,
        )
        self.assertEqual(
            katakana_vertical_transform(400, "curve", ord("ス")).sy,
            1,
        )

    def test_full_marked_outline_and_metrics_are_transformed_once(self) -> None:
        font = _katakana_test_font()
        original_horizontal = glyph_path(font, "horizontal").bounds
        original_vertical = glyph_path(font, "vertical").bounds
        original_vertical_origin = (
            font["vmtx"].metrics["vertical"][1] + original_vertical[3]
        )

        result = apply_novel_katakana(
            font,
            400,
            {"horizontal": "curve"},
            {"vertical": "curve"},
            {"vertical": ord("ジ")},
            {"vertical"},
        )

        self.assertEqual(result.horizontal_glyphs, ("horizontal",))
        self.assertEqual(result.vertical_glyphs, ("vertical",))
        horizontal_bounds = glyph_path(font, "horizontal").bounds
        vertical_bounds = glyph_path(font, "vertical").bounds
        original_width = original_horizontal[2] - original_horizontal[0]
        original_height = original_horizontal[3] - original_horizontal[1]
        self.assertAlmostEqual(
            horizontal_bounds[2] - horizontal_bounds[0],
            original_width * 0.94,
            delta=2,
        )
        self.assertAlmostEqual(
            horizontal_bounds[3] - horizontal_bounds[1],
            original_height * 0.95,
            delta=2,
        )
        self.assertAlmostEqual(
            vertical_bounds[2] - vertical_bounds[0],
            original_width * 0.94 * 1.03,
            delta=2,
        )
        self.assertAlmostEqual(
            vertical_bounds[3] - vertical_bounds[1],
            original_height * 0.95 * 0.99,
            delta=2,
        )
        for name in ("horizontal", "vertical"):
            self.assertEqual(font["hmtx"].metrics[name][0], 1000)
            self.assertEqual(font["vmtx"].metrics[name][0], 1000)
        transformed_vertical_origin = (
            font["vmtx"].metrics["vertical"][1] + vertical_bounds[3]
        )
        self.assertLessEqual(
            abs(transformed_vertical_origin - original_vertical_origin),
            1,
        )

    def test_invalid_input_fails_before_any_outline_or_metric_mutation(self) -> None:
        font = _katakana_test_font()
        original_points = tuple(glyph_path(font, "horizontal").points)
        original_hmtx = dict(font["hmtx"].metrics)
        original_vmtx = dict(font["vmtx"].metrics)

        with self.assertRaisesRegex(ValueError, "conflicting novel katakana groups"):
            apply_novel_katakana(
                font,
                400,
                {"horizontal": "curve"},
                {"horizontal": "straight"},
            )

        self.assertEqual(tuple(glyph_path(font, "horizontal").points), original_points)
        self.assertEqual(font["hmtx"].metrics, original_hmtx)
        self.assertEqual(font["vmtx"].metrics, original_vmtx)


if __name__ == "__main__":
    unittest.main()
