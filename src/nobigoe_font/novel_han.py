"""Canonical Han whitespace adjustment for the Novel family."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import math
from typing import Iterable

from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont

from . import geometry

HAN_UNICODE_VERSION = "15.1"
HAN_SCALE = 1000 / 1024
HAN_CELL_CENTER = (500.0, 500.0)
HAN_FD_NAME_SUFFIX = "-NovelHanScaled"
HAN_TOP_FONT_MATRIX = (0.001, 0, 0, 0.001, 0, 0)
HAN_FD_FONT_MATRIX = (
    HAN_SCALE / 1000,
    0,
    0,
    HAN_SCALE / 1000,
    (HAN_CELL_CENTER[0] - HAN_SCALE * HAN_CELL_CENTER[0]) / 1000,
    (HAN_CELL_CENTER[1] - HAN_SCALE * HAN_CELL_CENTER[1]) / 1000,
)

# Unicode 15.1 CJK Unified Ideographs, Extensions A-I, and CJK
# Compatibility Ideographs including the Supplement. Endpoints are inclusive.
HAN_CODEPOINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
    (0x2EBF0, 0x2EE5F),
    (0x2F800, 0x2FA1F),
    (0x30000, 0x3134F),
    (0x31350, 0x323AF),
)

# Shape alternates that retain Han semantics, followed by vertical forms.
# Discretionary ligatures and ruby forms are presentation or sizing behavior
# rather than Han forms, so this transform leaves their existing shapes alone.
HAN_GSUB_FEATURES: tuple[str, ...] = (
    "aalt",
    "expt",
    "hojo",
    "jp04",
    "jp78",
    "jp83",
    "jp90",
    "locl",
    "nlck",
    "salt",
    "smpl",
    "trad",
    *(f"ss{index:02d}" for index in range(1, 21)),
    "vert",
    "vrt2",
)
HAN_VERTICAL_FEATURES = frozenset({"vert", "vrt2"})

# Explicitly protected families of non-Han mappings. A source alias between a
# target Han glyph and one of these mappings is a contract error because the
# shared outline could not be transformed without changing protected text.
_PROTECTED_CODEPOINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x024F),  # ASCII and Latin
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
    (0xAB30, 0xAB6F),  # Latin Extended-E
    (0xFB00, 0xFB06),  # Latin alphabetic presentation forms
    (0x10780, 0x107BF),  # Latin Extended-F
    (0x1DF00, 0x1DFFF),  # Latin Extended-G
    (0x2000, 0x27FF),  # punctuation, letterlike symbols, and added symbols
    (0x3000, 0x303F),  # CJK symbols and punctuation
    (0x3040, 0x30FF),  # hiragana and katakana
    (0x31F0, 0x31FF),  # katakana phonetic extensions
    (0xE000, 0xF8FF),  # project PUA mappings
    (0xFF00, 0xFF9F),  # fullwidth punctuation and halfwidth katakana
    (0xFFE0, 0xFFEF),
    (0x1AFF0, 0x1AFFF),
    (0x1B000, 0x1B16F),
)


@dataclass(frozen=True)
class HanFeatureReach:
    tag: str
    output_count: int
    added_count: int


@dataclass(frozen=True)
class HanGlyphPlan:
    encoded_codepoints: tuple[int, ...]
    encoded_glyphs: tuple[str, ...]
    alternate_glyphs: tuple[str, ...]
    vertical_glyphs: tuple[str, ...]
    target_glyphs: tuple[str, ...]
    non_han_aliases: tuple[tuple[int, str], ...]
    features: tuple[HanFeatureReach, ...]


def is_han_codepoint(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in HAN_CODEPOINT_RANGES)


def _is_protected_codepoint(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in _PROTECTED_CODEPOINT_RANGES)


def han_transform() -> Transform:
    center_x, center_y = HAN_CELL_CENTER
    return Transform(
        HAN_SCALE,
        0,
        0,
        HAN_SCALE,
        center_x - HAN_SCALE * center_x,
        center_y - HAN_SCALE * center_y,
    )


def _feature_lookup_indices(font: TTFont, feature_tag: str) -> tuple[int, ...]:
    if "GSUB" not in font:
        return ()
    indices: list[int] = []
    for record in font["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag == feature_tag:
            indices.extend(record.Feature.LookupListIndex)
    return tuple(dict.fromkeys(indices))


def _mapping_outputs(mapping: object, candidates: set[str]) -> set[str]:
    if not isinstance(mapping, dict):
        return set()
    outputs: set[str] = set()
    for source, destination in mapping.items():
        if source not in candidates:
            continue
        if isinstance(destination, str):
            outputs.add(destination)
        else:
            outputs.update(destination)
    return outputs


def _substitution_records(subtable: object) -> Iterable[object]:
    direct = getattr(subtable, "SubstLookupRecord", None)
    if direct:
        yield from direct
    for collection_name in (
        "SubRuleSet",
        "SubClassSet",
        "ChainSubRuleSet",
        "ChainSubClassSet",
    ):
        for rule_set in getattr(subtable, collection_name, None) or ():
            if rule_set is None:
                continue
            rules = (
                getattr(rule_set, "SubRule", None)
                or getattr(rule_set, "ChainSubRule", None)
                or getattr(rule_set, "SubClassRule", None)
                or getattr(rule_set, "ChainSubClassRule", None)
                or ()
            )
            for rule in rules:
                yield from getattr(rule, "SubstLookupRecord", None) or ()


def _context_intersects(subtable: object, candidates: set[str]) -> bool:
    coverages = getattr(subtable, "InputCoverage", None)
    if coverages:
        return any(candidates.intersection(coverage.glyphs) for coverage in coverages)
    coverage = getattr(subtable, "Coverage", None)
    return coverage is None or bool(candidates.intersection(coverage.glyphs))


def _lookup_outputs(
    font: TTFont,
    lookup_index: int,
    candidates: set[str],
    active_lookups: frozenset[int] = frozenset(),
) -> set[str]:
    if lookup_index in active_lookups:
        return set()
    lookup = font["GSUB"].table.LookupList.Lookup[lookup_index]
    outputs: set[str] = set()
    nested_active = active_lookups | {lookup_index}
    for original_subtable in lookup.SubTable:
        lookup_type = lookup.LookupType
        subtable = original_subtable
        if lookup_type == 7:
            lookup_type = subtable.ExtensionLookupType
            subtable = subtable.ExtSubTable

        if lookup_type in {1, 2, 8}:
            outputs.update(
                _mapping_outputs(getattr(subtable, "mapping", None), candidates)
            )
        elif lookup_type == 3:
            outputs.update(
                _mapping_outputs(getattr(subtable, "alternates", None), candidates)
            )
        elif lookup_type == 4:
            for first, ligatures in getattr(subtable, "ligatures", {}).items():
                if first not in candidates:
                    continue
                for ligature in ligatures:
                    if all(component in candidates for component in ligature.Component):
                        outputs.add(ligature.LigGlyph)
        elif lookup_type in {5, 6}:
            if not _context_intersects(subtable, candidates):
                continue
            for record in _substitution_records(subtable):
                outputs.update(
                    _lookup_outputs(
                        font,
                        record.LookupListIndex,
                        candidates,
                        nested_active,
                    )
                )
    return outputs


def collect_novel_han_glyphs(font: TTFont) -> HanGlyphPlan:
    """Collect encoded and reachable alternate Han glyphs without mutation."""
    cmap = font.getBestCmap() or {}
    glyph_order = font.getGlyphOrder()
    glyph_ids = {name: index for index, name in enumerate(glyph_order)}
    encoded_codepoints = tuple(
        sorted(codepoint for codepoint in cmap if is_han_codepoint(codepoint))
    )
    encoded = {cmap[codepoint] for codepoint in encoded_codepoints}
    if not encoded:
        raise ValueError("The Noto source has no encoded Unicode 15.1 Han glyphs")

    reachable = set(encoded)
    feature_outputs = {tag: set() for tag in HAN_GSUB_FEATURES}
    feature_additions = {tag: set() for tag in HAN_GSUB_FEATURES}
    changed = True
    while changed:
        changed = False
        for tag in HAN_GSUB_FEATURES:
            outputs: set[str] = set()
            for lookup_index in _feature_lookup_indices(font, tag):
                outputs.update(_lookup_outputs(font, lookup_index, reachable))
            feature_outputs[tag].update(outputs)
            added = outputs - reachable
            if added:
                feature_additions[tag].update(added)
                reachable.update(added)
                changed = True

    missing = sorted(reachable.difference(glyph_ids))
    if missing:
        raise ValueError(
            "Han GSUB graph references missing glyphs: " + ", ".join(missing)
        )

    protected = {
        name for codepoint, name in cmap.items() if _is_protected_codepoint(codepoint)
    }
    conflicts = sorted(reachable.intersection(protected))
    if conflicts:
        raise ValueError(
            "Han glyph aliases protected Kana, punctuation, Latin, symbol, or PUA "
            "mappings: " + ", ".join(conflicts)
        )

    vertical = set().union(*(feature_outputs[tag] for tag in HAN_VERTICAL_FEATURES))
    alternate = reachable - encoded - vertical
    non_han_aliases = tuple(
        sorted(
            (codepoint, name)
            for codepoint, name in cmap.items()
            if not is_han_codepoint(codepoint) and name in reachable
        )
    )
    ordered = lambda names: tuple(sorted(names, key=glyph_ids.__getitem__))
    features = tuple(
        HanFeatureReach(
            tag,
            len(feature_outputs[tag]),
            len(feature_additions[tag]),
        )
        for tag in HAN_GSUB_FEATURES
        if _feature_lookup_indices(font, tag)
    )
    return HanGlyphPlan(
        encoded_codepoints=encoded_codepoints,
        encoded_glyphs=ordered(encoded),
        alternate_glyphs=ordered(alternate),
        vertical_glyphs=ordered(vertical),
        target_glyphs=ordered(reachable),
        non_han_aliases=non_han_aliases,
        features=features,
    )


def apply_novel_han(font: TTFont) -> HanGlyphPlan:
    """Assign contracted Han to scaled CID Font DICT clones without rewriting."""

    plan = collect_novel_han_glyphs(font)
    if "CFF " not in font:
        raise ValueError("Novel Han requires a CID-keyed OpenType/CFF source")
    top = font["CFF "].cff.topDictIndex[0]
    if not all(hasattr(top, name) for name in ("ROS", "FDArray", "FDSelect")):
        raise ValueError("Novel Han requires CFF FDArray and FDSelect")
    if tuple(top.FontMatrix) != HAN_TOP_FONT_MATRIX:
        raise ValueError(
            f"Novel Han requires top FontMatrix {HAN_TOP_FONT_MATRIX}, "
            f"got {tuple(top.FontMatrix)}"
        )

    glyph_ids = {name: font.getGlyphID(name) for name in plan.target_glyphs}
    source_fd_indices = {top.FDSelect[glyph_id] for glyph_id in glyph_ids.values()}
    prepared_metrics: dict[str, tuple[int, int]] = {}
    transform = han_transform()

    # Validate the complete batch before mutating FDArray, FDSelect, or metrics.
    for name in plan.target_glyphs:
        outline = geometry.glyph_path(font, name)
        if not outline.verbs:
            raise ValueError(f"Han glyph {name!r} has an empty outline")
        transformed = geometry.transform_path(outline, transform)
        bounds = transformed.bounds
        if not all(math.isfinite(value) for value in bounds):
            raise ValueError(f"Han glyph {name!r} has non-finite transformed bounds")
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError(f"Han glyph {name!r} has non-positive transformed bounds")

        horizontal_advance = font["hmtx"].metrics[name][0]
        if horizontal_advance != 1000:
            raise ValueError(
                f"Han glyph {name!r} has hAdvance {horizontal_advance}, expected 1000"
            )
        horizontal_side_bearing = math.floor(bounds[0])
        vertical_side_bearing = 0
        if "vmtx" in font:
            vertical_advance, top_side_bearing = font["vmtx"].metrics[name]
            if vertical_advance != 1000:
                raise ValueError(
                    f"Han glyph {name!r} has vAdvance {vertical_advance}, expected 1000"
                )
            vertical_origin = top_side_bearing + outline.bounds[3]
            vertical_side_bearing = round(vertical_origin - bounds[3])
        prepared_metrics[name] = (
            horizontal_side_bearing,
            vertical_side_bearing,
        )

    scaled_fd_indices: dict[int, int] = {}
    for source_index in sorted(source_fd_indices):
        source_fd = top.FDArray[source_index]
        if getattr(source_fd, "FontMatrix", None) is not None:
            raise ValueError(
                f"Novel Han source FD {source_index} already has a FontMatrix"
            )
        if not hasattr(source_fd, "Private"):
            raise ValueError(f"Novel Han source FD {source_index} has no Private DICT")

        scaled_private = copy(source_fd.Private)
        scaled_private.rawDict = dict(source_fd.Private.rawDict)
        scaled_fd = copy(source_fd)
        scaled_fd.rawDict = dict(source_fd.rawDict)
        scaled_fd.Private = scaled_private
        scaled_fd.FontName = f"{source_fd.FontName}{HAN_FD_NAME_SUFFIX}"
        scaled_fd.FontMatrix = list(HAN_FD_FONT_MATRIX)
        scaled_index = len(top.FDArray)
        top.FDArray.append(scaled_fd)
        scaled_fd_indices[source_index] = scaled_index

    for name, glyph_id in glyph_ids.items():
        source_index = top.FDSelect[glyph_id]
        top.FDSelect[glyph_id] = scaled_fd_indices[source_index]
        horizontal_side_bearing, vertical_side_bearing = prepared_metrics[name]
        font["hmtx"].metrics[name] = (1000, horizontal_side_bearing)
        if "vmtx" in font:
            font["vmtx"].metrics[name] = (1000, vertical_side_bearing)

    return plan
