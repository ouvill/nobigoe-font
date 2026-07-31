from __future__ import annotations

import math
import unittest
from typing import cast
from unittest.mock import Mock, patch

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from nobigoe_font.marks import (
    KOBURI_HEART_BASE_PUA,
    KOBURI_HEART_MARK_PAIRS,
    KOBURI_HEART_OUTPUT_PUA,
)
from nobigoe_font.operations import feature_ligatures
from nobigoe_font.variable_marks import (
    _WEIGHTS,
    _append_heart_mark_composites,
)


def _fixture_font() -> TTFont:
    glyph_order = [
        ".notdef",
        "heart.white",
        "heart.black",
        "dakuten.comb",
        "dakuten.space",
        "old.white",
        "old.black",
    ]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in glyph_order})
    builder.setupHorizontalMetrics({name: (1000, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(
        {
            0x2661: "heart.white",
            0x2665: "heart.black",
            0x3099: "dakuten.comb",
            0x309B: "dakuten.space",
        }
    )
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    addOpenTypeFeaturesFromString(
        builder.font,
        """
        feature ccmp {
            sub heart.white dakuten.comb by old.white;
            sub heart.black dakuten.comb by old.black;
        } ccmp;
        feature liga {
            sub heart.white dakuten.space by old.white;
            sub heart.black dakuten.space by old.black;
        } liga;
        """,
        tables={"GSUB"},
    )
    return cast(TTFont, builder.font)


def _polygon_master(segment_count: int, radius: float) -> pathops.Path:
    result = pathops.Path()
    pen = result.getPen()
    points = [
        (
            500 + radius * math.cos(2 * math.pi * index / segment_count),
            400 + radius * math.sin(2 * math.pi * index / segment_count),
        )
        for index in range(segment_count)
    ]
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    for x in (850, 920):
        pen.moveTo((x, 650))
        pen.lineTo((x + 20, 650))
        pen.lineTo((x + 20, 670))
        pen.lineTo((x, 670))
        pen.closePath()
    return result


def _operations(path: pathops.Path) -> tuple[str, ...]:
    recording = RecordingPen()
    path.draw(recording)
    return tuple(operation for operation, _ in recording.value)


class VariableHeartMarkTests(unittest.TestCase):
    def test_helper_normalizes_masters_and_installs_all_mappings(self) -> None:
        font = _fixture_font()
        cmap = cast(dict[int, str], font.getBestCmap())
        paths = {
            weight: {
                "heart.white": pathops.Path(),
                "heart.black": pathops.Path(),
                "dakuten.comb": pathops.Path(),
            }
            for weight in _WEIGHTS
        }
        segment_counts = (
            (8, 7, 7, 6, 6, 5, 4),
            (6, 6, 6, 6, 5, 5, 4),
        )
        raw = [
            _polygon_master(count, 240 + master_index)
            for pair_counts in segment_counts
            for master_index, count in enumerate(pair_counts)
        ]
        captured: list[tuple[str, list[pathops.Path]]] = []

        def append_glyphs(
            target: TTFont,
            _top,
            glyphs: list[tuple[str, list[pathops.Path]]],
            _model,
            _vsindex,
            _metric_source,
        ) -> None:
            captured.extend(glyphs)
            target.setGlyphOrder(
                [*target.getGlyphOrder(), *(name for name, _ in glyphs)]
            )

        with (
            patch(
                "nobigoe_font.variable_marks.geometry.compose_heart_dakuten_glyph",
                side_effect=raw,
            ),
            patch(
                "nobigoe_font.variable_marks._append_glyphs",
                side_effect=append_glyphs,
            ),
        ):
            _append_heart_mark_composites(
                font,
                Mock(),
                cmap,
                paths,
                Mock(),
                17,
            )

        self.assertEqual(len(captured), len(KOBURI_HEART_MARK_PAIRS))
        expected_body_segments = (8, 6)
        raw_index = 0
        for (_, masters), segment_count in zip(
            captured, expected_body_segments, strict=True
        ):
            self.assertEqual(len(masters), len(_WEIGHTS))
            signatures = [_operations(master) for master in masters]
            self.assertTrue(all(item == signatures[0] for item in signatures[1:]))
            self.assertEqual(
                _operations(next(iter(masters[0].contours))),
                ("moveTo", *("curveTo",) * segment_count, "closePath"),
            )
            for master in masters:
                difference = pathops.op(master, raw[raw_index], pathops.PathOp.XOR)
                self.assertAlmostEqual(
                    sum(abs(contour.area) for contour in difference.contours),
                    0,
                    places=6,
                )
                raw_index += 1

        built_cmap = cast(dict[int, str], font.getBestCmap())
        for codepoint, (base, _) in zip(
            KOBURI_HEART_BASE_PUA,
            KOBURI_HEART_MARK_PAIRS,
            strict=True,
        ):
            self.assertEqual(built_cmap[codepoint], built_cmap[base])
        for codepoint, (name, _) in zip(
            KOBURI_HEART_OUTPUT_PUA,
            captured,
            strict=True,
        ):
            self.assertEqual(built_cmap[codepoint], name)

        ccmp = feature_ligatures(font, "ccmp")
        liga = feature_ligatures(font, "liga")
        for pair, (name, _) in zip(KOBURI_HEART_MARK_PAIRS, captured, strict=True):
            base, mark = pair
            self.assertEqual(ccmp[(built_cmap[base], built_cmap[mark])], name)
            self.assertEqual(liga[(built_cmap[base], built_cmap[0x309B])], name)


if __name__ == "__main__":
    unittest.main()
