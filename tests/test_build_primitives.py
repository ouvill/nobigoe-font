from __future__ import annotations

from io import BytesIO
import unittest

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from font_operations import (
    append_ttf_glyphs,
    feature_ligatures,
    feature_single_substitutions,
    replace_latin_glyphs,
    replace_latin_gsub_glyphs,
    tt_glyph,
)
from font_geometry import (
    adjust_outline_weight,
    mark_collision_free_transform,
    transform_path,
)


def rectangle_path() -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((100, 100))
    pen.lineTo((900, 100))
    pen.lineTo((900, 500))
    pen.lineTo((100, 500))
    pen.closePath()
    return path


def minimal_true_type_font() -> TTFont:
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "base"])
    glyphs = {}
    for name in (".notdef", "base"):
        pen = TTGlyphPen(None)
        if name == "base":
            rectangle_path().draw(pen)
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({".notdef": (1000, 0), "base": (1000, 100)})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap({0x25A1: "base"})
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def ascii_true_type_font(width: int, role: str) -> TTFont:
    cmap = {codepoint: f"{role}.{codepoint:04X}" for codepoint in range(0x20, 0x7F)}
    zero_alternate = f"{role}.zero.alt"
    fi_ligature = f"{role}.fi"
    glyph_order = [".notdef", *cmap.values(), zero_alternate, fi_ligature]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    glyphs = {}
    metrics = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        if name not in {".notdef", cmap[0x20]}:
            pen.moveTo((40, 80))
            pen.lineTo((width - 40, 80))
            pen.lineTo((width - 40, 600))
            pen.lineTo((40, 600))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (width, 40 if name not in {".notdef", cmap[0x20]} else 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(cmap)
    builder.setupNameTable({"familyName": role, "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    font = builder.font
    if role == "target":
        features = (
            f"feature locl {{ sub {cmap[0x30]} by {zero_alternate}; }} locl;\n"
            f"feature liga {{ sub {cmap[0x66]} {cmap[0x69]} by {fi_ligature}; }} liga;"
        )
    else:
        features = (
            f"feature liga {{ sub {cmap[0x66]} {cmap[0x69]} by {fi_ligature}; }} liga;"
        )
    addOpenTypeFeaturesFromString(font, features, tables={"GSUB"})
    return font


class TrueTypeBuildTests(unittest.TestCase):
    def test_cubic_outline_is_converted_to_quadratic_glyf(self) -> None:
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, 100))
        pen.curveTo((100, 500), (900, 500), (900, 100))
        pen.closePath()

        glyph = tt_glyph(path, 1000)

        self.assertEqual(glyph.numberOfContours, 1)
        self.assertTrue(glyph.coordinates)
        self.assertFalse(any(flag & 0x80 for flag in glyph.flags))

    def test_weight_adjustment_expands_and_thins_outline_edges(self) -> None:
        outline = rectangle_path()

        self.assertEqual(
            adjust_outline_weight(outline, 10).bounds,
            (90.0, 90.0, 910.0, 510.0),
        )
        self.assertEqual(
            adjust_outline_weight(outline, -10).bounds,
            (110.0, 110.0, 890.0, 490.0),
        )

    def test_mark_collision_transform_preserves_clear_placement(self) -> None:
        base = rectangle_path()
        mark = transform_path(
            rectangle_path(), Transform(0.2, 0, 0, 0.2, 680, 430)
        )

        adjusted = mark_collision_free_transform(
            base, mark, Transform(), 1000
        )
        intersection = pathops.op(
            base,
            transform_path(mark, adjusted),
            pathops.PathOp.INTERSECTION,
        )
        clear_transform = Transform(1, 0, 0, 1, 0, 100)

        self.assertGreater(adjusted.dy, 0)
        self.assertLessEqual(
            transform_path(mark, adjusted).bounds[3], 1000
        )
        self.assertFalse(intersection.verbs)
        self.assertEqual(
            mark_collision_free_transform(
                base, mark, clear_transform, 1000
            ),
            clear_transform,
        )

    def test_mark_collision_transform_uses_shorter_horizontal_escape(
        self,
    ) -> None:
        base = rectangle_path()
        mark = transform_path(
            rectangle_path(), Transform(0.2, 0, 0, 0.2, 830, 200)
        )

        adjusted = mark_collision_free_transform(
            base, mark, Transform(), 1000
        )
        intersection = pathops.op(
            base,
            transform_path(mark, adjusted),
            pathops.PathOp.INTERSECTION,
        )

        self.assertGreater(adjusted.dx, 0)
        self.assertEqual(adjusted.dy, 0)
        self.assertFalse(intersection.verbs)

    def test_mark_collision_transform_rejects_metric_overflow(self) -> None:
        base = rectangle_path()
        mark = transform_path(
            rectangle_path(), Transform(0.2, 0, 0, 0.2, 680, 430)
        )

        with self.assertRaisesRegex(ValueError, "vertical metrics"):
            mark_collision_free_transform(base, mark, Transform(), 500)


    def test_appended_glyph_has_unique_order_and_survives_round_trip(self) -> None:
        font = minimal_true_type_font()
        append_ttf_glyphs(
            font,
            [rectangle_path()],
            ["extension.middle"],
            "base",
            880,
        )

        self.assertEqual(font.getGlyphOrder(), [".notdef", "base", "extension.middle"])
        self.assertEqual(len(font["glyf"].glyphs), 3)
        self.assertEqual(font["hmtx"].metrics["extension.middle"], (1000, 100))

        data = BytesIO()
        font.save(data)
        data.seek(0)
        rebuilt = TTFont(data)
        self.assertEqual(rebuilt.getGlyphOrder(), font.getGlyphOrder())
        self.assertEqual(rebuilt["maxp"].numGlyphs, 3)


    def test_latin_replacement_covers_default_and_gsub_outputs(self) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")

        replaced = replace_latin_glyphs(target, source)
        outputs = replace_latin_gsub_glyphs(target, source, replaced)

        target_cmap = target.getBestCmap()
        source_cmap = source.getBestCmap()
        self.assertEqual(
            target["hmtx"].metrics[target_cmap[0x41]],
            source["hmtx"].metrics[source_cmap[0x41]],
        )
        target_locl = feature_single_substitutions(target, "locl")
        self.assertIn(target_cmap[0x30], target_locl)
        self.assertEqual(
            target["hmtx"].metrics[target_locl[target_cmap[0x30]]],
            source["hmtx"].metrics[source_cmap[0x30]],
        )
        target_liga = feature_ligatures(target, "liga")
        source_liga = feature_ligatures(source, "liga")
        target_fi = target_liga[(target_cmap[0x66], target_cmap[0x69])]
        source_fi = source_liga[(source_cmap[0x66], source_cmap[0x69])]
        self.assertIn(target_fi, outputs)
        self.assertEqual(
            target["hmtx"].metrics[target_fi],
            source["hmtx"].metrics[source_fi],
        )

if __name__ == "__main__":
    unittest.main()
