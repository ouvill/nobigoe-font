"""Topology-compatible Novel kana masters derived from Noto Serif JP VF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument
from fontTools.designspaceLib import InstanceDescriptor, SourceDescriptor
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont
from fontTools.varLib import build as varlib_build
from fontTools.varLib.instancer import instantiateVariableFont

from .kana_terminals import (
    GlyfTerminalResult,
    TerminalCandidateId,
    TerminalInventory,
    inventory_glyf_terminals,
    taper_glyf_terminals,
)
from .novel import (
    HIRAGANA_CODEPOINTS,
    NOVEL_KA_CODEPOINT,
    _HORIZONTAL_ANCHORS,
    _VERTICAL_ANCHORS,
    _ka_terminal_deformation,
    novel_base_codepoint,
    novel_group_for_codepoint,
    novel_ka_terminal_raise,
    novel_transform,
    novel_vertical_transform,
)
from .novel_katakana import KATAKANA_HORIZONTAL_ANCHORS, KATAKANA_SOURCE_CODEPOINTS
from .novel_katakana import KATAKANA_VERTICAL_ANCHORS, katakana_transform
from .novel_katakana import (
    katakana_vertical_transform,
    novel_katakana_group_for_codepoint,
)
from .operations import feature_single_substitutions
from .metadata import set_japanese_name, set_name
from .profiles import NOTO_WEIGHT_CLASSES, NOTO_WEIGHT_DESIGN_LOCATIONS
from .terminal_plans import terminal_depth_ratio

VARIABLE_KANA_MASTER_WEIGHTS = (200, 400, 900)
_SUPPORTED_WEIGHTS = tuple(NOTO_WEIGHT_CLASSES.values())
_WEIGHT_NAMES = {value: name for name, value in NOTO_WEIGHT_CLASSES.items()}
VARIABLE_KANA_DESIGN_FAMILY = "Nobigoe Novel Kana Design"
_VARIABLE_KANA_DESIGN_POSTSCRIPT = "NobigoeNovelKanaDesignVF"
KanaScript: TypeAlias = Literal["hiragana", "katakana"]
KanaOrientation: TypeAlias = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class VariableKanaTerminalRecord:
    weight_class: int
    glyph_name: str
    codepoint: int
    script: KanaScript
    orientation: KanaOrientation
    inventory: TerminalInventory
    adjusted_count: int
    rejected_count: int
    unresolved_count: int


@dataclass(frozen=True)
class VariableKanaResult:
    weight_class: int
    encoded_hiragana_count: int
    encoded_katakana_count: int
    horizontal_glyph_count: int
    vertical_glyph_count: int
    adjusted_terminal_count: int
    rejected_terminal_count: int
    unresolved_terminal_count: int
    terminal_inventory: tuple[VariableKanaTerminalRecord, ...]


@dataclass(frozen=True)
class VariableKanaBuildResult:
    source: Path
    output: Path
    master_results: tuple[VariableKanaResult, ...]
    named_instance_weights: tuple[int, ...]

    def _coverage(self, field: str) -> int:
        values = {getattr(result, field) for result in self.master_results}
        if len(values) != 1:
            raise ValueError(
                f"Variable kana masters disagree on {field}: {sorted(values)!r}"
            )
        return next(iter(values))

    @property
    def encoded_hiragana_count(self) -> int:
        return self._coverage("encoded_hiragana_count")

    @property
    def encoded_katakana_count(self) -> int:
        return self._coverage("encoded_katakana_count")

    @property
    def adjusted_terminal_count(self) -> int:
        return sum(x.adjusted_terminal_count for x in self.master_results)

    @property
    def unresolved_terminal_count(self) -> int:
        return sum(x.unresolved_terminal_count for x in self.master_results)

    @property
    def terminal_inventory(self) -> tuple[VariableKanaTerminalRecord, ...]:
        return tuple(
            x for result in self.master_results for x in result.terminal_inventory
        )


@dataclass(frozen=True)
class _OwnedGlyph:
    name: str
    codepoint: int
    script: KanaScript
    orientation: KanaOrientation
    group: str


def _load_variable(source: Path) -> TTFont:
    font = TTFont(Path(source), recalcBBoxes=False, recalcTimestamp=False)
    if (
        font.sfntVersion != "\x00\x01\x00\x00"
        or "glyf" not in font
        or "fvar" not in font
    ):
        font.close()
        raise ValueError(f"Expected a variable TrueType glyf source: {source}")
    axes = {axis.axisTag: axis for axis in font["fvar"].axes}
    if "wght" not in axes or axes["wght"].minValue > 200 or axes["wght"].maxValue < 900:
        font.close()
        raise ValueError(f"Source wght axis does not cover 200..900: {source}")
    return font


def _instantiate(source: Path, weight: int) -> TTFont:
    variable = _load_variable(source)
    try:
        limits = {
            axis.axisTag: weight if axis.axisTag == "wght" else None
            for axis in variable["fvar"].axes
        }
        font = instantiateVariableFont(
            variable, limits, inplace=False, updateFontNames=False, static=True
        )
    finally:
        variable.close()
    font.recalcBBoxes = font.recalcTimestamp = False
    return font


def instantiate_variable_kana_source(source: Path, weight_class: int) -> TTFont:
    """Instantiate one authored master from the pinned Noto variable TTF."""
    if weight_class not in VARIABLE_KANA_MASTER_WEIGHTS:
        raise ValueError(
            f"Variable kana masters are {VARIABLE_KANA_MASTER_WEIGHTS!r}, got {weight_class!r}"
        )
    return _instantiate(Path(source), weight_class)


def _collect(font: TTFont) -> tuple[int, int, tuple[_OwnedGlyph, ...]]:
    cmap = font.getBestCmap() or {}
    vertical: dict[str, str] = {}
    if "GSUB" in font:
        vertical.update(feature_single_substitutions(font, "vert"))
        vertical.update(feature_single_substitutions(font, "vrt2"))
    owned: dict[str, _OwnedGlyph] = {}
    counts = [0, 0]
    scripts = (
        ("hiragana", HIRAGANA_CODEPOINTS, novel_group_for_codepoint),
        ("katakana", KATAKANA_SOURCE_CODEPOINTS, novel_katakana_group_for_codepoint),
    )
    for script_index, (script, codepoints, classify) in enumerate(scripts):
        for codepoint in sorted(codepoints):
            name = cmap.get(codepoint)
            if name is None:
                continue
            counts[script_index] += 1
            group = classify(codepoint)
            candidates = [(name, "horizontal")]
            if vertical.get(name) not in {None, name}:
                candidates.append((vertical[name], "vertical"))
            for glyph_name, orientation in candidates:
                item = _OwnedGlyph(glyph_name, codepoint, script, orientation, group)  # type: ignore[arg-type]
                previous = owned.get(glyph_name)
                if previous is None:
                    owned[glyph_name] = item
                elif previous.script != script or previous.group != group:
                    raise ValueError(
                        f"Conflicting Unicode ownership for {glyph_name!r}"
                    )
                elif orientation == "horizontal":
                    owned[glyph_name] = item
    missing = sorted(set(owned).difference(font.getGlyphOrder()))
    if missing:
        raise ValueError(f"Unicode/layout-owned kana glyphs are missing: {missing!r}")
    return counts[0], counts[1], tuple(owned[name] for name in sorted(owned))


def _profile_transform(profile: object, anchor: tuple[float, float]) -> Transform:
    sx, sy = float(getattr(profile, "sx")), float(getattr(profile, "sy"))
    dx, dy = float(getattr(profile, "dx")), float(getattr(profile, "dy"))
    x, y = anchor
    return Transform(sx, 0, 0, sy, x + dx - sx * x, y + dy - sy * y)


def _transform_for(item: _OwnedGlyph, weight: int) -> Transform:
    if item.script == "hiragana":
        horizontal = _profile_transform(novel_transform(weight, item.group), _HORIZONTAL_ANCHORS[item.group])  # type: ignore[arg-type,index]
        if item.orientation == "horizontal":
            return horizontal
        vertical = _profile_transform(novel_vertical_transform(weight, item.group, item.codepoint), _VERTICAL_ANCHORS[item.group])  # type: ignore[arg-type,index]
    else:
        horizontal = _profile_transform(katakana_transform(weight, item.group), KATAKANA_HORIZONTAL_ANCHORS[item.group])  # type: ignore[arg-type,index]
        if item.orientation == "horizontal":
            return horizontal
        vertical = _profile_transform(katakana_vertical_transform(weight, item.group, item.codepoint), KATAKANA_VERTICAL_ANCHORS[item.group])  # type: ignore[arg-type,index]
    return vertical.transform(horizontal)


def _topology(glyph: object) -> tuple[object, ...]:
    contours = int(getattr(glyph, "numberOfContours"))
    if contours < 0:
        return (
            "composite",
            tuple(
                (x.glyphName, hasattr(x, "firstPt"))
                for x in getattr(glyph, "components")
            ),
        )
    if contours == 0:
        return ("empty",)
    return (
        "simple",
        contours,
        tuple(getattr(glyph, "endPtsOfContours")),
        tuple(int(flag) & 1 for flag in getattr(glyph, "flags")),
        len(getattr(glyph, "coordinates")),
    )


def _transform_glyph(font: TTFont, name: str, transform: Transform) -> None:
    glyf, glyph = font["glyf"], font["glyf"][name]
    before = _topology(glyph)
    if glyph.isComposite():
        for component in glyph.components:
            if hasattr(component, "firstPt"):
                raise ValueError(
                    f"Cannot transform point-attached component in {name!r}"
                )
            new = transform.transform(Transform(*component.getComponentInfo()[1]))
            component.x, component.y = new.dx, new.dy
            component.transform = [[new.xx, new.xy], [new.yx, new.yy]]
    else:
        glyph.coordinates.transform(
            ((transform.xx, transform.xy), (transform.yx, transform.yy))
        )
        glyph.coordinates.translate((transform.dx, transform.dy))
        glyph.coordinates.toInt()
    glyph.recalcBounds(glyf)
    if _topology(glyph) != before:
        raise ValueError(f"Affine transform changed topology for {name!r}")


def _shorten_ka_glyph(font: TTFont, name: str, amount: float) -> None:
    """Shorten a ka terminal by moving existing TrueType points only."""
    glyf, glyph = font["glyf"], font["glyf"][name]
    before = _topology(glyph)
    if glyph.isComposite() or glyph.numberOfContours <= 0:
        raise ValueError(f"Variable novel ka glyph {name!r} must be a simple outline")

    contours: list[tuple[tuple[float, float], ...]] = []
    contour_indices: list[tuple[int, ...]] = []
    start = 0
    for raw_end in glyph.endPtsOfContours:
        end = int(raw_end)
        indices = tuple(range(start, end + 1))
        contour_indices.append(indices)
        contours.append(
            tuple(
                (
                    float(glyph.coordinates[index][0]),
                    float(glyph.coordinates[index][1]),
                )
                for index in indices
            )
        )
        start = end + 1
    if start != len(glyph.coordinates):
        raise ValueError(f"Variable novel ka glyph {name!r} has invalid contour ends")

    try:
        deformation = _ka_terminal_deformation(tuple(contours), amount)
    except ValueError as error:
        raise ValueError(
            f"Could not correct variable novel ka terminal glyph {name!r}"
        ) from error

    for contour_index, (indices, points) in enumerate(
        zip(contour_indices, contours, strict=True)
    ):
        for local_index, (point_index, point) in enumerate(
            zip(indices, points, strict=True)
        ):
            strength = (
                deformation.strengths.get(local_index, 0)
                if contour_index == deformation.contour_index
                else deformation.companion_strength(point)
            )
            if not strength:
                continue
            glyph.coordinates[point_index] = (
                round(point[0] + deformation.translation[0] * strength),
                round(point[1] + deformation.translation[1] * strength),
            )

    glyph.recalcBounds(glyf)
    if _topology(glyph) != before:
        raise ValueError(f"Novel ka terminal adjustment changed topology for {name!r}")


def _transform_owned_glyph(font: TTFont, item: _OwnedGlyph, weight: int) -> None:
    _transform_glyph(font, item.name, _transform_for(item, weight))
    if (
        item.script == "hiragana"
        and novel_base_codepoint(item.codepoint) == NOVEL_KA_CODEPOINT
    ):
        _shorten_ka_glyph(font, item.name, novel_ka_terminal_raise(weight))


def _apply_design(
    font: TTFont,
    weight: int,
    counts_and_items: tuple[int, int, tuple[_OwnedGlyph, ...]],
    selected: dict[str, frozenset[TerminalCandidateId]] | None = None,
) -> VariableKanaResult:
    hiragana_count, katakana_count, items = counts_and_items
    records: list[VariableKanaTerminalRecord] = []
    for item in items:
        before = _topology(font["glyf"][item.name])
        candidate_ids = selected.get(item.name) if selected is not None else None
        outcome: GlyfTerminalResult = taper_glyf_terminals(
            font["glyf"][item.name],
            candidate_ids,
            taper_depth_ratio=terminal_depth_ratio(
                item.script,
                item.codepoint,
                item.orientation,
                weight,
            ),
        )
        if _topology(outcome.glyph) != before:
            raise ValueError(f"Terminal adjustment changed topology for {item.name!r}")
        font["glyf"][item.name] = outcome.glyph
        outcome.glyph.recalcBounds(font["glyf"])
        records.append(
            VariableKanaTerminalRecord(
                weight,
                item.name,
                item.codepoint,
                item.script,
                item.orientation,
                outcome.inventory,
                outcome.adjusted_count,
                outcome.rejected_count,
                outcome.unresolved_count,
            )
        )
    return VariableKanaResult(
        weight,
        hiragana_count,
        katakana_count,
        sum(x.orientation == "horizontal" for x in items),
        sum(x.orientation == "vertical" for x in items),
        sum(x.adjusted_count for x in records),
        sum(x.rejected_count for x in records),
        sum(x.unresolved_count for x in records),
        tuple(records),
    )


def apply_variable_kana_design(font: TTFont, weight_class: int) -> VariableKanaResult:
    """Apply compatible Novel affine profiles and terminal adjustment in place."""
    if weight_class not in VARIABLE_KANA_MASTER_WEIGHTS or "glyf" not in font:
        raise ValueError(
            "Variable kana design requires a glyf master at 200, 400, or 900"
        )
    counts_and_items = _collect(font)
    metrics = {
        x.name: (
            font["hmtx"].metrics[x.name],
            font["vmtx"].metrics.get(x.name) if "vmtx" in font else None,
        )
        for x in counts_and_items[2]
    }
    for item in counts_and_items[2]:
        _transform_owned_glyph(font, item, weight_class)
    result = _apply_design(font, weight_class, counts_and_items)
    for name, metric in metrics.items():
        if font["hmtx"].metrics[name] != metric[0] or (
            "vmtx" in font and font["vmtx"].metrics.get(name) != metric[1]
        ):
            raise ValueError(
                f"Full-width or vertical-origin metrics changed for {name!r}"
            )
    return result


def _assert_compatible(masters: tuple[TTFont, ...]) -> None:
    order = masters[0].getGlyphOrder()
    reference = tuple(_topology(masters[0]["glyf"][name]) for name in order)
    for weight, master in zip(VARIABLE_KANA_MASTER_WEIGHTS[1:], masters[1:]):
        if master.getGlyphOrder() != order:
            raise ValueError(f"Master {weight} has incompatible glyph order")
        candidate = tuple(_topology(master["glyf"][name]) for name in order)
        if candidate != reference:
            mismatch = next(
                name for name, a, b in zip(order, reference, candidate) if a != b
            )
            raise ValueError(
                f"Master {weight} has incompatible topology for {mismatch!r}"
            )


def _designspace(masters: tuple[TTFont, ...]) -> DesignSpaceDocument:
    document = DesignSpaceDocument()
    axis = AxisDescriptor(
        tag="wght", name="Weight", minimum=200, default=400, maximum=900
    )
    axis.map = list(NOTO_WEIGHT_DESIGN_LOCATIONS.items())
    document.addAxis(axis)
    for weight, font in zip(VARIABLE_KANA_MASTER_WEIGHTS, masters):
        source = SourceDescriptor(
            name=f"NovelKana-{weight}",
            styleName=_WEIGHT_NAMES[weight],
            designLocation={axis.name: NOTO_WEIGHT_DESIGN_LOCATIONS[weight]},
            font=font,
        )
        if weight == 400:
            source.copyInfo = source.copyLib = source.copyFeatures = True
        document.addSource(source)
    for weight in _SUPPORTED_WEIGHTS:
        document.addInstance(
            InstanceDescriptor(
                name=f"NovelKana-{weight}",
                styleName=_WEIGHT_NAMES[weight],
                designLocation={axis.name: NOTO_WEIGHT_DESIGN_LOCATIONS[weight]},
            )
        )
    return document


def _rename_design_font(font: TTFont) -> None:
    """Mark the intermediate VF so static builds can reuse it directly."""

    for name_id, value in (
        (1, VARIABLE_KANA_DESIGN_FAMILY),
        (2, "Regular"),
        (3, f"NOBIGOE;{_VARIABLE_KANA_DESIGN_POSTSCRIPT}"),
        (4, VARIABLE_KANA_DESIGN_FAMILY),
        (6, _VARIABLE_KANA_DESIGN_POSTSCRIPT),
        (16, VARIABLE_KANA_DESIGN_FAMILY),
        (17, "Regular"),
        (25, _VARIABLE_KANA_DESIGN_POSTSCRIPT),
    ):
        set_name(font, name_id, value)
    for name_id, value in (
        (1, "のびごえ小説かな制作VF"),
        (4, "のびごえ小説かな制作VF"),
        (16, "のびごえ小説かな制作VF"),
        (17, "Regular"),
    ):
        set_japanese_name(font, name_id, value)


def is_variable_kana_design_source(source: Path) -> bool:
    """Return whether ``source`` is a rebuilt Novel kana design VF."""

    font = TTFont(source, lazy=True)
    try:
        family_names = {font["name"].getDebugName(name_id) for name_id in (1, 16)}
        return (
            VARIABLE_KANA_DESIGN_FAMILY in family_names
            and "fvar" in font
            and "glyf" in font
        )
    finally:
        font.close()


def build_variable_kana_source(source: Path, output: Path) -> VariableKanaBuildResult:
    """Rebuild the Novel kana ``wght`` source with seven named instances."""
    source, output = Path(source), Path(output)
    masters = tuple(
        instantiate_variable_kana_source(source, weight)
        for weight in VARIABLE_KANA_MASTER_WEIGHTS
    )
    try:
        applications = tuple(_collect(font) for font in masters)
        if any(application != applications[0] for application in applications[1:]):
            raise ValueError(
                "Variable kana masters disagree on Unicode/layout ownership"
            )
        for font, weight, application in zip(
            masters,
            VARIABLE_KANA_MASTER_WEIGHTS,
            applications,
        ):
            for item in application[2]:
                _transform_owned_glyph(font, item, weight)

        # Threshold crossings must not give a terminal different semantic
        # ownership at different masters. Candidate IDs are contour/point based,
        # so their per-glyph union is stable across compatible masters.
        selected: dict[str, set[TerminalCandidateId]] = {
            item.name: set() for item in applications[0][2]
        }
        for font, application in zip(masters, applications):
            for item in application[2]:
                inventory = inventory_glyf_terminals(font["glyf"][item.name])
                selected[item.name].update(
                    candidate.candidate_id for candidate in inventory.candidates
                )
        frozen_selected = {
            name: frozenset(candidate_ids) for name, candidate_ids in selected.items()
        }
        results = tuple(
            _apply_design(font, weight, application, frozen_selected)
            for font, weight, application in zip(
                masters,
                VARIABLE_KANA_MASTER_WEIGHTS,
                applications,
            )
        )
        _assert_compatible(masters)
        # fontTools 4.63 cannot merge Noto's BASE VariationIndex references
        # from fully instantiated masters. It is optional for this kana design
        # source; retain all shaping tables that varLib can merge safely.
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
    return VariableKanaBuildResult(source, output, results, _SUPPORTED_WEIGHTS)


def export_variable_kana_instance(
    source: Path, weight_class: int, output: Path
) -> Path:
    """Export one supported named weight from a rebuilt Novel kana VF."""
    if weight_class not in _SUPPORTED_WEIGHTS:
        raise ValueError(
            f"Unsupported instance weight {weight_class!r}; expected {_SUPPORTED_WEIGHTS!r}"
        )
    font, output = _instantiate(Path(source), weight_class), Path(output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        font.save(output, reorderTables=False)
    finally:
        font.close()
    return output


__all__ = (
    "VARIABLE_KANA_DESIGN_FAMILY",
    "VARIABLE_KANA_MASTER_WEIGHTS",
    "VariableKanaBuildResult",
    "VariableKanaResult",
    "VariableKanaTerminalRecord",
    "apply_variable_kana_design",
    "build_variable_kana_source",
    "export_variable_kana_instance",
    "instantiate_variable_kana_source",
    "is_variable_kana_design_source",
)
