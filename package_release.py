#!/usr/bin/env python3
"""Package the two Nobigoe font families as separate release archives."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import zipfile

from font_profiles import NOTO_WEIGHT_CLASSES, VERSION_NUMBER

ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
DOCUMENTS = (Path("README.md"), Path("OFL.txt"), Path("THIRD_PARTY_NOTICES.md"))


@dataclass(frozen=True)
class ReleaseSpec:
    directory: str
    archive: str
    fonts: tuple[str, ...]


NOTO_RELEASE = ReleaseSpec(
    directory=f"NobigoeMincho-v{VERSION_NUMBER}",
    archive=f"NobigoeMincho-v{VERSION_NUMBER}.zip",
    fonts=tuple(f"NobigoeMincho-{weight}.otf" for weight in NOTO_WEIGHT_CLASSES),
)
KOBURI_RELEASE = ReleaseSpec(
    directory=f"NobigoeKoburiMincho-v{VERSION_NUMBER}",
    archive=f"NobigoeKoburiMincho-v{VERSION_NUMBER}.zip",
    fonts=("NobigoeKoburiMincho-Regular.ttf",),
)
RELEASES = (NOTO_RELEASE, KOBURI_RELEASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package Nobigoe Mincho families into separate ZIP archives."
    )
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def archive_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ARCHIVE_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def write_file(archive: zipfile.ZipFile, source: Path, destination: str) -> None:
    archive.writestr(archive_info(destination), source.read_bytes())


def package_release(spec: ReleaseSpec, dist: Path) -> Path:
    sources = [dist / font_name for font_name in spec.fonts]
    sources.extend(DOCUMENTS)
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing release files: " + ", ".join(missing))

    archive_path = dist / spec.archive
    manifest_lines: list[str] = []
    for source in sources:
        destination = (
            f"Fonts/{source.name}" if source.parent == dist else source.name
        )
        manifest_lines.append(f"{sha256(source)}  {destination}")

    with zipfile.ZipFile(archive_path, "w") as archive:
        for source in sources:
            relative = (
                f"Fonts/{source.name}" if source.parent == dist else source.name
            )
            write_file(archive, source, f"{spec.directory}/{relative}")
        archive.writestr(
            archive_info(f"{spec.directory}/MANIFEST.sha256"),
            ("\n".join(manifest_lines) + "\n").encode(),
        )
    return archive_path


def main() -> None:
    args = parse_args()
    for release in RELEASES:
        output = package_release(release, args.dist)
        print(output)


if __name__ == "__main__":
    main()
