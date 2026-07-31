"""Command-line interface for building the experimental CFF2 variable font."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import pipeline, variable_marks
from .profiles import (
    NOTO_WEIGHT_CLASSES,
    default_output_path,
    font_identity,
    latin_build_profile,
    latin_font_source,
    noto_serif_cff2_variable_source,
    shippori_source,
)
from .sources import DEFAULT_CACHE_DIR, SourceCache

DEFAULT_OUTPUT_PATH = Path("dist") / "NobigoeVariableMarks-VF.otf"
DEFAULT_STATIC_OUTPUT_DIR = Path("dist")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Customize the pinned Noto Serif JP CFF2 variable font with Nobigoe "
            "glyphs and features, instance all seven static weights, then import "
            "the static-only Latin outlines and release metadata."
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
    parser.add_argument(
        "--static-output-dir",
        type=Path,
        default=DEFAULT_STATIC_OUTPUT_DIR,
        help=(
            "directory for all seven release-ready static OTFs "
            f"(default: {DEFAULT_STATIC_OUTPUT_DIR})"
        ),
    )
    parser.add_argument(
        "--autohint",
        action="store_true",
        help=(
            "run AFDKO otfautohint on imported Latin glyphs in each static OTF; "
            "requires the otfautohint command"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    cache = SourceCache(args.cache_dir)
    source_path = args.source
    if source_path is None:
        source_path = cache.fetch(noto_serif_cff2_variable_source())
    punctuation_sources = {
        weight: cache.fetch(shippori_source(style))
        for style, weight in NOTO_WEIGHT_CLASSES.items()
    }
    latin_sources: dict[int, Path] = {}
    for style, weight in NOTO_WEIGHT_CLASSES.items():
        latin_spec = latin_font_source("libertinus", style)
        if latin_spec is None:
            raise AssertionError(f"Missing Libertinus source for {style}")
        latin_sources[weight] = cache.fetch(latin_spec)
    variable_marks.build_variable_marks(
        source_path,
        args.output,
        args.face,
        punctuation_sources,
    )
    for style, weight in NOTO_WEIGHT_CLASSES.items():
        identity = font_identity("noto", style)
        output_path = args.static_output_dir / default_output_path(
            identity, "noto"
        ).name
        pipeline.build_static_instance(
            args.output,
            latin_sources[weight],
            output_path,
            identity,
            latin_build_profile("libertinus", style),
            args.autohint,
        )
