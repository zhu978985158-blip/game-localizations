#!/usr/bin/env python3
"""Translate inline Skyrim ESP strings while preserving record and group structure."""
from pathlib import Path
import argparse
import struct
import zlib

TEXT_FIELDS = {b"FULL", b"DESC", b"RNAM", b"ITXT"}


def load_translations(path: Path):
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        source, sep, target = line.partition("\t")
        if not sep or not source or not target:
            raise ValueError(f"Bad translation line {number}")
        source = source.replace("<NL>", "\n")
        target = target.replace("<NL>", "\n")
        if source in result:
            raise ValueError(f"Duplicate source: {source}")
        result[source] = target
    return result


def translate_record(payload, translations, counts):
    result = bytearray()
    pos = 0
    extended = None
    while pos < len(payload):
        if pos + 6 > len(payload):
            raise ValueError("Incomplete subrecord header")
        tag = payload[pos:pos + 4]
        size = struct.unpack_from("<H", payload, pos + 4)[0]
        pos += 6
        if tag == b"XXXX":
            if size != 4 or pos + 4 > len(payload):
                raise ValueError("Malformed XXXX size extension")
            extended = struct.unpack_from("<I", payload, pos)[0]
            result += tag + struct.pack("<H", size) + payload[pos:pos + 4]
            pos += 4
            continue
        actual_size = extended if extended is not None else size
        if pos + actual_size > len(payload):
            raise ValueError("Subrecord past record boundary")
        original = payload[pos:pos + actual_size]
        pos += actual_size
        replacement = original
        if tag in TEXT_FIELDS:
            try:
                source = original.rstrip(b"\x00").decode("utf-8")
            except UnicodeDecodeError:
                source = None
            lookup = source.replace("\r\n", "\n") if source is not None else None
            if lookup in translations:
                suffix = original[len(original.rstrip(b"\x00")):]
                target = translations[lookup]
                if "\r\n" in source:
                    target = target.replace("\n", "\r\n")
                replacement = target.encode("utf-8") + suffix
                counts[lookup] = counts.get(lookup, 0) + 1
        if extended is not None:
            if len(replacement) != actual_size:
                result[-4:] = struct.pack("<I", len(replacement))
            result += tag + struct.pack("<H", 0) + replacement
            extended = None
        else:
            if len(replacement) > 65535:
                raise ValueError("Translated field exceeds 65535 bytes")
            result += tag + struct.pack("<H", len(replacement)) + replacement
    return bytes(result)


def translate_container(raw, start, end, translations, counts):
    out = bytearray()
    pos = start
    while pos < end:
        if pos + 24 > end:
            raise ValueError("Incomplete record header")
        tag = raw[pos:pos + 4]
        size = struct.unpack_from("<I", raw, pos + 4)[0]
        header = bytearray(raw[pos:pos + 24])
        if tag == b"GRUP":
            if size < 24 or pos + size > end:
                raise ValueError("Invalid GRUP size")
            body = translate_container(raw, pos + 24, pos + size, translations, counts)
            struct.pack_into("<I", header, 4, len(body) + 24)
            out += header + body
            pos += size
        else:
            if pos + 24 + size > end:
                raise ValueError("Invalid record size")
            flags = struct.unpack_from("<I", header, 8)[0]
            original_payload = raw[pos + 24:pos + 24 + size]
            if flags & 0x40000:
                payload = zlib.decompress(original_payload[4:])
                if len(payload) != struct.unpack_from("<I", original_payload, 0)[0]:
                    raise ValueError("Compressed record length mismatch")
            else:
                payload = original_payload
            translated = translate_record(payload, translations, counts)
            if translated == payload:
                result_payload = original_payload
            elif flags & 0x40000:
                result_payload = struct.pack("<I", len(translated)) + zlib.compress(translated)
            else:
                result_payload = translated
            struct.pack_into("<I", header, 4, len(result_payload))
            out += header + result_payload
            pos += 24 + size
    if pos != end:
        raise ValueError("Container length mismatch")
    return bytes(out)


def mark_utf8_for_xedit(raw):
    """Mark non-localized translated strings so xEdit decodes them as UTF-8."""
    if raw[:4] != b"TES4":
        raise ValueError("Plugin does not start with TES4")
    old_size = struct.unpack_from("<I", raw, 4)[0]
    payload = raw[24:24 + old_size]
    pos = 0
    rebuilt = bytearray()
    found = False
    while pos < len(payload):
        if pos + 6 > len(payload):
            raise ValueError("Invalid TES4 subrecord")
        tag = payload[pos:pos + 4]
        length = struct.unpack_from("<H", payload, pos + 4)[0]
        value = payload[pos + 6:pos + 6 + length]
        if len(value) != length:
            raise ValueError("Invalid TES4 subrecord length")
        if tag == b"SNAM":
            found = True
            if b"<cp:utf8>" not in value:
                terminator = b"\x00" if value.endswith(b"\x00") else b""
                value = value.rstrip(b"\x00") + b"\n<cp:utf8>" + terminator
            if len(value) > 65535:
                raise ValueError("TES4 SNAM too long")
        rebuilt += tag + struct.pack("<H", len(value)) + value
        pos += 6 + length
    if not found:
        raise ValueError("TES4 description SNAM missing")
    header = bytearray(raw[:24])
    struct.pack_into("<I", header, 4, len(rebuilt))
    return bytes(header) + rebuilt + raw[24 + old_size:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("translations", type=Path)
    args = parser.parse_args()
    translations = load_translations(args.translations)
    counts = {}
    raw = args.source.read_bytes()
    out = translate_container(raw, 0, len(raw), translations, counts)
    if counts:
        out = mark_utf8_for_xedit(out)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_bytes(out)
    print(f"{args.source.name}: {sum(counts.values())} translated fields, {len(counts)} unique; {len(raw)} -> {len(out)} bytes")


if __name__ == "__main__":
    main()
