from __future__ import annotations

import unittest
from pathlib import Path

from nobigoe_font.profiles import (
    DirectSource,
    KOBURI_ARCHIVE_SHA256,
    KOBURI_RUBY_STROKE_ADJUSTMENTS,
    LATIN_FAMILIES,
    LIBERTINUS_ARCHIVE_SHA256,
    LIBERTINUS_HORIZONTAL_STROKE_ADJUSTMENTS,
    LIBERTINUS_SCALE_FACTORS,
    NOTO_WEIGHT_CLASSES,
    SHIPPORI_ARCHIVE_SHA256,
    SHIPPORI_STROKE_ADJUSTMENTS,
    SOURCE_SERIF_ARCHIVE_SHA256,
    STIX_TWO_OTF_SHA256,
    VERSION_NUMBER,
    ZipMemberSource,
    default_output_path,
    font_identity,
    latin_build_profile,
    latin_font_source,
    libertinus_serif_source,
    noto_sans_source,
    noto_serif_source,
    shippori_source,
    source_serif_source,
    stix_two_text_source,
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
                serif = noto_serif_source(weight)
                self.assertIsInstance(serif, DirectSource)
                self.assertIn(weight, serif.filename)
                self.assertTrue(serif.url.endswith(serif.filename))
                self.assertEqual(len(serif.sha256), 64)

                sans = noto_sans_source(weight)
                self.assertIsInstance(sans, DirectSource)
                self.assertTrue(sans.url.endswith(sans.filename))
                self.assertEqual(len(sans.sha256), 64)

                shippori = shippori_source(weight)
                self.assertIsInstance(shippori, ZipMemberSource)
                self.assertTrue(
                    shippori.member.startswith("ShipporiMincho-OTF-")
                )
                self.assertEqual(len(shippori.sha256), 64)

        self.assertEqual(len(SHIPPORI_ARCHIVE_SHA256), 64)
        self.assertEqual(len(LIBERTINUS_ARCHIVE_SHA256), 64)

    def test_libertinus_latin_uses_nearest_available_serif_weights(self) -> None:
        self.assertEqual(
            {
                weight: libertinus_serif_source(weight).member
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
            self.assertEqual(len(libertinus_serif_source(weight).sha256), 64)
        self.assertEqual(
            LIBERTINUS_SCALE_FACTORS,
            {
                "ExtraLight": 1.119,
                "Light": 1.119,
                "Regular": 1.119,
                "Medium": 1.119,
                "SemiBold": 1.129,
                "Bold": 1.138,
                "Black": 1.138,
            },
        )
        self.assertEqual(
            LIBERTINUS_HORIZONTAL_STROKE_ADJUSTMENTS,
            {
                "ExtraLight": -13,
                "Light": -9,
                "Regular": -6,
                "Medium": 1,
                "SemiBold": -8,
                "Bold": -5,
                "Black": 6,
            },
        )

    def test_latin_candidates_are_pinned_and_keep_libertinus_default(self) -> None:
        self.assertEqual(
            LATIN_FAMILIES,
            ("noto", "libertinus", "stix-two-text", "source-serif-4"),
        )
        self.assertIsNone(latin_font_source("noto", "Regular"))
        self.assertEqual(
            latin_build_profile("libertinus", "Regular").scale_factor,
            LIBERTINUS_SCALE_FACTORS["Regular"],
        )

        stix = stix_two_text_source("Regular")
        self.assertIsInstance(stix, DirectSource)
        self.assertEqual(stix.sha256, STIX_TWO_OTF_SHA256["Regular"])
        self.assertEqual(
            latin_build_profile("stix-two-text", "Regular").scale_factor,
            1.110,
        )
        with self.assertRaisesRegex(ValueError, "no native ExtraLight"):
            stix_two_text_source("ExtraLight")

        source_serif = source_serif_source()
        self.assertIsInstance(source_serif, ZipMemberSource)
        self.assertEqual(len(SOURCE_SERIF_ARCHIVE_SHA256), 64)
        self.assertEqual(
            dict(latin_build_profile("source-serif-4", "Black").variations),
            {"wght": 900.0, "opsz": 20.0},
        )

    def test_shippori_punctuation_adjustments_cover_every_noto_weight(
        self,
    ) -> None:
        self.assertEqual(
            SHIPPORI_STROKE_ADJUSTMENTS,
            {
                "ExtraLight": -13,
                "Light": -10,
                "Regular": -7,
                "Medium": -4,
                "SemiBold": -1,
                "Bold": 4,
                "Black": 11,
            },
        )


    def test_koburi_ruby_weight_adjustments_cover_every_noto_weight(self) -> None:
        self.assertEqual(
            KOBURI_RUBY_STROKE_ADJUSTMENTS,
            {
                "ExtraLight": -4,
                "Light": -1,
                "Regular": 2,
                "Medium": 7,
                "SemiBold": 11,
                "Bold": 17,
                "Black": 25,
            },
        )


    def test_release_version_tracks_feature_change(self) -> None:
        self.assertEqual(VERSION_NUMBER, "1.027")

    def test_missing_sans_weights_use_nearest_static_sources(self) -> None:
        self.assertEqual(
            noto_sans_source("ExtraLight").filename, "NotoSansJP-Thin.otf"
        )
        self.assertEqual(
            noto_sans_source("SemiBold").filename, "NotoSansJP-Bold.otf"
        )

    def test_shippori_ligatures_follow_available_weights(self) -> None:
        self.assertEqual(
            {
                weight: shippori_source(weight).filename
                for weight in NOTO_WEIGHT_CLASSES
            },
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
