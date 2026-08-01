"""Build the marks-only variable font for use before another font."""

from __future__ import annotations

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

from .metadata import set_japanese_name, set_name
from .profiles import NOTO_WEIGHT_CLASSES
from .version import VERSION, VERSION_NUMBER

ESSENTIAL_CODEPOINTS: frozenset[int] = frozenset(
    (0x2015, 0x301C, 0x3030, 0x30FC, 0xFF5E)
)
ESSENTIAL_LAYOUT_FEATURES: tuple[str, ...] = (
    "liga",
    "calt",
    "ss04",
    "ss05",
    "vert",
    "vrt2",
)
ESSENTIAL_FAMILY = "Nobigoe Essential"
ESSENTIAL_JAPANESE_FAMILY = "のびごえエッセンシャル"
ESSENTIAL_POSTSCRIPT_PREFIX = "NobigoeEssential"


def _default_style(font: TTFont) -> str:
    if "fvar" not in font:
        record = font["name"].getName(17, 3, 1, 0x409)
        if record is None:
            record = font["name"].getName(2, 3, 1, 0x409)
        return record.toUnicode() if record is not None else "Regular"

    weight_axis = next(
        (axis for axis in font["fvar"].axes if axis.axisTag == "wght"), None
    )
    if weight_axis is None:
        return "Regular"
    styles = {weight: style for style, weight in NOTO_WEIGHT_CLASSES.items()}
    try:
        return styles[weight_axis.defaultValue]
    except KeyError as error:
        raise ValueError(
            f"Unsupported default weight {weight_axis.defaultValue:g} in essential source"
        ) from error


def _rename_font(font: TTFont) -> None:
    style = _default_style(font)
    postscript_name = f"{ESSENTIAL_POSTSCRIPT_PREFIX}-{style}"
    full_name = f"{ESSENTIAL_FAMILY} {style}"
    japanese_full_name = f"{ESSENTIAL_JAPANESE_FAMILY} {style}"

    set_name(font, 1, ESSENTIAL_FAMILY)
    set_name(font, 2, style)
    set_name(font, 3, f"{VERSION_NUMBER};NOBIGOE;{postscript_name}")
    set_name(font, 4, full_name)
    set_name(font, 5, VERSION)
    set_name(font, 6, postscript_name)
    set_name(font, 16, ESSENTIAL_FAMILY)
    set_name(font, 17, style)
    set_name(font, 25, ESSENTIAL_POSTSCRIPT_PREFIX)
    set_japanese_name(font, 1, ESSENTIAL_JAPANESE_FAMILY)
    set_japanese_name(font, 4, japanese_full_name)
    set_japanese_name(font, 16, ESSENTIAL_JAPANESE_FAMILY)
    set_japanese_name(font, 17, style)

    if "fvar" not in font:
        return
    styles = {weight: name for name, weight in NOTO_WEIGHT_CLASSES.items()}
    for instance in font["fvar"].instances:
        instance_style = styles[instance.coordinates["wght"]]
        if instance.postscriptNameID != 0xFFFF:
            set_name(
                font,
                instance.postscriptNameID,
                f"{ESSENTIAL_POSTSCRIPT_PREFIX}-{instance_style}",
            )


def _best_cmap(font: TTFont) -> dict[int, str]:
    cmap = font.getBestCmap()
    if cmap is None:
        raise ValueError("The essential source has no Unicode cmap")
    return cmap


def build_essential(source_path: Path, output_path: Path, face: int = 0) -> None:
    """Subset a Nobigoe variable source to the five connected marks."""

    font = TTFont(source_path, fontNumber=face, recalcTimestamp=False)
    source_codepoints = set(_best_cmap(font))
    missing = sorted(ESSENTIAL_CODEPOINTS.difference(source_codepoints))
    if missing:
        formatted = ", ".join(f"U+{codepoint:04X}" for codepoint in missing)
        raise ValueError(f"The essential source is missing {formatted}")

    options = subset.Options()
    options.layout_features = [str(tag) for tag in ESSENTIAL_LAYOUT_FEATURES]
    options.glyph_names = True
    options.name_legacy = True
    options.notdef_outline = True
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=ESSENTIAL_CODEPOINTS)
    subsetter.subset(font)

    actual_codepoints = set(_best_cmap(font))
    differences = sorted(actual_codepoints.symmetric_difference(ESSENTIAL_CODEPOINTS))
    if differences:
        formatted = ", ".join(f"U+{codepoint:04X}" for codepoint in differences)
        raise AssertionError(f"Essential cmap differs at: {formatted}")

    _rename_font(font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path)
