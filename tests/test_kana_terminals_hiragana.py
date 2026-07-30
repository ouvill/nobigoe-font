from __future__ import annotations

import unittest

import pathops
from fontTools.pens.basePen import AbstractPen
from fontTools.pens.recordingPen import RecordingPen

from nobigoe_font.kana_terminals import soften_kana_terminals


Point = tuple[float, float]
Command = tuple[str, tuple[Point, ...]]


def _draw_curved_terminal(
    pen: AbstractPen,
    *,
    origin: Point,
    stroke_length: float,
    cap_length: float,
) -> None:
    """Draw a closed curve-line-curve stroke with one flat terminal cap."""
    x, y = origin
    far_x = x + stroke_length
    shoulder_x = x + cap_length
    middle_x = x + stroke_length / 2
    pen.moveTo((far_x, y))
    pen.curveTo((middle_x, y), (shoulder_x, y), (x, y))
    pen.lineTo((x, y + cap_length))
    pen.curveTo(
        (shoulder_x, y + cap_length),
        (middle_x, y + cap_length),
        (far_x, y),
    )
    pen.closePath()


def _hiragana_terminal_path(*, with_dakuten: bool = False) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    _draw_curved_terminal(
        pen,
        origin=(0, 0),
        stroke_length=100,
        cap_length=20,
    )
    if with_dakuten:
        _draw_curved_terminal(
            pen,
            origin=(140, 60),
            stroke_length=40,
            cap_length=8,
        )
    return outline


def _long_sweep_terminal_path() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((400, 0))
    pen.curveTo((350, 0), (200, 0), (0, 0))
    pen.lineTo((0, 20))
    pen.curveTo((200, 20), (350, 20), (400, 0))
    pen.closePath()
    return outline


def _segmented_seam_terminal_path(*, bent: bool = False) -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((0, 0))
    pen.lineTo((-10 if bent else -1, -10))
    pen.lineTo((0, -20))
    pen.curveTo((20, -20), (50, -20), (100, 0))
    pen.curveTo((50, 0), (20, 0), (0, 0))
    pen.closePath()
    return outline


def _commands(outline: pathops.Path) -> tuple[Command, ...]:
    recording = RecordingPen()
    outline.draw(recording)
    return tuple(recording.value)


class HiraganaTerminalTests(unittest.TestCase):
    def test_softens_one_flat_cap_without_mutating_source_geometry(self) -> None:
        outline = _hiragana_terminal_path()
        commands_before = _commands(outline)
        verbs_before = tuple(outline.verbs)
        points_before = tuple(outline.points)
        bounds_before = outline.bounds

        softened, softened_count = soften_kana_terminals(outline)

        self.assertEqual(softened_count, 1)
        self.assertIsNot(softened, outline)
        self.assertEqual(_commands(outline), commands_before)
        self.assertEqual(tuple(outline.verbs), verbs_before)
        self.assertEqual(tuple(outline.points), points_before)
        self.assertEqual(outline.bounds, bounds_before)

        commands_after = _commands(softened)
        self.assertEqual(
            tuple(operator for operator, _ in commands_after),
            (
                "moveTo",
                "curveTo",
                "curveTo",
                "curveTo",
                "curveTo",
                "closePath",
            ),
        )
        self.assertEqual(commands_after[1][1][-1], commands_before[1][1][-1])
        self.assertEqual(commands_after[3][1][-1], commands_before[2][1][-1])
        expected_curves = (
            ((-6.0, 0.0), (0.0, 6.4), (0.0, 10.0)),
            ((0.0, 13.6), (-6.0, 20.0), (0.0, 20.0)),
        )
        for command, expected in zip(
            commands_after[2:4],
            expected_curves,
            strict=True,
        ):
            self.assertEqual(command[0], "curveTo")
            for actual_point, expected_point in zip(
                command[1],
                expected,
                strict=True,
            ):
                self.assertAlmostEqual(actual_point[0], expected_point[0], places=6)
                self.assertAlmostEqual(actual_point[1], expected_point[1], places=6)
        self.assertEqual(len(tuple(softened.contours)), len(tuple(outline.contours)))

        x_min_before, y_min_before, x_max_before, y_max_before = bounds_before
        x_min_after, y_min_after, x_max_after, y_max_after = softened.bounds
        self.assertGreaterEqual(x_min_after, x_min_before - 3)
        self.assertEqual(y_min_after, y_min_before)
        self.assertEqual(x_max_after, x_max_before)
        self.assertEqual(y_max_after, y_max_before)
        self.assertEqual(commands_after[2][1][-1], (0.0, 10.0))

    def test_long_sweep_uses_sharper_nose_without_extending_tip(self) -> None:
        short, short_count = soften_kana_terminals(_hiragana_terminal_path())
        long, long_count = soften_kana_terminals(_long_sweep_terminal_path())

        self.assertEqual(short_count, 1)
        self.assertEqual(long_count, 1)
        short_curves = _commands(short)[2:4]
        long_curves = _commands(long)[2:4]
        self.assertEqual(short_curves[0][1][-1], (0.0, 10.0))
        self.assertEqual(long_curves[0][1][-1], (0.0, 10.0))
        self.assertAlmostEqual(short_curves[0][1][-2][1], 6.4, places=6)
        self.assertAlmostEqual(long_curves[0][1][-2][1], 7.2, places=6)
        self.assertNotIn("lineTo", (operator for operator, _ in _commands(long)))

    def test_softens_nearly_straight_segmented_cap_at_contour_seam(self) -> None:
        softened, count = soften_kana_terminals(_segmented_seam_terminal_path())

        self.assertEqual(count, 1)
        commands = _commands(softened)
        self.assertNotIn("lineTo", (operator for operator, _ in commands))
        self.assertEqual(commands[1][1][-1], (0.0, -10.0))

    def test_rejects_bent_segment_chain_that_is_not_a_terminal_cap(self) -> None:
        outline = _segmented_seam_terminal_path(bent=True)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_commands(softened), _commands(outline))

    def test_drops_non_rendering_open_subpaths_when_rebuilding(self) -> None:
        outline = _hiragana_terminal_path()
        pen = outline.getPen()
        pen.moveTo((200, 200))
        pen.lineTo((220, 220))
        pen.endPath()

        softened, softened_count = soften_kana_terminals(outline)

        self.assertEqual(softened_count, 1)
        commands = _commands(softened)
        self.assertNotIn("endPath", (operator for operator, _ in commands))
        self.assertEqual(len(tuple(softened.contours)), 1)

    def test_softens_each_contour_once_and_is_idempotent(self) -> None:
        outline = _hiragana_terminal_path(with_dakuten=True)
        commands_before = _commands(outline)

        softened, softened_count = soften_kana_terminals(outline)

        self.assertEqual(softened_count, 2)
        self.assertEqual(_commands(outline), commands_before)
        self.assertEqual(len(tuple(outline.contours)), 2)
        self.assertEqual(len(tuple(softened.contours)), 2)
        commands_after = _commands(softened)
        self.assertNotIn("lineTo", (operator for operator, _ in commands_after))
        self.assertEqual(
            sum(operator == "curveTo" for operator, _ in commands_after),
            8,
        )
        softened_contours = tuple(softened.contours)
        self.assertGreaterEqual(softened_contours[0].bounds[0], -3.0)
        self.assertGreaterEqual(softened_contours[1].bounds[0], 138.0)

        softened_twice, second_count = soften_kana_terminals(softened)

        self.assertEqual(second_count, 0)
        self.assertEqual(_commands(softened_twice), commands_after)
        self.assertEqual(tuple(softened_twice.verbs), tuple(softened.verbs))
        self.assertEqual(tuple(softened_twice.points), tuple(softened.points))
        self.assertEqual(len(tuple(softened_twice.contours)), 2)


if __name__ == "__main__":
    unittest.main()
