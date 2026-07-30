"""Load the shared font release version."""

from __future__ import annotations

from importlib.resources import files
import json
import re


_VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]{3}\Z")
_VERSION_DATA = json.loads(
    files("nobigoe_font").joinpath("version.json").read_text(encoding="utf-8")
)
VERSION_NUMBER = _VERSION_DATA.get("version")
if not isinstance(VERSION_NUMBER, str) or not _VERSION_PATTERN.fullmatch(
    VERSION_NUMBER
):
    raise RuntimeError("version.json must contain a version in N.NNN format")
VERSION = f"Version {VERSION_NUMBER}"


def main() -> None:
    """Print the canonical release version for scripts and workflows."""
    print(VERSION_NUMBER)


if __name__ == "__main__":
    main()
