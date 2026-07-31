"""Resolve pinned build-font source files from local overrides or a cache."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .profiles import (
    BaseType,
    DirectSource,
    FontSource,
    LatinFamily,
    ZipMemberSource,
    koburi_source,
    latin_font_source,
    noto_serif_source,
    noto_serif_variable_source,
    shippori_source,
)

DEFAULT_CACHE_DIR: Final[Path] = Path(".cache") / "font-sources"
_SHA256_BLOCK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class SourceOverrides:
    """Explicit local font paths, which take precedence over cached sources."""

    source: Path | None = None
    latin_source: Path | None = None
    punctuation_source: Path | None = None
    variable_kana_source: Path | None = None


@dataclass(frozen=True)
class ResolvedSources:
    """Inputs consumed by the static build pipeline."""

    source: Path
    latin_source: Path | None
    punctuation_source: Path
    variable_kana_source: Path | None = None


def verify_sha256(path: Path, expected: str) -> None:
    """Raise when *path* does not have the pinned SHA-256 digest."""

    hasher = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(_SHA256_BLOCK_SIZE):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: {digest} != {expected}")


@dataclass(frozen=True)
class SourceCache:
    """Persistent, verified storage for the fixed build-font source files."""

    cache_dir: Path = DEFAULT_CACHE_DIR

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache_dir", Path(self.cache_dir))

    def resolve(
        self,
        base: BaseType,
        weight: str,
        overrides: SourceOverrides = SourceOverrides(),
        latin_family: LatinFamily = "libertinus",
        variable_kana: bool = False,
    ) -> ResolvedSources:
        """Resolve all build inputs, downloading only missing or invalid cache data."""
        resolved_variable_kana_source: Path | None = None

        if base == "noto":
            source = overrides.source or self._fetch_direct(noto_serif_source(weight))
            if overrides.latin_source is not None:
                latin_source = overrides.latin_source
            else:
                latin_spec = latin_font_source(latin_family, weight)
                latin_source = (
                    self.fetch(latin_spec) if latin_spec is not None else None
                )
            secondary_weight = weight
            resolved_variable_kana_source = (
                self.resolve_variable_kana(overrides.variable_kana_source)
                if variable_kana
                else None
            )
        elif base == "koburi":
            if overrides.latin_source is not None:
                raise ValueError("--latin-source is available for the Noto base only")
            if variable_kana:
                raise ValueError("Variable kana is available for the Noto base only")
            source = overrides.source or self._fetch_zip_member(koburi_source())
            latin_source = None
            secondary_weight = "Regular"
        else:
            raise ValueError(f"Unknown base type {base!r}")

        punctuation_source = overrides.punctuation_source or self._fetch_zip_member(
            shippori_source(secondary_weight)
        )
        return ResolvedSources(
            source=source,
            latin_source=latin_source,
            punctuation_source=punctuation_source,
            variable_kana_source=resolved_variable_kana_source,
        )

    def resolve_variable_kana(self, override: Path | None = None) -> Path:
        """Resolve the pinned development VF, unless a local source is explicit."""

        return override or self._fetch_direct(noto_serif_variable_source())

    def fetch(self, source: FontSource) -> Path:
        """Return a pinned source from the verified persistent cache."""
        if isinstance(source, DirectSource):
            return self._fetch_direct(source)
        return self._fetch_zip_member(source)

    def _fetch_direct(self, source: DirectSource) -> Path:
        return self._download(
            source.url,
            self._cache_path(source.filename),
            source.sha256,
        )

    def _fetch_zip_member(self, source: ZipMemberSource) -> Path:
        destination = self._cache_path(source.filename)
        cached = self._cached_file(destination, source.sha256)
        if cached is not None:
            return cached
        archive_path = self._download(
            source.archive_url,
            self._cache_path(source.archive_filename),
            source.archive_sha256,
        )
        temporary_path = self._temporary_path(destination)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                with archive.open(source.member) as member:
                    with temporary_path.open("wb") as extracted:
                        shutil.copyfileobj(member, extracted)
            verify_sha256(temporary_path, source.sha256)
            os.replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        return destination

    def _download(self, url: str, destination: Path, expected: str) -> Path:
        cached = self._cached_file(destination, expected)
        if cached is not None:
            return cached

        temporary_path = self._temporary_path(destination)
        try:
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, temporary_path)
            verify_sha256(temporary_path, expected)
            os.replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        return destination

    def _cached_file(self, destination: Path, expected: str) -> Path | None:
        if not destination.exists():
            return None
        if not destination.is_file():
            raise ValueError(f"Cache path is not a file: {destination}")
        try:
            verify_sha256(destination, expected)
        except ValueError:
            destination.unlink()
            return None
        return destination

    def _cache_path(self, filename: str) -> Path:
        name = Path(filename)
        if name.name != filename or name.name in {"", "."}:
            raise ValueError(f"Cache filename must not contain a directory: {filename}")
        return self.cache_dir / name

    def _temporary_path(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        return Path(temporary_name)
