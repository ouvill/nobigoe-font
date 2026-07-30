"""Validated optical terminal-depth plans for encoded Novel kana."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Literal, TypeAlias

from ..novel import HIRAGANA_CODEPOINTS
from ..novel_katakana import KATAKANA_SOURCE_CODEPOINTS
from . import (
    hiragana_3041_3054,
    hiragana_3055_3069,
    hiragana_306A_307D,
    hiragana_307E_3088,
    hiragana_3089_309F,
    katakana_30A1_30B4,
    katakana_30B5_30C9,
    katakana_30CA_30DD,
    katakana_30DE_30F6,
    katakana_30F7_31FF,
)

KanaScript: TypeAlias = Literal["hiragana", "katakana"]
KanaOrientation: TypeAlias = Literal["horizontal", "vertical"]
TerminalDepthMasters: TypeAlias = dict[int, tuple[float, float]]

_MASTER_WEIGHTS = frozenset((200, 400, 900))
_MIN_SCALE = 0.70
_MAX_SCALE = 1.35
_BASE_DEPTH_RATIO = 0.18
_MODULES = (
    (hiragana_3041_3054, "hiragana", 0x3041, 0x3054),
    (hiragana_3055_3069, "hiragana", 0x3055, 0x3069),
    (hiragana_306A_307D, "hiragana", 0x306A, 0x307D),
    (hiragana_307E_3088, "hiragana", 0x307E, 0x3088),
    (hiragana_3089_309F, "hiragana", 0x3089, 0x309F),
    (katakana_30A1_30B4, "katakana", 0x30A1, 0x30B4),
    (katakana_30B5_30C9, "katakana", 0x30B5, 0x30C9),
    (katakana_30CA_30DD, "katakana", 0x30CA, 0x30DD),
    (katakana_30DE_30F6, "katakana", 0x30DE, 0x30F6),
    (katakana_30F7_31FF, "katakana", 0x30F7, 0x31FF),
)


def _codepoints_for_script(script: str) -> frozenset[int]:
    if script == "hiragana":
        return HIRAGANA_CODEPOINTS
    if script == "katakana":
        return KATAKANA_SOURCE_CODEPOINTS
    raise ValueError(f"Unknown kana script {script!r}")


def _validated_terminal_depth_scales() -> dict[int, TerminalDepthMasters]:
    loaded: dict[int, TerminalDepthMasters] = {}
    owners: dict[int, str] = {}
    expected_all = HIRAGANA_CODEPOINTS | KATAKANA_SOURCE_CODEPOINTS

    for module, script, first, last in _MODULES:
        module_name = module.__name__
        raw_plan = getattr(module, "TERMINAL_DEPTH_SCALES", None)
        if not isinstance(raw_plan, Mapping):
            raise ValueError(f"{module_name}.TERMINAL_DEPTH_SCALES must be a mapping")
        if any(isinstance(key, bool) or not isinstance(key, int) for key in raw_plan):
            raise ValueError(f"{module_name} codepoint keys must be integers")

        actual = set(raw_plan)
        expected = {
            codepoint
            for codepoint in _codepoints_for_script(script)
            if first <= codepoint <= last
        }
        missing = expected - actual
        extra = actual - expected
        if missing or extra:
            details = [
                *(f"missing U+{codepoint:04X}" for codepoint in sorted(missing)),
                *(f"extra U+{codepoint:04X}" for codepoint in sorted(extra)),
            ]
            raise ValueError(f"{module_name}: {', '.join(details)}")

        for codepoint, raw_masters in raw_plan.items():
            previous_owner = owners.get(codepoint)
            if previous_owner is not None:
                raise ValueError(
                    f"Duplicate terminal plan for U+{codepoint:04X} in "
                    f"{previous_owner} and {module_name}"
                )
            owners[codepoint] = module_name
            if not isinstance(raw_masters, Mapping):
                raise ValueError(
                    f"{module_name} U+{codepoint:04X} must map weights to scales"
                )
            if any(
                isinstance(weight, bool) or not isinstance(weight, int)
                for weight in raw_masters
            ):
                raise ValueError(
                    f"{module_name} U+{codepoint:04X} master keys must be integers"
                )
            if set(raw_masters) != _MASTER_WEIGHTS:
                raise ValueError(
                    f"{module_name} U+{codepoint:04X} must contain only masters "
                    "200, 400, and 900"
                )

            masters: TerminalDepthMasters = {}
            for weight, raw_scales in raw_masters.items():
                if not isinstance(raw_scales, tuple) or len(raw_scales) != 2:
                    raise ValueError(
                        f"{module_name} U+{codepoint:04X} weight {weight} must be "
                        "a (horizontal, vertical) tuple"
                    )
                if any(
                    isinstance(scale, bool)
                    or not isinstance(scale, (int, float))
                    or not math.isfinite(scale)
                    or not _MIN_SCALE <= scale <= _MAX_SCALE
                    for scale in raw_scales
                ):
                    raise ValueError(
                        f"{module_name} U+{codepoint:04X} weight {weight} scales "
                        f"must be finite numbers in {_MIN_SCALE:.2f}..{_MAX_SCALE:.2f}"
                    )
                masters[weight] = (float(raw_scales[0]), float(raw_scales[1]))
            loaded[codepoint] = masters

    actual_all = set(loaded)
    if actual_all != expected_all:
        missing = expected_all - actual_all
        extra = actual_all - expected_all
        details = [
            *(f"missing U+{codepoint:04X}" for codepoint in sorted(missing)),
            *(f"extra U+{codepoint:04X}" for codepoint in sorted(extra)),
        ]
        raise ValueError(f"Terminal plans: {', '.join(details)}")
    if len(loaded) != 198:
        raise AssertionError("Terminal plans must cover 89 hiragana and 109 katakana")
    return loaded


_TERMINAL_DEPTH_SCALES = _validated_terminal_depth_scales()


def terminal_depth_ratio(
    script: KanaScript,
    codepoint: int,
    orientation: KanaOrientation,
    weight_class: int,
) -> float:
    """Return the tuned convex-tip depth ratio for one semantic kana owner."""

    if codepoint not in _codepoints_for_script(script):
        raise ValueError(
            f"U+{codepoint:04X} is not an encoded {script} terminal-plan owner"
        )
    if orientation == "horizontal":
        orientation_index = 0
    elif orientation == "vertical":
        orientation_index = 1
    else:
        raise ValueError(f"Unknown kana orientation {orientation!r}")
    if weight_class not in _MASTER_WEIGHTS:
        raise ValueError(
            f"Terminal depth plans contain only masters 200, 400, and 900; got {weight_class!r}"
        )
    return (
        _BASE_DEPTH_RATIO
        * _TERMINAL_DEPTH_SCALES[codepoint][weight_class][orientation_index]
    )


__all__ = ("terminal_depth_ratio",)
