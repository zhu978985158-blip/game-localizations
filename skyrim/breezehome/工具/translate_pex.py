#!/usr/bin/env python3
"""Extract selected Papyrus PEX files from BSA and replace UTF-8 string-table entries."""
from pathlib import Path
import struct

TRANSLATIONS = {
    "Start the giving...": "开始发放物品……",
    "Giving done! ": "物品发放完成！用时 ",
    "Sort is already running!": "物品分类正在进行！",
    "Please wait until variable initialization has completed!": "请等待变量初始化完成！",
    "Beginning sort...": "开始分类……",
    "Sort container empty!": "分类容器为空！",
    "Sort done! ": "分类完成！用时 ",
    "Variable initialization complete!": "变量初始化完成！",
    "Added ": "已添加 ",
    "AutoLoot in Operation": "自动取料正在运行",
    "The Breezehome Armoury ladder is in a collapsed state. You cannot enter. Haha!!!": "微风阁军械库的梯子已收起，无法进入！",
    "PLNPCUS: SKSE64 was not found, please install SKSE64": "PLNPCUS：未找到 SKSE64，请先安装 SKSE64",
    "Door Unlocked": "门已解锁",
    "Door Locked": "门已上锁",
}


def bsa_files(path):
    data = path.read_bytes()
    if data[:4] != b"BSA\x00":
        raise ValueError(f"Not a BSA: {path}")
    folders = struct.unpack_from("<I", data, 16)[0]
    offset = 36 + folders * 24
    entries = []
    for folder_index in range(folders):
        count = struct.unpack_from("<I", data, 36 + folder_index * 24 + 8)[0]
        length = data[offset]
        folder = data[offset + 1:offset + 1 + length].rstrip(b"\x00").decode("latin1")
        offset += 1 + length
        for _ in range(count):
            _, size, file_offset = struct.unpack_from("<QII", data, offset)
            offset += 16
            entries.append((folder, size, file_offset))
    for folder, size, file_offset in entries:
        end = data.index(b"\x00", offset)
        name = data[offset:end].decode("latin1")
        offset = end + 1
        if name.lower().endswith(".pex"):
            if size & 0x40000000:
                raise ValueError(f"Compressed PEX not supported: {name}")
            yield folder, name, data[file_offset:file_offset + size]


def replace_pex_strings(data, name):
    if data[:4] != b"\xfa\x57\xc0\xde":
        raise ValueError("Not a Papyrus PEX")
    hits = []
    translations = dict(TRANSLATIONS)
    if name == "ebo_autosort_sortingquestscript.pex":
        # This is used by StringUtil.Find(itemName, ...). Vanilla heart items
        # have Chinese names in a Chinese game, so the English predicate misses them.
        translations["heart"] = "心"
    for old, new in translations.items():
        source = old.encode("utf-8")
        target = new.encode("utf-8")
        marker = struct.pack(">H", len(source)) + source
        count = data.count(marker)
        if count:
            data = data.replace(marker, struct.pack(">H", len(target)) + target)
            hits.extend([old] * count)
    return data, hits


def main():
    root = Path(__file__).resolve().parents[1]
    src = root / "原版解包"
    dst = root / "EBO-3X_简体中文_MO2"
    for bsa in src.rglob("*.bsa"):
        if bsa.name not in ("Eli_Breezehome.bsa", "Eli_Breezehome [ADDON - Auto Systems].bsa"):
            continue
        count = 0
        for folder, name, data in bsa_files(bsa):
            translated, hits = replace_pex_strings(data, name)
            if not hits:
                continue
            folder_target = dst / bsa.relative_to(src).parent / "Scripts"
            folder_target.mkdir(parents=True, exist_ok=True)
            (folder_target / name).write_bytes(translated)
            count += len(hits)
            print(name, len(hits), ", ".join(hits))
        print(bsa.name, "translated literals", count)


if __name__ == "__main__":
    main()
