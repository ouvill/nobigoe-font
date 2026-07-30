"""Outline geometry for generated glyphs and combining marks."""

from __future__ import annotations

import math

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from .marks import (
    DEFAULT_MARK_TRANSFORM,
    HEART_DAKUTEN_CLEARANCE_RATIO,
    HEART_DAKUTEN_CLEARANCE_STEPS,
    HEART_DAKUTEN_MARK_TRANSFORMS,
)


def rectangle(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_min))
    pen.lineTo((x_max, y_max))
    pen.lineTo((x_min, y_max))
    pen.closePath()
    return path


def _cff_fd_transform(font: TTFont, glyph_name: str) -> Transform | None:
    """Return the relative CID Font DICT matrix omitted by fontTools glyph sets."""

    if "CFF " not in font:
        return None
    top = font["CFF "].cff.topDictIndex[0]
    if not all(hasattr(top, name) for name in ("FDArray", "FDSelect")):
        return None
    expected_scale = 1 / font["head"].unitsPerEm
    expected_top = (expected_scale, 0, 0, expected_scale, 0, 0)
    if tuple(top.FontMatrix) != expected_top:
        return None
    fd_index = top.FDSelect[font.getGlyphID(glyph_name)]
    matrix = getattr(top.FDArray[fd_index], "FontMatrix", None)
    if matrix is None:
        return None
    return Transform(*(value / expected_scale for value in matrix))


def glyph_path(font: TTFont, glyph_name: str) -> pathops.Path:
    path = pathops.Path()
    glyph_set = font.getGlyphSet()
    glyph_set[glyph_name].draw(DecomposingFilterPen(path.getPen(), glyph_set))
    transform = _cff_fd_transform(font, glyph_name)
    return transform_path(path, transform) if transform is not None else path


def bounds(font: TTFont, glyph_name: str) -> tuple[float, float, float, float]:
    pen = BoundsPen(font.getGlyphSet())
    font.getGlyphSet()[glyph_name].draw(pen)
    if pen.bounds is None:
        raise ValueError(f"Glyph {glyph_name} has no outline")
    return pen.bounds


def transform_path(outline: pathops.Path, transform: Transform) -> pathops.Path:
    transformed = pathops.Path()
    outline.draw(TransformPen(transformed.getPen(), transform))
    return transformed


def adjust_outline_weight(outline: pathops.Path, amount: float) -> pathops.Path:
    if amount == 0 or not outline.verbs:
        return outline
    boundary = pathops.Path()
    boundary.addPath(outline)
    boundary.stroke(
        2 * abs(amount),
        pathops.LineCap.BUTT_CAP,
        pathops.LineJoin.MITER_JOIN,
        4,
    )
    boundary.convertConicsToQuads()
    operation = pathops.PathOp.UNION if amount > 0 else pathops.PathOp.DIFFERENCE
    adjusted = pathops.op(outline, boundary, operation)
    if outline.verbs and not adjusted.verbs:
        raise ValueError("Latin weight adjustment removed an entire glyph")
    return adjusted


_HORIZONTAL_WEIGHT_STRETCH = 16


def adjust_outline_horizontal_weight(
    outline: pathops.Path,
    amount: float,
) -> pathops.Path:
    """Adjust vertical stems while retaining thin horizontal strokes."""
    if amount == 0 or not outline.verbs:
        return outline
    stretched = transform_path(
        outline,
        Transform(1, 0, 0, _HORIZONTAL_WEIGHT_STRETCH, 0, 0),
    )
    adjusted = adjust_outline_weight(stretched, amount)
    return transform_path(
        adjusted,
        Transform(1, 0, 0, 1 / _HORIZONTAL_WEIGHT_STRETCH, 0, 0),
    )


def centered_transform(
    outline: pathops.Path,
    scale: float,
    target_x: float,
    target_y: float,
) -> Transform:
    x_min, y_min, x_max, y_max = outline.bounds
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    return Transform(
        scale,
        0,
        0,
        scale,
        target_x - scale * center_x,
        target_y - scale * center_y,
    )


def centered_scaled_path(
    outline: pathops.Path,
    scale: float,
    target_x: float,
    target_y: float,
) -> pathops.Path:
    return transform_path(
        outline,
        centered_transform(outline, scale, target_x, target_y),
    )


def compose_mark_glyph(
    base: pathops.Path,
    mark: pathops.Path,
    mark_transform: Transform = DEFAULT_MARK_TRANSFORM,
) -> pathops.Path:
    combined = pathops.Path()
    combined.addPath(base)
    combined.addPath(transform_path(mark, mark_transform))
    return combined


def expand_outline(
    outline: pathops.Path,
    radius: float,
    steps: int,
) -> pathops.Path:
    expanded = outline
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        shifted = transform_path(
            outline,
            Transform(
                1,
                0,
                0,
                1,
                radius * math.cos(angle),
                radius * math.sin(angle),
            ),
        )
        expanded = pathops.op(expanded, shifted, pathops.PathOp.UNION)
    return expanded


def compose_heart_dakuten_glyph(
    base: pathops.Path,
    mark: pathops.Path,
) -> pathops.Path:
    mark_contours = list(mark.contours)
    if len(mark_contours) != len(HEART_DAKUTEN_MARK_TRANSFORMS):
        raise ValueError("Expected a two-contour combining dakuten glyph")
    placed_contours = [
        transform_path(contour, transform)
        for contour, transform in zip(
            mark_contours,
            HEART_DAKUTEN_MARK_TRANSFORMS,
            strict=True,
        )
    ]
    placed_mark = pathops.Path()
    for contour in placed_contours:
        placed_mark.addPath(contour)
    centers = [
        ((x_min + x_max) / 2, (y_min + y_max) / 2)
        for x_min, y_min, x_max, y_max in (
            contour.bounds for contour in placed_contours
        )
    ]
    clearance_radius = math.dist(*centers) * HEART_DAKUTEN_CLEARANCE_RATIO
    clearance = expand_outline(
        placed_mark,
        clearance_radius,
        HEART_DAKUTEN_CLEARANCE_STEPS,
    )
    notched_base = pathops.op(base, clearance, pathops.PathOp.DIFFERENCE)
    combined = pathops.Path()
    combined.addPath(notched_base)
    combined.addPath(placed_mark)
    return combined
