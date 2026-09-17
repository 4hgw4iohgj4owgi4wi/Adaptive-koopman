# Round10 进展记录：向 100% 推进

- 日期：2026-05-11
- 目标：把中文稿、核心多随机种子实验证据、文献映射和剩余缺口记录继续推进到可审稿状态。
- 主 agent 原则：不覆盖旧稿；所有新增证据写入 dated derivative 文件；baseline 仍按上传 AKE 原文和可复现实验边界区分，不把 AKE-M surrogate 写成 AKE-A 严格复现。

## 1. 本轮已完成的数据与图

### E2 mixed fault/noise 全量消融

- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/e2_n20_mixed_fault_ablation_merged`
- 合并来源：原始 partial seed + 3 个 shard。
- run 数：`240`
- minimum_group_n：`20`
- Gate：`paired_n20=PASS`，`required_method_success=PASS`，`AKE_status=FAIL`，`NonKoopman_baseline=PARTIAL`，`trace_ids=PARTIAL`
- Gate 目录说明：以 `e2_n20_mixed_fault_ablation_merged_gate_v2` 为准；旧目录 `e2_n20_mixed_fault_ablation_merged_gate` 是规则修正前输出，保留作历史记录，不作为当前判断依据。
- 关键结论：
  - `no_comm_aware` 使连接最大利用率从 `0.05497` 增至 `0.42938`，纵向 RMSE 从 `0.46793` 增至 `0.50678`。
  - `no_ppc_progress_guard` 和 `zoh_consensus_surrogate` 成功率为 `0`，纵向 RMSE 分别约 `12.93` 与 `14.02`。
  - 部分消融指标有混合变化，不能写成所有模块在所有指标上单调提升。
- 图：
  - `R2_round10_module_ablation_heatmap`
  - `R2_round10_key_module_effects`

### E2 high-communication-noise 关键消融

- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/e2_n20_comm_noise_key_ablation_merged`
- run 数：`80`
- 覆盖方法：`full_tf14`、`no_comm_aware`、`no_delay_compensation`、`zoh_consensus_surrogate`
- minimum_group_n：`20`
- Gate：`paired_n20=PASS`，`required_method_success=PASS`，`AKE_status=FAIL`，`NonKoopman_baseline=PARTIAL`，`trace_ids=PARTIAL`
- 关键结论：
  - `no_comm_aware` 使连接最大利用率从 `0.04465` 增至 `0.43840`，约上升 `881.90%`。
  - `no_comm_aware` 使证书 ok 均值从 `0.99995` 降至 `0.31775`，纵向 RMSE 上升 `14.66%`。
  - `zoh_consensus_surrogate` 成功率为 `0`，纵向 RMSE 约 `14.12`。
  - `no_delay_compensation` 在该关键指标集下几乎不变，因此时延补偿不能单独强写为已充分证明，只能作为网络感知 MPC 的组成部分，后续需 dose/topology 进一步验证。
- 图：
  - `R2_comm_key_ablation_heatmap`
  - `R2_comm_key_effects`

### 仍沿用的 n=20 证据

- E0 targeted 主对比：`publication_readiness_round8_2026-05-11/e0_n20_mixed_fault_main_comparison`
- E3 证书统计：`publication_readiness_round8_2026-05-11/e3_n20_certificate`
- E7 连接安全：`publication_readiness_round8_2026-05-11/e7_n20_connection_safety`

### E0 high-communication-noise 主对比

- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/e0_n20_comm_noise_key_main_comparison_merged`
- run 数：`80`
- 覆盖方法：`baseline`、`tf14_main`、`tf14_phase_role`、`zoh_consensus_surrogate`
- minimum_group_n：`20`
- Gate：`paired_n20=PASS`，`required_method_success=PASS`，`AKE_status=PARTIAL`，`NonKoopman_baseline=PARTIAL`，`trace_ids=PARTIAL`
- 关键结论：
  - TF14-full 相对 AKE-M baseline 横向 RMSE 降低 `18.20%`，纵向 RMSE 降低 `7.94%`，连接最大利用率降低 `87.97%`。
  - 证书 ok 均值从 `0.34055` 提升到 `0.99995`。
  - 力峰值上升 `54.28%`，继续不能写受力更小或更平滑。
- 图：
  - `R0_comm_key_main_comparison_summary`
  - `R0_comm_key_relative_change`

## 2. 中文 DOCX/PDF 更新

- 基底文件：`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`
- 最新输出 DOCX：`paper_dcn_tf12_draft/manuscript_zh_tf14_round10_n20_e0e2_comm_update_2026-05-11.docx`
- 最新输出 PDF：`paper_dcn_tf12_draft/manuscript_zh_tf14_round10_n20_e0e2_comm_update_2026-05-11.pdf`
- 当前结构检查：
  - 段落数：`409`
  - 表格数：`15`
  - 图片数：`62`
  - PDF 页数：`42`
  - 未检出过期 `minimum_group_n=1`、`当前 n=1`、`单 seed gap-closure`、`证明通信感知` 等残留。
- 本轮新增/修正内容：
  - 5.8 节改为 Round10 多随机种子结果与 claim 边界更新。
  - 插入 E0 high-communication-noise 主对比表、统计汇总图和相对变化图。
  - 插入 E2 mixed fault/noise 全量消融表、热力图和关键模块图。
  - 插入 E2 high-communication-noise 关键消融表、热力图和关键模块图。
  - 将 “E2 证明” 降级为 “E2 在指定场景下支持”。
  - 明确力峰值只作代价监测，不写“受力更小/更平滑”。
  - 明确 `no_delay_compensation` 当前独立消融收益不足，需更高延迟强度和拓扑恢复曲线验证。
- PDF QA：
  - `docx_pdf_qa_e0e2_comm/contact_sheet_e0e2_comm.png`
  - 新增 E0 comm-key 和 E2 comm-key 页面已抽查，表格和图可读。

## 3. 并行 agent 输出

- 实验/工程缺口审计：`round10_to100_experiment_gap_register_zh.md`
  - 结论：实验工程约 `92%`，投稿级数据约 `82%`；硬缺口为 E1 fresh、AKE-A、强物理/DMPC baseline、dose-response/topology、trace provenance 和最终图表统计审稿。
- 文献-贡献映射：`round10_literature_claim_map_zh.md`
  - 结论：C1-C3 文献支撑基本可写；C4 FDI/FTC 直接文献仍偏弱，需要补近三年 actuator fault-tolerant MPC/FDI/control allocation 文献。
- reviewer 审查已吸收：
  - 删除过强 `证明` 语气。
  - 修正证书 ok 比例四舍五入风险，改为五位均值。
  - 修正 `no_delay_compensation` 的解释边界。
  - 修正旧 E3 段落中 “所有场景证书 ok=1 且正裕度” 的错误表述；当前只写 comm-high/mixed 为正，nominal/single-fault 仍有负裕度。
  - 修正早期机制表中 “载荷横向冲突力更小” 的过强语气；当前统一写为连接误差改善、受力作为代价监测。
  - 保留 “不能主张全面优于/受力更平滑/严格优于 AKE-A” 的禁写边界。

## 4. 当前仍不能写的 claim

| 禁写表述 | 原因 |
|---|---|
| 严格优于上传 AKE 原文 baseline | 当前主对比是 AKE-M mechanism comparator，不是 AKE-A 原文级复现。 |
| 优于所有物理模型或 DMPC baseline | 目前只有 ZOH surrogate，NonKoopman baseline 仍为 `PARTIAL`。 |
| 所有模块在所有指标上单调提升 | E2 中部分模块呈现指标混合变化。 |
| 货物受力更小或更平滑 | E0/E2/E7 中 TF14 force peak/RMS 不一定优于 baseline。 |
| E3 直接证明全局渐近稳定 | 理论口径是有界扰动和可恢复通信下的 practical boundedness/UUB，E3 是证书记录证据，不替代理论证明。 |
| 时延补偿单独已被充分证明 | `no_delay_compensation` 在 mixed 与 comm-key 两组当前主指标中影响较弱，需要 delay dose/topology 进一步验证。 |

## 5. 当前完成度估计

| 维度 | 当前估计 | 说明 |
|---|---:|---|
| 主线/claim 边界 | 94% | 已把 E0/E2 mixed 与 comm-key 证据写入稿件，并明确禁写边界。 |
| 方法/证明 | 90% | Lyapunov/UUB 口径已进中文稿；仍需全稿公式编号、引用和排版复核。 |
| 实验工程 | 95% | E0/E2/E3/E7 runner、shard、merge、plot、gate 链路已跑通；E1 fresh 和 dose/topology runner 仍未闭合。 |
| 投稿级数据 | 87% | E0 targeted、E0 comm-key、E2 mixed、E2 comm-key、E3、E7 均有 paired n=20；缺强 baseline、E1 fresh、E0 all-scenarios、dose/topology。 |
| 文献证据 | 82% | 已有贡献映射和核心 BibTeX 草案；C4 直接文献、若干作者元数据和全文精读仍缺。 |
| 投稿包完整性 | 72% | 中文 DOCX/PDF 已显著推进；英文 LaTeX、最终引用、图表编号、数据包 provenance 仍未完成。 |

## 6. 下一步若继续冲 100%

1. 跑 `E0 all-scenarios n=20`，解决主对比只针对 mixed fault/noise 的问题。
2. 跑 delay/dropout dose-response 与 topology recovery，支撑 DCN/network-resilient 主切入。
3. 补 E1 fresh Koopman 多训练 seed，解决 Koopman 预测器统计可信度。
4. 实现或复现至少一个强物理/DMPC baseline，或严格复现 AKE-A；否则 baseline 维度不能到 100%。
5. 补 FDI/FTC 直接文献和故障识别/重分配曲线。
6. 做全稿 Word/PDF 逐页 QA、图表编号、公式编号、引用编号和英文 LaTeX 同步。
