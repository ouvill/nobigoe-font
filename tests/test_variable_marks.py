from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from nobigoe_font.profiles import noto_serif_variable_source
from nobigoe_font.variable_cli import DEFAULT_OUTPUT_PATH, main
from nobigoe_font.variable_marks import _DeltaModel, _scalar


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
