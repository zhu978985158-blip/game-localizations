#!/usr/bin/env python3
"""Build a small static TrueType font containing every character used by the mod."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

import patch_mod


HARDCODED_CHINESE = "周日周一周二周三周四周五周六暗经典亮菜单粉色自定左上右下全男女默认拳击功夫踢拳脚摩船车飞机直挂火区类测试列表｜"
IMGUI_COMMON_SYMBOL = "_ZN11ImFontAtlas37GetGlyphRangesChineseSimplifiedCommonEv"


def imgui_common_chinese(package_dir: Path) -> set[int]:
    """Extract ImGui's own 2,500-character Simplified Chinese common set."""
    image = patch_mod.ElfImage(package_dir / "libCheatMenu64.so")
    function = image.symbols[IMGUI_COMMON_SYMBOL][0]
    instruction_address = function + 0x2C
    instruction_offset = image.file_offset(instruction_address)
    instruction = struct.unpack_from("<I", image.data, instruction_offset)[0]
    if instruction & 0x9F00001F != 0x1000000B:  # ADR x11, ...
        raise ValueError("unexpected ImGui Chinese-common offset instruction")
    immlo = (instruction >> 29) & 0x3
    immhi = (instruction >> 5) & 0x7FFFF
    immediate = (immhi << 2) | immlo
    if immediate & (1 << 20):
        immediate -= 1 << 21
    offsets_address = instruction_address + immediate
    offsets_file = image.file_offset(offsets_address)

    codepoint = 0x4E00
    result: set[int] = set()
    for index in range(2500):
        codepoint += struct.unpack_from("<H", image.data, offsets_file + index * 2)[0]
        result.add(codepoint)
    if len(result) != 2500 or min(result) != 0x4E00 or max(result) > 0x9FFF:
        raise ValueError("invalid ImGui Chinese-common character table")
    return result


def collect_characters(package_dir: Path) -> set[int]:
    codepoints = set(range(0x20, 0x7F))
    codepoints.update(range(0xA0, 0x100))
    codepoints.update(ord(ch) for ch in HARDCODED_CHINESE)
    codepoints.update(imgui_common_chinese(package_dir))
    for path in package_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".toml", ".dat", ".ini", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        codepoints.update(ord(ch) for ch in text if ch not in "\r\n\t")
    return codepoints


def set_font_names(font: TTFont) -> None:
    replacements = {
        1: "ARM CJK UI Subset",
        2: "Regular",
        4: "ARM CJK UI Subset Regular",
        6: "ARMCJKUISubset-Regular",
        16: "ARM CJK UI Subset",
        17: "Regular",
    }
    if "name" not in font:
        return
    for record in font["name"].names:
        if record.nameID not in replacements:
            continue
        value = replacements[record.nameID]
        try:
            record.string = value.encode(record.getEncoding())
        except (LookupError, UnicodeEncodeError):
            record.string = value.encode("utf-16-be")


def cmap_codepoints(font: TTFont) -> set[int]:
    points: set[int] = set()
    for table in font["cmap"].tables:
        points.update(table.cmap)
    return points


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: build_font.py SOURCE_VARIABLE_TTF PACKAGE_DIR OUTPUT_TTF REPORT_JSON", file=sys.stderr)
        return 2

    source_font = Path(sys.argv[1])
    package_dir = Path(sys.argv[2])
    output_font = Path(sys.argv[3])
    report_path = Path(sys.argv[4])
    required = collect_characters(package_dir)

    font = TTFont(source_font, recalcTimestamp=False)
    if "fvar" in font:
        instantiateVariableFont(font, {"wght": 400}, inplace=True, optimize=True)

    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    options.name_languages = ["*"]
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recalc_average_width = True
    options.recalc_max_context = True
    options.retain_gids = False
    options.drop_tables = []

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=required)
    subsetter.subset(font)
    set_font_names(font)
    output_font.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_font, reorderTables=True)

    check = TTFont(output_font, lazy=False)
    covered = cmap_codepoints(check)
    missing = sorted(required - covered)
    report = {
        "source_font": source_font.name,
        "output_font": output_font.name,
        "source_size": source_font.stat().st_size,
        "output_size": output_font.stat().st_size,
        "required_codepoints": len(required),
        "covered_codepoints": len(required & covered),
        "missing_codepoints": [f"U+{value:04X}" for value in missing],
        "has_glyf": "glyf" in check,
        "has_cff": "CFF " in check or "CFF2" in check,
        "is_variable": "fvar" in check,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing or "glyf" not in check or "fvar" in check:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
