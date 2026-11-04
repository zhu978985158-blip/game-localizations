# 多游戏简体中文译文与制作工具 / Game Localizations

这里集中维护 Tong 整理的游戏及 Mod 简体中文译文、配置说明、字体与资源制作工具。每个子项目面向特定游戏和输入版本；请先读对应说明。**这不是游戏下载站，也不是把仓库复制进游戏就能使用的成品汉化合集。**

## 项目索引

| 作用于哪款游戏 | 项目 | 用途与收录范围 | 入口 |
| --- | --- | --- | --- |
| 上古卷轴5：天际特别版 / Skyrim Special Edition | High Level Enemies | 326 条译文、ESP 文字回填工具、中文 FOMOD 安装器模板；针对敌人等级扩展 Mod | [说明](skyrim/high-level-enemies/README.md) |
| 上古卷轴5：天际特别版 / Skyrim Special Edition | Elianora’s Breezehome Overhaul（微风阁大修） | 476 条 ESP 与 208 条安装器译文，ESP/FOMOD/PEX 翻译和校验工具；针对雪漫城住宅改造 Mod | [说明](skyrim/breezehome/README.md) |
| 英灵神殿 / Valheim | 五款 BepInEx Mod 的中文配置 | LazyVikings、BetterSmelting、LichKing、BossAdd、Races Of Valheim 的配置注释和使用说明 | [说明](valheim/README.md) |
| 侠盗猎车手：圣安地列斯 / GTA: San Andreas（Android） | ARM Cheat Menu 2.2 | 32/64 位菜单的文字回填、中文字体制作及检查脚本；不附作弊菜单本体 | [说明](gta-san-andreas/arm-cheat-menu/README.md) |
| Battlevoid: Harbinger（桌面 Java 版） | 简体中文制作资料 | 589 条主文本、程序与角色称谓映射，自写 Java 字节码补丁器、构建与结构检查工具 | [说明](battlevoid-harbinger/README.md) |
| 第一滴血 / Rambo（Windows） | v4 汉化制作工具 | 1,474 条审校台账，界面、字幕、启动器和字库构建、校验工具 | [说明](rambo-v4/README.md) |
| 百战天虫：终极伤害 / Worms Ultimate Mayhem（Windows） | 主语言资源中文化 | 5,409 条译文、151 条技术保留项、XOM 语言读写器和字库制作原型 | [说明](worms-ultimate-mayhem/README.md) |
| 战争艺术2：全球联盟 / Art of War 2: Global Confederation（J2ME） | 既有扩充地图版基础译表 | 337 个文本槽位及地图名称、目标译表，自写显示译表生成器 | [说明](art-of-war-2/global-confederation/README.md) |
| 魔域争霸 / Atrox（Windows） | 残留文字补汉化 | 菜单、韩文帮助、战役标题和地图名补译，字体补字与资源校验工具 | [说明](atrox/README.md) |

## 怎样使用

1. 从索引打开对应项目，确认游戏、平台、输入版本或哈希及当前完成范围。
2. 自行准备合法取得且版本匹配的游戏或原 Mod，以及说明要求的字体、库和工具。仓库不附原游戏、原 Mod 二进制、模型、贴图、音乐、商业字体或客户资料。
3. 在独立工作目录运行制作和检查命令。先保留自己的原文件与存档，再按项目说明测试安装和恢复。

各子目录的依赖不同，可能需要 Python、lxml、Pillow、fontTools、JDK/ASM 等；没有一个适用于所有游戏的统一安装命令。部分工具是固定版本的历史制作流程或原型，缺少外部输入时不能构建。

## 验证与维护边界

README 分别记录文件数量、译文范围、真实输入输出、依赖、执行命令及限制。本次整理完成了译表格式、语法、路径、资源边界和相应合成数据检查；历史制作记录单独标明。**没有把静态检查或合成样例表述为完整游戏、Windows/MO2、手机或真实设备验收。**

这批文件可以公开阅读，但公开不等于为原游戏或原 Mod 重新授予许可。第三方名称、原文和资源权利归各自权利人；使用和发布构建产物时仍须遵守原作者及实际使用字体的许可。没有为整个合集添加会覆盖第三方内容的统一许可。
