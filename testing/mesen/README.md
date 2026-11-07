# Mesen 调试脚本

`trace_battle.lua`、`replay_x_window.lua` 来自原 R30 工程，保留其探针逻辑。没有捆绑普通存档、即时存档、转储或模拟器。原生入口地址是本作特定地址。

`tools/run_mesen.py` 提供参数化启动，可在**新隔离目录**中运行已有 R29/R30/R45 身份的冷启动路线。原历史路线要求 SRAM SHA256 `5949394e7e70097649207f5d539a77a15506d294b1aa44ef64d26c1a6c570e09`；不同存档应另写实际输入路线，不能把未到入口判为补丁失败。

```powershell
python tools/run_mesen.py --emulator 'D:\Mesen\Mesen.exe' --rom 'D:\ROM\R45_X.smc' --sram 'D:\Saves\field.srm' --output local/mesen-x --x
python tools/run_mesen.py --emulator 'D:\Mesen\Mesen.exe' --rom 'D:\ROM\R45_X.smc' --sram 'D:\Saves\field.srm' --output local/mesen-normal
```

它会声明并写入机体ID、驾驶员、坐标、占位、HP/EN等条件，**属于受控测试**；没有写PC、脚本游标或结果来模拟跳过。只有原生返回地图、正确skip标记和正常结束才报告具名路线通过。完整验收还要比较队伍/进度记录、消耗、奖励及保存生命周期，不能只凭这个启动器的结果声称全流程通过。

`replay_x_window.lua` 消费同ROM原生入口即时检查点；设置PROBE_OUT/PROBE_STATE/PROBE_KEY/PROBE_FIRST/PROBE_LAST环境变量即可研究单帧X、超时或其他按键。它不是跨ROM通用即时存档工具。

公开整理仅做了源码语法和本地构建检查，本轮没有新运行Mesen。历史运行范围见evidence/mesen-r30-20261015.json。
