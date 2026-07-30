from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, TypeAlias

BaseType: TypeAlias = Literal["noto", "koburi"]
KanaStyle: TypeAlias = Literal["noto", "novel"]
KANA_STYLES: tuple[KanaStyle, ...] = ("noto", "novel")
LatinFamily: TypeAlias = Literal[
    "noto",
    "libertinus",
    "stix-two-text",
    "source-serif-4",
]
LATIN_FAMILIES: tuple[LatinFamily, ...] = (
    "noto",
    "libertinus",
    "stix-two-text",
    "source-serif-4",
)

LatinGlyphClass: TypeAlias = Literal[
    "letters",
    "figures",
    "marks",
    "punctuation",
    "symbols",
    "spacing",
]


@dataclass(frozen=True)
class LatinTransform:
    """Geometric adjustments for one class of imported Latin glyphs."""

    scale_factor: float
    horizontal_stroke_adjustment: float
    baseline_shift: float = 0


@dataclass(frozen=True)
class LatinTransformOverride:
    """Replace the default transform for one Unicode glyph class."""

    glyph_class: LatinGlyphClass
    transform: LatinTransform


LATIN_LAYOUT_FEATURES = ("*",)
LATIN_COMMON_LAYOUT_FEATURES = (
    "case",
    "frac",
    "lnum",
    "onum",
    "pnum",
    "subs",
    "sups",
    "tnum",
    "zero",
)


@dataclass(frozen=True)
class DirectSource:
    """A pinned font file available directly from a fixed URL."""

    filename: str
    url: str
    sha256: str


@dataclass(frozen=True)
class ZipMemberSource:
    """A pinned font file extracted from a member of a fixed ZIP archive."""

    archive_filename: str
    archive_url: str
    archive_sha256: str
    member: str
    sha256: str

    @property
    def filename(self) -> str:
        return PurePosixPath(self.member).name


FontSource: TypeAlias = DirectSource | ZipMemberSource


@dataclass(frozen=True)
class LatinBuildProfile:
    """Source-specific transformations applied while importing Latin glyphs."""

    family: LatinFamily
    scale_factor: float
    horizontal_stroke_adjustment: float
    variations: tuple[tuple[str, float], ...] = ()
    copyright: str | None = None
    baseline_shift: float = 0
    transform_overrides: tuple[LatinTransformOverride, ...] = ()
    layout_features: tuple[str, ...] = LATIN_LAYOUT_FEATURES
    common_layout_features: tuple[str, ...] = LATIN_COMMON_LAYOUT_FEATURES

    def transform_for(self, glyph_class: LatinGlyphClass) -> LatinTransform:
        for override in self.transform_overrides:
            if override.glyph_class == glyph_class:
                return override.transform
        return LatinTransform(
            self.scale_factor,
            self.horizontal_stroke_adjustment,
            self.baseline_shift,
        )


NOTO_COMMIT = "9b0f1436e455d902de067a2501422e5dc71ad16b"
NOTO_SERIF_CFF2_VARIABLE_SHA256 = (
    "39701fd096bc51204a8444c6c2659f007b29674a13eb62ddfa470638fe8179cd"
)
NOTO_WEIGHT_CLASSES = {
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "Black": 900,
}
NOTO_SERIF_VARIABLE_SHA256 = (
    "99999f906b3793c7c97661a05ef9d53488d488604683b308c756d084b71df7d1"
)
NOTO_SERIF_SHA256 = {
    "ExtraLight": "a5056bf9b22a624b62115e9ad242879492179fe6f0b45ce5932967eb20295d5e",
    "Light": "54e6b0fa70430987a6c12001f128812f37fc315d899cb1d964395ab6450bb977",
    "Regular": "2c9a12dbd4f2408c4610c7ee84a108b62d7236c3775baed618c64d9cb44b2f04",
    "Medium": "f3a906cadd27f812a8b4b18618fa750928e65339fb372bd3f825f24e3271180b",
    "SemiBold": "116d06c2b11ceba33ccb3f8c9eb1c86aba3d5761a1199fd37f74e83365e7a53d",
    "Bold": "1e03488a0d5e819f07fcd74f54703a7961ba466d3ae900f8a2a730541e6d4543",
    "Black": "b7197366b775ccb6cd3473b7b09f2c5759a2fdfdbfedf975029203828d0ad386",
}
NOTO_SANS_WEIGHTS = {
    "ExtraLight": "Thin",
    "Light": "Light",
    "Regular": "Regular",
    "Medium": "Medium",
    "SemiBold": "Bold",
    "Bold": "Bold",
    "Black": "Black",
}
NOTO_SANS_SHA256 = {
    "Thin": "1d8462eb0050bf6f8ee8dc0a34f11185839e155b0fce8ec2f14427b28d4d134f",
    "Light": "e358dcfa7970805300a953bb71209c3efcbcc17a00a5e4101f8cf94a3870ad93",
    "Regular": "dff723ba59d57d136764a04b9b2d03205544f7cd785a711442d6d2d085ac5073",
    "Medium": "f396a3b57256e4515be9cb41f7aac54766d654890082a9f1b5c2451b5c093d8a",
    "Bold": "1b0edfb500b73a4fa8a4fcaae1bbbd403994e08e73e3e0da37e70d3853f42c5f",
    "Black": "3aa30b0956510f4205f759ab3079a5b658310ebcda2577f290466ea51c948819",
}
LIBERTINUS_VERSION = "7.051"
LIBERTINUS_ARCHIVE_URL = (
    "https://github.com/alerque/libertinus/releases/download/"
    f"v{LIBERTINUS_VERSION}/Libertinus-{LIBERTINUS_VERSION}.zip"
)
LIBERTINUS_ARCHIVE_SHA256 = (
    "4d9be29b5cb380c35af8ba967abcc752ad1e07be1f738a9789c33e0dd7478c92"
)
LIBERTINUS_WEIGHTS = {
    "ExtraLight": "Regular",
    "Light": "Regular",
    "Regular": "Regular",
    "Medium": "Regular",
    "SemiBold": "Semibold",
    "Bold": "Bold",
    "Black": "Bold",
}
LIBERTINUS_SCALE_FACTORS = {
    "ExtraLight": 1.119,
    "Light": 1.119,
    "Regular": 1.119,
    "Medium": 1.119,
    "SemiBold": 1.129,
    "Bold": 1.138,
    "Black": 1.138,
}
LIBERTINUS_HORIZONTAL_STROKE_ADJUSTMENTS = {
    "ExtraLight": -13,
    "Light": -9,
    "Regular": -6,
    "Medium": 1,
    "SemiBold": -8,
    "Bold": -5,
    "Black": 6,
}
# Normalize Koburi's 97.7%-sized hiragana before comparing kana ink area.
KOBURI_RUBY_STROKE_ADJUSTMENTS = {
    "ExtraLight": -4,
    "Light": -1,
    "Regular": 2,
    "Medium": 7,
    "SemiBold": 11,
    "Bold": 17,
    "Black": 25,
}
LIBERTINUS_OTF_SHA256 = {
    "Regular": "fcf06307a77367394fcb0ccb241e59eea70dba3d732be309647611224679c733",
    "Semibold": "a4b3f28e85881db34695c1f005e4c79233a6caf3a2bd286c9b418c025fb99308",
    "Bold": "0264914210ed51b3231ebc92ce529e9f2e166ba9eebf0cd4a579558690a27b64",
}
LIBERTINUS_COPYRIGHT = "Copyright © 2012-2024 The Libertinus Project Authors."

STIX_TWO_VERSION = "2.13b171"
STIX_TWO_TAG = f"v{STIX_TWO_VERSION}"
STIX_TWO_WEIGHTS = {
    "Regular": "Regular",
    "Medium": "Medium",
    "SemiBold": "SemiBold",
    "Bold": "Bold",
}
STIX_TWO_OTF_SHA256 = {
    "Regular": "c4864ca6ec071c2d31d0d8309001faa1ee3517fffb53a31a405a697b71f52ca1",
    "Medium": "9cc9f870852a46d708907b96ed024b8d0067a05276d939bfe0b7e89752afc8d9",
    "SemiBold": "896d80fbfd67e86ead7e2d593d631eab9bb142ee96dcd8e7aa8dff95ddda0f2a",
    "Bold": "7ef76c666a6704f76ed3fa27bcdda55b36e558b5c2c93b49b03d854db96bdeb5",
}
STIX_TWO_SCALE_FACTOR = 1.110
# Minimize the mean absolute per-glyph area/advance error against Noto Serif JP
# over A-Z, a-z, and 0-9 after applying the shared STIX Two scale factor.
STIX_TWO_HORIZONTAL_STROKE_ADJUSTMENTS = {
    "Regular": -10,
    "Medium": -12,
    "SemiBold": -14,
    "Bold": -15,
}
STIX_TWO_COPYRIGHT = (
    "Copyright 2001-2021 The STIX Fonts Project Authors "
    "(https://github.com/stipub/stixfonts)"
)
SOURCE_SERIF_VERSION = "4.005"
SOURCE_SERIF_ARCHIVE_URL = (
    "https://github.com/adobe-fonts/source-serif/releases/download/"
    f"{SOURCE_SERIF_VERSION}R/source-serif-{SOURCE_SERIF_VERSION}_Desktop.zip"
)
SOURCE_SERIF_ARCHIVE_SHA256 = (
    "549fdb8f9a682bd06944298621404969f6de77c2e422ff3b8244a1dcd6a0c425"
)
SOURCE_SERIF_VARIABLE_MEMBER = (
    f"source-serif-{SOURCE_SERIF_VERSION}_Desktop/VAR/SourceSerif4Variable-Roman.ttf"
)
SOURCE_SERIF_VARIABLE_SHA256 = (
    "14d360ee1b76655da9276628b229e11671bc1f5d1083636144db6677d452cf55"
)
SOURCE_SERIF_SCALE_FACTOR = 1.088
SOURCE_SERIF_OPTICAL_SIZE = 20.0
SOURCE_SERIF_COPYRIGHT = (
    "© 2014 - 2023 Adobe (http://www.adobe.com/), with Reserved Font Name ‘Source’."
)

KOBURI_ARCHIVE_URL = "https://okoneya.jp/font/GenEiKoburiMin_v6.1.zip"
KOBURI_ARCHIVE_SHA256 = (
    "b17d4def22c048e704955912423c7bac8a03a3dbf1acaa722f254a7e9ece148a"
)
KOBURI_TTF_MEMBER = "GenEiKoburiMin_v6.1a/GenEiKoburiMin6-R.ttf"
KOBURI_TTF_SHA256 = "c27fb4039ac9fae19152716992b5b9d07558e24f6cccea7b0c1abd0109235166"
SHIPPORI_ARCHIVE_URL = "https://fontdasu.com/download/shippori3.zip"
SHIPPORI_ARCHIVE_SHA256 = (
    "dbdcab920d82238bda26296bccd9630906b427ee91b31f5da2dde8e47b0b202e"
)
SHIPPORI_WEIGHTS = {
    "ExtraLight": "Regular",
    "Light": "Regular",
    "Regular": "Regular",
    "Medium": "Medium",
    "SemiBold": "SemiBold",
    "Bold": "Bold",
    "Black": "ExtraBold",
}
# Match Shippori punctuation to Noto Serif JP's fullwidth !/? stroke weight.
# Values minimize the mean 2 * ink area / outline perimeter difference.
SHIPPORI_STROKE_ADJUSTMENTS = {
    "ExtraLight": -13,
    "Light": -10,
    "Regular": -7,
    "Medium": -4,
    "SemiBold": -1,
    "Bold": 4,
    "Black": 11,
}
SHIPPORI_OTF_SHA256 = {
    "Regular": "f597e65ce1e686ad36b63e0c82e4931e9d815187ff2311705dcf1b751ecae804",
    "Medium": "f2791831f662ad4de127eaef7e86a1ff6deb2e7a404330747729abc565821e06",
    "SemiBold": "52c424195a4b47bdacb3ea5cf4ced699846dfbe8a3287272fdbb8c10bcc3215d",
    "Bold": "1d890e64150ea8db1b593aa5ba78150a1db6156a6c566d00cf45bfe13526399f",
    "ExtraBold": "1ff1f3d462b1d37d69995ececced9011f89d15a56a4e94db923e982125b7f768",
}
SHIPPORI_COPYRIGHT = (
    "Copyright (c) 2021, The Shippori Mincho Project Authors "
    "(https://github.com/fontdasu/ShipporiMincho)"
)


@dataclass(frozen=True)
class FontIdentity:
    family: str
    japanese_family: str
    style: str
    weight_class: int
    postscript_name: str

    @property
    def full_name(self) -> str:
        return f"{self.family} {self.style}"

    @property
    def japanese_full_name(self) -> str:
        return f"{self.japanese_family} {self.style}"

    @property
    def legacy_family(self) -> str:
        if self.style in {"Regular", "Bold"}:
            return self.family
        return self.full_name

    @property
    def japanese_legacy_family(self) -> str:
        if self.style in {"Regular", "Bold"}:
            return self.japanese_family
        return self.japanese_full_name


def font_identity(
    base: BaseType,
    weight: str,
    kana_style: KanaStyle = "noto",
) -> FontIdentity:
    if kana_style == "novel":
        if base != "noto":
            raise ValueError("--kana-style novel requires --base noto")
        return FontIdentity(
            "Nobigoe Novel Mincho",
            "のびごえ小説明朝",
            weight,
            NOTO_WEIGHT_CLASSES[weight],
            f"NobigoeNovelMincho-{weight}",
        )
    if kana_style != "noto":
        raise ValueError(f"Unknown kana style {kana_style!r}")
    if base == "koburi":
        return FontIdentity(
            "Nobigoe Koburi Mincho",
            "のびごえこぶり明朝",
            "Regular",
            400,
            "NobigoeKoburiMincho-Regular",
        )
    return FontIdentity(
        "Nobigoe Mincho",
        "のびごえ明朝",
        weight,
        NOTO_WEIGHT_CLASSES[weight],
        f"NobigoeMincho-{weight}",
    )


def default_output_path(identity: FontIdentity, base: BaseType) -> Path:
    suffix = "ttf" if base == "koburi" else "otf"
    return Path("dist") / f"{identity.postscript_name}.{suffix}"


def noto_serif_source(weight: str) -> DirectSource:
    filename = f"NotoSerifJP-{weight}.otf"
    url = (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/"
        f"{NOTO_COMMIT}/Serif/SubsetOTF/JP/{filename}"
    )
    return DirectSource(filename, url, NOTO_SERIF_SHA256[weight])


def noto_serif_variable_source() -> DirectSource:
    """Return the pinned development source for the Novel kana design VF."""

    filename = "NotoSerifJP-VF.ttf"
    url = (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/"
        f"{NOTO_COMMIT}/Serif/Variable/TTF/Subset/{filename}"
    )
    return DirectSource(filename, url, NOTO_SERIF_VARIABLE_SHA256)


def noto_serif_cff2_variable_source() -> DirectSource:
    """Return the pinned CFF2 source for the experimental variable build."""

    filename = "NotoSerifJP-VF.otf"
    url = (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/"
        f"{NOTO_COMMIT}/Serif/Variable/OTF/Subset/{filename}"
    )
    return DirectSource(filename, url, NOTO_SERIF_CFF2_VARIABLE_SHA256)


def noto_sans_source(weight: str) -> DirectSource:
    sans_weight = NOTO_SANS_WEIGHTS[weight]
    filename = f"NotoSansJP-{sans_weight}.otf"
    url = (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/"
        f"{NOTO_COMMIT}/Sans/SubsetOTF/JP/{filename}"
    )
    return DirectSource(filename, url, NOTO_SANS_SHA256[sans_weight])


def koburi_source() -> ZipMemberSource:
    return ZipMemberSource(
        "GenEiKoburiMin_v6.1.zip",
        KOBURI_ARCHIVE_URL,
        KOBURI_ARCHIVE_SHA256,
        KOBURI_TTF_MEMBER,
        KOBURI_TTF_SHA256,
    )


def libertinus_serif_source(weight: str) -> ZipMemberSource:
    libertinus_weight = LIBERTINUS_WEIGHTS[weight]
    member = (
        f"Libertinus-{LIBERTINUS_VERSION}/static/OTF/"
        f"LibertinusSerif-{libertinus_weight}.otf"
    )
    return ZipMemberSource(
        f"Libertinus-{LIBERTINUS_VERSION}.zip",
        LIBERTINUS_ARCHIVE_URL,
        LIBERTINUS_ARCHIVE_SHA256,
        member,
        LIBERTINUS_OTF_SHA256[libertinus_weight],
    )


def stix_two_text_source(weight: str) -> DirectSource:
    if weight not in STIX_TWO_WEIGHTS:
        supported = ", ".join(STIX_TWO_WEIGHTS)
        raise ValueError(
            f"STIX Two Text has no native {weight} source; choose one of {supported}"
        )
    stix_weight = STIX_TWO_WEIGHTS[weight]
    filename = f"STIXTwoText-{stix_weight}.otf"
    url = (
        "https://raw.githubusercontent.com/stipub/stixfonts/"
        f"{STIX_TWO_TAG}/fonts/static_otf/{filename}"
    )
    return DirectSource(filename, url, STIX_TWO_OTF_SHA256[stix_weight])


def source_serif_source() -> ZipMemberSource:
    return ZipMemberSource(
        f"source-serif-{SOURCE_SERIF_VERSION}_Desktop.zip",
        SOURCE_SERIF_ARCHIVE_URL,
        SOURCE_SERIF_ARCHIVE_SHA256,
        SOURCE_SERIF_VARIABLE_MEMBER,
        SOURCE_SERIF_VARIABLE_SHA256,
    )


def latin_font_source(family: LatinFamily, weight: str) -> FontSource | None:
    if family == "noto":
        return None
    if family == "libertinus":
        return libertinus_serif_source(weight)
    if family == "stix-two-text":
        return stix_two_text_source(weight)
    if family == "source-serif-4":
        return source_serif_source()
    raise ValueError(f"Unknown Latin family {family!r}")


def latin_build_profile(family: LatinFamily, weight: str) -> LatinBuildProfile:
    if family == "noto":
        return LatinBuildProfile(family, 1, 0)
    if family == "libertinus":
        return LatinBuildProfile(
            family,
            LIBERTINUS_SCALE_FACTORS[weight],
            LIBERTINUS_HORIZONTAL_STROKE_ADJUSTMENTS[weight],
            copyright=LIBERTINUS_COPYRIGHT,
        )
    if family == "stix-two-text":
        stix_two_text_source(weight)
        return LatinBuildProfile(
            family,
            STIX_TWO_SCALE_FACTOR,
            STIX_TWO_HORIZONTAL_STROKE_ADJUSTMENTS[weight],
            copyright=STIX_TWO_COPYRIGHT,
        )
    if family == "source-serif-4":
        return LatinBuildProfile(
            family,
            SOURCE_SERIF_SCALE_FACTOR,
            0,
            (
                ("wght", float(NOTO_WEIGHT_CLASSES[weight])),
                ("opsz", SOURCE_SERIF_OPTICAL_SIZE),
            ),
            SOURCE_SERIF_COPYRIGHT,
        )
    raise ValueError(f"Unknown Latin family {family!r}")


def shippori_source(weight: str) -> ZipMemberSource:
    shippori_weight = SHIPPORI_WEIGHTS[weight]
    member = f"ShipporiMincho-OTF-{shippori_weight}.otf"
    return ZipMemberSource(
        "shippori3.zip",
        SHIPPORI_ARCHIVE_URL,
        SHIPPORI_ARCHIVE_SHA256,
        member,
        SHIPPORI_OTF_SHA256[shippori_weight],
    )
