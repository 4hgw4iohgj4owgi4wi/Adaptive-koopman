# Round10 剩余到 100% 的实验/工程缺口审计

- 审计日期：2026-05-11
- 审计范围：仅检查 `publication_readiness_round8_2026-05-11`、`publication_readiness_round10_2026-05-11`、已有 gate 报告、汇总 CSV 和图表目录。
- 操作边界：本 worker 未修改 DOCX、PDF、实验 runner 或已有数据；本报告只写入本文件。
- 结论摘要：E0、E2、E3、E7 的核心 n=20 证据链已基本成形，实验工程从 Round9 的约 85%-90% 推进到约 92%；投稿级数据从约 70%-75% 推进到约 82%。距离 100% 的硬缺口集中在 E1 fresh 训练 seed、AKE-A 原文级复现、强物理/DMPC baseline、dose-response/topology recovery、trace provenance 外链和最终图表/统计显著性审稿。

## 1. 已完成实验证据清单

| 证据包 | 目录/文件 | n 与场景 | Gate 状态 | 当前可支持的结论 | 使用边界 |
|---|---|---:|---|---|---|
| E0 targeted 主对比 | `publication_readiness_round8_2026-05-11/e0_n20_mixed_fault_main_comparison` | `n=20`，`sine_mixed_fault_noise`，baseline/AKE-M/TF14/ZOH | `paired_n20=PASS`，`required_method_success=PASS`，AKE/NonKoopman/trace 均 `PARTIAL` | mixed fault/noise 下 TF14 相对 AKE-M/baseline 可写横向 RMSE、纵向 RMSE、连接利用率的定量改善；ZOH surrogate 不完成路径可作为弱底线失败观察。 | 不能代表全场景主对比；不能声称严格优于上传 AKE 原文；ZOH 不能等价为强 DMPC baseline。 |
| E2 模块消融 | `publication_readiness_round10_2026-05-11/e2_n20_mixed_fault_ablation_merged` | `n=20`，`sine_mixed_fault_noise`，12 组方法/消融 | `paired_n20=PASS`，`required_method_success=PASS`，`AKE_status=FAIL`，NonKoopman `PARTIAL`，trace `PARTIAL` | 已能证明若移除 `comm_aware`，纵向 RMSE 从 0.468 升至 0.507，连接利用率从 0.055 升至 0.429，证书通过率从约 1.000 降至 0.786；移除 `ppc_progress_guard` 会导致成功率 0、纵向 RMSE 约 12.93。 | 部分消融如 `no_bilinear`、`no_stable_projection` 在当前闭环指标上不劣于 full，不能写“所有模块均逐项提升所有指标”；E2 缺 `sine_comm_noise_high` n=20 消融。 |
| E3 证书统计 | `publication_readiness_round8_2026-05-11/e3_n20_certificate` | `n=20`，4 个场景 | `paired_n20=PASS`，`required_method_success=PASS`，AKE/NonKoopman `FAIL`，trace `PARTIAL` | 证书/安全监测链可稳定生成；mixed fault/noise 与 high comm noise 证书通过率约 1.000，nominal/single_fault 场景存在负裕度或通过率不足。 | 不能把 E3 写成严格稳定性证明；只能写为与 UUB/practical boundedness 口径一致的闭环监测证据。 |
| E7 连接/载荷安全 | `publication_readiness_round8_2026-05-11/e7_n20_connection_safety` | `n=20`，`sine_comm_noise_high` 与 `sine_mixed_fault_noise` | `paired_n20=PASS`，`required_method_success=PASS`，AKE/NonKoopman/trace `PARTIAL` | TF14/phase-role 在两个场景下连接违规为 0，连接最大利用率显著低于 baseline；ZOH surrogate 路径不完成。 | 不能写货物受力峰值更低或更平滑；已有记录反而提示 TF14 的 force norm peak 高于 baseline，应写为安全约束代价/待优化项。 |
| E1 Koopman 预测缓存证据 | `tf14_final_gap_closure_20260509/source/E1_koopman_prediction_validation.csv` 与相关图 | cached/screening，非 fresh 多训练 seed | 无正式 n>=5/n>=10 gate | 可解释稳定投影、rollout error、spectral radius before/after 的机制。 | 不能写统计显著优于 AKE 原文或 fresh training seed 已完成。 |
| 图表目录 | round8/round10 `figures` 子目录 | 已有 PNG/PDF/SVG | figure provenance 仍为 `pending` | 可用候选：`R0_main_comparison_summary`、`R0_error_timeseries`、`R0_reliability_runtime`、`R2_round10_module_ablation_heatmap`、`R2_round10_key_module_effects`、`R3_certificate_statistics`、`R7_payload_connection_safety`。 | 图表 ledger 尚未把 main/supplement 安全状态最终落定；主文图仍需统一单位、图例、显著性标注和 caption 场景说明。 |

## 2. 贡献对应现有证据和缺口

| 贡献 | 现有证据 | 仍缺什么 | 当前写作强度 |
|---|---|---|---|
| 网络感知时延补偿一致性 MPC | E0 n=20 主对比；E2 `no_comm_aware` 显示连接利用率和证书通过率明显退化；E7 两场景连接利用率降低且违规为 0。 | E2 `sine_comm_noise_high` n=20；通信强度 dose-response；拓扑断边/恢复曲线；trace provenance 外部原始 trace 链接。 | 可写“在指定 mixed fault/noise 与 high communication noise 工况下提升连接安全和保持实践有界监测”；不能写“任意网络退化/攻击下稳定”。 |
| 载荷协同运输建模与连接安全审计 | E7 记录 connection utilization、violation、force norm peak/RMS/rate；E0/E7 都可支撑连接安全。 | 货物力峰值/RMS 不占优的解释图；力分量 `Fx/Fy/Mz` 或 per-corner load spread 主文级图；连接安全与力代价的 Pareto/权衡表。 | 可写“纳入载荷受力和连接约束审计”；不能写“受力更小、更平滑”。 |
| 双线性 Koopman 预测与稳定投影 | E1 cached 预测/谱半径证据；E2 有 `no_bilinear`、`no_stable_projection` n=20。 | E1 fresh 5-10 个训练 seed；固定 train/val/test split；与 linear Koopman、bilinear、stable projection、learnable C、AKE-M 的预测统计；当前 E2 中 `no_bilinear/no_stable_projection` 未显示闭环优势。 | 可写方法机制和筛选证据；不能写“预测器统计显著优于 AKE 原文”或“该模块在所有闭环指标上显著提升”。 |
| FDI/FTC 与证书保护 | E2 `no_fdi/no_ftc_switching`、E3 证书、E7 安全统计都有 n=20。 | 更强故障注入剂量曲线；故障识别延迟/误检/漏检统计；控制重分配前后每车力/控制份额图。 | 可写“闭环中包含在线故障识别、容错切换和证书监测”；不能写“故障下所有指标均优于无故障/无容错”。 |
| PPC/progress guard 与实时调度工程 | E2 `no_ppc_progress_guard` 成功率 0、纵向 RMSE 约 12.93，说明 progress guard 是闭环可完成路径的关键保护；`no_realtime_scheduler` 影响连接利用率和单步裕度但 RMSE 不一定更差。 | 需要将工程模块解释为安全/可完成性保护，不要包装成算法主贡献；需补 runtime/solve-time 分布图。 | 可写“progress guard 是工程安全保护，移除后任务失败”；不宜写成独立理论创新。 |

## 3. 还需要跑的实验、命令建议、n、场景、指标、图规格

### P0：把网络韧性和模块消融补到主文强证据

| 实验 | 命令建议 | n | 场景 | 关键指标 | 图规格 | 目的 |
|---|---|---:|---|---|---|---|
| E2 communication-only 全量消融 | `E:\anaconda\envs\pytorch_new\python.exe tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E2 --full-final-seeds --scenarios sine_comm_noise_high --include-zoh-surrogate --continue-on-error --retry-exceptions --output-root paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_n20_comm_noise_ablation` | 20 | `sine_comm_noise_high` | RMSE_y、RMSE_s、connection utilization、certificate_ok_ratio、min margin、success、force peak/RMS/rate | 与 round10 E2 mixed 一致：heatmap + key module effects，PNG/PDF/SVG，统一颜色，full TF14 为黑/蓝基准，消融为暖色，失败方法灰色 hatch。 | 支撑“通信退化”不是只在 mixed fault/noise 中成立。 |
| E0 全场景主对比 | `E:\anaconda\envs\pytorch_new\python.exe tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise --include-zoh-surrogate --continue-on-error --retry-exceptions --output-root paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e0_n20_all_scenarios_main_comparison` | 20/场景 | 4 个 E0 场景 | RMSE_y、RMSE_s、max error、success、certificate、connection utilization、runtime | 2x2 场景 summary bar，主文只放 normalized improvement 和 completion rate；详细时序放补充。 | 避免主结果只覆盖 targeted mixed 场景。 |
| E7 force tradeoff 复核图 | 优先复用已有 E7 CSV；若需重跑，用 E7 两场景 n=20 相同命令 | 20 | `sine_comm_noise_high`、`sine_mixed_fault_noise` | force_norm_peak/RMS/rate、connection utilization、violation、corner load spread | 主文或补充做 Pareto scatter：x=connection utilization，y=force peak/RMS，点形=method，误差条=95% CI；明确标出 TF14 连接更安全但力峰值可能更高。 | 防止审稿人质疑“连接安全以受力代价换来”。 |

### P1：补齐投稿级 baseline 与预测器可信度

| 实验 | 命令/工程建议 | n | 场景 | 关键指标 | 图规格 | 目的 |
|---|---|---:|---|---|---|---|
| E1 fresh Koopman/AKE 多训练 seed | 需要单独 DNN 训练/评估 runner；建议输出到 `publication_readiness_round10_2026-05-11\e1_fresh_koopman_prediction_n10`，不要覆盖 cached E1。 | 最低 5，推荐 10 training seeds | 固定 train/val/test split，测试集不参与 ridge refit | one-step RMSE、multi-step rollout L2、per-state RMSE、spectral radius、NaN/failure count、train seed variance | 箱线图、rollout error vs horizon、per-state heatmap、spectral radius before/after 四联图；标出 median、IQR、n。 | 让 Koopman 贡献从“机制图”升级为“统计证据”。 |
| AKE-A 原文严格复现 | 需要按上传 baseline 的公开设定/网络/训练协议复现；若不可行，至少建立清晰 AKE-M/AKE-A 差异表。 | 最低 10，推荐 20 | 与 E0/E2 mixed 和 comm-only 对齐 | tracking RMSE、connection utilization、success、runtime、force metrics | baseline fidelity table + main comparison bar；图例必须区分 `AKE-M surrogate` 与 `AKE-A reproduced`。 | 解决“严格优于上传 AKE baseline”不能写的问题。 |
| 物理模型/强 DMPC baseline | 新增或外部实现，不建议把 ZOH surrogate 包装为 DMPC。 | 20 | 至少 mixed fault/noise 与 high comm noise | tracking、connection、constraint violation、solve time、success | 主文一张强 baseline 对比图；补充给求解失败/超时统计。 | 解决 NonKoopman baseline `PARTIAL`。 |

### P1/P2：补齐网络韧性曲线和可追溯性

| 实验 | 建议 | n | 场景 | 指标 | 图规格 | 目的 |
|---|---|---:|---|---|---|---|
| delay/dropout dose-response | 建议以 `sine_comm_noise_high` 为基准，扫描 delay/dropout 强度：0、低、中、高、极高；每档 n=10-20。 | 最低 10/档，推荐 20/档 | communication-only | RMSE、success、certificate margin、connection utilization、fallback count | x=通信退化强度，y=指标；均值线+95% CI；标出 failure region。 | 让“network-resilient”有强度曲线，而不只是单点。 |
| topology recovery / link outage | 设置单边/双边/环断裂/恢复窗口，记录恢复时间。 | 10-20/拓扑 | mixed 与 comm-only | recovery time、max connection utilization、certificate margin、path completion、fallback duration | timeline + topology schematic + recovery CDF。 | 支撑可恢复拓扑假设与 DCN 主题。 |
| trace provenance closure | 不一定要重跑；需要把 CSV 中 trace id 链接到原始 trace/config/seed 文件。 | 全部已有 n=20 包 | E0/E2/E3/E7 | trace_id、seed、config hash、source notebook/runtime hash | provenance ledger 表，主文不放，投稿补充/代码包放。 | 把 gate 的 `trace_ids=PARTIAL` 推到 PASS。 |

## 4. 仍不能写的 claim

| 不能写的表述 | 原因 | 安全替代表述 |
|---|---|---|
| “严格优于上传 AKE 原文 baseline” | E0/E7 只有 AKE-M surrogate；E2 gate 中 `AKE_status=FAIL`。 | “相对 AKE-style mechanism comparator 展示了网络/故障/安全机制收益；原文级 AKE-A 复现仍为待补。” |
| “优于所有网络控制或 DMPC 方法” | NonKoopman baseline 仍是低阶 ZOH surrogate，gate 为 `PARTIAL`。 | “相对弱底线 ZOH surrogate 和模块消融显示机制有效；强物理模型/DMPC baseline 待补。” |
| “所有模块消融都证明 full TF14 在所有指标上最优” | E2 中 `no_bilinear`、`no_stable_projection`、`no_realtime_scheduler` 在部分 RMSE 指标不劣于 full。 | “关键通信感知与 progress guard 对连接安全、证书裕度和任务完成性最关键；其他模块提供结构化预测/工程稳健性，闭环收益具有指标依赖性。” |
| “货物受力更小或更平滑” | E0/E7/E2 均提示 TF14 force peak/RMS/rate 不一定低于 baseline 或 ZOH。 | “本文记录并审计载荷受力；连接安全改善伴随受力代价，需在图表中显式呈现。” |
| “E3 证明严格渐近稳定” | 证明口径是有界扰动、可恢复通信和有限切换下的 practical boundedness/UUB；E3 nominal/single fault 也有负裕度。 | “证书记录与理论假设一致地支持实践有界监测，不能替代严格全局稳定性证明。” |
| “Koopman 预测精度已最终验证且显著优于 AKE” | E1 仍是 cached/screening，缺 fresh 多训练 seed 和 AKE-A。 | “当前 E1 作为机制证据；fresh seed 完成后再写统计提升。” |
| “DCN 网络韧性已完整覆盖” | 目前主要是 mixed/high communication 单点；缺 dose-response、topology recovery、trace closure。 | “在指定通信退化场景中验证网络感知控制；更广泛退化强度和拓扑恢复为后续补充实验。” |

## 5. 实验工程/投稿级数据完成度估计

| 维度 | Round10 审计估计 | 已经站稳的部分 | 到 100% 的阻塞 |
|---|---:|---|---|
| 实验工程 | 约 92% | runner 支持 output-root、full-final-seeds、continue-on-error、retry；E0/E2/E3/E7 多包均能形成 summary、manifest、gate 和图件；E2 合并后已 `minimum_group_n=20`。 | E1 fresh DNN runner/评估链未闭合；dose/topology runner 不明确；trace provenance 仍 `PARTIAL`；强 baseline 需要新工程。 |
| 投稿级数据 | 约 82% | E0 targeted 主对比 n=20；E2 mixed 消融 n=20；E3 四场景证书 n=20；E7 两场景安全 n=20；主文候选图已具备。 | AKE-A、强 DMPC/physical baseline、E1 fresh、E2 comm-only、E0 all-scenarios、dose/topology、force tradeoff 图和显著性/CI 审稿。 |
| Claim 可写性 | 约 88% | 主线、贡献、UUB/practical boundedness、连接安全和通信感知机制已经可写。 | 严格 baseline、全场景泛化、受力优势、预测器统计优势仍必须降级。 |
| 投稿包完整性 | 约 65%-70% | 中文 DOCX 已回填 E0/E3/E7 并导出 PDF；round10 有核心 BibTeX 草案。 | 全文公式/引用/图表逐页 QA、英文 LaTeX/投稿格式、代码数据包 provenance、主/补充图最终分流。 |

## 6. 建议的 100% 路线

1. 先补 `E2 sine_comm_noise_high n=20` 与 `E0 all-scenarios n=20`，这是最直接提升主文实验完整性的 P0。
2. 同步完成 E7 force tradeoff 图，不要回避 force peak 上升，把它写成连接安全/容错重构的代价和未来优化方向。
3. 用 E1 fresh n=5-10 解决 Koopman 预测器可信度；若时间不足，主文只保留 cached E1 为补充机制图。
4. AKE-A 或强 DMPC baseline 至少完成一个，否则所有“优于原文/优于 DMPC”的表述继续禁止。
5. dose-response/topology recovery 至少各做一组统计曲线，用于支撑 DCN/network-resilient 主题。
6. 最后做 figure provenance ledger 定稿：每张图标为 `Main text`、`Supplement`、`Not safe` 或 `Needs rerun`，并在 caption 中写清楚场景、n、方法、指标和限制。
