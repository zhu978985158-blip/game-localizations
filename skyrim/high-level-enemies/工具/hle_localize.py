#!/usr/bin/env python3
"""Audit and localize the supplied HLE plugins without changing gameplay data."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re
import struct
import sys
import zipfile
import zlib

WORK = Path(__file__).resolve().parents[1]
PROJECT = WORK
ORIGINAL = PROJECT / '01_原文件'
DATA = WORK / '数据'
TEXT_FIELDS = {b'FULL', b'DESC'}
EXPECTED_FIELDS = 814
EXPECTED_UNIQUE = 326
ARCHIVES = {
    'normal': 'High Level Enemies-3231-1-71.zip',
    'scaled': 'High Level Enemies - Scaled-3231-1-71.zip',
    'caps': 'High Level Enemies - Raised Ability Caps-3231-1-4.zip',
    'resists': 'HLE - Increased Max Resists-3231-1-2-1576945821.zip',
}


def is_text_field(record_type, tag):
    return (tag in TEXT_FIELDS or
            record_type == b'MGEF' and tag == b'DNAM' or
            record_type == b'NPC_' and tag == b'SHRT')


def parse_fields(body):
    fields, pos, extended = [], 0, None
    while pos < len(body):
        assert pos + 6 <= len(body), 'Truncated subrecord header'
        tag = body[pos:pos + 4]
        size = struct.unpack_from('<H', body, pos + 4)[0]
        pos += 6
        if tag == b'XXXX':
            assert size == 4 and pos + 4 <= len(body) and extended is None
            extended = struct.unpack_from('<I', body, pos)[0]
            pos += 4
            continue
        actual = extended if extended is not None else size
        assert pos + actual <= len(body), 'Subrecord outside record'
        fields.append((tag, body[pos:pos + actual], extended is not None))
        extended = None
        pos += actual
    assert pos == len(body) and extended is None
    return fields


def pack_fields(fields):
    out = bytearray()
    for tag, value, extended in fields:
        if extended or len(value) > 65535:
            out += b'XXXX' + struct.pack('<HI', 4, len(value))
            out += tag + struct.pack('<H', 0) + value
        else:
            out += tag + struct.pack('<H', len(value)) + value
    return bytes(out)


def nodes(raw, start=0, end=None):
    end = len(raw) if end is None else end
    out, pos = [], start
    while pos < end:
        assert pos + 24 <= end, 'Truncated record header'
        header = raw[pos:pos + 24]
        tag = header[:4]
        size = struct.unpack_from('<I', header, 4)[0]
        if tag == b'GRUP':
            assert size >= 24 and pos + size <= end
            out.append({'header': header, 'children': nodes(raw, pos + 24, pos + size)})
            pos += size
        else:
            assert pos + 24 + size <= end
            payload = raw[pos + 24:pos + 24 + size]
            body = payload
            if struct.unpack_from('<I', header, 8)[0] & 0x40000:
                assert len(payload) >= 4
                body = zlib.decompress(payload[4:])
                assert len(body) == struct.unpack_from('<I', payload)[0]
            out.append({'header': header, 'payload': payload, 'body': body,
                        'fields': parse_fields(body)})
            pos += 24 + size
    assert pos == end
    return out


def flat(tree):
    for node in tree:
        if 'children' in node:
            yield from flat(node['children'])
        else:
            yield node


def string(value):
    return value.rstrip(b'\0').decode('utf-8')


def load_translations():
    result = {}
    with (DATA / '译文对照.tsv').open(encoding='utf-8', newline='') as f:
        for source, target in csv.reader(f, delimiter='\t'):
            assert source and target and source not in result
            assert '\ufffd' not in target and re.search('[\u4e00-\u9fff]', target)
            assert re.findall(r'\d+(?:\.\d+)?%?', source) == re.findall(r'\d+(?:\.\d+)?%?', target), source
            assert re.findall(r'<[^>]+>', source) == re.findall(r'<[^>]+>', target), source
            result[source] = target
    return result


def extract():
    rows, inventory = [], []
    for kind, archive in ARCHIVES.items():
        with zipfile.ZipFile(ORIGINAL / archive) as z:
            assert z.testzip() is None
            for info in z.infolist():
                if info.is_dir():
                    continue
                inventory.append({'kind': kind, 'archive': archive, 'path': info.filename,
                                  'size': info.file_size, 'crc32': f'{info.CRC:08x}'})
                if not info.filename.lower().endswith('.esp'):
                    continue
                tree = nodes(z.read(info))
                assert tree[0]['header'][:4] == b'TES4'
                assert not struct.unpack_from('<I', tree[0]['header'], 8)[0] & 0x80
                for record in flat(tree):
                    typ = record['header'][:4].decode('ascii')
                    fid = f"{struct.unpack_from('<I', record['header'], 12)[0]:08X}"
                    edid = next((string(v) for k, v, _ in record['fields'] if k == b'EDID'), '')
                    for tag, value, _ in record['fields']:
                        if is_text_field(record['header'][:4], tag) and value.rstrip(b'\0'):
                            rows.append([kind, info.filename, typ, fid, edid,
                                         tag.decode('ascii'), string(value)])
    with (DATA / '原文位置.tsv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(['package', 'plugin', 'record', 'formid', 'edid', 'field', 'source'])
        writer.writerows(rows)
    sources = sorted({r[-1] for r in rows})
    (DATA / '不重复原文.txt').write_text('\n'.join(sources) + '\n', encoding='utf-8')
    (DATA / '压缩包内容清单.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert len(rows) == EXPECTED_FIELDS and len(sources) == EXPECTED_UNIQUE
    print('Text fields:', len(rows), 'Unique sources:', len(sources), 'Files:', len(inventory))
    return rows


def translate_tree(tree, translations, counts):
    out = bytearray()
    for node in tree:
        header = bytearray(node['header'])
        if 'children' in node:
            body = translate_tree(node['children'], translations, counts)
            struct.pack_into('<I', header, 4, len(body) + 24)
            out += header + body
            continue
        fields = list(node['fields'])
        for i, (tag, value, extended) in enumerate(fields):
            if is_text_field(header[:4], tag) and value.rstrip(b'\0'):
                source = string(value)
                suffix = value[len(value.rstrip(b'\0')):]
                fields[i] = (tag, translations[source].encode('utf-8') + suffix, extended)
                counts[source] += 1
        if header[:4] == b'TES4':
            indexes = [i for i, (tag, _, _) in enumerate(fields) if tag == b'SNAM']
            if indexes:
                i = indexes[0]
                tag, value, extended = fields[i]
                suffix = b'\0' if value.endswith(b'\0') else b''
                fields[i] = (tag, value.rstrip(b'\0') + b'\n<cp:utf8>' + suffix, extended)
            else:
                i = next((i + 1 for i, (tag, _, _) in enumerate(fields) if tag == b'CNAM'), 1)
                fields.insert(i, (b'SNAM', b'<cp:utf8>\0', False))
        body = pack_fields(fields)
        if body == node['body']:
            payload = node['payload']
        elif struct.unpack_from('<I', header, 8)[0] & 0x40000:
            payload = struct.pack('<I', len(body)) + zlib.compress(body)
        else:
            payload = body
        struct.pack_into('<I', header, 4, len(payload))
        out += header + payload
    return bytes(out)


def verify_trees(original, translated, translations, stats):
    assert len(original) == len(translated)
    for a, b in zip(original, translated):
        assert a['header'][:4] + a['header'][8:] == b['header'][:4] + b['header'][8:], 'Record/group identity changed'
        if 'children' in a:
            assert 'children' in b
            verify_trees(a['children'], b['children'], translations, stats)
            continue
        stats['records'] += 1
        af, bf = list(a['fields']), list(b['fields'])
        if a['header'][:4] == b'TES4':
            s0 = [(i, v) for i, (t, v, _) in enumerate(af) if t == b'SNAM']
            s1 = [(i, v) for i, (t, v, _) in enumerate(bf) if t == b'SNAM']
            assert len(s1) == 1 and b'<cp:utf8>' in s1[0][1]
            if not s0:
                assert s1[0][1] == b'<cp:utf8>\0'
                bf.pop(s1[0][0])
            else:
                i, v = s0[0]
                assert s1[0][0] == i
                suffix = b'\0' if v.endswith(b'\0') else b''
                assert s1[0][1] == v.rstrip(b'\0') + b'\n<cp:utf8>' + suffix
                bf[i] = af[i]
            stats['utf8_markers'] += 1
        assert len(af) == len(bf), 'Subrecord count changed'
        for (ta, va, ea), (tb, vb, eb) in zip(af, bf):
            assert ta == tb and ea == eb
            if is_text_field(a['header'][:4], ta) and va.rstrip(b'\0'):
                source = string(va)
                suffix = va[len(va.rstrip(b'\0')):]
                assert vb == translations[source].encode('utf-8') + suffix
                stats['translated_fields'] += 1
            else:
                assert va == vb, (a['header'][:4], ta, 'Non-text data changed')


def translated_plugins():
    translations = load_translations()
    rows = extract()
    assert set(translations) == {r[-1] for r in rows}, 'Translation coverage mismatch'
    counts = collections.Counter()
    stats, outputs = {}, {}
    for kind, archive in ARCHIVES.items():
        with zipfile.ZipFile(ORIGINAL / archive) as z:
            for name in z.namelist():
                if not name.endswith('.esp'):
                    continue
                raw = z.read(name)
                source = nodes(raw)
                output = raw if kind == 'resists' else translate_tree(source, translations, counts)
                if kind == 'resists':
                    assert output == raw
                    stats[kind + '/' + name] = {'unchanged_numeric_only_plugin': True}
                else:
                    plugin_stats = collections.Counter()
                    verify_trees(source, nodes(output), translations, plugin_stats)
                    stats[kind + '/' + name] = dict(plugin_stats)
                outputs[(kind, name)] = output
    assert sum(counts.values()) == EXPECTED_FIELDS and len(counts) == EXPECTED_UNIQUE
    return outputs, stats


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'extract':
        extract()
    else:
        outputs, stats = translated_plugins()
        for (kind, name), payload in outputs.items():
            path = PROJECT / '02_汉化版' / '汉化插件' / kind / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        (WORK / '检查').mkdir(parents=True, exist_ok=True)
        (WORK / '检查' / '插件检查.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(stats, ensure_ascii=False, indent=2))
