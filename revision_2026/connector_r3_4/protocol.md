# 连接器 R3.4 完整改造与验收执行书

> 编制时间：2026-08-26 19:10 +08:00  
> 权威状态：用于接替旧 `connector_run.md` 中已被最新 R1 数据否定的步长语义  
> 目标机器：5080（`DESKTOP-9IUUGEO`）  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前源码：`revision_2026\connector_r3_4`  
> 当前结果：`revision_2026\connector_r3_4_results`  
> Python：`E:\anaconda\envs\pytorch_new\python.exe`，现场版本 Python 3.11.14  
> 当前状态：`STOPPED_AT_R1_SEMANTIC_GATE`  
> 授权边界：本文件是可执行任务书；只有用户随后明确要求“按 connector_fix.md 执行”时，才允许修改5080源码和启动实验  
> 终止原则：任一硬门失败，保存现场、更新工作记录和 `solutions.md`，将后续标为 `NOT_RUN`；不得临时放宽阈值或删除不利工况

## 0. 执行目标和完成定义

### 0.1 总目标

在不修改冻结 V1/R3 力律参数的前提下，完成以下闭环：

1. 修正 R3.4 结果包中“小于 2 μs 步”的语义和报告矛盾；
2. 实现能够区分常规步、事件对齐步、有限外层剩余步和浮点闭合量的事件积分器；
3. 用事件对齐固定步序列和独立 DOP853 参考证明单连接器数值可信；
4. 证明四点连接力真实进入四车和货物动力学，并满足作用反作用、力矩和完整内力一致性；
5. 在 100 m 分阶段、单移线、回头弯和定向激励中完成 V1/R3 × 固定步/事件步的公平比较；
6. 修通新植物到训练数据的唯一入口，完成因果特征、pilot 数据和正式数据验收；
7. 运行训练冒烟测试，交付 `READY_FOR_KOOPMAN_TRAINING` 证书。

### 0.2 “完成改动”的唯一判定

只有同时满足以下条件，状态才允许写为 `COMPLETE_READY_FOR_KOOPMAN_TRAINING`：

- S0--S9 全部 `PASS`；
- 源码、协议、配置、原始时序、自动摘要和图均有 SHA256 清单；
- R3.4 结果包内部不存在 `complete.json` 与 `stage_status.json` 相互矛盾；
- 单连接器、四车、完整内力和受力方向硬门全部通过；
- 选定力律和积分器已书面冻结；
- pilot 和正式数据仅来自新植物，因果索引、轨迹级切分和确定性重放通过；
- 固定线性和双线性训练冒烟无 NaN/Inf，模型保存/重载一致；
- R3.4 数据、模型和报告能够由工作记录中的命令重建。

若科学硬门失败但已保存完整失败证据与解决方案，状态应为 `BLOCKED_WITH_EVIDENCE`，不能写“完成”。

## 1. 最新事实和必须修正的前提

### 1.1 最新现场事实

| 对象 | 最新事实 | 来源 | 可信度 |
|---|---|---|---|
| R3.4阶段 | `STOPPED_AT_R1_SEMANTIC_GATE` | `connector_r3_4_results/stage_status.json` | 已复算 |
| 运行进程 | 无Python/MATLAB进程 | 5080现场进程表 | 已核对 |
| 磁盘 | D盘空闲约304.36 GiB | 5080现场 | 已核对 |
| R1参考复现 | 12个速度/力律组合与R3.3对应4个指标最大绝对差为0 | 两版CSV逐项复算 | 已复算 |
| 亚2 μs记录 | 66条：64条不大于`1e-12 s`，2条为有限外层剩余步 | R3.2表和R3.4逐步trace | 已复算 |
| Q95/R3 | `1.475339697 μs`外层剩余步包含一次平滑边界穿越 | `trace_q95_phase12_R3.csv` | 已复算 |
| V1/stress0.25 | `1.443448476 μs`外层剩余步不含事件穿越 | `trace_stress_0p25_phase22_V1.csv` | 已复算 |
| 报告矛盾 | CSV仍写`TRUE_EVENT_NEIGHBOR`，`complete.json`写`passed=true`，阶段状态却正确停止 | R3.4结果包 | 已核对 |
| 源码进度 | `event_substep.py`、`four_vehicle_common.py`、`step_features.py`、`steering_allocator.py`、`internal_force.py`和`run.py`与R3.3哈希相同 | SHA256逐文件比较 | 已核对 |
| R3.4协议 | `protocol.md`与R3.3哈希相同；本方案尚未同步到5080 | SHA256 `08B239...B1B19` | 已核对 |
| 数据/模型/MPC | R3.4三个目录均为空 | 5080目录 | 已核对 |

### 1.2 不能继续沿用的错误前提

1. 不能仅凭 `dt < 2 μs` 判断“事件对齐步”。
2. 不能把两条有限小步都说成“与事件无关”：Q95/R3 的步由外层余量选出，但确实跨过平滑事件。
3. 不能把事件对齐步小于 2 μs 自动判为数值失败。事件根可以因任意外层网格相位落在很近的位置；应允许真实事件落点微步，并单独审计。
4. 只有当“常规平滑区分辨率”主动要求小于 `2 μs` 时，才说明最小常规步不足。
5. 不能直接运行旧 `control_source_generate_k2.py`：它仍导入旧 `four_vehicle_coupled` 和固定步 RK4。
6. 不能直接使用当前 `step_features.py`：其区间均值、占比、最小值和最大值实际是端点量。

### 1.3 模型边界

当前是平面 30 状态模型。连接点输出是地面平面内的纵向 `Fx` 和横向 `Fy`，不是重力方向真实竖向 `Fz`。本轮不增加悬架、俯仰、侧倾或竖向结构力；报告中统一使用“纵向/横向”。若审稿人要求真实 `Fz`，必须另立3D模型任务，不能用本结果替代。

## 2. 允许修改和禁止修改

### 2.1 允许修改

- R3.4隔离目录中的协议、事件积分器、审计数据结构、参考积分器、测试、四车接线、内力诊断、转向分配导入、数据特征、数据生成入口、绘图和报告脚本；
- R3.4结果、数据、模型和MPC空目录；
- R3.4持续追加的 `work_log.md` 和 `solutions.md`。

### 2.2 禁止修改

- R3.3及更早源码和结果；
- 冻结力律参数：`k=30000 N/m`、`c=3500 N·s/m`、`l0=0.002 m`、`delta_s=0.0001776170305060031 m`；
- V1/R3力律代数，除非本任务在某硬门失败后停止并另立新版本；
- 历史训练数据、模型和MPC结果；
- 已产生的R3.4 R1失败证据。语义修正必须写入新子目录 `r1_1`，不能覆盖 `r1`。

### 2.3 结果目录

```text
revision_2026/connector_r3_4_results/
├─ r0/
├─ r1/                    # 已有，只读
├─ r1_1/                  # 新语义修正
├─ n1/
├─ n2a/
├─ n2/
├─ n3/
├─ n4/
├─ n5/
├─ data_audit/
├─ figures/
├─ figure_data/
├─ audit_history/
├─ stage_status.json
├─ report.md
├─ solutions.md
├─ work_log.md
└─ artifact_manifest.json
```

## 3. 公式和审计语义

### 3.1 R3连接力

对第 `i` 个连接点：

\[
d_i=p_i^v-p_i^p,\qquad
v_i=\dot p_i^v-\dot p_i^p,
\]

\[
n_i=\frac{d_i}{\max(\lVert d_i\rVert,\epsilon)},\qquad
q_i=\lVert d_i\rVert-l_0,\qquad
\delta_i=\max(q_i,0),\qquad
v_{n,i}=v_i^Tn_i.
\]

令 `s=clip(delta_i/delta_s,0,1)`：

\[
g(\delta_i)=
\begin{cases}
0,&\delta_i\le0,\\
3s^2-2s^3,&0<\delta_i<\delta_s,\\
1,&\delta_i\ge\delta_s.
\end{cases}
\]

\[
f_i=k\delta_i+c\,g(\delta_i)\max(v_{n,i},0),
\qquad
F_i^p=f_in_i,\qquad
F_i^v=-F_i^p.
\]

`max(v_n,0)` 表示阻尼只在加载阶段生效，是当前单边连接器假设，不是实物材料辨识结论。

### 3.2 三个正交步长字段

每个已接受时间段不能只存一个含混的 `step_class`，必须同时存：

#### A. `dt_class`：只描述大小

- `REGULAR_DT`：`dt >= 2 μs`；
- `FINITE_SUBMINIMUM_DT`：`1e-12 s < dt < 2 μs`，真实推进状态；
- `FLOATING_CLOSURE`：`0 < dt <= 1e-12 s`，不推进状态。

#### B. `selection_cause`：描述为什么选择该步

- `PROBE_LIMIT`；
- `ZONE_RESOLUTION`；
- `EVENT_ROOT`；
- `OUTER_REMAINDER`；
- `FIXED_REFERENCE`。

#### C. `event_relation`：描述该段和事件的关系

- `NO_EVENT`；
- `CONTAINS_EVENT`；
- `ENDS_AT_EVENT`；
- `STARTS_AT_EVENT`；
- `SIMULTANEOUS_EVENT_GROUP`。

另存 `candidate_origin`。例如Q95/R3修正后：

1. 原候选来自 `OUTER_REMAINDER`；
2. 候选内发现平滑事件根；
3. 首段约 `0.824475724 μs`，`selection_cause=EVENT_ROOT`、`candidate_origin=OUTER_REMAINDER`、`ENDS_AT_EVENT`；
4. 根后约 `0.650863973 μs`，`selection_cause=OUTER_REMAINDER`。

V1/stress0.25则保持一个 `1.443448476 μs` 的有限外层剩余步，`NO_EVENT`。

### 3.3 时间守恒

每个外部周期 `H` 必须满足：

\[
H=\sum_j h_j^{advanced}+r_{floating},
\qquad
\left|H-\sum_j h_j^{advanced}-r_{floating}\right|\le10^{-12}\ {\rm s}.
\]

`FLOATING_CLOSURE` 不更新状态、不积分冲量、不计入最小物理步；有限外层剩余步和事件对齐步必须真实推进并计入冲量与计算成本。

### 3.4 何时判定分辨率不足

平滑区穿越时间：

\[
\tau_s=\frac{\delta_s}{\max(|v_n|,\epsilon)}.
\]

常规区间目标步长：

\[
h_{zone}=\frac{\delta_s}{N_{zone}\max(|v_n|,\epsilon)},\qquad N_{zone}=8.
\]

只有 `h_zone < 2 μs` 时触发 `UNRESOLVED_ZONE_RESOLUTION`。事件根落点或外层余量小于2 μs本身不触发失败，但必须满足事件残差和参考误差门。

### 3.5 力矩、系统横摆和完整内力

\[
M_{z,i}=r_{x,i}F_{y,i}-r_{y,i}F_{x,i}.
\]

货物姿态 `psi_p/r_p` 作为四车阵列虚拟底盘的系统横摆角/横摆角速度；四车 `psi_i/r_i` 分别报告。禁止用四车横摆角简单平均值替代系统动力学。

将四点货物体坐标力堆叠为 `f`：

\[
w=Wf=[F_x,F_y,M_z]^T,
\qquad
f_{motion}=W^\dagger w,
\qquad
f_{int}=(I-W^\dagger W)f.
\]

硬门：

\[
\lVert Wf_{int}\rVert
<10^{-8}\max(1\ {\rm N},\lVert f_{int}\rVert).
\]

定义货物纵向/横向拉伸载荷代理：

\[
T_x=\frac12\max\left(0,(F_F-F_R)^Te_x\right),
\qquad
T_y=\frac12\max\left(0,(F_L-F_{Rt})^Te_y\right).
\]

它们单位为N，只是内部拉伸趋势，不是材料撕裂判据。代码和中文报告禁止继续使用含混字段 `opening`。

## 4. 源码修改清单

| 文件 | 函数/类 | 修改内容 | 输入 | 输出 | 必须测试 |
|---|---|---|---|---|---|
| `protocol.md` | 全文 | 用本执行书同步并冻结；记录修订原因 | 本MD | 远程协议SHA256 | 与本地交付哈希一致 |
| `scripts/freeze_r34.py` | 新增 | 保存环境、R3.3基线、当前源码和协议清单 | 项目根 | `r0/*.json` | 清单逐文件复核 |
| `scripts/diagnose_r1_semantics.py` | 新增 | 不覆盖R1；生成三字段语义分类 | R1原始CSV/trace | `r1_1/*` | 64/2分类和Q95事件关系 |
| `src/event_substep.py` | `StepAuditV2`/`StepRecord` | 新增三字段、candidate_origin、事件组、时间守恒 | 每个子步 | 可序列化审计 | JSON/CSV round-trip |
| `src/event_substep.py` | `_next_scalar_step` | 先定候选，再查最早事件；允许亚2 μs事件落点 | 标量状态/余量 | dt和步记录 | Q95/V1构造例 |
| `src/event_substep.py` | `integrate` | 根处分段；有限外层余量真实推进；闭合量不推进 | 标量工况 | 原始trace/metrics | 时间、冲量、事件计数 |
| `src/event_substep.py` | `advance_outer_step` | 四点最早事件和同时事件真实分段 | state30/control | state30/StepAuditV2 | 2点/4点同时事件 |
| `src/reference_oracle.py` | 新增 | 事件分段DOP853；连续峰值和容差减半 | 力律/初态 | oracle trace/metric | 解析振子/事件面 |
| `tests/test_step_semantics.py` | 新增 | 四种步长语义和Q95重放 | 构造工况 | pytest | 见S2 |
| `tests/test_reference_oracle.py` | 新增 | oracle自收敛和事件重启 | 解析工况 | pytest | 容差减半 |
| `src/four_vehicle_common.py` | `connector_diagnostics` | 输出世界/货物体/车辆体力、方向、左右/前后组合、完整内力 | state30/law | 完整诊断 | 坐标、镜像、零力 |
| `src/four_vehicle_common.py` | `system_derivative` | 差分证明连接力进入每车和货物`vx/vy/r`导数 | state/control | dx30 | 单点力注入 |
| `src/internal_force.py` | 内力函数 | 增加`T_x/T_y`和字段重命名，保留完整零空间 | 四点力 | 内力向量/代理 | 纯合力/力矩/内力 |
| `src/steering_allocator.py` | imports/allocator | 改为导入R3.4 `four_vehicle_common`；禁止旧植物 | state/虚拟4WS | 4×2控制 | 直线/左右镜像/ICR |
| `src/paired_maneuvers_r3.py` | 全部 | 实现100m、单移线、回头弯、定向激励 | 冻结配置 | 控制序列 | 阶段时钟/距离 |
| `src/spectral_metrics.py` | 全部 | Welch、跳变量、Parseval、冲量/RMS | 2ms时序 | 指标 | 正弦/白噪声解析例 |
| `src/step_features.py` | `aggregate_step_audit` | 用真实dt聚合，不用端点冒充均值 | 10个2ms审计 | 20ms因果特征 | 常量/单事件/变步 |
| `src/schema_r3.py` | schema | 名称、单位、坐标、采样时刻、输入/标签权限、版本ID | 配置 | `schema.json` | 维数和唯一名 |
| `scripts/run.py` | S0--S7入口 | 严格前置门；失败即退出2并更新状态 | stage | 原始结果 | 前置门拒绝 |
| `scripts/build_pilot.py` | 实现 | 只调用R3.4事件植物 | 场景/种子 | pilot数据 | 无旧import |
| `scripts/generate_data.py` | 新增 | 正式数据唯一入口 | 冻结配置 | NPZ/manifest | 轨迹级切分 |
| `scripts/verify_data.py` | 新增 | 因果、覆盖、确定性、哈希审计 | 数据目录 | data report | 未来事件泄漏 |
| `scripts/train_smoke.py` | 新增 | fixed linear和bilinear冒烟 | 冻结数据 | 模型/日志 | 保存重载一致 |
| `scripts/plot_evidence.py` | 扩展 | 从原始数据生成全部验收图和figure_data | NPZ/CSV | PNG/CSV | 数值回读 |
| `scripts/finalize_report.py` | 扩展 | 一致状态、失败方案、自包含清单 | 所有阶段 | report/status/manifest | 独立verify |

## 5. 总任务树

```text
S0 证据合同、协议和版本冻结
└─ FAIL → E001/E002，后续NOT_RUN

S1 R1.1步长语义修正
└─ FAIL → E003，后续NOT_RUN

S2 事件积分器改造与单元测试
└─ FAIL → E004--E007，后续NOT_RUN

S3 N1事件检测和静态物理回归
└─ FAIL → E008/E009，后续NOT_RUN

S4 N2A-v2参考与独立oracle证书
└─ FAIL → E010--E012，后续NOT_RUN
   └─ PASS后第一次强制人工复核

S5 N2 768行单连接器四因素回归
└─ FAIL → E013，后续NOT_RUN

S6 N3四车收敛、守恒和力接线
└─ FAIL → E014--E017，后续NOT_RUN

S7 N4/N5完整工况与V1/R3公平比较
└─ FAIL → E018--E022，禁止数据生成

S8 数据入口、特征和因果单元测试
└─ FAIL → E023--E026，禁止pilot

S9 pilot、正式数据和训练冒烟
└─ FAIL → E027--E031，停止在数据/学习层

S10 报告、图、清单和训练就绪证书
└─ FAIL → E032，不得标记完成
```

## 6. 分阶段可执行说明

### S0：证据合同、协议和冻结

#### 前置条件

- 用户明确授权执行；
- 无其他Python/MATLAB任务占用同一结果目录；
- R3.3保持只读。

#### 操作

1. 保存当前R3.4源码哈希和R1结果哈希；
2. 把本地 `D:\PDxc\Review\connector_fix.md` 复制为远程 `connector_r3_4\protocol.md`；
3. 保存环境版本、CPU/GPU、磁盘、进程和时区；
4. 保存R3.3基线26项清单复核结果；
5. 生成 `r0/environment.json`、`r0/source_manifest_prechange.json`、`r0/baseline_manifest.json`；
6. 将现有R1结果标记只读输入，不改文件内容。

#### 硬门

- 协议本地/远程SHA256一致；
- R3.3清单全部匹配；
- Python可导入NumPy、SciPy、PyTorch；
- D盘空闲`>=50 GiB`；
- 没有无法解释的源码漂移。

#### 失败

保存现场清单，状态 `BLOCKED_S0_IDENTITY`；禁止修改积分器。

### S1：R1.1语义修正

#### 输入

- `r1/sub2us_classification.csv`；
- 两条逐步trace；
- R3.2单连接器原表；
- R3.3参考对。

#### 操作

新增 `scripts/diagnose_r1_semantics.py`，生成：

- `r1_1/sub2us_semantics.csv`；
- `r1_1/q95_event_split.json`；
- `r1_1/summary.json`；
- `r1_1/complete.json`。

分类必须为：

- 64条`FLOATING_CLOSURE`；
- 2条`FINITE_SUBMINIMUM_DT + OUTER_REMAINDER`；
- Q95/R3：`CONTAINS_EVENT=smoothing`；
- V1/stress0.25：`NO_EVENT`；
- 历史12对参考指标最大绝对差保持0。

#### 硬门

- `complete.json.passed`、`stage_status.json`和CSV语义一致；
- Q95根时间通过原事件检测器复算，残差`<=1e-8 m`；
- 所有数字能追溯到原始行。

#### 通过后

状态 `PASS_S1_SEMANTICS`，进入S2。

#### 失败

状态 `BLOCKED_S1_SEMANTICS`，输出字段冲突和最小复现；不能根据人工文字强制PASS。

### S2：事件积分器改造

#### 核心算法

每个循环：

1. 计算外层 `remaining`；
2. 若 `remaining<=closure_tol`，登记浮点闭合并结束；
3. 计算探测/区域候选步和 `candidate_origin`；
4. 用起点、中点、终点检查 contact/smoothing 两事件面；
5. 对所有穿越做根定位，选择最早根并合并同时事件；
6. 有根时积分到根，登记 `EVENT_ROOT`；无根时按候选推进；
7. 根后重新计算剩余量，不复用根前导数；
8. 更新冲量、能量、峰值、事件、时间守恒和步记录；
9. 若常规 `h_zone<2 μs`，停止为 `UNRESOLVED_ZONE_RESOLUTION`；
10. 检查事件释放锁，防止同一事件面零时间重复触发。

#### 必须通过的单元测试

1. `test_floating_closure_no_state_advance`；
2. `test_v1_outer_remainder_1p443us_no_event`；
3. `test_q95_outer_remainder_splits_at_smoothing_root`；
4. `test_sub2us_event_alignment_is_allowed_and_logged`；
5. `test_zone_resolution_below_2us_fails`；
6. `test_time_conservation_each_outer_step`；
7. `test_no_duplicate_endpoint_event`；
8. `test_two_and_four_simultaneous_events`；
9. `test_double_crossing_detected`；
10. `test_scalar_and_vehicle_audit_schema_equal`。

#### 修正前后回归

重放两条轨迹，保存修正前/后：

- 峰值力、冲量、末状态、事件时刻；
- 绝对差和相对差；
- 步分类和运行时间。

不要求修正后与旧结果达到`1e-10`等价，因为Q95真实分段会改变数值轨迹；改用S4的独立oracle判断新结果是否更准确。

#### 硬门

- 10项测试全PASS；
- 无死循环、NaN/Inf、零时间重复根；
- 时间守恒通过；
- Q95被拆为事件根段和根后余量；
- V1有限外层余量真实推进。

### S3：N1和静态物理回归

运行全部测试，不只运行新文件：

- 解析事件时间误差`<=1 μs`；
- 事件面残差`<=1e-8 m`；
- 同时2点/4点、双穿越、端点一次、无假事件、确定性全部PASS；
- R3力律非负、连续性和能量方向测试PASS；
- 作用反作用静态残差`<1e-12 N`；
- 不改变V1/R3参数哈希。

任何历史测试退化都必须停止，不能以“新语义更合理”为理由跳过。

### S4：N2A-v2参考证书

#### 实验矩阵

```text
速度：Q05/Q50/Q95/Q99/0.25/1.0 m/s
力律：V1/R3
事件对齐固定步：2/1/0.5/0.25 μs
DOP853 oracle：主容差 + 4倍收紧确认
固定步运行：48
oracle运行：24
```

#### DOP853设置

- 每个contact/smoothing事件处终止并重启；
- 主容差：`rtol=1e-11`；
- 状态绝对容差：位移`1e-13 m`、速度`1e-11 m/s`；
- 确认容差：主容差和绝对容差各除以4；
- 峰值使用DOP853 dense output先粗查，再在包围区间做有界一维极值；
- 冲量作为增广状态积分，不用事后低采样率梯形积分。

#### 指标

\[
D_h(M)=\frac{|M_h-M_{h/2}|}{S_M},
\qquad
p_{obs}=\log_2\frac{D_h}{D_{h/2}}.
\]

尺度：

- 峰值：`max(|F_oracle|,50 N)`；
- 冲量：`max(|J_oracle|,50 N*T_ref)`；
- 末状态：位移/速度物理尺度化。

#### 硬门

1. 两档oracle：
   - 峰值差`<=0.05%`；
   - 冲量差`<=0.02%`；
   - 末状态差`<=0.01%`。
2. `0.5 μs`固定步对确认oracle：
   - 峰值`<=0.5%`；
   - 冲量`<=0.2%`；
   - 末状态`<=0.1%`。
3. 未进入`D<=1e-10`数值地板的冲量和末状态：
   - 最后两级差异单调下降；
   - `p_obs>=0.9`。
4. 连续极值峰值满足预算；原始采样最大值保留为采样相位诊断，不再用精确`0.5`比例作为唯一主门。
5. 事件残差、时间守恒和有限性全部PASS。

这些门在运行前冻结。若失败，禁止根据失败结果改为更宽阈值。

#### 第一次强制停止

S4结束后无论PASS/FAIL都停止自动任务，人工核对：

- 两档oracle是否自洽；
- V1事件重启是否正确；
- Q95连续峰值是否解释采样非单调；
- 步长语义是否无矛盾；
- 主要门是否未被修改。

只有人工放行才进入S5。

### S5：N2 768行回归

矩阵：

```text
6速度 × 32接触相位 × 2力律 × 2积分器 = 768
因素：V1-F2 / V1-ES / R3-F2 / R3-ES
```

公平性：

- 相同初态、持续时间和相位；
- 每个力律与自己的确认oracle比较；
- 固定步不使用事件信息；
- 事件步使用S2冻结积分器；
- 不删除最坏相位。

硬门：

- ES峰值误差`<=5%`；
- ES冲量误差`<=2%`；
- ES末状态`<=1%`；
- 接触时刻误差`<=2 μs`；
- R3每次平滑穿越至少8个有效区间，事件落点段单列；
- 无负拉力、NaN/Inf、静默裁剪或15 kN越界；
- 同时报均值、P95/P99、最坏相位、步数和运行时间。

### S6：N3四车收敛和物理接线

#### 工况

1. 历史G3 2 s正反转向；
2. 冻结Q99四点接触覆盖工况。

#### 每工况运行

```text
V1-F2, V1-ES, R3-F2, R3-ES，外层2 ms
V1/R3 ES，外层1 ms和0.5 ms
V1/R3确认参考：2 ms记录块内最大常规步0.1 ms + 事件根分段
```

20 ms控制命令必须在10个2 ms外步内保持，不因参考更细而提高控制更新频率。

#### 力真实进入动力学的差分验收

对同一状态和控制：

1. 正常连接力计算 `dx_force`；
2. 将连接力仅在动力学入口置零，计算 `dx_zero`；
3. 验证每辆车和货物的`vx/vy/r`导数按力和力矩公式变化；
4. 诊断数组仍保留，证明差异来自动力学入口而不是绘图。

#### 硬门

- 四点峰值误差`<=5%`；
- 四点冲量误差`<=2%`；
- 末状态尺度化误差`<=1%`；
- 完整内力、货物合力矩和每车连接力矩误差`<=5%`；
- 每点作用反作用残差`<1e-10 N`；
- 内力零空间残差通过第3.5节；
- 所有连接点都通过动力学差分接线测试；
- 无NaN/Inf、15 kN停止、事件死循环和力裁剪。

### S7：N4/N5完整工况

#### S7.1 100 m分阶段工况

以货物质心累计路程 `s_p` 切换：

| 阶段 | 条件 | 纵向命令 | 虚拟4WS命令 |
|---|---|---|---|
| A加速 | `0<=s_p<30 m` | 初速`2.0 m/s`，`a=+0.40 m/s²` | `0°/0°` |
| B正向阶跃 | 从30 m起5.00 s | 锁定30 m处实际速度`v30` | 前/后`+4°/-2°` |
| C反向阶跃 | 随后5.00 s | 继续锁定`v30` | 前/后`-4°/+2°` |
| D减速 | 剩余路段至100 m | 目标`0.7 m/s`；按D段起点实测速度和剩余距离计算减速度 | `0°/0°` |

D段开始时以实测 `v_D` 和 `s_D` 计算前馈减速度：

\[
a_D=\frac{0.7^2-v_D^2}{2(100-s_D)}.
\]

若 `a_D` 不在既有控制范围 `[-1.4,0) m/s²` 内，说明前面阶段和100 m终点约束不可同时满足，工况在启动长仿真前即判配置FAIL；不得把 `a_D` 静默裁剪后仍声称满足100 m减速合同。D段可叠加小幅速度反馈，但前馈值、反馈值和最终施加值必须分别保存。

硬门：

- 终点`100.00±0.05 m`；
- 正/反阶跃各`5.00±0.02 s`；
- 匀速段P95速度误差`<=max(0.10 m/s,0.03*v30)`；
- 终点速度`0.7±0.2 m/s`；
- ICR几何法向残差`<=1e-8 m/s`；
- 无未登记转角裁剪；转角饱和时间比例必须为0；
- 四点力、横摆、内力和事件全部保存。

#### S7.2 其他工况

- 单移线：左右镜像各5个冻结种子；
- 回头弯：左右镜像各5个冻结种子，含入弯、持续弯道、出弯；
- 连接器定向激励：前后、左右、两条对角四种零和小激励；
- 直线匀速：用于高频噪声底和无事件基线。

每个配对实验共用初态、参数、控制和种子。

#### S7.3 必报量

- 四点世界系和货物体坐标`Fx/Fy`；
- 力方向角；`||F||<50 N`记`INACTIVE`；
- 四车`psi_i/r_i`和货物/系统`psi_p/r_p`；
- 货物左右/前后侧合力、合力矩；
- 完整`f_int`、`T_x/T_y`；
- 接触/平滑事件、步长类型、冲量、能量和计算成本；
- 正阶跃开始、正反切换、反阶跃结束各±1 s放大窗。

#### S7.4 平滑指标

2 ms共同采样网格，Welch设置：

- Hann窗；
- `nperseg=min(1024,不超过样本数的最大2次幂)`；
- 50%重叠；
- 去均值；
- 高频带`>25 Hz`；
- Parseval相对误差`<=1%`。

同时报告最大/P95/P99力跳、高频绝对能量、高频占比、RMS和冲量，防止把“力变小”误写成“更平滑”。

#### S7.5 力律与积分器归因

- 积分器主效应：同一力律F2对ES；
- 力律主效应：同一ES下V1对R3；
- 交互作用：比较力律收益是否依赖积分器。

物理可用硬门：所有轨迹完成、守恒通过、无15 kN停止、无异常转向裁剪。

论文“R3更平滑”研究目标：

- 配对轨迹的事件窗P99力跳和高频绝对能量中位改善`>=10%`；
- 轨迹级bootstrap 95%区间下界`>0`；
- 任一注册场景的冲量、轨迹误差或`T_x/T_y` P95不得退化超过`5%`。

若物理硬门通过但R3优势门失败，状态为`PASS_PHYSICS_NO_R3_ADVANTAGE`，必须停止选择植物：

- 选择V1-ES：可快速生成可信数据，但不能写R3创新；
- 保留R3-ES：只能写数值可用，不能写物理优势；
- 若坚持改力律：另立R3.5，不允许在R3.4内继续调参。

### S8：数据入口、特征和因果

#### 唯一入口

`generate_data.py`只能导入R3.4：

```text
src/four_vehicle_common.py
src/event_substep.py
src/steering_allocator.py
src/step_features.py
src/schema_r3.py
```

静态测试发现 `four_vehicle_coupled`、旧 `ConnectorParams` 或直接固定步 `rk4_step` 推进时必须FAIL。

#### 时钟

```text
20 ms控制保持
└─ 10 × 2 ms外部植物审计
   └─ 每个2 ms外步内部使用事件积分
```

#### 特征聚合

\[
\bar F_k=\frac{1}{T_c}\sum_jF_{mid,j}\Delta t_j,\qquad
J_k=\sum_jF_{mid,j}\Delta t_j,
\]

\[
c_k=\frac1{T_c}\sum_j\mathbb{1}_{contact}\Delta t_j.
\]

`g_mean`按时间加权；`g_min/g_max`、`delta_min/max`取全部子步真实极值；禁止硬除以`0.002`或用端点布尔量冒充区间占比。

#### 因果索引

区间 `(t_{k-1},t_k]` 的已完成事件特征记作 `e_k`：

\[
(x_k,u_k,e_k)\rightarrow x_{k+1}.
\]

禁止使用 `(t_k,t_{k+1}]` 内才知道的 `e_{k+1}`。必须用人为未来事件测试证明当前输入不变化。

#### 数据契约

- `S1_team`：12维，仅作低信息基线；
- `S2_four`：30维完整状态；
- `S3_deform`：46维，30状态+8位移+8相对速度；
- `S4_force_event`：在S3上增加四点力、完整内力和因果事件；维数由schema自动计算；
- 主控制：四车实际8维；
- 系统等效2维和分配器13维仅作消融；
- 每字段记录名称、单位、坐标、时刻、输入/标签权限。

### S9：pilot、正式数据和训练冒烟

#### pilot

- 清洁场景：100m、单移线、回头弯、定向激励，每场景2条，共8条；
- 网络场景仅生成2条接口检查，不混入第一版清洁训练；
- 固定种子，按完整轨迹切分；
- 相同种子至少重放1条验证确定性。

pilot硬门：

- 数组有限、时间单调、长度合同正确；
- `plant_id/law_id/integrator_id/schema_id`完整；
- 没有旧植物import；
- 因果测试PASS；
- 100m阶段合同PASS；
- 所有清洁场景覆盖注册事件；
- 原始轮胎利用率和饱和标志均保存；
- 无15 kN停止；
- 原始NPZ可重绘全部验收图。

#### 正式数据

pilot通过后冻结 `data_config.json`：

- 每个4个清洁场景20条，共80条；
- 参数外推20条，完全独立；
- 每场景轨迹ID 0--13训练、14--16验证、17--19测试；
- external不参与归一化、调参或模型选择；
- 窗口不得跨轨迹；
- 归一化统计只来自训练轨迹。

若覆盖报告显示某个事件/内力模态缺失，增加物理轨迹而不是增加重叠窗口。

#### 训练冒烟

只验证“数据能被正确训练”，不宣称Koopman创新：

1. fixed linear闭式/统一训练入口；
2. bilinear小预算训练，固定种子1个；
3. 检查前向、反向、梯度、保存、重载、1/5/10/20步滚动；
4. 所有损失、参数和预测有限；
5. 重载后同一批次输出最大绝对差`<=1e-7`；
6. 记录参数量、训练时间和推理时间。

训练冒烟通过后写 `READY_FOR_KOOPMAN_TRAINING.json`。完整fixed linear、可训练lift、bilinear、三专家和组合候选比较另按Koopman实验书执行。

### S10：报告、图和清单

必须生成：

1. 四级参考/oracle收敛图；
2. 三字段步长语义分布；
3. Q95事件根拆分放大图；
4. 100m距离、速度、加速度和转向阶段；
5. 四点`Fx/Fy`和关键时刻力箭头；
6. 四车与系统横摆；
7. 货物合力/合力矩、完整内力、`T_x/T_y`；
8. 力跳、Welch、冲量、RMS四因素对比；
9. 数据场景、事件、形变、力和轮胎利用率覆盖；
10. 冒烟训练1/5/10/20步图。

每张PNG必须有 `figure_data/*.csv`、单位、采样率、生成脚本和源NPZ。最终运行独立 `verify_manifest.py`；报告生成后再生成清单，清单不包含自身哈希循环。

## 7. 失败编号和恢复方案

| 编号 | 失败 | 立即动作 | 推荐修复 | 重新进入门 |
|---|---|---|---|---|
| E001 | 基线哈希漂移 | 保存diff并停 | 查明来源，重新冻结新版本 | S0全PASS |
| E002 | 环境/依赖缺失 | 保存版本和导入错误 | 使用现有环境修复；不临时联网安装 | 环境清单PASS |
| E003 | R1.1分类仍矛盾 | 保存CSV/JSON | 三字段从原始trace计算，禁止按dt猜事件 | S1一致 |
| E004 | 事件零时间循环 | 保存事件面和调用栈 | 释放锁+事件ID去重 | N1端点测试PASS |
| E005 | 同时事件漏记 | 保存四点根时间 | 最早根排序+容差分组 | 2/4点测试PASS |
| E006 | Q95未在根处分段 | 保存起中终事件面 | 根定位后重启积分 | 根残差PASS |
| E007 | 有限余量被合并 | 保存时间账本 | 单独真实推进 | 时间守恒PASS |
| E008 | N1解析门失败 | 后续停 | 修根定位，不放宽1 μs/1e-8 m | N1 PASS |
| E009 | 力律/参数哈希变化 | 后续停 | 回退非授权力律改动 | 哈希恢复 |
| E010 | DOP853两档不一致 | 保存两档trace | 更细容差/分段检查；不得直接选一档 | oracle预算PASS |
| E011 | 仅采样峰值不收敛 | 保存峰值邻域 | 连续极值诊断；原峰值仍保留 | 连续峰值+oraclePASS |
| E012 | 冲量/末状态阶不足 | 保存4级序列 | 检查事件重启和冲量增广状态 | S4全部PASS |
| E013 | N2最坏相位失败 | 保存该相位完整trace | 最小复现，不删相位 | N2原门PASS |
| E014 | 作用反作用失败 | 保存世界/体坐标力 | 修符号和旋转 | `<1e-10 N` |
| E015 | 力矩失败 | 保存力臂和逐点力矩 | 构造纯力矩单测 | N3门PASS |
| E016 | 内力零空间失败 | 保存W/SVD/残差 | 修点序和坐标 | 零空间门PASS |
| E017 | 连接力未进入状态导数 | 保存dx差分 | 修`system_derivative`接线 | 六导数通道PASS |
| E018 | Ackermann/ICR异常 | 保存转角、ICR、裁剪 | 修旧import/分配器，不怪连接器 | 镜像/ICR门PASS |
| E019 | 超过15 kN | 保存原始轨迹/控制 | 检查工况、参数、分配；禁止截断 | 修复版本重验 |
| E020 | 100m合同失败 | 保存距离和阶段时间 | 修距离触发/速度锁定 | 阶段门PASS |
| E021 | R3无平滑优势 | 保留公平结果 | 选V1-ES或停止R3创新；不调参硬过 | 植物书面冻结 |
| E022 | 某工况退化>5% | 保留最坏轨迹 | 说明适用区或另立R3.5 | 新预注册通过 |
| E023 | 数据导入旧植物 | 停止生成 | 静态拒绝测试+唯一入口 | import门PASS |
| E024 | 区间统计仍是端点 | 保存解析例 | 真实dt加权聚合 | 聚合单测PASS |
| E025 | 未来事件泄漏 | 删除未冻结pilot并停 | 修`e_k`索引 | 因果测试PASS |
| E026 | schema单位/维数错 | 保存字段diff | schema生成而非手写维数 | schema门PASS |
| E027 | pilot NaN/Inf/15kN | 保存首个失败轨迹 | 回到相应物理层 | 对应层PASS |
| E028 | pilot覆盖不足 | 保存覆盖图 | 增加物理轨迹，不堆窗口 | 覆盖门PASS |
| E029 | 100m运行过慢 | 完成当前代表轨迹后停 | 分析事件步成本，不降采样 | 资源方案获批 |
| E030 | 冒烟训练NaN | 保存batch/归一化/梯度 | 查数据尺度和损失，不换测试集 | 冒烟PASS |
| E031 | 模型重载不一致 | 保存checkpoint/版本 | 修随机层和序列化 | `<=1e-7` |
| E032 | 报告与原始数据不一致 | 标记报告无效 | 从原始数据重算并重绘 | 清单复核PASS |

每次失败的 `solutions.md` 必须包含：已确认事实、根因候选、反证、最小诊断、方案成本/风险和重新进入门。不能只写“跑不动”。

## 8. 执行命令顺序

以下命令在源码按本书完成后使用；每条命令和退出码立即写工作记录：

```powershell
$taskPython = 'E:\anaconda\envs\pytorch_new\python.exe'
$taskRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$taskR34 = Join-Path $taskRoot 'revision_2026\connector_r3_4'

& $taskPython "$taskR34\scripts\freeze_r34.py" --project-root $taskRoot
& $taskPython "$taskR34\scripts\diagnose_r1_semantics.py" --project-root $taskRoot
& $taskPython -m pytest "$taskR34\tests" -q
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N1
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N2A

# S4后强制停止，独立复核通过才继续
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N2
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N3
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N4
& $taskPython "$taskR34\scripts\run.py" --project-root $taskRoot --stage N5

& $taskPython "$taskR34\scripts\build_pilot.py" --project-root $taskRoot --per-scenario 2
& $taskPython "$taskR34\scripts\verify_data.py" --project-root $taskRoot --dataset pilot
& $taskPython "$taskR34\scripts\generate_data.py" --project-root $taskRoot --config "$taskR34\configs\data_full.json"
& $taskPython "$taskR34\scripts\verify_data.py" --project-root $taskRoot --dataset full
& $taskPython "$taskR34\scripts\train_smoke.py" --project-root $taskRoot

& $taskPython "$taskR34\scripts\plot_evidence.py" --project-root $taskRoot
& $taskPython "$taskR34\scripts\finalize_report.py" --project-root $taskRoot
& $taskPython "$taskR34\scripts\verify_manifest.py" --project-root $taskRoot
```

如果某命令退出码非0，后续命令不得继续。

## 9. 资源和运行策略

- S0--S3：预计低成本，逐项前台运行；
- S4：先跑一个Q05和一个Q95计时，再估算全部72次参考；
- S5：先跑一个速度的64相位子矩阵估时；
- S6：先跑Q99一个力律候选；
- S7：先跑100m一个种子；
- S9：先pilot，再正式数据。

任一阶段估算总耗时超过4 h或新增输出超过5 GB时，完成当前代表病例后停止，报告成本。不得通过删除场景、减少原始字段或降低采样率绕过。

仿真默认CPU；训练冒烟才使用GPU。不得终止其他任务进程，除非用户明确确认PID属于本任务。

## 10. 工作记录模板

每完成一个任务节点立即追加：

```markdown
## R34-XXX — YYYY-MM-DD HH:mm — 任务标题

- 请求/任务编号：
- 授权模式：执行实验
- 机器与项目根目录：
- 协议SHA256：
- 基线源码/数据SHA256：
- 读取：
- 修改文件与函数：
- 运行命令：
- 退出码与运行时间：
- 配置/种子：
- 原始产物：
- 关键指标、单位和样本范围：
- 自动摘要复算：
- 结论类型：事实 / 推断 / 建议 / 未知
- 状态：PASS / PARTIAL / BLOCKED / NOT_RUN
- 停止原因：
- 下一允许动作：
```

计划任务不能提前记成完成。失败源码、失败轨迹和失败图写入 `audit_history`，不得覆盖。

## 11. 论文可写结论边界

| 最后通过阶段 | 可写结论 |
|---|---|
| S1 | 修正了事件步、外层余量和浮点闭合的语义 |
| S4 | 单连接器事件积分通过独立参考和收敛证书 |
| S6 | 四车代表工况满足数值、作用反作用、力矩和内力一致性 |
| S7物理门 | 新植物在注册完整工况可用 |
| S7优势门 | 才可写R3相对V1的平滑/受力改善 |
| S9数据门 | 新植物数据链通过因果和覆盖验收 |
| S9冒烟 | 数据可进入正式Koopman比较 |

无论通过哪一层，都不能写“货物不会撕裂”或“15 kN是实物破断极限”。没有材料、连接区结构、疲劳曲线和实测力时，只能写“仿真货物拉伸载荷代理”。

## 12. 最终交付清单

完成时必须交付：

- 更新后的R3.4源码和协议；
- 全部测试与命令日志；
- R1.1、N1、N2A、N2、N3、N4、N5原始数据；
- pilot与正式数据、schema、split、manifest和归一化统计；
- fixed linear/bilinear冒烟模型和报告；
- 10类验收图片及figure_data；
- `report.md`、`solutions.md`、`work_log.md`、`stage_status.json`；
- 自包含 `artifact_manifest.json` 和独立核验结果；
- `READY_FOR_KOOPMAN_TRAINING.json`。

最终状态必须是以下之一：

- `COMPLETE_READY_FOR_KOOPMAN_TRAINING`；
- `BLOCKED_WITH_EVIDENCE`；
- `STOPPED_BY_USER`。

不得用 `PARTIAL` 冒充完成。
