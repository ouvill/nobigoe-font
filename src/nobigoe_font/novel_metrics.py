"""Measure reproducible kana outline metrics across fonts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Callable, Mapping, Sequence, TextIO

import pathops
from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTFont, TTLibError

from .geometry import glyph_path as _raw_glyph_path
from .novel import HIRAGANA_CODEPOINTS as NOVEL_HIRAGANA_CODEPOINTS
from .novel_katakana import (
    CURVE_KATAKANA_CODEPOINTS,
    ITERATION_KATAKANA_CODEPOINTS,
    KATAKANA_CODEPOINTS as NOVEL_KATAKANA_CODEPOINTS,
    KATAKANA_SOURCE_CODEPOINTS as NOVEL_KATAKANA_SOURCE_CODEPOINTS,
    SMALL_KATAKANA_CODEPOINTS,
    STRAIGHT_KATAKANA_CODEPOINTS,
)
from .operations import vertical_glyph_or_self

HIRAGANA_CODEPOINTS = tuple(sorted(NOVEL_HIRAGANA_CODEPOINTS))
BASIC_HIRAGANA = tuple(
    ord(character)
    for character in "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "はひふへほまみむめもやゆよらりるれろわをん"
)
REPRESENTATIVE_KANJI = tuple(ord(character) for character in "永漢字山川雨月語本")
COUNTER_HIRAGANA = tuple(ord(character) for character in "あのぬめ")
KATAKANA_CODEPOINTS = tuple(sorted(NOVEL_KATAKANA_SOURCE_CODEPOINTS))
STANDARD_KATAKANA = tuple(
    sorted(STRAIGHT_KATAKANA_CODEPOINTS | CURVE_KATAKANA_CODEPOINTS)
)
SMALL_KATAKANA = tuple(
    sorted(SMALL_KATAKANA_CODEPOINTS & NOVEL_KATAKANA_SOURCE_CODEPOINTS)
)
ITERATION_KATAKANA = tuple(sorted(ITERATION_KATAKANA_CODEPOINTS))
DELIVERED_NOVEL_KATAKANA = tuple(sorted(NOVEL_KATAKANA_CODEPOINTS))
SUMMARY_SECTIONS = (
    "hiragana_89",
    "basic_hiragana_46",
    "representative_kanji_9",
    "katakana_109",
    "standard_katakana_78",
    "small_katakana_28",
    "iteration_katakana_3",
    "novel_katakana_110",
)
COMPARISON_SECTIONS = SUMMARY_SECTIONS[:-1]
SET_SECTIONS = (
    *SUMMARY_SECTIONS[:3],
    "counter_hiragana_4",
    *SUMMARY_SECTIONS[3:],
)
PRECISION = 6
SCHEMA_VERSION = 3
METRIC_NAMES = (
    "bbox_width",
    "bbox_height",
    "bbox_center_x",
    "bbox_center_y",
    "signed_ink_area",
    "bbox_fill",
)


@dataclass(frozen=True)
class GlyphMetrics:
    bbox_width: float
    bbox_height: float
    bbox_center_x: float
    bbox_center_y: float
    signed_ink_area: float
    bbox_fill: float
    counter_area: float


@dataclass(frozen=True)
class FontInput:
    label: str
    path: Path


class FontMeasurementError(ValueError):
    """A font could not be measured."""


def _codepoint(codepoint: int) -> str:
    width = 4 if codepoint <= 0xFFFF else 5
    return f"U+{codepoint:0{width}X}"


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    rounded = round(value, PRECISION)
    return 0.0 if rounded == 0 else rounded


def _glyph_path(font: TTFont, glyph_name: str) -> pathops.Path:
    try:
        outline = _raw_glyph_path(font, glyph_name)
    except Exception as error:
        raise FontMeasurementError(
            f"fontTools could not read outline: {error}"
        ) from error
    if not outline.verbs:
        raise FontMeasurementError("outline is empty")
    try:
        outline.simplify(
            fix_winding=True,
            keep_starting_points=False,
            clockwise=False,
        )
    except (pathops.PathOpsError, ValueError) as error:
        raise FontMeasurementError(
            f"pathops could not simplify outline: {error}"
        ) from error
    if not outline.verbs:
        raise FontMeasurementError(
            "outline has no visible contours after simplification"
        )
    return outline


def _contour_area(contour: pathops.Path) -> float:
    pen = AreaPen(None)
    contour.draw(pen)
    return pen.value


def _glyph_metrics(outline: pathops.Path, units_per_em: int) -> GlyphMetrics:
    x_min, y_min, x_max, y_max = outline.bounds
    width = x_max - x_min
    height = y_max - y_min
    if not all(math.isfinite(value) for value in (x_min, y_min, x_max, y_max)):
        raise FontMeasurementError("outline has non-finite bounds")
    if width <= 0 or height <= 0:
        raise FontMeasurementError(
            f"outline has non-positive visible bounds ({width:g} x {height:g})"
        )

    contour_areas = tuple(_contour_area(contour) for contour in outline.contours)
    signed_area = math.fsum(contour_areas)
    if not math.isfinite(signed_area) or signed_area <= 0:
        raise FontMeasurementError(
            f"outline has invalid signed ink area {signed_area!r} after winding repair"
        )
    counter_area = math.fsum(-area for area in contour_areas if area < 0)
    em = float(units_per_em)
    return GlyphMetrics(
        bbox_width=width / em,
        bbox_height=height / em,
        bbox_center_x=(x_min + x_max) / (2 * em),
        bbox_center_y=(y_min + y_max) / (2 * em),
        signed_ink_area=signed_area / (em * em),
        bbox_fill=signed_area / (width * height),
        counter_area=counter_area / (em * em),
    )


def _coverage(
    expected: Sequence[int],
    measured: Mapping[int, GlyphMetrics],
    missing: set[int],
    outline_errors: Mapping[int, str],
) -> dict[str, object]:
    expected_set = set(expected)
    measured_count = sum(codepoint in measured for codepoint in expected)
    relevant_missing = sorted(expected_set & missing)
    relevant_errors = {
        _codepoint(codepoint): outline_errors[codepoint]
        for codepoint in sorted(expected_set & outline_errors.keys())
    }
    return {
        "expected": len(expected),
        "measured": measured_count,
        "coverage_fraction": _round(measured_count / len(expected)),
        "missing_codepoints": [_codepoint(codepoint) for codepoint in relevant_missing],
        "outline_errors": relevant_errors,
    }


def _statistic(
    metrics: Sequence[GlyphMetrics],
    kanji_metrics: Sequence[GlyphMetrics],
    aggregate: Callable[[Sequence[float]], float],
) -> dict[str, float | None]:
    def value(attribute: str, values: Sequence[GlyphMetrics]) -> float | None:
        if not values:
            return None
        return _round(aggregate([getattr(item, attribute) for item in values]))

    kana_ink = value("signed_ink_area", metrics)
    kanji_ink = value("signed_ink_area", kanji_metrics)
    ratio = (
        None
        if kana_ink is None or kanji_ink is None or kanji_ink == 0
        else _round(kana_ink / kanji_ink)
    )
    result = {name: value(name, metrics) for name in METRIC_NAMES}
    result["kana_to_representative_kanji_ink_ratio"] = ratio
    return result


def _summary(
    codepoints: Sequence[int],
    measured: Mapping[int, GlyphMetrics],
    kanji_metrics: Sequence[GlyphMetrics],
) -> dict[str, object]:
    metrics = [measured[codepoint] for codepoint in codepoints if codepoint in measured]
    return {
        "count": len(metrics),
        "mean": _statistic(metrics, kanji_metrics, statistics.fmean),
        "median": _statistic(metrics, kanji_metrics, statistics.median),
    }


def _measure_font(
    font_input: FontInput, *, vertical: bool = False
) -> dict[str, object]:
    try:
        font = TTFont(font_input.path, lazy=False)
    except (OSError, TTLibError) as error:
        raise FontMeasurementError(
            f"{font_input.label}={font_input.path}: cannot open font: {error}"
        ) from error

    try:
        if "head" not in font:
            raise FontMeasurementError(
                f"{font_input.label}={font_input.path}: font has no head table"
            )
        units_per_em = int(font["head"].unitsPerEm)
        if units_per_em <= 0:
            raise FontMeasurementError(
                f"{font_input.label}={font_input.path}: invalid unitsPerEm {units_per_em}"
            )
        cmap = font.getBestCmap() or {}
        requested = (
            set(HIRAGANA_CODEPOINTS)
            | set(REPRESENTATIVE_KANJI)
            | set(DELIVERED_NOVEL_KATAKANA)
        )
        missing = {codepoint for codepoint in requested if codepoint not in cmap}
        outline_errors: dict[int, str] = {}
        measured: dict[int, GlyphMetrics] = {}
        for codepoint in sorted(requested - missing):
            glyph_name = cmap[codepoint]
            if vertical:
                glyph_name = vertical_glyph_or_self(font, glyph_name)
            try:
                measured[codepoint] = _glyph_metrics(
                    _glyph_path(font, glyph_name), units_per_em
                )
            except Exception as error:
                outline_errors[codepoint] = (
                    f"glyph {glyph_name!r} could not be measured: {error}"
                )
    finally:
        font.close()

    kanji_metrics = [
        measured[codepoint]
        for codepoint in REPRESENTATIVE_KANJI
        if codepoint in measured
    ]
    return {
        "label": font_input.label,
        "path": str(font_input.path),
        "units_per_em": units_per_em,
        "coverage": {
            "hiragana_89": _coverage(
                HIRAGANA_CODEPOINTS, measured, missing, outline_errors
            ),
            "basic_hiragana_46": _coverage(
                BASIC_HIRAGANA, measured, missing, outline_errors
            ),
            "representative_kanji_9": _coverage(
                REPRESENTATIVE_KANJI, measured, missing, outline_errors
            ),
            "katakana_109": _coverage(
                KATAKANA_CODEPOINTS, measured, missing, outline_errors
            ),
            "standard_katakana_78": _coverage(
                STANDARD_KATAKANA, measured, missing, outline_errors
            ),
            "small_katakana_28": _coverage(
                SMALL_KATAKANA, measured, missing, outline_errors
            ),
            "iteration_katakana_3": _coverage(
                ITERATION_KATAKANA, measured, missing, outline_errors
            ),
            "novel_katakana_110": _coverage(
                DELIVERED_NOVEL_KATAKANA, measured, missing, outline_errors
            ),
        },
        "hiragana_89": _summary(HIRAGANA_CODEPOINTS, measured, kanji_metrics),
        "basic_hiragana_46": _summary(BASIC_HIRAGANA, measured, kanji_metrics),
        "representative_kanji_9": _summary(
            REPRESENTATIVE_KANJI, measured, kanji_metrics
        ),
        "katakana_109": _summary(KATAKANA_CODEPOINTS, measured, kanji_metrics),
        "standard_katakana_78": _summary(STANDARD_KATAKANA, measured, kanji_metrics),
        "small_katakana_28": _summary(SMALL_KATAKANA, measured, kanji_metrics),
        "iteration_katakana_3": _summary(ITERATION_KATAKANA, measured, kanji_metrics),
        "novel_katakana_110": _summary(
            DELIVERED_NOVEL_KATAKANA, measured, kanji_metrics
        ),
        "counter_areas": {
            _codepoint(codepoint): (
                _round(measured[codepoint].counter_area)
                if codepoint in measured
                else None
            )
            for codepoint in COUNTER_HIRAGANA
        },
    }


def _ratio_or_delta(
    left: Mapping[str, float | None], right: Mapping[str, float | None]
) -> dict[str, float | None]:
    comparison: dict[str, float | None] = {}
    for key in ("bbox_width", "bbox_height", "signed_ink_area", "bbox_fill"):
        numerator = left[key]
        denominator = right[key]
        comparison[f"{key}_ratio"] = (
            None
            if numerator is None or denominator in (None, 0)
            else _round(numerator / denominator)
        )
    for key in ("bbox_center_x", "bbox_center_y"):
        left_value = left[key]
        right_value = right[key]
        comparison[f"{key}_delta"] = (
            None
            if left_value is None or right_value is None
            else _round(left_value - right_value)
        )
    return comparison


def _comparisons(fonts: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    comparisons: list[dict[str, object]] = []
    for left_index, left in enumerate(fonts):
        for right in fonts[left_index + 1 :]:
            item: dict[str, object] = {
                "numerator": left["label"],
                "denominator": right["label"],
            }
            for section in COMPARISON_SECTIONS:
                left_section = left[section]
                right_section = right[section]
                item[section] = {
                    statistic: _ratio_or_delta(
                        left_section[statistic], right_section[statistic]
                    )
                    for statistic in ("mean", "median")
                }
            comparisons.append(item)
    return comparisons


def _set_schema() -> dict[str, list[str]]:
    return {
        "hiragana_89": [_codepoint(codepoint) for codepoint in HIRAGANA_CODEPOINTS],
        "basic_hiragana_46": [_codepoint(codepoint) for codepoint in BASIC_HIRAGANA],
        "representative_kanji_9": [
            _codepoint(codepoint) for codepoint in REPRESENTATIVE_KANJI
        ],
        "katakana_109": [_codepoint(codepoint) for codepoint in KATAKANA_CODEPOINTS],
        "standard_katakana_78": [
            _codepoint(codepoint) for codepoint in STANDARD_KATAKANA
        ],
        "small_katakana_28": [_codepoint(codepoint) for codepoint in SMALL_KATAKANA],
        "iteration_katakana_3": [
            _codepoint(codepoint) for codepoint in ITERATION_KATAKANA
        ],
        "novel_katakana_110": [
            _codepoint(codepoint) for codepoint in DELIVERED_NOVEL_KATAKANA
        ],
        "counter_hiragana_4": [_codepoint(codepoint) for codepoint in COUNTER_HIRAGANA],
    }


def measure(
    font_inputs: Sequence[FontInput], *, vertical: bool = False
) -> dict[str, object]:
    """Measure horizontal or substituted vertical outlines in a stable schema."""
    fonts = [_measure_font(font_input, vertical=vertical) for font_input in font_inputs]
    return {
        "schema_version": SCHEMA_VERSION,
        "orientation": "vertical" if vertical else "horizontal",
        "numeric_precision": PRECISION,
        "sets": _set_schema(),
        "fonts": fonts,
        "comparisons": _comparisons(fonts),
    }


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{PRECISION}f}"
    return str(value)


def _format_set(codepoints: Sequence[str]) -> str:
    return " ".join(
        f"{codepoint}({chr(int(codepoint[2:], 16))})" for codepoint in codepoints
    )


def _write_summary(name: str, summary: Mapping[str, object], output: TextIO) -> None:
    print(f"  {name}: count={summary['count']}", file=output)
    for statistic in ("mean", "median"):
        values = summary[statistic]
        rendered = " ".join(
            f"{key}={_format_value(value)}" for key, value in values.items()
        )
        print(f"    {statistic}: {rendered}", file=output)


def write_text(report: Mapping[str, object], output: TextIO) -> None:
    """Write a deterministic human-readable rendering of a report."""
    print(f"orientation: {report['orientation']}", file=output)
    sets = report["sets"]
    for name in SET_SECTIONS:
        print(f"set {name}: {_format_set(sets[name])}", file=output)

    for font in report["fonts"]:
        print(f"\n[{font['label']}] {font['path']}", file=output)
        print(f"  units_per_em: {font['units_per_em']}", file=output)
        for name, coverage in font["coverage"].items():
            print(
                f"  coverage {name}: {coverage['measured']}/{coverage['expected']} "
                f"({_format_value(coverage['coverage_fraction'])})",
                file=output,
            )
            if coverage["missing_codepoints"]:
                print(
                    "    missing: " + " ".join(coverage["missing_codepoints"]),
                    file=output,
                )
            for codepoint, error in coverage["outline_errors"].items():
                print(f"    outline error {codepoint}: {error}", file=output)
        _write_summary("hiragana_89", font["hiragana_89"], output)
        _write_summary("basic_hiragana_46", font["basic_hiragana_46"], output)
        _write_summary("representative_kanji_9", font["representative_kanji_9"], output)
        counters = " ".join(
            f"{codepoint}={_format_value(value)}"
            for codepoint, value in font["counter_areas"].items()
        )
        print(f"  counter_areas: {counters}", file=output)
        _write_summary("katakana_109", font["katakana_109"], output)
        _write_summary("standard_katakana_78", font["standard_katakana_78"], output)
        _write_summary("small_katakana_28", font["small_katakana_28"], output)
        _write_summary("iteration_katakana_3", font["iteration_katakana_3"], output)
        _write_summary("novel_katakana_110", font["novel_katakana_110"], output)

    for comparison in report["comparisons"]:
        print(
            f"\n[comparison {comparison['numerator']}/{comparison['denominator']}]",
            file=output,
        )
        for section in COMPARISON_SECTIONS:
            for statistic in ("mean", "median"):
                values = comparison[section][statistic]
                rendered = " ".join(
                    f"{key}={_format_value(value)}" for key, value in values.items()
                )
                print(f"  {section} {statistic}: {rendered}", file=output)


def _parse_font_input(value: str) -> FontInput:
    label, separator, path_value = value.partition("=")
    if not separator or not label or not path_value:
        raise argparse.ArgumentTypeError(f"{value!r} must use the form label=path")
    path = Path(path_value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(
            f"{value!r} points to a missing or non-file path: {path}"
        )
    return FontInput(label=label, path=path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare normalized visible-outline metrics for the contracted "
            "kana and representative Han codepoints."
        )
    )
    parser.add_argument(
        "fonts",
        metavar="LABEL=PATH",
        type=_parse_font_input,
        nargs="+",
        help="labeled OpenType font to measure; repeat for comparisons",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the stable machine-readable JSON schema instead of text",
    )
    parser.add_argument(
        "--vertical",
        action="store_true",
        help="measure glyphs selected by the vert/vrt2 substitution instead",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write output to this path instead of stdout",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "fail if any contracted source kana or representative kanji is "
            "missing or unreadable"
        ),
    )
    args = parser.parse_args(argv)
    labels = [font.label for font in args.fonts]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        parser.error("duplicate font labels: " + ", ".join(duplicates))
    return args


def _strict_failures(report: Mapping[str, object]) -> list[str]:
    failures: list[str] = []
    for font in report["fonts"]:
        for set_name in (
            "hiragana_89",
            "representative_kanji_9",
            "katakana_109",
        ):
            coverage = font["coverage"][set_name]
            missing = coverage["missing_codepoints"]
            errors = coverage["outline_errors"]
            if missing or errors:
                details: list[str] = []
                if missing:
                    details.append("missing " + ", ".join(missing))
                if errors:
                    details.append("outline errors " + ", ".join(errors))
                failures.append(f"{font['label']} {set_name}: " + "; ".join(details))
    return failures


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        report = measure(args.fonts, vertical=args.vertical)
    except FontMeasurementError as error:
        raise SystemExit(f"nobigoe-measure-kana: error: {error}") from error

    output: TextIO
    should_close = args.output is not None
    if should_close:
        try:
            output = args.output.open("w", encoding="utf-8", newline="\n")
        except OSError as error:
            raise SystemExit(
                f"nobigoe-measure-kana: error: cannot write {args.output}: {error}"
            ) from error
    else:
        output = sys.stdout
    try:
        if args.json:
            json.dump(
                report,
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            output.write("\n")
        else:
            write_text(report, output)
    finally:
        if should_close:
            output.close()

    if args.strict:
        failures = _strict_failures(report)
        if failures:
            print(
                "nobigoe-measure-kana: strict coverage failed:\n  "
                + "\n  ".join(failures),
                file=sys.stderr,
            )
            raise SystemExit(1)


if __name__ == "__main__":
    main()
