from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from nobigoe_font.novel_metrics import (
    DELIVERED_NOVEL_KATAKANA,
    FontInput,
    HIRAGANA_CODEPOINTS,
    KATAKANA_CODEPOINTS,
    REPRESENTATIVE_KANJI,
    SCHEMA_VERSION,
    _set_schema,
    _strict_failures,
    measure,
    write_text,
)


def _rectangle_glyph(x_min: int, y_min: int, x_max: int, y_max: int) -> object:
    pen = TTGlyphPen(None)
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_min))
    pen.lineTo((x_max, y_max))
    pen.lineTo((x_min, y_max))
    pen.closePath()
    return pen.glyph()


def _metrics_test_font(path: Path, *, include_generated_ko: bool) -> None:
    builder = FontBuilder(1000, isTTF=True)
    glyph_order = [".notdef", "horizontal", "vertical"]
    builder.setupGlyphOrder(glyph_order)
    builder.setupGlyf(
        {
            ".notdef": _rectangle_glyph(0, 0, 500, 500),
            "horizontal": _rectangle_glyph(100, 0, 900, 800),
            "vertical": _rectangle_glyph(200, 100, 800, 800),
        }
    )
    builder.setupHorizontalMetrics({name: (1000, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(
        {
            codepoint: "horizontal"
            for codepoint in (
                set(HIRAGANA_CODEPOINTS)
                | set(REPRESENTATIVE_KANJI)
                | set(
                    DELIVERED_NOVEL_KATAKANA
                    if include_generated_ko
                    else KATAKANA_CODEPOINTS
                )
            )
        }
    )
    builder.setupNameTable({"familyName": "Metrics Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    builder.save(path)


class NovelMetricsKatakanaTests(unittest.TestCase):
    def test_schema_records_contracted_katakana_sets(self) -> None:
        sets = _set_schema()
        self.assertEqual(SCHEMA_VERSION, 3)
        self.assertEqual(len(sets["katakana_109"]), 109)
        self.assertEqual(len(sets["standard_katakana_78"]), 78)
        self.assertEqual(len(sets["small_katakana_28"]), 28)
        self.assertEqual(len(sets["iteration_katakana_3"]), 3)
        self.assertEqual(len(sets["novel_katakana_110"]), 110)
        self.assertEqual(
            set(DELIVERED_NOVEL_KATAKANA) - set(KATAKANA_CODEPOINTS),
            {0x1B155},
        )

    def test_reports_like_for_like_metrics_and_generated_ko_coverage(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            source_path = Path(directory, "source.ttf")
            novel_path = Path(directory, "novel.ttf")
            _metrics_test_font(source_path, include_generated_ko=False)
            _metrics_test_font(novel_path, include_generated_ko=True)
            inputs = (
                FontInput("source", source_path),
                FontInput("novel", novel_path),
            )
            horizontal = measure(inputs)
            with patch(
                "nobigoe_font.novel_metrics.vertical_glyph_or_self",
                return_value="vertical",
            ):
                vertical = measure(inputs, vertical=True)

        self.assertEqual(horizontal["orientation"], "horizontal")
        self.assertEqual(vertical["orientation"], "vertical")
        for report in (horizontal, vertical):
            coverage = report["fonts"][0]["coverage"]
            self.assertEqual(coverage["katakana_109"]["measured"], 109)
            self.assertEqual(coverage["novel_katakana_110"]["expected"], 110)
            self.assertEqual(coverage["novel_katakana_110"]["measured"], 109)
            self.assertEqual(
                coverage["novel_katakana_110"]["missing_codepoints"],
                ["U+1B155"],
            )
            novel_coverage = report["fonts"][1]["coverage"]["novel_katakana_110"]
            self.assertEqual(novel_coverage["measured"], 110)
            self.assertEqual(novel_coverage["missing_codepoints"], [])
            self.assertEqual(report["fonts"][0]["novel_katakana_110"]["count"], 109)
            self.assertEqual(report["fonts"][1]["novel_katakana_110"]["count"], 110)
            self.assertEqual(_strict_failures(report), [])
            json.dumps(report, allow_nan=False)

        horizontal_mean = horizontal["fonts"][0]["katakana_109"]["mean"]
        self.assertEqual(horizontal_mean["bbox_width"], 0.8)
        self.assertEqual(horizontal_mean["bbox_height"], 0.8)
        self.assertEqual(horizontal_mean["bbox_center_x"], 0.4)
        self.assertEqual(horizontal_mean["bbox_center_y"], 0.4)
        self.assertEqual(horizontal_mean["signed_ink_area"], 0.64)

        vertical_mean = vertical["fonts"][0]["katakana_109"]["mean"]
        self.assertEqual(vertical_mean["bbox_width"], 0.6)
        self.assertEqual(vertical_mean["bbox_height"], 0.7)
        self.assertEqual(vertical_mean["bbox_center_x"], 0.3)
        self.assertEqual(vertical_mean["bbox_center_y"], 0.45)
        self.assertEqual(vertical_mean["signed_ink_area"], 0.42)

        comparison = horizontal["comparisons"][0]
        self.assertEqual(
            set(comparison),
            {
                "numerator",
                "denominator",
                "hiragana_89",
                "basic_hiragana_46",
                "representative_kanji_9",
                "katakana_109",
                "standard_katakana_78",
                "small_katakana_28",
                "iteration_katakana_3",
            },
        )
        self.assertNotIn("novel_katakana_110", comparison)
        self.assertEqual(
            comparison["standard_katakana_78"]["mean"]["bbox_width_ratio"],
            1.0,
        )

        output = StringIO()
        write_text(horizontal, output)
        rendered = output.getvalue()
        for name in (
            "katakana_109",
            "standard_katakana_78",
            "small_katakana_28",
            "iteration_katakana_3",
            "novel_katakana_110",
        ):
            self.assertIn(f"set {name}:", rendered)
            self.assertIn(f"  {name}: count=", rendered)


if __name__ == "__main__":
    unittest.main()
