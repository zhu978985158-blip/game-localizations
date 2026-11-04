#!/usr/bin/env python3
"""Static QA for the ARM Cheat Menu 2.2 Chinese build."""

from __future__ import annotations

import configparser
import hashlib
import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

import build_font
import patch_mod


ARRAYS = [
    ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    ["Dark", "Classic", "Light", "PC Cheat Menu", "Pink. mine>-<"],
    ["Custom", "Top left", "Top right", "Bottom left", "Bottom right"],
    ["All", "Male", "Female"],
    ["Default", "Boxing", "Kung Fu", "Kick Boxing", "Punch Kick"],
    ["All", "Bikes", "Boats", "Cars", "Planes", "Helis", "Trailers", "Trains"],
    ["StatFat", "Type", "gang1", "swat"],
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_simple_toml(path: Path) -> tuple[dict[tuple[str, str], str], list[str]]:
    result: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    section = ""
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            errors.append(f"line {line_number}: missing equals sign")
            continue
        key, value = line.split("=", 1)
        identity = (section, key.strip())
        if identity in result:
            errors.append(f"line {line_number}: duplicate key {identity}")
        try:
            result[identity] = json.loads(value.strip())
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid basic string: {exc}")
    return result, errors


def parse_dat_ids(path: Path) -> list[int]:
    result: list[int] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        result.append(int(fields[-1]))
    return result


def parse_ini(path: Path) -> dict[tuple[str, str], str]:
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    with path.open("r", encoding="utf-8") as handle:
        parser.read_file(handle)
    return {(section, key): value for section in parser.sections() for key, value in parser.items(section)}


def allowed_diff_offsets(original: Path) -> list[range]:
    image = patch_mod.ElfImage(original)
    default_value = image.symbols[patch_mod.SYM_DEFAULT][0] & ~1
    legacy_value = image.symbols[patch_mod.SYM_LEGACY_PRELOAD][0] & ~1
    default_offset = image.file_offset(default_value)
    if image.elf_class == 2:
        legacy_offset = image.file_offset(legacy_value + 0x40)
        allowed = [range(default_offset, default_offset + 4), range(legacy_offset, legacy_offset + 4)]
    else:
        literal = image.file_offset(default_value + 8)
        legacy_literal = image.file_offset(legacy_value + 0x160)
        allowed = [range(literal, literal + 4), range(legacy_literal, legacy_literal + 4)]
    for fields in ARRAYS:
        needle = patch_mod.packed_fields(fields)
        start = image.data.find(needle)
        if start < 0 or image.data.count(needle) != 1:
            raise ValueError(f"cannot resolve original UI array: {fields}")
        allowed.append(range(start, start + len(needle)))
    world = b"\0World\0"
    if image.data.count(world) != 1:
        raise ValueError("cannot resolve standalone World label")
    world_start = image.data.find(world) + 1
    allowed.append(range(world_start, world_start + len("World") + 1))
    unavailable = b"\0Not yet Available\0"
    if image.data.count(unavailable) != 1:
        raise ValueError("cannot resolve standalone Not yet Available label")
    unavailable_start = image.data.find(unavailable) + 1
    allowed.append(range(unavailable_start, unavailable_start + len("Not yet Available") + 1))
    return allowed


def verify_binary(original: Path, patched: Path) -> dict[str, object]:
    before = original.read_bytes()
    after = patched.read_bytes()
    if len(before) != len(after):
        raise AssertionError(f"binary size changed: {patched.name}")
    differences = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
    allowed = allowed_diff_offsets(original)
    outside = [index for index in differences if not any(index in region for region in allowed)]
    if outside:
        raise AssertionError(f"unexpected binary differences in {patched.name}: {outside[:20]}")
    if b"\0Not yet Available\0" in after:
        raise AssertionError(f"untranslated Not yet Available label remains in {patched.name}")
    translated_unavailable = "暂不可用".encode("utf-8") + b"\0" * 6
    if after.count(translated_unavailable) != 1:
        raise AssertionError(f"translated not-available label missing in {patched.name}")

    image = patch_mod.ElfImage(patched)
    default_value = image.symbols[patch_mod.SYM_DEFAULT][0] & ~1
    chinese_value = image.symbols[patch_mod.SYM_CHINESE_FULL][0] & ~1
    legacy_value = image.symbols[patch_mod.SYM_LEGACY_PRELOAD][0] & ~1
    default_offset = image.file_offset(default_value)
    if image.elf_class == 2:
        def decode_adr(instruction: int, address: int) -> int:
            if instruction & 0x9F000000 != 0x10000000:
                raise AssertionError(f"unexpected AArch64 ADR at 0x{address:x}")
            immlo = (instruction >> 29) & 0x3
            immhi = (instruction >> 5) & 0x7FFFF
            immediate = (immhi << 2) | immlo
            if immediate & (1 << 20):
                immediate -= 1 << 21
            return address + immediate

        instruction = int.from_bytes(image.data[default_offset : default_offset + 4], "little")
        immediate = instruction & 0x03FFFFFF
        if immediate & 0x02000000:
            immediate -= 0x04000000
        target = default_value + immediate * 4
        if instruction >> 26 != 0b000101 or target != chinese_value:
            raise AssertionError("AArch64 glyph-range branch does not target ChineseFull")
        glyph_target = f"0x{target:x}"
        chinese_adr_address = chinese_value + 4
        chinese_adr_offset = image.file_offset(chinese_adr_address)
        chinese_range = decode_adr(
            int.from_bytes(image.data[chinese_adr_offset : chinese_adr_offset + 4], "little"),
            chinese_adr_address,
        )
        legacy_adr_address = legacy_value + 0x40
        legacy_adr_offset = image.file_offset(legacy_adr_address)
        legacy_adr = int.from_bytes(image.data[legacy_adr_offset : legacy_adr_offset + 4], "little")
        legacy_target = decode_adr(legacy_adr, legacy_adr_address)
        if (legacy_adr & 0x1F) != 23 or legacy_target != chinese_range:
            raise AssertionError("AArch64 legacy preload does not target ChineseFull range data")
    else:
        literal = int.from_bytes(image.data[default_offset + 8 : default_offset + 12], "little", signed=True)
        target = default_value + 6 + literal
        original_image = patch_mod.ElfImage(original)
        source_offset = original_image.file_offset(chinese_value + 8)
        source_literal = int.from_bytes(
            original_image.data[source_offset : source_offset + 4], "little", signed=True
        )
        expected = chinese_value + 6 + source_literal
        if target != expected:
            raise AssertionError("ARM32 glyph-range literal does not target ChineseFull data")
        glyph_target = f"0x{target:x}"
        legacy_literal_offset = image.file_offset(legacy_value + 0x160)
        legacy_literal = int.from_bytes(
            image.data[legacy_literal_offset : legacy_literal_offset + 4], "little", signed=True
        )
        legacy_pc = (legacy_value + 0x108 + 4) & ~3
        legacy_target = legacy_pc + legacy_literal
        if legacy_target != expected:
            raise AssertionError("ARM32 legacy preload does not target ChineseFull range data")
        chinese_range = expected

    return {
        "file": patched.name,
        "size_unchanged": True,
        "changed_bytes": len(differences),
        "unexpected_changed_bytes": len(outside),
        "glyph_target": glyph_target,
        "legacy_preload_range": f"0x{legacy_target:x}",
        "chinese_range": f"0x{chinese_range:x}",
        "sha256_original": sha256(original),
        "sha256_patched": sha256(patched),
    }


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: qa_mod.py ORIGINAL_PACKAGE PATCHED_PACKAGE REPORT_JSON", file=sys.stderr)
        return 2
    original = Path(sys.argv[1])
    patched = Path(sys.argv[2])
    report_path = Path(sys.argv[3])

    english, english_errors = parse_simple_toml(original / "ARM/CheatMenu/locale/English.toml")
    chinese, chinese_errors = parse_simple_toml(patched / "ARM/CheatMenu/locale/Chinese.toml")
    missing = sorted(set(english) - set(chinese))
    extra = sorted(set(chinese) - set(english))
    if english_errors or chinese_errors or missing or extra or len(chinese) != 251:
        raise AssertionError(
            f"locale validation failed: English={english_errors}, Chinese={chinese_errors}, "
            f"missing={missing}, extra={extra}, count={len(chinese)}"
        )

    original_config = parse_ini(original / "configs/ARM.CheatMenu.ini")
    patched_config = parse_ini(patched / "configs/ARM.CheatMenu.ini")
    config_differences = {
        key: (original_config.get(key), patched_config.get(key))
        for key in set(original_config) | set(patched_config)
        if original_config.get(key) != patched_config.get(key)
    }
    expected_config_difference = {("Menu", "Language"): ("English", "Chinese")}
    if config_differences != expected_config_difference:
        raise AssertionError(f"unexpected config differences: {config_differences}")

    original_cheats = parse_dat_ids(original / "ARM/CheatMenu/data/cheats.dat")
    patched_cheats = parse_dat_ids(patched / "ARM/CheatMenu/data/cheats.dat")
    original_weapons = parse_dat_ids(original / "ARM/CheatMenu/data/weapons.dat")
    patched_weapons = parse_dat_ids(patched / "ARM/CheatMenu/data/weapons.dat")
    if original_cheats != patched_cheats or original_weapons != patched_weapons:
        raise AssertionError("cheat or weapon numeric IDs changed")

    preserved_files = [
        "ARM/CheatMenu/locale/English.toml",
        "ARM/CheatMenu/locale/Indonesia.toml",
        "ARM/CheatMenu/data/cutscenes.dat",
        "ARM/CheatMenu/data/addonskin.dat",
    ]
    for relative in preserved_files:
        if (original / relative).read_bytes() != (patched / relative).read_bytes():
            raise AssertionError(f"protected file changed: {relative}")

    required = build_font.collect_characters(patched)
    font_path = patched / "ARM/CheatMenu/font/MyFont.ttf"
    font = TTFont(font_path, lazy=False)
    cmap: set[int] = set()
    for table in font["cmap"].tables:
        cmap.update(table.cmap)
    font_missing = sorted(required - cmap)
    if font_missing or "glyf" not in font or "fvar" in font or "CFF " in font or "CFF2" in font:
        raise AssertionError(f"font validation failed: missing={font_missing[:20]}")

    binary_reports = [
        verify_binary(original / "libCheatMenu.so", patched / "libCheatMenu.so"),
        verify_binary(original / "libCheatMenu64.so", patched / "libCheatMenu64.so"),
    ]

    report = {
        "locale": {
            "english_keys": len(english),
            "chinese_keys": len(chinese),
            "missing_keys": len(missing),
            "extra_keys": len(extra),
            "syntax_errors": len(english_errors) + len(chinese_errors),
        },
        "data_lists": {
            "cheat_entries": len(patched_cheats),
            "weapon_entries": len(patched_weapons),
            "cheat_ids_unchanged": original_cheats == patched_cheats,
            "weapon_ids_unchanged": original_weapons == patched_weapons,
        },
        "configuration": {
            "only_change": "Menu.Language: English -> Chinese",
            "total_keys": len(patched_config),
        },
        "font": {
            "file": "ARM/CheatMenu/font/MyFont.ttf",
            "size": font_path.stat().st_size,
            "required_codepoints": len(required),
            "covered_codepoints": len(required & cmap),
            "missing_codepoints": len(font_missing),
            "true_type_glyf": "glyf" in font,
            "static_font": "fvar" not in font,
        },
        "binaries": binary_reports,
        "protected_files_unchanged": preserved_files,
        "result": "ALL STATIC CHECKS PASSED",
        "runtime_test": "Not performed; Android game/device validation is still required.",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
