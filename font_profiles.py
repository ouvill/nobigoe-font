from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, TypeAlias

BaseType: TypeAlias = Literal["noto", "koburi"]


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

NOTO_COMMIT = "9b0f1436e455d902de067a2501422e5dc71ad16b"
NOTO_WEIGHT_CLASSES = {
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "Black": 900,
}
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
LIBERTINUS_STROKE_ADJUSTMENTS = {
    "ExtraLight": -6,
    "Light": -3,
    "Regular": 0,
    "Medium": 4,
    "SemiBold": 0,
    "Bold": 0,
    "Black": 8,
}
LIBERTINUS_OTF_SHA256 = {
    "Regular": "fcf06307a77367394fcb0ccb241e59eea70dba3d732be309647611224679c733",
    "Semibold": "a4b3f28e85881db34695c1f005e4c79233a6caf3a2bd286c9b418c025fb99308",
    "Bold": "0264914210ed51b3231ebc92ce529e9f2e166ba9eebf0cd4a579558690a27b64",
}
LIBERTINUS_COPYRIGHT = (
    "Copyright © 2012-2024 The Libertinus Project Authors."
)
KOBURI_ARCHIVE_URL = "https://okoneya.jp/font/GenEiKoburiMin_v6.1.zip"
KOBURI_ARCHIVE_SHA256 = (
    "b17d4def22c048e704955912423c7bac8a03a3dbf1acaa722f254a7e9ece148a"
)
KOBURI_TTF_MEMBER = "GenEiKoburiMin_v6.1a/GenEiKoburiMin6-R.ttf"
KOBURI_TTF_SHA256 = (
    "c27fb4039ac9fae19152716992b5b9d07558e24f6cccea7b0c1abd0109235166"
)
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
VERSION_NUMBER = "1.025"
VERSION = f"Version {VERSION_NUMBER}"


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


def font_identity(base: BaseType, weight: str) -> FontIdentity:
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
