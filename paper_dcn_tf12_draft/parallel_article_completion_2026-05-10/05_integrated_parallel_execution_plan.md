# 主 Agent 整合结果：DCN 论文完成并行任务树

## 1. 本轮多 Agent 执行记录

本轮目标是把“完成 DCN 论文还需要做什么”拆成可并行任务，并按照 worker-reviewer-rework-integration 流程形成可执行计划。所有输出都限制在：

`paper_dcn_tf12_draft/parallel_article_completion_2026-05-10`

未修改现有中文 DOCX、LaTeX、实验代码或图件目录。

| 阶段 | Agent | 职责 | 输出或结果 |
|---|---|---|---|
| Worker A | Storyline and Contribution Tree | 论文 topic、主线、贡献点与 baseline 差异 | `01_storyline_contribution_tree.md` |
| Worker B | Literature and Baseline Gap Map | 文献支撑树、baseline gap、公平比较边界 | `02_literature_baseline_gap_map.md` |
| Worker C | Method and Theory Completion Tasks | 方法公式、符号、控制链、Lyapunov 边界 | `03_method_theory_completion_tasks.md` |
| Worker D | Experiment, Figure, and Ablation Plan | 实验、图表、消融、统计门槛 | `04_experiment_figure_ablation_plan.md` |
| Reviewer 1 | Narrative and Novelty Review | 只读 A/B，检查 DCN 主题、baseline、公平性和过强 claim | 输出 P0/P1 问题清单，未改文件 |
| Reviewer 2 | Technical and Evidence Review | 只读 C/D，检查方法-证明-实验闭环 | 输出 P0/P1 问题清单，未改文件 |
| Main Agent | Integration | 根据审核意见下发返工并整合最终计划 | `05_integrated_parallel_execution_plan.md` |

## 2. 审核后已完成的返工

Reviewer 1 指出叙事仍偏控制侧、baseline 公平性未冻结、文献缺 DCN-native 支撑。已要求 Worker A/B 返工，结果如下：

| 文件 | 已修正内容 |
|---|---|
| `01_storyline_contribution_tree.md` | 将主线升级为“通信网络问题驱动控制设计”；明确 delay/dropout/burst/jitter/topology/link quality/timestamp 如何进入 consensus weights、neighbor prediction、fallback 和实验指标；重排贡献点，把 delay-compensated consensus MPC 作为核心 novelty；压低所有稳定性和网络韧性 claim。 |
| `02_literature_baseline_gap_map.md` | 补入 V2X/CAV/CACC、wireless multi-robot、QoS-aware control、communication-control co-design、timestamped exchange、bursty loss/jitter、resilient DMPC 等 DCN-native 文献类别；新增 baseline 三状态 `AKE-R/AKE-A/AKE-M`；冻结 baseline fairness gate。 |

Reviewer 2 指出控制层级与证明层级未闭合、实验统计不足、安全诊断可能有 NaN、正文图过载。已要求 Worker C/D 返工，结果如下：

| 文件 | 已修正内容 |
|---|---|
| `03_method_theory_completion_tasks.md` | 增加 `u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}->x_{c,k+1}` 控制链到团队闭环 `A_sigma/B_sigma` 的桥接门禁；将稳定性限制为 practical boundedness / ISS-practical stability / UUB；增加 `q/Gamma/delta/tau/x/z/G/A/B` 符号硬门禁；将 400 ms、40% dropout、leader-lost 标为 stress-test 或需额外连通性假设。 |
| `04_experiment_figure_ablation_plan.md` | 强制 T1 baseline 冻结；强制至少一个非 Koopman 网络控制基线；主闭环统计要求 `n>=20` paired seeds、fresh training seeds、failure count 和 95% CI；安全图禁止 NaN，必须有 violation count、fallback/intervention log 和 constraint activity；正文图收敛为 6-8 张。 |

## 3. 最终并行任务树

### A. Topic 与论文主线

目标：把文章切入固定为“退化数字通信网络下的多车协同运输控制”，而不是“一个更复杂的 Koopman-MPC 控制器”。

| 子任务 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| A1 固定主 topic | Worker A 输出 | 最终 title、abstract opening、intro first paragraph | 无 |
| A2 重排贡献点 | Worker A/B/C/D 输出 | 4 个贡献点：网络感知 DCC-MPC、协同运输建模、Koopman predictor、安全韧性扩展 | A1 |
| A3 压低 claim | Reviewer 1/2 输出 | claim boundary 清单 | A1/A2 |
| A4 删除内部版本叙事 | 当前中文稿 | manuscript-facing 表述 | A2 |

验收标准：标题、摘要、贡献、引言中不得出现 TF12/TF13/TF14 作为创新来源；所有 novelty 都必须面向 baseline 和 recent literature。

### B. 文献与 Baseline 公平性

目标：补齐每个模块的已发表工作支撑，并把 baseline 比较变成可审计、可复现实验合同。

| 子任务 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| B1 补 DCN-native 文献 | 合法来源检索 | 文献表：V2X/CAV/CACC、QoS、AoI、burst loss、resilient DMPC | A1 |
| B2 补 Koopman/MPC/协同运输文献 | 合法来源检索 | 每个贡献对应的 related work 句 | A2 |
| B3 冻结 T1 baseline | baseline PDF、现有实现 | `AKE-R/AKE-A/AKE-M` 三选一说明 | A2/D |
| B4 增加非 Koopman baseline | 实验代码 | `Physical-model DMPC` 或 `ZOH consensus MPC` | D |
| B5 写 fairness gate | Worker B 输出 | 训练数据、horizon、solver、dt、约束、通信 trace、seed/CI 表 | B3/B4 |

验收标准：未完成 T1 前，论文不得写“本文优于 baseline”；只能写机制差异或任务适配待验证。

### C. 方法与理论闭环

目标：把系统模型、通信模型、Koopman、MPC、FTC、安全和 Lyapunov 证明写成一个闭环，而不是模块堆叠。

| 子任务 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| C1 统一坐标系与符号 | 当前中文稿、代码 | 符号表、模式表、角点编号表 | A2 |
| C2 重写车辆-载荷模型 | 动力学代码、当前稿 | 载荷中心模型、角点映射、连接误差、载荷受力定义 | C1 |
| C3 重写通信模型 | comm 模块 | delay/dropout/burst/jitter/topology/link quality/timestamp 公式 | C1/A1 |
| C4 重写 Koopman 网络 | tf14 配置 | lifted state、bilinear dynamics、loss、ridge、stable projection | C1 |
| C5 重写 DCC-MPC | 控制代码 | MPC 目标函数、约束、delay compensation、consensus weights | C3/C4 |
| C6 桥接控制链到证明 | Worker C 输出 | `u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}->A_sigma` 说明 | C2/C5 |
| C7 修正 Lyapunov 证明 | 当前 4.8 证明 | practical boundedness / ISS-practical stability / UUB 证明 | C6 |

验收标准：证明中的 `A_sigma/B_sigma` 必须说明来自完整控制链诱导的团队闭环等效模型，不能直接等同 Koopman 训练矩阵或单车 MPC 矩阵。

### D. 实验与图表

目标：用可重复、多 seed、公平 baseline 的实验支撑每个创新点。

| 子任务 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| D1 T1 主 baseline 实验 | B3/B5 | baseline 设置表和主比较数据 | B3/B5 |
| D2 非 Koopman baseline | B4 | `Physical-model DMPC` 或 `ZOH consensus MPC` 数据 | B4 |
| D3 主闭环统计 | 实验 runner | nominal、bounded comm、single fault、mixed 的 `n>=20` 结果 | D1/D2 |
| D4 fresh Koopman 学习统计 | Koopman 训练脚本 | `n_train>=5`，目标 `n_train>=10` 的 prediction/rollout 统计 | C4 |
| D5 通信 dose-response | 通信 trace | 0-200 ms、0-20% dropout、jitter、short burst、recoverable topology | C3 |
| D6 stress-test 分离 | 实验 runner | 400 ms、40% dropout、leader-lost 仅作 stress-test | D5 |
| D7 安全诊断修复 | logging/export | 无 NaN 的 violation、fallback、constraint activity、force/connection 指标 | C7 |
| D8 消融实验 | 完整 method set | no delay、no comm-aware、no bilinear、no FDI/FTC、no guard、online on/off 若保留 | C5/C6 |
| D9 正文图冻结 | 最终数据 | 6-8 张主图、supplement 图清单、provenance ledger | D3-D8 |

验收标准：`n=1`、smoke、cached、历史 TF13 图不能支撑主结论；正文主图必须有 provenance、seed、scenario、method set。

### E. 稿件集成与投稿

目标：把上述结果集成回中文稿，再迁移到英文 LaTeX 投稿稿。

| 子任务 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| E1 中文稿集成 | 最新中文稿、A-D 输出 | 新版中文 DOCX | A-D |
| E2 DOCX 公式/图表 QA | E1 | PDF 渲染检查、表格结构检查、公式页检查 | E1 |
| E3 英文 LaTeX | E1 | DCN 模板英文稿 | E1 |
| E4 终审 | E3 | top reviewer 风险清单 | E3 |
| E5 投稿包 | E3/E4 | cover letter、highlights、data availability | E4 |

验收标准：英文稿不得机械翻译中文；必须用 DCN 读者视角重写摘要和引言。

## 4. P0 / P1 / P2 优先级

### P0：不完成不能投稿

| 编号 | 工作 | 原因 | 产物 |
|---|---|---|---|
| P0-1 | 冻结 T1 baseline fairness | baseline 不清会直接被审稿人否定 | `T1_baseline_fairness.md/csv` |
| P0-2 | 至少加入一个非 Koopman 网络控制基线 | 防止“只比弱 Koopman baseline” | baseline 数据和表 T1/T2/T4 |
| P0-3 | 完成 `n>=20` paired closed-loop 统计 | 当前 smoke/cached 不支持统计结论 | T2/T3/T4/T5 |
| P0-4 | 完成 fresh Koopman/AKE 多训练种子 | cached learning 图不能支撑主 claim | prediction/rollout 统计 |
| P0-5 | 修复安全诊断 NaN 和 intervention log | 安全图有 NaN 不能进正文 | T5、safety figures |
| P0-6 | 方法-证明闭环桥接 | 否则 Lyapunov 证明会被认为跳步 | 修正后的 method/proof |
| P0-7 | 补真实近三年文献 | 当前只是检索计划，不是文献支撑 | literature matrix |

### P1：强烈建议完成

| 编号 | 工作 | 原因 | 产物 |
|---|---|---|---|
| P1-1 | topology recovery sweep | 支撑网络韧性主题 | Fig. N2、T4 |
| P1-2 | online adaptation on/off paired ablation | 若保留 online adaptation，必须验证 | A7、T3/T6 |
| P1-3 | dwell-time/switching stress sweep | 支撑切换 Lyapunov 假设 | certificate/switching 图 |
| P1-4 | payload mass / friction OOD | 支撑 Koopman 鲁棒性 | OOD 统计表 |
| P1-5 | runtime/message-size overhead | DCN 读者会关心通信与计算代价 | T6 |

### P2：补强项

| 编号 | 工作 | 原因 | 产物 |
|---|---|---|---|
| P2-1 | 4/6/8 车规模扩展 | 支撑可扩展性讨论 | supplement 表/图 |
| P2-2 | 更真实 burst loss / correlated jitter | 增强 DCN 说服力 | supplement stress 图 |
| P2-3 | 作者公开稿/机构库全文归档 | 方便写 related work | 文献文件夹和摘要表 |

## 5. 推荐正文主图压缩方案

正文默认只保留 8 张主图，其余进补充材料。

| 主图 | 功能 | 必须满足 |
|---|---|---|
| Fig. 1 | 系统模型和通信图 | 标出车辆、载荷、通信边、delay/dropout/timestamp |
| Fig. 2 | Koopman 学习与预测验证 | fresh 多训练种子、AKE/EDMD/DMDc 对比 |
| Fig. 3 | 主闭环轨迹和误差 | Proposed、T1 AKE、非 Koopman baseline、关键消融 |
| Fig. 4 | bounded communication dose-response | 0-200 ms、0-20% dropout、95% CI |
| Fig. 5 | 消融汇总 | no delay/no comm/no bilinear/no FTC/no guard |
| Fig. 6 | payload force and connection safety | 无 NaN、violation count、constraint activity |
| Fig. 7 | Lyapunov/certificate margin | 与 proof 字段一致，不超过 UUB claim |
| Fig. 8 | runtime and communication overhead | solve p95、overrun、message size、packet rate |

## 6. 稳定性与 claim 边界

全文只能使用以下级别的理论表述：

- practical boundedness
- ISS-practical stability
- uniform ultimate boundedness
- bounded tracking/connection errors under tested bounded network degradation

全文不得使用以下表述，除非后续新增严格证明：

- global asymptotic stability
- arbitrary delay/dropout stability
- complete fault tolerance
- guaranteed safety under all network failures
- exact nonlinear Koopman representation
- baseline failure under out-of-scope conditions

## 7. 立即执行建议

下一轮如果开始实际推进论文，建议按这个顺序：

1. 先冻结 `T1_baseline_fairness`，确定 AKE baseline 属于 `AKE-R`、`AKE-A` 还是 `AKE-M`。
2. 同时实现或启用一个非 Koopman 网络控制基线。
3. 并行跑 fresh Koopman/AKE 学习统计和主闭环 `n>=20` 统计。
4. 修复 safety diagnostics export，确保没有 NaN，并记录 intervention/fallback/constraint activity。
5. 基于最终数据冻结 6-8 张正文图和 supplement 图。
6. 再回到中文稿，统一重写引言、方法、实验和 Lyapunov 边界。
7. 中文稿过审后再迁移英文 LaTeX。

## 8. 剩余风险

| 风险 | 当前状态 | 处理策略 |
|---|---|---|
| baseline 不可复现 | 尚未冻结 T1 | 降级为 `AKE-A` 或 `AKE-M`，避免 strict reproduction claim |
| 实验统计不足 | 现有部分结果为 smoke/cached | 主结论必须等 `n>=20` 和 fresh seeds |
| DCN 主题不够强 | 已通过返工加强，但文献还未真实补齐 | 优先补 DCN-native 文献 |
| 理论证明跳层 | 已列桥接门禁，但正文尚未改 | 集成中文稿时必须先写控制链到团队闭环 |
| 安全图字段 NaN | 已识别风险 | 未修复前 safety 图不得进正文 |
| 正文图过多 | 已收敛到 8 张主图方案 | 其余图放 supplement |
| online adaptation 证据不足 | 当前建议降级为接口 | 没有 paired ablation 不写主贡献 |
