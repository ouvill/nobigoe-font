"""Command-line interface for building Nobigoe font families."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

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
        help="local font overriding the selected Noto-based Latin source",
    )
    parser.add_argument(
        "--ruby-source",
        type=Path,
        help="GenEi Koburi Mincho TTF used for Noto-based ruby glyphs",
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
        "--sans-source",
        type=Path,
        help="local Noto Sans JP OTF used for sans punctuation variants",
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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.base == "koburi" and args.kana_style == "novel":
        raise ValueError("--kana-style novel requires --base noto")
    if args.base == "koburi" and args.weight != "Regular":
        raise ValueError("GenEi Koburi Mincho is available in Regular only")
    if args.base == "koburi" and args.latin_source is not None:
        raise ValueError("--latin-source is available for the Noto base only")
    if args.base == "koburi" and args.ruby_source is not None:
        raise ValueError("--ruby-source is available for the Noto base only")
    if args.base == "koburi" and args.latin_family != "libertinus":
        raise ValueError("--latin-family is available for the Noto base only")
    if (
        args.base == "noto"
        and args.latin_family == "noto"
        and args.latin_source is not None
    ):
        raise ValueError("--latin-source cannot be combined with --latin-family noto")

    identity = font_identity(args.base, args.weight, args.kana_style)
    latin_profile = latin_build_profile(
        args.latin_family if args.base == "noto" else "noto",
        args.weight,
    )
    if args.output is not None:
        output_path = args.output
    elif args.base == "noto" and args.latin_family != "libertinus":
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
            ruby_source=args.ruby_source,
            punctuation_source=args.punctuation_source,
            sans_source=args.sans_source,
        ),
        latin_family=args.latin_family,
    )
    build(
        sources.source,
        sources.latin_source,
        sources.ruby_source,
        sources.punctuation_source,
        sources.sans_source,
        output_path,
        identity,
        latin_profile,
        args.face,
        args.base,
        args.autohint,
        args.kana_style,
    )
