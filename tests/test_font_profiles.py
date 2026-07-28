from __future__ import annotations

import unittest
from pathlib import Path

from font_profiles import (
    LIBERTINUS_ARCHIVE_SHA256,
    LIBERTINUS_STROKE_ADJUSTMENTS,
    KOBURI_ARCHIVE_SHA256,
    NOTO_WEIGHT_CLASSES,
    SHIPPORI_ARCHIVE_SHA256,
    default_output_path,
    VERSION_NUMBER,
    font_identity,
    libertinus_serif_source,
    noto_sans_source,
    noto_serif_source,
    shippori_source,
)


class FontProfileTests(unittest.TestCase):
    def test_noto_release_has_seven_ordered_weights(self) -> None:
        self.assertEqual(
            list(NOTO_WEIGHT_CLASSES.items()),
            [
                ("ExtraLight", 200),
                ("Light", 300),
                ("Regular", 400),
                ("Medium", 500),
                ("SemiBold", 600),
                ("Bold", 700),
                ("Black", 900),
            ],
        )

    def test_noto_identity_uses_typographic_family_for_all_weights(self) -> None:
        medium = font_identity("noto", "Medium")
        self.assertEqual(medium.family, "Nobigoe Mincho")
        self.assertEqual(medium.legacy_family, "Nobigoe Mincho Medium")
        self.assertEqual(medium.style, "Medium")
        self.assertEqual(medium.weight_class, 500)
        self.assertEqual(medium.postscript_name, "NobigoeMincho-Medium")
        self.assertEqual(
            default_output_path(medium, "noto"),
            Path("dist/NobigoeMincho-Medium.otf"),
        )

    def test_regular_and_bold_share_legacy_family(self) -> None:
        for weight in ("Regular", "Bold"):
            with self.subTest(weight=weight):
                identity = font_identity("noto", weight)
                self.assertEqual(identity.legacy_family, "Nobigoe Mincho")

    def test_koburi_is_a_distinct_true_type_family(self) -> None:
        identity = font_identity("koburi", "Regular")
        self.assertEqual(identity.family, "Nobigoe Koburi Mincho")
        self.assertEqual(identity.japanese_family, "のびごえこぶり明朝")
        self.assertEqual(identity.weight_class, 400)
        self.assertEqual(
            default_output_path(identity, "koburi"),
            Path("dist/NobigoeKoburiMincho-Regular.ttf"),
        )
        self.assertEqual(len(KOBURI_ARCHIVE_SHA256), 64)

    def test_source_profiles_are_pinned(self) -> None:
        for weight in NOTO_WEIGHT_CLASSES:
            with self.subTest(weight=weight):
                serif_name, serif_url, serif_hash = noto_serif_source(weight)
                self.assertIn(weight, serif_name)
                self.assertTrue(serif_url.endswith(serif_name))
                self.assertEqual(len(serif_hash), 64)

                sans_name, sans_url, sans_hash = noto_sans_source(weight)
                self.assertTrue(sans_url.endswith(sans_name))
                self.assertEqual(len(sans_hash), 64)

                shippori_name, shippori_hash = shippori_source(weight)
                self.assertTrue(shippori_name.startswith("ShipporiMincho-OTF-"))
                self.assertEqual(len(shippori_hash), 64)

        self.assertEqual(len(SHIPPORI_ARCHIVE_SHA256), 64)
        self.assertEqual(len(LIBERTINUS_ARCHIVE_SHA256), 64)

    def test_libertinus_latin_uses_nearest_available_serif_weights(self) -> None:
        self.assertEqual(
            {
                weight: libertinus_serif_source(weight)[0]
                for weight in NOTO_WEIGHT_CLASSES
            },
            {
                "ExtraLight": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Regular.otf"
                ),
                "Light": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Regular.otf"
                ),
                "Regular": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Regular.otf"
                ),
                "Medium": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Regular.otf"
                ),
                "SemiBold": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Semibold.otf"
                ),
                "Bold": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Bold.otf"
                ),
                "Black": (
                    "Libertinus-7.051/static/OTF/"
                    "LibertinusSerif-Bold.otf"
                ),
            },
        )
        for weight in NOTO_WEIGHT_CLASSES:
            self.assertEqual(len(libertinus_serif_source(weight)[1]), 64)
        self.assertEqual(
            LIBERTINUS_STROKE_ADJUSTMENTS,
            {
                "ExtraLight": -6,
                "Light": -3,
                "Regular": 0,
                "Medium": 4,
                "SemiBold": 0,
                "Bold": 0,
                "Black": 8,
            },
        )

    def test_release_version_tracks_latin_source_change(self) -> None:
        self.assertEqual(VERSION_NUMBER, "1.024")

    def test_missing_sans_weights_use_nearest_static_sources(self) -> None:
        self.assertEqual(noto_sans_source("ExtraLight")[0], "NotoSansJP-Thin.otf")
        self.assertEqual(noto_sans_source("SemiBold")[0], "NotoSansJP-Bold.otf")

    def test_shippori_ligatures_follow_available_weights(self) -> None:
        self.assertEqual(
            {weight: shippori_source(weight)[0] for weight in NOTO_WEIGHT_CLASSES},
            {
                "ExtraLight": "ShipporiMincho-OTF-Regular.otf",
                "Light": "ShipporiMincho-OTF-Regular.otf",
                "Regular": "ShipporiMincho-OTF-Regular.otf",
                "Medium": "ShipporiMincho-OTF-Medium.otf",
                "SemiBold": "ShipporiMincho-OTF-SemiBold.otf",
                "Bold": "ShipporiMincho-OTF-Bold.otf",
                "Black": "ShipporiMincho-OTF-ExtraBold.otf",
            },
        )


if __name__ == "__main__":
    unittest.main()
