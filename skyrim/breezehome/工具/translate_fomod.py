#!/usr/bin/env python3
"""Localize FOMOD display text without changing dependency checks or file paths."""
from pathlib import Path
import re
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
XML = ROOT / "EBO-3X_简体中文_MO2" / "FOMOD" / "ModuleConfig.xml"
INFO = ROOT / "EBO-3X_简体中文_MO2" / "FOMOD" / "info.xml"


def load_lines():
    result = {}
    for number, line in enumerate((ROOT / "fomod_lines.tsv").read_text(encoding="utf-8").splitlines(), 1):
        source, sep, target = line.partition("\t")
        if not sep or not source or not target:
            raise ValueError(f"Invalid line {number}")
        if source in result:
            raise ValueError(f"Duplicate source {source}")
        result[source] = target
    return result


def display_name(text):
    if text == "GENERAL INFORMATION":
        return "安装说明"
    names = {
        "BreezehomeFULL.nif": "BreezehomeFULL.nif（完整外部模型）",
        "COMBINED README WITH CHANGELOG": "说明文件与更新日志",
        "Auto Systems SortIt()": "自动分类 SortIt() 测试工具",
        "Bat EBODisplays": "EBODisplays 批处理工具",
        "CC Armoury Expansion Player Alias Items": "CC 军械库展品测试工具",
    }
    if text in names:
        return names[text]
    text = text.replace("Elianora's Breezehome Overhaul", "微风阁大修")
    text = text.replace("ELIANORA'S BREEZEHOME", "微风阁")
    text = text.replace("Eli's Breezehome", "微风阁")
    text = text.replace("[HOME INTERIOR]", "【室内】").replace("[HOME EXTERIOR]", "【室外】")
    text = text.replace("[HOME MISCELLANEOUS]", "【其他】")
    text = text.replace("[MAIN]", "【主文件】").replace("[Main]", "【主文件】")
    text = text.replace("[ADDON - SELECT AT MOST ONE]", "【附加组件：至多选一】")
    text = text.replace("[ADDON - SELECT ANY]", "【附加组件：可多选】")
    text = text.replace("[ADDON - ", "【附加组件：").replace("[PATCH - ", "【兼容补丁：")
    if "【附加组件：" in text or "【兼容补丁：" in text:
        text = text.replace("]", "】")
    text = text.replace(" - OPTIONAL ADDONS", "—可选附加组件")
    text = text.replace(" - OPTIONAL PATCHES", "—可选兼容补丁")
    text = text.replace(" - OPTIONAL DOCUMENTATION", "—可选文档")
    text = text.replace(" - DEV TOOLS (NOT FOR USERS)", "—开发工具（普通玩家勿用）")
    text = text.replace(" - LIGHTING PATCHES (SPECIAL)", "—特殊光照补丁")
    text = text.replace(" - LIGHTING PATCHES (SINGULAR)", "—光照补丁（单选）")
    text = text.replace(" - LIGHTING PATCHES (MULTIPLE)", "—光照补丁（可多选）")
    text = text.replace(" - SEGMENTED MODEL OPTIONS", "—分段模型选项")
    text = text.replace(" - BUGFIX.GAMEPLAY", "—修复／玩法")
    text = text.replace(" - CITY OVERHAUL", "—城市大修")
    text = text.replace("[MISC PATCHES]", "【杂项补丁】")
    text = text.replace("[01]", "【01】").replace("[02]", "【02】").replace("[03]", "【03】")
    text = text.replace("[04]", "【04】").replace("[05]", "【05】").replace("[06]", "【06】")
    return text


def translate_line(line, translations):
    match = re.match(r"^([ \t>]*)(.*?)([ \t]*)$", line)
    prefix, text, suffix = match.groups()
    if text in translations:
        return prefix + translations[text] + suffix, True
    if text.startswith(("Eli's Breezehome [", "ELIANORA'S BREEZEHOME")):
        return prefix + display_name(text) + suffix, True
    replacements = {
        " (Product Addon)": "（本包附加组件）",
        " (Product Patch)": "（本包兼容补丁）",
        " [Main-file]": "【主文件】",
        " (ESP Version)": "（ESP 版）",
        " (ESL-Flagged Version)": "（带 ESL 标记版）",
        " (not embedded as a required master-file)": "（不是硬性主文件）",
        " (ESL/ESM Flagged or ESP version. Doesn't Matter)": "（ESL／ESM 标记版或 ESP 版均可）",
        " (v3.1.6+)": "（3.1.6 或更新版）",
        ' "OR" ': " 或 ",
    }
    output = text
    for old, new in replacements.items():
        output = output.replace(old, new)
    if output != text:
        return prefix + output + suffix, True
    return line, False


def main():
    translations = load_lines()
    tree = etree.parse(str(XML))
    used = set()
    for element in tree.iter():
        if element.tag in {"installStep", "group", "plugin"} and element.get("name"):
            element.set("name", display_name(element.get("name")))
        if element.tag == "moduleName":
            element.text = "微风阁大修（EBO-3X）简体中文"
        if element.tag == "description" and element.text:
            result = []
            for line in element.text.splitlines(keepends=True):
                body = line.rstrip("\r\n")
                ending = line[len(body):]
                translated, hit = translate_line(body, translations)
                if hit:
                    used.add(body.strip(" \t>"))
                result.append(translated + ending)
            element.text = "".join(result)
    # Add loose translated PEX overrides to the always-installed main file.
    for plugin in tree.iter("plugin"):
        if "【主文件】" in plugin.get("name", ""):
            files = plugin.find("files")
            if files is None:
                raise ValueError("Main plugin missing <files>")
            etree.SubElement(files, "folder", source="000.00 Eli's Breezehome Assets (ESP+BSA)\\Scripts", destination="Scripts", priority="0")
            break
    else:
        raise ValueError("Main plugin not found")
    XML.write_bytes(etree.tostring(tree, encoding="UTF-16", xml_declaration=True, pretty_print=False))
    info = etree.parse(str(INFO))
    info.find("Name").text = "微风阁大修（EBO-3X）简体中文"
    info.find("Description").text = "微风阁大修简体中文整合版；保留原 FOMOD 选项。"
    INFO.write_bytes(etree.tostring(info, encoding="UTF-16", xml_declaration=True, pretty_print=False))
    print(f"Line translations used: {len(used)}/{len(translations)}")
    print("Unused keys:")
    for key in sorted(set(translations) - used):
        print(key)


if __name__ == "__main__":
    main()
