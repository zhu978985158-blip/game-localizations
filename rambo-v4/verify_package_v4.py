from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from build_v4 import FILES, PATCH, RESTORE, ROOT, SOURCE, sha


TAG = re.compile(r"<[^>]+>")
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-+0-9.#]*[sdfxX]|\{[^{}]+\}|\\[nr]")


def rows(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8"), newline="")))


def main() -> None:
    errors: list[str] = []
    report: dict = {"scope": "静态文件检查；尚未经过 Windows 游戏画面验收", "errors": errors, "tables": {}, "font": {}, "restore": {}, "delivery": {}}
    items = [json.loads(line) for line in (ROOT / "逐行校对台账.jsonl").read_text("utf-8").splitlines()]
    ledger = {(item["table"], item["record"]): item for item in items}
    assert len(items) == len(ledger) == 1474 and all(item["reviewed"] for item in items)
    required: set[int] = set()
    with zipfile.ZipFile(SOURCE) as original:
        for name in FILES:
            old = original.read(name)
            new = (RESTORE / name).read_bytes()
            if old != new:
                errors.append("Restore differs from source: " + name)
            report["restore"][name] = {"source_sha256": sha(old), "restored_sha256": sha(new), "patch_sha256": sha((PATCH / name).read_bytes())}
        for name in ("translation.csv", "subtitles.csv"):
            path = "data/localisation/" + name
            source_rows = rows(original.read(path))
            patched_rows = rows((PATCH / path).read_bytes())
            if len(source_rows) != len(patched_rows) or source_rows[0] != patched_rows[0]:
                errors.append(name + ": row count/header changed")
                continue
            english = source_rows[0].index("English")
            japanese = source_rows[0].index("Japan")
            count = 0
            no_key = 0
            for record, (before, after) in enumerate(zip(source_rows[1:], patched_rows[1:]), 2):
                if len(before) != len(after):
                    errors.append(f"{name}:{record} column count changed")
                    continue
                if any(a != b for index, (a, b) in enumerate(zip(before, after)) if index not in (english, japanese)):
                    errors.append(f"{name}:{record} metadata/timing changed")
                if not before[english].strip():
                    if before != after:
                        errors.append(f"{name}:{record} non-candidate row changed")
                    continue
                item = ledger.get((name, record))
                if item is None or item["en"] != before[english] or item["ja"] != before[japanese]:
                    errors.append(f"{name}:{record} ledger/source mismatch")
                    continue
                expected = item["v4_zh"]
                if after[english] != expected or after[japanese] != expected or not expected.strip():
                    errors.append(f"{name}:{record} missing/wrong translation")
                if TAG.findall(before[english]) != TAG.findall(expected):
                    errors.append(f"{name}:{record} tag mismatch")
                if PLACEHOLDER.findall(TAG.sub(" ", before[english])) != PLACEHOLDER.findall(TAG.sub(" ", expected)):
                    errors.append(f"{name}:{record} placeholder mismatch")
                required.update(ord(char) for char in TAG.sub("", expected) if ord(char) >= 32)
                count += 1
                if name == "subtitles.csv" and not before[0].strip():
                    no_key += 1
            report["tables"][name] = {"source_records": len(source_rows) - 1, "patch_records": len(patched_rows) - 1, "translated_rows": count, "no_key_continuation_rows": no_key}
            if count != (943 if name == "translation.csv" else 514):
                errors.append(name + " translation count incorrect")
            if name == "subtitles.csv" and no_key != 289:
                errors.append("Subtitle continuation count incorrect")

        font_base = "data/localisation/english/font/"
        source_font_lines = original.read(font_base + "font.data").decode("utf-8").splitlines()
        patch_font_lines = (PATCH / font_base / "font.data").read_text("utf-8").splitlines()
        original_metrics = [tuple(map(int, line.split())) for line in source_font_lines[1:]]
        patch_metrics = [tuple(map(int, line.split())) for line in patch_font_lines[1:]]
        font_header = patch_font_lines[0].split()
        if font_header[0] != "v3" or int(font_header[1]) != len(patch_metrics) or len(patch_metrics) != len({row[0] for row in patch_metrics}):
            errors.append("English font header, glyph count or uniqueness invalid")
        if {row[0]: row for row in original_metrics}.items() - {row[0]: row for row in patch_metrics}.items():
            errors.append("Original English font metrics changed")
        font_codes = {row[0] for row in patch_metrics}
        missing = sorted(required - font_codes)
        if missing:
            errors.append("English font missing codepoints: " + repr(missing[:20]))
        font_texture = Image.open(PATCH / font_base / "font.png").convert("RGBA")
        source_texture = Image.open(io.BytesIO(original.read(font_base + "font.png"))).convert("RGBA")
        if font_texture.size != (2048, 1024) or font_texture.crop((0, 0, 1804, 96)).tobytes() != source_texture.tobytes():
            errors.append("English font DDS invalid or original glyph pixels changed")
        invalid_bounds = [row[0] for row in patch_metrics if not (0 <= row[2] and 0 <= row[3] and row[2] + row[4] <= 2048 and row[3] + row[5] <= 1024 and row[4] >= 0 and row[5] >= 0)]
        if invalid_bounds:
            errors.append("English font glyph bounds invalid: " + repr(invalid_bounds[:20]))
        empty_added = [row[0] for row in patch_metrics if row[0] not in {r[0] for r in original_metrics} and not font_texture.crop((row[2], row[3], row[2] + row[4], row[3] + row[5])).getbbox()]
        if empty_added:
            errors.append("English font added blank glyphs: " + repr(empty_added[:20]))
        report["font"] = {"english_glyphs": len(patch_metrics), "original_glyphs_preserved": len(original_metrics), "required_codepoints": len(required), "missing_codepoints": missing, "blank_added_glyphs": empty_added, "out_of_bounds": invalid_bounds, "texture_size": font_texture.size, "format": "DDS"}
        # Inspect actual atlas pixels, not only the metadata values.
        english_sampler = Image.new("L", font_texture.size, 0)
        sampler_draw = ImageDraw.Draw(english_sampler)
        sampler_draw.rectangle((0, 0, 1803, 95), fill=255)
        for code, page, x, y, width, height, offset_x, offset_y, advance in patch_metrics:
            if width and height:
                sampler_draw.rectangle((x, y, x + width - 1, y + height - 1), fill=255)
        english_uncovered = ImageChops.subtract(font_texture.getchannel("A"), english_sampler).getbbox()
        if english_uncovered:
            errors.append("English atlas has ink outside sampler rectangles")
        report["font"]["ink_outside_samplers"] = english_uncovered

    japan_base = PATCH / "data/localisation/japan/font"
    japan_lines = (japan_base / "font.data").read_text("utf-8").splitlines()
    line_height, japan_count, page_count = map(int, japan_lines[0].split())
    japan_rows = [tuple(map(int, line.split())) for line in japan_lines[1:]]
    japan_codes = [row[0] for row in japan_rows]
    if japan_count != len(japan_rows) or japan_codes != sorted(set(japan_codes)):
        errors.append("Japan glyph count/order invalid")
    japan_missing = sorted(required - set(japan_codes))
    if japan_missing:
        errors.append("Japan font missing codepoints")
    blob = (japan_base / "font.bmp").read_bytes()
    if blob[0] != page_count or not 1 <= page_count <= 10:
        errors.append("Japan font container page count invalid")
    page_lengths = struct.unpack_from("<" + "I" * page_count, blob, 1)
    if len(blob) != 41 + sum(page_lengths) or blob[1 + page_count * 4:41] != b"\xff" * (40 - page_count * 4):
        errors.append("Japan font container lengths/padding invalid")
    pages = []
    offset = 41
    for length in page_lengths:
        atlas = Image.open(io.BytesIO(blob[offset:offset + length])).convert("RGBA")
        atlas.load()
        pages.append(atlas)
        offset += length
    masks = [Image.new("L", atlas.size, 0) for atlas in pages]
    overlapping = []
    empty_japan = []
    for code, x, y, width, page in japan_rows:
        if not (0 <= page < page_count and width > 0 and 0 <= x and 0 <= y and x + width <= pages[page].width and y + line_height <= pages[page].height):
            errors.append(f"Japan font glyph U+{code:04X} exceeds atlas")
            continue
        rectangle = (x, y, x + width, y + line_height)
        if masks[page].crop(rectangle).getbbox():
            overlapping.append(code)
        ImageDraw.Draw(masks[page]).rectangle((x, y, x + width - 1, y + line_height - 1), fill=255)
        if code != 32 and not pages[page].crop(rectangle).getchannel("A").getbbox():
            empty_japan.append(code)
    uncovered = [ImageChops.subtract(atlas.getchannel("A"), mask).getbbox() for atlas, mask in zip(pages, masks)]
    if overlapping or empty_japan or any(uncovered):
        errors.append("Japan font has overlapping samplers, empty glyphs or ink outside declared samplers")
    order = ET.fromstring((japan_base / "font.xlor").read_bytes()).find("./body/order")
    xlor_codes = []
    if order is not None:
        xlor_codes.extend(map(ord, order.text or ""))
        for child in order:
            if child.tag == "sp":
                xlor_codes.append(32)
            xlor_codes.extend(map(ord, child.text or ""))
            xlor_codes.extend(map(ord, child.tail or ""))
    if xlor_codes != japan_codes:
        errors.append("Japan font XML glyph order differs from metadata")
    report["japan_font"] = {"glyphs": japan_count, "line_height": line_height, "pages": page_count, "missing_codepoints": japan_missing,
                            "overlapping_samplers": overlapping, "empty_glyphs": empty_japan, "ink_outside_samplers": uncovered,
                            "atlas_sizes": [atlas.size for atlas in pages], "xml_order_matches": xlor_codes == japan_codes}

    launcher = (PATCH / "loader_data/English.lng").read_bytes()
    launcher_lines = launcher.decode("gbk").splitlines()
    if len(launcher_lines) != 17:
        errors.append("Launcher encoding/line count incorrect")
    for record, line in enumerate(launcher_lines, 1):
        if line != ledger[("English.lng", record)]["v4_zh"]:
            errors.append(f"Launcher line {record} differs from ledger")
    report["launcher"] = {"lines": len(launcher_lines), "encoding": "GBK"}
    if errors:
        (ROOT / "校验报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
        raise RuntimeError("\n".join(errors[:30]))

    delivery = ROOT / "Rambo_汉化补丁_v4"
    if delivery.exists():
        shutil.rmtree(delivery)
    shutil.copytree(PATCH, delivery / "覆盖文件")
    shutil.copytree(RESTORE, delivery / "恢复原版")
    (delivery / "安装说明.txt").write_text(
        "Rambo 汉化补丁 v4\r\n\r\n"
        "安装：把“覆盖文件”里的 data 和 loader_data 文件夹复制到游戏目录（Rambo.exe 所在文件夹），合并文件夹并替换同名文件。\r\n\r\n"
        "恢复原版：把“恢复原版”里的 data 和 loader_data 文件夹复制到同一位置，合并文件夹并替换同名文件。\r\n",
        "utf-8",
    )
    package_path = ROOT / "Rambo_汉化补丁_v4.zip"
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(delivery.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(ROOT))
    with zipfile.ZipFile(package_path) as package:
        bad = package.testzip()
        if bad:
            raise RuntimeError("ZIP CRC failed: " + bad)
        report["delivery"] = {"zip": str(package_path), "sha256": sha(package_path.read_bytes()), "files": len(package.namelist()), "zip_crc": "passed"}
    (ROOT / "校验报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({"tables": report["tables"], "font": report["font"], "delivery": report["delivery"], "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
