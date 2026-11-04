# 英灵神殿（Valheim）Mod 中文配置说明

本目录用于 **《英灵神殿》（Valheim）** 的 BepInEx Mod，收录五份已有的中文配置资料。主要作用是让玩家看懂英文设置项、默认值、范围和服务器同步说明，**不是原 Mod 的完整代码或安装包，也不保证把游戏界面全部汉化**。

| 子目录 | Mod / 配置内版本 | 插件标识 | 主要内容 |
| --- | --- | --- | --- |
| `lazy-vikings` | LazyVikings 1.2.3 | `blacks7ar.LazyVikings` | 蜂箱、窑炉、冶炼与其他设施的自动化、材料保留及同步设置 |
| `better-smelting` | BetterSmelting 1.3.0 | `ruijven.BetterSmelting` | 替代燃料、冶炼／加工设施与相关操作配置 |
| `lich-king` | LichKing 1.0.2 | `Voidey.LichKing` | 巫妖王主题装备、制作条件与效果配置 |
| `bossadd` | BossAdd 1.0.5 | `bossadd` | 各 Boss 生命值等战斗参数的中文注释 |
| `races-of-valheim` | Races Of Valheim 1.4.9 | `com.nandor.racesofvalheim` | 种族能力、外观、快捷键与战斗效果配置 |

名称、版本及标识来自配置文件头，中文配置由 Tong 整理。原 Mod 可从原作者发布页识别：[LazyVikings / blacks7ar](https://thunderstore.io/c/valheim/p/blacks7ar/LazyVikings/)、[BetterSmelting / Ruijven](https://thunderstore.io/c/valheim/p/Ruijven/BetterSmelting/)、[BossAdd / LJS](https://thunderstore.io/c/valheim/p/LJS/BossAdd/)、[RacesOfValheim / Nandor](https://thunderstore.io/c/valheim/p/Nandor/RacesOfValheim)。LichKing 的命名空间为 `Voidey`，确切原发布页本批尚未核实。以上作者／命名空间用于识别插件，不表示原 Mod 由本仓库作者制作，也不构成对原 DLL 的再分发授权。

请从相应原作者渠道获取匹配原 Mod 和依赖，并遵守其授权。发布页可能已有更高版本；这里是上表版本的配置快照，不是持续更新的配置镜像。本目录不含原 DLL、补充运行时 DLL、模型、贴图、服务器地址或存档，也没有收录 Ways of the Gods。

## 安装和使用

1. 先安装匹配版本的原 Mod、BepInEx 和其所需依赖，正常启动一次，让插件生成配置，再退出游戏和服务器。
2. 备份你自己的 `BepInEx/config` 中对应 `.cfg`。本目录各子文件夹中的文件名就是对应插件所使用的配置名。
3. 优先把中文注释合并进自己的配置，保留个人设置值。若直接覆盖整份文件，里面的实际参数也会一起覆盖；这些不是只更新注释的自动合并补丁。
4. 使用相同文件名放回 `BepInEx/config/`，重新启动，并查看 BepInEx 日志确认插件加载与配置解析。服务器同步、管理员锁定项目应由有权限的一端配置，单独更换客户端文件不一定改变服务器行为。

不要改动英文节名、键名和枚举值；有些插件只识别这些固定标识。版本升级后新增、改名或废弃的选项需要按新原版配置逐项比对，不能直接假定旧文件仍完整兼容。

## 撤回

退出游戏后恢复先前备份的配置即可。也可让原插件重新生成配置，但这会失去你当前的个性化参数，不应通过删除存档或替换游戏文件处理配置问题。

## 本次检查

五份配置均按 UTF-8（包含需要的 BOM）完整复制，并通过节名／键值结构解析；没有改写配置值。只进行了文件与文本结构检查，未安装原 Mod、进入游戏或连接服务器验证。该检查不能替代具体插件版本下的功能和服务器同步测试。
