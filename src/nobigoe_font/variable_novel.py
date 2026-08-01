"""Novel variable customization layered on the customized Nobigoe CFF2 source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias, cast
import unicodedata

import pathops
from fontTools.cffLib import TopDict
from fontTools.misc.transform import Transform
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from . import geometry, operations
from .kana_terminals import (
    compatible_path_terminal_ids,
    taper_variable_path_terminals,
)
from .marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    MANGA_MARK_PAIRS,
    load_mark_position_overrides,
)
from .novel import (
    HIRAGANA_CODEPOINTS,
    NOVEL_KA_CODEPOINT,
    NOVEL_SMALL_KO_CODEPOINT,
    NovelGlyphGroup,
    _HORIZONTAL_ANCHORS,
    _VERTICAL_ANCHORS,
    novel_base_codepoint,
    novel_group_for_codepoint,
    novel_ka_terminal_raise,
    novel_transform,
    novel_vertical_transform,
    shorten_novel_ka_terminal,
)
from .novel_katakana import (
    KATAKANA_CODEPOINTS,
    KATAKANA_HORIZONTAL_ANCHORS,
    KATAKANA_VERTICAL_ANCHORS,
    NovelKatakanaGroup,
    katakana_transform,
    katakana_vertical_transform,
    novel_katakana_group_for_codepoint,
)
from .profiles import NOTO_WEIGHT_CLASSES, NOTO_WEIGHT_DESIGN_LOCATIONS
from .terminal_plans import terminal_depth_ratio
from .variable_marks import (
    _WEIGHTS,
    _DeltaModel,
    _append_var_data,
    _replace_var_glyph,
    _validate,
    rename_variable_font,
)

_DESIGN_MASTERS = (200, 400, 900)


def _path(glyph_set: Any, name: str) -> pathops.Path:
    outline = pathops.Path()
    glyph_set[name].draw(  # type: ignore[index]
        DecomposingFilterPen(outline.getPen(), glyph_set)
    )
    return outline

KanaScript: TypeAlias = Literal["hiragana", "katakana"]
KanaOrientation: TypeAlias = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class _OwnedGlyph:
    name: str
    codepoint: int
    script: KanaScript
    orientation: KanaOrientation
    group: NovelGlyphGroup | NovelKatakanaGroup


def _collect_owned_glyphs(font: TTFont) -> tuple[_OwnedGlyph, ...]:
    """Collect encoded, vertical, and native-composite kana by semantic owner."""
    cmap = font.getBestCmap() or {}
    vertical = {
        **operations.feature_single_substitutions(font, "vert"),
        **operations.feature_single_substitutions(font, "vrt2"),
    }
    ccmp = operations.feature_ligatures(font, "ccmp")
    owned: dict[str, _OwnedGlyph] = {}

    def add(
        glyph_name: str,
        codepoint: int,
        script: KanaScript,
        orientation: KanaOrientation,
        group: NovelGlyphGroup | NovelKatakanaGroup,
    ) -> None:
        item = _OwnedGlyph(
            glyph_name,
            codepoint,
            script,
            orientation,
            group,
        )
        previous = owned.get(glyph_name)
        if previous is None:
            owned[glyph_name] = item
        elif previous.script != script or previous.group != group:
            raise ValueError(f"Conflicting Unicode ownership for {glyph_name!r}")
        elif orientation == "horizontal":
            owned[glyph_name] = item

    scripts = (
        (
            "hiragana",
            HIRAGANA_CODEPOINTS | {NOVEL_SMALL_KO_CODEPOINT},
            novel_group_for_codepoint,
        ),
        ("katakana", KATAKANA_CODEPOINTS, novel_katakana_group_for_codepoint),
    )
    for script, codepoints, classify in scripts:
        for codepoint in sorted(codepoints):
            name = cmap.get(codepoint)
            if name is None:
                continue
            group = classify(codepoint)
            candidates: list[tuple[str, KanaOrientation]] = [
                (name, "horizontal")
            ]
            vertical_name = vertical.get(name)
            if vertical_name is not None and vertical_name != name:
                candidates.append((vertical_name, "vertical"))
            native_marked: list[tuple[str, KanaOrientation]] = []
            for glyph_name, orientation in candidates:
                for mark_codepoint in (0x3099, 0x309A):
                    mark_name = cmap.get(mark_codepoint)
                    output_name = (
                        ccmp.get((glyph_name, mark_name))
                        if mark_name is not None
                        else None
                    )
                    composed = unicodedata.normalize(
                        "NFC", chr(codepoint) + chr(mark_codepoint)
                    )
                    if (
                        output_name is not None
                        and len(composed) == 1
                        and cmap.get(ord(composed)) == output_name
                    ):
                        native_marked.append((output_name, orientation))
            for glyph_name, orientation in (*candidates, *native_marked):
                add(
                    glyph_name,
                    codepoint,
                    cast(KanaScript, script),
                    orientation,
                    group,
                )
    missing = sorted(set(owned).difference(font.getGlyphOrder()))
    if missing:
        raise ValueError(f"Unicode/layout-owned kana glyphs are missing: {missing!r}")
    return tuple(owned[name] for name in sorted(owned))


def _profile_transform(profile: object, anchor: tuple[float, float]) -> Transform:
    sx, sy = float(getattr(profile, "sx")), float(getattr(profile, "sy"))
    dx, dy = float(getattr(profile, "dx")), float(getattr(profile, "dy"))
    x, y = anchor
    return Transform(sx, 0, 0, sy, x + dx - sx * x, y + dy - sy * y)


def _transform_for(item: _OwnedGlyph, weight: int) -> Transform:
    if item.script == "hiragana":
        group = cast(NovelGlyphGroup, item.group)
        horizontal = _profile_transform(
            novel_transform(weight, group),
            _HORIZONTAL_ANCHORS[group],
        )
        if item.orientation == "horizontal":
            return horizontal
        vertical = _profile_transform(
            novel_vertical_transform(weight, group, item.codepoint),
            _VERTICAL_ANCHORS[group],
        )
    else:
        group = cast(NovelKatakanaGroup, item.group)
        horizontal = _profile_transform(
            katakana_transform(weight, group),
            KATAKANA_HORIZONTAL_ANCHORS[group],
        )
        if item.orientation == "horizontal":
            return horizontal
        vertical = _profile_transform(
            katakana_vertical_transform(weight, group, item.codepoint),
            KATAKANA_VERTICAL_ANCHORS[group],
        )
    return vertical.transform(horizontal)


def _recording(
    outline: pathops.Path,
) -> tuple[tuple[str, tuple[tuple[float, float], ...]], ...]:
    pen = RecordingPen()
    outline.draw(pen)
    return tuple(pen.value)


def _outline_signature(outline: pathops.Path) -> tuple[tuple[str, int], ...]:
    return tuple(
        (operator, len(operands)) for operator, operands in _recording(outline)
    )


def _interpolate_outline(
    left: pathops.Path,
    right: pathops.Path,
    fraction: float,
) -> pathops.Path:
    left_commands, right_commands = _recording(left), _recording(right)
    if tuple((op, len(args)) for op, args in left_commands) != tuple(
        (op, len(args)) for op, args in right_commands
    ):
        raise ValueError("Cannot interpolate incompatible cubic outlines")
    outline = pathops.Path()
    pen = outline.getPen()
    for (operator, left_points), (_, right_points) in zip(
        left_commands,
        right_commands,
        strict=True,
    ):
        points = tuple(
            (
                left_x + (right_x - left_x) * fraction,
                left_y + (right_y - left_y) * fraction,
            )
            for (left_x, left_y), (right_x, right_y) in zip(
                left_points,
                right_points,
                strict=True,
            )
        )
        getattr(pen, operator)(*points)
    return outline


def _instance_outline(
    masters: dict[int, pathops.Path],
    weight: int,
) -> pathops.Path:
    if weight in masters:
        return pathops.Path(masters[weight])
    lower, upper = (200, 400) if weight < 400 else (400, 900)
    location = NOTO_WEIGHT_DESIGN_LOCATIONS[weight]
    lower_location = NOTO_WEIGHT_DESIGN_LOCATIONS[lower]
    upper_location = NOTO_WEIGHT_DESIGN_LOCATIONS[upper]
    fraction = (location - lower_location) / (upper_location - lower_location)
    return _interpolate_outline(masters[lower], masters[upper], fraction)


def _transformed_outlines(
    font: TTFont,
    items: tuple[_OwnedGlyph, ...],
) -> dict[str, list[pathops.Path]]:
    glyph_sets = {
        weight: font.getGlyphSet(location={"wght": weight})
        for weight in _DESIGN_MASTERS
    }
    snapshots = {
        item.name: {
            weight: _path(glyph_sets[weight], item.name)
            for weight in _DESIGN_MASTERS
        }
        for item in items
    }
    transformed: dict[str, list[pathops.Path]] = {}
    for item in items:
        master_outlines: dict[int, pathops.Path] = {}
        for weight in _DESIGN_MASTERS:
            outline = geometry.transform_path(
                snapshots[item.name][weight],
                _transform_for(item, weight),
            )
            if (
                item.script == "hiragana"
                and novel_base_codepoint(item.codepoint) == NOVEL_KA_CODEPOINT
            ):
                outline = shorten_novel_ka_terminal(
                    outline,
                    novel_ka_terminal_raise(weight),
                )
            master_outlines[weight] = outline
        selected = compatible_path_terminal_ids(tuple(master_outlines.values()))
        tapered_masters: dict[int, pathops.Path] = {}
        for weight in _DESIGN_MASTERS:
            tapered = taper_variable_path_terminals(
                master_outlines[weight],
                selected,
                terminal_depth_ratio(
                    item.script,
                    item.codepoint,
                    item.orientation,
                    weight,
                ),
            ).path
            # The former glyf-to-CFF2 production path preserved hmtx's source
            # left sidebearing when converting the edited outline. Keep that
            # established placement while changing only the Novel ink shape.
            source_left = snapshots[item.name][weight].bounds[0]
            tapered_left = tapered.bounds[0]
            tapered_masters[weight] = geometry.transform_path(
                tapered,
                Transform(1, 0, 0, 1, source_left - tapered_left, 0),
            )
        master_signatures = {
            _outline_signature(outline) for outline in tapered_masters.values()
        }
        if len(master_signatures) != 1:
            raise ValueError(
                f"Novel cubic masters have incompatible topology for {item.name!r}"
            )
        outlines = [
            _instance_outline(tapered_masters, weight) for weight in _WEIGHTS
        ]
        transformed[item.name] = outlines
    return transformed


def _replace_novel_kana(
    font: TTFont,
    top: TopDict,
    model: _DeltaModel,
    vsindex: int,
) -> set[str]:
    outlines = _transformed_outlines(font, _collect_owned_glyphs(font))
    for name, masters in outlines.items():
        _replace_var_glyph(
            font,
            top,
            name,
            masters,
            880,
            model,
            vsindex,
        )
    return set(outlines)


def _replace_generated_mark_composites(
    font: TTFont,
    transformed: set[str],
    top: TopDict,
    model: _DeltaModel,
    vsindex: int,
) -> None:
    cmap = font.getBestCmap() or {}
    target_ccmp = operations.feature_ligatures(font, "ccmp")
    glyph_sets = {
        weight: font.getGlyphSet(location={"wght": weight})
        for weight in _WEIGHTS
    }
    positions = {
        weight: load_mark_position_overrides(base="noto", weight=style)
        for style, weight in NOTO_WEIGHT_CLASSES.items()
    }
    generated: set[str] = set()

    for base, mark in (*MANGA_MARK_PAIRS, CHOON_DAKUTEN_PAIR):
        horizontal_base = cmap.get(base)
        horizontal_mark = cmap.get(mark)
        if horizontal_base is None or horizontal_mark is None:
            continue
        horizontal_output = target_ccmp.get((horizontal_base, horizontal_mark))
        if horizontal_output is None:
            raise ValueError(
                f"Nobigoe source lacks U+{base:04X}+U+{mark:04X} ccmp output"
            )
        vertical_base = operations.vertical_glyph_or_self(font, horizontal_base)
        vertical_output = operations.vertical_glyph_or_self(font, horizontal_output)

        for orientation, base_name, output_name in (
            ("horizontal", horizontal_base, horizontal_output),
            ("vertical", vertical_base, vertical_output),
        ):
            orientation_key = cast(
                Literal["horizontal", "vertical"],
                orientation,
            )
            if output_name in transformed:
                continue
            if output_name in generated:
                raise ValueError(
                    f"Novel generated mark output {output_name!r} is shared"
                )
            outlines = []
            for weight in _WEIGHTS:
                glyph_set = glyph_sets[weight]
                base_path = _path(glyph_set, base_name)
                mark_path = _path(glyph_set, horizontal_mark)
                if (base, mark) == CHOON_DAKUTEN_PAIR:
                    target_x, target_y = CHOON_DAKUTEN_MARK_CENTERS[orientation_key]
                    mark_transform = geometry.centered_transform(
                        mark_path,
                        1,
                        target_x,
                        target_y,
                    )
                else:
                    mark_transform = geometry.mark_placement_transform(
                        mark_path,
                        positions[weight][(base, mark)][orientation_key],
                    )
                outlines.append(
                    geometry.compose_mark_glyph(
                        base_path,
                        mark_path,
                        mark_transform,
                    )
                )
            _replace_var_glyph(
                font,
                top,
                output_name,
                outlines,
                880,
                model,
                vsindex,
            )
            generated.add(output_name)


def build_variable_novel(
    nobigoe_source_path: Path,
    output_path: Path,
) -> Path:
    """Build Novel directly from cubic outlines in the customized Nobigoe CFF2 VF."""

    font = TTFont(nobigoe_source_path, recalcTimestamp=True)
    try:
        top, locations = _validate(font)
        vsindex, model = _append_var_data(top, locations)
        transformed = _replace_novel_kana(font, top, model, vsindex)
        _replace_generated_mark_composites(
            font,
            transformed,
            top,
            model,
            vsindex,
        )
        rename_variable_font(
            font,
            family="Nobigoe Novel Mincho",
            japanese_family="のびごえ小説明朝",
            postscript_prefix="NobigoeNovelMincho",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path)
    finally:
        font.close()
    return output_path
