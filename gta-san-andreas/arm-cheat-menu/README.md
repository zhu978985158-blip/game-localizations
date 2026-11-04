# GTA 圣安地列斯：ARM Cheat Menu 2.2 汉化制作工具

这些 Python 工具用于 **Android 版《侠盗猎车手：圣安地列斯》（Grand Theft Auto: San Andreas）** 的 **ARM Cheat Menu 2.2**。它们帮助处理菜单内嵌文字、中文字体及交付文件检查，**不是作弊菜单本体，也不是可直接安装的游戏或完整汉化包**。

历史制作布局分别针对 32 位 GTA SA 2.00 与 64 位 GTA SA 2.10；不能将这两个目标扩展为其他游戏版本、其他作弊菜单或所有 Android 设备的兼容保证。原 Mod 的作者和确切发布链接未由这批源码独立核实，原 `.so` 的权利仍归原权利人。仓库只保存本地制作脚本，不附原 `.so`、游戏、现成字体或客户文件。

## 四个脚本

| 脚本 | 用途 | 输入和输出 |
| --- | --- | --- |
| `tools/patch_mod.py` | 重定向 ImGui 默认及旧式预载的字形范围以支持中文，并在固定空间回填菜单文字；拒绝长度超限、缺失或重复匹配 | 修改传入工作包中的两份 `libCheatMenu*.so`，写 JSON 报告 |
| `tools/build_font.py` | 收集菜单所需字符，将自行准备的可用字体子集化并验证字形覆盖 | 输入字体和工作包，输出静态 TrueType 字体及报告 |
| `tools/qa_mod.py` | 检查中文 TOML、配置差异、数字 ID、字体和允许的二进制改动 | 比较原包与工作包，写报告；预期中文键数为历史原包的 251 |
| `tools/final_qa.py` | 检查历史 32／64 位交付布局、归档路径、CRC、UTF-8 标志和内容哈希 | 需要完整历史工程布局；不是任意目录的通用检查器 |

工具使用 Python 3.9 或更高版本，字体生成及主校验依赖 `fontTools`。本批只收录自写工具；中文语言输入、匹配的原 Mod、具有适当许可的源字体和字体许可说明需要自行准备，不能只下载这些脚本就重建完整安装包。

## 工作副本上的用法

先退出游戏，保存原 Mod 与个人配置的独立副本。以下命令均从本目录运行，`work/original` 是只读参照，`work/patched` 必须是另行准备的副本：

```sh
mkdir -p reports
python3 tools/patch_mod.py work/patched reports/binary-patch.json
python3 tools/build_font.py /path/to/licensed-source-font.ttf work/patched \
  work/patched/ARM/CheatMenu/font/MyFont.ttf reports/font.json
python3 tools/qa_mod.py work/original work/patched reports/check.json
```

`patch_mod.py` **会原地修改工作包中的 `.so`**。不要把正在游戏中使用的目录或唯一原件当作 `work/patched`。脚本的长度、匹配和结构检查不能替代开始前的备份。

`qa_mod.py` 还会读取 `ARM/CheatMenu/locale/English.toml`、`Chinese.toml`、配置和数据列表。历史期望是仅将 `Menu.Language` 从 English 改成 Chinese；字体需保留 `glyf` 且不能为可变字体。不同原包结构应先更新并重新验证对应检查，不能靠删掉断言绕过不匹配。

最终交付检查使用原有工程布局：

```sh
python3 tools/final_qa.py /path/to/project-root /path/to/original-archive /path/to/source-Chinese.toml
```

它预期 `01_原文件`、`03_工作文件/package`、`02_汉化版` 以及按 32／64 位分开的历史输出目录；本仓库没有附带这些文件。它会生成交付报告，不负责创造缺失的语言、字体或原 Mod 输入。

## 安装与卸载边界

这里只提供制作工具，因此本目录自身没有“安装到游戏”的步骤。制作出通过检查的匹配版本补丁后，再按你原作弊菜单的安装位置和加载器说明应用；32 位和 64 位插件不能混装。撤回时退出游戏并恢复事先保存的原 Mod 和配置。运行工具不应接触正式游戏存档，卸载也不应删除存档。

## 本次验证

四个脚本通过 Python 语法检查和安全导入。使用临时合成数据验证了固定长度回填、前后非目标字节保持、缺失／超长替换拒绝、TOML 重复键识别和 INI 读取。没有读取或修改原 `.so`，没有生成字体或运行真实交付检查，也没有进行 Android 游戏或设备测试。
