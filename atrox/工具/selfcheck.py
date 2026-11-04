"""Synthetic checks only; never reads a game installation or font."""
from pathlib import Path
import json
import struct
from build import BASE, BLOCK, Pak, replace_fixed, swap_bits, MAIN, HELP, DESCS, MAP_NAMES


def rejected(call):
    try:
        call()
    except AssertionError:
        return
    raise AssertionError("Invalid input was accepted")


payload = bytes(range(256)) * 9
data = bytearray(BASE + 3 * BLOCK)
struct.pack_into("<I", data, 512 + 4, 2)
data[BASE] = 1
data[BASE + 1:BASE + 10] = b"hello.bin"
struct.pack_into("<IIII", data, BASE + 112, 1, len(payload), 0, 258)
data[BASE + BLOCK:BASE + BLOCK + len(payload)] = payload
pak = Pak(data)
assert pak.read("/hello.bin") == payload
assert bytes(pak.data) == bytes(data)
rejected(lambda: pak.write_same_size("/hello.bin", b"short"))
changed = bytes(x ^ 255 for x in payload)
pak.write_same_size("/hello.bin", changed)
assert pak.read("/hello.bin") == changed
assert pak.data[:BASE + BLOCK] == data[:BASE + BLOCK]
assert pak.data[BASE + BLOCK + len(payload):] == data[BASE + BLOCK + len(payload):]
assert Pak(pak.data).entries == pak.entries

cyclic = bytearray(data)
struct.pack_into("<I", cyclic, 512 + 4, 1)
rejected(lambda: Pak(cyclic).read("/hello.bin"))
outside = bytearray(data)
struct.pack_into("<I", outside, 512 + 4, 99)
rejected(lambda: Pak(outside).read("/hello.bin"))
duplicate = bytearray(data)
duplicate[BASE + 128:BASE + 256] = duplicate[BASE:BASE + 128]
rejected(lambda: Pak(duplicate))

field = bytearray(b"PRE" + b"old\0" + b"~" * 12 + b"POST")
before = bytes(field)
assert replace_fixed(field, 3, 16, "中文") == b"old"
assert len(field) == len(before)
assert field[:3] == b"PRE" and field[19:] == b"POST"
assert field[3:8] == "中文".encode("gbk") + b"\0"
assert field[8:19] == before[8:19]
before = bytes(field)
rejected(lambda: replace_fixed(field, 3, 16, "中" * 8))
assert bytes(field) == before
all_bytes = bytes(range(256))
assert swap_bits(swap_bits(all_bytes)) == all_bytes

inventory = json.loads((Path(__file__).resolve().parents[1] / "data/pak目录.json").read_text())
assert len(inventory) == len({e["path"] for e in inventory}) == 1016
assert all(set(e) == {"path", "block", "size", "attr"} for e in inventory)
assert all(e["block"] >= 0 and e["size"] >= 0 for e in inventory)
assert sum(e["path"].endswith(".spm") for e in inventory) == len(DESCS) == 26
assert (len(MAIN), len(HELP), len(MAP_NAMES)) == (22, 16, 15)
assert all(len(s.encode("gbk")) < 32 for s in MAP_NAMES.values())
assert all(len(s.encode("gbk")) < 1024 for s in DESCS.values())
print("PASS: synthetic PAK round-trip, fixed fields, invalid inputs and translation inventory")
