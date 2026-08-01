"""Command-line interface for building Nobigoe Essential."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .essential import build_essential

DEFAULT_SOURCE_PATH = Path("dist") / "NobigoeVariableMarks-VF.otf"
DEFAULT_OUTPUT_PATH = Path("dist") / "NobigoeEssential-VF.otf"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Subset a Nobigoe variable source to ー, ―, 〜, ～, and 〰 for use "
            "before another font in a fallback stack."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_PATH,
        help=f"customized Nobigoe CFF2 variable source (default: {DEFAULT_SOURCE_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"output marks-only variable OTF (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument("--face", type=int, default=0, help="font collection face index")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    build_essential(args.source, args.output, args.face)


if __name__ == "__main__":
    main()
