#!/usr/bin/env python3
from pathlib import Path
import collections
import struct
import zlib
from lxml import etree
from translate_pex import bsa_files

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "原版解包"
CHINESE = ROOT / "EBO-3X_简体中文_MO2"
TEXT_FIELDS = {b"FULL", b"DESC", b"RNAM", b"ITXT"}


def records(data):
    out = []
    pos = 0
    while pos < len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        if tag == b"GRUP":
            assert size >= 24 and pos + size <= len(data)
            pos += 24
            continue
        assert pos + 24 + size <= len(data)
        header = data[pos:pos + 24]
        flags = struct.unpack_from("<I", header, 8)[0]
        body = data[pos + 24:pos + 24 + size]
        if flags & 0x40000:
            expected = struct.unpack_from("<I", body, 0)[0]
            body = zlib.decompress(body[4:])
            assert len(body) == expected
        out.append((header[:4] + header[8:], fields(body)))
        pos += 24 + size
    assert pos == len(data)
    return out


def fields(body):
    out = []
    pos = 0
    extended = None
    while pos < len(body):
        tag = body[pos:pos + 4]
        size = struct.unpack_from("<H", body, pos + 4)[0]
        pos += 6
        if tag == b"XXXX":
            extended = struct.unpack_from("<I", body, pos)[0]
            pos += 4
            continue
        if extended is not None:
            size = extended
            extended = None
        assert pos + size <= len(body)
        value = body[pos:pos + size]
        pos += size
        out.append((tag, value))
    assert pos == len(body)
    return out


def verify_esp():
    differences = 0
    markers = 0
    for source in ORIGINAL.rglob("*.esp"):
        translated = CHINESE / source.relative_to(ORIGINAL)
        a = records(source.read_bytes())
        b = records(translated.read_bytes())
        assert len(a) == len(b), source
        for (header_a, fields_a), (header_b, fields_b) in zip(a, b):
            assert header_a == header_b, source
            assert len(fields_a) == len(fields_b), source
            for (tag_a, value_a), (tag_b, value_b) in zip(fields_a, fields_b):
                assert tag_a == tag_b, source
                if value_a != value_b:
                    if header_a[:4] == b"TES4" and tag_a == b"SNAM":
                        terminator = b"\0" if value_a.endswith(b"\0") else b""
                        assert value_b == value_a.rstrip(b"\0") + b"\n<cp:utf8>" + terminator, source
                        markers += 1
                    else:
                        assert tag_a in TEXT_FIELDS, (source, tag_a)
                        assert value_a.endswith(b"\0") == value_b.endswith(b"\0"), source
                        value_b.rstrip(b"\0").decode("utf-8")
                        differences += 1
    print("ESP", len(list(ORIGINAL.rglob("*.esp"))), "files; text fields changed", differences, "xEdit UTF-8 markers", markers)


def verify_fomod():
    original = etree.parse(str(ORIGINAL / "FOMOD" / "ModuleConfig.xml"))
    chinese = etree.parse(str(CHINESE / "FOMOD" / "ModuleConfig.xml"))
    src_paths = []
    dst_paths = []
    for tree, paths in [(original, src_paths), (chinese, dst_paths)]:
        for element in tree.iter():
            if element.tag in ("file", "folder") and element.get("source"):
                paths.append((element.tag, element.get("source"), element.get("destination")))
    assert len(dst_paths) == len(src_paths) + 1
    assert set(src_paths).issubset(set(dst_paths))
    for _, source, _ in dst_paths:
        assert (CHINESE / source.replace("\\", "/")).exists(), source
    assert any(source.endswith("\\Scripts") and "ESP+BSA" in source for _, source, _ in dst_paths)
    assert etree.parse(str(CHINESE / "FOMOD" / "info.xml"))
    print("FOMOD", len(dst_paths), "source paths valid")


def verify_assets():
    all_files = [p.relative_to(ORIGINAL) for p in ORIGINAL.rglob("*") if p.is_file()]
    for rel in all_files:
        assert (CHINESE / rel).is_file(), rel
    bsa = [rel for rel in all_files if rel.suffix.lower() == ".bsa"]
    for rel in bsa:
        assert (ORIGINAL / rel).read_bytes() == (CHINESE / rel).read_bytes(), rel
    print("Original files preserved", len(all_files), "; BSA unchanged", len(bsa))


def pex_parts(data):
    assert data[:4] == b"\xfa\x57\xc0\xde"
    pos = 16
    for _ in range(3):
        size = struct.unpack_from(">H", data, pos)[0]
        pos += 2 + size
    count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    strings = []
    for _ in range(count):
        size = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        strings.append(data[pos:pos + size].decode("utf-8"))
        pos += size
    return strings, data[pos:]


def verify_pex():
    changed = 0
    for bsa in ORIGINAL.rglob("*.bsa"):
        if bsa.name not in {"Eli_Breezehome.bsa", "Eli_Breezehome [ADDON - Auto Systems].bsa"}:
            continue
        for _, name, original in bsa_files(bsa):
            target = CHINESE / bsa.relative_to(ORIGINAL).parent / "Scripts" / name
            if not target.exists():
                continue
            strings_a, tail_a = pex_parts(original)
            strings_b, tail_b = pex_parts(target.read_bytes())
            assert len(strings_a) == len(strings_b), name
            assert tail_a == tail_b, name
            changed += sum(a != b for a, b in zip(strings_a, strings_b))
            if name == "ebo_autosort_sortingquestscript.pex":
                assert "heart" in strings_a and "心" in strings_b
    assert changed == 15, changed
    print("PEX string entries changed", changed, "with bytecode unchanged")


if __name__ == "__main__":
    verify_esp()
    verify_fomod()
    verify_assets()
    verify_pex()
