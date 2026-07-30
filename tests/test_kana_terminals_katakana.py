from __future__ import annotations

import unittest

import pathops
from fontTools.pens.recordingPen import RecordingPen

from nobigoe_font.kana_terminals import soften_kana_terminals


Point = tuple[float, float]
Command = tuple[str, tuple[Point, ...]]


def _recording(outline: pathops.Path) -> list[Command]:
    recording = RecordingPen()
    outline.draw(recording)
    return recording.value


def _diagonal_terminal(
    *,
    cap_end: Point = (320, 280),
    outgoing_control: Point = (260, 220),
) -> pathops.Path:
    """Make a katakana-like diagonal stroke with one short, flat end cap."""
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((100, 100))
    pen.curveTo((150, 150), (240, 240), (300, 300))
    pen.lineTo(cap_end)
    pen.curveTo(outgoing_control, (180, 140), (120, 80))
    pen.curveTo((110, 85), (105, 95), (100, 100))
    pen.closePath()
    return outline


def _open_diagonal_terminal() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((100, 100))
    pen.curveTo((150, 150), (240, 240), (300, 300))
    pen.lineTo((320, 280))
    pen.curveTo((260, 220), (180, 140), (120, 80))
    pen.endPath()
    return outline


def _diagonal_terminal_with_line_neighbor() -> pathops.Path:
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((100, 100))
    pen.curveTo((150, 150), (240, 240), (280, 280))
    pen.lineTo((300, 300))
    pen.lineTo((320, 280))
    pen.curveTo((260, 220), (180, 140), (120, 80))
    pen.curveTo((110, 85), (105, 95), (100, 100))
    pen.closePath()
    return outline


def _two_diagonal_terminals() -> pathops.Path:
    """Make one closed stroke whose opposite ends are both eligible caps."""
    outline = pathops.Path()
    pen = outline.getPen()
    pen.moveTo((200, 200))
    pen.curveTo((230, 230), (270, 270), (300, 300))
    pen.lineTo((320, 280))
    pen.curveTo((290, 250), (250, 210), (220, 180))
    pen.curveTo((190, 150), (150, 110), (120, 80))
    pen.lineTo((100, 100))
    pen.curveTo((130, 130), (170, 170), (200, 200))
    pen.closePath()
    return outline


class KanaTerminalKatakanaTest(unittest.TestCase):
    def test_softens_diagonal_cap_without_moving_its_endpoints(self) -> None:
        outline = _diagonal_terminal()
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)
        commands = _recording(softened)

        self.assertEqual(count, 1)
        self.assertEqual(commands[2][0], "curveTo")
        self.assertEqual(commands[3][0], "curveTo")
        self.assertEqual(commands[1][1][-1], original[1][1][-1])
        self.assertEqual(commands[3][1][-1], original[2][1][-1])
        self.assertEqual(_recording(outline), original)

    def test_does_not_wrap_an_open_contour_for_terminal_detection(self) -> None:
        outline = _open_diagonal_terminal()
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_recording(softened), original)

    def test_rejects_cap_longer_than_45_units(self) -> None:
        outline = _diagonal_terminal(
            cap_end=(340, 260),
            outgoing_control=(280, 200),
        )
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_recording(softened), original)

    def test_rejects_tangents_that_do_not_point_in_opposite_directions(
        self,
    ) -> None:
        outline = _diagonal_terminal(outgoing_control=(380, 340))
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_recording(softened), original)

    def test_rejects_cap_parallel_to_the_stroke_axis(self) -> None:
        outline = _diagonal_terminal(
            cap_end=(320, 320),
            outgoing_control=(260, 260),
        )
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_recording(softened), original)

    def test_rejects_cap_with_a_line_neighbor(self) -> None:
        outline = _diagonal_terminal_with_line_neighbor()
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)

        self.assertEqual(count, 0)
        self.assertEqual(_recording(softened), original)

    def test_softens_every_eligible_cap_in_one_contour(self) -> None:
        outline = _two_diagonal_terminals()
        original = _recording(outline)

        softened, count = soften_kana_terminals(outline)
        commands = _recording(softened)

        self.assertEqual(count, 2)
        for index in (2, 3, 6, 7):
            with self.subTest(index=index):
                self.assertEqual(commands[index][0], "curveTo")
        self.assertEqual(commands[1][1][-1], original[1][1][-1])
        self.assertEqual(commands[3][1][-1], original[2][1][-1])
        self.assertEqual(commands[5][1][-1], original[4][1][-1])
        self.assertEqual(commands[7][1][-1], original[5][1][-1])
        self.assertNotIn("lineTo", (operator for operator, _ in commands))
        self.assertEqual(_recording(outline), original)


if __name__ == "__main__":
    unittest.main()
