from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from nobigoe_font.release import (
    ARCHIVE_TIMESTAMP,
    ESSENTIAL_RELEASE,
    NOVEL_RELEASE,
    RELEASES,
    ReleaseSpec,
    package_release,
    parse_args,
    release_specs,
)
from nobigoe_font.version import VERSION_NUMBER


class ReleasePackagingTests(unittest.TestCase):
    def test_family_archive_is_separate_complete_and_reproducible(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            font = dist / "Family-Regular.otf"
            font.write_bytes(b"font-data")
            documents = tuple(
                root / name for name in ("README.md", "OFL.txt", "NOTICES.md")
            )
            for document in documents:
                document.write_text(document.name)
            spec = ReleaseSpec("Family-v1", "Family-v1.zip", (font.name,))

            with patch("nobigoe_font.release.DOCUMENTS", documents):
                archive_path = package_release(spec, dist)
                first_bytes = archive_path.read_bytes()
                package_release(spec, dist)

            self.assertEqual(archive_path.read_bytes(), first_bytes)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "Family-v1/Fonts/Family-Regular.otf",
                        "Family-v1/README.md",
                        "Family-v1/OFL.txt",
                        "Family-v1/NOTICES.md",
                        "Family-v1/MANIFEST.sha256",
                    ],
                )
                self.assertTrue(
                    all(
                        info.date_time == ARCHIVE_TIMESTAMP
                        for info in archive.infolist()
                    )
                )
                manifest = archive.read("Family-v1/MANIFEST.sha256").decode()
                self.assertIn(
                    f"{hashlib.sha256(b'font-data').hexdigest()}  Fonts/{font.name}",
                    manifest,
                )

    def test_experimental_release_requires_explicit_opt_in(self) -> None:
        self.assertNotIn(NOVEL_RELEASE, RELEASES)
        self.assertEqual(release_specs(), RELEASES)
        self.assertEqual(release_specs(False), RELEASES)
        self.assertEqual(release_specs(True), (*RELEASES, NOVEL_RELEASE))
        self.assertFalse(parse_args([]).include_experimental)
        self.assertTrue(parse_args(["--include-experimental"]).include_experimental)

    def test_essential_release_is_a_separate_variable_font_archive(self) -> None:
        self.assertIn(ESSENTIAL_RELEASE, RELEASES)
        self.assertEqual(
            ESSENTIAL_RELEASE.archive,
            f"NobigoeEssential-v{VERSION_NUMBER}.zip",
        )
        self.assertEqual(ESSENTIAL_RELEASE.fonts, ("NobigoeEssential-VF.otf",))


    def test_novel_release_is_a_separate_seven_weight_archive(self) -> None:
        self.assertEqual(
            NOVEL_RELEASE.archive,
            f"NobigoeNovelMincho-v{VERSION_NUMBER}.zip",
        )
        self.assertEqual(len(NOVEL_RELEASE.fonts), 7)
        self.assertEqual(
            NOVEL_RELEASE.fonts[0],
            "NobigoeNovelMincho-ExtraLight.otf",
        )
        self.assertEqual(
            NOVEL_RELEASE.fonts[-1],
            "NobigoeNovelMincho-Black.otf",
        )

    def test_missing_font_stops_packaging(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            spec = ReleaseSpec("Missing-v1", "Missing-v1.zip", ("missing.otf",))
            with patch("nobigoe_font.release.DOCUMENTS", ()):
                with self.assertRaisesRegex(FileNotFoundError, "missing.otf"):
                    package_release(spec, root)


if __name__ == "__main__":
    unittest.main()
