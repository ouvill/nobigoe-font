from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from nobigoe_font.essential import (
    ESSENTIAL_CODEPOINTS,
    ESSENTIAL_FAMILY,
    ESSENTIAL_JAPANESE_FAMILY,
    ESSENTIAL_LAYOUT_FEATURES,
    build_essential,
)
from nobigoe_font.essential_cli import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SOURCE_PATH,
    main,
    parse_args,
)


def _source_font(path: Path, omitted_codepoint: int | None = None) -> None:
    cmap = {
        0x2015: "bar",
        0x301C: "wave",
        0x3030: "manga",
        0x30FC: "choon",
        0xFF5E: "wave",
        0x3042: "noise",
    }
    if omitted_codepoint is not None:
        del cmap[omitted_codepoint]
    glyph_order = [
        ".notdef",
        "bar",
        "wave",
        "manga",
        "choon",
        "noise",
        "bar.end",
        "wave.end",
        "manga.end",
        "choon.end",
        "wave.relaxed",
        "wave.compact",
        "bar.vert",
        "wave.vert",
        "manga.vert",
        "choon.vert",
        "noise.alt",
    ]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in glyph_order})
    builder.setupHorizontalMetrics({name: (1000, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(cmap)
    builder.setupNameTable(
        {
            "familyName": "Nobigoe Variable Marks",
            "styleName": "Regular",
            "fullName": "Nobigoe Variable Marks Regular",
            "psName": "NobigoeVariableMarks-Regular",
        }
    )
    builder.setupOS2()
    builder.setupPost()
    font = builder.font
    addOpenTypeFeaturesFromString(
        font,
        """
        feature calt {
          sub bar bar' by bar.end;
          sub wave wave' by wave.end;
          sub manga manga' by manga.end;
          sub choon choon' by choon.end;
        } calt;
        feature ss04 { sub wave by wave.relaxed; } ss04;
        feature ss05 { sub wave by wave.compact; } ss05;
        feature vert {
          sub bar by bar.vert;
          sub wave by wave.vert;
          sub manga by manga.vert;
          sub choon by choon.vert;
        } vert;
        feature vrt2 {
          sub bar by bar.vert;
          sub wave by wave.vert;
          sub manga by manga.vert;
          sub choon by choon.vert;
        } vrt2;
        feature ccmp { sub noise by noise.alt; } ccmp;
        """,
    )
    font.save(path)


class EssentialBuildTests(unittest.TestCase):
    def test_build_keeps_only_five_codepoints_and_their_layout_closure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.ttf"
            output = root / "essential.ttf"
            _source_font(source)

            build_essential(source, output)

            font = TTFont(output)
            self.assertEqual(set(font.getBestCmap() or {}), ESSENTIAL_CODEPOINTS)
            self.assertTrue(
                {
                    "bar.end",
                    "wave.end",
                    "manga.end",
                    "choon.end",
                    "wave.relaxed",
                    "wave.compact",
                    "bar.vert",
                    "wave.vert",
                    "manga.vert",
                    "choon.vert",
                }.issubset(font.getGlyphOrder())
            )
            self.assertNotIn("noise", font.getGlyphOrder())
            feature_tags = {
                record.FeatureTag
                for record in font["GSUB"].table.FeatureList.FeatureRecord
            }
            self.assertEqual(feature_tags, set(ESSENTIAL_LAYOUT_FEATURES))
            self.assertEqual(font["name"].getDebugName(16), ESSENTIAL_FAMILY)
            japanese_family = font["name"].getName(16, 3, 1, 0x411)
            self.assertIsNotNone(japanese_family)
            assert japanese_family is not None
            self.assertEqual(japanese_family.toUnicode(), ESSENTIAL_JAPANESE_FAMILY)

    def test_missing_supported_codepoint_stops_the_build(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.ttf"
            _source_font(source, omitted_codepoint=0xFF5E)

            with self.assertRaisesRegex(ValueError, "U\\+FF5E"):
                build_essential(source, root / "essential.ttf")


class EssentialCliTests(unittest.TestCase):
    def test_defaults_use_the_customized_variable_source(self) -> None:
        args = parse_args([])

        self.assertEqual(args.source, DEFAULT_SOURCE_PATH)
        self.assertEqual(args.output, DEFAULT_OUTPUT_PATH)
        self.assertEqual(args.face, 0)

    def test_cli_forwards_explicit_paths_and_face(self) -> None:
        with patch("nobigoe_font.essential_cli.build_essential") as build:
            main(
                [
                    "--source",
                    "source.otf",
                    "--output",
                    "output.otf",
                    "--face",
                    "2",
                ]
            )

        build.assert_called_once_with(Path("source.otf"), Path("output.otf"), 2)


if __name__ == "__main__":
    unittest.main()
