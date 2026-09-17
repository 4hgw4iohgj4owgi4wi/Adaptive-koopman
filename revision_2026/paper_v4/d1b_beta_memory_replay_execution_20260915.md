# D1+ 参考链记忆（beta）只读回放执行记录

执行日期：2026-09-15。范围为D1+只读回放；没有修改计算源码、没有安装软件、没有执行植物积分/MPC求解/GPU/闭环，没有续跑或重跑旧P1。本文件与`experiment.md`第34节、`exp_status.md`、`exp_solution.md`、`koopman_work_log.md`同批登记。

## 正式身份与结果

- 正式协议：`protocol/D1B_BETA_MEMORY_REPLAY_20260915_v3.json`。
- 协议SHA-256：`0b766030a2c0eaf3a5bdfa7976b6587c0f8518dcf83058ded291f70e89900954`。
- 正式输出：`analysis/20260915_D1B_BETA_MEMORY_REPLAY_03`。
- 科学状态：`PASS_READ_ONLY_BETA_MEMORY_RECONSTRUCTED_WITH_GATE_LIMITS`；`figure_status=PASS_VISUAL_QA`。
- 决策：`REGISTER_BETA_RECOVERY_AS_AVAILABLE; KEEP_D3_BLOCKED_ON_G1_G2_AND_RESTART_EQUIVALENCE`。
- 错误协议SHA负例退出1且没有创建输出目录。

## 被修订的判定

第32节D1登记“`previous_u`可重建；`beta`记忆未保存，故完整恢复状态不可用，D3不可拼接”。本次把该结论拆成可证伪的一问：`beta`是独立记忆，还是已落盘参考链的确定性函数？

重放规则与冻结runner同序（`post_r3_r4_runner.py`第130、171—172行）：

1. 每周期实际接受时长由`time_s = k·Ts + accepted_duration`直接还原，不需要子步归属启发式；
2. `distance`先用该时长更新并截断到`ROUTE_LENGTH`；
3. `beta`再用**同一**`refs[0]["beta_star"]`（即更新前`distance`、`beta`处的预览）更新。

校核量是落盘的`reference_distance_m`，它与重放相互独立。

| 量 | 结果 |
|---|---|
| 距离重放最大绝对差 | `1.4210854715202004e-14` m |
| 距离重放最大相对差 | `2.2204460492503116e-16` |
| 逐位为零的tick | 1246 / 2200 |
| 时长之和 | `44.00000000000128` s |
| 时长与`Ts`最大偏差 | `3.1259717037102064e-15` s |
| 子步时间严格递增 | 0 处违反 |
| 子步`dt`和与时长和闭合残差 | `−1.2647660696529783e-12` s |
| 重建`beta`末值 | `[1.2e-9, 1.2e-9, −9.2e-5, −8.4e-5]` deg |
| 重建`beta`前缀最大绝对值 | `[8.61, 7.26, 22.45, 18.97]` deg |
| `previous_u`与solver首控制逐位相同 | **2200 / 2200 tick，最大差 `0.0`** |

`previous_u`的核对必须先还原排列：raw按分组`[a1..a4, δ1..δ4]`存放，而`solver.jsonl`的`first_control`按交错`[a1, δ1, a2, δ2, …]`存放。首版协议漏了这一步，见下文。

## 状态/记忆恢复清单

| 量 | 状态 | 依据 |
|---|---|---|
| `plant_state_x30` | IN_RAW | `raw.npz`的`x0..x29` |
| `actual_steering_delta4` | IN_RAW | `raw.npz`的`actual_delta0..3` |
| `reference_distance` | IN_RAW | `raw.npz`的`reference_distance_m` |
| `previous_u8` | IN_RAW | 排列还原后与`solver.jsonl`首控制2200/2200逐位相同 |
| `reference_beta4` | RECONSTRUCTED_THIS_ANALYSIS | 参考链确定性重放；距离递推在浮点噪声级闭合 |
| 植物/连接器隐藏记忆 | STATIC_SOURCE_INSPECTION_ONLY | 冻结plant/连接器无历史或滞回字段，`advance_outer_step`为纯函数 |
| 重启等价试验 | NOT_RUN | 需另行授权的短窗运行，本协议不允许 |

## 修订边界

**只修订“beta不可恢复”这一条。**以下全部保持：D1的晚段纵/横向/航向/速度分解、用户指定的`FAIL_LATE_TRACKING_DIVERGENCE`、未观测179周期不补画、旧P1不续跑/不重跑、D3对G1/G2的阻断、全部旧失败证据。三条限制同等登记：

1. `beta`从未落盘，本回放是“同源码路径+落盘距离自洽校核”，不是与真实`beta`序列对拍；
2. 没有做“从第k tick重启后与原轨迹逐位一致”的动态等价试验；
3. 恢复清单并非全绿（`full_restart_equivalence_test = NOT_RUN`），本分析不释放D3。

因此下一步的前置条件从“先解决G1/G2并重建beta”变为“先解决G1/G2，并在短窗协议里补一次重启等价试验”。

## 顺带核实的协议身份事实

逐项复核`protocol/RTX5080_G0_G2_20260915_v3.json`的23条`identity_files`：

```
STALE    protocol/P1中断数据分析与RTX5080迁移任务说明_20260915.md
STALE    experiment.md
MATCH    其余21条（全部gpu_port源码、controller、plant、e01_100m、references、
         post_r3_r4_runner，以及 P1 的 raw/substeps/solver/status）
```

结论：没有越权改动源码或旧结果；但第32/33节是在v3冻结之后追加进`experiment.md`的，使v3身份门失效。**即使重新授权修复，也不能直接复用v3协议重跑G1/G2**，必须另冻v4协议（新文档SHA、新源码SHA、新输出目录）。本次D1+协议据此把“会被本次工作更新的MD”排除在身份门外，只锁不可变输入，理由写入协议`identity_rule`。

## 工程缺陷与修复（只读分析自身）

首版`analysis/20260915_D1B_BETA_MEMORY_REPLAY_01`（协议v1）有两个缺陷：

- `previous_u8`把raw的分组排列与solver的交错排列直接相减，报出`9.376302005812323e-15`的伪差异，该数字不是对落盘数据的测量；
- 三处图缺陷：距离面板把精确零夹到最小次正规数产生不可读尖刺、时长面板用`0.02`量程显示`3e-15`的抖动、恢复清单面板标签压在柱上。

首版保留并写`failure.json`，不覆盖。v2修正排列还原后`previous_u`变为逐位相同，但面板2标题被右边缘截断、面板3仍不可读，故按D2既有惯例标`FAIL_VISUAL_QA_SUPERSEDED`——**数值有效并保留**。v3只改绘图（绝对偏差取对数、缩短标题），重算后四面板全部打开验收通过。

两次修正都没有改动科学阈值、重放规则或输入数据。三次运行的`executed`六项均为`false`：未跑植物、MPC求解器、GPU、闭环，未续跑P1，未改`src/`。

## 交付物

`analysis/20260915_D1B_BETA_MEMORY_REPLAY_03/`：`beta_memory_replay.json`、`beta_replay.npz`、`beta_memory_replay.png`、`beta_memory_replay.svg`、`figure_manifest.json`、`README.md`。

工具：`tools/d1b_beta_memory_replay.py`（SHA-256 `f670727714ec937486a886ca86b795c6028b32849d597a0333d671c3c79587c1`）。
