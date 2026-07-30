from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from nobigoe_font.marks import (
    KOBURI_GENERATED_MARK_PAIRS,
    KOBURI_NATIVE_MARK_PAIRS,
    MARK_POSITION_DIRECTORY,
    PUNCTUATION_MARK_PAIRS,
    load_mark_position_overrides,
    load_punctuation_mark_positions,
)


def placement_values(placement: object) -> tuple[float, float, float, float]:
    return (
        placement.scale,
        placement.x,
        placement.y,
        placement.rotation,
    )


class PunctuationMarkPositionTests(unittest.TestCase):
    def test_every_family_weight_covers_all_four_punctuation_pairs(self) -> None:
        family_weights = {
            "noto": (
                "ExtraLight",
                "Light",
                "Regular",
                "Medium",
                "SemiBold",
                "Bold",
                "Black",
            ),
            "koburi": ("Regular",),
        }
        for family, weights in family_weights.items():
            for weight in weights:
                with self.subTest(family=family, weight=weight):
                    positions = load_punctuation_mark_positions(
                        base=family,
                        weight=weight,
                    )
                    self.assertEqual(set(positions), set(PUNCTUATION_MARK_PAIRS))
                    for pair in PUNCTUATION_MARK_PAIRS:
                        for orientation in ("horizontal", "vertical"):
                            self.assertGreater(
                                positions[pair][orientation].scale,
                                0,
                            )
                            expected_rotation = -3 if pair[1] == 0x3099 else 0
                            self.assertEqual(
                                positions[pair][orientation].rotation,
                                expected_rotation,
                            )

    def test_unknown_family_weight_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Unknown Noto punctuation mark position weight",
        ):
            load_punctuation_mark_positions(weight="Unknown")
        with self.assertRaisesRegex(
            ValueError,
            "Regular only",
        ):
            load_punctuation_mark_positions(base="koburi", weight="Bold")


class NotoWeightMarkPositionOverrideTests(unittest.TestCase):
    def test_every_nonregular_weight_has_explicit_optical_overrides(self) -> None:
        regular = load_mark_position_overrides(weight="Regular")
        for weight in (
            "ExtraLight",
            "Light",
            "Medium",
            "SemiBold",
            "Bold",
            "Black",
        ):
            with self.subTest(weight=weight):
                weighted = load_mark_position_overrides(weight=weight)
                self.assertEqual(set(weighted), set(regular))
                self.assertTrue(
                    any(
                        placement_values(weighted[pair][orientation])
                        != placement_values(regular[pair][orientation])
                        for pair in regular
                        for orientation in ("horizontal", "vertical")
                    )
                )

    def test_black_ke_handakuten_uses_its_reviewed_position(self) -> None:
        black = load_mark_position_overrides(weight="Black")
        pair = (0x3051, 0x309A)
        self.assertEqual(
            placement_values(black[pair]["horizontal"]),
            (0.929, 1016, 75, 0),
        )
        self.assertEqual(
            placement_values(black[pair]["vertical"]),
            (0.929, 1005, 79, 0),
        )

    def test_mi_dakuten_preserves_its_reviewed_rotation_across_weights(
        self,
    ) -> None:
        pair = (0x30DF, 0x3099)
        for weight in (
            "ExtraLight",
            "Light",
            "Regular",
            "Medium",
            "SemiBold",
            "Bold",
            "Black",
        ):
            with self.subTest(weight=weight):
                positions = load_mark_position_overrides(weight=weight)
                self.assertEqual(
                    positions[pair]["horizontal"].rotation,
                    5,
                )
                self.assertEqual(
                    positions[pair]["vertical"].rotation,
                    5,
                )


    def test_six_reviewed_dakuten_positions_are_preserved(self) -> None:
        regular = load_mark_position_overrides()
        expected = {
            0x3041: ((0.806, 869, -46, 0), (0.806, 1010, 85, 0)),
            0x304A: ((0.957, 1031, 39, 3), (0.957, 1002, 25, 3)),
            0x3049: ((0.787, 909, -55, 6), (0.787, 1014, 129, 6)),
            0x30A5: ((0.8, 912, -96, 0), (0.8, 1041, 105, 2)),
            0x30A1: ((0.8, 963, -49, 3), (0.8, 1044, 179, 3)),
            0x30A2: ((0.956, 1049, 72, 3), (0.956, 1027, 65, 3)),
        }

        for base, (horizontal, vertical) in expected.items():
            with self.subTest(base=f"U+{base:04X}"):
                positions = regular[(base, 0x3099)]
                self.assertEqual(
                    placement_values(positions["horizontal"]),
                    horizontal,
                )
                self.assertEqual(
                    placement_values(positions["vertical"]),
                    vertical,
                )


    def test_unknown_noto_weight_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown Noto mark position weight"):
            load_mark_position_overrides(weight="Unknown")


class KoburiMarkPositionOverrideTests(unittest.TestCase):
    def test_koburi_overrides_only_generated_sequences(self) -> None:
        noto = load_mark_position_overrides()
        koburi = load_mark_position_overrides(base="koburi")

        self.assertEqual(set(koburi), set(noto))
        self.assertEqual(len(KOBURI_NATIVE_MARK_PAIRS), 88)
        self.assertEqual(len(KOBURI_GENERATED_MARK_PAIRS), 103)
        for pair in KOBURI_NATIVE_MARK_PAIRS:
            for orientation in ("horizontal", "vertical"):
                self.assertEqual(
                    placement_values(koburi[pair][orientation]),
                    placement_values(noto[pair][orientation]),
                )

        changed_pairs = {
            pair
            for pair in KOBURI_GENERATED_MARK_PAIRS
            if any(
                placement_values(koburi[pair][orientation])
                != placement_values(noto[pair][orientation])
                for orientation in ("horizontal", "vertical")
            )
        }
        self.assertEqual(changed_pairs, KOBURI_GENERATED_MARK_PAIRS)
        self.assertEqual(
            placement_values(koburi[(0x3042, 0x309A)]["horizontal"]),
            (0.992, 738, -14, 0),
        )

    def test_koburi_configuration_rejects_missing_unknown_and_invalid_values(
        self,
    ) -> None:
        cases = (
            (
                lambda data: data["positions"].pop("3042+309A"),
                "missing U\\+3042\\+U\\+309A",
            ),
            (
                lambda data: data["positions"].update(
                    {
                        "FFFF+3099": {
                            "horizontal": [1, 0, 0, 0],
                            "vertical": [1, 0, 0, 0],
                        }
                    }
                ),
                "extra U\\+FFFF\\+U\\+3099",
            ),
            (
                lambda data: data["positions"]["3042+309A"]["horizontal"].pop(),
                "\\[scale, x, y, rotation\\]",
            ),
            (
                lambda data: data["positions"]["3042+309A"]["horizontal"].__setitem__(
                    0, 0
                ),
                "scale must be positive",
            ),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    directory = Path(temporary_directory)
                    for path in MARK_POSITION_DIRECTORY.glob("*.json"):
                        shutil.copy(path, directory / path.name)
                    config_path = directory / "koburi.json"
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                    mutate(data)
                    config_path.write_text(
                        json.dumps(data), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        load_mark_position_overrides(directory, base="koburi")


if __name__ == "__main__":
    unittest.main()
