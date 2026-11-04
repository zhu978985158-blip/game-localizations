from __future__ import annotations

import csv
import hashlib
import io
import os
import json
import re
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
SOURCE = ROOT / "inputs/Rambo.zip"
FONT_PATH = os.environ.get("RAMBO_CJK_FONT", str(ROOT / "inputs/CJK-font.ttf"))
PATCH = ROOT / "补丁"
RESTORE = ROOT / "恢复原版"
FILES = (
    "data/localisation/translation.csv",
    "data/localisation/subtitles.csv",
    "data/localisation/config.lua",
    "data/localisation/japan/font/font.data",
    "data/localisation/japan/font/font.bmp",
    "data/localisation/japan/font/font.xlor",
    "data/localisation/english/font/font.data",
    "data/localisation/english/font/font.png",
    "loader_data/English.lng",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def serialize(rows: list[list[str]], name: str) -> bytes:
    def cell(value: str) -> str:
        if not value:
            return ""
        if name == "translation.csv" and value == "0":
            return "0"
        return '"' + value.replace('"', '""') + '"'
    return ("\r\n".join(",".join(cell(c) for c in row) for row in rows) + "\r\n").encode("utf-8")


def build_english_font(source: zipfile.ZipFile, required: set[int]) -> None:
    name = "data/localisation/english/font/"
    metadata = source.read(name + "font.data").decode("utf-8").splitlines()
    original_rows = [tuple(map(int, line.split())) for line in metadata[1:]]
    original_codes = {row[0] for row in original_rows}
    assert len(original_rows) == 152 and len(original_codes) == 152
    original_image = Image.open(io.BytesIO(source.read(name + "font.png"))).convert("RGBA")
    assert original_image.size == (1804, 96)
    width, height = 2048, 1024
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    atlas.paste(original_image, (0, 0))
    font = ImageFont.truetype(FONT_PATH, 30)
    draw = ImageDraw.Draw(atlas)
    added = []
    new_codes = sorted(required - original_codes)
    cell_width, cell_height, start_y = 36, 38, 104
    cells_per_row = width // cell_width
    for index, code in enumerate(new_codes):
        char = chr(code)
        bbox = draw.textbbox((0, 0), char, font=font, stroke_width=1)
        left, top, right, bottom = bbox
        glyph_width, glyph_height = right - left, bottom - top
        if glyph_width > cell_width or glyph_height > cell_height:
            raise RuntimeError(f"Glyph exceeds cell: U+{code:04X} ({glyph_width}x{glyph_height})")
        x = (index % cells_per_row) * cell_width
        y = start_y + (index // cells_per_row) * cell_height
        if y + cell_height > height:
            raise RuntimeError("English font atlas needs more space")
        draw.text((x - left, y - top), char, font=font, fill=(255, 255, 255, 255),
                  stroke_width=1, stroke_fill=(255, 255, 255, 255))
        advance = max(glyph_width, round(font.getlength(char))) + 2
        added.append((code, 0, x, y, glyph_width, glyph_height, 0, -glyph_height + 3, advance))
    if any(code > 127 and bytes(font.getmask(chr(code))) == bytes(font.getmask("\uffff")) for code in new_codes):
        raise RuntimeError("Source font contains a missing Chinese glyph")
    rows = sorted(original_rows + added)
    meta = f"v3 {len(rows)} 1 41 10 0 0 1 51\n" + "\n".join(" ".join(map(str, row)) for row in rows) + "\n"
    destination = PATCH / name
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "font.data").write_text(meta, "utf-8")
    atlas.save(destination / "font.png", format="DDS")
    print(json.dumps({"english_font_glyphs": len(rows), "added_glyphs": len(added), "atlas": [width, height]}, ensure_ascii=False))


def build_japan_font() -> None:
    codes = set(range(32, 127))
    for name in ("translation.csv", "subtitles.csv"):
        with (PATCH / "data/localisation" / name).open(encoding="utf-8", newline="") as file:
            table = list(csv.reader(file))
        column = table[0].index("Japan")
        for row in table[1:]:
            codes.update(ord(char) for char in re.sub(r"<[^>]+>", "", row[column]) if 32 <= ord(char) <= 65535)
    codes.update(ord(char) for char in "，。！？：；（）《》“”‘’—…·％＋－×→←↑↓①②③④⑤")
    ordered_codes = sorted(codes)
    regular = ImageFont.truetype(FONT_PATH, 28)
    pages = [Image.new("RGBA", (1024, 988), (0, 0, 0, 0))]
    records = []
    x = y = page = 0
    for code in ordered_codes:
        char = chr(code)
        glyph_width = round(regular.getlength(char))
        cell_width = 16 if code == 32 else max(12, min(38, glyph_width + 7))
        advance = 14 if code == 32 else max(10, glyph_width + 2)
        if x + cell_width > 1024:
            x, y = 0, y + 38
        if y + 38 > 988:
            pages.append(Image.new("RGBA", (1024, 988), (0, 0, 0, 0)))
            page += 1
            x = y = 0
        sample_width = advance
        if code != 32:
            isolated = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
            ImageDraw.Draw(isolated).text((13, 12), char, font=regular, fill=(255, 255, 255, 255),
                                          stroke_width=2, stroke_fill=(15, 15, 15, 255))
            box = tuple(value - 10 for value in isolated.getchannel("A").getbbox())
            sample_width = max(advance, box[2] + 1)
            assert 0 <= box[0] and 0 <= box[1] and box[3] <= 34
            assert sample_width <= cell_width, (char, sample_width, cell_width)
            ImageDraw.Draw(pages[page]).text((x + 3, y + 2), char, font=regular, fill=(255, 255, 255, 255),
                                            stroke_width=2, stroke_fill=(15, 15, 15, 255))
        records.append(f"{code} {x} {y} {sample_width} {page}")
        x += cell_width
    destination = PATCH / "data/localisation/japan/font"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "font.data").write_text(f"34 {len(records)} {len(pages)}\n" + "\n".join(records) + "\n", "utf-8")
    encoded = []
    for atlas in pages:
        stream = io.BytesIO()
        atlas.save(stream, "PNG")
        encoded.append(stream.getvalue())
    assert len(encoded) <= 10
    header = bytes([len(encoded)]) + b"".join(struct.pack("<I", len(blob)) for blob in encoded)
    header += b"\xff" * (40 - 4 * len(encoded))
    (destination / "font.bmp").write_bytes(header + b"".join(encoded))
    order = "".join("<sp/>" if code == 32 else escape(chr(code), {'"': '&quot;'}) for code in ordered_codes)
    xlor = ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<letter-order version="1.1"><head><title>Rambo Simplified Chinese</title></head>'
            '<body><area width="16"/><order>' + order + '</order></body></letter-order>')
    (destination / "font.xlor").write_text(xlor, "utf-16")
    print(json.dumps({"japan_font_glyphs": len(records), "pages": len(pages)}, ensure_ascii=False))


def main() -> None:
    source_hash = json.loads((ROOT / "源文件指纹.json").read_text("utf-8"))["sha256"]
    archive_digest = hashlib.sha256()
    with SOURCE.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            archive_digest.update(block)
    actual_hash = archive_digest.hexdigest()
    assert actual_hash == source_hash, "Original game archive changed"
    ledger_items = [json.loads(line) for line in (ROOT / "逐行校对台账.jsonl").read_text("utf-8").splitlines()]
    ledger = {(item["table"], item["record"]): item for item in ledger_items}
    assert len(ledger_items) == len(ledger) == 1474 and all(item["reviewed"] for item in ledger_items)
    required = set(range(32, 127))
    with zipfile.ZipFile(SOURCE) as source:
        for name in FILES:
            dest = RESTORE / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read(name))
        for name in ("translation.csv", "subtitles.csv"):
            path = "data/localisation/" + name
            old = source.read(path)
            rows = list(csv.reader(io.StringIO(old.decode("utf-8"), newline="")))
            assert serialize(rows, name) == old
            english = rows[0].index("English")
            japanese = rows[0].index("Japan")
            count = 0
            for record, row in enumerate(rows[1:], 2):
                if not row[english].strip():
                    continue
                item = ledger[(name, record)]
                assert item["en"] == row[english] and item["ja"] == row[japanese]
                final = item["v4_zh"]
                row[english] = row[japanese] = final
                required.update(ord(char) for char in re.sub(r"<[^>]+>", "", final) if ord(char) >= 32)
                count += 1
            assert count == (943 if name == "translation.csv" else 514)
            dest = PATCH / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(serialize(rows, name))
        config = source.read("data/localisation/config.lua")
        assert config.count(b"force_change_language = false") == 1
        (PATCH / "data/localisation/config.lua").write_bytes(config.replace(b"force_change_language = false", b"force_change_language = true"))
        launcher = []
        for record, original_line in enumerate(source.read("loader_data/English.lng").decode("utf-8").splitlines(), 1):
            item = ledger[("English.lng", record)]
            assert item["en"] == original_line
            launcher.append(item["v4_zh"])
        assert len(launcher) == 17
        launcher_path = PATCH / "loader_data/English.lng"
        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        launcher_path.write_bytes("\r\n".join(launcher).encode("gbk"))
        build_english_font(source, required)
        build_japan_font()


if __name__ == "__main__":
    main()
