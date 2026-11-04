# 微风阁大修简体中文翻译资料

对应 **Elianora's Breezehome Overhaul**，项目名称中的原作者署名为 **Elianora**，本地汉化包标识为 **EBO-3X**。原始发布链接、确切上游版本及再分发授权尚未通过本次源文件整理核验。

这里保存译表与制作工具，不附带完整原 Mod、BSA、ESP、PEX、模型、贴图或客户记录。构建时须自行取得与这些译表匹配的原 Mod；本目录不构成原 Mod 的完整安装包。

## 文件

- `esp_translation.tsv`：476 条 ESP 原文与译文，无表头，每行两列；文本内换行用 `<NL>` 表示。
- `fomod_lines.tsv`：208 条安装器描述原文与译文，无表头，每行两列。
- `工具/translate_esp.py`：转换 ESP 内嵌文本字段，保留记录与组结构；有译文命中时添加 xEdit UTF-8 标记。
- `工具/translate_pex.py`：从指定 BSA 提取并翻译 Papyrus 脚本字符串，含 14 条内置译文及限定脚本的 `heart → 心` 修正。
- `工具/translate_fomod.py`：翻译安装器显示文本，并加入汉化脚本的安装映射。
- `工具/verify_package.py`：比较原包与输出树的 ESP、安装器、BSA 和 PEX；其中 PEX 预期改动数固定为 15，适用于这份历史原包，不是任意版本的通用校验器。

## 输入布局与运行

使用 Python 3；安装器转换和包校验还需要 `lxml`。所有命令从本目录运行。

自行将原 Mod 解包为 `原版解包/`，并用同一原包的独立副本准备 `EBO-3X_简体中文_MO2/` 输出树，保持文件层级一致。原版目录只作输入。

对需要翻译的各个 ESP 分别执行，原包相对路径在输出树中保持一致：

```sh
python3 工具/translate_esp.py "原版解包/相对路径/插件.esp" "EBO-3X_简体中文_MO2/相对路径/插件.esp" esp_translation.tsv
```

脚本处理与安装器更新使用固定相对布局：

```sh
python3 工具/translate_pex.py
python3 工具/translate_fomod.py
python3 工具/verify_package.py
```

PEX 工具仅处理 `Eli_Breezehome.bsa` 与 `Eli_Breezehome [ADDON - Auto Systems].bsa`，不支持其中的压缩 PEX。输出为对应子目录中的松散 `Scripts/*.pex`，不会改写 BSA。

安装器工具会原地改写输出树的 `FOMOD/ModuleConfig.xml` 与 `FOMOD/info.xml`，并增加一项脚本映射。**每次重建须从干净原包副本准备输出树，不能对已汉化 XML 连续重复运行。** 完整包校验需要原版和输出的全部对应资源，仓库本身不提供这些资源，也没有自动打包入口。

## 本次检查范围

四个脚本通过 AST/compile 检查；两个译表均为两列，无空原文、空译文或重复原文。纯函数自检使用合成数据，覆盖 ESP 翻译与结构、FOMOD 文本替换、PEX 翻译和非法魔数拒绝。

未运行真实原 Mod 的全量转换、完整包校验、Windows MO2 或游戏。既有历史交付记录不等于本次重新实机验证。
