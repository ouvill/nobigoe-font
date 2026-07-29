"""Naming and style metadata updates for generated fonts."""

from __future__ import annotations

from fontTools.ttLib import TTFont

from .profiles import FontIdentity, VERSION, VERSION_NUMBER


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name_table = font["name"]
    matching = [record for record in name_table.names if record.nameID == name_id]
    if matching:
        for record in matching:
            name_table.setName(
                value,
                name_id,
                record.platformID,
                record.platEncID,
                record.langID,
            )
    else:
        name_table.setName(value, name_id, 3, 1, 0x409)


def set_japanese_name(font: TTFont, name_id: int, value: str) -> None:
    font["name"].setName(value, name_id, 3, 1, 0x411)


def rename_font(
    font: TTFont,
    copyright_notice: str,
    font_notice: str,
    identity: FontIdentity,
) -> None:
    legacy_style = "Bold" if identity.style == "Bold" else "Regular"
    set_name(font, 0, copyright_notice)
    set_name(font, 1, identity.legacy_family)
    set_name(font, 2, legacy_style)
    set_name(
        font,
        3,
        f"{VERSION_NUMBER};NOBIGOE;{identity.postscript_name}",
    )
    set_name(font, 4, identity.full_name)
    set_name(font, 5, VERSION)
    set_name(font, 6, identity.postscript_name)
    set_name(font, 16, identity.family)
    set_name(font, 17, identity.style)
    set_japanese_name(font, 1, identity.japanese_legacy_family)
    set_japanese_name(font, 4, identity.japanese_full_name)
    set_japanese_name(font, 16, identity.japanese_family)
    set_japanese_name(font, 17, identity.style)

    font["OS/2"].usWeightClass = identity.weight_class
    font["OS/2"].fsSelection &= ~((1 << 5) | (1 << 6))
    if identity.style == "Regular":
        font["OS/2"].fsSelection |= 1 << 6
    elif identity.style == "Bold":
        font["OS/2"].fsSelection |= 1 << 5
    font["head"].macStyle &= ~1
    if identity.style == "Bold":
        font["head"].macStyle |= 1

    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames = [identity.postscript_name]
        top = cff.topDictIndex[0]
        top.Notice = font_notice.encode("latin-1", "replace").decode("latin-1")
        top.FamilyName = identity.family
        top.FullName = identity.full_name
