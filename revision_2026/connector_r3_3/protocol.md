# Connector R3.3 下一轮实验执行书

> 编制时间：2026-08-25 13:31 +08:00  
> 目标机器：5080，`DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前证据：`revision_2026\connector_r3_2_results`  
> 授权模式：方案编写；本文件不授权修改源码或启动实验  
> 推荐首个实际停止点：完成 N2A、N2 回归和 N3 后停止复核；N4--N9 不运行

## 0. 当前事实与问题

### 0.1 结论摘要

- 当前注册状态：`PASS_N0_N2_STOP_FOR_REVIEW`。
- 本次独立审计状态：`PARTIAL`。N0--N2 的注册门和自动摘要可由原始数据复算，但参考解自收敛与最小步长留痕仍需补证。
- H1（事件子步提高数值可解析性）：当前证据支持。
- H2（R3 力律在同一积分器下改善整车受力/平滑性）：未知，未运行 N3--N5。
- H3（R3 或事件特征改善 Koopman 多步预测）：未知，未运行 N6--N8。
- MPC 兼容性：未知；旧 MPC 只能作为旧植物历史基线。

### 0.2 证据账本

| 对象 | 来源 | 身份/范围 | 独立复算 | 可信度 | 问题 |
|---|---|---|---|---|---|
| 任务书 | `connector_r3_2/protocol.md` | SHA256 `89937c0c...f74784` | 已核对 | 已复算 | N3--N6 源码尚未实现 |
| 冻结源码 | `connector_r3_2` | 23 个文件 | 当前哈希与 N0 清单完全一致 | 已复算 | 无 Git 元数据，只能用 SHA256 |
| 结果包 | `connector_r3_2_results` | 35 个清单产物 | 大小和 SHA256 全部一致 | 已复算 | `artifact_manifest.json` 不自包含 |
| N2 原始表 | `n2/single_connector_factorial.csv` | 768 行；6 速度 × 32 相位 × 2 力律 × 2 积分器 | 无重复、无非有限值、768 行均为 PASS | 已复算 | 参考只有固定 2 us |
| N2 参考表 | `n2/reference_2us.csv` | 12 行；6 速度 × 2 力律 | 已核对 | 仅单分辨率支持 | 缺少 1 us/0.5 us 减半试验 |
| 自动摘要 | `n2/summary.json` | N2 最坏值和因子均值 | 与原始表差异小于 `1e-16` | 已复算 | 不包含跨力律物理公平结论 |

### 0.3 已复算的关键数字

全部误差均相对各自力律的固定 2 us 参考，样本为 384 条 ES 轨迹（V1/R3 各 192 条）。

| 指标 | ES 最坏值 | 注册门 | 结果 |
|---|---:|---:|---|
| 峰值力相对误差 | 0.048496% | 5% | PASS |
| 冲量相对误差 | 0.049040% | 2% | PASS |
| 末状态尺度化误差 | 0.038868% | 1% | PASS |
| 接触时刻绝对误差 | 0.000478 us | 2 us | PASS |
| R3 平滑区接受步数 | 最小 9 步 | 至少 8 步 | PASS |

平均冲量误差由固定步到事件子步的变化为：

| 力律 | 固定 2 ms | 事件子步 | 降幅 |
|---|---:|---:|---:|
| V1 | 1.765413% | 0.021548% | 98.78% |
| R3 | 0.973949% | 0.000315% | 99.97% |

四因子摘要中的积分器主效应为 `-1.358750` 个百分点，力律主效应为 `-0.406348` 个百分点。这里的响应量是“相对各自参考的数值误差”，因此只能说明积分器是本轮误差下降的主要原因，不能说明 R3 的物理受力优于 V1。

### 0.4 原因分析

1. **事实：** R3.1 的 Q99 平滑穿越名义时间为 `0.885285 ms`，小于固定植物步长 `2 ms`；固定步可能跨过接触建立和平滑区。
2. **事实：** N2 中事件子步把 Q99、0.25 m/s、1.0 m/s 的最坏冲量误差从固定步的约 2.84%--4.43% 降到远低于 0.1%。
3. **推断：** R3.1 的前置失败主要是离散分辨率不足，不是连续 R3 公式已被证伪。
4. **事实：** 前两次失败分别来自事件二分提前停止/同时事件去重错误，以及把 256 子步上限误用于固定 2 us 参考；修正没有改变力律、数据或注册门槛。
5. **未知：** 2 us 参考本身是否已收敛。当前没有 1 us 和 0.5 us 的继续减半证据。
6. **事实：** 384 条 ES 轨迹中有 66 条记录 `min_accepted_dt_s < 2 us`，最小为 `1.11e-15 s`。代码显示这是外部步边界的浮点闭合余量被计作接受步，不是物理上要求的超细子步；它几乎不影响力/冲量，但使“最小步长”统计和图 02 不可信。
7. **事实：** 当前 `run.py` 只接受 N0/N1/N2；`paired_maneuvers_r3.py`、`spectral_metrics.py`、`build_pilot.py`、`train_compare.py` 仍为占位；`four_vehicle_common.py` 仍硬编码 V2 连接器，尚未实现 V1/R3 注入和四车事件子步。
8. **风险信号：** 单连接器 R3-ES/V1-ES 冲量比在 Q05 为约 1.322、Q50 为约 0.768；对应绝对冲量仅为 `0.122 vs 0.092 N·s` 和 `0.508 vs 0.661 N·s`。比例可能受小分母放大，但说明 H2 不能由 N2 推出，N3 必须同时报告相对比和绝对差。

## 1. 目标、非目标和论文声明边界

### 1.1 本轮目标

1. 证明或否定固定 2 us 参考的自收敛性。
2. 修复浮点闭合余量被计作接受子步的问题，并确认修复前后物理量仅有舍入级差异。
3. 把事件子步推广到 30 维四车/货物植物，保持 V1/R3 公平注入。
4. 运行 N3 的两个代表载荷工况，验证四点力、冲量、末状态、力矩、作用--反作用和完整内力收敛。
5. 完成后停止，单独决定是否进入 N4--N5。

### 1.2 非目标

- 不调 `k=30000 N/m`、`c=3500 N·s/m`、`l0=0.002 m` 或 `delta_s=0.0001776170305060031 m`。
- 不改变原 N1/N2/N3 科学门槛。
- 不运行 N4 成对整车、N5 撕裂型代理、N6 数据、N7 正式数据、N8 Koopman 或 N9 MPC。
- 不读取 locked development/confirm 预测结果。
- 不把 12/15 kN 称为实物安全或破断阈值；它们仍是 `numerical_legacy_unverified`。

### 1.3 本轮通过后允许的声明

仅当 N2A、N2 回归和 N3 全通过时，可声明：

> 在冻结 R3/V1 力律和 2 ms 植物接口下，事件感知子步通过了单连接器参考自收敛审计，并在两个预注册四车代表工况中满足数值收敛、作用--反作用、力矩和完整内力残差门。

仍不得声明 R3 比 V1 更平滑、更安全、更易学习，或适用于新 MPC。

## 2. 假设与可证伪预测

| 编号 | 假设 | 可证伪预测 | 失败归类 |
|---|---|---|---|
| A1 | 2 us 参考足够细 | 1 us 对 0.5 us 的误差不超过原 N2 门槛的 10%，且相对 2 us 对 1 us 差异继续收缩 | 数值层 |
| A2 | 亚 2 us 记录仅是浮点闭合留痕错误 | 闭合修复后不再记录 `<2 us` 接受步，N2 核心量变化不超过 `1e-10` 相对量或明确的舍入下限 | 实现/数值层 |
| A3 | 事件子步可推广到四车 | N3 两工况全部满足注册收敛和物理残差门 | 物理/数值层 |
| A4 | R3 力律物理收益 | 本轮不检验；必须留到 N4--N5 的 V1-ES/R3-ES 公平比较 | 未运行 |

## 3. 版本隔离、数据边界和基线身份

### 3.1 新版本目录

未来获得执行授权后，只新增：

```text
revision_2026/connector_r3_3/
revision_2026/connector_r3_3_results/
revision_2026/connector_r3_3_data/
revision_2026/connector_r3_3_models/
revision_2026/connector_r3_3_mpc/
```

`connector_r3_2` 和 `connector_r3_2_results` 保持只读；不得修改其日志来“补齐”本次审计。

### 3.2 必须冻结的输入

- R3.2 协议 SHA256：`89937c0c7c334d9b5c5f2e5275f04227ce99f442b9ffffa68446675205774784`。
- R3 力律：`connector_r3.py` SHA256 `0bd16c4d...310459`。
- R3 schema：`schema_r3.py` SHA256 `bff45ef3...0a6d562`。
- V2 内力：`internal_force.py` SHA256 `0a00d298...c28c0`。
- V2 四车：`four_vehicle_v2.py` SHA256 `7ffc9514...57685`。
- 成对工况：`paired_maneuvers.py` SHA256 `5c41bd4d...a91e4`。
- R3.2 N2 原始表：SHA256 `29be9ddf...210813`。

N0 必须现场重算完整哈希，缩写只用于阅读。

## 4. 公式与变量定义

事件面保持：

\[
\phi_i^{(0)}=q_i,\qquad \phi_i^{(1)}=q_i-\delta_s.
\]

浮点闭合余量 `r=outer_end-t` 若满足 `0<r<=1e-12 s`，只能并入时间守恒审计，不得作为物理接受子步，也不得进入最小步长或成本统计。若 `r>1e-12 s` 且 `<h_min`，必须停止并标记 `UNRESOLVED_CLOSURE_STEP`。

参考收敛对任一指标 `M` 定义：

\[
d_{2,1}=\frac{|M_{2us}-M_{1us}|}{\max(|M_{0.5us}|,\epsilon)},\qquad
d_{1,0.5}=\frac{|M_{1us}-M_{0.5us}|}{\max(|M_{0.5us}|,\epsilon)}.
\]

四点作用--反作用、力矩和内力残差继续使用：

\[
F_i^v+F_i^p=0,
\qquad M_{z,i}=r_{x,i}F_{y,i}-r_{y,i}F_{x,i},
\qquad \|Wf_{int}\|.
\]

## 5. 代码修改表

| 文件 | 函数/类 | 修改 | 输入 | 输出 | 单元测试 |
|---|---|---|---|---|---|
| `src/event_substep.py` | `advance_outer_step`/通用求解器 | 支持 30 维状态和回调事件面；按最早事件真正分段；区分物理子步与浮点闭合余量 | state30、control4x2、law、config | state30、完整 `StepAudit` | 端点闭合、双穿越、同时事件、亚 2 us 余量 |
| `src/event_substep.py` | 步长选择 | 保留 `h_min=2 us`；`<=1e-12 s` 余量吸收；其他亚下限步立即停止 | 当前状态、剩余时间、事件速度 | dt/status | 66 条历史触发模式不再污染 `min_dt` |
| `src/connector_adapter.py` | `VectorConnector` | 为 V1/R3 提供统一四点向量接口，不改冻结力律公式 | 四点位移/相对速度 | 世界系力、标量分量、能量和状态标志 | 与冻结 V1/R3 逐点一致 |
| `src/four_vehicle_common.py` | `signed_connector_gaps`、`connector_event_surfaces` | 去除 V2 硬编码，保留有符号间隙和两事件面 | state30、params | gaps4、surfaces4x2 | 静态几何、镜像、接触边界 |
| `src/four_vehicle_common.py` | `system_derivative(..., law)` | 注入力律；显式输出逐点作用--反作用、车辆/货物力矩、完整内力 | state30、control4x2 | dx30、aux | 逐点反力、力矩重构、零空间残差 |
| `src/step_features.py` | `aggregate_step_audit` | 实现协议 2.7 的全部 2 ms 区间字段；事件特征仅来自已完成区间 | 子步审计 | 外部周期特征 | shape/单位/时间索引合同 |
| `scripts/run.py` | `run_n2a` | 新增 2/1/0.5 us 参考自收敛、闭合审计和源哈希前置门 | 6 速度 × 2 力律 | reference CSV、summary JSON | 摘要与原表独立复算 |
| `scripts/run.py` | `run_n3` | 新增四车代表载荷矩阵，保存原始时序，不只写摘要 | 两工况、四因素、各分辨率 | NPZ/CSV/JSON | N3 门逐项测试 |
| `tests/test_n1_event_detector.py` | pytest 用例 | 把当前文档占位改为可独立运行测试 | 解析算例 | 测试报告 | N1 全门 |
| `tests/test_n2_single_connector_factorial.py` | pytest 用例 | 增加参考减半、闭合余量、摘要复算 | N2A/N2 原始数据 | 测试报告 | N2A/N2 全门 |
| `tests/test_n3_four_vehicle_convergence.py` | 新文件 | 四点力、冲量、末状态、力矩、作用反作用、内力残差 | N3 原始数据 | 测试报告 | N3 全门 |
| `scripts/plot_evidence.py` | N3 图表 | 新增图 05，并修正最小步长图不把浮点闭合余量当物理 dt | 原始 CSV/NPZ | PNG + CSV | 图数值与原表一致 |
| `scripts/finalize_report.py` | 报告/清单 | 支持 N2A/N3；记录 NOT_RUN N4--N9；输出自洽 SHA256 清单 | 阶段结果 | 状态、解决方案、清单 | 清单逐文件复核 |

`paired_maneuvers_r3.py`、`spectral_metrics.py`、`build_pilot.py` 和 `train_compare.py` 本轮保持 `NOT_RUN`；不要提前实现或运行 N4--N8。

## 6. 实验矩阵与公平性

### 6.1 N2A 参考自收敛

```text
速度：Q05/Q50/Q95/Q99/0.25/1.0 m/s
力律：V1/R3
参考步长：2/1/0.5 us
总计：36 个参考运行
指标：峰值、冲量、末状态、能量余额、运行时间
```

各步长使用相同初态、持续时间、力律和中点区间积分。若 2 us 未通过，不得修改历史 N2；在 R3.3 中使用合格的更细参考重新评价 768 行矩阵。

### 6.2 N3 四车收敛

工况：

1. 历史 G3 的 2 s 小转向反转；
2. 一条冻结 train-only Q99 接触事件覆盖工况。

每个工况的初态、20 ms 控制序列和停止规则只生成一次。植物以 2 ms 记录，20 ms 控制在 10 个植物周期内保持；0.1 ms 参考不能提高控制更新频率。

```text
主候选：V1-F2、V1-ES、R3-F2、R3-ES，H=2 ms
ES 收敛诊断：V1/R3，H=1 ms 和 0.5 ms
参考：V1/R3，2 ms 外部记录块内使用 0.1 ms+ES
```

## 7. 顺序任务树

```text
R0 预飞行与新版本隔离
├─ 主机/解释器/进程/磁盘/路径检查
├─ 冻结输入和 R3.2 证据哈希
└─ 失败：停止

R1 实现与静态单元测试
├─ 通用事件求解器和闭合余量处理
├─ V1/R3 四点适配器
├─ 30 维植物、力矩和内力审计
└─ 失败：保存源码/测试，停止

R2 N1 回归
├─ 解析事件、同时事件、双穿越、时间守恒
└─ 失败：不得进入 N2A

R3 N2A 参考自收敛
├─ 2/1/0.5 us
├─ 闭合余量审计
└─ 失败：不得进入 N2/N3

R4 N2 全矩阵回归
├─ 768 行原矩阵
├─ 使用通过 N2A 的参考
└─ 失败：不得进入 N3

R5 N3 历史 G3 工况
├─ 四因素和分辨率收敛
└─ 失败：停止

R6 N3 Q99 覆盖工况
├─ 四因素和分辨率收敛
└─ 失败：停止

R7 报告、哈希与停止复核
└─ N4--N9 标记 NOT_RUN
```

## 8. 每阶段指标与硬门

### 8.1 N2A 新增数值预算门

- 1 us 对 0.5 us：峰值误差 `<=0.5%`、冲量 `<=0.2%`、末状态 `<=0.1%`；这些是原 N2 门的 10% 数值预算，不是物理安全阈值。
- 对每个指标，`d_1,0.5 <= 0.5*d_2,1`；若差异已进入明确的舍入下限，记录绝对值后允许判为收敛。
- 所有运行有限、非负法向力、能量余额有限。
- 物理接受步 `>=2 us`；`<=1e-12 s` 闭合余量不计作接受步；其他亚下限步为 FAIL。
- 闭合修复前后 N2 指标变化不得超过 `max(1e-10 相对量, 1e-12 绝对量)`；超过则说明修复改变了数值轨迹，必须停止分析。

### 8.2 N1/N2 回归门

原 `connector_r3_2/protocol.md` 的 N1/N2 所有门保持不变，不得因当前结果优秀而收紧/放宽后再选择性解释。

### 8.3 N3 硬门

`2 ms+ES` 相对 0.1 ms+ES 参考：

- 四点峰值力误差 `<=5%`；
- 四点冲量误差 `<=2%`；
- 末状态尺度化误差 `<=1%`；
- 完整内部力峰值误差 `<=5%`；
- 货物合力矩误差 `<=5%`；
- 每车连接力矩误差 `<=5%`；
- 逐点作用--反作用残差 `<1e-10 N`；
- 内力零空间残差 `<1e-8*max(1, internal_norm)`；
- 无 NaN/Inf、15 kN 数值停止或静默力裁剪；
- 所有 Q99 事件被记录，R3 平滑区每次穿越至少 8 个物理接受子步；
- 同时报告平均、P95/P99、最坏轨迹和运行成本。

## 9. 图表和原始产物

必须新增：

```text
connector_r3_3_results/n2a/reference_convergence.csv
connector_r3_3_results/n2a/closure_audit.json
connector_r3_3_results/n2/single_connector_factorial.csv
connector_r3_3_results/n3/<scenario>/raw_timeseries.npz
connector_r3_3_results/n3/<scenario>/metrics.csv
connector_r3_3_results/n3/summary.json
connector_r3_3_results/figures/05_four_vehicle_dt_convergence.png
connector_r3_3_results/figure_data/05_four_vehicle_dt_convergence.csv
connector_r3_3_results/stage_status.json
connector_r3_3_results/solutions.md
connector_r3_3_results/work_log.md
connector_r3_3_results/artifact_manifest.json
```

所有力给出 N，冲量给出 N·s，力矩给出 N·m，时间给出 s/us，状态尺度化公式写入配置。图不能替代原始数据。

## 10. 失败情形、停止条件与解决方案

| 失败 | 立即动作 | 禁止动作 | 恢复门 |
|---|---|---|---|
| 源哈希漂移 | 保存 diff 和现场清单，停止 | 覆盖旧文件以匹配哈希 | 明确来源并重新冻结 |
| 0.5 us 仍不收敛 | 保存三分辨率结果，写 `solutions.md` | 直接宣称 2 us 合格 | 新版本预注册更细参考/其他积分器 |
| 闭合修复改变物理量 | 保存修复前后最坏轨迹 | 把差异称为舍入误差 | 最小诊断定位积分路径变化 |
| 需要真实 `<2 us` 子步 | 标记速度/事件面并停止 | 静默裁剪 | 重新选择积分器并从 N1 开始 |
| N3 作用反作用/力矩/内力失败 | 保存逐点世界/体坐标量 | 只展示货物合力掩盖错误 | 坐标和力臂单元测试全通过 |
| 低幅值比例异常 | 同报绝对量、比值和分母 | 临时增加分母地板让门通过 | 依据预注册物理相关性另立诊断 |
| 控制时钟或单位不一致 | 停止 N3 | 猜测控制单位 | 控制 API 和逐元素复用审计通过 |
| 预计总耗时超过 4 h 或输出超过 5 GB | 在首个代表病例后停止并报告成本 | 降采样或删工况来通过 | 用户复核资源方案 |

## 11. 运行命令和资源预算

以下命令仅供获得未来“执行实验”授权后使用，本轮不得运行：

```powershell
$python = 'E:\anaconda\envs\pytorch_new\python.exe'
$project = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$source = Join-Path $project 'revision_2026\connector_r3_3'

& $python "$source\scripts\run.py" --project-root $project --stage N0
& $python -m pytest "$source\tests" -q
& $python "$source\scripts\run.py" --project-root $project --stage N1
& $python "$source\scripts\run.py" --project-root $project --stage N2A
& $python "$source\scripts\run.py" --project-root $project --stage N2
& $python "$source\scripts\run.py" --project-root $project --stage N3
& $python "$source\scripts\plot_evidence.py" --project-root $project --through-stage N3
& $python "$source\scripts\finalize_report.py" --project-root $project --through-stage N3
```

资源：CPU-only，不占用 GPU；D 盘现场可用约 261.83 GB。先运行一个 Q05 0.5 us 参考和一个 2 s N3 病例计时，再估算总成本。4 h/5 GB 是操作停止点，不是科学门。

## 12. 工作记录要求

每完成一个节点立即追加：时间、任务编号、授权模式、机器、解释器、输入/输出 SHA256、修改文件与函数、命令、退出码、运行时间、原始产物、硬门、事实/推断/建议/未知、停止原因和下一允许动作。

任何失败尝试的源码和摘要保存到 `audit_history`，不得覆盖或删除。最终清单必须再由独立脚本逐文件复核。

## 13. 允许写入论文的结论

- N2A 通过：允许写“固定 2 us 单连接器参考在注册指标上已通过继续减半审计”。
- N3 通过：允许写“事件子步在两个四车代表载荷工况中满足数值和物理一致性门”。
- N4/N5 未运行：不得写 R3 相对 V1 的整车平滑、完整内力或撕裂型代理优势。
- N6--N8 未运行：不得写 Koopman 可学习性或多步预测收益。
- N9 未运行：不得写新植物的 MPC/通信/DoS 结论。

## 14. 第一次实际停止点

完成 N2A、N2 回归和 N3 后必须停止。即使 N3 全部 PASS，也只生成状态报告和证据包，不自动进入 N4/N5。下一次复核需要回答：

1. 2 us 参考是否真正自收敛；
2. 亚 2 us 记录是否已从物理步统计中消失；
3. 四车事件子步是否真实按最早事件分段，而不是只记录事件；
4. 作用--反作用、车辆/货物力矩和完整内力是否逐点通过；
5. N3 结果是否足以授权 N4--N5，还是应停止 R3 力律路线。

