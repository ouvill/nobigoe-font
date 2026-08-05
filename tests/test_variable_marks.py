from __future__ import annotations

import math
import unittest
from itertools import pairwise
from pathlib import Path
from unittest.mock import Mock, call, patch

import pathops
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from nobigoe_font import geometry
from nobigoe_font.features import (
    consolidate_vrt2_lookups,
    punctuation_feature_source,
    symbol_feature_source,
)
from nobigoe_font.operations import feature_ligatures, feature_single_substitutions
from nobigoe_font.profiles import (
    NOTO_WEIGHT_CLASSES,
    default_output_path,
    font_identity,
    latin_build_profile,
    latin_font_source,
    noto_serif_cff2_variable_source,
    shippori_source,
)
from nobigoe_font.punctuation import (
    MANGA_PUNCTUATION_SEQUENCES,
    PUNCTUATION_VARIANT_SEQUENCES,
    rotate_punctuation_outline,
    make_original_punctuation_ligature,
    make_variable_shippori_punctuation_ligature,
)
from nobigoe_font.variable_cli import (
    DEFAULT_NOVEL_OUTPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    main,
)
from nobigoe_font.variable_marks import (
    _cap_cut_span,
    _DeltaModel,
    _normalize_vertical_parts,
    _scalar,
    _split_caps,
    _split_horizontal_parts,
    _split_vertical_parts,
)


class VariableMarkInterpolationTests(unittest.TestCase):
    def test_reviewed_values_round_trip_through_cff2_regions(self) -> None:
        locations = (0.0, 0.1, 0.25, 0.4, 0.6, 0.8, 1.0)
        supports = tuple(
            (locations[index - 1], locations[index], locations[index + 1])
            for index in range(1, 6)
        )
        values = (40.0, 52.0, 49.0, 68.0, 61.0, 89.0, 100.0)
        model = _DeltaModel(locations, supports)

        deltas = model.getDeltas(values, round=lambda value: value)

        for location, expected in zip(locations, values, strict=True):
            actual = deltas[0] + deltas[1] * location
            actual += sum(
                delta * _scalar(location, support)
                for delta, support in zip(deltas[2:], supports, strict=True)
            )
            self.assertAlmostEqual(actual, expected)


class VariableSymbolTests(unittest.TestCase):
    @staticmethod
    def _oval(y_min: float, y_max: float) -> pathops.Path:
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, (y_min + y_max) / 2))
        pen.curveTo((200, y_min), (800, y_min), (900, (y_min + y_max) / 2))
        pen.curveTo((800, y_max), (200, y_max), (100, (y_min + y_max) / 2))
        pen.closePath()
        return path

    @staticmethod
    def _vertical_oval(y_min: float, y_max: float) -> pathops.Path:
        center_y = (y_min + y_max) / 2
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo((100, center_y))
        pen.curveTo((100, y_max), (300, y_max), (500, y_max))
        pen.curveTo((700, y_max), (900, y_max), (900, center_y))
        pen.curveTo((900, y_min), (700, y_min), (500, y_min))
        pen.curveTo((300, y_min), (100, y_min), (100, center_y))
        pen.closePath()
        return path

    def assertSameFill(self, actual: pathops.Path, expected: pathops.Path) -> None:
        difference = pathops.op(actual, expected, pathops.PathOp.XOR)
        self.assertEqual(sum(abs(contour.area) for contour in difference.contours), 0)

    def assertJoined(
        self,
        parts: tuple[pathops.Path, pathops.Path, pathops.Path],
        axis: str,
    ) -> None:
        start_contours = list(parts[0].contours)
        end_contours = list(parts[2].contours)
        pairs = (
            (start_contours[0], start_contours[1]),
            (end_contours[1], end_contours[0]),
        )
        for cap, bar in pairs:
            bar_span = (
                (bar.bounds[1], bar.bounds[3])
                if axis == "horizontal"
                else (bar.bounds[0], bar.bounds[2])
            )
            self.assertEqual(_cap_cut_span(cap, axis), bar_span)
        if axis == "horizontal":
            self.assertGreaterEqual(
                start_contours[0].bounds[2], start_contours[1].bounds[0]
            )
            self.assertLessEqual(end_contours[1].bounds[0], end_contours[0].bounds[2])
        else:
            self.assertLessEqual(
                start_contours[0].bounds[1], start_contours[1].bounds[3]
            )
            self.assertGreaterEqual(
                end_contours[1].bounds[3], end_contours[0].bounds[1]
            )

    def test_choon_terminals_split_source_curves_without_changing_fill(self) -> None:
        horizontal_sources = (self._oval(300, 500), self._oval(250, 550))
        vertical_sources = (
            self._vertical_oval(250, 650),
            self._vertical_oval(200, 700),
        )
        horizontal = [
            _split_horizontal_parts(source, 1000) for source in horizontal_sources
        ]
        vertical = _normalize_vertical_parts(
            [_split_vertical_parts(source, 1000, 880) for source in vertical_sources]
        )

        for source, parts in zip(horizontal_sources, horizontal, strict=True):
            low, high = _split_caps(source, "horizontal", 500)
            self.assertSameFill(
                low,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, -4096, 500, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertSameFill(
                high,
                pathops.op(
                    source,
                    geometry.rectangle(500, -4096, 4096, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertJoined(parts, "horizontal")
            self.assertGreaterEqual(parts[0].bounds[2], 1008)
            self.assertEqual(parts[1].bounds[0::2], (-8, 1008))
            self.assertLessEqual(parts[2].bounds[0], -8)
        for source, parts in zip(vertical_sources, vertical, strict=True):
            low, high = _split_caps(source, "vertical", 400)
            self.assertSameFill(
                low,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, -4096, 4096, 400),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertSameFill(
                high,
                pathops.op(
                    source,
                    geometry.rectangle(-4096, 400, 4096, 4096),
                    pathops.PathOp.INTERSECTION,
                ),
            )
            self.assertJoined(parts, "vertical")
            self.assertLessEqual(parts[0].bounds[1], -128)
            self.assertEqual(parts[1].bounds[1::2], (-128, 888))
            self.assertGreaterEqual(parts[2].bounds[3], 888)

        for parts_by_master in (horizontal, vertical):
            for index, contour_count in enumerate((2, 1, 2)):
                verbs = [tuple(parts[index].verbs) for parts in parts_by_master]
                self.assertEqual(verbs[0], verbs[1])
                self.assertTrue(
                    all(
                        sum(1 for _ in parts[index].contours) == contour_count
                        for parts in parts_by_master
                    )
                )

    def test_symbol_features_compile_to_expected_gsub_contracts(self) -> None:
        extensions = [
            ("choon", "choon", "choon.v", [f"choon{i}" for i in range(6)]),
            ("dash", "dash", "dash.v", [f"dash{i}" for i in range(6)]),
        ]
        wave = ("wave", "wave", "wave.v", [f"wave{i}" for i in range(10)])
        relaxed = (
            "relaxed",
            "wave",
            "wave.v",
            [f"relaxed{i}" for i in range(20)],
        )
        one_cycle = (
            "one-cycle",
            "wave",
            "wave.v",
            [f"one-cycle{i}" for i in range(8)],
        )
        manga = ("manga", "manga", [f"manga{i}" for i in range(11)])
        transition = ("transition", [f"transition{i}" for i in range(8)])
        reverse_transition = (
            "reverse-transition",
            [f"reverse-transition{i}" for i in range(8)],
        )
        linear_transitions = [
            (
                f"{prefix}-transition",
                [f"{prefix}-transition{index}" for index in range(12)],
            )
            for prefix in ("choon", "dash")
        ]
        linear_manga_transitions = [
            (
                f"{prefix}-manga-transition",
                [f"{prefix}-manga-transition{index}" for index in range(10)],
            )
            for prefix in ("choon", "dash")
        ]
        glyph_order = [
            ".notdef",
            "choon",
            "choon.v",
            "dash",
            "dash.v",
            "wave",
            "wave.v",
            "manga",
            *(name for extension in extensions for name in extension[3]),
            *wave[3],
            *relaxed[3],
            *manga[2],
            *one_cycle[3],
            *transition[1],
            *reverse_transition[1],
            *(
                name
                for _, transition_names in linear_transitions
                for name in transition_names
            ),
            *(
                name
                for _, transition_names in linear_manga_transitions
                for name in transition_names
            ),
        ]
        font = TTFont()
        font.setGlyphOrder(glyph_order)

        addOpenTypeFeaturesFromString(
            font,
            symbol_feature_source(
                extensions,
                wave,
                relaxed,
                manga,
                one_cycle,
                transition,
                reverse_transition,
                linear_transitions,
                linear_manga_transitions,
            ),
            tables={"GSUB"},
        )
        consolidate_vrt2_lookups(font)

        feature_tags = {
            record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord
        }
        self.assertEqual(feature_tags, {"ss04", "ss05", "calt", "vert", "vrt2"})
        self.assertEqual(feature_ligatures(font, "ccmp"), {})
        self.assertEqual(feature_ligatures(font, "liga"), {})
        expected_vertical = {
            "choon0": "choon3",
            "wave0": "wave5",
            "one-cycle0": "one-cycle4",
            "manga": "manga5",
            "manga0": "manga6",
            "manga3": "manga9",
            "manga4": "manga10",
            "transition0": "transition4",
            "transition3": "transition7",
            "reverse-transition0": "reverse-transition4",
            "reverse-transition3": "reverse-transition7",
            "choon-transition0": "choon-transition6",
            "choon-transition5": "choon-transition11",
            "choon-manga-transition0": "choon-manga-transition5",
            "choon-manga-transition4": "choon-manga-transition9",
        }
        for tag in ("vert", "vrt2"):
            substitutions = feature_single_substitutions(font, tag)
            self.assertEqual(
                {name: substitutions[name] for name in expected_vertical},
                expected_vertical,
            )
        vrt2_records = [
            record
            for record in font["GSUB"].table.FeatureList.FeatureRecord
            if record.FeatureTag == "vrt2"
        ]
        self.assertTrue(vrt2_records)
        self.assertTrue(
            all(len(record.Feature.LookupListIndex) == 1 for record in vrt2_records)
        )
        vrt2_index = vrt2_records[0].Feature.LookupListIndex[0]
        vrt2_lookup = font["GSUB"].table.LookupList.Lookup[vrt2_index]
        self.assertEqual(vrt2_lookup.LookupType, 1)
        self.assertEqual(vrt2_lookup.LookupFlag, 0)
        self.assertEqual(len(vrt2_lookup.SubTable), 1)

    def test_vrt2_lookups_are_consolidated_for_windows_cff_loading(self) -> None:
        font = TTFont()
        font.setGlyphOrder([".notdef", "a", "b", "c"])
        addOpenTypeFeaturesFromString(
            font,
            """
            languagesystem DFLT dflt;
            lookup first {
                sub a by b;
            } first;
            lookup second {
                sub b by c;
            } second;
            feature vrt2 {
                lookup first;
                lookup second;
            } vrt2;
            """,
            tables={"GSUB"},
        )

        consolidate_vrt2_lookups(font)

        record = next(
            record
            for record in font["GSUB"].table.FeatureList.FeatureRecord
            if record.FeatureTag == "vrt2"
        )
        self.assertEqual(len(record.Feature.LookupListIndex), 1)
        lookup = font["GSUB"].table.LookupList.Lookup[
            record.Feature.LookupListIndex[0]
        ]
        self.assertEqual(lookup.LookupType, 1)
        self.assertEqual(lookup.LookupFlag, 0)
        self.assertEqual(len(lookup.SubTable), 1)
        self.assertEqual(lookup.SubTable[0].mapping, {"a": "c", "b": "c"})


def _cubic_ellipse(
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    segment_count: int,
) -> pathops.Path:
    step = 2 * math.pi / segment_count
    control_scale = 4 / 3 * math.tan(step / 4)
    result = pathops.Path()
    pen = result.getPen()
    start_angle = -math.pi / 2
    start = (
        center_x + radius_x * math.cos(start_angle),
        center_y + radius_y * math.sin(start_angle),
    )
    pen.moveTo(start)
    for index in range(segment_count):
        segment_start_angle = start_angle + index * step
        end_angle = segment_start_angle + step
        end = (
            center_x + radius_x * math.cos(end_angle),
            center_y + radius_y * math.sin(end_angle),
        )
        pen.curveTo(
            (
                center_x
                + radius_x
                * (
                    math.cos(segment_start_angle)
                    - control_scale * math.sin(segment_start_angle)
                ),
                center_y
                + radius_y
                * (
                    math.sin(segment_start_angle)
                    + control_scale * math.cos(segment_start_angle)
                ),
            ),
            (
                center_x
                + radius_x
                * (math.cos(end_angle) + control_scale * math.sin(end_angle)),
                center_y
                + radius_y
                * (math.sin(end_angle) - control_scale * math.cos(end_angle)),
            ),
            end,
        )
    pen.closePath()
    return result


def _shippori_punctuation_fixture() -> dict[str, pathops.Path]:
    outlines = {}
    for mark, radius_x, segment_count in (
        ("?", 170, 14),
        ("!", 60, 6),
    ):
        outline = _cubic_ellipse(500, 480, radius_x, 300, segment_count)
        outline.addPath(geometry.rectangle(455, -12, 545, 80))
        outlines[mark] = outline
    return outlines


class VariablePunctuationTests(unittest.TestCase):
    def test_original_masters_keep_topology_and_aligned_height(self) -> None:
        weights = (200, 300, 400, 500, 600, 700, 900)
        for sans in (False, True):
            for sequence in PUNCTUATION_VARIANT_SEQUENCES:
                with self.subTest(sans=sans, sequence=sequence):
                    masters = [
                        make_original_punctuation_ligature(
                            sequence,
                            weight,
                            sans=sans,
                        )
                        for weight in weights
                    ]
                    signatures = {
                        (
                            tuple(master.verbs),
                            len(master.points),
                            sum(1 for _ in master.contours),
                        )
                        for master in masters
                    }
                    self.assertEqual(len(signatures), 1)
                    for master in masters:
                        self.assertAlmostEqual(master.bounds[1], -30, places=4)
                        self.assertAlmostEqual(master.bounds[3], 790, places=4)

    def test_original_serif_ligatures_keep_shared_dots_circular(self) -> None:
        for weight in (200, 300, 400, 500, 600, 700, 900):
            for sequence in PUNCTUATION_VARIANT_SEQUENCES:
                outline = make_original_punctuation_ligature(sequence, weight)
                contours = list(outline.contours)
                self.assertEqual(len(contours), len(sequence) * 2)
                for dot in contours[1::2]:
                    width = dot.bounds[2] - dot.bounds[0]
                    height = dot.bounds[3] - dot.bounds[1]
                    self.assertAlmostEqual(width, height, places=4)

    def test_rotated_punctuation_preserves_contours_and_aligns_edges(self) -> None:
        source = geometry.rectangle(450, 160, 550, 790)
        source.addPath(geometry.rectangle(450, -30, 550, 80))

        rotated = rotate_punctuation_outline(source)
        body, dot = list(rotated.contours)
        cosine = math.cos(math.radians(10))
        sine = math.sin(math.radians(10))

        self.assertAlmostEqual(body.bounds[3], 790)
        self.assertAlmostEqual(dot.bounds[1], -30)
        self.assertAlmostEqual(
            body.bounds[2] - body.bounds[0],
            100 * cosine + 630 * sine,
            places=3,
        )
        self.assertAlmostEqual(
            dot.bounds[3] - dot.bounds[1],
            100 * sine + 110 * cosine,
            places=3,
        )
        self.assertAlmostEqual(abs(body.area), 100 * 630, places=2)
        self.assertAlmostEqual(abs(dot.area), 100 * 110, places=2)

    def test_rotated_ligature_edges_share_parallel_guides(self) -> None:
        source = make_original_punctuation_ligature("!!??", 400)

        rotated = rotate_punctuation_outline(source)
        body_tops = {
            round(contour.bounds[3], 3)
            for contour in rotated.contours
            if contour.bounds[3] >= 140
        }
        dot_bottoms = {
            round(contour.bounds[1], 3)
            for contour in rotated.contours
            if contour.bounds[3] < 140
        }

        self.assertEqual(body_tops, {790})
        self.assertEqual(dot_bottoms, {-30})

    def test_rotated_mixed_pairs_restore_source_body_gaps(self) -> None:
        gaps = []
        for sequence in ("!?", "?!"):
            source = make_original_punctuation_ligature(sequence, 400)
            source_bodies = sorted(
                (contour for contour in source.contours if contour.bounds[3] >= 140),
                key=lambda contour: contour.bounds[0],
            )
            expected = source_bodies[1].bounds[0] - source_bodies[0].bounds[2]

            rotated = rotate_punctuation_outline(source)
            rotated_bodies = sorted(
                (contour for contour in rotated.contours if contour.bounds[3] >= 140),
                key=lambda contour: contour.bounds[0],
            )
            actual = rotated_bodies[1].bounds[0] - rotated_bodies[0].bounds[2]
            self.assertAlmostEqual(actual, expected, places=3)
            gaps.append(actual)

        self.assertAlmostEqual(gaps[0], gaps[1], delta=4)

    def test_rotated_five_exclamations_fit_with_positive_equal_gaps(self) -> None:
        for sans in (False, True):
            for weight in (200, 400, 900):
                source = make_original_punctuation_ligature(
                    "!!!!!",
                    weight,
                    sans=sans,
                )
                rotated = rotate_punctuation_outline(source)
                bodies = sorted(
                    (
                        contour
                        for contour in rotated.contours
                        if contour.bounds[3] >= 140
                    ),
                    key=lambda contour: contour.bounds[0],
                )
                gaps = [
                    following.bounds[0] - previous.bounds[2]
                    for previous, following in zip(bodies, bodies[1:])
                ]
                span = bodies[-1].bounds[2] - bodies[0].bounds[0]

                with self.subTest(sans=sans, weight=weight):
                    self.assertLessEqual(span, 960.001)
                    self.assertGreater(min(gaps), 0)
                    self.assertAlmostEqual(max(gaps), min(gaps), places=3)

    def test_rotated_punctuation_preserves_variable_master_topology(self) -> None:
        for sans in (False, True):
            for sequence in PUNCTUATION_VARIANT_SEQUENCES:
                signatures = set()
                for weight in (200, 400, 900):
                    outline = make_original_punctuation_ligature(
                        sequence,
                        weight,
                        sans=sans,
                    )
                    designed = rotate_punctuation_outline(outline)
                    signatures.add(
                        (
                            tuple(designed.verbs),
                            len(designed.points),
                            sum(1 for _ in designed.contours),
                        )
                    )
                with self.subTest(sans=sans, sequence=sequence):
                    self.assertEqual(len(signatures), 1)

    def test_five_exclamations_fill_the_optical_cell(self) -> None:
        for weight in (200, 300, 400, 500, 600, 700, 900):
            outline = make_original_punctuation_ligature("!!!!!", weight)
            width = outline.bounds[2] - outline.bounds[0]
            self.assertGreaterEqual(width, 800)
            self.assertLessEqual(width, 900)

    def test_variable_shippori_ligatures_use_smooth_cubic_bodies(self) -> None:
        sources = _shippori_punctuation_fixture()
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value=sources,
        ):
            for weight in (200, 300, 400, 500, 600, 700, 900):
                outlines = {
                    mark: make_variable_shippori_punctuation_ligature(
                        Mock(),
                        mark,
                        weight,
                        0,
                    )
                    for mark in ("!", "?")
                }
                for mark, outline in outlines.items():
                    with self.subTest(weight=weight, mark=mark):
                        body, dot = list(outline.contours)
                        recording = RecordingPen()
                        body.draw(recording)
                        operations = [operation for operation, _ in recording.value]
                        self.assertEqual(operations[0], "moveTo")
                        self.assertEqual(operations[-1], "closePath")
                        self.assertEqual(
                            operations.count("curveTo"),
                            6 if mark == "!" else 18,
                        )
                        self.assertNotIn("lineTo", operations)
                        dot_width = dot.bounds[2] - dot.bounds[0]
                        dot_height = dot.bounds[3] - dot.bounds[1]
                        self.assertAlmostEqual(dot_width, dot_height, places=4)
                        self.assertAlmostEqual(dot.bounds[3], 80, places=4)
                exclamation_body = next(iter(outlines["!"].contours))
                question_body = next(iter(outlines["?"].contours))
                self.assertGreater(
                    abs(question_body.area),
                    abs(exclamation_body.area),
                )

    def test_variable_question_dot_centers_on_terminal_axis(self) -> None:
        sources = _shippori_punctuation_fixture()
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value=sources,
        ):
            for weight in (200, 300, 400, 500, 600, 700, 900):
                outline = make_variable_shippori_punctuation_ligature(
                    Mock(),
                    "?",
                    weight,
                    0,
                )
                body, dot = list(outline.contours)
                recording = RecordingPen()
                body.draw(recording)
                terminal_x = recording.value[0][1][0][0]
                dot_center_x = (dot.bounds[0] + dot.bounds[2]) / 2
                self.assertAlmostEqual(dot_center_x, terminal_x, places=4)

    def test_variable_source_bodies_balance_against_kanji_stems(self) -> None:
        sources = _shippori_punctuation_fixture()
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value=sources,
        ):
            for mark in ("!", "?"):
                outline = make_variable_shippori_punctuation_ligature(
                    Mock(),
                    mark,
                    400,
                    0,
                )
                body = next(iter(outline.contours))
                source_body = next(
                    contour
                    for contour in sources[mark].contours
                    if contour.bounds[3] >= 200
                )
                self.assertAlmostEqual(body.bounds[1], source_body.bounds[1], places=4)
                self.assertAlmostEqual(body.bounds[3], source_body.bounds[3], places=4)
                self.assertLess(body.area, source_body.area)

    def test_variable_source_weight_correction_preserves_vertical_bounds(
        self,
    ) -> None:
        sources = _shippori_punctuation_fixture()
        adjustment = 5
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value=sources,
        ):
            for mark in ("!", "?"):
                outline = make_variable_shippori_punctuation_ligature(
                    Mock(),
                    mark,
                    400,
                    adjustment,
                )
                body = next(iter(outline.contours))
                source_body = next(
                    contour
                    for contour in sources[mark].contours
                    if contour.bounds[3] >= 200
                )
                self.assertAlmostEqual(
                    body.bounds[1],
                    source_body.bounds[1] - adjustment,
                    places=4,
                )
                self.assertAlmostEqual(
                    body.bounds[3],
                    source_body.bounds[3] + adjustment,
                    places=4,
                )

    def test_variable_question_kanji_balance_keeps_inner_curve_tangent(
        self,
    ) -> None:
        sources = _shippori_punctuation_fixture()
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value=sources,
        ):
            for weight in (300, 400, 500, 600, 700, 900):
                outline = make_variable_shippori_punctuation_ligature(
                    Mock(),
                    "?",
                    weight,
                    0,
                )
                body = next(iter(outline.contours))
                recording = RecordingPen()
                body.draw(recording)
                current = None
                segments = []
                for operation, points in recording.value:
                    if operation == "moveTo":
                        current = points[0]
                    elif operation == "curveTo":
                        self.assertIsNotNone(current)
                        control_1, control_2, end = points
                        segments.append((current, control_1, control_2, end))
                        current = end
                for previous, following in pairwise(segments[10:18]):
                    incoming = (
                        previous[3][0] - previous[2][0],
                        previous[3][1] - previous[2][1],
                    )
                    outgoing = (
                        following[1][0] - following[0][0],
                        following[1][1] - following[0][1],
                    )
                    cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
                    lengths = math.hypot(*incoming) * math.hypot(*outgoing)
                    self.assertAlmostEqual(cross / lengths, 0, delta=1e-5)
                    self.assertGreater(
                        incoming[0] * outgoing[0] + incoming[1] * outgoing[1],
                        0,
                    )

    def test_variable_question_inner_curve_is_c2_continuous(self) -> None:
        source = geometry.rectangle(450, 200, 550, 760)
        source.addPath(geometry.rectangle(455, -12, 545, 80))
        with patch(
            "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
            return_value={"!": source, "?": source},
        ):
            outline = make_variable_shippori_punctuation_ligature(
                Mock(),
                "?",
                200,
                0,
            )
            body = next(iter(outline.contours))
            recording = RecordingPen()
            body.draw(recording)
            current = None
            segments = []
            for operation, points in recording.value:
                if operation == "moveTo":
                    current = points[0]
                elif operation == "curveTo":
                    self.assertIsNotNone(current)
                    control_1, control_2, end = points
                    segments.append((current, control_1, control_2, end))
                    current = end
            inner_segments = segments[11:16]
            for previous, following in pairwise(inner_segments):
                previous_height = abs(previous[3][1] - previous[0][1])
                following_height = abs(following[3][1] - following[0][1])
                previous_second_derivative = (
                    previous[3][0] - 2 * previous[2][0] + previous[1][0]
                ) / previous_height**2
                following_second_derivative = (
                    following[0][0] - 2 * following[1][0] + following[2][0]
                ) / following_height**2
                self.assertAlmostEqual(
                    previous_second_derivative,
                    following_second_derivative,
                    places=6,
                )

    def test_five_variable_exclamations_repeat_across_cell_boundaries(
        self,
    ) -> None:
        source = pathops.Path()
        for center in (140, 320, 500, 680, 860):
            source.addPath(geometry.rectangle(center - 30, 200, center + 30, 760))
            source.addPath(geometry.rectangle(center - 45, -12, center + 45, 80))
        punctuation_sources = _shippori_punctuation_fixture()
        with (
            patch(
                "nobigoe_font.punctuation.make_punctuation_ligature",
                return_value=source,
            ),
            patch(
                "nobigoe_font.punctuation.shippori_upright_punctuation_paths",
                return_value=punctuation_sources,
            ),
        ):
            for weight in (200, 300, 400, 500, 600, 700, 900):
                outline = make_variable_shippori_punctuation_ligature(
                    Mock(),
                    "!!!!!",
                    weight,
                    0,
                )
                contours = list(outline.contours)
                bodies = contours[0::2]
                dots = contours[1::2]
                expected_centers = (100, 300, 500, 700, 900)
                for components in (bodies, dots):
                    centers = tuple(
                        (component.bounds[0] + component.bounds[2]) / 2
                        for component in components
                    )
                    for center, expected in zip(centers, expected_centers, strict=True):
                        self.assertAlmostEqual(center, expected, places=3)
                    gaps = [
                        following.bounds[0] - previous.bounds[2]
                        for previous, following in pairwise(components)
                    ]
                    boundary_gap = (
                        components[0].bounds[0] + 1000 - components[-1].bounds[2]
                    )
                    for gap in gaps:
                        self.assertAlmostEqual(gap, boundary_gap, places=3)

    def test_original_punctuation_features_compile_to_expected_contracts(
        self,
    ) -> None:
        variants = [
            (
                sequence,
                tuple(f"punctuation{index}_{variant}" for variant in range(4)),
            )
            for index, sequence in enumerate(PUNCTUATION_VARIANT_SEQUENCES)
        ]
        font = TTFont()
        font.setGlyphOrder(
            [".notdef", *(name for _, names in variants for name in names)]
        )

        addOpenTypeFeaturesFromString(
            font,
            punctuation_feature_source(variants),
            tables={"GSUB"},
        )

        feature_tags = {
            record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord
        }
        self.assertEqual(feature_tags, {"aalt", "ccmp", "ss01", "ss02", "ss03"})
        names = dict(variants)
        ligatures = feature_ligatures(font, "ccmp")
        inputs = {"!": names["!"][0], "?": names["?"][0]}
        expected = {
            tuple(inputs[mark] for mark in sequence): names[sequence][0]
            for sequence in MANGA_PUNCTUATION_SEQUENCES
        }
        self.assertEqual(ligatures, expected)
        for variant, tag in enumerate(("ss01", "ss02", "ss03"), 1):
            self.assertEqual(
                feature_single_substitutions(font, tag),
                {names[sequence][0]: names[sequence][variant] for sequence in names},
            )


class VariableBuildCliTests(unittest.TestCase):
    def test_variable_source_is_pinned_to_the_noto_cff2_subset(self) -> None:
        source = noto_serif_cff2_variable_source()

        self.assertEqual(source.filename, "NotoSerifJP-VF.otf")
        self.assertTrue(
            source.url.endswith("/Serif/Variable/OTF/Subset/NotoSerifJP-VF.otf")
        )
        self.assertEqual(
            source.sha256,
            "39701fd096bc51204a8444c6c2659f007b29674a13eb62ddfa470638fe8179cd",
        )

    def test_local_noto_source_builds_novel_directly_from_custom_cff2(
        self,
    ) -> None:
        cached = Path("cache/font.otf")
        with (
            patch(
                "nobigoe_font.variable_cli.SourceCache.fetch",
                return_value=cached,
            ) as fetch,
            patch(
                "nobigoe_font.variable_cli.variable_marks.build_variable_marks"
            ) as build_variable,
            patch(
                "nobigoe_font.variable_cli.build_variable_novel"
            ) as build_novel_variable,
            patch(
                "nobigoe_font.variable_cli.pipeline.build_static_instance"
            ) as build_static,
            patch(
                "nobigoe_font.variable_cli.pipeline.build_novel_static_instance"
            ) as build_novel,
        ):
            main(
                [
                    "--source",
                    "source.otf",
                    "--output",
                    "custom.otf",
                    "--novel-output",
                    "novel.otf",
                    "--static-output-dir",
                    "static",
                    "--static-weight",
                    "Regular",
                    "--face",
                    "2",
                    "--autohint",
                ]
            )

        self.assertEqual(
            [item.args[0] for item in fetch.call_args_list],
            [
                *(shippori_source(style) for style in NOTO_WEIGHT_CLASSES),
                latin_font_source("libertinus", "Regular"),
            ],
        )
        build_variable.assert_called_once_with(
            Path("source.otf"),
            Path("custom.otf"),
            2,
            {weight: cached for weight in NOTO_WEIGHT_CLASSES.values()},
        )
        build_novel_variable.assert_called_once_with(
            Path("custom.otf"),
            Path("novel.otf"),
        )
        identity = font_identity("noto", "Regular")
        self.assertEqual(
            build_static.call_args_list,
            [
                call(
                    Path("custom.otf"),
                    cached,
                    Path("static") / default_output_path(identity, "noto").name,
                    identity,
                    latin_build_profile("libertinus", "Regular"),
                    True,
                )
            ],
        )
        novel_identity = font_identity("noto", "Regular", "novel")
        self.assertEqual(
            build_novel.call_args_list,
            [
                call(
                    Path("novel.otf"),
                    cached,
                    Path("static") / default_output_path(novel_identity, "noto").name,
                    novel_identity,
                    latin_build_profile("libertinus", "Regular"),
                    True,
                )
            ],
        )

    def test_default_build_uses_only_pinned_cff2_punctuation_and_latin_sources(
        self,
    ) -> None:
        cached = Path("cache/font.otf")
        with (
            patch(
                "nobigoe_font.variable_cli.SourceCache.fetch", return_value=cached
            ) as fetch,
            patch(
                "nobigoe_font.variable_cli.variable_marks.build_variable_marks"
            ) as build_variable,
            patch(
                "nobigoe_font.variable_cli.build_variable_novel"
            ) as build_novel_variable,
            patch(
                "nobigoe_font.variable_cli.pipeline.build_static_instance"
            ) as build_static,
            patch(
                "nobigoe_font.variable_cli.pipeline.build_novel_static_instance"
            ) as build_novel,
        ):
            main([])

        self.assertEqual(
            [item.args[0] for item in fetch.call_args_list],
            [
                noto_serif_cff2_variable_source(),
                *(shippori_source(style) for style in NOTO_WEIGHT_CLASSES),
                *(
                    latin_font_source("libertinus", style)
                    for style in NOTO_WEIGHT_CLASSES
                ),
            ],
        )
        build_variable.assert_called_once_with(
            cached,
            DEFAULT_OUTPUT_PATH,
            0,
            {weight: cached for weight in NOTO_WEIGHT_CLASSES.values()},
        )
        build_novel_variable.assert_called_once_with(
            DEFAULT_OUTPUT_PATH,
            DEFAULT_NOVEL_OUTPUT_PATH,
        )
        self.assertEqual(len(build_static.call_args_list), len(NOTO_WEIGHT_CLASSES))
        self.assertEqual(len(build_novel.call_args_list), len(NOTO_WEIGHT_CLASSES))


if __name__ == "__main__":
    unittest.main()
