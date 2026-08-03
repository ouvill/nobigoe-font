"""Command-line interface for building Nobigoe font families."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .brush import DEFAULT_VERTICAL_END_PROFILE, VERTICAL_END_PROFILES

from .pipeline import build
from .profiles import (
    LATIN_FAMILIES,
    KANA_STYLES,
    NOTO_WEIGHT_CLASSES,
    default_output_path,
    font_identity,
    latin_build_profile,
)
from .sources import DEFAULT_CACHE_DIR, SourceCache, SourceOverrides
from .variable_stix import build_variable_stix_source


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add automatically joining ー, ―, 〜, ～, and 〰 glyphs to "
            "Noto Serif JP or GenEi Koburi Mincho."
        )
    )
    parser.add_argument(
        "--base",
        choices=("noto", "koburi"),
        default="noto",
        help="base typeface; Koburi is available in Regular only",
    )
    parser.add_argument(
        "--kana-style",
        choices=KANA_STYLES,
        default="noto",
        help="hiragana design; novel is available for the Noto base only",
    )
    parser.add_argument(
        "--han-brush-elements",
        action="store_true",
        help=(
            "match Han start, end, and uroko elements; locally reshape them "
            "while keeping stroke bodies, hige, and metrics"
        ),
    )
    parser.add_argument(
        "--han-brush-end-profile",
        choices=VERTICAL_END_PROFILES,
        default=DEFAULT_VERTICAL_END_PROFILE,
        help=(
            "vertical stroke ending used with --han-brush-elements; "
            "traditional is the compact default, silver is long and asymmetric"
        ),
    )
    parser.add_argument(
        "--weight",
        choices=tuple(NOTO_WEIGHT_CLASSES),
        default="Regular",
        help="Noto Serif JP weight",
    )
    parser.add_argument(
        "--latin-family",
        choices=LATIN_FAMILIES,
        default="libertinus",
        help=(
            "Latin glyph source for the Noto base; "
            "the existing Libertinus profile remains the default"
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="local Noto Serif JP OTF/TTC or GenEi Koburi Mincho TTF",
    )
    parser.add_argument(
        "--latin-source",
        type=Path,
        help=(
            "local font overriding the selected Noto-based Latin source; "
            "with --build-variable-stix, the raw STIX VF"
        ),
    )
    parser.add_argument(
        "--punctuation-source",
        type=Path,
        help=(
            "Shippori Mincho OTF/TTF used for Manga1 "
            "exclamation/question ligatures (matching OTF weight by default)"
        ),
    )
    parser.add_argument(
        "--build-variable-stix",
        type=Path,
        metavar="OUTPUT",
        help=(
            "build the tuned STIX Two Text Latin design VF at OUTPUT; "
            "this is not a release artifact"
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="directory for the persistent verified font-source cache",
    )
    parser.add_argument("--face", type=int, default=0, help="TTC face index")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--autohint",
        action="store_true",
        help=(
            "run AFDKO otfautohint on imported Latin glyphs after building; "
            "requires the otfautohint command"
        ),
    )
    return parser.parse_args(argv)


def _build_variable_stix(args: argparse.Namespace) -> None:
    incompatible = [
        option
        for option, used in (
            ("--output", args.output is not None),
            ("--source", args.source is not None),
            ("--punctuation-source", args.punctuation_source is not None),
            ("--autohint", args.autohint),
            ("--face", args.face != 0),
            ("--base koburi", args.base != "noto"),
            ("--kana-style novel", args.kana_style != "noto"),
            ("--han-brush-elements", args.han_brush_elements),
            (
                "--han-brush-end-profile",
                args.han_brush_end_profile != DEFAULT_VERTICAL_END_PROFILE,
            ),
            ("--weight", args.weight != "Regular"),
            ("--latin-family", args.latin_family != "libertinus"),
        )
        if used
    ]
    if incompatible:
        raise ValueError(
            "--build-variable-stix cannot be combined with " + ", ".join(incompatible)
        )
    source = SourceCache(args.cache_dir).resolve_variable_stix(args.latin_source)
    build_variable_stix_source(source, args.build_variable_stix)
    print(
        f"Built tuned STIX Two Text Latin design VF at {args.build_variable_stix}; "
        "this output is not release-ready."
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.build_variable_stix is not None:
        _build_variable_stix(args)
        return
    if (
        not args.han_brush_elements
        and args.han_brush_end_profile != DEFAULT_VERTICAL_END_PROFILE
    ):
        raise ValueError("--han-brush-end-profile requires --han-brush-elements")
    if args.base == "koburi" and args.kana_style == "novel":
        raise ValueError("--kana-style novel requires --base noto")
    if args.base == "koburi" and args.han_brush_elements:
        raise ValueError("--han-brush-elements requires --base noto")
    if args.base == "koburi" and args.weight != "Regular":
        raise ValueError("GenEi Koburi Mincho is available in Regular only")
    if args.base == "koburi" and args.latin_source is not None:
        raise ValueError("--latin-source is available for the Noto base only")
    if args.base == "koburi" and args.latin_family != "libertinus":
        raise ValueError("--latin-family is available for the Noto base only")
    if (
        args.base == "noto"
        and args.latin_family == "noto"
        and args.latin_source is not None
    ):
        raise ValueError("--latin-source cannot be combined with --latin-family noto")

    identity = font_identity(
        args.base,
        args.weight,
        args.kana_style,
        latin_family=args.latin_family,
    )
    latin_profile = latin_build_profile(
        args.latin_family if args.base == "noto" else "noto",
        args.weight,
    )
    if args.output is not None:
        output_path = args.output
    elif args.base == "noto" and args.latin_family not in {
        "libertinus",
        "stix-two-text",
    }:
        output_path = (
            Path("dist")
            / "comparison"
            / f"{identity.postscript_name}-{args.latin_family}.otf"
        )
    else:
        output_path = default_output_path(identity, args.base)

    sources = SourceCache(args.cache_dir).resolve(
        args.base,
        args.weight,
        SourceOverrides(
            source=args.source,
            latin_source=args.latin_source,
            punctuation_source=args.punctuation_source,
        ),
        latin_family=args.latin_family,
    )
    build(
        sources.source,
        sources.latin_source,
        sources.punctuation_source,
        output_path,
        identity,
        latin_profile,
        args.face,
        args.base,
        args.autohint,
        args.kana_style,
        han_brush_elements=args.han_brush_elements,
        han_brush_end_profile=args.han_brush_end_profile,
    )
