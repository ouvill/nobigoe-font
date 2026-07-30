from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from nobigoe_font import geometry
from nobigoe_font.features import symbol_feature_source
from nobigoe_font.operations import feature_ligatures, feature_single_substitutions
from nobigoe_font.profiles import noto_serif_variable_source
from nobigoe_font.variable_cli import DEFAULT_OUTPUT_PATH, main
from nobigoe_font.variable_marks import (
    _cap_cut_span,
    _DeltaModel,
    _normalize_vertical_parts,
    _scalar,
    _split_caps,
    _split_horizontal_parts,
    _split_vertical_parts,
)


class VariableMarkInterpolationTests(unittest.TestCase):
    def test_reviewed_values_round_trip_through_cff2_regions(self) -> None:
        locations = (0.0, 0.1, 0.25, 0.4, 0.6, 0.8, 1.0)
        supports = tuple(
            (locations[index - 1], locations[index], locations[index + 1])
            for index in range(1, 6)
        )
        values = (40.0, 52.0, 49.0, 68.0, 61.0, 89.0, 100.0)
        model = _DeltaModel(locations, supports)

        deltas = model.getDeltas(values, round=lambda value: value)

        for location, expected in zip(locations, values, strict=True):
            actual = deltas[0] + deltas[1] * location
            actual += sum(
                delta * _scalar(location, support)
                for delta, support in zip(deltas[2:], supports, strict=True)
            )
            self.assertAlmostEqual(actual, expected)


class VariableSymbolTests(unittest.TestCase):
    @staticmethod
    def _oval(y_min: float, y_max: float) -> pathops.Path:
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, (y_min + y_max) / 2))
        pen.curveTo((200, y_min), (800, y_min), (900, (y_min + y_max) / 2))
        pen.curveTo((800, y_max), (200, y_max), (100, (y_min + y_max) / 2))
        pen.closePath()
        return path

    @staticmethod
    def _vertical_oval(y_min: float, y_max: float) -> pathops.Path:
        center_y = (y_min + y_max) / 2
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, center_y))
        pen.curveTo((100, y_max), (300, y_max), (500, y_max))
        pen.curveTo((700, y_max), (900, y_max), (900, center_y))
        pen.curveTo((900, y_min), (700, y_min), (500, y_min))
        pen.curveTo((300, y_min), (100, y_min), (100, center_y))
        pen.closePath()
        return path

    def assertSameFill(self, actual: pathops.Path, expected: pathops.Path) -> None:
        difference = pathops.op(actual, expected, pathops.PathOp.XOR)
        self.assertEqual(sum(abs(contour.area) for contour in difference.contours), 0)

    def assertJoined(
        self,
        parts: tuple[pathops.Path, pathops.Path, pathops.Path],
        axis: str,
    ) -> None:
        start_contours = list(parts[0].contours)
        end_contours = list(parts[2].contours)
        pairs = (
            (start_contours[0], start_contours[1]),
            (end_contours[1], end_contours[0]),
        )
        for cap, bar in pairs:
            bar_span = (
                (bar.bounds[1], bar.bounds[3])
                if axis == "horizontal"
                else (bar.bounds[0], bar.bounds[2])
            )
            self.assertEqual(_cap_cut_span(cap, axis), bar_span)
        if axis == "horizontal":
            self.assertGreaterEqual(
                start_contours[0].bounds[2], start_contours[1].bounds[0]
            )
            self.assertLessEqual(end_contours[1].bounds[0], end_contours[0].bounds[2])
        else:
            self.assertLessEqual(
                start_contours[0].bounds[1], start_contours[1].bounds[3]
            )
            self.assertGreaterEqual(
                end_contours[1].bounds[3], end_contours[0].bounds[1]
            )

    def test_choon_terminals_split_source_curves_without_changing_fill(self) -> None:
        horizontal_sources = (self._oval(300, 500), self._oval(250, 550))
        vertical_sources = (
            self._vertical_oval(250, 650),
            self._vertical_oval(200, 700),
        )
        horizontal = [
            _split_horizontal_parts(source, 1000) for source in horizontal_sources
        ]
        vertical = _normalize_vertical_parts(
            [_split_vertical_parts(source, 1000, 880) for source in vertical_sources]
        )

        for source, parts in zip(horizontal_sources, horizontal, strict=True):
            low, high = _split_caps(source, "horizontal", 500)
            self.assertSameFill(
                low,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, -4096, 500, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertSameFill(
                high,
                pathops.op(
                    source,
                    geometry.rectangle(500, -4096, 4096, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertJoined(parts, "horizontal")
        for source, parts in zip(vertical_sources, vertical, strict=True):
            low, high = _split_caps(source, "vertical", 400)
            self.assertSameFill(
                low,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, -4096, 4096, 400),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertSameFill(
                high,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, 400, 4096, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertJoined(parts, "vertical")

        for parts_by_master in (horizontal, vertical):
            for index, contour_count in enumerate((2, 1, 2)):
                verbs = [tuple(parts[index].verbs) for parts in parts_by_master]
                self.assertEqual(verbs[0], verbs[1])
                self.assertTrue(
                    all(
                        sum(1 for _ in parts[index].contours) == contour_count
                        for parts in parts_by_master
                    )
                )

    def test_symbol_features_compile_to_expected_gsub_contracts(self) -> None:
        extensions = [
            ("choon", "choon", "choon.v", [f"choon{i}" for i in range(6)]),
            ("dash", "dash", "dash.v", [f"dash{i}" for i in range(6)]),
        ]
        wave = ("wave", "wave", "wave.v", [f"wave{i}" for i in range(10)])
        relaxed = (
            "relaxed",
            "wave",
            "wave.v",
            "selector",
            "seed",
            [f"relaxed{i}" for i in range(20)],
        )
        manga = ("manga", "manga", [f"manga{i}" for i in range(7)])
        glyph_order = [
            ".notdef",
            "choon",
            "choon.v",
            "dash",
            "dash.v",
            "wave",
            "wave.v",
            "selector",
            "seed",
            "manga",
            *(name for extension in extensions for name in extension[3]),
            *wave[3],
            *relaxed[5],
            *manga[2],
        ]
        font = TTFont()
        font.setGlyphOrder(glyph_order)

        addOpenTypeFeaturesFromString(
            font,
            symbol_feature_source(extensions, wave, relaxed, manga),
            tables={"GSUB"},
        )

        feature_tags = {
            record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord
        }
        self.assertEqual(feature_tags, {"ccmp", "ss04", "calt", "vert", "vrt2"})
        self.assertEqual(
            feature_ligatures(font, "ccmp"), {("selector", "wave"): "seed"}
        )
        expected_vertical = {
            "choon0": "choon3",
            "wave0": "wave5",
            "manga": "manga3",
            "manga0": "manga4",
        }
        for tag in ("vert", "vrt2"):
            substitutions = feature_single_substitutions(font, tag)
            self.assertEqual(
                {name: substitutions[name] for name in expected_vertical},
                expected_vertical,
            )


class VariableBuildCliTests(unittest.TestCase):
    def test_variable_source_is_pinned_to_the_noto_cff2_subset(self) -> None:
        source = noto_serif_variable_source()

        self.assertEqual(source.filename, "NotoSerifJP-VF.otf")
        self.assertTrue(
            source.url.endswith("/Serif/Variable/OTF/Subset/NotoSerifJP-VF.otf")
        )
        self.assertEqual(
            source.sha256,
            "39701fd096bc51204a8444c6c2659f007b29674a13eb62ddfa470638fe8179cd",
        )

    def test_local_source_bypasses_the_download_cache(self) -> None:
        with (
            patch("nobigoe_font.variable_cli.SourceCache.fetch") as fetch,
            patch(
                "nobigoe_font.variable_cli.variable_marks.build_variable_marks"
            ) as build,
        ):
            main(
                [
                    "--source",
                    "source.otf",
                    "--output",
                    "result.otf",
                    "--face",
                    "2",
                ]
            )

        fetch.assert_not_called()
        build.assert_called_once_with(Path("source.otf"), Path("result.otf"), 2)

    def test_default_build_fetches_the_pinned_source(self) -> None:
        cached = Path("cache/NotoSerifJP-VF.otf")
        with (
            patch(
                "nobigoe_font.variable_cli.SourceCache.fetch", return_value=cached
            ) as fetch,
            patch(
                "nobigoe_font.variable_cli.variable_marks.build_variable_marks"
            ) as build,
        ):
            main([])

        self.assertEqual(fetch.call_args.args[0], noto_serif_variable_source())
        build.assert_called_once_with(cached, DEFAULT_OUTPUT_PATH, 0)


if __name__ == "__main__":
    unittest.main()
