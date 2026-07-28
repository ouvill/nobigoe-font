from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import Mock, patch

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from build_font import (
    feature_source,
    import_koburi_ruby,
    make_punctuation_ligature,
    make_manga_wave_parts,
    make_wave_parts,
    shippori_upright_punctuation_paths,
)
from mark_positioning import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    KOBURI_PUA_MARK_PAIRS,
    KOBURI_PUA_START,
    MANGA_MISSING_SMALL_KANA,
)

from font_operations import (
    add_unicode_mapping_if_missing,
    append_ttf_glyphs,
    feature_ligatures,
    feature_single_substitutions,
    replace_latin_glyphs,
    replace_latin_gsub_glyphs,
    tt_glyph,
)
from font_geometry import (
    bounds,
    adjust_outline_weight,
    centered_transform,
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


def named_true_type_font(
    glyph_order: list[str], cmap: dict[int, str]
) -> TTFont:
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    glyphs = {}
    metrics = {}
    for name in glyph_order:
        glyphs[name] = TTGlyphPen(None).glyph()
        metrics[name] = (1000, 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(cmap)
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

    def test_wave_terminals_reuse_source_glyph_margins(self) -> None:
        (
            horizontal_start,
            horizontal_middle,
            _,
            horizontal_end,
            _,
            vertical_start,
            vertical_middle,
            _,
            vertical_end,
            _,
        ) = make_wave_parts(rectangle_path(), 1000, 880)

        self.assertEqual(horizontal_start.bounds[0], 100)
        self.assertEqual(horizontal_end.bounds[2], 900)
        self.assertEqual(horizontal_middle.bounds[0::2], (0, 1000))
        self.assertEqual(vertical_start.bounds[3], 780)
        self.assertEqual(vertical_end.bounds[1], -20)
        self.assertEqual(vertical_middle.bounds[1::2], (-120, 880))

        manga_isolated, manga_parts = make_manga_wave_parts(
            rectangle_path(), 1000, 880
        )
        (
            manga_start,
            manga_middle,
            manga_end,
            manga_vertical_isolated,
            manga_vertical_start,
            manga_vertical_middle,
            manga_vertical_end,
        ) = manga_parts

        self.assertEqual(manga_isolated.bounds[0::2], (100, 900))
        self.assertEqual(manga_start.bounds[0], 100)
        self.assertEqual(manga_end.bounds[2], 900)
        self.assertEqual(manga_middle.bounds[0::2], (0, 1000))
        self.assertEqual(manga_vertical_isolated.bounds[1::2], (-20, 780))
        self.assertEqual(manga_vertical_start.bounds[3], 780)
        self.assertEqual(manga_vertical_end.bounds[1], -20)
        self.assertEqual(
            manga_vertical_middle.bounds[1::2], (-120, 880)
        )

    def test_exclamation_sequences_use_shippori_upright_pua_ligatures(
        self,
    ) -> None:
        source_ligature = pathops.Path()
        pen = source_ligature.getPen()
        for x_min, y_min, x_max, y_max in (
            (100, 200, 200, 800),
            (600, 200, 700, 800),
            (120, 0, 180, 100),
            (620, 0, 680, 100),
        ):
            pen.moveTo((x_min, y_min))
            pen.lineTo((x_max, y_min))
            pen.lineTo((x_max, y_max))
            pen.lineTo((x_min, y_max))
            pen.closePath()

        font = minimal_true_type_font()
        font["glyf"]["base"] = tt_glyph(source_ligature, 1000)
        for codepoint in (0xE002, 0xE007, 0xE0E3):
            add_unicode_mapping_if_missing(font, codepoint, "base")

        pair = make_punctuation_ligature(font, "!!")
        triple = make_punctuation_ligature(font, "!!!")
        quadruple = make_punctuation_ligature(font, "!!!!")
        five = make_punctuation_ligature(font, "!!!!!")

        self.assertEqual(pair.bounds, source_ligature.bounds)
        self.assertEqual(triple.bounds, source_ligature.bounds)
        self.assertEqual(quadruple.bounds, source_ligature.bounds)
        self.assertEqual(len(list(pair.contours)), 4)
        self.assertEqual(len(list(five.contours)), 10)

    def test_upright_question_uses_shippori_fullwidth_glyph(self) -> None:
        font = named_true_type_font(
            [".notdef", "exclamation", "question"],
            {0xE000: "exclamation", 0xFF1F: "question"},
        )
        exclamation = rectangle_path()
        question = transform_path(
            rectangle_path(), Transform(0.5, 0, 0, 1, 250, 0)
        )
        font["glyf"]["exclamation"] = tt_glyph(exclamation, 1000)
        font["glyf"]["question"] = tt_glyph(question, 1000)

        upright = shippori_upright_punctuation_paths(font)

        self.assertEqual(upright["!"].bounds, exclamation.bounds)
        self.assertEqual(upright["?"].bounds, question.bounds)

    def test_koburi_ruby_import_maps_every_source_input_class(self) -> None:
        direct_codepoints = [0x2022, 0x3042, *range(0x3400, 0x3400 + 226)]
        source_direct = {
            codepoint: f"source.direct.{index}"
            for index, codepoint in enumerate(direct_codepoints)
        }
        target_direct = {
            codepoint: f"target.direct.{index}"
            for index, codepoint in enumerate(direct_codepoints)
        }
        source_marks = {
            KOBURI_PUA_START + index: f"source.mark.{index}"
            for index in range(14)
        }
        source_small_ko = ["source.small.hira", "source.small.kata"]
        source_vertical = {
            **{
                source_direct[codepoint]: f"source.vertical.{index}"
                for index, codepoint in enumerate(direct_codepoints[:42])
            },
            source_small_ko[0]: "source.small.hira.vert",
            source_small_ko[1]: "source.small.kata.vert",
        }
        source_bullet = "source.bullet.fullwidth"
        source_inputs = [
            *source_direct.values(),
            *source_marks.values(),
            *source_small_ko,
            *source_vertical.values(),
            source_bullet,
        ]
        self.assertEqual(len(source_inputs), 289)
        source_substitutions = {
            source_name: f"source.ruby.{index}"
            for index, source_name in enumerate(source_inputs)
        }
        source_substitutions[source_bullet] = source_substitutions[
            source_direct[0x2022]
        ]
        source_outputs = list(dict.fromkeys(source_substitutions.values()))
        self.assertEqual(len(source_outputs), 288)

        source_cmap = source_direct | source_marks
        ruby_font = Mock()
        ruby_font.getBestCmap.return_value = source_cmap
        glyph_ids = {
            source_small_ko[0]: 100,
            source_small_ko[1]: 101,
        }
        ruby_font.getGlyphID.side_effect = glyph_ids.__getitem__
        target_font = Mock()
        target_cmap = target_direct
        target_vertical = {
            target_direct[codepoint]: f"target.vertical.{index}"
            for index, codepoint in enumerate(direct_codepoints[:42])
        }
        missing_small_glyphs = {
            codepoint: (f"target.small.{index}", f"target.small.{index}.vert")
            for index, codepoint in enumerate(MANGA_MISSING_SMALL_KANA)
        }
        mark_outputs = {
            pair: f"target.mark.{index}"
            for index, pair in enumerate(KOBURI_PUA_MARK_PAIRS)
        }
        allocated_names = [f"target.ruby.{index}" for index in range(288)]

        def feature_substitutions(font, feature_tag):
            if font is target_font:
                return {}
            return {
                "ruby": source_substitutions,
                "vert": source_vertical,
                "vrt2": {},
                "fwid": {source_direct[0x2022]: source_bullet},
            }[feature_tag]

        with (
            patch(
                "build_font._font_operations.feature_single_substitutions",
                side_effect=feature_substitutions,
            ),
            patch(
                "build_font._font_operations.find_vertical_glyph",
                side_effect=lambda _, target_name: target_vertical[target_name],
            ),
            patch(
                "build_font._font_geometry.glyph_path",
                side_effect=lambda _, source_name: f"path:{source_name}",
            ),
            patch(
                "build_font._font_geometry.adjust_outline_weight",
                side_effect=lambda outline, amount: f"{outline}@{amount}",
            ),
            patch("build_font._font_operations.append_glyphs") as append,
        ):
            substitutions, vertical_maps = import_koburi_ruby(
                target_font,
                ruby_font,
                target_cmap,
                mark_outputs,
                missing_small_glyphs,
                allocated_names,
                weight_adjustment=7,
            )

        imported = dict(substitutions)
        output_names = dict(zip(source_outputs, allocated_names, strict=True))
        self.assertEqual(len(imported), 288)
        self.assertEqual(
            imported[target_direct[0x3400]],
            output_names[source_substitutions[source_direct[0x3400]]],
        )
        self.assertEqual(
            imported[mark_outputs[KOBURI_PUA_MARK_PAIRS[0]]],
            output_names[source_substitutions[source_marks[KOBURI_PUA_START]]],
        )
        self.assertEqual(
            imported[missing_small_glyphs[MANGA_MISSING_SMALL_KANA[0]][0]],
            output_names[source_substitutions[source_small_ko[0]]],
        )
        self.assertEqual(
            imported[missing_small_glyphs[MANGA_MISSING_SMALL_KANA[0]][1]],
            output_names[
                source_substitutions[source_vertical[source_small_ko[0]]]
            ],
        )
        self.assertEqual(len(vertical_maps), 44)
        append.assert_called_once_with(
            target_font,
            [f"path:{source_name}@7" for source_name in source_outputs],
            allocated_names,
            target_direct[0x3042],
            880,
            add_stem_hints=False,
            advance_override=1000,
        )

    def test_choon_dakuten_uses_koburi_mark_centers(self) -> None:
        mark = transform_path(
            rectangle_path(), Transform(0.2, 0, 0, 0.2, -300, 500)
        )
        for orientation, (target_x, target_y) in (
            CHOON_DAKUTEN_MARK_CENTERS.items()
        ):
            placed = transform_path(
                mark,
                centered_transform(mark, 1, target_x, target_y),
            )
            x_min, y_min, x_max, y_max = placed.bounds
            with self.subTest(orientation=orientation):
                self.assertAlmostEqual(
                    (x_min + x_max) / 2, target_x, places=3
                )
                self.assertAlmostEqual(
                    (y_min + y_max) / 2, target_y, places=3
                )

    def test_feature_source_builds_choon_dakuten_substitutions(self) -> None:
        base_codepoint, mark_codepoint = CHOON_DAKUTEN_PAIR
        base = f"uni{base_codepoint:04X}"
        mark = f"uni{mark_codepoint:04X}"
        output = "choon.dakuten"
        vertical_output = f"{output}.vert"
        wave_names = [f"wave.{index}" for index in range(10)]
        manga_wave_names = [f"manga-wave.{index}" for index in range(7)]
        punctuation_variants = [
            ("!", ("exclamation", "exclamation.a1", "exclamation.a2", "exclamation.a3")),
            ("?", ("question", "question.a1", "question.a2", "question.a3")),
        ]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    base,
                    mark,
                    output,
                    vertical_output,
                    "wave.base",
                    "wave.vert",
                    *wave_names,
                    "manga-wave.base",
                    *manga_wave_names,
                    *(
                        name
                        for _, names in punctuation_variants
                        for name in names
                    ),
                ]
            )
        )
        font = named_true_type_font(
            glyph_order,
            {base_codepoint: base, mark_codepoint: mark},
        )
        source = feature_source(
            [],
            ("wave", "wave.base", "wave.vert", wave_names),
            ("manga-wave", "manga-wave.base", manga_wave_names),
            punctuation_variants,
            [(base, mark, output)],
            [(output, vertical_output)],
            [],
        )

        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        self.assertEqual(feature_ligatures(font, "ccmp")[(base, mark)], output)
        self.assertEqual(
            feature_single_substitutions(font, "vert")[output],
            vertical_output,
        )

    def test_fallback_unicode_mapping_preserves_a_native_pua_glyph(
        self,
    ) -> None:
        font = named_true_type_font(
            [".notdef", "unicode.heart", "pua.heart"],
            {0x2661: "unicode.heart", 0xE064: "pua.heart"},
        )

        existing = add_unicode_mapping_if_missing(
            font, 0xE064, "unicode.heart"
        )
        added = add_unicode_mapping_if_missing(
            font, 0xE065, "unicode.heart"
        )

        self.assertEqual(existing, "pua.heart")
        self.assertEqual(added, "unicode.heart")
        self.assertEqual(font.getBestCmap()[0xE064], "pua.heart")
        self.assertEqual(font.getBestCmap()[0xE065], "unicode.heart")



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

    def test_latin_replacement_scales_outlines_advances_and_gsub_outputs(
        self,
    ) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")

        replaced = replace_latin_glyphs(target, source, scale_factor=1.1)
        replace_latin_gsub_glyphs(
            target,
            source,
            replaced,
            scale_factor=1.1,
        )

        target_cmap = target.getBestCmap()
        target_a = target_cmap[0x41]
        self.assertEqual(target["hmtx"].metrics[target_a], (550, 44))
        self.assertEqual(bounds(target, target_a), (44, 88, 506, 660))
        target_fi = feature_ligatures(target, "liga")[
            (target_cmap[0x66], target_cmap[0x69])
        ]
        self.assertEqual(target["hmtx"].metrics[target_fi], (550, 44))
        self.assertEqual(bounds(target, target_fi), (44, 88, 506, 660))


if __name__ == "__main__":
    unittest.main()
