"""Command-line interface for building the experimental CFF2 variable font."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import variable_marks
from .profiles import noto_serif_cff2_variable_source
from .sources import DEFAULT_CACHE_DIR, SourceCache

DEFAULT_OUTPUT_PATH = Path("dist") / "NobigoeVariableMarks-VF.otf"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the CFF2 Nobigoe variable font with kana marks and "
            "automatically joining ー, ―, 〜, and 〰."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        help=("local Noto Serif JP CFF2 variable OTF overriding the pinned download"),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=(
            "directory for the persistent verified font-source cache "
            f"(default: {DEFAULT_CACHE_DIR})"
        ),
    )
    parser.add_argument(
        "--face",
        type=int,
        default=0,
        help="font collection face index (default: 0)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"output CFF2 variable OTF (default: {DEFAULT_OUTPUT_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    source_path = args.source
    if source_path is None:
        source_path = SourceCache(args.cache_dir).fetch(
            noto_serif_cff2_variable_source()
        )
    variable_marks.build_variable_marks(source_path, args.output, args.face)
