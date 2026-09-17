# Worker D: Experiment, Figure, and Ablation Task Plan

## 0. 边界与证据状态

本文实验计划服务于 DCN 投稿主题 `Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC`。主比较对象应是上传基线论文 `Adaptive Koopman Embedding for Robust Control of Complex` 的可复现实验版本，而不是 TF12/TF13/TF14 的本地版本演进。

已盘点的可参考图源如下。不得移动、删除、重命名这些目录中的任何图。

| 图源层级 | 目录 | 当前用途 | 投稿风险 |
|---|---|---|---|
| 最新 paper 图层 | `tf14_paper_figures_20260510/figures` | 可作为主图和补充图文件清单 | 图源数据仍在 `tf14_paper_figures_20260508/source` |
| paper 图源数据 | `tf14_paper_figures_20260508/source` | 可追溯 `fig00` 到 `fig14`、`figSxx` 的数据来源 | 其中部分图是 Stage5/Stage6 和定向 rerun，不等同最终多随机种子统计 |
| remaining 实验层 | `tf14_remaining_experiments_20260509` | 已有 E0/E2/E3/E7 smoke 结果和 R0/R2/R3/R7 图 | README 明确 `Final n>=20 ready: False`，当前 `n=1` 不可作为最终统计结论 |
| gap closure 图层 | `tf14_final_gap_closure_20260509` | 补齐 E1/E2/E3/E7 机制图和复制后的 paper/remaining/gap 图 | README 明确仍不是最终 `n>=20` 统计，E1 依赖 cached offline screening data |
| 历史通信消融 | `paper_dcn_tf12_draft/figures_reasonable_comm_ablation_2026-05-07` | 可参考通信压力和混合扰动图形结构 | TF13 证据只能作为补充或重跑模板，不应支撑 TF14 主创新 |

统一颜色和线型建议如下。所有图必须使用同一图例映射，避免不同图中同一方法颜色变化。

| 方法或元素 | 颜色 | 线型 | 备注 |
|---|---|---|---|
| Proposed TF14 full / BK-DCCMPC | `#1f77b4` 蓝色 | 实线 | 主方法 |
| Uploaded baseline / AK baseline | `#d95f02` 橙色 | 长虚线 | 基线论文复现方法 |
| No delay compensation | `#d62728` 红色 | 点划线 | 延迟补偿消融 |
| No communication-aware term | `#9467bd` 紫色 | 点线 | 通信感知消融 |
| No bilinear Koopman | `#2ca02c` 绿色 | 短虚线 | 学习模型消融 |
| No FDI/FTC switching | `#8c564b` 棕色 | 点划线 | 故障重构消融 |
| Reference / desired path | `#111111` 黑色 | 细虚线 | 轨迹和目标 |
| Safety bound / constraint | `#555555` 深灰 | 细实线 | 约束边界 |
| Communication fault window | `#f0ad4e` 半透明橙 | 背景带 | 延迟、丢包、拓扑降级 |
| Actuator fault window | `#c44e52` 半透明红 | 背景带 | 降额、失效、混合故障 |

单位规范如下。位置、路径误差和连接误差用 `m`；纵向进度或弧长误差用 `m`；航向误差用 `rad` 或 `deg` 并保持全文一致；力用 `N`；力矩用 `N*m`；求解和步进时间用 `ms`；延迟用 `ms`；丢包率用 `%`；证书 margin 使用无量纲或明确归一化单位；利用率用 `%` 或 `[0,1]`。

### 0.1 Reviewer 2 P0/P1 硬门槛

以下规则覆盖后续所有实验和图表；未满足时不得进入正文主结论，只能标为补充材料、开发记录或需重跑。

| 硬门槛 | 可进入正文的最低条件 | 不满足时处理 |
|---|---|---|
| Baseline 公平性 | T1 必须冻结 uploaded AKE baseline 的定义，并强制包含至少一个非 Koopman 网络控制基线 | 图表不得写 `baseline outperforms` 或 `proposed improves over baseline` |
| 通信压力边界 | 主结果只使用 bounded realistic degradation；400 ms、40% dropout、leader-lost 只能作为 stress-test | 不得用于“保证稳定”“任意通信故障鲁棒”等过强 claim |
| 统计证据 | 主闭环统计每个 method-scenario `n>=20` paired seeds；E1/M1 使用 fresh 多训练种子；失败计数和 95% CI 必须报告 | `n=1`、smoke、cached 数据只能进补充或开发记录 |
| 安全图 | safety diagnostics 不允许 NaN；必须有 violation count、fallback/intervention log、constraint activity | 任一字段缺失则安全相关图不得进入正文 |
| 正文图数量 | 正文图收敛到 6-8 张；每张图必须记录 data provenance、seed、scenario、method set | 超出图放 supplement；缺 provenance 的图不得编号 |
| Online adaptation | 若作为主贡献，必须有 online-on/off paired ablation；否则降级为补充接口 | 不允许用 `No online adapt` smoke 结果支撑主贡献 |

### 0.2 T1 baseline 公平性冻结规则

T1 不是普通参数表，而是投稿前必须冻结的 baseline 合同。uploaded AKE baseline 只能采用以下三种定义之一；选定后全文统一命名，不得混用。

| T1 标签 | 定义 | 可支持的论文表述 | 禁止表述 |
|---|---|---|---|
| `AKE-R` 原论文复现 | 尽量忠实复现 uploaded AKE 论文的模型、训练损失、预测/控制接口，并说明为适配协同搬运所做的最小环境映射 | `Compared with a reproduced AKE baseline under the same cooperative-transport task` | 如果网络退化、协同搬运接口或控制器已大改，不得称为 strict reproduction |
| `AKE-A` 任务适配基线 | 保留 AKE embedding/学习机制，将任务、状态、输入和 MPC 约束适配到本文协同搬运环境 | `Compared with a task-adapted AKE baseline` | 不得暗示完全复现原论文全部实验设置 |
| `AKE-M` 机制对照 | 仅把 AKE embedding 作为机制对照，用于分离本文双线性 Koopman 或 DCC-MPC 模块的贡献 | `AKE-style embedding mechanism control` | 不得作为唯一主 baseline，也不得替代闭环控制 baseline |

主闭环图表的强制 method set 为：`Proposed BK-DCCMPC`、一个冻结后的 `AKE-R/AKE-A/AKE-M`、至少一个非 Koopman 网络控制基线、`No delay compensation`、`No comm-aware`。非 Koopman 网络控制基线必须至少选一项：`Physical-model DMPC`、`physical MPC + ZOH consensus`、`ZOH consensus MPC`。若物理模型 DMPC 暂不可用，最低可接受强制项是 `ZOH consensus MPC`，并在 T1 中写明其不使用 Koopman 预测。

### 0.3 通信压力边界

| 等级 | 延迟 | 丢包 | 拓扑 | 可支持的 claim | 图表位置 |
|---|---|---|---|---|---|
| Bounded realistic main | `0-200 ms`，含 jitter/burst 但有上界 | `0-20%`，含短 burst loss | complete/ring/path/single-edge loss，必须可恢复 | bounded delay/dropout 和可恢复拓扑退化下的网络韧性 | 正文主结果 |
| Stress-test only | `400 ms` | `40%` | leader-lost、长时间断连、不可恢复 topology | 极端压力下的失效边界、降级行为和 safety fallback | 补充或 stress-test 小节 |

正文不得把 stress-test 成功样本外推为任意通信故障鲁棒性；stress-test 失败也必须计入 failure mode，不得删除。

### 0.4 统计与安全验收

| 项目 | 正文验收标准 |
|---|---|
| 闭环 seeds | 每个主场景、主方法和关键消融 `n>=20` paired random seeds；相同 seed 必须复用同一参考轨迹、通信 trace、故障 trace |
| 学习 seeds | Koopman/AKE 学习必须 fresh 多训练种子，最低 `n_train>=5`，目标 `n_train>=10`；不能用 cached screening data 作为主结论 |
| 统计输出 | mean、std、95% CI、paired delta、success/failure count、solver failure/skip count 必须同时报告 |
| 失败处理 | crash、path incomplete、constraint violation、safety fallback、solver infeasible 均计入失败或干预，不允许静默剔除 |
| 安全输出 | force/connection/corner-load/saturation/constraint activity/fallback log 不得为 NaN；所有方法必须导出相同字段 |

## 1. 主实验

| 实验 ID | 目的 | 变量 | 指标 | Baseline | 公平性要求 | 输出图表 |
|---|---|---|---|---|---|---|
| M1: Offline Koopman learning validation | 验证双线性 Koopman 学习是否在协同搬运动力学上提供更稳定、可滚动预测的模型 | 模型类型：双线性 Koopman、线性 EDMD/DMDc、T1 冻结的 `AKE-R/AKE-A/AKE-M`、无 stable projection；fresh 训练种子；预测 horizon | one-step RMSE、multi-step rollout RMSE、spectral radius、稳定投影前后 margin、训练/验证 loss、95% CI | T1 冻结的 AKE baseline；线性 DMDc/EDMD；非 Koopman 预测模型可选 | 相同离线数据、相同 train/validation split、相同状态/输入归一化、相同训练 epoch 或早停规则、相同测试轨迹；`n_train>=5`，目标 `n_train>=10` | `fig02`、`fig03`、`gap_E1`、`figS01`、表 T1/T2 |
| M2: Nominal cooperative transport | 证明在无通信退化和无故障下，主方法不会牺牲基本跟踪与实时性 | 场景 `sine_nominal_clean`，路径曲率，载荷质量，速度设定，paired random seeds | lateral RMSE、longitudinal RMSE、max error、full path reached、solve time p95、step overrun ratio、failure count | T1 冻结的 AKE baseline、非 Koopman 网络控制基线 `Physical-model DMPC` 或 `ZOH consensus MPC`、No bilinear | 同一初始条件、同一参考轨迹、同一 MPC horizon/约束、同一控制频率、同一 solver tolerances；主统计 `n>=20` | `fig05`、`fig06`、`fig07`、`R0_main_comparison_summary`、表 T2 |
| M3: Representative network-resilient closed-loop run | 展示 bounded realistic 通信退化或混合故障下的代表性闭环轨迹、误差和恢复过程 | 场景 `sine_comm_noise_high`、`sine_mixed_fault_noise`；主文延迟不超过 `200 ms`、丢包不超过 `20%`；故障时间窗；是否 phase-role scheduling | 轨迹偏差、误差时序、恢复时间、路径完成率、控制平滑度、solver success、failure count | T1 冻结的 AKE baseline、非 Koopman 网络控制基线、No delay compensation、No comm-aware | 干扰时间窗、随机种子、约束、控制频率完全一致；同一通信 trace 在所有方法间复用；400 ms/40%/leader-lost 仅 supplement stress-test | `fig04`、`fig05`、`R0_error_timeseries`、`figS09`、`figS10`、`figS11`、表 T2 |
| M4: Real-time feasibility and performance tradeoff | 证明新增模块没有破坏 DCN 场景下的在线可执行性 | 方法版本、是否实时调度器、车辆数量、MPC horizon、通信负载 | step time mean/p95/p99、solve time p95、overrun ratio、RMSE、certificate ok ratio、solver skip/fallback count | T1 冻结的 AKE baseline、非 Koopman 网络控制基线、No realtime scheduler | 固定硬件、固定 Python/solver 环境、固定 logging 开销，统计所有 seeds；runtime 图必须声明 hardware/software | `fig14`、`R0_reliability_runtime`、表 T6 |

## 2. 通信压力实验

| 实验 ID | 目的 | 变量 | 指标 | Baseline | 公平性要求 | 输出图表 |
|---|---|---|---|---|---|---|
| C1: Delay/dropout dose-response | 验证延迟补偿和通信感知项在 bounded realistic degradation 下的收益边界，并单独标出 stress-test 失效边界 | 主文延迟 `{0, 50, 100, 200}` ms；主文丢包率 `{0, 5, 10, 20}`%；stress-test 延迟 `400 ms`、丢包 `40%` 只进补充；jitter；burst loss 长度 | RMSE_y、RMSE_s、max error、full path reached、certificate ok ratio、connection utilization、solver skip、failure count | T1 冻结的 AKE baseline、No delay compensation、No comm-aware、强制非 Koopman `ZOH consensus MPC` 或 `Physical-model DMPC` | 同一通信 trace 预生成并被所有方法复用；只改变通信变量，不同时改变 fault 或 controller tuning；stress-test 不用于过强 claim | 新图 `F_comm_dose_response`，可参考 `N07_comm_noise_dose_response.png` 的结构；表 T4 |
| C2: Topology degradation and recovery | 验证 complete/ring/path/single-edge loss 等可恢复拓扑退化下仍能保持协同搬运，并把 leader-lost 标为 stress-test | 主文拓扑：complete、ring、path、single edge loss、recoverable intermittent edge；stress-test：leader-lost、long disconnect；恢复时间；切换 dwell time | consensus error、role switch count、RMSE、force peak、connection violation count、certificate min margin、fallback count | T1 冻结的 AKE baseline、No comm-aware、No phase-role、非 Koopman网络控制基线 | 图切换 schedule 固定；每种拓扑同一初始状态；拓扑退化不与未声明的控制增益变化混合；leader-lost 不支撑主 claim | 新图 `F_topology_recovery`，`figS05` 补充通信质量诊断，表 T4 |
| C3: Communication-only bounded-realistic closed loop | 单独隔离通信退化，避免 reviewers 认为性能来自故障或轨迹差异 | 场景 `sine_comm_noise_high`，主文 bounded delay/dropout/jitter，fault off；stress-test 另列 | tracking RMSE、communication quality、stale packet age、control smoothness、certificate ok ratio、failure count | T1 冻结的 AKE baseline、非 Koopman网络控制基线、No delay compensation、No comm-aware | 禁用 actuator fault；所有方法使用相同通信 log；统计 `n>=20`；smoke/cached 图不得进正文主结论 | `R0_error_timeseries`、`R2_module_ablation_heatmap_dlc_comm_noise_high`、`E2_positive_worse_heatmap_dlc_comm_noise_high`、表 T2/T3 |
| C4: Mixed communication and actuator disturbance | 验证 DCN 主题中 bounded communication degradation 与局部执行器故障叠加时的鲁棒性 | 场景 `sine_mixed_fault_noise`，主文通信 trace 限于 bounded realistic；故障类型，故障持续时间，phase-role | RMSE、recovery time、FDI latency、FTC switch correctness、force rate、certificate min margin、violation/fallback count | T1 冻结的 AKE baseline、非 Koopman 网络控制基线、No FDI、No FTC switching、No comm-aware | fault trace 与通信 trace 均预生成；所有方法使用同一 actuator limit 和 safety bound；400 ms/40% 混合扰动只作 stress-test | `fig08`、`fig09`、`fig10`、`fig11`、`R7_payload_connection_safety_dlc_mixed_fault_noise`、表 T5 |

## 3. Baseline 对比

| 实验 ID | 目的 | 变量 | 指标 | Baseline | 公平性要求 | 输出图表 |
|---|---|---|---|---|---|---|
| B1: T1 frozen uploaded AKE baseline | 形成投稿主对比，避免只与本地 TF 历史版本比较 | 方法：Proposed TF14、T1 选定的 `AKE-R/AKE-A/AKE-M`、T1 强制非 Koopman 网络控制基线、关键消融 | M1/M2/M3 全部核心指标 | 上传基线论文 `Adaptive Koopman Embedding for Robust Control of Complex` 的冻结定义 | T1 必须写明 AKE 标签、网络假设、是否无延迟补偿、是否无协同通信退化处理、训练预算、seeds；若选 `AKE-A/M`，正文不得称 strict reproduction | `fig03`、`fig05`、`fig06`、`fig10`、表 T1/T2 |
| B2: Mandatory non-Koopman network-control baseline | 增加强对照，证明收益不是“只有 Koopman baseline 太弱”造成 | 非 Koopman 控制：`Physical-model DMPC`、`physical MPC + ZOH consensus` 或 `ZOH consensus MPC` 至少一项；可加 classical MPC | closed-loop RMSE、success/failure、constraint violation、runtime、communication sensitivity | 强制非 Koopman 网络控制基线 | 不使用 Koopman 预测；同一通信 trace、约束、horizon、频率和 safety bound；若模型不含 payload learning，需在 T1 说明 | `R0_main_comparison_summary`、`F_comm_dose_response`、表 T1/T2/T4 |
| B3: Same-model same-controller fairness check | 分离模型学习收益和控制器收益 | 控制器固定，仅替换 Koopman 模型；模型固定，仅替换 DCC-MPC 模块 | prediction RMSE、closed-loop RMSE、solver time、constraint violation | 双线性 Koopman + baseline controller；baseline Koopman + DCC-MPC | 模块互换时只改一个变量；所有 tuning 参数写入表 T1 | 新表 T1，`fig13` 或 `R2_true_module_ablation_delta` |
| B4: Statistical significance and failure accounting | 支撑最终论文量化声明 | seeds `n>=20`；fresh training seeds；场景 nominal/comm/fault/mixed；方法集 | mean、std、95% CI、paired delta、success rate、failure count、solver skip/fallback/intervention count | T1 baseline、非 Koopman baseline 和所有关键消融 | paired seeds；失败不能静默剔除；完整报告 crash、constraint violation、path incomplete、fallback intervention；`n=1/smoke/cached` 不进正文主结论 | 表 T2/T3/T4/T5，`R0_main_comparison_summary` |
| B5: Complexity and deployment overhead | 说明网络韧性机制的通信和计算代价 | horizon、lift dimension、车辆数、通信频率、payload states | compute time、message size、packet rate、overrun ratio、accuracy tradeoff | T1 baseline、非 Koopman baseline、No realtime scheduler | 同一硬件和日志级别；消息体大小按实际 fields 计算；runtime seeds 与主实验 paired | `fig14`、`R0_reliability_runtime`、表 T6 |

## 4. 消融实验

| 实验 ID | 目的 | 变量 | 指标 | Baseline | 公平性要求 | 输出图表 |
|---|---|---|---|---|---|---|
| A1: Bilinear Koopman ablation | 验证双线性输入作用项而非普通线性 lifting 带来预测和控制收益 | Full TF14、No bilinear、linear EDMD/DMDc、No stable projection | prediction RMSE、spectral radius、closed-loop RMSE、certificate margin、95% CI | T1 冻结的 AKE embedding、No bilinear、非 Koopman预测/控制基线 | 同一训练数据和控制器；不重新调 controller gains 来补偿消融版本；fresh training seeds | `fig03`、`gap_E1`、`R2_true_module_ablation_delta`、表 T3 |
| A2: Delay compensation ablation | 验证延迟补偿是 bounded communication pressure 收益来源 | Full TF14、No delay compensation、zero-order hold、No comm-aware | RMSE_s、stale packet age、recovery time、certificate ok ratio、failure count | T1 baseline、非 Koopman `ZOH consensus MPC` | 同一通信 trace；同一 consensus topology；同一 MPC horizon；400 ms/40% 仅 stress-test | `R2_module_ablation_heatmap_dlc_comm_noise_high`、`E2_positive_worse_heatmap_dlc_comm_noise_high`、表 T3/T4 |
| A3: Communication-aware MPC term ablation | 验证通信质量权重和约束处理对连接安全与稳定 margin 的贡献 | Full TF14、No comm-aware、No delay compensation、No scheduler | connection utilization、violation count、force peak/RMS、certificate min margin、fallback/intervention count | T1 baseline、非 Koopman网络控制基线 | 消融仅关闭通信质量输入，不改变 safety bound 和 FDI threshold；safety diagnostics 不允许 NaN | `figS05`、`fig10`、`R7_payload_connection_safety_dlc_comm_noise_high`、表 T5 |
| A4: FDI/FTC switching ablation | 验证故障识别、隔离和控制重分配模块 | Full TF14、No FDI、No FTC switching、wrong threshold sensitivity | detection delay、false positive rate、switch accuracy、post-fault RMSE、force redistribution、fallback/intervention log | T1 baseline、No FTC、非 Koopman网络控制基线 | 故障注入强度和时间窗相同；阈值调参只在 validation set 上完成；失败和 fallback 必须计数 | `fig08`、`fig09`、`figS06`、`figS12`、表 T3/T5 |
| A5: Phase-role scheduler ablation | 验证 phase-role 对不同搬运阶段和故障支持车角色的贡献 | Full TF14、No phase-role、static role、No realtime scheduler | per-vehicle error balance、role switch count、support vehicle error、runtime overhead、constraint activity | T1 baseline、static role、非 Koopman网络控制基线 | 同一车辆初始队形；角色切换惩罚和约束记录完整；主文只使用 `n>=20` | `fig07`、`fig11`、`figS12`、`fig14`、表 T3/T6 |
| A6: Progress guard / safety fallback ablation | 验证安全和进度保护是防止失稳或路径未完成的关键 | Full TF14、No PPC/progress guard、No stable projection、No safety fallback | full path reached、max longitudinal error、constraint violation、certificate margin、fallback/intervention count | T1 baseline、非 Koopman网络控制基线 | 不能只展示成功样本；必须保留路径未完成、约束失败和 intervention log；No guard 若失稳仍计入统计 | `fig12`、`R2_true_module_ablation_delta`、`E3_certificate_margin_bound_distribution`、表 T3/T5 |
| A7: Online adaptation on/off paired ablation | 若 online adaptation 保留为主贡献，证明在线更新本身带来收益且不破坏安全；若不执行，则 online adaptation 仅作为补充接口 | Full TF14 online-on、online-off、frozen Koopman、optional slow-update variant | closed-loop RMSE、prediction drift、certificate margin、solver time、failure/intervention count | T1 baseline、Full TF14 online-off | paired seeds、相同通信/故障 trace、相同训练初始化；主文要求 `n>=20`，并报告 online update 计算开销 | `R2_true_module_ablation_delta`、`fig14`、表 T3/T6；若未完成则只进 supplement |

## 5. 稳定性与安全性实验

| 实验 ID | 目的 | 变量 | 指标 | Baseline | 公平性要求 | 输出图表 |
|---|---|---|---|---|---|---|
| S1: Lyapunov/certificate timeline | 验证理论证书与实际闭环记录一致，避免过度声称渐近稳定 | 场景 nominal/comm/fault/mixed；模式切换；扰动上界 | certificate ok ratio、min margin、max V、practical bound、dwell-time events、failure count | T1 baseline、No stable projection、No progress guard、非 Koopman网络控制基线 | 证书公式和代码记录字段一一对应；记录所有 switching events；smoke/cached 只作补充 | `fig12`、`R3_certificate_timeline_*`、`E3_certificate_margin_bound_distribution`、表 T5 |
| S2: Payload force and connection safety | 证明网络退化下仍保持载荷连接和力学安全 | force norm、Fx/Fy/Mz、force rate、connection ds/dey、corner load spread | force peak/RMS、force rate peak/RMS、connection utilization、violation count、corner load spread、fallback/intervention count | T1 baseline、No comm-aware、No FTC switching、非 Koopman网络控制基线 | 相同 payload mass 和连接刚度；相同 safety bounds；所有方法输出同一诊断字段；任何 NaN 都触发重跑 | `fig10`、`R7_payload_connection_safety_*`、`E7_force_rate_jerk_corner_timeline_*`、表 T5 |
| S3: Constraint activity and saturation | 说明控制饱和、连接约束和安全层不是装饰性模块 | actuator saturation ratio、constraint active count、fallback/intervention flag、solver infeasible flag | saturation time、constraint violation count、tracking degradation after intervention、fallback duration | T1 baseline、No safety fallback、非 Koopman网络控制基线 | 相同 actuator limits；不能隐藏 infeasible 或 skipped solver steps；必须导出 intervention log 和 constraint activity | `figS15`、新图 `F_constraint_activity`、表 T5 |
| S4: Robustness envelope | 给出方法在 bounded realistic 区间内的承受边界，并把极端压力作为 stress-test | delay/dropout/fault severity 网格；topology type；payload mass | success probability、failure mode、certificate min margin、force safety violation、fallback count | T1 baseline、No comm-aware、No FTC、非 Koopman网络控制基线 | 主文网格 `n>=20`；stress-test 可 `n>=10` 初筛但只进补充；失败计入统计 | 新图 `F_robustness_envelope`，表 T4/T5 |

## 6. 图表规格清单

正文图冻结为 6-8 张。下表是主文默认 8 图方案，只有这些图可进入正文；后续详细清单中的其他图默认放 supplement、stress-test 或开发记录，除非主文图被明确替换。每张正文图都必须在 caption 或图表脚注中写清 data provenance、seed、scenario、method set。

| 正文图 | 对应证据 | Data provenance | Seed 要求 | Scenario 边界 | Method set | 正文准入状态 |
|---|---|---|---|---|---|---|
| Fig. 1 | 系统模型和网络韧性框架 | `fig00/fig01` 的 vector source 和方法模块清单 | 不适用 | 不作性能 claim | Proposed modules only | 可进正文，作为方法示意 |
| Fig. 2 | Koopman learning validation | `fig02/fig03/G1`，最终替换为 fresh E1 训练结果 | `n_train>=5`，目标 `n_train>=10`；固定测试轨迹 | 离线 dataset，不含 stress-test | Proposed、T1 AKE、No bilinear、linear EDMD/DMDc | 当前 cached 只能补充；fresh 后进正文 |
| Fig. 3 | 主闭环轨迹和误差 | `R0_error_timeseries` 或 `fig05/fig06` final rerun | 闭环 `n>=20` 统计；代表性时序注明 seed id | bounded realistic degradation；400 ms/40% 不进入此图 | Proposed、T1 AKE、非 Koopman baseline、No delay、No comm-aware | 需 final seeds 后进正文 |
| Fig. 4 | 通信压力 dose-response | 新 `F_comm_dose_response`/`N1` | 每个通信网格 `n>=20` | 主图仅 `0-200 ms`、`0-20%`；stress-test 分图进 supplement | Proposed、T1 AKE、非 Koopman baseline、No delay、No comm-aware | 需新增/重跑 |
| Fig. 5 | 模块消融 | `R2_true_module_ablation_delta` final | 每个消融 `n>=20` paired seeds | bounded realistic high-comm 和 mixed | Full、No bilinear、No delay、No comm-aware、No FDI/FTC、No phase-role、No guard、online-on/off 若保留 | 需 final seeds 后进正文 |
| Fig. 6 | 安全和载荷连接 | `R7_payload_connection_safety_*` final 或 `fig10` final | `n>=20`；代表性时序注明 seed id | bounded realistic high-comm/mixed；stress-test 分开放补充 | Proposed、T1 AKE、非 Koopman baseline、No comm-aware、No FTC | 需无 NaN、violation/fallback/constraint activity 后进正文 |
| Fig. 7 | 稳定性证书和 safety intervention | `R3_certificate_statistics`、`G4`、`F_constraint_activity` | `n>=20`；certificate timeline 可用代表性 seed | bounded realistic；stress-test 只说明失效边界 | Proposed、No stable projection、No guard、T1 baseline | 需与 Worker C 公式字段一致 |
| Fig. 8 | 实时性和部署开销 | `fig14`、`R0_reliability_runtime` final | 与主闭环 paired seeds 一致 | bounded realistic workload；记录硬件 | Proposed、T1 AKE、非 Koopman baseline、No realtime scheduler、online-on/off 若保留 | 需 T6 硬件和 message-size 记录 |

正文图标题和编号不得直接沿用 `R/G/N` 开发文件名；开发图名只作为 provenance。所有 `n=1`、smoke、cached、QA contact sheet、TF13 历史图都不得进入正文图编号。

| 图表 ID | 当前可参考文件 | 图内容与曲线规格 | 单位 | 标题建议 | 位置 |
|---|---|---|---|---|---|
| Fig. 0 | `tf14_paper_figures_20260510/figures/fig00_graphical_abstract.*` | 方法流程图：离线双线性 Koopman、通信退化估计、DCC-MPC、FDI/FTC、安全证书；不放性能曲线 | 无 | `Network-resilient cooperative transport framework` | 图形摘要或正文开头 |
| Fig. 1 | `fig01_system_modeling.*` | 车辆、载荷、连接和通信图示；标注状态、输入、通信边、延迟通道 | m、rad、N | `Cooperative transport model and communication graph` | 正文 |
| Fig. 2 | `fig02_offline_koopman_learning.*` | 训练/验证 loss 曲线；数据覆盖散点或分布；Proposed 蓝实线，baseline 橙虚线 | loss、m、N | `Offline bilinear Koopman learning and dataset coverage` | 正文 |
| Fig. 3 | `fig03_koopman_prediction_accuracy.*` | one-step 与 rollout RMSE；spectral radius 或 stable projection margin；Proposed 蓝，baseline 橙，No bilinear 绿 | m、无量纲 | `Koopman prediction accuracy and rollout stability` | 正文 |
| Fig. 4 | `fig04_scenario_map.*` | 场景地图、通信退化窗口、故障窗口、路径曲率；用橙色通信带和红色故障带 | m、s、ms、% | `Evaluation scenarios under communication and fault disturbances` | 正文 |
| Fig. 5 | `fig05_main_trajectory_compare.*` | 参考轨迹黑虚线；Proposed 蓝实线；baseline 橙虚线；No delay 红点划线；可叠加载荷中心和车队轨迹 | m | `Closed-loop trajectory comparison under network degradation` | 正文 |
| Fig. 6 | `fig06_tracking_error_statistics.*` | 多种方法的 lateral/longitudinal RMSE 条形图或箱线图；`n>=20` 后加 95% CI | m | `Tracking error statistics over paired random seeds` | 正文 |
| Fig. 7 | `fig07_vehicle_error_role_balance.*` | 四车或多车 per-vehicle error；角色切换前后分组；颜色按车辆固定，方法用线型区分 | m | `Vehicle-level role balance and tracking errors` | 正文或补充 |
| Fig. 8 | `fig08_fdi_identification.*` | residual、threshold、detected fault flag、true fault window；阈值黑线，故障红色背景 | residual 单位或归一化 | `Fault detection and isolation timeline` | 正文 |
| Fig. 9 | `fig09_ftc_switch_redistribution.*` | 控制重分配权重、故障车输出、支援车输出；故障窗口红色背景 | N、% | `Fault-tolerant control switching and redistribution` | 正文 |
| Fig. 10 | `fig10_payload_force_connection_safety.*` | force norm、Fx/Fy/Mz、connection utilization、violation count；安全边界灰线 | N、N*m、% | `Payload force and connection safety under mixed disturbances` | 正文 |
| Fig. 11 | `fig11_phase_role_scheduler.*` | phase、role assignment、communication quality、scheduler decision；阶梯图加背景阶段 | 无量纲、% | `Phase-role scheduling under degraded communication` | 正文或补充 |
| Fig. 12 | `fig12_lyapunov_certificate.*` | V(t)、delta V 或 margin、bound、switch events；margin 0 线黑色，失败区域红色 | 无量纲 | `Recorded Lyapunov certificate and practical stability margin` | 正文 |
| Fig. 13 | `fig13_module_ablation_available_variants.*` | 模块消融的 delta heatmap 或 grouped bar；正值表示 worse 必须在色条标题中写清 | m、%、无量纲 | `Module ablation summary` | 正文 |
| Fig. 14 | `fig14_realtime_pareto.*` | RMSE vs p95 solve time Pareto；点大小表示 overrun ratio；颜色按方法 | m、ms、% | `Real-time performance and accuracy Pareto` | 正文或补充 |
| Fig. S1 | `figS01_all_state_input_distribution.*` | 离线数据 state/input 分布、覆盖边界、训练/测试重叠 | m、rad、N | `Offline dataset state-input coverage` | 补充 |
| Fig. S5 | `figS05_comm_quality_diagnostics.*` | packet age、delay、dropout、quality score；通信窗口橙色背景 | ms、%、无量纲 | `Communication quality diagnostics` | 补充 |
| Fig. S6 | `figS06_fdi_tuning_summary.*` | threshold sensitivity、false positive/negative、detection delay | s、%、无量纲 | `FDI tuning and threshold sensitivity` | 补充 |
| Fig. S9 | `figS09_all_scenario_team_traj.*` | 全场景车队中心轨迹；参考黑虚线，方法颜色统一 | m | `Team trajectories over all scenarios` | 补充 |
| Fig. S10 | `figS10_all_scenario_four_vehicle_traj.*` | 全场景每车轨迹；车辆颜色固定，方法线型固定 | m | `Vehicle trajectories over all scenarios` | 补充 |
| Fig. S11 | `figS11_all_scenario_errors.*` | 全场景误差时序或分布；按场景分面 | m | `Tracking errors over all scenarios` | 补充 |
| Fig. S12 | `figS12_fault_support_vehicle_errors.*` | 故障车和支援车误差、输出变化；故障窗口红色背景 | m、N | `Support vehicle behavior during actuator faults` | 补充 |
| Fig. S15 | `figS15_control_saturation.*` | 控制饱和比例、active constraint count、solver skip；安全边界灰线 | %、count | `Control saturation and constraint activity` | 补充 |
| Fig. S19 | `figS19_tf13_error_match_runtime.*` | 仅作为内部历史或补充 sanity check，不作为主创新证据 | m、ms | `Runtime sanity check against historical implementation` | 补充，必要时删除正文引用 |
| Fig. R0a | `tf14_remaining_experiments_20260509/figures/R0_main_comparison_summary.*` | E0 主比较条形图；必须重跑 `n>=20` 后替换 smoke 版本 | m、%、ms | `Main comparison over final random seeds` | 正文候选 |
| Fig. R0b | `R0_error_timeseries.*` | 高通信和混合扰动误差时序；背景标出通信/故障窗口 | m、s | `Error timelines under representative disturbances` | 正文候选 |
| Fig. R0c | `R0_reliability_runtime.*` | success rate、runtime、solver overrun；点线或 grouped bar | %、ms | `Reliability and runtime statistics` | 正文或补充 |
| Fig. R2a | `R2_module_ablation_heatmap_dlc_comm_noise_high.*` | 通信高压下消融 heatmap；正值表示 worse；色条用发散色 | m、%、无量纲 | `Ablation heatmap under high communication degradation` | 正文候选 |
| Fig. R2b | `R2_module_ablation_heatmap_dlc_mixed_fault_noise.*` | 混合扰动下消融 heatmap；保持 R2a 同一排序 | m、%、无量纲 | `Ablation heatmap under mixed disturbance` | 正文候选 |
| Fig. R2c | `R2_true_module_ablation_delta.*` | 各模块移除后的 paired delta；误差条为 95% CI | m、%、ms | `True module ablation deltas` | 正文 |
| Fig. R3a | `R3_certificate_statistics.*` | certificate ok ratio、min margin、max V 的统计条形图 | %、无量纲 | `Certificate statistics over final seeds` | 正文候选 |
| Fig. R3b | `R3_certificate_timeline_dlc_comm_noise_high.*` | 通信高压下 V/margin 时序；0 margin 黑线 | 无量纲、s | `Certificate timeline under high communication degradation` | 补充 |
| Fig. R3c | `R3_certificate_timeline_dlc_mixed_fault_noise.*` | 混合扰动下 V/margin 时序；通信和故障背景双层标注 | 无量纲、s | `Certificate timeline under mixed disturbance` | 补充 |
| Fig. R7a | `R7_payload_connection_safety_dlc_comm_noise_high.*` | 通信高压下 force、connection、corner load；安全边界灰线 | N、%、m | `Payload and connection safety under communication degradation` | 正文候选 |
| Fig. R7b | `R7_payload_connection_safety_dlc_mixed_fault_noise.*` | 混合扰动下 safety metrics；同 R7a 轴范围便于比较 | N、%、m | `Payload and connection safety under mixed disturbance` | 正文候选 |
| Fig. G1 | `tf14_final_gap_closure_20260509/figures/E1_koopman_prediction_validation.*` | one-step、rollout、spectral radius 三联图；当前为 cached data，最终应重跑 E1 | m、无量纲 | `Koopman prediction validation gap closure` | 正文候选，需最终 E1 替换 |
| Fig. G2 | `E2_positive_worse_heatmap_dlc_comm_noise_high.*` | positive=worse 消融热图；列为指标，行为模块 | m、%、无量纲 | `Positive-worse ablation map under communication stress` | 补充或正文 |
| Fig. G3 | `E2_positive_worse_heatmap_dlc_mixed_fault_noise.*` | 同 G2，用混合扰动数据；必须同一色条范围 | m、%、无量纲 | `Positive-worse ablation map under mixed stress` | 补充或正文 |
| Fig. G4 | `E3_certificate_margin_bound_distribution.*` | mode-wise margin distribution、practical bound；箱线图或 violin | 无量纲 | `Mode-wise certificate margin and practical bound` | 正文候选 |
| Fig. G5 | `E7_force_rate_jerk_corner_timeline_dlc_comm_noise_high.*` | force rate、jerk、corner spread 时序；安全边界灰线 | N/s、m/s^3、% | `Force-rate and corner-load timeline under communication stress` | 补充 |
| Fig. G6 | `E7_force_rate_jerk_corner_timeline_dlc_mixed_fault_noise.*` | 同 G5，用混合扰动；故障窗口红色背景 | N/s、m/s^3、% | `Force-rate and corner-load timeline under mixed stress` | 补充 |
| Fig. N1 | 需新生成 | delay/dropout dose-response 曲线；x 轴为 delay 或 dropout，y 轴为 RMSE/success/certificate；方法颜色统一 | ms、%、m | `Communication dose-response envelope` | 正文 |
| Fig. N2 | 需新生成 | topology degradation/recovery 分面图；complete/ring/path/leader-lost | m、%、s | `Topology degradation and recovery performance` | 正文或补充 |
| Fig. N3 | 需新生成 | robustness envelope heatmap；x 为 delay，y 为 dropout，颜色为 success probability 或 min margin | ms、%、% | `Robustness envelope over communication stress` | 正文 |
| Fig. N4 | 需新生成 | constraint activity/safety intervention timeline；active constraints、saturation、fallback flags | count、%、s | `Constraint activity and safety fallback events` | 补充 |

## 7. 表格规格清单

| 表 ID | 内容 | 指标和单位 | 位置 | 必须包含 |
|---|---|---|---|---|
| T1 | Baseline fairness and parameter table | AKE baseline 标签 `AKE-R/AKE-A/AKE-M`、非 Koopman baseline 选择、horizon、dt、lift dimension、training samples、solver、constraints、communication model | 正文 | Proposed、冻结 AKE baseline、强制非 Koopman 网络控制基线的可比性说明 |
| T2 | Main `n>=20` aggregate comparison | RMSE_y/RMSE_s `m`、max error `m`、full path `%`、success `%`、solve p95 `ms`、failure count | 正文 | paired seed mean/std/95% CI；`n=1/smoke/cached` 禁止进入 |
| T3 | Module ablation statistics | paired delta、failure count、certificate ok `%`、runtime `ms`、fallback/intervention count | 正文 | Full TF14、No bilinear、No delay、No comm-aware、No FDI/FTC、No phase-role、No guard；online-on/off 若 online adaptation 保留 |
| T4 | Communication pressure envelope | delay `ms`、dropout `%`、topology、success `%`、RMSE、certificate margin、failure mode | 正文或补充 | bounded realistic 与 stress-test 分栏；400 ms/40%/leader-lost 不用于主 claim |
| T5 | Safety and stability metrics | force peak/RMS `N`、force rate `N/s`、connection utilization `%`、violation count、min margin、constraint activity、fallback/intervention log | 正文 | 不允许安全指标为 NaN；所有方法必须导出同名字段 |
| T6 | Computational and communication overhead | solve time `ms`、overrun `%`、message size `bytes`、packet rate `Hz`、online update cost | 正文或补充 | 固定硬件与软件环境；若 online adaptation 保留，必须报告 on/off paired overhead |

## 8. 创新点到证据映射

| 创新点 | 需要证明的机制 | 必要图 | 必要表 | 当前状态 |
|---|---|---|---|---|
| C1: 双线性 Koopman 学习用于协同搬运预测与控制 | 双线性输入作用和 stable projection 提升 rollout 稳定性，并改善闭环预测一致性 | 正文 Fig. 2、正文 Fig. 5；补充 Fig. S1/G1 | T1、T2、T3 | 有 cached/paper 图；最终需要 fresh E1 多训练种子，cached 只能补充 |
| C2: Delay-compensated consensus MPC 面向网络退化 | bounded delay/dropout/stale packet 下比 T1 baseline、非 Koopman baseline 和 No delay 更稳 | 正文 Fig. 3、Fig. 4、Fig. 5；补充 R0/R2/N3 | T2、T3、T4 | 有 E0/E2 smoke；需要 `n>=20` 和 bounded communication sweep；400 ms/40% 只作 stress-test |
| C3: Communication-aware safety and topology resilience | 通信质量进入 MPC 后降低连接风险、fallback 频率和证书失败率 | 正文 Fig. 4、Fig. 6、Fig. 7；补充 Fig. S5/G5/N2/N3 | T4、T5 | 有通信诊断和 E7 smoke；缺 topology sweep 和 safety 无 NaN final export |
| C4: FDI/FTC 与 phase-role scheduling 支撑故障恢复 | 故障检测、角色切换和控制重分配缩短恢复并平衡单车误差 | 正文 Fig. 5 或 Fig. 6 中合并呈现；补充 Fig. 8/9/11/S6/S12 | T3、T5 | 有代表性图；需要最终 mixed/fault `n>=20`，否则不作为独立正文主图 |
| C5: 稳定性证书和安全层避免过度声称 | 证书 margin、practical bound、约束活动与 intervention log 和代码记录一致 | 正文 Fig. 7；补充 Fig. 12/R3/G4/N4 | T5 | 有 E3 smoke/gap 图；需要公式字段核对、final seeds、constraint activity log |
| C6: 实时可部署性 | 新模块在实时频率下保持 solve p95 和 overrun 可接受 | 正文 Fig. 8；补充 Fig. 14/R0c | T6 | 有 paper 图和 R0 runtime；需要固定硬件 final run 和 message-size 记录 |
| C7: Online adaptation | 仅在 online-on/off paired ablation 通过后保留为主贡献；否则作为补充接口 | 正文 Fig. 5/8 若保留；否则 supplement only | T3、T6 | 当前默认降级为补充接口，除非 A7 完成 `n>=20` |

## 9. 当前最可能缺失的数据和需要重跑的场景

| 优先级 | 缺失或风险 | 需要重跑或补充 | 接受标准 |
|---|---|---|---|
| P0 | `tf14_remaining_experiments_20260509` 当前 `Final n>=20 ready: False`，E0/E2/E3/E7 表中 `num_runs=1` | 按 `FULL_FINAL_COMMANDS.md` 重跑 E0/E2/E3/E7 的 `--full-final-seeds`，并加入 T1 非 Koopman baseline | 每个主要 method-scenario 组合 `n>=20`，输出 mean/std/95% CI、failure count、solver skip/fallback count |
| P0 | 上传 AKE baseline 复现边界尚需写清，当前 `baseline` 名称可能被 reviewer 质疑不是同一 baseline | 建立 T1，三选一冻结 `AKE-R/AKE-A/AKE-M`，逐项记录模型、训练数据、控制器、通信假设和调参规则 | 主文所有 baseline 叙述都能回到 T1；若为 `AKE-A/M` 不得称 strict reproduction |
| P0 | 缺强制非 Koopman 网络控制基线 | 实现或启用 `Physical-model DMPC`、`physical MPC + ZOH consensus` 或最低 `ZOH consensus MPC` | T1/T2/T4 中必须出现至少一个非 Koopman baseline，否则主闭环比较不合格 |
| P0 | E1 目前使用 cached offline screening data，不是 fresh multi-seed DNN retraining sweep | 单独实现或运行 E1 多 seed Koopman DNN/AKE 训练验证 | 最低 `n_train>=5`，目标 `n_train>=10`；报告 rollout RMSE、spectral radius、95% CI；cached 仅补充 |
| P0 | 通信压力实验边界不够清晰，可能导致过强 claim | 生成 bounded dose-response：`0-200 ms`、`0-20% dropout`、可恢复 topology；把 `400 ms/40%/leader-lost` 单独标为 stress-test | Fig. N1/N2/N3 和 T4 明确 main vs stress-test；正文 claim 只写 bounded realistic |
| P0 | 混合扰动 safety summary 中部分 connection/corner-load 字段可能为 `NaN`，且 intervention log 不完整 | 修复 diagnostics export，确保 T1 baseline、非 Koopman baseline、No comm-aware、No FTC、TF14 都输出 force、connection、corner load、constraint activity、fallback/intervention log | T5 无 NaN；安全边界、violation count、fallback count、constraint activity 可复核 |
| P0 | 正文图数量过多且缺统一 provenance | 将正文图冻结为 6-8 张，并为每张图建立 data provenance、seed、scenario、method set | 无 provenance 或 seed/scenario/method set 的图不得编号进入正文 |
| P1 | `sine_single_fault_v2` 的最终统计尚未在 E0/E3 full list 中形成正文图 | 重跑单故障场景 final seeds，并输出 FDI latency、FTC switch、support vehicle metrics | Fig. 8/9/S12 的代表性图与 T3/T5 的统计一致 |
| P1 | No progress guard 在 smoke 中出现 path incomplete，适合证明安全层但不能只用单 seed | 对 No PPC/progress guard、No stable projection 重跑 paired seeds | 失败计入统计，不能剔除；T3 明确 failure count |
| P1 | Runtime/overrun 指标中 solver skip count 需要解释，否则 reviewer 会质疑实时结论 | 检查 logging 语义，区分 skipped MPC solve、warm-start reuse、fallback step | T6 写明字段定义，Fig. R0c 不误导 |
| P1 | 现有历史 TF13 通信消融图不能作为 TF14 主证据 | 用 TF14 final runner 重做对应通信保护和混合扰动消融，旧图仅作为模板 | 正文不引用 TF13 图作为创新证明 |
| P1 | 稳定性证书的代码字段与理论公式需要一致 | Worker C 完成公式后，回查 E3 certificate.csv 字段含义 | Fig. 12/R3/G4 的 caption 不超过理论假设 |
| P1 | Online adaptation 当前尚未有 online-on/off 成对统计 | 若保留为主贡献，运行 A7 online-on/off paired ablation；否则从主贡献和正文图中降级 | 完成 `n>=20` 才可作为主贡献；未完成则只写补充接口 |
| P2 | Scalability 可能被 DCN reviewer 追问 | 可补 4/6/8 车或 message-size sweep | 至少 T6 给 message size 和 compute trend |
| P2 | 真实通信模型缺少 burst loss 或 correlated jitter | 补 burst loss trace 与恢复时间统计 | T4 明确通信模型不是独立同分布丢包的单一设定 |

## 10. 立即执行顺序

| 顺序 | 操作 | 产物 |
|---|---|---|
| 1 | 冻结 T1 baseline fairness 参数表：三选一 `AKE-R/AKE-A/AKE-M`，并强制选定非 Koopman 网络控制基线 | `T1_baseline_fairness.csv/md` |
| 2 | 实现或启用非 Koopman baseline，并确认与 Proposed/AKE 共用同一 seeds、通信 trace、故障 trace、约束和 horizon | T1/T2/T4 可用 method set |
| 3 | 运行 E0 full-final-seeds，覆盖 nominal、bounded comm、single fault、mixed；400 ms/40% 另跑 stress-test | Fig. R0a/R0b/R0c final，T2 |
| 4 | 运行 E2 full-final-seeds，覆盖 bounded high comm 和 mixed；若 online adaptation 保留，同步运行 A7 online-on/off | Fig. R2a/R2b/R2c final，T3 |
| 5 | 运行 E3 full-final-seeds，并与 Worker C 的证书公式核对，输出 failure/fallback/intervention count | Fig. R3a/R3b/R3c/G4 final，T5 |
| 6 | 运行 E7 full-final-seeds，修复所有 safety diagnostics NaN，补齐 violation count、constraint activity、fallback/intervention log | Fig. R7a/R7b/G5/G6 final，T5 |
| 7 | 新增 bounded communication dose-response 和 recoverable topology degradation sweep；leader-lost 只作 stress-test | Fig. N1/N2/N3，T4 |
| 8 | 新增或刷新 E1 Koopman/AKE fresh 多训练种子验证 | Fig. 2/G1 final，T2/T3 |
| 9 | 冻结正文 6-8 张图的 provenance ledger：data source、seed、scenario、method set、main/supplement 状态 | 可投稿图表清单 |
