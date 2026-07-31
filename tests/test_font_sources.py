from __future__ import annotations

from contextlib import ExitStack, contextmanager
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import urllib.error
import zipfile
from unittest.mock import patch

from nobigoe_font.profiles import DirectSource, ZipMemberSource
from nobigoe_font.sources import ResolvedSources, SourceCache, SourceOverrides


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def archive_bytes(member: str, content: bytes) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(member, content)
    return output.getvalue()


class SourceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.cache_directory = Path(self.temporary_directory.name) / "cache"

        self.noto_content = b"noto serif"
        self.latin_content = b"libertinus"
        self.punctuation_content = b"shippori"
        self.koburi_content = b"koburi"
        self.noto = DirectSource(
            "NotoSerifJP-Regular.otf",
            "https://fonts.example/noto.otf",
            digest(self.noto_content),
        )
        self.latin, latin_archive = self._zip_source(
            "libertinus.zip",
            "https://fonts.example/libertinus.zip",
            "fonts/LibertinusSerif-Regular.otf",
            self.latin_content,
        )
        self.punctuation, punctuation_archive = self._zip_source(
            "shippori.zip",
            "https://fonts.example/shippori.zip",
            "ShipporiMincho-OTF-Regular.otf",
            self.punctuation_content,
        )
        self.koburi, koburi_archive = self._zip_source(
            "koburi.zip",
            "https://fonts.example/koburi.zip",
            "GenEiKoburiMin6-R.ttf",
            self.koburi_content,
        )
        self.payloads = {
            self.noto.url: self.noto_content,
            self.latin.archive_url: latin_archive,
            self.punctuation.archive_url: punctuation_archive,
            self.koburi.archive_url: koburi_archive,
        }

    def _zip_source(
        self, archive_filename: str, archive_url: str, member: str, content: bytes
    ) -> tuple[ZipMemberSource, bytes]:
        archive = archive_bytes(member, content)
        return (
            ZipMemberSource(
                archive_filename,
                archive_url,
                digest(archive),
                member,
                digest(content),
            ),
            archive,
        )

    @contextmanager
    def _pinned_sources(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch("nobigoe_font.sources.noto_serif_source", return_value=self.noto)
            )
            stack.enter_context(
                patch(
                    "nobigoe_font.sources.latin_font_source",
                    side_effect=lambda family, _weight: (
                        None if family == "noto" else self.latin
                    ),
                )
            )
            stack.enter_context(
                patch("nobigoe_font.sources.shippori_source", return_value=self.punctuation)
            )
            stack.enter_context(
                patch("nobigoe_font.sources.koburi_source", return_value=self.koburi)
            )
            yield

    def _urlretrieve(self, url: str, destination: Path) -> tuple[str, None]:
        destination.write_bytes(self.payloads[url])
        return str(destination), None

    def test_initial_resolution_downloads_and_caches_all_noto_sources(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ) as retrieve:
            resolved = cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(
            resolved,
            ResolvedSources(
                source=self.cache_directory / self.noto.filename,
                latin_source=self.cache_directory / self.latin.filename,
                punctuation_source=self.cache_directory / self.punctuation.filename,
            ),
        )
        self.assertEqual(retrieve.call_count, 3)
        self.assertEqual(resolved.source.read_bytes(), self.noto_content)
        self.assertEqual(resolved.latin_source.read_bytes(), self.latin_content)
        self.assertEqual(
            resolved.punctuation_source.read_bytes(), self.punctuation_content
        )

    def test_noto_latin_profile_keeps_the_base_latin_glyphs(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ) as retrieve:
            resolved = cache.resolve(
                "noto",
                "Regular",
                SourceOverrides(),
                latin_family="noto",
            )

        self.assertIsNone(resolved.latin_source)
        self.assertEqual(retrieve.call_count, 2)

    def test_second_resolution_reuses_the_same_cached_paths_without_network(
        self,
    ) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ) as retrieve:
            first = cache.resolve("noto", "Regular", SourceOverrides())
            first_call_count = retrieve.call_count
            second = cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(second, first)
        self.assertEqual(first_call_count, 3)
        self.assertEqual(retrieve.call_count, first_call_count)

    def test_zip_members_are_not_reextracted_after_they_are_cached(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ):
            cache.resolve("noto", "Regular", SourceOverrides())
            with patch(
                "nobigoe_font.sources.zipfile.ZipFile", wraps=zipfile.ZipFile
            ) as open_archive:
                cache.resolve("noto", "Regular", SourceOverrides())

        open_archive.assert_not_called()

    def test_cached_zip_members_do_not_require_the_archives(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ):
            first = cache.resolve("noto", "Regular", SourceOverrides())

        (self.cache_directory / self.latin.archive_filename).unlink()
        (self.cache_directory / self.punctuation.archive_filename).unlink()
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve"
        ) as retrieve:
            second = cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(second, first)
        retrieve.assert_not_called()

    def test_explicit_paths_take_precedence_over_every_cached_source(self) -> None:
        source_directory = Path(self.temporary_directory.name) / "explicit"
        source_directory.mkdir()
        overrides = SourceOverrides(
            source=source_directory / "base.otf",
            latin_source=source_directory / "latin.otf",
            punctuation_source=source_directory / "punctuation.otf",
        )
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve"
        ) as retrieve:
            resolved = cache.resolve("noto", "Regular", overrides)

        self.assertEqual(
            resolved,
            ResolvedSources(
                source=overrides.source,
                latin_source=overrides.latin_source,
                punctuation_source=overrides.punctuation_source,
            ),
        )
        retrieve.assert_not_called()

    def test_corrupt_cached_source_is_downloaded_again(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ) as retrieve:
            first = cache.resolve("noto", "Regular", SourceOverrides())
            first.source.write_bytes(b"corrupt")
            second = cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(second.source, first.source)
        self.assertEqual(second.source.read_bytes(), self.noto_content)
        self.assertEqual(retrieve.call_count, 4)

    def test_corrupt_cached_archive_is_downloaded_again(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=self._urlretrieve,
        ) as retrieve:
            cache.resolve("noto", "Regular", SourceOverrides())
            (self.cache_directory / self.latin.filename).unlink()
            (self.cache_directory / self.latin.archive_filename).write_bytes(
                b"corrupt"
            )
            cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(retrieve.call_count, 4)

    def test_koburi_resolves_without_a_latin_source(self) -> None:
        source_directory = Path(self.temporary_directory.name) / "explicit"
        source_directory.mkdir()
        overrides = SourceOverrides(
            source=source_directory / "base.ttf",
            punctuation_source=source_directory / "punctuation.otf",
        )
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve"
        ) as retrieve:
            resolved = SourceCache(self.cache_directory).resolve(
                "koburi", "Regular", overrides
            )

        self.assertEqual(resolved.latin_source, None)
        retrieve.assert_not_called()

    def test_failed_download_removes_its_temporary_file(self) -> None:
        cache = SourceCache(self.cache_directory)
        with self._pinned_sources(), patch(
            "nobigoe_font.sources.urllib.request.urlretrieve",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(urllib.error.URLError):
                cache.resolve("noto", "Regular", SourceOverrides())

        self.assertEqual(list(self.cache_directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
