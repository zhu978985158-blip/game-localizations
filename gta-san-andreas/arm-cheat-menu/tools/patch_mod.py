#!/usr/bin/env python3
"""Patch ARM Cheat Menu 2.2 for CJK glyphs and visible hard-coded labels.

The patch is intentionally narrow:
- redirects ImGui's exported default glyph range and its inlined legacy-preload
  fallback to the built-in Chinese-full range;
- translates a few small UI arrays that are not routed through locale TOML;
- leaves game IDs, model names, symbols, logging strings, and code untouched.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


SYM_DEFAULT = "_ZN11ImFontAtlas21GetGlyphRangesDefaultEv"
SYM_CHINESE_FULL = "_ZN11ImFontAtlas25GetGlyphRangesChineseFullEv"
SYM_LEGACY_PRELOAD = "_Z43ImFontAtlasBuildLegacyPreloadAllGlyphRangesP11ImFontAtlas"


@dataclass
class Section:
    name_offset: int
    section_type: int
    address: int
    offset: int
    size: int
    link: int
    entry_size: int


class ElfImage:
    def __init__(self, path: Path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        if self.data[:4] != b"\x7fELF":
            raise ValueError(f"not an ELF file: {path}")
        self.elf_class = self.data[4]
        self.endian = "<" if self.data[5] == 1 else ">"
        if self.endian != "<":
            raise ValueError("only little-endian ELF files are supported")
        self.machine = struct.unpack_from(self.endian + "H", self.data, 18)[0]
        self.sections = self._read_sections()
        self.load_segments = self._read_load_segments()
        self.symbols = self._read_dynamic_symbols()

    def _read_sections(self) -> list[Section]:
        if self.elf_class == 2:
            shoff = struct.unpack_from(self.endian + "Q", self.data, 40)[0]
            shentsize, shnum = struct.unpack_from(self.endian + "HH", self.data, 58)
            fmt = self.endian + "IIQQQQIIQQ"
        elif self.elf_class == 1:
            shoff = struct.unpack_from(self.endian + "I", self.data, 32)[0]
            shentsize, shnum = struct.unpack_from(self.endian + "HH", self.data, 46)
            fmt = self.endian + "IIIIIIIIII"
        else:
            raise ValueError(f"unsupported ELF class: {self.elf_class}")

        sections: list[Section] = []
        for index in range(shnum):
            values = struct.unpack_from(fmt, self.data, shoff + index * shentsize)
            sections.append(
                Section(
                    name_offset=values[0],
                    section_type=values[1],
                    address=values[3],
                    offset=values[4],
                    size=values[5],
                    link=values[6],
                    entry_size=values[9],
                )
            )
        return sections

    def _read_load_segments(self) -> list[tuple[int, int, int]]:
        if self.elf_class == 2:
            phoff = struct.unpack_from(self.endian + "Q", self.data, 32)[0]
            phentsize, phnum = struct.unpack_from(self.endian + "HH", self.data, 54)
            fmt = self.endian + "IIQQQQQQ"
        else:
            phoff = struct.unpack_from(self.endian + "I", self.data, 28)[0]
            phentsize, phnum = struct.unpack_from(self.endian + "HH", self.data, 42)
            fmt = self.endian + "IIIIIIII"

        segments: list[tuple[int, int, int]] = []
        for index in range(phnum):
            values = struct.unpack_from(fmt, self.data, phoff + index * phentsize)
            if values[0] != 1:  # PT_LOAD
                continue
            if self.elf_class == 2:
                file_offset, vaddr, file_size = values[2], values[3], values[5]
            else:
                file_offset, vaddr, file_size = values[1], values[2], values[4]
            segments.append((vaddr, file_offset, file_size))
        return segments

    def _read_dynamic_symbols(self) -> dict[str, tuple[int, int]]:
        symbols: dict[str, tuple[int, int]] = {}
        for section in self.sections:
            if section.section_type != 11:  # SHT_DYNSYM
                continue
            strings = self.sections[section.link]
            string_data = self.data[strings.offset : strings.offset + strings.size]
            if self.elf_class == 2:
                fmt = self.endian + "IBBHQQ"
            else:
                fmt = self.endian + "IIIBBH"
            entry_size = section.entry_size or struct.calcsize(fmt)
            for offset in range(section.offset, section.offset + section.size, entry_size):
                values = struct.unpack_from(fmt, self.data, offset)
                if self.elf_class == 2:
                    name_offset, value, size = values[0], values[4], values[5]
                else:
                    name_offset, value, size = values[0], values[1], values[2]
                end = string_data.find(b"\0", name_offset)
                if name_offset == 0 or end < 0:
                    continue
                name = bytes(string_data[name_offset:end]).decode("utf-8", "replace")
                symbols[name] = (value, size)
        return symbols

    def file_offset(self, vaddr: int) -> int:
        for seg_vaddr, seg_offset, seg_size in self.load_segments:
            if seg_vaddr <= vaddr < seg_vaddr + seg_size:
                return seg_offset + (vaddr - seg_vaddr)
        raise ValueError(f"virtual address not backed by file data: 0x{vaddr:x}")

    def patch_glyph_range(self) -> dict[str, object]:
        default_value = self.symbols[SYM_DEFAULT][0] & ~1
        chinese_value = self.symbols[SYM_CHINESE_FULL][0] & ~1
        legacy_value = self.symbols[SYM_LEGACY_PRELOAD][0] & ~1
        default_offset = self.file_offset(default_value)
        chinese_offset = self.file_offset(chinese_value)

        if self.elf_class == 2 and self.machine == 183:  # AArch64
            def decode_adr(instruction: int, address: int) -> int:
                if instruction & 0x9F000000 != 0x10000000:
                    raise ValueError(f"unexpected AArch64 ADR at 0x{address:x}")
                immlo = (instruction >> 29) & 0x3
                immhi = (instruction >> 5) & 0x7FFFF
                immediate = (immhi << 2) | immlo
                if immediate & (1 << 20):
                    immediate -= 1 << 21
                return address + immediate

            def encode_adr(register: int, address: int, target: int) -> int:
                delta = target - address
                if not -(1 << 20) <= delta < (1 << 20):
                    raise ValueError("AArch64 ADR target is out of range")
                immediate = delta & ((1 << 21) - 1)
                return (
                    0x10000000
                    | ((immediate & 0x3) << 29)
                    | (((immediate >> 2) & 0x7FFFF) << 5)
                    | register
                )

            original = struct.unpack_from("<I", self.data, default_offset)[0]
            if original != 0xD503201F:  # nop
                raise ValueError(f"unexpected AArch64 prologue at 0x{default_value:x}")
            delta = chinese_value - default_value
            if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
                raise ValueError("AArch64 branch target is out of range")
            branch = 0x14000000 | ((delta >> 2) & 0x03FFFFFF)
            struct.pack_into("<I", self.data, default_offset, branch)

            default_adr_address = default_value + 4
            chinese_adr_address = chinese_value + 4
            default_range = decode_adr(
                struct.unpack_from("<I", self.data, self.file_offset(default_adr_address))[0],
                default_adr_address,
            )
            chinese_range = decode_adr(
                struct.unpack_from("<I", self.data, self.file_offset(chinese_adr_address))[0],
                chinese_adr_address,
            )
            legacy_adr_address = legacy_value + 0x40
            legacy_adr_offset = self.file_offset(legacy_adr_address)
            legacy_adr = struct.unpack_from("<I", self.data, legacy_adr_offset)[0]
            if (legacy_adr & 0x1F) != 23 or decode_adr(legacy_adr, legacy_adr_address) != default_range:
                raise ValueError("unexpected AArch64 inlined default glyph-range fallback")
            struct.pack_into(
                "<I",
                self.data,
                legacy_adr_offset,
                encode_adr(23, legacy_adr_address, chinese_range),
            )
            return {
                "architecture": "arm64-v8a",
                "default_symbol": f"0x{default_value:x}",
                "chinese_symbol": f"0x{chinese_value:x}",
                "chinese_range": f"0x{chinese_range:x}",
                "function_patch": f"AArch64 B 0x{chinese_value:x}",
                "legacy_fallback_patch": f"AArch64 ADR x23, 0x{chinese_range:x}",
            }

        if self.elf_class == 1 and self.machine == 40:  # ARM / Thumb-2
            expected = b"\x01\x48\x78\x44\x70\x47\x00\xbf"
            if bytes(self.data[default_offset : default_offset + 8]) != expected:
                raise ValueError(f"unexpected ARM32 default-range function at 0x{default_value:x}")
            if bytes(self.data[chinese_offset : chinese_offset + 8]) != expected:
                raise ValueError(f"unexpected ARM32 Chinese-range function at 0x{chinese_value:x}")

            default_literal_offset = self.file_offset(default_value + 8)
            chinese_literal_offset = self.file_offset(chinese_value + 8)
            default_literal = struct.unpack_from("<i", self.data, default_literal_offset)[0]
            chinese_literal = struct.unpack_from("<i", self.data, chinese_literal_offset)[0]
            default_range = default_value + 6 + default_literal
            chinese_range = chinese_value + 6 + chinese_literal
            new_literal = chinese_range - (default_value + 6)
            if not -(1 << 31) <= new_literal < (1 << 31):
                raise ValueError("ARM32 range pointer is out of range")
            struct.pack_into("<i", self.data, default_literal_offset, new_literal)

            legacy_literal_address = legacy_value + 0x160
            legacy_literal_offset = self.file_offset(legacy_literal_address)
            legacy_literal = struct.unpack_from("<i", self.data, legacy_literal_offset)[0]
            legacy_pc = (legacy_value + 0x108 + 4) & ~3
            if legacy_pc + legacy_literal != default_range:
                raise ValueError("unexpected ARM32 inlined default glyph-range fallback")
            new_legacy_literal = chinese_range - legacy_pc
            if not -(1 << 31) <= new_legacy_literal < (1 << 31):
                raise ValueError("ARM32 inlined glyph-range pointer is out of range")
            struct.pack_into("<i", self.data, legacy_literal_offset, new_legacy_literal)
            return {
                "architecture": "armeabi-v7a",
                "default_symbol": f"0x{default_value:x}",
                "chinese_symbol": f"0x{chinese_value:x}",
                "chinese_range": f"0x{chinese_range:x}",
                "function_patch": "retargeted exported PC-relative glyph-range literal",
                "legacy_fallback_patch": "retargeted inlined PC-relative glyph-range literal",
            }

        raise ValueError(f"unsupported ELF target: class={self.elf_class}, machine={self.machine}")


def packed_fields(fields: list[str]) -> bytes:
    return b"".join(field.encode("utf-8") + b"\0" for field in fields)


def replace_field_array(blob: bytearray, old: list[str], new: list[str], label: str) -> dict[str, object]:
    if len(old) != len(new):
        raise ValueError(f"field count mismatch: {label}")
    needle = packed_fields(old)
    occurrences = blob.count(needle)
    if occurrences != 1:
        raise ValueError(f"expected exactly one {label} array, found {occurrences}")
    start = blob.find(needle)
    cursor = start
    for source, target in zip(old, new):
        source_bytes = source.encode("utf-8")
        target_bytes = target.encode("utf-8")
        if len(target_bytes) > len(source_bytes):
            raise ValueError(f"replacement too long in {label}: {source!r} -> {target!r}")
        slot_size = len(source_bytes) + 1
        blob[cursor : cursor + slot_size] = target_bytes + b"\0" * (slot_size - len(target_bytes))
        cursor += slot_size
    return {"label": label, "file_offset": f"0x{start:x}", "items": len(old)}


def replace_standalone_string(blob: bytearray, source: str, target: str, label: str) -> dict[str, object]:
    source_bytes = source.encode("utf-8")
    target_bytes = target.encode("utf-8")
    if len(target_bytes) > len(source_bytes):
        raise ValueError(f"replacement too long in {label}: {source!r} -> {target!r}")
    needle = b"\0" + source_bytes + b"\0"
    occurrences = blob.count(needle)
    if occurrences != 1:
        raise ValueError(f"expected exactly one standalone {label}, found {occurrences}")
    start = blob.find(needle) + 1
    slot_size = len(source_bytes) + 1
    blob[start : start + slot_size] = target_bytes + b"\0" * (slot_size - len(target_bytes))
    return {"label": label, "file_offset": f"0x{start:x}", "items": 1}


def patch_one(path: Path) -> dict[str, object]:
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    elf = ElfImage(path)
    glyph_report = elf.patch_glyph_range()

    arrays = [
        (
            ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            ["周日", "周一", "周二", "周三", "周四", "周五", "周六"],
            "weekdays",
        ),
        (
            ["Dark", "Classic", "Light", "PC Cheat Menu", "Pink. mine>-<"],
            ["暗", "经典", "亮", "PC菜单", "粉色"],
            "themes",
        ),
        (
            ["Custom", "Top left", "Top right", "Bottom left", "Bottom right"],
            ["自定", "左上", "右上", "左下", "右下"],
            "overlay positions",
        ),
        (["All", "Male", "Female"], ["全", "男", "女"], "ped filters"),
        (
            ["Default", "Boxing", "Kung Fu", "Kick Boxing", "Punch Kick"],
            ["默认", "拳击", "功夫", "踢拳", "拳脚"],
            "fighting styles",
        ),
        (
            ["All", "Bikes", "Boats", "Cars", "Planes", "Helis", "Trailers", "Trains"],
            ["全", "摩", "船", "车", "飞机", "直", "挂车", "火车"],
            "vehicle categories",
        ),
        (["StatFat", "Type", "gang1", "swat"], ["StatFat", "类", "gang1", "swat"], "type label"),
    ]
    array_reports = [replace_field_array(elf.data, old, new, label) for old, new, label in arrays]
    array_reports.append(replace_standalone_string(elf.data, "World", "区", "world label"))
    array_reports.append(
        replace_standalone_string(elf.data, "Not yet Available", "暂不可用", "not available label")
    )
    path.write_bytes(elf.data)
    patched_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "file": path.name,
        "size": path.stat().st_size,
        "sha256_before": original_hash,
        "sha256_after": patched_hash,
        "glyph_range": glyph_report,
        "hardcoded_arrays": array_reports,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: patch_mod.py PACKAGE_DIR REPORT_JSON", file=sys.stderr)
        return 2
    package_dir = Path(sys.argv[1])
    report_path = Path(sys.argv[2])
    files = [package_dir / "libCheatMenu.so", package_dir / "libCheatMenu64.so"]
    report = {"patched_files": [patch_one(path) for path in files]}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
