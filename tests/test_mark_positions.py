from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from build_font import (
    KOBURI_GENERATED_MARK_PAIRS,
    KOBURI_NATIVE_MARK_PAIRS,
    MARK_POSITION_DIRECTORY,
    load_mark_position_overrides,
)


def transform_values(transform: object) -> tuple[float, float, float, float, float, float]:
    return (
        transform.xx,
        transform.xy,
        transform.yx,
        transform.yy,
        transform.dx,
        transform.dy,
    )


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
                    transform_values(koburi[pair][orientation]),
                    transform_values(noto[pair][orientation]),
                )

        changed_pairs = {
            pair
            for pair in KOBURI_GENERATED_MARK_PAIRS
            if any(
                transform_values(koburi[pair][orientation])
                != transform_values(noto[pair][orientation])
                for orientation in ("horizontal", "vertical")
            )
        }
        self.assertEqual(changed_pairs, KOBURI_GENERATED_MARK_PAIRS)
        self.assertEqual(
            transform_values(koburi[(0x3042, 0x309A)]["horizontal"]),
            (0.992, 0, 0, 0.992, 738, -14),
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
                            "horizontal": [1, 0, 0],
                            "vertical": [1, 0, 0],
                        }
                    }
                ),
                "extra U\\+FFFF\\+U\\+3099",
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
