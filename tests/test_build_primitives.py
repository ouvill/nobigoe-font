from __future__ import annotations

import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from nobigoe_font.hinting import autohint_latin_glyphs
from nobigoe_font.features import (
    alternating_wave_rules,
    contextual_extension_rules,
    feature_source,
    merge_features,
)
from nobigoe_font.pipeline import (
    COMBINING_MARK_INPUTS,
    import_koburi_ruby,
    SPACING_MARK_INPUTS,
    mark_ligature_rules,
    make_manga_wave_parts,
    make_wave_parts,
)
from nobigoe_font.metadata import rename_font
from nobigoe_font.punctuation import (
    make_punctuation_ligature,
    shippori_upright_punctuation_paths,
)
from nobigoe_font.marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    KOBURI_PUA_MARK_PAIRS,
    KOBURI_PUA_START,
    MANGA_MISSING_SMALL_KANA,
    MarkPlacement,
)

from nobigoe_font.operations import (
    add_unicode_mapping_if_missing,
    append_ttf_glyphs,
    feature_ligatures,
    feature_single_substitutions,
    import_latin_font,
    remove_repeated_ligatures,
    tt_glyph,
)
from nobigoe_font.profiles import (
    LatinBuildProfile,
    VERSION_NUMBER,
    font_identity,
)
from nobigoe_font.geometry import (
    bounds,
    adjust_outline_weight,
    adjust_outline_horizontal_weight,
    centered_transform,
    mark_placement_transform,
    glyph_path,
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
            "languagesystem latn dflt;\n"
            f"feature liga {{ sub {cmap[0x66]} {cmap[0x69]} by {fi_ligature}; }} liga;\n"
            f"feature pnum {{ sub {cmap[0x30]} by {zero_alternate}; }} pnum;"
        )
    addOpenTypeFeaturesFromString(font, features, tables={"GSUB"})
    return font


class FontMetadataTests(unittest.TestCase):
    def test_rename_font_sets_open_type_revision(self) -> None:
        font = minimal_true_type_font()

        rename_font(
            font,
            "Copyright",
            "Notice",
            font_identity("noto", "Regular"),
        )

        self.assertAlmostEqual(
            font["head"].fontRevision,
            float(VERSION_NUMBER),
            places=4,
        )


class FontGeometryTests(unittest.TestCase):
    def test_glyph_path_decomposes_true_type_components(self) -> None:
        font = minimal_true_type_font()
        pen = TTGlyphPen(font.getGlyphSet())
        pen.addComponent("base", Transform(1, 0, 0, 1, 50, 75))
        font["glyf"].glyphs["composite"] = pen.glyph()
        font["hmtx"].metrics["composite"] = (1000, 150)
        font.setGlyphOrder([*font.getGlyphOrder(), "composite"])

        self.assertEqual(glyph_path(font, "composite").bounds, (150, 175, 950, 575))


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

    def test_horizontal_weight_adjustment_preserves_vertical_extent(self) -> None:
        adjusted = adjust_outline_horizontal_weight(rectangle_path(), 10)

        self.assertEqual((adjusted.bounds[0], adjusted.bounds[2]), (90.0, 910.0))
        self.assertAlmostEqual(adjusted.bounds[1], 99.375)
        self.assertAlmostEqual(adjusted.bounds[3], 500.625)

        thinned = adjust_outline_horizontal_weight(rectangle_path(), -10)
        self.assertEqual((thinned.bounds[0], thinned.bounds[2]), (110.0, 890.0))
        self.assertAlmostEqual(thinned.bounds[1], 100.625)
        self.assertAlmostEqual(thinned.bounds[3], 499.375)

    def test_horizontal_weight_adjustment_handles_round_isolated_contours(
        self,
    ) -> None:
        outline = pathops.Path()
        pen = outline.getPen()
        pen.moveTo((101, 754))
        pen.curveTo((85, 754), (72, 741), (72, 725))
        pen.curveTo((72, 709), (85, 696), (101, 696))
        pen.curveTo((117, 696), (130, 709), (130, 725))
        pen.curveTo((130, 741), (117, 754), (101, 754))
        pen.closePath()

        adjusted = adjust_outline_horizontal_weight(outline, 1)

        self.assertEqual(adjusted.bounds[0::2], (71.0, 131.0))

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
                "nobigoe_font.pipeline._font_operations.feature_single_substitutions",
                side_effect=feature_substitutions,
            ),
            patch(
                "nobigoe_font.pipeline._font_operations.find_vertical_glyph",
                side_effect=lambda _, target_name: target_vertical[target_name],
            ),
            patch(
                "nobigoe_font.pipeline._font_geometry.glyph_path",
                side_effect=lambda _, source_name: f"path:{source_name}",
            ),
            patch(
                "nobigoe_font.pipeline._font_geometry.adjust_outline_weight",
                side_effect=lambda outline, amount: f"{outline}@{amount}",
            ),
            patch("nobigoe_font.pipeline._font_operations.append_glyphs") as append,
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

    def test_zero_mark_rotation_matches_the_original_transform(self) -> None:
        transform = mark_placement_transform(
            rectangle_path(),
            MarkPlacement(0.8, 900, -50, 0),
        )

        self.assertEqual(transform, Transform(0.8, 0, 0, 0.8, 900, -50))

    def test_mark_rotation_preserves_center_and_uses_positive_ccw(self) -> None:
        mark = rectangle_path()
        transform = mark_placement_transform(
            mark,
            MarkPlacement(0.8, 900, -50, 90),
        )
        placed = transform_path(mark, transform)
        x_min, y_min, x_max, y_max = placed.bounds

        self.assertAlmostEqual((x_min + x_max) / 2, 1300)
        self.assertAlmostEqual((y_min + y_max) / 2, 190)
        self.assertAlmostEqual(x_max - x_min, 320)
        self.assertAlmostEqual(y_max - y_min, 640)
        right_edge_x, right_edge_y = transform.transformPoint((900, 300))
        self.assertAlmostEqual(right_edge_x, 1300)
        self.assertAlmostEqual(right_edge_y, 510)

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
        spacing_mark_codepoint = 0x309B
        spacing_mark = f"uni{spacing_mark_codepoint:04X}"
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
                    spacing_mark,
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
            {
                base_codepoint: base,
                mark_codepoint: mark,
                spacing_mark_codepoint: spacing_mark,
            },
        )
        source = feature_source(
            [],
            ("wave", "wave.base", "wave.vert", wave_names),
            ("manga-wave", "manga-wave.base", manga_wave_names),
            punctuation_variants,
            mark_ligature_rules(
                font.getBestCmap(),
                [CHOON_DAKUTEN_PAIR],
                {CHOON_DAKUTEN_PAIR: output},
                COMBINING_MARK_INPUTS,
            ),
            mark_ligature_rules(
                font.getBestCmap(),
                [CHOON_DAKUTEN_PAIR],
                {CHOON_DAKUTEN_PAIR: output},
                SPACING_MARK_INPUTS,
            ),
            [(output, vertical_output)],
            [],
        )

        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        ccmp = feature_ligatures(font, "ccmp")
        liga = feature_ligatures(font, "liga")
        self.assertEqual(ccmp[(base, mark)], output)
        self.assertNotIn((base, spacing_mark), ccmp)
        self.assertEqual(liga[(base, spacing_mark)], output)
        self.assertEqual(
            feature_single_substitutions(font, "vert")[output],
            vertical_output,
        )

    def test_mark_ligature_rules_alias_spacing_marks(self) -> None:
        pairs = ((0x3042, 0x3099), (0x304B, 0x309A))
        outputs = {
            pairs[0]: "hiragana-a.dakuten",
            pairs[1]: "hiragana-ka.handakuten",
        }
        cmap = {
            0x3042: "hiragana-a",
            0x304B: "hiragana-ka",
            0x3099: "dakuten",
            0x309A: "handakuten",
            0x309B: "spacing-dakuten",
            0x309C: "spacing-handakuten",
        }

        combining_rules = {
            (base, mark): output
            for base, mark, output in mark_ligature_rules(
                cmap, pairs, outputs, COMBINING_MARK_INPUTS
            )
        }
        spacing_rules = {
            (base, mark): output
            for base, mark, output in mark_ligature_rules(
                cmap, pairs, outputs, SPACING_MARK_INPUTS
            )
        }

        self.assertEqual(
            combining_rules,
            {
                ("hiragana-a", "dakuten"): "hiragana-a.dakuten",
                ("hiragana-ka", "handakuten"): "hiragana-ka.handakuten",
            },
        )
        self.assertEqual(
            spacing_rules,
            {
                ("hiragana-a", "spacing-dakuten"): "hiragana-a.dakuten",
                (
                    "hiragana-ka",
                    "spacing-handakuten",
                ): "hiragana-ka.handakuten",
            },
        )

    def test_feature_source_builds_punctuation_mark_substitutions(self) -> None:
        punctuation_variants = [
            ("!", ("exclamation", "exclamation.a1", "exclamation.a2", "exclamation.a3")),
            ("?", ("question", "question.a1", "question.a2", "question.a3")),
        ]
        marks = ("dakuten", "handakuten")
        outputs = [
            "exclamation.dakuten",
            "exclamation.handakuten",
            "question.dakuten",
            "question.handakuten",
        ]
        vertical_outputs = [f"{output}.vert" for output in outputs]
        punctuation_marks = [
            ("exclamation", "dakuten", outputs[0]),
            ("exclamation", "handakuten", outputs[1]),
            ("question", "dakuten", outputs[2]),
            ("question", "handakuten", outputs[3]),
        ]
        vertical_maps = list(zip(outputs, vertical_outputs, strict=True))
        wave_names = [f"wave.{index}" for index in range(10)]
        manga_wave_names = [f"manga-wave.{index}" for index in range(7)]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    *marks,
                    *outputs,
                    *vertical_outputs,
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
        font = named_true_type_font(glyph_order, {})
        source = feature_source(
            [],
            ("wave", "wave.base", "wave.vert", wave_names),
            ("manga-wave", "manga-wave.base", manga_wave_names),
            punctuation_variants,
            [],
            [],
            vertical_maps,
            [],
            punctuation_marks,
        )

        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        ccmp = feature_ligatures(font, "ccmp")
        self.assertEqual(
            {
                (base, mark): ccmp[(base, mark)]
                for base, mark, _ in punctuation_marks
            },
            {
                (base, mark): output
                for base, mark, output in punctuation_marks
            },
        )
        vert = feature_single_substitutions(font, "vert")
        self.assertEqual(
            {output: vert[output] for output in outputs},
            dict(vertical_maps),
        )


    def test_horizontal_choon_calt_is_added_to_kana_script(self) -> None:
        glyph_order = [
            ".notdef",
            "choon",
            "old.alt",
            "choon.start",
            "choon.middle",
            "choon.end",
            "choon.vert",
        ]
        font = named_true_type_font(glyph_order, {0x30FC: "choon"})
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem kana dflt;
            languagesystem latn dflt;
            feature calt {
              script latn;
              sub choon by old.alt;
            } calt;
            feature vert {
              script kana;
              sub choon by choon.vert;
            } vert;
            """,
            tables={"GSUB"},
        )

        merge_features(
            font,
            "languagesystem DFLT dflt;\n"
            "feature calt {\n"
            + contextual_extension_rules(
                "choon_h",
                "choon",
                "choon.start",
                "choon.middle",
                "choon.end",
            )
            + "} calt;\n",
        )

        gsub = font["GSUB"].table
        feature_records = gsub.FeatureList.FeatureRecord
        kana = next(
            record.Script
            for record in gsub.ScriptList.ScriptRecord
            if record.ScriptTag == "kana"
        )
        self.assertIsNotNone(kana.DefaultLangSys)
        self.assertIn(
            "calt",
            {
                feature_records[index].FeatureTag
                for index in kana.DefaultLangSys.FeatureIndex
            },
        )

    @unittest.skipUnless(shutil.which("hb-shape"), "hb-shape is not installed")
    def test_all_horizontal_extension_symbols_shape_to_calt_parts(self) -> None:
        cmap = {
            0x30FC: "choon",
            0x2015: "dash",
            0x301C: "wave",
            0xFF5E: "wave",
            0x3030: "manga-wave",
        }
        expected = {
            0x30FC: ["choon.start", "choon.middle", "choon.end"],
            0x2015: ["dash.start", "dash.middle", "dash.end"],
            0x301C: ["wave.start", "wave.middle-b", "wave.end-a"],
            0xFF5E: ["wave.start", "wave.middle-b", "wave.end-a"],
            0x3030: ["manga-wave.start", "manga-wave.middle", "manga-wave.end"],
        }
        generated_names = [
            *expected[0x30FC],
            *expected[0x2015],
            "wave.start",
            "wave.middle-a",
            "wave.middle-b",
            "wave.end-a",
            "wave.end-b",
            *expected[0x3030],
        ]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    *cmap.values(),
                    "old.alt",
                    "choon.vert",
                    "dash.two",
                    "dash.three",
                    *generated_names,
                ]
            )
        )
        font = named_true_type_font(glyph_order, cmap)
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem DFLT dflt;
            languagesystem kana dflt;
            languagesystem latn dflt;
            feature ccmp {
              script DFLT;
              sub dash dash dash by dash.three;
              sub dash dash by dash.two;
            } ccmp;
            feature calt {
              script latn;
              sub choon by old.alt;
            } calt;
            feature vert {
              script DFLT;
              sub choon by choon.vert;
              script kana;
              sub choon by choon.vert;
            } vert;
            """,
            tables={"GSUB"},
        )
        self.assertEqual(remove_repeated_ligatures(font, "ccmp", "dash"), 2)

        calt_source = (
            "languagesystem DFLT dflt;\n"
            "feature calt {\n"
            + contextual_extension_rules(
                "choon_h",
                "choon",
                "choon.start",
                "choon.middle",
                "choon.end",
            )
            + contextual_extension_rules(
                "dash_h",
                "dash",
                "dash.start",
                "dash.middle",
                "dash.end",
            )
            + alternating_wave_rules(
                "wave_h",
                "wave",
                [
                    "wave.start",
                    "wave.middle-a",
                    "wave.middle-b",
                    "wave.end-a",
                    "wave.end-b",
                ],
            )
            + contextual_extension_rules(
                "manga_wave_h",
                "manga-wave",
                "manga-wave.start",
                "manga-wave.middle",
                "manga-wave.end",
            )
            + "} calt;\n"
        )
        merge_features(font, calt_source)

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "extensions.ttf"
            font.save(path)
            for codepoint, enabled_glyphs in expected.items():
                text = chr(codepoint) * 3
                for calt, expected_glyphs in (
                    (0, [cmap[codepoint]] * 3),
                    (1, enabled_glyphs),
                ):
                    shaped = subprocess.run(
                        [
                            "hb-shape",
                            "--output-format=json",
                            f"--features=calt={calt}",
                            str(path),
                            text,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    actual_glyphs = [
                        record["g"] for record in json.loads(shaped.stdout)
                    ]
                    with self.subTest(codepoint=codepoint, calt=calt):
                        self.assertEqual(actual_glyphs, expected_glyphs)

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



    def test_latin_import_merges_source_layout_and_common_numeric_features(
        self,
    ) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")
        result = import_latin_font(
            target,
            source,
            LatinBuildProfile("libertinus", 1, 0),
        )

        target_cmap = target.getBestCmap()
        target_liga = feature_ligatures(target, "liga")
        target_pnum = feature_single_substitutions(target, "pnum")
        self.assertIn(
            (target_cmap[0x66], target_cmap[0x69]),
            target_liga,
        )
        self.assertIn(target_cmap[0x30], target_pnum)
        self.assertIn(target_pnum[target_cmap[0x30]], result.glyph_names)

    def test_autohint_limits_processing_to_imported_glyphs(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "font.otf"
            output_path.write_bytes(b"unhinted")

            def fake_run(command: list[str], check: bool) -> None:
                self.assertTrue(check)
                self.assertEqual(command[0], "/usr/bin/otfautohint")
                glyph_list_path = Path(command[command.index("--glyphs-file") + 1])
                self.assertEqual(
                    glyph_list_path.read_text(encoding="utf-8"),
                    "latin.A,latin.B",
                )
                hinted_path = Path(command[command.index("--output") + 1])
                hinted_path.write_bytes(b"hinted")

            with patch(
                "nobigoe_font.hinting.subprocess.run", side_effect=fake_run
            ):
                autohint_latin_glyphs(
                    output_path,
                    ("latin.A", "latin.B"),
                    executable="/usr/bin/otfautohint",
                )

            self.assertEqual(output_path.read_bytes(), b"hinted")

    def test_latin_replacement_scales_outlines_advances_and_gsub_outputs(
        self,
    ) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")

        import_latin_font(
            target,
            source,
            LatinBuildProfile("libertinus", 1.1, 0),
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
