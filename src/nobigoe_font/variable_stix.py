"""Build Noto-matched STIX Two Text Latin variable-font sources."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path

from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    SourceDescriptor,
)
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib import build as varlib_build
from fontTools.varLib.instancer import instantiateVariableFont

from .metadata import set_japanese_name, set_name
from .profiles import (
    NOTO_WEIGHT_CLASSES,
    NOTO_WEIGHT_DESIGN_LOCATIONS,
    STIX_TWO_SCALE_FACTOR,
)

STIX_LATIN_DESIGN_FAMILY = "Nobigoe STIX Latin Design"
_STIX_LATIN_DESIGN_POSTSCRIPT = "NobigoeSTIXLatinDesignVF"
_SOURCE_MIN_WEIGHT = 400
_SOURCE_MAX_WEIGHT = 700
_SUPPORTED_WEIGHTS = tuple(NOTO_WEIGHT_CLASSES.values())
_WEIGHT_NAMES = {value: name for name, value in NOTO_WEIGHT_CLASSES.items()}
_TUNING_PATH = Path(__file__).with_name("stix_latin_tuning.json")
_TUNING_VERSION = 6
_TUNING_METRIC = "japanese-latin-main-vertical-stem"


@dataclass(frozen=True)
class StixLatinBuildResult:
    """Summary of one rebuilt STIX Latin design variable font."""

    source: Path
    output: Path
    tuned_glyph_count: int
    named_instance_weights: tuple[int, ...]


@dataclass(frozen=True)
class _TuningProfile:
    weights: tuple[int, ...]
    global_locations: tuple[float, ...]
    glyph_locations: dict[str, tuple[float, ...]]


@cache
def _tuning_profile() -> _TuningProfile:
    data = json.loads(_TUNING_PATH.read_text(encoding="utf-8"))
    if data.get("version") != _TUNING_VERSION:
        raise ValueError(f"Unsupported STIX tuning profile version in {_TUNING_PATH}")
    if data.get("metric", {}).get("name") != _TUNING_METRIC:
        raise ValueError(f"Unsupported STIX tuning metric in {_TUNING_PATH}")
    weights = tuple(int(value) for value in data["weights"])
    if weights != _SUPPORTED_WEIGHTS:
        raise ValueError(
            f"STIX tuning weights {weights!r} do not match {_SUPPORTED_WEIGHTS!r}"
        )
    if float(data["scale_factor"]) != STIX_TWO_SCALE_FACTOR:
        raise ValueError("STIX tuning profile and Latin scale factor disagree")
    global_locations = tuple(float(value) for value in data["global_locations"])
    if len(global_locations) != len(weights):
        raise ValueError("STIX global tuning locations do not cover every weight")
    glyph_locations = {
        str(name): tuple(float(value) for value in locations)
        for name, locations in data["glyph_locations"].items()
    }
    invalid = [
        name
        for name, locations in glyph_locations.items()
        if len(locations) != len(weights)
    ]
    if invalid:
        raise ValueError(f"STIX glyph tuning locations are incomplete: {invalid[:5]!r}")
    return _TuningProfile(weights, global_locations, glyph_locations)


def _weight_index(weight_class: int) -> int:
    try:
        return _SUPPORTED_WEIGHTS.index(weight_class)
    except ValueError as error:
        raise ValueError(
            f"Unsupported STIX Latin weight {weight_class!r}; expected {_SUPPORTED_WEIGHTS!r}"
        ) from error


def _is_variable_glyf(font: TTFont) -> bool:
    return font.sfntVersion == "\x00\x01\x00\x00" and all(
        tag in font for tag in ("glyf", "fvar")
    )


def _weight_axis(font: TTFont):
    if not _is_variable_glyf(font):
        raise ValueError("STIX Latin source must be a variable TrueType glyf font")
    axes = {axis.axisTag: axis for axis in font["fvar"].axes}
    if "wght" not in axes:
        raise ValueError("STIX Latin source has no wght axis")
    return axes["wght"]


def is_variable_stix_design_font(font: TTFont) -> bool:
    """Return whether *font* is a rebuilt Noto-matched STIX Latin VF."""

    if not _is_variable_glyf(font):
        return False
    family_names = {font["name"].getDebugName(name_id) for name_id in (1, 16)}
    return STIX_LATIN_DESIGN_FAMILY in family_names


def _instantiate_static(font: TTFont, weight: float) -> TTFont:
    limits = {
        axis.axisTag: weight if axis.axisTag == "wght" else None
        for axis in font["fvar"].axes
    }
    instance = instantiateVariableFont(
        font, limits, inplace=False, updateFontNames=False, static=True
    )
    instance.recalcBBoxes = instance.recalcTimestamp = False
    return instance


def _validate_raw_source(font: TTFont) -> None:
    axis = _weight_axis(font)
    if axis.minValue > _SOURCE_MIN_WEIGHT or axis.maxValue < _SOURCE_MAX_WEIGHT:
        raise ValueError("Raw STIX Two Text wght axis must cover 400..700")
    if is_variable_stix_design_font(font):
        raise ValueError(
            "Expected raw STIX Two Text, got a rebuilt STIX Latin design VF"
        )


def _topology(glyph: object) -> tuple[object, ...]:
    contours = int(getattr(glyph, "numberOfContours"))
    if contours <= 0:
        return ("empty", contours)
    return (
        "simple",
        contours,
        tuple(getattr(glyph, "endPtsOfContours")),
        tuple(int(flag) & 1 for flag in getattr(glyph, "flags")),
        len(getattr(glyph, "coordinates")),
    )


def _flattened_glyphs(font: TTFont) -> dict[str, object]:
    glyph_set = font.getGlyphSet()
    flattened: dict[str, object] = {}
    for name in font.getGlyphOrder():
        pen = TTGlyphPen(None)
        glyph_set[name].draw(DecomposingFilterPen(pen, glyph_set))
        flattened[name] = pen.glyph()
    return flattened


def _assert_endpoint_compatibility(
    font_400: TTFont,
    font_700: TTFont,
    glyphs_400: dict[str, object],
    glyphs_700: dict[str, object],
) -> None:
    order = font_400.getGlyphOrder()
    if font_700.getGlyphOrder() != order:
        raise ValueError("STIX endpoint glyph orders differ")
    for name in order:
        if _topology(glyphs_400[name]) != _topology(glyphs_700[name]):
            raise ValueError(f"STIX endpoint topology differs for {name!r}")


def _interpolate_glyph(
    glyph_400: object,
    glyph_700: object,
    location: float,
    glyf_table: object,
) -> object:
    glyph = deepcopy(glyph_400)
    if int(getattr(glyph, "numberOfContours")) <= 0:
        return glyph
    coordinates = deepcopy(getattr(glyph_400, "coordinates"))
    coordinates_700 = getattr(glyph_700, "coordinates")
    for index, (point_400, point_700) in enumerate(
        zip(coordinates, coordinates_700, strict=True)
    ):
        coordinates[index] = (
            round(point_400[0] + location * (point_700[0] - point_400[0])),
            round(point_400[1] + location * (point_700[1] - point_400[1])),
        )
    setattr(glyph, "coordinates", coordinates)
    getattr(glyph, "recalcBounds")(glyf_table)
    return glyph


def _substitution_rules(
    font: TTFont,
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    if "GSUB" not in font:
        return ()
    table = font["GSUB"].table
    if table.LookupList is None:
        return ()
    rules: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for lookup in table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            while hasattr(subtable, "ExtSubTable"):
                subtable = subtable.ExtSubTable
            mapping = getattr(subtable, "mapping", None)
            if mapping is not None:
                for source_name, outputs in mapping.items():
                    output_names = (
                        (outputs,) if isinstance(outputs, str) else tuple(outputs)
                    )
                    rules.append(((source_name,), output_names))
            alternates = getattr(subtable, "alternates", None)
            if alternates is not None:
                rules.extend(
                    ((source_name,), tuple(outputs))
                    for source_name, outputs in alternates.items()
                )
            ligatures = getattr(subtable, "ligatures", None)
            if ligatures is not None:
                for first, records in ligatures.items():
                    for record in records:
                        rules.append(((first, *record.Component), (record.LigGlyph,)))
    return tuple(rules)


def _mean_locations(inputs: Iterable[tuple[float, ...]]) -> tuple[float, ...]:
    values = tuple(inputs)
    return tuple(
        sum(locations[index] for locations in values) / len(values)
        for index in range(len(_SUPPORTED_WEIGHTS))
    )


def _glyph_locations(font: TTFont) -> dict[str, tuple[float, ...]]:
    profile = _tuning_profile()
    order = set(font.getGlyphOrder())
    direct = {
        name: locations
        for name, locations in profile.glyph_locations.items()
        if name in order
    }
    resolved = dict(direct)
    rules = _substitution_rules(font)
    changed = True
    while changed:
        changed = False
        candidates: dict[str, list[tuple[float, ...]]] = {}
        for inputs, outputs in rules:
            if not all(name in resolved for name in inputs):
                continue
            locations = _mean_locations(resolved[name] for name in inputs)
            for output in outputs:
                if output in order and output not in direct:
                    candidates.setdefault(output, []).append(locations)
        for output, values in candidates.items():
            combined = _mean_locations(values)
            if output not in resolved:
                resolved[output] = combined
                changed = True
    return {
        name: resolved.get(name, profile.global_locations)
        for name in font.getGlyphOrder()
    }


def _build_master(
    raw_source: TTFont,
    font_400: TTFont,
    font_700: TTFont,
    glyphs_400: dict[str, object],
    glyphs_700: dict[str, object],
    locations: dict[str, tuple[float, ...]],
    weight_class: int,
) -> TTFont:
    weight_index = _weight_index(weight_class)
    global_location = _tuning_profile().global_locations[weight_index]
    source_weight = max(
        _SOURCE_MIN_WEIGHT,
        min(
            _SOURCE_MAX_WEIGHT,
            _SOURCE_MIN_WEIGHT
            + (_SOURCE_MAX_WEIGHT - _SOURCE_MIN_WEIGHT) * global_location,
        ),
    )
    master = _instantiate_static(raw_source, source_weight)
    glyph_order = master.getGlyphOrder()
    new_glyphs: dict[str, object] = {}
    new_metrics: dict[str, tuple[int, int]] = {}
    for name in glyph_order:
        location = locations[name][weight_index]
        glyph = _interpolate_glyph(
            glyphs_400[name], glyphs_700[name], location, master["glyf"]
        )
        new_glyphs[name] = glyph
        advance_400, lsb_400 = font_400["hmtx"].metrics[name]
        advance_700, lsb_700 = font_700["hmtx"].metrics[name]
        advance = round(advance_400 + location * (advance_700 - advance_400))
        if int(getattr(glyph, "numberOfContours")) > 0:
            left_side_bearing = int(getattr(glyph, "xMin"))
        else:
            left_side_bearing = round(lsb_400 + location * (lsb_700 - lsb_400))
        new_metrics[name] = (advance, left_side_bearing)
    master["glyf"].glyphs = new_glyphs
    master["hmtx"].metrics = new_metrics
    setattr(master["OS/2"], "usWeightClass", weight_class)
    master.recalcBBoxes = master.recalcTimestamp = False
    return master


def _raw_endpoints(
    raw_source: TTFont,
) -> tuple[TTFont, TTFont, dict[str, object], dict[str, object]]:
    _validate_raw_source(raw_source)
    font_400 = _instantiate_static(raw_source, _SOURCE_MIN_WEIGHT)
    font_700 = _instantiate_static(raw_source, _SOURCE_MAX_WEIGHT)
    glyphs_400 = _flattened_glyphs(font_400)
    glyphs_700 = _flattened_glyphs(font_700)
    _assert_endpoint_compatibility(font_400, font_700, glyphs_400, glyphs_700)
    return font_400, font_700, glyphs_400, glyphs_700


def instantiate_stix_latin_font(font: TTFont, weight_class: int) -> TTFont:
    """Return one static Noto-matched STIX Latin instance."""

    _ = _weight_index(weight_class)
    if is_variable_stix_design_font(font):
        instance = _instantiate_static(font, weight_class)
        if "fvar" in instance:
            raise ValueError("STIX Latin design instance remained variable")
        return instance
    font_400, font_700, glyphs_400, glyphs_700 = _raw_endpoints(font)
    try:
        locations = _glyph_locations(font_400)
        return _build_master(
            font, font_400, font_700, glyphs_400, glyphs_700, locations, weight_class
        )
    finally:
        font_400.close()
        font_700.close()


def _assert_master_compatibility(masters: tuple[TTFont, ...]) -> None:
    order = masters[0].getGlyphOrder()
    reference = tuple(_topology(masters[0]["glyf"][name]) for name in order)
    for weight, master in zip(_SUPPORTED_WEIGHTS[1:], masters[1:]):
        if master.getGlyphOrder() != order:
            raise ValueError(f"STIX Latin master {weight} has incompatible glyph order")
        candidate = tuple(_topology(master["glyf"][name]) for name in order)
        if candidate != reference:
            mismatch = next(
                name
                for name, expected, actual in zip(order, reference, candidate)
                if expected != actual
            )
            raise ValueError(
                f"STIX Latin master {weight} has incompatible topology for {mismatch!r}"
            )


def _designspace(masters: tuple[TTFont, ...]) -> DesignSpaceDocument:
    document = DesignSpaceDocument()
    axis = AxisDescriptor(
        tag="wght", name="Weight", minimum=200, default=400, maximum=900
    )
    axis.map = list(NOTO_WEIGHT_DESIGN_LOCATIONS.items())
    document.addAxis(axis)
    for weight, master in zip(_SUPPORTED_WEIGHTS, masters, strict=True):
        source = SourceDescriptor(
            name=f"STIXLatin-{weight}",
            styleName=_WEIGHT_NAMES[weight],
            designLocation={axis.name: NOTO_WEIGHT_DESIGN_LOCATIONS[weight]},
            font=master,
        )
        if weight == 400:
            source.copyInfo = source.copyLib = source.copyFeatures = True
        document.addSource(source)
    for weight in _SUPPORTED_WEIGHTS:
        document.addInstance(
            InstanceDescriptor(
                name=f"STIXLatin-{weight}",
                styleName=_WEIGHT_NAMES[weight],
                designLocation={axis.name: NOTO_WEIGHT_DESIGN_LOCATIONS[weight]},
            )
        )
    return document


def _rename_design_font(font: TTFont) -> None:
    for name_id, value in (
        (1, STIX_LATIN_DESIGN_FAMILY),
        (2, "Regular"),
        (3, f"NOBIGOE;{_STIX_LATIN_DESIGN_POSTSCRIPT}"),
        (4, STIX_LATIN_DESIGN_FAMILY),
        (6, _STIX_LATIN_DESIGN_POSTSCRIPT),
        (16, STIX_LATIN_DESIGN_FAMILY),
        (17, "Regular"),
        (25, _STIX_LATIN_DESIGN_POSTSCRIPT),
    ):
        set_name(font, name_id, value)
    for name_id, value in (
        (1, "のびごえSTIX欧文制作VF"),
        (4, "のびごえSTIX欧文制作VF"),
        (16, "のびごえSTIX欧文制作VF"),
        (17, "Regular"),
    ):
        set_japanese_name(font, name_id, value)


def build_variable_stix_source(source: Path, output: Path) -> StixLatinBuildResult:
    """Build the reusable Noto-matched STIX Latin design VF."""

    source, output = Path(source), Path(output)
    raw_source = TTFont(source, recalcBBoxes=False, recalcTimestamp=False)
    font_400: TTFont | None = None
    font_700: TTFont | None = None
    masters: tuple[TTFont, ...] = ()
    try:
        font_400, font_700, glyphs_400, glyphs_700 = _raw_endpoints(raw_source)
        locations = _glyph_locations(font_400)
        masters = tuple(
            _build_master(
                raw_source,
                font_400,
                font_700,
                glyphs_400,
                glyphs_700,
                locations,
                weight,
            )
            for weight in _SUPPORTED_WEIGHTS
        )
        _assert_master_compatibility(masters)
        for master in masters:
            if "BASE" in master:
                del master["BASE"]
        variable, _, _ = varlib_build(_designspace(masters))
        variable.recalcBBoxes = variable.recalcTimestamp = False
        _rename_design_font(variable)
        output.parent.mkdir(parents=True, exist_ok=True)
        variable.save(output, reorderTables=False)
        variable.close()
    finally:
        for master in masters:
            master.close()
        if font_400 is not None:
            font_400.close()
        if font_700 is not None:
            font_700.close()
        raw_source.close()
    return StixLatinBuildResult(
        source, output, len(_tuning_profile().glyph_locations), _SUPPORTED_WEIGHTS
    )


__all__ = (
    "STIX_LATIN_DESIGN_FAMILY",
    "StixLatinBuildResult",
    "build_variable_stix_source",
    "instantiate_stix_latin_font",
    "is_variable_stix_design_font",
)
