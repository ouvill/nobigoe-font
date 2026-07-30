from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.cffLib import FDArrayIndex, FDSelect, FontDict, SubrsIndex
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T2CharString
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

from nobigoe_font.geometry import glyph_path
from nobigoe_font.novel_metrics import _glyph_path as measurement_glyph_path
from nobigoe_font.novel_han import (
    HAN_CELL_CENTER,
    HAN_CODEPOINT_RANGES,
    HAN_SCALE,
    HAN_FD_FONT_MATRIX,
    HAN_FD_NAME_SUFFIX,
    HAN_TOP_FONT_MATRIX,
    HAN_UNICODE_VERSION,
    apply_novel_han,
    collect_novel_han_glyphs,
    han_transform,
    is_han_codepoint,
)


def _rectangle_charstring(
    x_min: int = 100,
    y_min: int = 100,
    x_max: int = 900,
    y_max: int = 800,
):
    pen = T2CharStringPen(1000, None)
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_min))
    pen.lineTo((x_max, y_max))
    pen.lineTo((x_min, y_max))
    pen.closePath()
    return pen.getCharString()


def _han_test_font(*, protected_alias: bool = False) -> TTFont:
    glyphs = {
        "han": "cid00001",
        "han.alt": "cid00002",
        "han.old": "cid00003",
        "han.vert": "cid00004",
        "kana": "cid00005",
    }
    names = [".notdef", *glyphs.values()]
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder(names)
    builder.setupHorizontalMetrics({name: (1000, 100) for name in names})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupVerticalMetrics({name: (1000, 80) for name in names})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    cmap = {
        0x2F00: glyphs["han"],
        0x4E00: glyphs["han"],
        0x3042: glyphs["han"] if protected_alias else glyphs["kana"],
    }
    builder.setupCharacterMap(cmap)
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
        {name: _rectangle_charstring() for name in names},
        {},
    )
    font = builder.font
    top = font["CFF "].cff.topDictIndex[0]
    private = top.Private
    private.Subrs = SubrsIndex()
    private.Subrs.append(
        T2CharString(
            program=["return"],
            private=private,
            globalSubrs=top.GlobalSubrs,
        )
    )
    fd_array = FDArrayIndex()
    fd_array.strings = None
    fd_array.GlobalSubrs = top.GlobalSubrs
    font_dict = FontDict()
    font_dict.setCFF2(False)
    font_dict.FontName = "Test-Regular-Ideographs"
    font_dict.Private = private
    fd_array.append(font_dict)
    fd_select = FDSelect()
    fd_select.format = 3
    fd_select.gidArray = [0] * len(names)
    top.FDArray = fd_array
    top.FDSelect = fd_select
    top.ROS = ("Adobe", "Identity", 0)
    top.CIDCount = len(names)
    del top.Private
    top.CharStrings.fdArray = fd_array
    top.CharStrings.fdSelect = fd_select
    for charstring in top.CharStrings.values():
        charstring.fdSelectIndex = 0
    addOpenTypeFeaturesFromString(
        font,
        f"""
        feature aalt {{ sub {glyphs["han"]} from [{glyphs["han.alt"]}]; }} aalt;
        feature jp78 {{ sub {glyphs["han"]} by {glyphs["han.old"]}; }} jp78;
        feature vert {{
            sub {glyphs["han.alt"]} by {glyphs["han.vert"]};
        }} vert;
        """,
    )
    return font


class NovelHanTests(unittest.TestCase):
    def test_static_unicode_15_1_ranges_include_only_contracted_han_blocks(
        self,
    ) -> None:
        self.assertEqual(HAN_UNICODE_VERSION, "15.1")
        self.assertEqual(HAN_CODEPOINT_RANGES[0], (0x3400, 0x4DBF))
        self.assertEqual(HAN_CODEPOINT_RANGES[-1], (0x31350, 0x323AF))
        for codepoint in (0x3400, 0x4E00, 0xFAFF, 0x20000, 0x2EBF0, 0x323AF):
            self.assertTrue(is_han_codepoint(codepoint))
        for codepoint in (0x3005, 0x3007, 0x303B, 0x303C, 0x30A2):
            self.assertFalse(is_han_codepoint(codepoint))

    def test_affine_transform_is_isotropic_around_fixed_cell_center(self) -> None:
        transform = han_transform()
        self.assertEqual(HAN_CELL_CENTER, (500.0, 500.0))
        self.assertEqual(HAN_SCALE, 0.9765625)
        self.assertEqual(transform.transformPoint((500, 500)), (500.0, 500.0))
        self.assertEqual(transform.transformPoint((0, 0)), (11.71875, 11.71875))
        self.assertEqual(transform.transformPoint((1000, 1000)), (988.28125, 988.28125))

    def test_gsub_graph_collects_only_outputs_reachable_from_han_seed(self) -> None:
        plan = collect_novel_han_glyphs(_han_test_font())
        self.assertEqual(plan.encoded_codepoints, (0x4E00,))
        self.assertEqual(plan.encoded_glyphs, ("cid00001",))
        self.assertEqual(set(plan.alternate_glyphs), {"cid00002", "cid00003"})
        self.assertEqual(plan.vertical_glyphs, ("cid00004",))
        self.assertEqual(len(plan.target_glyphs), len(set(plan.target_glyphs)))
        self.assertEqual(plan.non_han_aliases, ((0x2F00, "cid00001"),))
        feature_tags = {feature.tag for feature in plan.features}
        self.assertTrue({"aalt", "jp78", "vert"}.issubset(feature_tags))
        self.assertNotIn("cid00005", plan.target_glyphs)

    def test_fd_clone_preserves_programs_advances_origin_and_non_han(self) -> None:
        font = _han_test_font()
        cmap = font.getBestCmap()
        han = cmap[0x4E00]
        kana = cmap[0x3042]
        original_han = glyph_path(font, han).bounds
        original_kana_points = tuple(glyph_path(font, kana).points)
        original_origin = font["vmtx"].metrics[han][1] + original_han[3]
        source_private = font["CFF "].cff.topDictIndex[0].FDArray[0].Private

        plan = apply_novel_han(font)

        top = font["CFF "].cff.topDictIndex[0]
        self.assertEqual(len(top.FDArray), 2)
        self.assertEqual(
            top.FDArray[1].FontName,
            f"{top.FDArray[0].FontName}{HAN_FD_NAME_SUFFIX}",
        )
        self.assertEqual(tuple(top.FDArray[1].FontMatrix), HAN_FD_FONT_MATRIX)
        self.assertIsNot(top.FDArray[1].Private, source_private)
        self.assertIs(top.FDArray[1].Private.Subrs, source_private.Subrs)
        transformed_han = glyph_path(font, han).bounds
        self.assertAlmostEqual(
            transformed_han[2] - transformed_han[0],
            (original_han[2] - original_han[0]) * HAN_SCALE,
        )
        self.assertEqual(measurement_glyph_path(font, han).bounds, transformed_han)
        for name in plan.target_glyphs:
            self.assertEqual(top.FDSelect[font.getGlyphID(name)], 1)
            self.assertEqual(font["hmtx"].metrics[name][0], 1000)
            self.assertEqual(font["vmtx"].metrics[name][0], 1000)
            bounds = glyph_path(font, name).bounds
            origin = font["vmtx"].metrics[name][1] + bounds[3]
            self.assertLessEqual(abs(origin - original_origin), 1)
        self.assertEqual(top.FDSelect[font.getGlyphID(kana)], 0)
        self.assertEqual(tuple(glyph_path(font, kana).points), original_kana_points)

        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            control_path = directory / "control.otf"
            novel_path = directory / "novel.otf"
            resaved_path = directory / "novel-resaved.otf"
            _han_test_font().save(control_path)
            font.save(novel_path)
            control = TTFont(control_path)
            novel = TTFont(novel_path)
            novel.save(resaved_path)
            resaved = TTFont(resaved_path)

            control_charstrings = control["CFF "].cff.topDictIndex[0].CharStrings
            novel_top = novel["CFF "].cff.topDictIndex[0]
            resaved_top = resaved["CFF "].cff.topDictIndex[0]
            self.assertEqual(tuple(novel_top.FontMatrix), HAN_TOP_FONT_MATRIX)
            self.assertEqual(len(novel_top.FDArray[1].Private.Subrs), 1)
            self.assertEqual(len(resaved_top.FDArray[1].Private.Subrs), 1)
            for name in plan.target_glyphs:
                control_charstring = control_charstrings[name]
                novel_charstring = novel_top.CharStrings[name]
                control_charstring.decompile()
                novel_charstring.decompile()
                self.assertEqual(novel_charstring.program, control_charstring.program)
                glyph_id = novel.getGlyphID(name)
                self.assertEqual(novel_top.FDSelect[glyph_id], 1)
                self.assertEqual(resaved_top.FDSelect[glyph_id], 1)
            self.assertEqual(
                tuple(resaved_top.FDArray[1].FontMatrix),
                HAN_FD_FONT_MATRIX,
            )

    def test_protected_alias_fails_before_any_outline_mutation(self) -> None:
        font = _han_test_font(protected_alias=True)
        han = font.getBestCmap()[0x4E00]
        before = glyph_path(font, han).bounds
        with self.assertRaisesRegex(ValueError, "aliases protected"):
            apply_novel_han(font)
        self.assertEqual(glyph_path(font, han).bounds, before)


if __name__ == "__main__":
    unittest.main()
