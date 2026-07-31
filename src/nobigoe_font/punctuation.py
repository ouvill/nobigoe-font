"""Manga punctuation outline construction and ligature rules."""

from __future__ import annotations

import math

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from . import geometry

SHIPPORI_PRECOMPOSED_LIGATURES = {
    "!!": 0x203C,
    "??": 0x2047,
    "?!": 0x2048,
    "!?": 0x2049,
}
SHIPPORI_UPRIGHT_PUNCTUATION = {
    "!": 0xE000,
    "?": 0xFF1F,
}
SHIPPORI_UPRIGHT_EXCLAMATIONS = {
    "!": SHIPPORI_UPRIGHT_PUNCTUATION["!"],
    "!!": 0xE002,
    "!!!": 0xE007,
    "!!!!": 0xE0E3,
}
SHIPPORI_COMPONENT_LIGATURES = {
    "!": SHIPPORI_UPRIGHT_EXCLAMATIONS["!!"],
    "?": 0x2047,
}
MANGA_PUNCTUATION_SEQUENCES = (
    "!!!!!",
    "!!!!",
    "!!??",
    "??!!",
    "!!!",
    "???",
    "!!?",
    "??!",
    "?!?",
    "!??",
    "!?!",
    "?!!",
    "?!",
    "!?",
    "!!",
    "??",
)
PUNCTUATION_VARIANT_SEQUENCES = (
    "!",
    "?",
    *MANGA_PUNCTUATION_SEQUENCES,
)
PUNCTUATION_ITALIC_COUNT = len(PUNCTUATION_VARIANT_SEQUENCES)
PUNCTUATION_SLANT_ANGLE = 12


def shippori_upright_punctuation_paths(
    font: TTFont,
) -> dict[str, pathops.Path]:
    cmap = font.getBestCmap()
    return {
        mark: geometry.glyph_path(font, cmap[codepoint])
        for mark, codepoint in SHIPPORI_UPRIGHT_PUNCTUATION.items()
    }


def make_punctuation_ligature(
    font: TTFont, sequence: str, advance: int = 1000
) -> pathops.Path:
    gap = 40
    components: list[tuple[pathops.Path, float, float]] = []
    total_width = gap * (len(sequence) - 1)
    cmap = font.getBestCmap()
    upright_codepoint = SHIPPORI_UPRIGHT_EXCLAMATIONS.get(sequence)
    if upright_codepoint is not None:
        return geometry.glyph_path(font, cmap[upright_codepoint])
    precomposed_codepoint = SHIPPORI_PRECOMPOSED_LIGATURES.get(sequence)
    if precomposed_codepoint is not None:
        return geometry.glyph_path(font, cmap[precomposed_codepoint])

    for mark in sequence:
        source_codepoint = SHIPPORI_COMPONENT_LIGATURES[mark]
        source = geometry.glyph_path(font, cmap[source_codepoint])
        contours = list(source.contours)
        if len(contours) != 4:
            raise ValueError(f"Expected four contours in U+{source_codepoint:04X}")
        outline = pathops.Path()
        outline.addPath(contours[0])
        outline.addPath(contours[2])
        x_min, _, x_max, _ = outline.bounds
        width = x_max - x_min
        components.append((outline, x_min, width))
        total_width += width

    scale = min(1.0, (advance - 40) / total_width)
    combined = pathops.Path()
    cursor = (advance - total_width * scale) / 2
    for outline, x_min, width in components:
        transform = Transform(scale, 0, 0, 1, cursor - scale * x_min, 0)
        outline.draw(TransformPen(combined.getPen(), transform))
        cursor += (width + gap) * scale
    return combined


def slant_punctuation_outline(outline: pathops.Path) -> pathops.Path:
    shear = math.tan(math.radians(PUNCTUATION_SLANT_ANGLE))
    slanted = geometry.transform_path(outline, Transform(1, 0, shear, 1, 0, 0))
    x_min, _, x_max, _ = slanted.bounds
    return geometry.transform_path(
        slanted,
        Transform(1, 0, 0, 1, 500 - (x_min + x_max) / 2, 0),
    )


def punctuation_ligature_rules(
    exclamation: str,
    question: str,
    ligatures: list[tuple[str, str]],
) -> str:
    inputs = {"!": exclamation, "?": question}
    return "".join(
        f"  sub {' '.join(inputs[mark] for mark in sequence)}" f" by {name};\n"
        for sequence, name in ligatures
    )
