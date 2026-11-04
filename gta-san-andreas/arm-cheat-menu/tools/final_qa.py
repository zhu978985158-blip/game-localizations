#!/usr/bin/env python3
"""Verify source preservation, install folders, and the final UTF-8 ZIP."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: final_qa.py PROJECT_ROOT ORIGINAL_ARCHIVE ORIGINAL_TOML", file=sys.stderr)
        return 2
    project = Path(sys.argv[1])
    original_archive = Path(sys.argv[2])
    original_toml = Path(sys.argv[3])
    source_dir = project / "01_原文件"
    work_package = project / "03_工作文件/package"
    localized_dir = project / "02_汉化版"
    stage = localized_dir / "ARM作弊菜单（中文完整可用版）｜ARM Cheat Menu 2.2"
    zip_path = localized_dir / "ARM Cheat Menu 2.2 中文完整可用版.zip"
    package32 = stage / "安装包_32位_GTA-SA-2.00"
    package64 = stage / "安装包_64位_GTA-SA-2.10"

    source_archive_copy = source_dir / original_archive.name
    source_toml_copy = source_dir / original_toml.name
    if source_archive_copy.read_bytes() != original_archive.read_bytes():
        raise AssertionError("source archive copy differs from original")
    if source_toml_copy.read_bytes() != original_toml.read_bytes():
        raise AssertionError("source Chinese.toml copy differs from original")

    if not (package32 / "libCheatMenu.so").is_file() or (package32 / "libCheatMenu64.so").exists():
        raise AssertionError("32-bit package contains the wrong plugin set")
    if not (package64 / "libCheatMenu64.so").is_file() or (package64 / "libCheatMenu.so").exists():
        raise AssertionError("64-bit package contains the wrong plugin set")
    if (package32 / "libCheatMenu.so").read_bytes() != (work_package / "libCheatMenu.so").read_bytes():
        raise AssertionError("32-bit delivery plugin differs from verified build")
    if (package64 / "libCheatMenu64.so").read_bytes() != (work_package / "libCheatMenu64.so").read_bytes():
        raise AssertionError("64-bit delivery plugin differs from verified build")

    common_expected = {
        **{f"ARM/{key}": value for key, value in tree_hashes(work_package / "ARM").items()},
        **{f"configs/{key}": value for key, value in tree_hashes(work_package / "configs").items()},
    }
    for label, package in (("32-bit", package32), ("64-bit", package64)):
        actual = {
            **{f"ARM/{key}": value for key, value in tree_hashes(package / "ARM").items()},
            **{f"configs/{key}": value for key, value in tree_hashes(package / "configs").items()},
        }
        if actual != common_expected:
            raise AssertionError(f"{label} common data differs from verified build")
        config = (package / "configs/ARM.CheatMenu.ini").read_text(encoding="utf-8")
        if "Language=Chinese" not in config:
            raise AssertionError(f"{label} package does not default to Chinese")
        if not (package / "ARM/CheatMenu/locale/Chinese.toml").is_file():
            raise AssertionError(f"{label} package is missing Chinese.toml")
        if not (package / "ARM/CheatMenu/font/OFL-NotoSansSC.txt").is_file():
            raise AssertionError(f"{label} package is missing the font license")

    expected_files = {
        f"{stage.name}/{path.relative_to(stage).as_posix()}": path
        for path in stage.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise AssertionError(f"ZIP CRC failure: {bad_member}")
        actual_files = {info.filename: info for info in archive.infolist() if not info.is_dir()}
        if set(actual_files) != set(expected_files):
            missing = sorted(set(expected_files) - set(actual_files))
            extra = sorted(set(actual_files) - set(expected_files))
            raise AssertionError(f"ZIP member mismatch: missing={missing}, extra={extra}")
        for name, path in expected_files.items():
            posix = PurePosixPath(name)
            if posix.is_absolute() or ".." in posix.parts:
                raise AssertionError(f"unsafe ZIP path: {name}")
            info = actual_files[name]
            if any(ord(ch) > 127 for ch in name) and not (info.flag_bits & 0x800):
                raise AssertionError(f"UTF-8 flag missing for ZIP member: {name}")
            if archive.read(name) != path.read_bytes():
                raise AssertionError(f"ZIP content mismatch: {name}")

    report = {
        "source_preservation": {
            "archive_sha256": digest(original_archive),
            "archive_copy_identical": True,
            "chinese_toml_sha256": digest(original_toml),
            "chinese_toml_copy_identical": True,
        },
        "delivery": {
            "zip": zip_path.name,
            "zip_size": zip_path.stat().st_size,
            "zip_sha256": digest(zip_path),
            "zip_crc": "PASS",
            "zip_utf8_names": "PASS",
            "zip_file_count": len(expected_files),
            "unsafe_paths": 0,
            "package_32bit_plugin": "libCheatMenu.so only",
            "package_64bit_plugin": "libCheatMenu64.so only",
            "common_data_matches_verified_build": True,
        },
        "result": "ALL DELIVERY CHECKS PASSED",
        "runtime_test": "Android GTA SA real-device validation is still required.",
    }
    report_path = localized_dir / "最终交付验证.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
