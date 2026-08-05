from __future__ import annotations

import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.basePen import NullPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from nobigoe_font.hinting import autohint_latin_glyphs
from nobigoe_font.features import (
    alternating_wave_rules,
    contextual_extension_rules,
    feature_source,
    compact_auxiliary_single_substitutions,
    merge_features,
    linear_wave_transition_rules,
    mixed_wave_scan_rules,
    phased_wave_rules,
    repeated_glyph_rules,
)
from nobigoe_font.pipeline import (
    COMBINING_MARK_INPUTS,
    ConnectedStrokeWidths,
    connected_stroke_widths,
    _apply_novel_style,
    _novel_hiragana_mappings,
    _novel_katakana_mappings,
    _native_novel_ccmp_outputs,
    _normalize_cff_blue_zones,
    _synchronize_cff_widths,
    build,
    SPACING_MARK_INPUTS,
    mark_ligature_rules,
    make_manga_wave_parts,
    make_manga_to_wave_transition_parts,
    make_horizontal_parts,
    make_linear_wave_transition_parts,
    make_linear_manga_transition_parts,
    make_wave_to_manga_transition_parts,
    make_one_cycle_wave_parts,
    make_sine_wave_tile,
    make_wave_stroke_model,
    normalize_linear_stroke_width,
    stroke_band,
    make_relaxed_wave_parts,
    make_vertical_parts,
    make_wave_parts,
)
from nobigoe_font.metadata import rename_font
from nobigoe_font.punctuation import (
    make_punctuation_ligature,
    shippori_upright_punctuation_paths,
)
from nobigoe_font.marks import (
    CHOON_DAKUTEN_MARK_CENTERS,
    CHOON_DAKUTEN_PAIR,
    MANGA_MARK_PAIRS,
    MarkPlacement,
)
from nobigoe_font.novel_katakana import (
    KATAKANA_CODEPOINTS,
    KATAKANA_SOURCE_CODEPOINTS,
)

from nobigoe_font.operations import (
    add_unicode_mapping_if_missing,
    append_ttf_glyphs,
    feature_ligatures,
    feature_single_substitutions,
    import_latin_font,
    remove_repeated_ligatures,
    tt_glyph,
)
from nobigoe_font.profiles import LatinBuildProfile, font_identity
from nobigoe_font.version import VERSION_NUMBER
from nobigoe_font.geometry import (
    bounds,
    adjust_outline_weight,
    adjust_outline_horizontal_weight,
    centered_transform,
    mark_placement_transform,
    glyph_path,
    optical_stroke_width,
    transform_path,
)


def rectangle_path() -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((100, 100))
    pen.lineTo((900, 100))
    pen.lineTo((900, 500))
    pen.lineTo((100, 500))
    pen.closePath()
    return path


def wave_source_path() -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((50, 425))
    pen.lineTo((250, 475))
    pen.lineTo((500, 410))
    pen.lineTo((750, 325))
    pen.lineTo((950, 275))
    pen.lineTo((950, 225))
    pen.lineTo((750, 275))
    pen.lineTo((500, 340))
    pen.lineTo((250, 425))
    pen.lineTo((50, 375))
    pen.closePath()
    return path


def minimal_true_type_font() -> TTFont:
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "base"])
    glyphs = {}
    for name in (".notdef", "base"):
        pen = TTGlyphPen(None)
        if name == "base":
            rectangle_path().draw(pen)
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({".notdef": (1000, 0), "base": (1000, 100)})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap({0x25A1: "base"})
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def named_true_type_font(glyph_order: list[str], cmap: dict[int, str]) -> TTFont:
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    glyphs = {}
    metrics = {}
    for name in glyph_order:
        glyphs[name] = TTGlyphPen(None).glyph()
        metrics[name] = (1000, 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(cmap)
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def ascii_true_type_font(width: int, role: str) -> TTFont:
    cmap = {codepoint: f"{role}.{codepoint:04X}" for codepoint in range(0x20, 0x7F)}
    zero_alternate = f"{role}.zero.alt"
    fi_ligature = f"{role}.fi"
    glyph_order = [".notdef", *cmap.values(), zero_alternate, fi_ligature]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    glyphs = {}
    metrics = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        if name not in {".notdef", cmap[0x20]}:
            pen.moveTo((40, 80))
            pen.lineTo((width - 40, 80))
            pen.lineTo((width - 40, 600))
            pen.lineTo((40, 600))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (width, 40 if name not in {".notdef", cmap[0x20]} else 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupCharacterMap(cmap)
    builder.setupNameTable({"familyName": role, "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    font = builder.font
    if role == "target":
        features = (
            f"feature locl {{ sub {cmap[0x30]} by {zero_alternate}; }} locl;\n"
            f"feature liga {{ sub {cmap[0x66]} {cmap[0x69]} by {fi_ligature}; }} liga;"
        )
    else:
        features = (
            "languagesystem latn dflt;\n"
            f"feature liga {{ sub {cmap[0x66]} {cmap[0x69]} by {fi_ligature}; }} liga;\n"
            f"feature pnum {{ sub {cmap[0x30]} by {zero_alternate}; }} pnum;\n"
            f"feature kern {{ pos {cmap[0x41]} {cmap[0x56]} -40; }} kern;"
        )
    addOpenTypeFeaturesFromString(font, features, tables={"GSUB", "GPOS"})
    return font


class FontMetadataTests(unittest.TestCase):
    def test_rename_font_sets_open_type_revision(self) -> None:
        font = minimal_true_type_font()

        rename_font(
            font,
            "Copyright",
            "Notice",
            font_identity("noto", "Regular"),
        )

        self.assertAlmostEqual(
            font["head"].fontRevision,
            float(VERSION_NUMBER),
            places=4,
        )

    def test_rename_font_adds_macintosh_postscript_name(self) -> None:
        font = minimal_true_type_font()
        name_table = font["name"]
        name_table.removeNames(nameID=6, platformID=1)
        name_table.setName("Weight", 265, 1, 0, 0)

        identity = font_identity("noto", "Regular")
        rename_font(font, "Copyright", "Notice", identity)

        postscript_name = name_table.getName(6, 1, 0, 0)
        self.assertIsNotNone(postscript_name)
        assert postscript_name is not None
        self.assertEqual(postscript_name.toUnicode(), identity.postscript_name)


class StaticInstanceTests(unittest.TestCase):
    def test_crossed_variable_blue_zone_pairs_are_normalized_for_cff(self) -> None:
        private = SimpleNamespace(
            BlueValues=[-18, 0, 545, 527],
            OtherBlues=[-268, -278],
            FamilyBlues=[-20, 0, 550, 530],
            FamilyOtherBlues=[-260, -280],
        )
        font = {
            "CFF ": SimpleNamespace(
                cff=SimpleNamespace(
                    topDictIndex=[
                        SimpleNamespace(FDArray=[SimpleNamespace(Private=private)])
                    ]
                )
            )
        }

        _normalize_cff_blue_zones(font)  # type: ignore[arg-type]

        self.assertEqual(private.BlueValues, [-18, 0, 527, 545])
        self.assertEqual(private.OtherBlues, [-278, -268])
        self.assertEqual(private.FamilyBlues, [-20, 0, 530, 550])
        self.assertEqual(private.FamilyOtherBlues, [-280, -260])

    def test_final_cff_widths_match_horizontal_metrics(self) -> None:
        builder = FontBuilder(1000, isTTF=False)
        builder.setupGlyphOrder([".notdef", "base"])
        charstrings = {}
        for glyph_name in (".notdef", "base"):
            pen = T2CharStringPen(500, None)
            if glyph_name == "base":
                rectangle_path().draw(pen)
            charstrings[glyph_name] = pen.getCharString()
        builder.setupCharacterMap({0x25A1: "base"})
        builder.setupCFF(
            "Test-Regular",
            {"FullName": "Test Regular", "FamilyName": "Test"},
            charstrings,
            {},
        )
        builder.setupHorizontalMetrics({".notdef": (500, 0), "base": (700, 100)})
        builder.setupHorizontalHeader(ascent=880, descent=-120)
        builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
        builder.setupOS2()
        builder.setupPost()

        _synchronize_cff_widths(builder.font)
        output = BytesIO()
        builder.font.save(output)
        rebuilt = TTFont(BytesIO(output.getvalue()))
        charstring = rebuilt["CFF "].cff.topDictIndex[0].CharStrings["base"]
        charstring.draw(NullPen())

        self.assertEqual(charstring.width, rebuilt["hmtx"]["base"][0])


class FontGeometryTests(unittest.TestCase):
    def test_glyph_path_decomposes_true_type_components(self) -> None:
        font = minimal_true_type_font()
        pen = TTGlyphPen(font.getGlyphSet())
        pen.addComponent("base", Transform(1, 0, 0, 1, 50, 75))
        font["glyf"].glyphs["composite"] = pen.glyph()
        font["hmtx"].metrics["composite"] = (1000, 150)
        font.setGlyphOrder([*font.getGlyphOrder(), "composite"])

        self.assertEqual(glyph_path(font, "composite").bounds, (150, 175, 950, 575))


class TrueTypeBuildTests(unittest.TestCase):
    def test_cubic_outline_is_converted_to_quadratic_glyf(self) -> None:
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, 100))
        pen.curveTo((100, 500), (900, 500), (900, 100))
        pen.closePath()

        glyph = tt_glyph(path, 1000)

        self.assertEqual(glyph.numberOfContours, 1)
        self.assertTrue(glyph.coordinates)
        self.assertFalse(any(flag & 0x80 for flag in glyph.flags))

    def test_weight_adjustment_expands_and_thins_outline_edges(self) -> None:
        outline = rectangle_path()

        self.assertEqual(
            adjust_outline_weight(outline, 10).bounds,
            (90.0, 90.0, 910.0, 510.0),
        )
        self.assertEqual(
            adjust_outline_weight(outline, -10).bounds,
            (110.0, 110.0, 890.0, 490.0),
        )

    def test_horizontal_weight_adjustment_preserves_vertical_extent(self) -> None:
        adjusted = adjust_outline_horizontal_weight(rectangle_path(), 10)

        self.assertEqual((adjusted.bounds[0], adjusted.bounds[2]), (90.0, 910.0))
        self.assertAlmostEqual(adjusted.bounds[1], 99.375)
        self.assertAlmostEqual(adjusted.bounds[3], 500.625)

        thinned = adjust_outline_horizontal_weight(rectangle_path(), -10)
        self.assertEqual((thinned.bounds[0], thinned.bounds[2]), (110.0, 890.0))
        self.assertAlmostEqual(thinned.bounds[1], 100.625)
        self.assertAlmostEqual(thinned.bounds[3], 499.375)

    def test_horizontal_weight_adjustment_handles_round_isolated_contours(
        self,
    ) -> None:
        outline = pathops.Path()
        pen = outline.getPen()
        pen.moveTo((101, 754))
        pen.curveTo((85, 754), (72, 741), (72, 725))
        pen.curveTo((72, 709), (85, 696), (101, 696))
        pen.curveTo((117, 696), (130, 709), (130, 725))
        pen.curveTo((130, 741), (117, 754), (101, 754))
        pen.closePath()

        adjusted = adjust_outline_horizontal_weight(outline, 1)

        self.assertEqual(adjusted.bounds[0::2], (71.0, 131.0))

    def test_linear_stroke_normalization_matches_optical_target(self) -> None:
        outline = rectangle_path()
        target = 80

        horizontal = normalize_linear_stroke_width(
            outline, "horizontal", 500, 1000, target
        )
        vertical = normalize_linear_stroke_width(outline, "vertical", 300, 1000, target)
        horizontal_middle = make_horizontal_parts(horizontal, 1000)[1]
        vertical_middle = make_vertical_parts(vertical, 1000, 880)[1]

        self.assertAlmostEqual(optical_stroke_width(horizontal_middle), target, delta=1)
        self.assertAlmostEqual(optical_stroke_width(vertical_middle), target, delta=1)
        self.assertEqual(sum(horizontal.bounds[1::2]), sum(outline.bounds[1::2]))
        self.assertEqual(sum(vertical.bounds[0::2]), sum(outline.bounds[0::2]))

    def test_wave_stroke_matches_source_phase_weight(self) -> None:
        source = wave_source_path()

        wave = make_sine_wave_tile(source, 1000, half_waves=2)
        widths = []
        for position in (250, 500, 750):
            low, high = stroke_band(wave, "horizontal", position)
            widths.append(high - low)
        peak_width, crossing_width, trough_width = widths

        self.assertAlmostEqual(peak_width, 50, delta=2)
        self.assertAlmostEqual(crossing_width, 56, delta=2)
        self.assertAlmostEqual(trough_width, 50, delta=2)

    def test_connected_stroke_widths_use_orientation_medians(self) -> None:
        outline = rectangle_path()
        base_width = optical_stroke_width(outline)
        horizontal = [
            transform_path(outline, Transform(scale, 0, 0, scale, 0, 0))
            for scale in (0.5, 1, 1.5)
        ]
        vertical = [
            transform_path(outline, Transform(scale, 0, 0, scale, 0, 0))
            for scale in (0.75, 1.25, 1.75)
        ]

        widths = connected_stroke_widths(horizontal, vertical)

        self.assertAlmostEqual(widths.horizontal, base_width)
        self.assertAlmostEqual(widths.vertical, base_width * 1.25)

    def test_wave_stroke_model_matches_hiragana_targets_across_frequencies(
        self,
    ) -> None:
        source = wave_source_path()
        targets = ConnectedStrokeWidths(horizontal=80, vertical=70)
        model = make_wave_stroke_model(source, 1000, targets)
        default = make_wave_parts(source, 1000, 880, model)
        relaxed = make_relaxed_wave_parts(source, 1000, 880, model)
        one_cycle = make_one_cycle_wave_parts(source, 1000, 880, model)
        _, manga = make_manga_wave_parts(source, 1000, 880, model)

        for outline in (default[1], relaxed[2], one_cycle[2], manga[1]):
            self.assertAlmostEqual(
                optical_stroke_width(outline), targets.horizontal, delta=0.01
            )
        for outline in (default[6], relaxed[12], one_cycle[6], manga[7]):
            self.assertAlmostEqual(
                optical_stroke_width(outline), targets.vertical, delta=0.01
            )

    def test_frequency_transitions_preserve_scaled_boundary_widths(self) -> None:
        source = wave_source_path()
        model = make_wave_stroke_model(
            source,
            1000,
            ConnectedStrokeWidths(horizontal=80, vertical=70),
        )
        wave_middle = make_wave_parts(source, 1000, 880, model)[1]
        _, manga_parts = make_manga_wave_parts(source, 1000, 880, model)
        manga_middle = manga_parts[1]
        forward = make_manga_to_wave_transition_parts(source, 1000, 880, model)[0]
        reverse = make_wave_to_manga_transition_parts(source, 1000, 880, model)[0]

        def width_at(outline: pathops.Path, position: float) -> int:
            low, high = stroke_band(outline, "horizontal", position)
            return high - low

        self.assertEqual(width_at(manga_middle, 999), width_at(forward, 1))
        self.assertEqual(width_at(forward, 999), width_at(wave_middle, 1))
        self.assertEqual(width_at(wave_middle, 999), width_at(reverse, 1))
        self.assertEqual(width_at(reverse, 999), width_at(manga_middle, 1))

    def test_linear_wave_transitions_match_both_seams(self) -> None:
        horizontal = rectangle_path()
        vertical = pathops.Path()
        pen = vertical.getPen()
        pen.moveTo((300, -120))
        pen.lineTo((500, -120))
        pen.lineTo((500, 880))
        pen.lineTo((300, 880))
        pen.closePath()
        linear = (
            *make_horizontal_parts(horizontal, 1000),
            *make_vertical_parts(vertical, 1000, 880),
        )
        source = wave_source_path()
        model = make_wave_stroke_model(
            source,
            1000,
            ConnectedStrokeWidths(horizontal=80, vertical=70),
        )
        wave = make_wave_parts(source, 1000, 880, model)
        transitions = make_linear_wave_transition_parts(linear, wave, 1000, 880)

        def profile(
            outline: pathops.Path, axis: str, position: float
        ) -> tuple[float, float]:
            low, high = stroke_band(outline, axis, position)
            return (low + high) / 2, high - low

        self.assertEqual(
            profile(transitions[0], "horizontal", 0),
            profile(linear[1], "horizontal", 0),
        )
        self.assertEqual(
            profile(transitions[0], "horizontal", 1000),
            profile(wave[1], "horizontal", 1000),
        )
        self.assertEqual(
            profile(transitions[4], "horizontal", 0),
            profile(wave[1], "horizontal", 0),
        )
        self.assertEqual(
            profile(transitions[4], "horizontal", 1000),
            profile(linear[1], "horizontal", 1000),
        )
        self.assertEqual(
            profile(transitions[2], "horizontal", 0),
            profile(linear[1], "horizontal", 0),
        )
        self.assertEqual(
            profile(transitions[2], "horizontal", 1000),
            profile(linear[1], "horizontal", 1000),
        )
        self.assertEqual(
            profile(transitions[6], "vertical", 880),
            profile(linear[4], "vertical", 880),
        )
        self.assertEqual(
            profile(transitions[6], "vertical", -120),
            profile(wave[6], "vertical", -120),
        )
        self.assertEqual(
            profile(transitions[10], "vertical", 880),
            profile(wave[6], "vertical", 880),
        )
        self.assertEqual(
            profile(transitions[10], "vertical", -120),
            profile(linear[4], "vertical", -120),
        )
        self.assertLessEqual(transitions[0].bounds[0], -8)
        self.assertGreaterEqual(transitions[0].bounds[2], 1008)

        _, manga = make_manga_wave_parts(source, 1000, 880, model)
        manga_transitions = make_linear_manga_transition_parts(linear, manga, 1000, 880)
        self.assertEqual(len(manga_transitions), 10)
        self.assertEqual(
            profile(manga_transitions[0], "horizontal", 0),
            profile(linear[1], "horizontal", 0),
        )
        self.assertEqual(
            profile(manga_transitions[0], "horizontal", 1000),
            profile(manga[1], "horizontal", 1000),
        )
        self.assertEqual(
            profile(manga_transitions[4], "horizontal", 0),
            profile(manga[1], "horizontal", 0),
        )
        self.assertEqual(
            profile(manga_transitions[4], "horizontal", 1000),
            profile(linear[1], "horizontal", 1000),
        )
        self.assertEqual(
            profile(manga_transitions[5], "vertical", 880),
            profile(linear[4], "vertical", 880),
        )
        self.assertEqual(
            profile(manga_transitions[5], "vertical", -120),
            profile(manga[7], "vertical", -120),
        )
        self.assertEqual(
            profile(manga_transitions[9], "vertical", 880),
            profile(manga[7], "vertical", 880),
        )
        self.assertEqual(
            profile(manga_transitions[9], "vertical", -120),
            profile(linear[4], "vertical", -120),
        )
        self.assertLessEqual(manga_transitions[0].bounds[0], -8)
        self.assertGreaterEqual(manga_transitions[0].bounds[2], 1008)

    def test_joined_waves_use_constant_period_with_half_wave_offset(self) -> None:
        start, middle, inverted, end, inverted_end = make_wave_parts(
            wave_source_path(), 1000, 880
        )[:5]

        def center_at(path: pathops.Path, position: float) -> float:
            low, high = stroke_band(path, "horizontal", position)
            return (low + high) / 2

        def terminal_y(path: pathops.Path, position: float) -> list[float]:
            return [
                y for _, points in path for x, y in points if abs(x - position) < 1e-6
            ]

        self.assertAlmostEqual(center_at(middle, 250), 428.0, delta=2)
        self.assertAlmostEqual(center_at(middle, 750), 322.0, delta=2)
        self.assertAlmostEqual(center_at(start, 250), center_at(middle, 250), delta=2)
        self.assertAlmostEqual(center_at(end, 750), center_at(middle, 750), delta=2)
        self.assertAlmostEqual(center_at(start, 1000), center_at(inverted, 0))
        start_terminal = terminal_y(start, 50)
        end_terminal = terminal_y(inverted_end, 950)
        self.assertTrue(start_terminal)
        self.assertTrue(end_terminal)
        for y in start_terminal + end_terminal:
            self.assertAlmostEqual(y, 308.2, delta=1)

    def test_manga_to_wave_transition_preserves_centerline_and_tangent(self) -> None:
        source = wave_source_path()
        _, manga_parts = make_manga_wave_parts(source, 1000, 880)
        manga_middle = manga_parts[1]
        transition_middle, *_ = make_manga_to_wave_transition_parts(source, 1000, 880)
        wave_middle = make_wave_parts(source, 1000, 880)[1]

        def center_at(path: pathops.Path, position: float) -> float:
            low, high = stroke_band(path, "horizontal", position)
            return (low + high) / 2

        delta = 5
        manga_slope = (
            center_at(manga_middle, 1000) - center_at(manga_middle, 1000 - delta)
        ) / delta
        transition_start_slope = (
            center_at(transition_middle, delta) - center_at(transition_middle, 0)
        ) / delta
        transition_end_slope = (
            center_at(transition_middle, 1000)
            - center_at(transition_middle, 1000 - delta)
        ) / delta
        wave_slope = (center_at(wave_middle, delta) - center_at(wave_middle, 0)) / delta

        self.assertAlmostEqual(
            center_at(manga_middle, 1000),
            center_at(transition_middle, 0),
            delta=0.1,
        )
        self.assertAlmostEqual(manga_slope, transition_start_slope, delta=0.02)
        self.assertAlmostEqual(
            center_at(transition_middle, 1000),
            center_at(wave_middle, 0),
            delta=0.1,
        )
        self.assertAlmostEqual(transition_end_slope, wave_slope, delta=0.02)

    def test_wave_to_manga_transition_preserves_centerline_and_tangent(self) -> None:
        source = wave_source_path()
        wave_middle = make_wave_parts(source, 1000, 880)[1]
        rising_transition, _, falling_transition, *_ = (
            make_wave_to_manga_transition_parts(source, 1000, 880)
        )
        _, manga_parts = make_manga_wave_parts(source, 1000, 880)
        manga_middle = manga_parts[1]
        manga_inverted_middle = manga_parts[3]

        def center_at(path: pathops.Path, position: float) -> float:
            low, high = stroke_band(path, "horizontal", position)
            return (low + high) / 2

        delta = 5
        for preceding, transition, following in (
            (wave_middle, rising_transition, manga_middle),
            (
                make_wave_parts(source, 1000, 880)[2],
                falling_transition,
                manga_inverted_middle,
            ),
        ):
            preceding_slope = (
                center_at(preceding, 1000) - center_at(preceding, 1000 - delta)
            ) / delta
            transition_start_slope = (
                center_at(transition, delta) - center_at(transition, 0)
            ) / delta
            transition_end_slope = (
                center_at(transition, 1000) - center_at(transition, 1000 - delta)
            ) / delta
            following_slope = (
                center_at(following, delta) - center_at(following, 0)
            ) / delta

            self.assertAlmostEqual(
                center_at(preceding, 1000), center_at(transition, 0), delta=0.1
            )
            self.assertAlmostEqual(preceding_slope, transition_start_slope, delta=0.02)
            self.assertAlmostEqual(
                center_at(transition, 1000), center_at(following, 0), delta=0.1
            )
            self.assertAlmostEqual(transition_end_slope, following_slope, delta=0.02)

    def test_one_cycle_wave_uses_taller_amplitude_and_shorter_taper(self) -> None:
        _, start, middle, _, *_ = make_one_cycle_wave_parts(
            wave_source_path(), 1000, 880
        )

        peak_low, peak_high = stroke_band(middle, "horizontal", 500)
        self.assertAlmostEqual((peak_low + peak_high) / 2, 465, delta=2)

        start_low, start_high = stroke_band(start, "horizontal", 200)
        middle_low, middle_high = stroke_band(middle, "horizontal", 200)
        self.assertAlmostEqual(
            start_high - start_low,
            middle_high - middle_low,
            delta=2,
        )

    def test_wave_terminals_reuse_source_glyph_margins(self) -> None:
        (
            horizontal_start,
            horizontal_middle,
            _,
            horizontal_end,
            _,
            vertical_start,
            vertical_middle,
            _,
            vertical_end,
            _,
        ) = make_wave_parts(rectangle_path(), 1000, 880)

        self.assertEqual(horizontal_start.bounds[0], 100)
        self.assertEqual(horizontal_end.bounds[2], 900)
        self.assertEqual(horizontal_middle.bounds[0::2], (-8, 1008))
        self.assertEqual(vertical_start.bounds[3], 780)
        self.assertEqual(vertical_end.bounds[1], -20)
        self.assertEqual(vertical_middle.bounds[1::2], (-128, 888))

        relaxed = make_relaxed_wave_parts(rectangle_path(), 1000, 880)
        self.assertEqual(len(relaxed), 20)
        self.assertEqual(relaxed[0].bounds[0::2], (100, 900))
        self.assertEqual(relaxed[1].bounds[0], 100)
        for middle in relaxed[2:6]:
            self.assertEqual(middle.bounds[0::2], (-8, 1008))
        for end in relaxed[6:10]:
            self.assertEqual(end.bounds[2], 900)
        self.assertEqual(relaxed[10].bounds[1::2], (-20, 780))
        self.assertEqual(relaxed[11].bounds[3], 780)
        for middle in relaxed[12:16]:
            self.assertEqual(middle.bounds[1::2], (-128, 888))
        for end in relaxed[16:20]:
            self.assertEqual(end.bounds[1], -20)

        one_cycle = make_one_cycle_wave_parts(rectangle_path(), 1000, 880)
        self.assertEqual(len(one_cycle), 8)
        self.assertEqual(one_cycle[0].bounds[0::2], (100, 900))
        self.assertEqual(one_cycle[1].bounds[0], 100)
        self.assertEqual(one_cycle[2].bounds[0::2], (-8, 1008))
        self.assertEqual(one_cycle[3].bounds[2], 900)
        self.assertEqual(one_cycle[4].bounds[1::2], (-20, 780))
        self.assertEqual(one_cycle[5].bounds[3], 780)
        self.assertEqual(one_cycle[6].bounds[1::2], (-128, 888))
        self.assertEqual(one_cycle[7].bounds[1], -20)

        manga_isolated, manga_parts = make_manga_wave_parts(rectangle_path(), 1000, 880)
        (
            manga_start,
            manga_middle,
            manga_end,
            manga_inverted_middle,
            manga_inverted_end,
            manga_vertical_isolated,
            manga_vertical_start,
            manga_vertical_middle,
            manga_vertical_end,
            manga_vertical_inverted_middle,
            manga_vertical_inverted_end,
        ) = manga_parts

        self.assertEqual(manga_isolated.bounds[0::2], (100, 900))
        self.assertEqual(manga_start.bounds[0], 100)
        self.assertEqual(manga_end.bounds[2], 900)
        self.assertEqual(manga_middle.bounds[0::2], (-8, 1008))
        self.assertEqual(manga_vertical_isolated.bounds[1::2], (-20, 780))
        self.assertEqual(manga_vertical_start.bounds[3], 780)
        self.assertEqual(manga_vertical_end.bounds[1], -20)
        self.assertEqual(manga_vertical_middle.bounds[1::2], (-128, 888))
        self.assertEqual(manga_inverted_middle.bounds[0::2], (-8, 1008))
        self.assertEqual(manga_inverted_end.bounds[2], 900)
        self.assertEqual(manga_vertical_inverted_middle.bounds[1::2], (-128, 888))
        self.assertEqual(manga_vertical_inverted_end.bounds[1], -20)

    def test_exclamation_sequences_use_shippori_upright_pua_ligatures(
        self,
    ) -> None:
        source_ligature = pathops.Path()
        pen = source_ligature.getPen()
        for x_min, y_min, x_max, y_max in (
            (100, 200, 200, 800),
            (600, 200, 700, 800),
            (120, 0, 180, 100),
            (620, 0, 680, 100),
        ):
            pen.moveTo((x_min, y_min))
            pen.lineTo((x_max, y_min))
            pen.lineTo((x_max, y_max))
            pen.lineTo((x_min, y_max))
            pen.closePath()

        font = minimal_true_type_font()
        font["glyf"]["base"] = tt_glyph(source_ligature, 1000)
        for codepoint in (0xE002, 0xE007, 0xE0E3):
            add_unicode_mapping_if_missing(font, codepoint, "base")

        pair = make_punctuation_ligature(font, "!!")
        triple = make_punctuation_ligature(font, "!!!")
        quadruple = make_punctuation_ligature(font, "!!!!")
        five = make_punctuation_ligature(font, "!!!!!")

        self.assertEqual(pair.bounds, source_ligature.bounds)
        self.assertEqual(triple.bounds, source_ligature.bounds)
        self.assertEqual(quadruple.bounds, source_ligature.bounds)
        self.assertEqual(len(list(pair.contours)), 4)
        self.assertEqual(len(list(five.contours)), 10)

    def test_upright_question_uses_shippori_fullwidth_glyph(self) -> None:
        font = named_true_type_font(
            [".notdef", "exclamation", "question"],
            {0xE000: "exclamation", 0xFF1F: "question"},
        )
        exclamation = rectangle_path()
        question = transform_path(rectangle_path(), Transform(0.5, 0, 0, 1, 250, 0))
        font["glyf"]["exclamation"] = tt_glyph(exclamation, 1000)
        font["glyf"]["question"] = tt_glyph(question, 1000)

        upright = shippori_upright_punctuation_paths(font)

        self.assertEqual(upright["!"].bounds, exclamation.bounds)
        self.assertEqual(upright["?"].bounds, question.bounds)

    def test_zero_mark_rotation_matches_the_original_transform(self) -> None:
        transform = mark_placement_transform(
            rectangle_path(),
            MarkPlacement(0.8, 900, -50, 0),
        )

        self.assertEqual(transform, Transform(0.8, 0, 0, 0.8, 900, -50))

    def test_mark_rotation_preserves_center_and_uses_positive_ccw(self) -> None:
        mark = rectangle_path()
        transform = mark_placement_transform(
            mark,
            MarkPlacement(0.8, 900, -50, 90),
        )
        placed = transform_path(mark, transform)
        x_min, y_min, x_max, y_max = placed.bounds

        self.assertAlmostEqual((x_min + x_max) / 2, 1300)
        self.assertAlmostEqual((y_min + y_max) / 2, 190)
        self.assertAlmostEqual(x_max - x_min, 320)
        self.assertAlmostEqual(y_max - y_min, 640)
        right_edge_x, right_edge_y = transform.transformPoint((900, 300))
        self.assertAlmostEqual(right_edge_x, 1300)
        self.assertAlmostEqual(right_edge_y, 510)

    def test_choon_dakuten_uses_koburi_mark_centers(self) -> None:
        mark = transform_path(rectangle_path(), Transform(0.2, 0, 0, 0.2, -300, 500))
        for orientation, (target_x, target_y) in CHOON_DAKUTEN_MARK_CENTERS.items():
            placed = transform_path(
                mark,
                centered_transform(mark, 1, target_x, target_y),
            )
            x_min, y_min, x_max, y_max = placed.bounds
            with self.subTest(orientation=orientation):
                self.assertAlmostEqual((x_min + x_max) / 2, target_x, places=3)
                self.assertAlmostEqual((y_min + y_max) / 2, target_y, places=3)

    def test_feature_source_builds_choon_dakuten_substitutions(self) -> None:
        base_codepoint, mark_codepoint = CHOON_DAKUTEN_PAIR
        base = f"uni{base_codepoint:04X}"
        mark = f"uni{mark_codepoint:04X}"
        spacing_mark_codepoint = 0x309B
        spacing_mark = f"uni{spacing_mark_codepoint:04X}"
        output = "choon.dakuten"
        vertical_output = f"{output}.vert"
        wave_names = [f"wave.{index}" for index in range(10)]
        relaxed_wave_names = [f"wave-relaxed.{index}" for index in range(20)]
        one_cycle_wave_names = [f"wave-one-cycle.{index}" for index in range(8)]
        transition_names = [f"wave-transition.{index}" for index in range(8)]
        reverse_transition_names = [f"manga-transition.{index}" for index in range(8)]
        manga_wave_names = [f"manga-wave.{index}" for index in range(11)]
        punctuation_variants = [
            ("!", ("exclamation", "exclamation.a1")),
            ("?", ("question", "question.a1")),
        ]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    base,
                    mark,
                    spacing_mark,
                    output,
                    vertical_output,
                    "wave.base",
                    "wave.vert",
                    *wave_names,
                    *relaxed_wave_names,
                    *one_cycle_wave_names,
                    *transition_names,
                    *reverse_transition_names,
                    "manga-wave.base",
                    *manga_wave_names,
                    *(name for _, names in punctuation_variants for name in names),
                ]
            )
        )
        font = named_true_type_font(
            glyph_order,
            {
                base_codepoint: base,
                mark_codepoint: mark,
                spacing_mark_codepoint: spacing_mark,
            },
        )
        source = feature_source(
            [],
            ("wave", "wave.base", "wave.vert", wave_names),
            (
                "wave-relaxed",
                "wave.base",
                "wave.vert",
                relaxed_wave_names,
            ),
            ("manga-wave", "manga-wave.base", manga_wave_names),
            (
                "wave-one-cycle",
                "wave.base",
                "wave.vert",
                one_cycle_wave_names,
            ),
            ("wave-transition", transition_names),
            ("manga-transition", reverse_transition_names),
            punctuation_variants,
            [],
            [],
            mark_ligature_rules(
                font.getBestCmap(),
                [CHOON_DAKUTEN_PAIR],
                {CHOON_DAKUTEN_PAIR: output},
                COMBINING_MARK_INPUTS,
            ),
            mark_ligature_rules(
                font.getBestCmap(),
                [CHOON_DAKUTEN_PAIR],
                {CHOON_DAKUTEN_PAIR: output},
                SPACING_MARK_INPUTS,
            ),
            [(output, vertical_output)],
        )

        self.assertIn("feature ss01", source)
        self.assertIn("feature ss04", source)
        self.assertIn("feature ss05", source)
        self.assertNotIn("feature ss02", source)
        self.assertNotIn("feature ss03", source)

        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        ccmp = feature_ligatures(font, "ccmp")
        liga = feature_ligatures(font, "liga")
        self.assertEqual(ccmp[(base, mark)], output)
        self.assertNotIn((base, spacing_mark), ccmp)
        self.assertEqual(liga[(base, spacing_mark)], output)
        self.assertNotIn(
            ("manga-wave.base", "wave.base"),
            feature_ligatures(font, "liga"),
        )
        self.assertEqual(
            feature_single_substitutions(font, "vert")[output],
            vertical_output,
        )

    def test_mark_ligature_rules_alias_spacing_marks(self) -> None:
        pairs = ((0x3042, 0x3099), (0x304B, 0x309A))
        outputs = {
            pairs[0]: "hiragana-a.dakuten",
            pairs[1]: "hiragana-ka.handakuten",
        }
        cmap = {
            0x3042: "hiragana-a",
            0x304B: "hiragana-ka",
            0x3099: "dakuten",
            0x309A: "handakuten",
            0x309B: "spacing-dakuten",
            0x309C: "spacing-handakuten",
        }

        combining_rules = {
            (base, mark): output
            for base, mark, output in mark_ligature_rules(
                cmap, pairs, outputs, COMBINING_MARK_INPUTS
            )
        }
        spacing_rules = {
            (base, mark): output
            for base, mark, output in mark_ligature_rules(
                cmap, pairs, outputs, SPACING_MARK_INPUTS
            )
        }

        self.assertEqual(
            combining_rules,
            {
                ("hiragana-a", "dakuten"): "hiragana-a.dakuten",
                ("hiragana-ka", "handakuten"): "hiragana-ka.handakuten",
            },
        )
        self.assertEqual(
            spacing_rules,
            {
                ("hiragana-a", "spacing-dakuten"): "hiragana-a.dakuten",
                (
                    "hiragana-ka",
                    "spacing-handakuten",
                ): "hiragana-ka.handakuten",
            },
        )

    def test_feature_source_builds_punctuation_mark_substitutions(self) -> None:
        punctuation_variants = [
            ("!", ("exclamation", "exclamation.a1")),
            ("?", ("question", "question.a1")),
        ]
        marks = ("dakuten", "handakuten")
        outputs = [
            "exclamation.dakuten",
            "exclamation.handakuten",
            "question.dakuten",
            "question.handakuten",
        ]
        vertical_outputs = [f"{output}.vert" for output in outputs]
        punctuation_marks = [
            ("exclamation", "dakuten", outputs[0]),
            ("exclamation", "handakuten", outputs[1]),
            ("question", "dakuten", outputs[2]),
            ("question", "handakuten", outputs[3]),
        ]
        vertical_maps = list(zip(outputs, vertical_outputs, strict=True))
        wave_names = [f"wave.{index}" for index in range(10)]
        relaxed_wave_names = [f"wave-relaxed.{index}" for index in range(20)]
        one_cycle_wave_names = [f"wave-one-cycle.{index}" for index in range(8)]
        transition_names = [f"wave-transition.{index}" for index in range(8)]
        reverse_transition_names = [f"manga-transition.{index}" for index in range(8)]
        manga_wave_names = [f"manga-wave.{index}" for index in range(11)]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    *marks,
                    *outputs,
                    *vertical_outputs,
                    "wave.base",
                    "wave.vert",
                    *wave_names,
                    *relaxed_wave_names,
                    *one_cycle_wave_names,
                    *transition_names,
                    *reverse_transition_names,
                    "manga-wave.base",
                    *manga_wave_names,
                    *(name for _, names in punctuation_variants for name in names),
                ]
            )
        )
        font = named_true_type_font(glyph_order, {})
        source = feature_source(
            [],
            ("wave", "wave.base", "wave.vert", wave_names),
            (
                "wave-relaxed",
                "wave.base",
                "wave.vert",
                relaxed_wave_names,
            ),
            ("manga-wave", "manga-wave.base", manga_wave_names),
            (
                "wave-one-cycle",
                "wave.base",
                "wave.vert",
                one_cycle_wave_names,
            ),
            ("wave-transition", transition_names),
            ("manga-transition", reverse_transition_names),
            punctuation_variants,
            [],
            [],
            [],
            [],
            vertical_maps,
            punctuation_marks,
        )

        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        ccmp = feature_ligatures(font, "ccmp")
        self.assertEqual(
            {(base, mark): ccmp[(base, mark)] for base, mark, _ in punctuation_marks},
            {(base, mark): output for base, mark, output in punctuation_marks},
        )
        vert = feature_single_substitutions(font, "vert")
        self.assertEqual(
            {output: vert[output] for output in outputs},
            dict(vertical_maps),
        )

    def test_horizontal_choon_calt_is_added_to_kana_script(self) -> None:
        glyph_order = [
            ".notdef",
            "choon",
            "old.alt",
            "choon.start",
            "choon.middle",
            "choon.end",
            "choon.vert",
        ]
        font = named_true_type_font(glyph_order, {0x30FC: "choon"})
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem kana dflt;
            languagesystem latn dflt;
            feature calt {
              script latn;
              sub choon by old.alt;
            } calt;
            feature vert {
              script kana;
              sub choon by choon.vert;
            } vert;
            """,
            tables={"GSUB"},
        )

        merge_features(
            font,
            "languagesystem DFLT dflt;\n"
            "feature calt {\n"
            + contextual_extension_rules(
                "choon_h",
                "choon",
                "choon.start",
                "choon.middle",
                "choon.end",
            )
            + "} calt;\n",
        )

        gsub = font["GSUB"].table
        feature_records = gsub.FeatureList.FeatureRecord
        kana = next(
            record.Script
            for record in gsub.ScriptList.ScriptRecord
            if record.ScriptTag == "kana"
        )
        self.assertIsNotNone(kana.DefaultLangSys)
        self.assertIn(
            "calt",
            {
                feature_records[index].FeatureTag
                for index in kana.DefaultLangSys.FeatureIndex
            },
        )

    def test_merge_features_preserves_existing_ruby(self) -> None:
        font = named_true_type_font(
            [".notdef", "kana", "kana.ruby", "kana.alt"],
            {0x3042: "kana"},
        )
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem DFLT dflt;
            feature ruby { sub kana by kana.ruby; } ruby;
            """,
            tables={"GSUB"},
        )

        merge_features(
            font,
            """
            languagesystem DFLT dflt;
            feature ss01 { sub kana by kana.alt; } ss01;
            """,
        )

        output = BytesIO()
        font.save(output)
        rebuilt = TTFont(BytesIO(output.getvalue()))
        self.assertEqual(
            feature_single_substitutions(rebuilt, "ruby"),
            {"kana": "kana.ruby"},
        )
        self.assertEqual(
            feature_single_substitutions(rebuilt, "ss01"),
            {"kana": "kana.alt"},
        )

    def test_contextual_single_substitution_helpers_are_compacted(self) -> None:
        font = named_true_type_font(
            [".notdef", "a", "b", "c", "d", "a.alt", "c.alt"],
            {0x61: "a", 0x62: "b", 0x63: "c", 0x64: "d"},
        )
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem DFLT dflt;
            lookup first {
              sub a' b by a.alt;
            } first;
            lookup second {
              sub c' d by c.alt;
            } second;
            feature calt {
              lookup first;
              lookup second;
            } calt;
            """,
            tables={"GSUB"},
        )
        before = len(font["GSUB"].table.LookupList.Lookup)

        after = compact_auxiliary_single_substitutions(font)
        output = BytesIO()
        font.save(output)
        rebuilt = TTFont(BytesIO(output.getvalue()))
        mappings = [
            subtable.mapping
            for lookup in rebuilt["GSUB"].table.LookupList.Lookup
            if lookup.LookupType == 1
            for subtable in lookup.SubTable
        ]

        self.assertLess(after, before)
        self.assertIn({"a": "a.alt", "c": "c.alt"}, mappings)

    @unittest.skipUnless(shutil.which("hb-shape"), "hb-shape is not installed")
    def test_all_horizontal_extension_symbols_shape_to_calt_parts(self) -> None:
        cmap = {
            0x7E: "asciitilde",
            0x30FC: "choon",
            0x2015: "dash",
            0x301C: "wave",
            0xFF5E: "wave",
            0x3030: "manga-wave",
        }
        expected = {
            0x30FC: ["choon.start", "choon.middle", "choon.end"],
            0x2015: ["dash.start", "dash.middle", "dash.end"],
            0x301C: ["wave.start", "wave.middle-b", "wave.end-a"],
            0xFF5E: ["wave.start", "wave.middle-b", "wave.end-a"],
            0x3030: ["manga-wave.start", "manga-wave.middle", "manga-wave.end"],
        }
        generated_names = [
            *expected[0x30FC],
            *expected[0x2015],
            "wave.start",
            "wave.middle-a",
            "wave.middle-b",
            "wave.end-a",
            "wave.end-b",
            *expected[0x3030],
            "manga-wave.inverted-middle",
            "manga-wave.inverted-end",
            "wave-relaxed.isolated",
            "wave-relaxed.start",
            "wave-relaxed.middle-0",
            "wave-relaxed.middle-1",
            "wave-relaxed.middle-2",
            "wave-relaxed.middle-3",
            "wave-relaxed.end-0",
            "wave-relaxed.end-1",
            "wave-relaxed.end-2",
            "wave-relaxed.end-3",
            "manga-to-wave.middle",
            "manga-to-wave.end",
            "manga-to-wave.inverted-middle",
            "manga-to-wave.inverted-end",
            "wave-to-manga.rising-middle",
            "wave-to-manga.rising-end",
            "wave-to-manga.falling-middle",
            "wave-to-manga.falling-end",
            "wave-one-cycle.isolated",
            "wave-one-cycle.start",
            "wave-one-cycle.middle",
            "wave-one-cycle.end",
        ]
        glyph_order = list(
            dict.fromkeys(
                [
                    ".notdef",
                    *cmap.values(),
                    "old.alt",
                    "choon.vert",
                    "dash.two",
                    "dash.three",
                    *generated_names,
                ]
            )
        )
        font = named_true_type_font(glyph_order, cmap)
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem DFLT dflt;
            languagesystem kana dflt;
            languagesystem latn dflt;
            feature ccmp {
              script DFLT;
              sub dash dash dash by dash.three;
              sub dash dash by dash.two;
            } ccmp;
            feature calt {
              script latn;
              sub choon by old.alt;
            } calt;
            feature vert {
              script DFLT;
              sub choon by choon.vert;
              script kana;
              sub choon by choon.vert;
            } vert;
            """,
            tables={"GSUB"},
        )
        self.assertEqual(remove_repeated_ligatures(font, "ccmp", "dash"), 2)

        calt_source = (
            "languagesystem DFLT dflt;\n"
            "feature ss04 {\n"
            + repeated_glyph_rules(
                "wave_relaxed_style", "wave", "wave-relaxed.isolated"
            )
            + "} ss04;\n"
            "feature ss05 {\n"
            + repeated_glyph_rules(
                "wave_one_cycle_style", "wave", "wave-one-cycle.isolated"
            )
            + "} ss05;\n"
            "feature calt {\n"
            + mixed_wave_scan_rules(
                "mixed_wave_h",
                "manga-wave",
                [
                    "manga-wave.start",
                    "manga-wave.middle",
                    "manga-wave.end",
                    "manga-wave.inverted-middle",
                    "manga-wave.inverted-end",
                ],
                "wave",
                [
                    "wave.start",
                    "wave.middle-a",
                    "wave.middle-b",
                    "wave.end-a",
                    "wave.end-b",
                ],
                [
                    "manga-to-wave.middle",
                    "manga-to-wave.end",
                    "manga-to-wave.inverted-middle",
                    "manga-to-wave.inverted-end",
                ],
                [
                    "wave-to-manga.rising-middle",
                    "wave-to-manga.rising-end",
                    "wave-to-manga.falling-middle",
                    "wave-to-manga.falling-end",
                ],
            )
            + contextual_extension_rules(
                "choon_h",
                "choon",
                "choon.start",
                "choon.middle",
                "choon.end",
            )
            + contextual_extension_rules(
                "dash_h",
                "dash",
                "dash.start",
                "dash.middle",
                "dash.end",
            )
            + alternating_wave_rules(
                "wave_h",
                "wave",
                [
                    "wave.start",
                    "wave.middle-a",
                    "wave.middle-b",
                    "wave.end-a",
                    "wave.end-b",
                ],
            )
            + contextual_extension_rules(
                "manga_wave_h",
                "manga-wave",
                "manga-wave.start",
                "manga-wave.middle",
                "manga-wave.end",
            )
            + phased_wave_rules(
                "wave_relaxed_h",
                "wave-relaxed.isolated",
                [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-0",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.middle-2",
                    "wave-relaxed.middle-3",
                    "wave-relaxed.end-0",
                    "wave-relaxed.end-1",
                    "wave-relaxed.end-2",
                    "wave-relaxed.end-3",
                ],
            )
            + contextual_extension_rules(
                "wave_one_cycle_h",
                "wave-one-cycle.isolated",
                "wave-one-cycle.start",
                "wave-one-cycle.middle",
                "wave-one-cycle.end",
            )
            + "} calt;\n"
        )
        merge_features(font, calt_source)

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "extensions.ttf"
            font.save(path)
            for codepoint, enabled_glyphs in expected.items():
                text = chr(codepoint) * 3
                for calt, expected_glyphs in (
                    (0, [cmap[codepoint]] * 3),
                    (1, enabled_glyphs),
                ):
                    shaped = subprocess.run(
                        [
                            "hb-shape",
                            "--output-format=json",
                            f"--features=calt={calt}",
                            str(path),
                            text,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    actual_glyphs = [
                        record["g"] for record in json.loads(shaped.stdout)
                    ]
                    with self.subTest(codepoint=codepoint, calt=calt):
                        self.assertEqual(actual_glyphs, expected_glyphs)

            relaxed_sequences = {
                1: ["wave"],
                2: ["wave-relaxed.start", "wave-relaxed.end-1"],
                3: [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.end-2",
                ],
                4: [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.middle-2",
                    "wave-relaxed.end-3",
                ],
                5: [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.middle-2",
                    "wave-relaxed.middle-3",
                    "wave-relaxed.end-0",
                ],
                6: [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.middle-2",
                    "wave-relaxed.middle-3",
                    "wave-relaxed.middle-0",
                    "wave-relaxed.end-1",
                ],
                7: [
                    "wave-relaxed.start",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.middle-2",
                    "wave-relaxed.middle-3",
                    "wave-relaxed.middle-0",
                    "wave-relaxed.middle-1",
                    "wave-relaxed.end-2",
                ],
            }
            for length, expected_glyphs in relaxed_sequences.items():
                shaped = subprocess.run(
                    [
                        "hb-shape",
                        "--output-format=json",
                        "--features=calt=1,ss04=1",
                        str(path),
                        chr(0x301C) * length,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                actual_glyphs = [record["g"] for record in json.loads(shaped.stdout)]
                with self.subTest(relaxed_length=length):
                    self.assertEqual(actual_glyphs, expected_glyphs)

            one_cycle_sequences = {
                length: (
                    ["wave"]
                    if length == 1
                    else [
                        "wave-one-cycle.start",
                        *(["wave-one-cycle.middle"] * (length - 2)),
                        "wave-one-cycle.end",
                    ]
                )
                for length in range(1, 8)
            }
            for codepoint in (0x301C, 0xFF5E):
                for length, expected_glyphs in one_cycle_sequences.items():
                    shaped = subprocess.run(
                        [
                            "hb-shape",
                            "--output-format=json",
                            "--features=calt=1,ss04=0,ss05=1",
                            str(path),
                            chr(codepoint) * length,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    actual_glyphs = [
                        record["g"] for record in json.loads(shaped.stdout)
                    ]
                    with self.subTest(
                        one_cycle_codepoint=codepoint,
                        one_cycle_length=length,
                    ):
                        self.assertEqual(actual_glyphs, expected_glyphs)

            for wave_codepoint in (0x301C, 0xFF5E):
                for manga_length in range(1, 4):
                    for wave_length in range(1, 5):
                        manga_expected = [
                            "manga-wave.start",
                            *(["manga-wave.middle"] * (manga_length - 1)),
                        ]
                        if wave_length == 1:
                            wave_expected = ["manga-to-wave.end"]
                        else:
                            remaining = wave_length - 1
                            wave_expected = [
                                "manga-to-wave.middle",
                                *(
                                    (
                                        "wave.middle-a"
                                        if index % 2 == 0
                                        else "wave.middle-b"
                                    )
                                    for index in range(remaining - 1)
                                ),
                                ("wave.end-a" if remaining % 2 == 1 else "wave.end-b"),
                            ]
                        shaped = subprocess.run(
                            [
                                "hb-shape",
                                "--output-format=json",
                                "--features=calt=1,ss04=0,ss05=0",
                                str(path),
                                "〰" * manga_length + chr(wave_codepoint) * wave_length,
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        actual_glyphs = [
                            record["g"] for record in json.loads(shaped.stdout)
                        ]
                        with self.subTest(
                            wave_codepoint=wave_codepoint,
                            manga_length=manga_length,
                            wave_length=wave_length,
                        ):
                            self.assertEqual(
                                actual_glyphs, manga_expected + wave_expected
                            )

            reverse_expected = {
                "〜〰": ["wave.start", "wave-to-manga.rising-end"],
                "〜〜〰〰": [
                    "wave.start",
                    "wave.middle-b",
                    "wave-to-manga.falling-middle",
                    "manga-wave.inverted-end",
                ],
                "〜〰〜〰〜": [
                    "wave.start",
                    "wave-to-manga.rising-middle",
                    "manga-to-wave.middle",
                    "wave-to-manga.falling-middle",
                    "manga-to-wave.inverted-end",
                ],
                "〰〰〜〜〰〰〜〜": [
                    "manga-wave.start",
                    "manga-wave.middle",
                    "manga-to-wave.middle",
                    "wave.middle-a",
                    "wave-to-manga.rising-middle",
                    "manga-wave.middle",
                    "manga-to-wave.middle",
                    "wave.end-a",
                ],
            }
            for text, expected_glyphs in reverse_expected.items():
                shaped = subprocess.run(
                    [
                        "hb-shape",
                        "--output-format=json",
                        "--features=calt=1,ss04=0,ss05=0",
                        str(path),
                        text,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                actual_glyphs = [record["g"] for record in json.loads(shaped.stdout)]
                with self.subTest(mixed_text=text):
                    self.assertEqual(actual_glyphs, expected_glyphs)

            shaped_without_calt = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=0,ss04=0,ss05=0",
                    str(path),
                    "〰〜〜",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                [record["g"] for record in json.loads(shaped_without_calt.stdout)],
                ["manga-wave", "wave", "wave"],
            )

            shaped_tilde = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=1,liga=1,ss04=0",
                    str(path),
                    "~〜〜",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                [record["g"] for record in json.loads(shaped_tilde.stdout)],
                ["asciitilde", "wave.start", "wave.end-b"],
            )

    @unittest.skipUnless(shutil.which("hb-shape"), "hb-shape is required")
    def test_linear_wave_bridge_connects_a_single_wave_between_lines(self) -> None:
        line_names = ["line.start", "line.middle", "line.end"]
        wave_names = [
            "wave.start",
            "wave.middle-a",
            "wave.middle-b",
            "wave.end-a",
            "wave.end-b",
        ]
        transition_names = [
            "line-to-wave",
            "line-to-wave.end",
            "line-wave-line",
            "wave-to-line.start",
            "wave-to-line.a",
            "wave-to-line.b",
        ]
        glyph_order = [
            ".notdef",
            "line",
            "wave",
            "wave.relaxed",
            *line_names,
            *wave_names,
            *transition_names,
        ]
        font = named_true_type_font(
            glyph_order,
            {ord("L"): "line", ord("W"): "wave"},
        )
        source = (
            "languagesystem DFLT dflt;\n"
            "feature ss04 { sub wave by wave.relaxed; } ss04;\n"
            "feature calt {\n"
            + contextual_extension_rules("line", "line", *line_names)
            + alternating_wave_rules("wave", "wave", wave_names)
            + linear_wave_transition_rules(
                "line_wave",
                "line",
                line_names,
                "wave",
                wave_names[0],
                wave_names[1:3],
                wave_names[3:5],
                transition_names,
            )
            + "} calt;\n"
        )
        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "line-wave.ttf"
            font.save(path)
            shaped = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=1",
                    str(path),
                    "LWL",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            shaped_relaxed = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=1,ss04=1",
                    str(path),
                    "LWWL",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            [record["g"] for record in json.loads(shaped.stdout)],
            ["line.start", "line-wave-line", "line.end"],
        )
        self.assertEqual(
            [record["g"] for record in json.loads(shaped_relaxed.stdout)],
            ["line", "wave.relaxed", "wave.relaxed", "line"],
        )

    @unittest.skipUnless(shutil.which("hb-shape"), "hb-shape is required")
    def test_linear_manga_transitions_connect_two_cycle_waves(self) -> None:
        line_names = ["line.start", "line.middle", "line.end"]
        manga_names = ["manga.start", "manga.middle", "manga.end"]
        transition_names = [
            "line-to-manga",
            "line-to-manga.end",
            "line-manga-line",
            "manga-to-line.start",
            "manga-to-line",
        ]
        font = named_true_type_font(
            [
                ".notdef",
                "line",
                "manga",
                *line_names,
                *manga_names,
                *transition_names,
            ],
            {ord("L"): "line", ord("M"): "manga"},
        )
        source = (
            "languagesystem DFLT dflt;\n"
            "feature calt {\n"
            + contextual_extension_rules("line", "line", *line_names)
            + contextual_extension_rules("manga", "manga", *manga_names)
            + linear_wave_transition_rules(
                "line_manga",
                "line",
                line_names,
                "manga",
                manga_names[0],
                manga_names[1:2],
                manga_names[2:],
                transition_names,
            )
            + "} calt;\n"
        )
        addOpenTypeFeaturesFromString(font, source, tables={"GSUB"})

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "line-manga.ttf"
            font.save(path)
            shaped = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=1",
                    str(path),
                    "LLMMLL",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            bridge = subprocess.run(
                [
                    "hb-shape",
                    "--output-format=json",
                    "--features=calt=1",
                    str(path),
                    "LML",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            [record["g"] for record in json.loads(shaped.stdout)],
            [
                "line.start",
                "line.middle",
                "line-to-manga",
                "manga-to-line",
                "line.middle",
                "line.end",
            ],
        )
        self.assertEqual(
            [record["g"] for record in json.loads(bridge.stdout)],
            ["line.start", "line-manga-line", "line.end"],
        )

    def test_fallback_unicode_mapping_preserves_a_native_pua_glyph(
        self,
    ) -> None:
        font = named_true_type_font(
            [".notdef", "unicode.heart", "pua.heart"],
            {0x2661: "unicode.heart", 0xE064: "pua.heart"},
        )

        existing = add_unicode_mapping_if_missing(font, 0xE064, "unicode.heart")
        added = add_unicode_mapping_if_missing(font, 0xE065, "unicode.heart")

        self.assertEqual(existing, "pua.heart")
        self.assertEqual(added, "unicode.heart")
        self.assertEqual(font.getBestCmap()[0xE064], "pua.heart")
        self.assertEqual(font.getBestCmap()[0xE065], "unicode.heart")

    def test_appended_glyph_has_unique_order_and_survives_round_trip(self) -> None:
        font = minimal_true_type_font()
        append_ttf_glyphs(
            font,
            [rectangle_path()],
            ["extension.middle"],
            "base",
            880,
        )

        self.assertEqual(font.getGlyphOrder(), [".notdef", "base", "extension.middle"])
        self.assertEqual(len(font["glyf"].glyphs), 3)
        self.assertEqual(font["hmtx"].metrics["extension.middle"], (1000, 100))

        data = BytesIO()
        font.save(data)
        data.seek(0)
        rebuilt = TTFont(data)
        self.assertEqual(rebuilt.getGlyphOrder(), font.getGlyphOrder())
        self.assertEqual(rebuilt["maxp"].numGlyphs, 3)

    def test_latin_import_merges_source_layout_and_common_numeric_features(
        self,
    ) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")
        result = import_latin_font(
            target,
            source,
            LatinBuildProfile("libertinus", 1, 0),
        )

        target_cmap = target.getBestCmap()
        target_liga = feature_ligatures(target, "liga")
        target_pnum = feature_single_substitutions(target, "pnum")
        self.assertIn(
            (target_cmap[0x66], target_cmap[0x69]),
            target_liga,
        )
        self.assertIn(target_cmap[0x30], target_pnum)
        self.assertIn(target_pnum[target_cmap[0x30]], result.glyph_names)
        self.assertIn("GPOS", target)

    def test_autohint_limits_processing_to_imported_glyphs(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "font.otf"
            output_path.write_bytes(b"unhinted")

            def fake_run(command: list[str], check: bool) -> None:
                self.assertTrue(check)
                self.assertEqual(command[0], "/usr/bin/otfautohint")
                glyph_list_path = Path(command[command.index("--glyphs-file") + 1])
                self.assertEqual(
                    glyph_list_path.read_text(encoding="utf-8"),
                    "latin.A,latin.B",
                )
                hinted_path = Path(command[command.index("--output") + 1])
                hinted_path.write_bytes(b"hinted")

            with patch("nobigoe_font.hinting.subprocess.run", side_effect=fake_run):
                autohint_latin_glyphs(
                    output_path,
                    ("latin.A", "latin.B"),
                    executable="/usr/bin/otfautohint",
                )

            self.assertEqual(output_path.read_bytes(), b"hinted")

    def test_latin_replacement_scales_outlines_advances_and_gsub_outputs(
        self,
    ) -> None:
        target = ascii_true_type_font(900, "target")
        source = ascii_true_type_font(500, "source")

        import_latin_font(
            target,
            source,
            LatinBuildProfile("libertinus", 1.1, 0),
        )

        target_cmap = target.getBestCmap()
        target_a = target_cmap[0x41]
        self.assertEqual(target["hmtx"].metrics[target_a], (550, 44))
        self.assertEqual(bounds(target, target_a), (44, 88, 506, 660))
        target_fi = feature_ligatures(target, "liga")[
            (target_cmap[0x66], target_cmap[0x69])
        ]
        self.assertEqual(target["hmtx"].metrics[target_fi], (550, 44))
        self.assertEqual(bounds(target, target_fi), (44, 88, 506, 660))


class NovelKatakanaPipelineTests(unittest.TestCase):
    def test_native_katakana_ccmp_discovery_includes_vertical_outputs(
        self,
    ) -> None:
        cmap = {
            0x3099: "dakuten",
            0x309A: "handakuten",
            0x30AB: "katakana-ka",
            0x31F7: "small-katakana-pu",
            0x30FC: "choon",
        }
        ligatures = {
            ("katakana-ka", "dakuten"): "native-ga",
            ("katakana-ka.vert", "dakuten"): "native-ga.vert",
            ("small-katakana-pu", "handakuten"): "native-small-pu",
            (
                "small-katakana-pu.vert",
                "handakuten",
            ): "native-small-pu.vert",
            ("choon", "dakuten"): "excluded-choon-dakuten",
        }
        with patch(
            "nobigoe_font.pipeline._font_operations.vertical_glyph_or_self",
            side_effect=lambda _font, glyph_name: f"{glyph_name}.vert",
        ):
            horizontal, vertical = _native_novel_ccmp_outputs(
                Mock(),
                cmap,
                ligatures,
                KATAKANA_SOURCE_CODEPOINTS,
            )

        self.assertEqual(
            horizontal,
            {
                (0x30AB, 0x3099): "native-ga",
                (0x31F7, 0x309A): "native-small-pu",
            },
        )
        self.assertEqual(
            vertical,
            {
                (0x30AB, 0x3099): "native-ga.vert",
                (0x31F7, 0x309A): "native-small-pu.vert",
            },
        )
        self.assertNotIn(CHOON_DAKUTEN_PAIR, horizontal)

    def test_katakana_mapping_rejects_group_and_vertical_base_conflicts(
        self,
    ) -> None:
        with (
            patch(
                "nobigoe_font.pipeline._font_operations.vertical_glyph_or_self",
                side_effect=lambda _font, glyph_name: glyph_name,
            ),
            self.assertRaisesRegex(
                ValueError,
                "Conflicting novel katakana groups",
            ),
        ):
            _novel_katakana_mappings(
                Mock(),
                {0x30A2: "shared", 0x30A4: "shared"},
                {},
                {},
                {},
            )

        with (
            patch(
                "nobigoe_font.pipeline._font_operations.vertical_glyph_or_self",
                return_value="shared.vert",
            ),
            self.assertRaisesRegex(
                ValueError,
                "Conflicting novel katakana groups",
            ),
        ):
            _novel_katakana_mappings(
                Mock(),
                {0x30A2: "katakana-a", 0x30A4: "katakana-i"},
                {},
                {},
                {},
            )

    def test_hiragana_mapping_preserves_ka_identity_for_all_derivatives(
        self,
    ) -> None:
        cmap = {
            ord("か"): "ka",
            ord("が"): "ga",
            ord("き"): "ki",
        }
        mark_outputs = {
            (ord("か"), 0x3099): "ka.comb",
        }
        with patch(
            "nobigoe_font.pipeline._font_operations.vertical_glyph_or_self",
            side_effect=lambda _font, glyph_name: glyph_name,
        ):
            (
                horizontal,
                vertical,
                vertical_codepoints,
                vertical_marked,
                horizontal_codepoints,
            ) = _novel_hiragana_mappings(
                Mock(),
                cmap,
                mark_outputs,
                {},
                {},
            )

        self.assertEqual(
            {name: horizontal[name] for name in ("ka", "ga", "ka.comb", "ki")},
            {
                "ka": "normal",
                "ga": "normal",
                "ka.comb": "normal",
                "ki": "normal",
            },
        )
        self.assertEqual(
            horizontal_codepoints,
            {
                "ka": ord("か"),
                "ga": ord("が"),
                "ka.comb": ord("か"),
                "ki": ord("き"),
            },
        )
        self.assertEqual(vertical, {})
        self.assertEqual(vertical_codepoints, {})
        self.assertEqual(vertical_marked, frozenset())

    def test_complete_katakana_mappings_and_novel_apply_order(self) -> None:
        self.assertEqual(len(KATAKANA_SOURCE_CODEPOINTS), 109)
        target_pairs = tuple(
            pair for pair in MANGA_MARK_PAIRS if pair[0] in KATAKANA_CODEPOINTS
        )
        self.assertEqual(len(target_pairs), 93)

        cmap = {
            codepoint: f"encoded.{codepoint:05X}"
            for codepoint in KATAKANA_SOURCE_CODEPOINTS
        }
        excluded_names = {
            0x30FB: "excluded.middle-dot",
            0x30FC: "excluded.choon",
            0xFF71: "excluded.halfwidth-a",
        }
        cmap.update(excluded_names)
        mark_outputs = {
            pair: (f"native.ccmp.{index}" if index < 14 else f"generated.ccmp.{index}")
            for index, pair in enumerate(target_pairs)
        }
        mark_outputs[CHOON_DAKUTEN_PAIR] = "excluded.choon.ccmp"
        vertical_mark_outputs = {
            pair: f"{glyph_name}.vert" for pair, glyph_name in mark_outputs.items()
        }
        generated_small = ("generated.small-ko", "generated.small-ko.vert")
        missing_small_glyphs = {0x1B155: generated_small}
        no_distinct_vertical = 0x30FF

        def vertical_glyph_or_self(_font, glyph_name):
            if glyph_name == cmap[no_distinct_vertical]:
                return glyph_name
            return f"{glyph_name}.vert"

        with patch(
            "nobigoe_font.pipeline._font_operations.vertical_glyph_or_self",
            side_effect=vertical_glyph_or_self,
        ):
            katakana_mappings = _novel_katakana_mappings(
                Mock(),
                cmap,
                mark_outputs,
                vertical_mark_outputs,
                missing_small_glyphs,
            )

        horizontal, vertical, vertical_codepoints, vertical_marked = katakana_mappings
        self.assertEqual(len(horizontal), 203)
        self.assertEqual(len(vertical), 202)
        self.assertFalse(horizontal.keys() & vertical.keys())
        self.assertEqual(horizontal[cmap[0x30A2]], "curve")
        self.assertEqual(horizontal[cmap[0x31F7]], "small")
        self.assertEqual(horizontal[generated_small[0]], "small")
        core_pair = (0x30A2, 0x3099)
        self.assertEqual(horizontal[mark_outputs[core_pair]], "curve")
        self.assertEqual(
            vertical[vertical_mark_outputs[core_pair]],
            "curve",
        )
        self.assertEqual(
            vertical_codepoints[vertical_mark_outputs[core_pair]],
            0x30A2,
        )
        self.assertIn(vertical_mark_outputs[core_pair], vertical_marked)
        self.assertEqual(vertical[generated_small[1]], "small")
        self.assertEqual(vertical_codepoints[generated_small[1]], 0x1B155)
        for excluded_name in (*excluded_names.values(), "excluded.choon.ccmp"):
            self.assertNotIn(excluded_name, horizontal)
            self.assertNotIn(excluded_name, vertical)

        hiragana_mappings = (
            {"hiragana": "normal"},
            {"hiragana.vert": "normal"},
            {"hiragana.vert": 0x3042},
            frozenset(),
            {"hiragana": 0x3042},
        )
        font = Mock()
        calls = Mock()
        with (
            patch("nobigoe_font.pipeline.apply_novel_hiragana") as hiragana,
            patch("nobigoe_font.pipeline.apply_novel_katakana") as katakana,
            patch("nobigoe_font.pipeline.apply_novel_han") as han,
        ):
            calls.attach_mock(hiragana, "hiragana")
            calls.attach_mock(katakana, "katakana")
            calls.attach_mock(han, "han")
            _apply_novel_style(
                font,
                400,
                "novel",
                hiragana_mappings,
                katakana_mappings,
            )

        hiragana.assert_called_once_with(
            font,
            400,
            *hiragana_mappings[:4],
            horizontal_codepoints=hiragana_mappings[4],
        )
        katakana.assert_called_once_with(font, 400, *katakana_mappings)
        han.assert_called_once_with(font)
        self.assertEqual(
            [call[0] for call in calls.mock_calls],
            ["hiragana", "katakana", "han"],
        )

    def test_default_and_koburi_styles_do_not_apply_novel_transforms(self) -> None:
        font = Mock()
        with (
            patch("nobigoe_font.pipeline.apply_novel_hiragana") as hiragana,
            patch("nobigoe_font.pipeline.apply_novel_katakana") as katakana,
            patch("nobigoe_font.pipeline.apply_novel_han") as han,
        ):
            _apply_novel_style(font, 400, "noto")
            with self.assertRaisesRegex(
                ValueError,
                "--kana-style novel requires --base noto",
            ):
                build(
                    Path("source.otf"),
                    None,
                    Path("punctuation.otf"),
                    Path("output.otf"),
                    Mock(),
                    Mock(),
                    0,
                    "koburi",
                    kana_style="novel",
                )

        hiragana.assert_not_called()
        katakana.assert_not_called()
        han.assert_not_called()


if __name__ == "__main__":
    unittest.main()
