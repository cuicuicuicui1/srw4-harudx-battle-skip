# 春风DX：手柄 X 跳过战斗与原改版维护工具

用于 SFC/SNES《第4次超级机器人大战》春风DX（HaruDX）的开源维护工具。提供开战按手柄 X 跳过演出的 58 字节补丁源码、两份 BPS 增量补丁、中文技术说明，以及原改版资源索引与本地提取器。

**功能范围：** 确认普通战斗时按住手柄 X，或在约半秒窗口内轻按 X，即继续原生战后流程；不按则等待窗口后正常播放。动画已经开始后按 X 不会中断。每场单独判断，不写永久选项。X 指 SNES 手柄 X，键盘映射取决于模拟器。

## 快速入口

- [X 跳过技术说明](docs/technical.md)：钩子、按键位、解释器 ABI、原生结算、58 字节空间归属。
- [BPS 补丁与精确指纹](patches/manifest.json)：R45 标准→R45 X，R29→R30 X。
- [原改版解包与资源地图](docs/original-resources.md)：解析范围、边界、未解项和本地提取。
- [如何复现与贡献修复](CONTRIBUTING.md)：Issue、回归和提交要求。
- [历史运行证据](evidence/mesen-r30-20261015.json)：Mesen 具名场景，不是全游戏认证。
- [Mesen 调试脚本](testing/mesen/)：原生入口追踪、X 按键窗口回放、参数化隔离启动。

## 使用补丁

在 [Releases](https://github.com/cuicuicuicui1/srw4-harudx-battle-skip/releases) 下载对应 BPS，或直接使用仓库 [patches/](patches/)。用支持 BPS 的补丁工具应用到一个新文件。

| 底包 | 功能补丁 | 底包 SHA-256 |
|---|---|---|
| 春风DX R45 标准版 | [R45-standard-to-X.bps](patches/R45-standard-to-X.bps) | `8105ce9fced0519d733de4499e7ccacb72c5c951b02fae6c0bf78001f1b738bb` |
| 冻结春风DX R29 | [R29-to-R30-X.bps](patches/R29-to-R30-X.bps) | `897c76f1dc45573ea1313a8098c2b6dc4b3e27300bc2b622657905e48d3ef6db` |

补丁只添加开战 X 跳过功能，不能直接给日文 ROM、其他改版或已经打过的 X 版叠加。输入是 4 MiB 无 copier header 的精确底包。切换构建后从普通存档冷启动，避免跨构建即时存档保留旧脚本状态。

## 从源码构建

Python 3.10+，全部使用标准库，无须安装第三方包或汇编器。

```powershell
# 仅在内存构建并核验，不输出 ROM
python apply_x_skip.py 'D:\ROM\春风DX_R45_标准版_20261028.smc' --check

# 输出至不存在的新文件，拒绝覆盖
python apply_x_skip.py 'D:\ROM\春风DX_R45_标准版_20261028.smc' --output 'D:\ROM\春风DX_R45_X.smc'

# 本地核验源码构建、仓库 BPS 重建与回放；可选比较自备的目标 ROM
python tools/verify_local.py 'D:\ROM\春风DX_R45_标准版_20261028.smc' --expected-target 'D:\ROM\春风DX_R45_X.smc'

# 自己重建相同 BPS
python tools/make_patch.py 'D:\ROM\春风DX_R45_标准版_20261028.smc' 'D:\ROM\R45-X.bps'
```

构建器检查精确 SHA-256、钩子原字节、实际压缩流结束位置、329 个图像流以及最终目标 SHA-256。输出与已交付 X 版逐字节相同；当前两组转换实际差分均为 63 字节。

## 原改版资源资料

公开的是地址、容量、控制数量、哈希和解析状态；原游戏正文、图像、字库及玩家进度由工具从自备 ROM 本地提取。已列出 329 个非空图像资源及 8,725 个可解析文本目录入口，另外三条目录路径标为 unresolved。不能据此宣称已解包所有程序、动画、地图和剧情控制流。

```powershell
# 只生成索引（输出目录须不存在）
python tools/inspect_original.py 'D:\ROM\HaruDX_v05_09.smc' --output local/original-index

# 同时将压缩流、零历史解压图像、编码文本写到本地
python tools/inspect_original.py 'D:\ROM\HaruDX_v05_09.smc' --output local/unpacked --extract
```

精确日文原改版 SHA-256：`5cea22b5995e91e7e19c9ff73a2036f1929e5f162ea56d0819628728ec3d50d0`。本地提取不需要汉化字库或私有工程路径。资料见 [original/](original/)。

## 验证与已知边界

```powershell
python -m unittest discover -s tests -v
```

CI 在 Windows/Linux、Python 3.10/3.13 上运行无需 ROM 的测试，验证格式边界、输入保护、代码分支和补丁指纹。它不运行游戏，也不证明全关卡无 bug。

2026-10-15 的 Mesen 2.1.1 专用记录覆盖：不按／按住／短按／超时／按错键、反击、EN、弹药、击坠奖励、剧情推进、地图控制、原生保存与冷读档，七组结果记录相同。2026-11-07 从 R29 和 R45 标准版精确重建对应现存 X 成品；2026-11-08 公开补丁通过独立 BPS 解析器回放。

MAP 武器、全部敌方先手、全部剧情和硬件没有穷尽验证；本仓库也不是完整汉化源码包。原视频中“舰娘头像与杜台词组合”的完整自然入口尚未复现，不能据此推测改动人物分派。请把新问题写入 Issue，附 ROM 哈希及操作步骤。

## 许可

自研代码和说明采用 [MIT](LICENSE)。原游戏、改版及第三方汉化资产权利不由本许可授予，详见 [NOTICE.md](NOTICE.md)。仓库与 Release 不包含 ROM、玩家存档、图像字库或模拟器。
