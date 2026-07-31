from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    SourceDescriptor,
)
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib import build as varlib_build

from nobigoe_font.cli import parse_args
from nobigoe_font.profiles import NOTO_WEIGHT_CLASSES, NOTO_WEIGHT_DESIGN_LOCATIONS
from nobigoe_font.variable_stix import (
    STIX_LATIN_DESIGN_FAMILY,
    build_variable_stix_source,
    instantiate_stix_latin_font,
    is_variable_stix_design_font,
)


def _triangle(width: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width // 2, 700))
    pen.closePath()
    return pen.glyph()


def _master(weight: int, width: int) -> TTFont:
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "A", "f", "uni0192"])
    builder.setupCharacterMap({ord("A"): "A", ord("f"): "f", 0x0192: "uni0192"})
    weight_offset = 0 if weight == 400 else 100
    builder.setupGlyf(
        {
            ".notdef": _triangle(100),
            "A": _triangle(width),
            "f": _triangle(500 + weight_offset),
            "uni0192": _triangle(400 + weight_offset),
        }
    )
    builder.setupHorizontalMetrics(
        {
            ".notdef": (500, 0),
            "A": (700, 0),
            "f": (650, 0),
            "uni0192": (600, 0),
        }
    )
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(
        {
            "familyName": "Tiny STIX",
            "styleName": str(weight),
            "uniqueFontIdentifier": f"Tiny-STIX-{weight}",
            "fullName": f"Tiny STIX {weight}",
            "psName": f"TinySTIX-{weight}",
        }
    )
    builder.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        usWeightClass=weight,
    )
    builder.setupPost()
    builder.setupMaxp()
    return builder.font


def _raw_stix_source(path: Path) -> None:
    masters = ((400, _master(400, 400)), (700, _master(700, 500)))
    document = DesignSpaceDocument()
    axis = AxisDescriptor(
        tag="wght", name="Weight", minimum=400, default=400, maximum=700
    )
    document.addAxis(axis)
    for weight, font in masters:
        source = SourceDescriptor(
            name=str(weight),
            familyName="Tiny STIX",
            styleName=str(weight),
            designLocation={axis.name: weight},
            font=font,
        )
        if weight == 400:
            source.copyInfo = source.copyLib = source.copyFeatures = True
        document.addSource(source)
    variable, _, _ = varlib_build(document)
    variable.save(path)
    variable.close()
    for _, font in masters:
        font.close()


class VariableStixTests(unittest.TestCase):
    def test_cli_keeps_variable_stix_build_explicit(self) -> None:
        default = parse_args([])
        self.assertIsNone(default.build_variable_stix)

        selected = parse_args(
            [
                "--build-variable-stix",
                "design.ttf",
                "--latin-source",
                "raw.ttf",
            ]
        )
        self.assertEqual(selected.build_variable_stix, Path("design.ttf"))
        self.assertEqual(selected.latin_source, Path("raw.ttf"))

    def test_build_creates_seven_weight_noto_mapped_design_font(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "raw.ttf"
            output = root / "design.ttf"
            _raw_stix_source(source)

            result = build_variable_stix_source(source, output)
            variable = TTFont(output)
            self.addCleanup(variable.close)

            self.assertEqual(result.source, source)
            self.assertEqual(result.output, output)
            self.assertEqual(
                result.named_instance_weights, tuple(NOTO_WEIGHT_CLASSES.values())
            )
            self.assertEqual(result.tuned_glyph_count, 1)
            self.assertTrue(is_variable_stix_design_font(variable))
            self.assertEqual(
                variable["name"].getDebugName(16), STIX_LATIN_DESIGN_FAMILY
            )

            axis = variable["fvar"].axes[0]
            self.assertEqual(
                (axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue),
                ("wght", 200, 400, 900),
            )
            avar_points = sorted(variable["avar"].segments["wght"].items())
            expected_avar_points = (
                (-1.0, -1.0),
                (-0.5, (266.5 - 347) / (347 - 200)),
                (0.0, 0.0),
                (0.2, (452 - 347) / (900 - 347)),
                (0.4, (557 - 347) / (900 - 347)),
                (0.6, (711 - 347) / (900 - 347)),
                (1.0, 1.0),
            )
            self.assertEqual(len(avar_points), len(expected_avar_points))
            for actual, expected in zip(avar_points, expected_avar_points, strict=True):
                self.assertAlmostEqual(actual[0], expected[0], places=3)
                self.assertAlmostEqual(actual[1], expected[1], places=3)
            self.assertEqual(
                tuple(
                    round(instance.coordinates["wght"])
                    for instance in variable["fvar"].instances
                ),
                tuple(NOTO_WEIGHT_CLASSES.values()),
            )

            expected_x_max = {
                200: (340, 343),
                300: (356, 354),
                400: (362, 368),
                500: (388, 386),
                600: (412, 403),
                700: (450, 430),
                900: (492, 463),
            }
            for weight in NOTO_WEIGHT_DESIGN_LOCATIONS:
                with self.subTest(weight=weight):
                    instance = instantiate_stix_latin_font(variable, weight)
                    self.assertNotIn("fvar", instance)
                    self.assertEqual(
                        int(getattr(instance["OS/2"], "usWeightClass")), weight
                    )
                    cmap = instance.getBestCmap()
                    self.assertIsNotNone(cmap)
                    if cmap is not None:
                        self.assertEqual(cmap[ord("A")], "A")
                    normal_x_max, florin_x_max = expected_x_max[weight]
                    self.assertEqual(
                        (
                            int(getattr(instance["glyf"]["A"], "xMax")),
                            int(getattr(instance["glyf"]["f"], "xMax")),
                            int(getattr(instance["glyf"]["uni0192"], "xMax")),
                        ),
                        (normal_x_max, normal_x_max + 100, florin_x_max),
                    )
                    instance.close()

    def test_rejects_non_variable_source_and_unknown_weight(self) -> None:
        static = _master(400, 400)
        self.addCleanup(static.close)
        with self.assertRaisesRegex(ValueError, "variable TrueType glyf"):
            instantiate_stix_latin_font(static, 400)
        with self.assertRaisesRegex(ValueError, "Unsupported STIX Latin weight"):
            instantiate_stix_latin_font(static, 350)


if __name__ == "__main__":
    unittest.main()
