# Round9 最终状态与后续任务

## 1. 本轮最终状态

| 维度 | 当前完成度 | 状态 |
|---|---:|---|
| 主线/claim 边界 | 85% | 达到本轮目标。已删除“受力平滑”等过强 claim，改成连接安全和载荷受力审计。 |
| 方法/证明 | 85% | 达到本轮目标。证明口径限定为有界扰动、可恢复通信和有限切换下的 UUB/practical boundedness。 |
| 实验工程 | 85% | 达到本轮目标。runner 支持输出隔离、provenance、异常续跑、后台日志容错和 gate。 |
| 投稿级数据 | 70% | 达到本轮停止线。E0 targeted、E3、E7 均已有 paired n=20。 |
| 文献证据 | 70% | 达到本轮目标。已有 20 条模块化证据矩阵，仍需 BibTeX 和全文精读。 |

## 2. 已完成的投稿级数据包

| 数据包 | 输出目录 | Gate 状态 | 可用结论 |
|---|---|---|---|
| E0 targeted 主对比 | `paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e0_n20_mixed_fault_main_comparison` | `paired_n20=PASS`，`required_method_success=PASS` | mixed fault/noise 下 TF14 平均横向 RMSE、平均纵向 RMSE 和连接最大利用率优于 AKE-M/baseline。 |
| E3 证书统计 | `paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e3_n20_certificate` | `paired_n20=PASS`，`required_method_success=PASS` | 证书/安全监测链在四个场景下可稳定生成，路径完成率为 1。 |
| E7 载荷连接安全 | `paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e7_n20_connection_safety` | `paired_n20=PASS`，`required_method_success=PASS` | TF14 连接最大利用率显著降低，连接违规为 0。 |

## 3. 必须保留的 claim 边界

- 可以写：TF14 在 mixed fault/noise targeted 主对比中降低平均横向 RMSE 约 9.95%，降低平均纵向 RMSE 约 0.95%，连接最大利用率降低约 82.88%。
- 可以写：E7 两个场景中，TF14-full 相对 baseline 的连接最大利用率降低约 83% 到 86%，连接违规为 0。
- 可以写：ZOH surrogate 在 E0/E7 中不能完成路径，可作为弱底线失败观察。
- 不能写：本文严格优于上传的 AKE 原文 baseline，因为当前仍是 AKE-M surrogate。
- 不能写：TF14 在所有指标上全面优于 baseline，因为最大横向偏差和载荷受力峰值并非优势。
- 不能写：货物受力更小或更平滑，因为 E0/E7 n=20 均显示 TF14 force norm peak 高于 baseline。

## 4. 下一步任务树

| 优先级 | 任务 | 输出 |
|---|---|---|
| P0 | E2 mixed fault/noise 全量消融 n=20 | `R2_module_ablation_heatmap` 与模块贡献统计表。 |
| P0 | 将 E0/E3/E7 可用图和降级 claim 回填中文 DOCX | 新一版中文稿，公式和图题 QA。 |
| P1 | E1 fresh Koopman/AKE 多训练 seed | 预测误差、训练 seed 方差、Koopman 模型可信度图。 |
| P1 | stronger non-Koopman baseline 或 physical-model DMPC | 替代 ZOH surrogate，降低 baseline 质疑风险。 |
| P1 | dose-response/topology recovery | 通信强度曲线、拓扑恢复曲线、trace provenance。 |
| P2 | 文献 BibTeX 与全文精读压缩 | 14-18 条核心引用与逐条“原文做了什么/本文改进什么”。 |

## 5. 当前主要风险

- Baseline 风险：`AKE-A` 原文严格复现仍未完成，当前只能写 `AKE-M` mechanism comparator。
- 数据风险：E0 只有 targeted mixed fault/noise 场景，全场景主对比尚未完成。
- 力学风险：连接安全变强的同时载荷力峰值变高，正文必须解释为安全约束/连接刚度/容错重构的代价，而不是优势。
- 证明风险：Lyapunov 证明只能主张 UUB/practical boundedness，不能主张任意通信攻击下渐近稳定。
