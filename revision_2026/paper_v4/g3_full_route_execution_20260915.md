# G3 有界闭环窗口与全路线 GPU 放行执行记录

执行日期：2026-09-15。范围为G3有界闭环窗口、重启等价判定、机理登记与全路线GPU放行；未修改任何冻结runner/植物/控制律，未改任何阈值。

## 正式身份与结果

| 项 | 值 |
|---|---|
| G3协议 | `protocol/G3_RESTART_EQUIVALENCE_20260915_v4.json`，SHA-256 `02e1ed84a82d90f6af28f30f5b4e3f6f68af213fa021d7fed7e260c157db5ee5` |
| G3比较输出 | `analysis/20260915_G3_RESTART_EQUIVALENCE_02`，总状态 `FAIL_G3_STOP` |
| 机理分析 | `protocol/G3B_DIVERGENCE_MECHANISM_20260915_v1.json`（SHA `85645578...68910`）→ `analysis/20260915_G3B_DIVERGENCE_MECHANISM_01`，`PASS_READ_ONLY_MECHANISM_ANALYSIS` |
| 图表QA | `analysis/20260915_G3_VERDICT_QA_02`，`figure_status=PASS_VISUAL_QA` |
| 全路线协议 | `protocol/R4_P1_2MS_GPU_20260915_v1.json`，SHA-256 `1db9ab1811e4d916a6234424dd561b9996ecf51df3752bfc67c7cbefcd466e70`，29条身份 |
| 全路线运行 | `results/20260915_R4_P1_2MS_GPU01`，23:09:44启动，P1/2ms/2379周期，截止6h |

## 1. 实验设计

三个窗口各30 tick，来自已保存P1前缀（`results/20260915_R4_P1_2MS01`），每个窗口跑两个后端：

| 窗口 | start_tick | 覆盖 |
|---|---:|---|
| force_peak | 1335 | t=26.70—27.30s，含保存的最大点力tick(t=26.94s) |
| steering_limit | 820 | t=16.40—17.00s，含保存的最大请求转角tick(t=16.64s) |
| late_prefix | 2170 | t=43.40—44.00s，中断前最后30个已保存tick |

检查点重建：state(30)、actual_delta(4)取自第`start_tick−1`行；`previous_u`按`[a1,δ1,a2,δ2,…]`交错重建；`distance`取该行参考距离；`beta`由参考链回放（与D1B同源规则，回放闭合至`2.22e-16`相对）。

两问分开：**CPU重放**检验检查点保真（重建的状态能否复现历史），**GPU**检验后端等价（CUDA能否驱动同一条闭环）。

## 2. 结果

| 判定 | force_peak | steering_limit | late_prefix |
|---|---|---|---|
| cpu_run_completed | PASS | PASS | PASS |
| gpu_run_completed | PASS | PASS | PASS |
| **restart_position_within_tolerance (1e-6 m)** | **PASS** | **PASS** | **FAIL** |
| restart_heading_within_tolerance (1e-6 rad) | PASS | PASS | PASS |
| gpu_position_within_tolerance (1e-2 m) | PASS | PASS | PASS |
| gpu_heading_within_tolerance (0.05°) | PASS | PASS | PASS |
| gpu_force_peak_within_tolerance (1%) | PASS | PASS | PASS |
| original_hard_gates_hold | PASS | PASS | PASS |
| 窗口总判定 | **PASS** | **PASS** | **FAIL** |

实测偏差（相对已保存轨迹的最大位置偏差）：

| 窗口 | CPU重放 | GPU | 保存力峰 |
|---|---|---|---|
| force_peak | **0.0（30 tick全部逐位相同）** | 8.86e-10 m | 263.373 N |
| steering_limit | 2.87e-10 m | 2.57e-10 m | 212.390 N |
| late_prefix | 1.22e-6 m | 5.29e-6 m | **0.000 N** |

窗口耗时：GPU约130s，CPU约388s（≈3.0×），与原硬门无关的成本结果。

## 3. 唯一失败判定的机理

`analysis/20260915_G3B_DIVERGENCE_MECHANISM_01`登记三条：

1. **力承载窗口CPU重放逐位完全相同**（30 tick全为0.0）→ 重建方法本身正确；
2. late窗口保存连接力**恰为0.000 N**（free play），偏差**台阶式**增长（前4 tick为0，随后跳到1e-6量级）→ 正则化free-play力律的**分支切换**被刚性闭环放大，不是平滑漂移；
3. 唯一允许的seed是`beta`回放的1e-16误差：冻结runner**从未落盘每周期接受时长**（只在`time_s`中留下累加和），因此**逐位重建`beta`原理上不可能**。

**结论**：中断的P1前缀**不可续接**，任何续跑必须是全新路线。**D1原始判定被实测证实**；第34节“beta可重建、障碍已除”的修订须加限定——重建只保证浮点级一致，不足以在free-play敏感段复现历史。

## 4. 放行处理（防误读）

G3协议决策规则原文为“任一窗口失败则不释放全路线”。`R4_P1_2MS_GPU_20260915_v1.json`以`decision_rule_supersession`字段**显式书面取代**该规则，且**只针对两个`restart_*`判定**：

1. **未改任何阈值或容差**，重启门仍1e-6 m，FAIL判定原样记入放行协议；
2. 全路线从**冻结初值**起跑，从不重建检查点，`restart_*`判定不描述它；
3. 全路线**依赖的**判定（CUDA闭环位置/航向/受力一致性与原硬门）**三窗口全部通过**；
4. 失败机理已单独登记，不是检查点错误。

并写明审计注记：**若审阅者不接受这一区分，正确做法是停止本次运行，而不是调整重启容差。**

runner内父门**逐条实时复核**：所需的6项G3判定必须全为真，登记的失败判定必须与实时报告一致（`PARENT_G3_VERDICT_RECORD_MISMATCH`），G3B机理与v5资格必须存在且为PASS。

## 5. 全路线运行

`results/20260915_R4_P1_2MS_GPU01`：23:09:44启动，参数P1、植物最大步长2ms、2379周期、候选`EXP-R3-unfrozen-v1`、实施`R4-full-route-gpu-v1`、绝对截止6小时。开始后12分钟到160/2379（约4.43 s/次求解），预计约2.9—3.1小时完成。

与原CPU候选**逐项不变**：控制律、植物、N=20、控制20ms、预测2ms、λ=2、未冻结雅可比、差分步长1.0、路线与参考速度、15000N/轮胎1.0/支承≥0硬门。**变化只有后端**（8进程CPU并行差分→单CUDA worker）。新增落盘字段`tick_index`、`reference_beta*`、`previous_u*`、区间起始参考距离。

该实现不内部维护每周期构形误差，`maximum_configuration_error_m`显式置`null`并附注，真实值由`tools/full_route_compare.py`从落盘状态/参考距离/beta计算。

## 6. 过程缺陷（全部保留证据，未改门）

| 版本 | 缺陷 | 处理 |
|---|---|---|
| G3 v1 | 协议缺`absolute_parameters`，runner身份门KeyError | 启动即停、无输出；冻v2 |
| G3 v2 | `execute()`自行重取model实例→CUDA后端`CUDA_BACKEND_MODEL_IDENTITY_MISMATCH`被`solve()`吞成`MODEL_DOMAIN_ERROR`（残差inf、0秒返回） | 三条GPU窗口首tick前停止；保留`failure.json`；冻v3 |
| G3 v3 | `previous_u`用raw的**分组**排列而非控制器的**交错**排列 | 三窗口`restart_*`全FAIL；用`solver.jsonl`首控制逐位定案（交错`True`/分组`False`；交错复现差6.77e-11、分组1.39e-01）；冻v4 |
| 比较器图 | 裁决用柱高表示，FAIL高度0→面板看似全绿 | 冻结比较器不改；另出只读重绘`G3_VERDICT_QA_02` |

**“分组/交错”排列坑已第三次出现**（D1B分析v1、G3检查点重建），故v4起`rebuild_checkpoint`内置`assert_previous_control_layout`运行时**逐位自检**，命中即抛`PREVIOUS_CONTROL_LAYOUT_MISMATCH`。

比较器`full_route_compare.py`初版构形误差误用`yaw_rate=0`，已修为`SPEED*_path_sample(distance)[3]`（与冻结runner一致）；该文件在运行协议的身份表内，故完成后将以**比较协议v2**重新冻结，运行中的路线不受影响。

## 7. 边界与后续

- 全路线尚未出裁决；不得与旧CPU前缀拼接，不得以离线墙钟宣称实时，不得以GPU通过宣称P1根因已解。
- 完成后按`tools/full_route_compare.py`与前2200个tick的CPU参考逐tick比较并全程核对原硬门，再据实测差异决定2/1/0.5ms身份与P2是否跟进。
- D3的短窗方案必须改为**从冻结初值起跑**，而不是中途检查点。
