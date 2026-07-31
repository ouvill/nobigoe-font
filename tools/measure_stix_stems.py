"""Match shared STIX Latin locations to representative Japanese main stems."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any, Literal

from fontTools.misc.bezierTools import solveCubic, solveQuadratic
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from nobigoe_font.profiles import NOTO_WEIGHT_CLASSES, STIX_TWO_SCALE_FACTOR
from nobigoe_font.variable_stix import _interpolate_glyph, _raw_endpoints

ThinTarget = Literal["japanese", "midpoint", "noto-latin"]
_REGULAR_WEIGHT = NOTO_WEIGHT_CLASSES["Regular"]

LATIN_PROBES: dict[str, tuple[float, ...]] = {
    "H": (0.3, 0.7),
    "I": (0.5,),
    "E": (0.65,),
    "F": (0.7,),
    "L": (0.55,),
    "n": (0.35,),
    "i": (0.45,),
    "l": (0.45,),
    "h": (0.35,),
    "m": (0.35,),
    "u": (0.55,),
}
JAPANESE_PROBES: dict[str, tuple[float, ...]] = {
    "口": (0.25, 0.5, 0.75),
    "日": (0.2, 0.8),
    "田": (0.2, 0.8),
    "中": (0.2, 0.8),
    "山": (0.3, 0.6),
}


class HorizontalScanPen(BasePen):
    """Collect outline intersections with one horizontal scanline."""

    def __init__(self, glyph_set: Any, y: float) -> None:
        super().__init__(glyph_set)
        self.y = y
        self.intersections: list[float] = []
        self._start: tuple[float, float] | None = None
        self._current: tuple[float, float] | None = None

    def _moveTo(self, pt: tuple[float, float]) -> None:
        self._start = self._current = pt

    def _lineTo(self, pt: tuple[float, float]) -> None:
        point = pt
        if self._current is None:
            raise ValueError("Scanline contour has no current point")
        x_0, y_0 = self._current
        x_1, y_1 = point
        if (y_0 < self.y < y_1) or (y_1 < self.y < y_0):
            self.intersections.append(x_0 + (self.y - y_0) * (x_1 - x_0) / (y_1 - y_0))
        self._current = point

    def _qCurveToOne(self, pt1: tuple[float, float], pt2: tuple[float, float]) -> None:
        control, point = pt1, pt2
        if self._current is None:
            raise ValueError("Scanline contour has no current point")
        x_0, y_0 = self._current
        x_1, y_1 = control
        x_2, y_2 = point
        roots = solveQuadratic(
            y_0 - 2 * y_1 + y_2,
            2 * (y_1 - y_0),
            y_0 - self.y,
        )
        for location in roots:
            if 1e-7 < location < 1 - 1e-7:
                inverse = 1 - location
                self.intersections.append(
                    inverse * inverse * x_0
                    + 2 * inverse * location * x_1
                    + location * location * x_2
                )
        self._current = point

    def _curveToOne(
        self,
        pt1: tuple[float, float],
        pt2: tuple[float, float],
        pt3: tuple[float, float],
    ) -> None:
        control_1, control_2, point = pt1, pt2, pt3
        if self._current is None:
            raise ValueError("Scanline contour has no current point")
        x_0, y_0 = self._current
        x_1, y_1 = control_1
        x_2, y_2 = control_2
        x_3, y_3 = point
        roots = solveCubic(
            -y_0 + 3 * y_1 - 3 * y_2 + y_3,
            3 * y_0 - 6 * y_1 + 3 * y_2,
            -3 * y_0 + 3 * y_1,
            y_0 - self.y,
        )
        for location in roots:
            if 1e-7 < location < 1 - 1e-7:
                inverse = 1 - location
                self.intersections.append(
                    inverse**3 * x_0
                    + 3 * inverse * inverse * location * x_1
                    + 3 * inverse * location * location * x_2
                    + location**3 * x_3
                )
        self._current = point

    def _closePath(self) -> None:
        if self._current is not None and self._start is not None:
            if self._current != self._start:
                self._lineTo(self._start)

    def _endPath(self) -> None:
        pass

    def widths(self) -> tuple[float, ...]:
        intersections = sorted(self.intersections)
        if len(intersections) % 2:
            raise ValueError(
                f"Scanline has an odd intersection count: {intersections!r}"
            )
        return tuple(
            intersections[index + 1] - intersections[index]
            for index in range(0, len(intersections), 2)
        )


def _main_intervals(widths: tuple[float, ...]) -> tuple[float, ...]:
    if not widths:
        raise ValueError("Stem probe did not intersect the outline")
    threshold = max(widths) * 0.55
    return tuple(width for width in widths if width >= threshold)


def _font_stems(
    font: TTFont, probes: dict[str, tuple[float, ...]]
) -> tuple[float, ...]:
    cmap = font.getBestCmap()
    if cmap is None:
        raise ValueError("Noto source has no Unicode cmap")
    glyph_set = font.getGlyphSet()
    widths: list[float] = []
    for character, fractions in probes.items():
        glyph = glyph_set[cmap[ord(character)]]
        bounds_pen = BoundsPen(glyph_set)
        glyph.draw(bounds_pen)
        if bounds_pen.bounds is None:
            raise ValueError(f"Stem probe {character!r} has no bounds")
        _, y_min, _, y_max = bounds_pen.bounds
        for fraction in fractions:
            pen = HorizontalScanPen(glyph_set, y_min + fraction * (y_max - y_min))
            glyph.draw(pen)
            widths.extend(_main_intervals(pen.widths()))
    return tuple(widths)


def _stix_stems(
    location: float,
    font_400: TTFont,
    glyphs_400: dict[str, object],
    glyphs_700: dict[str, object],
) -> tuple[float, ...]:
    cmap = font_400.getBestCmap()
    if cmap is None:
        raise ValueError("STIX source has no Unicode cmap")
    widths: list[float] = []
    for character, fractions in LATIN_PROBES.items():
        name = cmap[ord(character)]
        glyph = _interpolate_glyph(
            glyphs_400[name],
            glyphs_700[name],
            location,
            font_400["glyf"],
        )
        y_min = float(getattr(glyph, "yMin"))
        y_max = float(getattr(glyph, "yMax"))
        for fraction in fractions:
            pen = HorizontalScanPen(None, y_min + fraction * (y_max - y_min))
            getattr(glyph, "draw")(pen, font_400["glyf"])
            widths.extend(
                width * STIX_TWO_SCALE_FACTOR for width in _main_intervals(pen.widths())
            )
    return tuple(widths)


def _fit_location(
    target: float,
    font_400: TTFont,
    glyphs_400: dict[str, object],
    glyphs_700: dict[str, object],
) -> float:
    lower, upper = -1.5, 2.0
    for _ in range(30):
        location = (lower + upper) / 2
        measured = median(_stix_stems(location, font_400, glyphs_400, glyphs_700))
        if measured < target:
            lower = location
        else:
            upper = location
    return round((lower + upper) / 2, 2)


def measure(
    stix_source: Path,
    noto_directory: Path,
    thin_target: ThinTarget = "midpoint",
) -> dict[str, object]:
    raw = TTFont(stix_source, recalcBBoxes=False, recalcTimestamp=False)
    font_400: TTFont | None = None
    font_700: TTFont | None = None
    noto_fonts: list[TTFont] = []
    try:
        font_400, font_700, glyphs_400, glyphs_700 = _raw_endpoints(raw)
        locations: list[float] = []
        measurements: list[dict[str, float | int | str]] = []
        for weight_name, weight_class in NOTO_WEIGHT_CLASSES.items():
            noto = TTFont(noto_directory / f"NotoSerifJP-{weight_name}.otf")
            noto_fonts.append(noto)
            japanese_target = median(_font_stems(noto, JAPANESE_PROBES))
            latin_target = median(_font_stems(noto, LATIN_PROBES))
            target_kind: ThinTarget = (
                thin_target if weight_class < _REGULAR_WEIGHT else "japanese"
            )
            if target_kind == "noto-latin":
                target = latin_target
            elif target_kind == "midpoint":
                target = (japanese_target + latin_target) / 2
            else:
                target = japanese_target
            location = _fit_location(target, font_400, glyphs_400, glyphs_700)
            actual = median(_stix_stems(location, font_400, glyphs_400, glyphs_700))
            locations.append(location)
            measurements.append(
                {
                    "weight": weight_class,
                    "target": target_kind,
                    "noto_stem": round(target, 2),
                    "stix_stem": round(actual, 2),
                }
            )
        return {
            "metric": "japanese-latin-main-vertical-stem",
            "thin_target": thin_target,
            "latin_probes": LATIN_PROBES,
            "japanese_probes": JAPANESE_PROBES,
            "weights": list(NOTO_WEIGHT_CLASSES.values()),
            "global_locations": locations,
            "measurements": measurements,
        }
    finally:
        for font in noto_fonts:
            font.close()
        if font_400 is not None:
            font_400.close()
        if font_700 is not None:
            font_700.close()
        raw.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Japanese, midpoint, or Noto-Latin STIX locations"
    )
    parser.add_argument(
        "--stix-source",
        type=Path,
        default=Path(".cache/font-sources/STIXTwoText[wght].ttf"),
    )
    parser.add_argument(
        "--noto-directory",
        type=Path,
        default=Path(".cache/font-sources"),
    )
    parser.add_argument(
        "--thin-target",
        choices=("japanese", "midpoint", "noto-latin"),
        default="midpoint",
        help="stem target for ExtraLight and Light",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            measure(args.stix_source, args.noto_directory, args.thin_target),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
