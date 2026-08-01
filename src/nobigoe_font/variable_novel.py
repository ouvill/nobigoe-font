"""Novel variable customization layered on the customized Nobigoe CFF2 source."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import pathops
from fontTools.cffLib import TopDict
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem

from . import geometry, operations
from .marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    MANGA_MARK_PAIRS,
    load_mark_position_overrides,
)
from .pipeline import _variable_kana_mappings
from .profiles import NOTO_WEIGHT_CLASSES
from .variable_kana import is_variable_kana_design_source
from .variable_marks import (
    _WEIGHTS,
    _DeltaModel,
    _append_var_data,
    _replace_var_glyph,
    _validate,
    rename_variable_font,
)


def _path(glyph_set: Any, name: str) -> pathops.Path:
    outline = pathops.Path()
    glyph_set[name].draw(  # type: ignore[index]
        DecomposingFilterPen(outline.getPen(), glyph_set)
    )
    return outline


def _replace_novel_kana(
    font: TTFont,
    design: TTFont,
    top: TopDict,
    model: _DeltaModel,
    vsindex: int,
) -> None:
    mappings = _variable_kana_mappings(
        font,
        design,
        allow_missing_ccmp_outputs=True,
    )
    glyph_sets = {
        weight: design.getGlyphSet(location={"wght": weight})
        for weight in _WEIGHTS
    }
    for target_name, source_name in dict.fromkeys(mappings.values()):
        outlines = [_path(glyph_sets[weight], source_name) for weight in _WEIGHTS]
        _replace_var_glyph(
            font,
            top,
            target_name,
            outlines,
            880,
            model,
            vsindex,
        )


def _replace_generated_mark_composites(
    font: TTFont,
    design: TTFont,
    top: TopDict,
    model: _DeltaModel,
    vsindex: int,
) -> None:
    cmap = font.getBestCmap() or {}
    design_cmap = design.getBestCmap() or {}
    target_ccmp = operations.feature_ligatures(font, "ccmp")
    design_ccmp = operations.feature_ligatures(design, "ccmp")
    glyph_sets = {
        weight: font.getGlyphSet(location={"wght": weight})
        for weight in _WEIGHTS
    }
    positions = {
        weight: load_mark_position_overrides(base="noto", weight=style)
        for style, weight in NOTO_WEIGHT_CLASSES.items()
    }
    replaced: set[str] = set()

    for base, mark in (*MANGA_MARK_PAIRS, CHOON_DAKUTEN_PAIR):
        design_base = design_cmap.get(base)
        design_mark = design_cmap.get(mark)
        if (
            design_base is not None
            and design_mark is not None
            and (design_base, design_mark) in design_ccmp
        ):
            continue

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
            if output_name in replaced:
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
            replaced.add(output_name)


def build_variable_novel(
    nobigoe_source_path: Path,
    variable_kana_source_path: Path,
    output_path: Path,
) -> Path:
    """Layer Novel kana and their generated marks onto a Nobigoe CFF2 VF."""

    if not is_variable_kana_design_source(variable_kana_source_path):
        raise ValueError("Novel variable customization requires a rebuilt kana design VF")
    font = TTFont(nobigoe_source_path, recalcTimestamp=True)
    design = TTFont(variable_kana_source_path, recalcTimestamp=False)
    if "glyf" not in design or "fvar" not in design:
        raise ValueError("Novel kana design source must be a TrueType variable font")
    design_upem = getattr(design["head"], "unitsPerEm")
    target_upem = getattr(font["head"], "unitsPerEm")
    if design_upem != target_upem:
        scale_upem(design, target_upem)

    top, locations = _validate(font)
    vsindex, model = _append_var_data(top, locations)
    _replace_novel_kana(font, design, top, model, vsindex)
    _replace_generated_mark_composites(font, design, top, model, vsindex)
    rename_variable_font(
        font,
        family="Nobigoe Novel Mincho",
        japanese_family="のびごえ小説明朝",
        postscript_prefix="NobigoeNovelMincho",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path)
    return output_path
