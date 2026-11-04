"""Lossless XOM language reader and append-only string-table writer."""
from pathlib import Path
import struct, json, hashlib

def read_varint(data, pos):
    value = shift = 0
    while True:
        byte = data[pos]; pos += 1
        value |= (byte & 127) << shift
        if byte < 128: return value, pos
        shift += 7
        if shift > 35: raise ValueError('Invalid variable integer')

def varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128); value >>= 7
    out.append(value)
    return bytes(out)

class Language:
    def __init__(self, data):
        self.data = data
        assert data[:4] == b'MOIK'
        self.section = data.index(b'STRS')
        n, size = struct.unpack_from('<II', data, self.section + 4)
        self.offsets = list(struct.unpack_from('<' + 'I' * n, data, self.section + 12))
        start = self.section + 12 + n * 4
        self.pool = data[start:start + size]
        self.strings = []
        for offset in self.offsets:
            assert offset < size
            self.strings.append(self.pool[offset:self.pool.index(b'\0', offset)].decode('utf-8'))
        count = struct.unpack_from('<I', data, 136)[0]
        pos = start + size; self.records = []
        for _ in range(count):
            assert data[pos:pos + 7] == b'CTNR\0\0\0'
            value, end = read_varint(data, pos + 7)
            key, end = read_varint(data, end)
            assert value < n and key < n and data[end:end + 4] == b'\0' * 4
            self.records.append((value, key))
            pos = end + 4
        self.tail = data[pos:]

    def items(self):
        return [(self.strings[k], self.strings[v]) for v, k in self.records]

    def build(self, translations):
        known = {k for k, v in self.items()}
        assert not (translations.keys() - known), translations.keys() - known
        offsets = self.offsets.copy(); pool = bytearray(self.pool)
        appended = {}; records = []
        for v, k in self.records:
            key = self.strings[k]
            if key in translations and translations[key] != self.strings[v]:
                text = translations[key]
                assert text and '\0' not in text
                if text not in appended:
                    appended[text] = len(offsets)
                    offsets.append(len(pool)); pool.extend(text.encode('utf-8') + b'\0')
                v = appended[text]
            records.append(b'CTNR\0\0\0' + varint(v) + varint(k) + b'\0' * 4)
        return (self.data[:self.section] + b'STRS' + struct.pack('<II', len(offsets), len(pool))
                + struct.pack('<' + 'I' * len(offsets), *offsets) + pool + b''.join(records) + self.tail)

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    source = root/'原始解包/Worms Ultimate Mayhem/Game/Data/Language/PC'
    output = root/'开发测试补丁/Game/Data/Language/PC'
    output.mkdir(parents=True, exist_ok=True)
    translations = json.loads((root/'译文/主语言表.json').read_text())
    results = []
    for name in ['English', 'EngFE', 'EngLoading', 'EngLS']:
        original = (source/(name + '.xom')).read_bytes()
        lang = Language(original)
        assert lang.build({}) == original, 'No-op changed original'
        entries = translations.get(name + '.xom', {})
        built = lang.build(entries); parsed = Language(built)
        expected = [(k, entries.get(k, v)) for k, v in lang.items()]
        assert parsed.items() == expected
        assert parsed.tail == lang.tail
        assert [k for k, v in parsed.items()] == [k for k, v in lang.items()]
        if entries: (output/(name + '.xom')).write_bytes(built)
        results.append({'file':name+'.xom','records':len(lang.records),'translated_records':len(entries),
                        'no_op_identical':True,'reparse_equal':True,'tail_identical':True,
                        'original_sha256':hashlib.sha256(original).hexdigest(),
                        'output_sha256':hashlib.sha256(built).hexdigest()})
    (root/'验证/语言资源回写.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False,indent=2))
