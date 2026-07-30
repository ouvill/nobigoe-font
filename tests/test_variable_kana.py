from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from nobigoe_font.cli import parse_args
from nobigoe_font.novel import HIRAGANA_CODEPOINTS
from nobigoe_font.novel_katakana import KATAKANA_SOURCE_CODEPOINTS
from nobigoe_font.kana_terminals import taper_glyf_terminals
from nobigoe_font.terminal_plans import terminal_depth_ratio
from nobigoe_font.variable_kana import (
    VARIABLE_KANA_DESIGN_FAMILY,
    _rename_design_font,
    is_variable_kana_design_source,
)


class VariableKanaContractTests(unittest.TestCase):
    def test_terminal_plans_cover_every_encoded_source_kana(self) -> None:
        targets = HIRAGANA_CODEPOINTS | KATAKANA_SOURCE_CODEPOINTS
        self.assertEqual(len(HIRAGANA_CODEPOINTS), 89)
        self.assertEqual(len(KATAKANA_SOURCE_CODEPOINTS), 109)
        self.assertEqual(len(targets), 198)

        ratios = set()
        for codepoint in targets:
            script = "hiragana" if codepoint in HIRAGANA_CODEPOINTS else "katakana"
            for weight in (200, 400, 900):
                for orientation in ("horizontal", "vertical"):
                    ratio = terminal_depth_ratio(script, codepoint, orientation, weight)
                    self.assertTrue(math.isfinite(ratio))
                    self.assertGreaterEqual(ratio, 0.18 * 0.70)
                    self.assertLessEqual(ratio, 0.18 * 1.35)
                    ratios.add(ratio)
        self.assertGreater(len(ratios), 10)

    def test_terminal_plan_rejects_wrong_semantic_owner(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an encoded hiragana"):
            terminal_depth_ratio("hiragana", ord("ア"), "horizontal", 400)
        with self.assertRaisesRegex(ValueError, "only masters 200, 400, and 900"):
            terminal_depth_ratio("katakana", ord("ア"), "horizontal", 500)

    def test_cli_keeps_variable_kana_explicit(self) -> None:
        default = parse_args([])
        self.assertFalse(default.variable_kana)
        self.assertIsNone(default.variable_kana_source)
        self.assertIsNone(default.build_variable_kana)

        selected = parse_args(
            [
                "--kana-style",
                "novel",
                "--variable-kana",
                "--variable-kana-source",
                "design.ttf",
                "--weight",
                "Black",
            ]
        )
        self.assertTrue(selected.variable_kana)
        self.assertEqual(selected.variable_kana_source, Path("design.ttf"))
        self.assertEqual(selected.weight, "Black")

        build_source = parse_args(["--build-variable-kana", "design.ttf"])
        self.assertEqual(build_source.build_variable_kana, Path("design.ttf"))

    def test_glyf_taper_preserves_interpolation_topology(self) -> None:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 100))
        pen.qCurveTo((150, 150), (240, 240), (300, 300))
        pen.lineTo((320, 280))
        pen.qCurveTo((260, 220), (120, 80))
        pen.qCurveTo((110, 85), (100, 100))
        pen.closePath()
        source = pen.glyph()
        source_coordinates = tuple(source.coordinates)
        source_flags = tuple(source.flags)
        source_end_points = tuple(source.endPtsOfContours)

        result = taper_glyf_terminals(source)

        self.assertEqual(result.adjusted_count, 1)
        self.assertEqual(result.unresolved_count, 0)
        self.assertEqual(tuple(source.coordinates), source_coordinates)
        self.assertEqual(tuple(result.glyph.flags), source_flags)
        self.assertEqual(tuple(result.glyph.endPtsOfContours), source_end_points)
        self.assertEqual(len(result.glyph.coordinates), len(source_coordinates))
        candidate = result.inventory.adjusted[0]
        first, second = candidate.point_indices
        self.assertEqual(
            result.glyph.coordinates[first],
            result.glyph.coordinates[second],
        )

    def test_design_source_has_an_explicit_reusable_identity(self) -> None:
        builder = FontBuilder(1000, isTTF=True)
        builder.setupGlyphOrder([".notdef"])
        pen = TTGlyphPen(None)
        builder.setupGlyf({".notdef": pen.glyph()})
        builder.setupHorizontalMetrics({".notdef": (1000, 0)})
        builder.setupHorizontalHeader(ascent=880, descent=-120)
        builder.setupCharacterMap({})
        builder.setupNameTable({"familyName": "Noto Serif JP", "styleName": "Regular"})
        builder.setupOS2()
        builder.setupPost()
        builder.setupFvar(
            [("wght", 200, 400, 900, "Weight")],
            [{"location": {"wght": 400}, "stylename": "Regular"}],
        )
        _rename_design_font(builder.font)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.ttf"
            builder.font.save(path)
            self.assertTrue(is_variable_kana_design_source(path))
        self.assertEqual(
            builder.font["name"].getDebugName(16), VARIABLE_KANA_DESIGN_FAMILY
        )


if __name__ == "__main__":
    unittest.main()
