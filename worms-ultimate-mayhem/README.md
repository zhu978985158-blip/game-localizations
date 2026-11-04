# 百战天虫：终极伤害（Worms Ultimate Mayhem）中文译表与工具

这份资料用于 **Windows 游戏《百战天虫：终极伤害》（Worms Ultimate Mayhem）** 的主语言资源中文化。公开可编辑译表、XOM 语言读写器、字体制作原型及原有检查工具；不附游戏、原始 XOM、字体、图片、视频或第三方工具源码。

游戏与原资源属于原权利人。本地中文译文和工具由 Tong 整理；XOM 结构研究参考 [AlexBond2 的 Xom2Xml](https://github.com/AlexBond2/Xom2Xml)，这里没有复制它的第三方实现。历史字库使用 [Noto CJK](https://github.com/notofonts/noto-cjk) SC Bold，字体需从官方获取并遵守对应 OFL，随新成品附上实际使用字体的许可。

## 已收录什么

`译文/主语言表.json` 是当前维护入口，含 5,409 条译文：

| 原资源文件 | 中文条目 |
| --- | ---: |
| `English.xom` | 2,344 |
| `EngFE.xom` | 1,463 |
| `EngLoading.xom` | 41 |
| `EngLS.xom` | 1,561 |

`技术保留.json` 列出另外 151 条明确保留项，包括图标／输入字符表、纯占位、空值与专用拼字等。两份武器 TSV 用作术语和帮助文字参考，构建以主 JSON 为准，不应把历史分批 TSV 逐份再覆盖回去。

`工具/xom_language.py` 读取 `MOIK/STRS/CTNR` 结构，以追加字符串方式重建语言文件，保留键、尾部和原字符串；无改动回写要求逐字节相等。`validate_translations.py` 检查实际原文键、保留分类、格式占位符、`\l` 分段和随机名字数量。`build_font.py` 扩充字体图集并保留原字形映射，`validate_build.py` 从实际资源回读文字与字体，检查非目标对象字节。

`验证/字体页结构.json` 和 `初步字体映射.json` 是该原包的结构元数据，不是字体文件；字体构建需要它们与匹配的原资源共同使用。它们不能证明其他版本的对象编号与布局相同。

## 自备输入和生成

Python 3.9+；语言工具只需标准库，字体工具与构建检查需要 Pillow。按下面的相对布局准备**独立工作副本**：

```text
原始解包/Worms Ultimate Mayhem/Game/
  Data/Language/PC/English.xom
  Data/Language/PC/EngFE.xom
  Data/Language/PC/EngLoading.xom
  Data/Language/PC/EngLS.xom
  Data/Bundles/Bundl03.xom
工具/字体源/NotoSansCJKsc-Bold.otf
验证/字体页结构.json
验证/初步字体映射.json
```

不要将正式安装目录或唯一原件重命名为工作目录。先确认四份原资源可无改动往返，并且字体与对象结构符合检查条件。命令从本目录运行：

```sh
python3 工具/validate_translations.py
python3 工具/xom_language.py
python3 工具/build_font.py
python3 工具/validate_build.py
```

生成文件位于 `开发测试补丁/Game/Data/Language/PC/` 和 `开发测试补丁/Game/Data/Bundles/Bundl03.xom`；报告写入 `验证/`。字体构建文件自身标明是**字体测试原型**，图集方向、字重、基线和间距需要 Windows 画面验收。脚本若因原包结构或字形容量不匹配而失败，应核对输入，不能删断言来强行产出。

## 应用和撤回

只有在生成和校验成功后，才退出游戏，备份五份对应原资源与独立存档，在测试副本中按 `Game/` 相对路径覆盖。目录名 `开发测试补丁` 不是可直接复制到任何游戏根目录的万能安装层级，应先找到实际 `Game/Data`。

撤回时退出游戏并恢复原来五份文件；保留个人存档。原始 XOM 和字体不随本仓库发布，恢复资源应从你自己的匹配原件备份取得。

## 当前阶段和本次验证

这份工作覆盖四份主语言表，**不代表全范围最终汉化**。启动器、额外脚本硬编码、图片和视频画面文字尚未在这套源码中完成；全文语境审校与地图／外观逐项对照仍有边界。历史客户验收版 v0.2 与早期仅含 317 条的 v0.1 测试包不是同一范围，本仓库没有附带或冒充其中任一成品。

本次检查 5,409 条译文与 151 条保留项数量、非空、无 NUL、键不重叠及“天虫”术语要求；语法检查通过。合成 XOM 通过无改动字节一致、中文回填后重读、键和尾部保持、未知键拒绝；可变整数边界往返通过。字体结构元数据按原件复制。

本次没有读取游戏原 XOM、生成字库、运行真实资源校验或进行 Windows 实测。历史记录中的 3,126 字形覆盖和原资源回写结果没有在此次重新执行，不能据此保证新输入版本的游戏兼容性。
