"""Outline geometry for generated glyphs and combining marks."""

from __future__ import annotations

import math

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from mark_positioning import (
    DEFAULT_MARK_TRANSFORM,
    HEART_DAKUTEN_CLEARANCE_RATIO,
    HEART_DAKUTEN_CLEARANCE_STEPS,
    HEART_DAKUTEN_MARK_TRANSFORMS,
)


MARK_COLLISION_AREA_EPSILON = 0.01


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


def glyph_path(font: TTFont, glyph_name: str) -> pathops.Path:
    path = pathops.Path()
    font.getGlyphSet()[glyph_name].draw(path.getPen())
    return path


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
    operation = (
        pathops.PathOp.UNION if amount > 0 else pathops.PathOp.DIFFERENCE
    )
    adjusted = pathops.op(outline, boundary, operation)
    if outline.verbs and not adjusted.verbs:
        raise ValueError("Latin weight adjustment removed an entire glyph")
    return adjusted


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


def mark_collision_free_transform(
    base: pathops.Path,
    mark: pathops.Path,
    mark_transform: Transform,
    maximum_y: float,
) -> Transform:
    """Move a combining mark by the shortest outward collision escape."""
    placed_mark = transform_path(mark, mark_transform)
    if placed_mark.bounds[3] > maximum_y:
        raise ValueError("Combining mark exceeds vertical metrics")

    def is_clear(outline: pathops.Path) -> bool:
        intersection = pathops.op(
            base, outline, pathops.PathOp.INTERSECTION
        )
        return (
            not intersection.verbs
            or abs(intersection.area) <= MARK_COLLISION_AREA_EPSILON
        )

    if is_clear(placed_mark):
        return mark_transform

    base_x_min, base_y_min, base_x_max, base_y_max = base.bounds
    mark_x_min, mark_y_min, mark_x_max, mark_y_max = placed_mark.bounds
    x_direction = (
        1 if mark_x_min + mark_x_max >= base_x_min + base_x_max else -1
    )
    y_direction = (
        1 if mark_y_min + mark_y_max >= base_y_min + base_y_max else -1
    )
    x_limit = max(
        1,
        math.ceil(
            base_x_max - mark_x_min
            if x_direction > 0
            else mark_x_max - base_x_min
        )
        + 1,
    )
    y_limit = max(
        1,
        math.ceil(
            base_y_max - mark_y_min
            if y_direction > 0
            else mark_y_max - base_y_min
        )
        + 1,
    )
    rays = (
        (x_direction, 0, x_limit),
        (0, y_direction, y_limit),
        (x_direction, y_direction, min(x_limit, y_limit)),
    )
    candidates: list[tuple[int, int, int, Transform]] = []
    for x_step, y_step, limit in rays:
        for distance in range(1, limit + 1):
            x_offset = x_step * distance
            y_offset = y_step * distance
            adjusted_transform = Transform(
                mark_transform.xx,
                mark_transform.xy,
                mark_transform.yx,
                mark_transform.yy,
                mark_transform.dx + x_offset,
                mark_transform.dy + y_offset,
            )
            adjusted_mark = transform_path(mark, adjusted_transform)
            if adjusted_mark.bounds[3] > maximum_y:
                if y_step > 0:
                    break
                continue
            if is_clear(adjusted_mark):
                candidates.append(
                    (
                        x_offset * x_offset + y_offset * y_offset,
                        abs(y_offset),
                        abs(x_offset),
                        adjusted_transform,
                    )
                )
                break
    if not candidates:
        raise ValueError(
            "Could not place combining mark without collision "
            "within vertical metrics"
        )
    return min(candidates, key=lambda candidate: candidate[:3])[3]


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
