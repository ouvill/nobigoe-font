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
from .variable_kana import build_variable_kana_source


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
        "--variable-kana",
        action="store_true",
        help=(
            "opt in to importing Novel kana from the pinned development "
            "variable-font source"
        ),
    )
    parser.add_argument(
        "--variable-kana-source",
        type=Path,
        help="local raw Noto Serif JP VF or rebuilt Novel kana design VF",
    )
    parser.add_argument(
        "--build-variable-kana",
        type=Path,
        metavar="OUTPUT",
        help=(
            "build the development Novel kana design VF at OUTPUT; "
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


def _build_variable_kana(args: argparse.Namespace) -> None:
    incompatible = [
        option
        for option, used in (
            ("--variable-kana", args.variable_kana),
            ("--output", args.output is not None),
            ("--source", args.source is not None),
            ("--latin-source", args.latin_source is not None),
            ("--ruby-source", args.ruby_source is not None),
            ("--punctuation-source", args.punctuation_source is not None),
            ("--sans-source", args.sans_source is not None),
            ("--autohint", args.autohint),
            ("--face", args.face != 0),
            ("--base koburi", args.base != "noto"),
            ("--kana-style novel", args.kana_style != "noto"),
            ("--weight", args.weight != "Regular"),
            ("--latin-family", args.latin_family != "libertinus"),
        )
        if used
    ]
    if incompatible:
        raise ValueError(
            "--build-variable-kana cannot be combined with " + ", ".join(incompatible)
        )
    source = SourceCache(args.cache_dir).resolve_variable_kana(
        args.variable_kana_source
    )
    result = build_variable_kana_source(source, args.build_variable_kana)
    print(
        f"Built development design VF at {result.output}; "
        "this output is not release-ready."
    )
    print(
        f"Encoded kana: {result.encoded_hiragana_count} hiragana, "
        f"{result.encoded_katakana_count} katakana; "
        f"adjusted terminals: {result.adjusted_terminal_count}; "
        f"unresolved terminals: {result.unresolved_terminal_count}."
    )
    if result.unresolved_terminal_count:
        print("Unresolved terminal inventory:")
        for entry in result.terminal_inventory:
            if entry.unresolved_count:
                print(
                    f"  {entry.weight_class} {entry.script} "
                    f"U+{entry.codepoint:04X} {entry.orientation} "
                    f"{entry.glyph_name}: {entry.unresolved_count}"
                )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.build_variable_kana is not None:
        _build_variable_kana(args)
        return
    if args.variable_kana_source is not None and not args.variable_kana:
        raise ValueError("--variable-kana-source requires --variable-kana")
    if args.variable_kana and (args.base != "noto" or args.kana_style != "novel"):
        raise ValueError("--variable-kana requires --kana-style novel with --base noto")
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
            variable_kana_source=args.variable_kana_source,
        ),
        latin_family=args.latin_family,
        variable_kana=args.variable_kana,
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
        sources.variable_kana_source,
    )
