from __future__ import annotations

import math
import unittest

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from nobigoe_font.kana_terminals import (
    compatible_path_terminal_ids,
    taper_variable_path_terminals,
)
from nobigoe_font.novel import HIRAGANA_CODEPOINTS, NOVEL_SMALL_KO_CODEPOINT
from nobigoe_font.novel_katakana import (
    KATAKANA_CODEPOINTS,
    KATAKANA_SOURCE_CODEPOINTS,
    NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
)
from nobigoe_font.profiles import NOTO_WEIGHT_DESIGN_LOCATIONS
from nobigoe_font.terminal_plans import terminal_depth_ratio
from nobigoe_font.variable_novel import _collect_owned_glyphs, _instance_outline


def _recording(outline: pathops.Path):
    pen = RecordingPen()
    outline.draw(pen)
    return tuple(pen.value)


def _command_signature(outline: pathops.Path) -> tuple[tuple[str, int], ...]:
    return tuple((operator, len(points)) for operator, points in _recording(outline))


def _cubic_terminal_outline(x_offset: float) -> pathops.Path:
    """Make one cubic stroke master with a short, topology-stable hard cap."""
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((100 + x_offset, 100))
    pen.curveTo(
        (150 + x_offset, 150),
        (240 + x_offset, 240),
        (300 + x_offset, 300),
    )
    pen.lineTo((320 + x_offset, 280))
    pen.curveTo(
        (260 + x_offset, 220),
        (180 + x_offset, 140),
        (120 + x_offset, 80),
    )
    pen.curveTo(
        (110 + x_offset, 85),
        (105 + x_offset, 95),
        (100 + x_offset, 100),
    )
    pen.closePath()
    return outline


def _semantic_kana_font() -> TTFont:
    glyph_order = (
        ".notdef",
        "ka",
        "ka.vert",
        "ga",
        "ga.vert",
        "small.hira",
        "small.hira.vert",
        "small.kata",
        "small.kata.vert",
        "dakuten",
    )
    font = TTFont()
    font.setGlyphOrder(glyph_order)

    cmap = newTable("cmap")
    cmap.tableVersion = 0
    subtable = CmapSubtable.newSubtable(12)
    subtable.platformID = 3
    subtable.platEncID = 10
    subtable.language = 0
    subtable.cmap = {
        ord("か"): "ka",
        ord("が"): "ga",
        NOVEL_SMALL_KO_CODEPOINT: "small.hira",
        NOVEL_SMALL_KATAKANA_KO_CODEPOINT: "small.kata",
        0x3099: "dakuten",
    }
    cmap.tables = [subtable]
    font["cmap"] = cmap

    addOpenTypeFeaturesFromString(
        font,
        """
        feature vert {
            sub ka by ka.vert;
            sub ga by ga.vert;
            sub small.hira by small.hira.vert;
            sub small.kata by small.kata.vert;
        } vert;
        feature ccmp {
            sub ka dakuten by ga;
            sub ka.vert dakuten by ga.vert;
        } ccmp;
        """,
        tables={"GSUB"},
    )
    return font


class VariableNovelContractTests(unittest.TestCase):
    def test_terminal_plans_cover_every_novel_kana_owner(self) -> None:
        hiragana = HIRAGANA_CODEPOINTS | {NOVEL_SMALL_KO_CODEPOINT}
        katakana = KATAKANA_CODEPOINTS
        targets = hiragana | katakana
        self.assertEqual(len(hiragana), 90)
        self.assertEqual(len(KATAKANA_SOURCE_CODEPOINTS), 109)
        self.assertEqual(len(katakana), 110)
        self.assertEqual(len(targets), 200)

        ratios = set()
        for codepoint in targets:
            script = "hiragana" if codepoint in hiragana else "katakana"
            for weight in (200, 300, 400, 500, 600, 700, 900):
                for orientation in ("horizontal", "vertical"):
                    ratio = terminal_depth_ratio(script, codepoint, orientation, weight)
                    self.assertTrue(math.isfinite(ratio))
                    self.assertGreaterEqual(ratio, 0.18 * 0.70)
                    self.assertLessEqual(ratio, 0.18 * 1.35)
                    ratios.add(ratio)
        self.assertGreater(len(ratios), 10)

    def test_added_small_ko_reuses_its_scale_invariant_source_plan(self) -> None:
        for weight in (200, 300, 400, 500, 600, 700, 900):
            for orientation in ("horizontal", "vertical"):
                self.assertEqual(
                    terminal_depth_ratio(
                        "hiragana",
                        NOVEL_SMALL_KO_CODEPOINT,
                        orientation,
                        weight,
                    ),
                    terminal_depth_ratio("hiragana", ord("こ"), orientation, weight),
                )
                self.assertEqual(
                    terminal_depth_ratio(
                        "katakana",
                        NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
                        orientation,
                        weight,
                    ),
                    terminal_depth_ratio("katakana", ord("コ"), orientation, weight),
                )

    def test_terminal_depth_keeps_masters_and_interpolates_static_weights(
        self,
    ) -> None:
        expected_scales = {
            200: 1.160,
            300: 1.110,
            400: 1.060,
            500: 1.016,
            600: 0.972,
            700: 0.928,
            900: 0.840,
        }

        for weight, scale in expected_scales.items():
            self.assertAlmostEqual(
                terminal_depth_ratio("hiragana", ord("か"), "horizontal", weight),
                0.18 * scale,
            )

    def test_intermediate_outlines_are_linear_at_normalized_design_positions(
        self,
    ) -> None:
        masters = {
            200: _cubic_terminal_outline(0),
            400: _cubic_terminal_outline(40),
            900: _cubic_terminal_outline(140),
        }
        offsets = {200: 0, 400: 40, 900: 140}

        for weight in (300, 500, 600, 700):
            lower, upper = (200, 400) if weight < 400 else (400, 900)
            fraction = (
                NOTO_WEIGHT_DESIGN_LOCATIONS[weight]
                - NOTO_WEIGHT_DESIGN_LOCATIONS[lower]
            ) / (
                NOTO_WEIGHT_DESIGN_LOCATIONS[upper]
                - NOTO_WEIGHT_DESIGN_LOCATIONS[lower]
            )
            expected_x = (
                100
                + offsets[lower]
                + (offsets[upper] - offsets[lower]) * fraction
            )
            move_x = _recording(_instance_outline(masters, weight))[0][1][0][0]
            self.assertAlmostEqual(move_x, expected_x, delta=2e-5)

    def test_terminal_plan_rejects_wrong_semantic_owner_and_weight(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an encoded hiragana"):
            terminal_depth_ratio("hiragana", ord("ア"), "horizontal", 400)
        with self.assertRaisesRegex(ValueError, "finite number in 200..900"):
            terminal_depth_ratio("katakana", ord("ア"), "horizontal", 901)

    def test_compatible_cubic_masters_replace_each_cap_with_two_curves(
        self,
    ) -> None:
        weights = (200, 400, 900)
        masters = tuple(
            _cubic_terminal_outline(offset) for offset in (-12.0, 0.0, 18.0)
        )
        source_recordings = tuple(_recording(outline) for outline in masters)

        selected = compatible_path_terminal_ids(masters)

        self.assertEqual(len(selected), 1)
        candidate_id = next(iter(selected))
        results = tuple(
            taper_variable_path_terminals(
                outline,
                selected,
                terminal_depth_ratio(
                    "katakana",
                    ord("ア"),
                    "horizontal",
                    weight,
                ),
            )
            for outline, weight in zip(masters, weights, strict=True)
        )
        self.assertEqual(
            {_command_signature(result.path) for result in results},
            {_command_signature(results[0].path)},
        )
        for source, before, result in zip(
            masters,
            source_recordings,
            results,
            strict=True,
        ):
            self.assertEqual(_recording(source), before)
            self.assertEqual(
                tuple(item.candidate_id for item in result.inventory.adjusted),
                (candidate_id,),
            )
            source_signature = _command_signature(source)
            result_signature = _command_signature(result.path)
            self.assertEqual(
                sum(operator == "curveTo" for operator, _ in result_signature),
                sum(operator == "curveTo" for operator, _ in source_signature) + 2,
            )
            self.assertEqual(
                sum(operator == "lineTo" for operator, _ in result_signature),
                sum(operator == "lineTo" for operator, _ in source_signature) - 1,
            )

    def test_semantic_collector_deduplicates_encoded_vertical_and_ccmp_owners(
        self,
    ) -> None:
        owned = _collect_owned_glyphs(_semantic_kana_font())
        by_name = {item.name: item for item in owned}

        self.assertEqual(
            set(by_name),
            {
                "ka",
                "ka.vert",
                "ga",
                "ga.vert",
                "small.hira",
                "small.hira.vert",
                "small.kata",
                "small.kata.vert",
            },
        )
        self.assertEqual(len(owned), len(by_name))
        self.assertEqual(
            {
                name: (item.codepoint, item.script, item.orientation)
                for name, item in by_name.items()
            },
            {
                "ka": (ord("か"), "hiragana", "horizontal"),
                "ka.vert": (ord("か"), "hiragana", "vertical"),
                "ga": (ord("が"), "hiragana", "horizontal"),
                "ga.vert": (ord("が"), "hiragana", "vertical"),
                "small.hira": (
                    NOVEL_SMALL_KO_CODEPOINT,
                    "hiragana",
                    "horizontal",
                ),
                "small.hira.vert": (
                    NOVEL_SMALL_KO_CODEPOINT,
                    "hiragana",
                    "vertical",
                ),
                "small.kata": (
                    NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
                    "katakana",
                    "horizontal",
                ),
                "small.kata.vert": (
                    NOVEL_SMALL_KATAKANA_KO_CODEPOINT,
                    "katakana",
                    "vertical",
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
