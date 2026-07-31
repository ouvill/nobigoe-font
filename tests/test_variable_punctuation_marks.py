from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import Mock, call, patch

import pathops
from fontTools.cffLib import FDSelect
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

from nobigoe_font.marks import (
    PUNCTUATION_MARK_PAIRS,
    load_punctuation_mark_positions,
)
from nobigoe_font.operations import feature_ligatures, feature_single_substitutions
from nobigoe_font.profiles import NOTO_WEIGHT_CLASSES
from nobigoe_font.variable_marks import (
    _append_punctuation_mark_composites,
    _append_var_data,
)

_WEIGHTS = tuple(NOTO_WEIGHT_CLASSES.values())
_CMAP = {
    0xFF01: "cid00001",
    0xFF1F: "cid00002",
    0x3099: "cid00003",
    0x309A: "cid00004",
    0x309B: "cid00005",
    0x309C: "cid00006",
}
_VERTICAL = {
    "cid00001": "cid00007",
    "cid00002": "cid00008",
}


def _rectangle(left: float, bottom: float, right: float, top: float) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((left, bottom))
    pen.lineTo((right, bottom))
    pen.lineTo((right, top))
    pen.lineTo((left, top))
    pen.closePath()
    return outline


def _charstring(outline: pathops.Path):
    pen = T2CharStringPen(None, None)
    outline.draw(pen)
    return pen.getCharString()


def _source_paths(
    cmap: dict[int, str],
    vertical: dict[str, str],
) -> dict[int, dict[str, pathops.Path]]:
    paths = {}
    for weight in _WEIGHTS:
        growth = (weight - 200) / 14
        paths[weight] = {
            cmap[0xFF01]: _rectangle(450 - growth, 0, 550 + growth, 760),
            vertical[cmap[0xFF01]]: _rectangle(
                120, 450 - growth, 880, 550 + growth
            ),
            cmap[0xFF1F]: _rectangle(350 - growth, 0, 650 + growth, 760),
            vertical[cmap[0xFF1F]]: _rectangle(
                120, 350 - growth, 880, 650 + growth
            ),
            cmap[0x3099]: _rectangle(100, 100, 190 + growth, 190 + growth),
            cmap[0x309A]: _rectangle(100, 100, 210 + growth, 210 + growth),
        }
    return paths


def _variable_cff2_fixture() -> tuple[TTFont, dict[int, str], dict[str, str]]:
    glyph_order = [
        ".notdef",
        *_CMAP.values(),
        *_VERTICAL.values(),
        "cid00009",
        "cid00010",
    ]
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder(glyph_order)
    builder.setupHorizontalMetrics({name: (1000, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupVerticalMetrics({name: (1000, 0) for name in glyph_order})
    builder.setupVerticalHeader(ascent=500, descent=-500)
    builder.setupCharacterMap(_CMAP)
    builder.setupNameTable(
        {
            "familyName": "Variable Punctuation Fixture",
            "styleName": "Regular",
            "psName": "VariablePunctuationFixture-Regular",
        }
    )
    builder.setupOS2()
    builder.setupPost()
    builder.setupFvar([("wght", 200, 200, 900, "Weight")], [])
    static = _rectangle(100, 100, 200, 200)
    builder.setupCFF2(
        {name: _charstring(static) for name in glyph_order},
        regions=[{"wght": (0, 1, 1)}],
    )
    font = builder.font
    top = font["CFF2"].cff.topDictIndex[0]
    fd_select = FDSelect()
    fd_select.format = 3
    fd_select.gidArray = [0] * len(glyph_order)
    top.FDSelect = fd_select
    top.CharStrings.fdArray = top.FDArray
    top.CharStrings.fdSelect = fd_select
    for charstring in top.CharStrings.values():
        charstring.fdSelectIndex = 0
    addOpenTypeFeaturesFromString(
        font,
        """
        feature ccmp { sub cid00009 cid00009 by cid00010; } ccmp;
        feature liga { sub cid00009 cid00009 by cid00010; } liga;
        feature vert { sub cid00009 by cid00010; } vert;
        feature vrt2 { sub cid00009 by cid00010; } vrt2;
        """,
        tables={"GSUB"},
    )
    buffer = BytesIO()
    font.save(buffer)
    buffer.seek(0)
    loaded = TTFont(buffer)
    cmap = loaded.getBestCmap()
    loaded_order = loaded.getGlyphOrder()
    vertical = {
        cmap[0xFF01]: loaded_order[7],
        cmap[0xFF1F]: loaded_order[8],
    }
    return loaded, cmap, vertical


def _outline_signature(font: TTFont, name: str, weight: int) -> tuple[str, ...]:
    recording = RecordingPen()
    font.getGlyphSet(location={"wght": weight})[name].draw(recording)
    return tuple(operation for operation, _ in recording.value)


class VariablePunctuationMarkTests(unittest.TestCase):
    def test_focused_cff2_fixture_builds_outlines_and_feature_contracts(self) -> None:
        font, cmap, source_vertical = _variable_cff2_fixture()
        top = font["CFF2"].cff.topDictIndex[0]
        locations = [(weight - 200) / 700 for weight in _WEIGHTS]
        vsindex, model = _append_var_data(top, locations)
        original_order = list(font.getGlyphOrder())
        original_region_count = top.VarStore.otVarStore.VarRegionList.RegionCount
        original_data_count = top.VarStore.otVarStore.VarDataCount
        font["HVAR"] = Mock(table=Mock())
        font["VVAR"] = Mock(table=Mock())

        with (
            patch(
                "nobigoe_font.variable_marks._paths",
                return_value=_source_paths(cmap, source_vertical),
            ),
            patch(
                "nobigoe_font.variable_marks.load_punctuation_mark_positions",
                wraps=load_punctuation_mark_positions,
            ) as load_positions,
            patch(
                "nobigoe_font.variable_marks.vertical_glyph_or_self",
                side_effect=lambda _font, name: source_vertical.get(name, name),
            ),
        ):
            _append_punctuation_mark_composites(
                font,
                top,
                cmap,
                model,
                vsindex,
            )
        del font["HVAR"]
        del font["VVAR"]

        self.assertEqual(
            load_positions.call_args_list,
            [
                call(base="noto", weight=style)
                for style in NOTO_WEIGHT_CLASSES
            ],
        )
        self.assertEqual(font.getGlyphOrder()[: len(original_order)], original_order)
        self.assertEqual(
            top.VarStore.otVarStore.VarRegionList.RegionCount,
            original_region_count,
        )
        self.assertEqual(top.VarStore.otVarStore.VarDataCount, original_data_count)

        added = font.getGlyphOrder()[len(original_order) :]
        self.assertEqual(len(added), 2 * len(PUNCTUATION_MARK_PAIRS))
        horizontal = added[::2]
        vertical = added[1::2]
        expected_ccmp = {
            (cmap[base], cmap[mark]): output
            for (base, mark), output in zip(
                PUNCTUATION_MARK_PAIRS,
                horizontal,
                strict=True,
            )
        }
        expected_liga = {
            (cmap[base], cmap[0x309B if mark == 0x3099 else 0x309C]): output
            for (base, mark), output in zip(
                PUNCTUATION_MARK_PAIRS,
                horizontal,
                strict=True,
            )
        }
        ccmp = feature_ligatures(font, "ccmp")
        liga = feature_ligatures(font, "liga")
        self.assertEqual(
            {inputs: ccmp[inputs] for inputs in expected_ccmp},
            expected_ccmp,
        )
        self.assertEqual(
            {inputs: liga[inputs] for inputs in expected_liga},
            expected_liga,
        )
        expected_vertical = dict(zip(horizontal, vertical, strict=True))
        for tag in ("vert", "vrt2"):
            substitutions = feature_single_substitutions(font, tag)
            self.assertEqual(
                {name: substitutions[name] for name in horizontal},
                expected_vertical,
            )

        for name in added:
            signatures = {
                _outline_signature(font, name, weight) for weight in _WEIGHTS
            }
            self.assertEqual(len(signatures), 1)
            charstring = top.CharStrings[name]
            charstring.decompile()
            self.assertIn("blend", charstring.program)
            self.assertIn("vsindex", charstring.program)

        buffer = BytesIO()
        font.save(buffer)
        buffer.seek(0)
        rebuilt = TTFont(buffer)
        self.assertEqual(
            rebuilt.getGlyphOrder()[: len(original_order)],
            original_order,
        )
        rebuilt_added = rebuilt.getGlyphOrder()[len(original_order) :]
        self.assertEqual(len(rebuilt_added), len(added))
        for name in rebuilt_added:
            for weight in _WEIGHTS:
                self.assertTrue(_outline_signature(rebuilt, name, weight))


if __name__ == "__main__":
    unittest.main()
