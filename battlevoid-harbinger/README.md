# Battlevoid: Harbinger 简体中文制作资料

这组译表和工具用于 **《Battlevoid: Harbinger》桌面 Java 版本**：把包内任务、提示和其他主文本，以及程序内写死的菜单文字、角色称谓改为中文，同时补充中文字形和断行支持。它针对已有的 `harbinger.jar`，不是同系列其他游戏的通用汉化器，也不是游戏本体。

原游戏及其程序、图片、音乐等权利属于原权利人。本目录是 Tong 的中文译表与本地制作工具整理；没有原 JAR、反编译的游戏类、编译后的 `.class` 或字体。未为原游戏资源另行授予许可。

## 内容和范围

| 文件 | 用途 |
| --- | --- |
| `work/主文本_简体中文.tsv` | 589 个稳定 `id` 对应的中文主文本 |
| `work/程序文本_简体中文.json` | 127 个按目标类分组的显示字符串映射 |
| `work/角色称谓_简体中文.json` | 22 个角色称谓；不修改枚举身份 |
| `work/LocalizeClasses.java` | 自写 ASM 字节码补丁器，只处理指定显示常量、称谓显示及字体／断行支持 |
| `work/StaticCheck.java` | 独立比较指令、符号引用、成员及方法结构的检查器 |
| `work/build.py` | 校验原 JAR、生成映射、调用 Java 补丁器、回填 XML 并构建汉化 JAR |
| `work/OFL.txt` | 历史使用的 Noto 字体许可文本；字体文件需要另行获取 |

主文本之外的联网内容、服务器返回文字不在这份静态资源汉化范围。译表中的英文专名、型号和品牌保留不表示漏译。

## 输入和依赖

需要 Python 3.9+、**JDK 8**。Java 工具使用 JDK 8 内部 ASM，并依赖 `-XDignore.symbol.file`，不能直接假定新版 JDK 的模块访问规则相同。将 `JAVA_HOME` 指向 JDK 8 的安装根目录。

自行准备以下文件：

```text
battlevoid-harbinger/
  inputs/harbinger.jar
  work/NotoSansCJKsc-Regular.otf
  work/OFL.txt
```

匹配原 JAR 的 SHA-256 为 `966d08f6d1e2f243bcbca6c6c5794677be372539496b391d53e32b50e43759d5`，脚本会拒绝其他版本。字体来自 [Noto CJK 官方仓库](https://github.com/notofonts/noto-cjk)，使用正确的 SC Regular 字体及其相应 OFL。仓库未附字体；如更换字体，需要同步检查构建器使用的文件名和字体许可，不能只替换扩展名。

## 构建和检查

从本目录运行：

```sh
export JAVA_HOME=/path/to/jdk8
python3 work/build.py
"$JAVA_HOME/bin/javac" -XDignore.symbol.file -encoding UTF-8 -cp work/build_classes -d work/build_classes work/StaticCheck.java
"$JAVA_HOME/bin/java" -cp work/build_classes StaticCheck inputs/harbinger.jar 汉化版/harbinger.jar \
  work/patch_mappings.tsv work/font_characters.txt work/line_break_characters.txt
```

主脚本输出 `汉化版/harbinger.jar`，并在 `work/` 生成中间映射、字形字符集、补丁类、双语对照和构建校验。它逐项检查 589 个文本 ID 和占位符、原语言内容保留、JAR 成员集合、未修改成员字节和 ZIP CRC，最后再次检查输入目录文件的哈希。`StaticCheck` 是额外的独立结构检查；语法检查通过不代表这个检查已经运行。

脚本会重建输出和中间结果，只在独立工作副本中运行。不要把唯一原件、游戏安装目录或正式存档放进工作目录。

## 应用和恢复

本仓库下载内容本身不能直接安装。取得匹配版本并成功构建后，退出游戏，先备份原 `harbinger.jar`，再以构建产物替换测试副本中的同名文件，保留其余游戏依赖。先用独立存档检查菜单、换行、战斗提示和存读档。撤回时恢复原 JAR；不应删除存档。

## 整理状态和验证

本次复核了 589 条主文本 ID 的唯一性、非空译文、127 个程序映射和 22 个称谓，Python 语法检查通过。整理副本只将个人临时 JDK 路径改为 `JAVA_HOME`、输入改为本目录 `inputs/`，并自动创建输出目录；保留原有校验规则。

历史制作记录包含 macOS 引擎字体、语言读取与字节码检查，不能当作此次重新运行结果。本次没有读取原游戏、编译补丁器、构建 JAR，或验证实际菜单、战斗、Windows 和完整游戏流程。当前发布的是可维护的译表与制作源码快照。
