"""Command-line interface for building the experimental CFF2 variable font."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import pipeline, variable_marks
from .variable_novel import build_variable_novel
from .profiles import (
    FontIdentity,
    LatinBuildProfile,
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
DEFAULT_NOVEL_OUTPUT_PATH = Path("dist") / "NobigoeNovelMincho-VF.otf"

DEFAULT_JOBS = min(4, os.process_cpu_count() or 1)


@dataclass(frozen=True)
class _StaticBuildTask:
    variable_source: Path
    latin_source: Path
    output: Path
    identity: FontIdentity
    latin_profile: LatinBuildProfile
    autohint: bool
    novel: bool


def _build_static_task(task: _StaticBuildTask) -> None:
    build_instance = (
        pipeline.build_novel_static_instance
        if task.novel
        else pipeline.build_static_instance
    )
    build_instance(
        task.variable_source,
        task.latin_source,
        task.output,
        task.identity,
        task.latin_profile,
        task.autohint,
    )


def _positive_job_count(value: str) -> int:
    jobs = int(value)
    if jobs < 1:
        raise argparse.ArgumentTypeError("jobs must be at least 1")
    return jobs


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Customize the pinned Noto Serif JP CFF2 variable font with Nobigoe "
            "glyphs and features, then instance Nobigoe and downstream Novel "
            "static weights before applying static-only Latin outlines and metadata."
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
        "--novel-output",
        type=Path,
        default=DEFAULT_NOVEL_OUTPUT_PATH,
        help=f"output Novel CFF2 variable OTF (default: {DEFAULT_NOVEL_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--static-output-dir",
        type=Path,
        default=DEFAULT_STATIC_OUTPUT_DIR,
        help=(
            "directory for generated Nobigoe and Novel static OTFs "
            f"(default: {DEFAULT_STATIC_OUTPUT_DIR})"
        ),
    )
    parser.add_argument(
        "--static-weight",
        choices=tuple(NOTO_WEIGHT_CLASSES),
        help=(
            "build only the selected Nobigoe static weight; Novel follows unless "
            "overridden (default: all seven)"
        ),
    )
    parser.add_argument(
        "--novel-static-weight",
        action="append",
        choices=tuple(NOTO_WEIGHT_CLASSES),
        help=(
            "build only the selected Novel static weight; repeat for multiple "
            "weights (default: follow --static-weight)"
        ),
    )
    parser.add_argument(
        "--jobs",
        type=_positive_job_count,
        default=DEFAULT_JOBS,
        help=(
            "maximum parallel static-instance builds "
            f"(automatic default: {DEFAULT_JOBS}, up to four available CPUs)"
        ),
    )
    parser.add_argument(
        "--autohint",
        action="store_true",
        help=(
            "run AFDKO otfautohint on imported Latin glyphs in generated static "
            "OTFs; requires the otfautohint command"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    static_styles = (
        tuple(NOTO_WEIGHT_CLASSES)
        if args.static_weight is None
        else (args.static_weight,)
    )
    novel_static_styles = (
        static_styles
        if args.novel_static_weight is None
        else tuple(dict.fromkeys(args.novel_static_weight))
    )
    requested_styles = set(static_styles) | set(novel_static_styles)

    cache = SourceCache(args.cache_dir)
    source_path = args.source
    if source_path is None:
        source_path = cache.fetch(noto_serif_cff2_variable_source())
    punctuation_sources = {
        weight: cache.fetch(shippori_source(style))
        for style, weight in NOTO_WEIGHT_CLASSES.items()
    }
    latin_sources: dict[str, Path] = {}
    for style in NOTO_WEIGHT_CLASSES:
        if style not in requested_styles:
            continue
        latin_spec = latin_font_source("libertinus", style)
        if latin_spec is None:
            raise AssertionError(f"Missing Libertinus source for {style}")
        latin_sources[style] = cache.fetch(latin_spec)
    variable_marks.build_variable_marks(
        source_path,
        args.output,
        args.face,
        punctuation_sources,
    )
    build_variable_novel(args.output, args.novel_output)

    tasks: list[_StaticBuildTask] = []
    # Novel instances scan every Han outline, so submit the longer tasks first.
    for style in NOTO_WEIGHT_CLASSES:
        if style not in novel_static_styles:
            continue
        novel_identity = font_identity("noto", style, "novel")
        tasks.append(
            _StaticBuildTask(
                args.novel_output,
                latin_sources[style],
                args.static_output_dir
                / default_output_path(novel_identity, "noto").name,
                novel_identity,
                latin_build_profile("libertinus", style),
                args.autohint,
                True,
            )
        )
    for style in NOTO_WEIGHT_CLASSES:
        if style not in static_styles:
            continue
        identity = font_identity("noto", style)
        tasks.append(
            _StaticBuildTask(
                args.output,
                latin_sources[style],
                args.static_output_dir / default_output_path(identity, "noto").name,
                identity,
                latin_build_profile("libertinus", style),
                args.autohint,
                False,
            )
        )

    if args.jobs == 1 or len(tasks) == 1:
        for task in tasks:
            _build_static_task(task)
        return

    with ProcessPoolExecutor(max_workers=min(args.jobs, len(tasks))) as executor:
        for _ in executor.map(_build_static_task, tasks):
            pass
