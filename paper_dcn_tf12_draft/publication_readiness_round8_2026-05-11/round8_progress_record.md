# Round8 进展记录

- 时间：2026-05-11
- 目标：继续提升主线/claim 边界、方法/证明、实验工程、投稿级数据链和文献证据的完成度。
- 原则：所有新增结果均写入 Round8 隔离目录，不覆盖中文 DOCX 和旧实验包。

## 本轮已执行

- 跑 E2 mixed 工况模块消融 smoke：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/smoke_matrix`
  - 方法：`full_tf14`、`no_bilinear`、`no_online_adapt`、`no_comm_aware`、`no_delay_compensation`、`no_fdi`、`no_ftc_switching`、`no_phase_role`、`zoh_consensus_surrogate`
  - 结果：非辅助方法均 `success=1`，ZOH surrogate 为 `path_not_completed`，按弱底线对照记录。
- 跑 E7 mixed 工况安全/连接 smoke：
  - 方法：`baseline`、`zoh_consensus_surrogate`、`no_comm_aware`、`no_ftc_switching`、`tf14_main`、`tf14_phase_role`
  - 结果：非辅助方法均 `success=1`，ZOH surrogate 为 `path_not_completed`。
- 生成 Round8 gate 表：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/smoke_matrix_gate`
  - Gate 结果：`AKE_status=PARTIAL`、`NonKoopman_baseline=PARTIAL`、`paired_n20=FAIL`、`required_method_success=PASS`、`trace_ids=PARTIAL`。

## 本轮判断

- 实验工程能力继续提升：E2/E7 的方法集、provenance、异常记录、成功率 gate 和图生成链路均可用。
- 投稿级数据已从 smoke 推进到局部正式统计：E3 证书统计和 E7 连接安全统计均已达到 paired `n=20`；但 E0/E2 baseline-facing 主对比、E1 fresh 和 dose/topology 仍未完成。
- 对论文主线和 claim 边界，本轮会新增“可写/不可写/待验证”清单，避免后续中文稿继续过强表述。

## 后续补跑结果

- E3 证书统计：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e3_n20_certificate`
  - Gate 结果：`paired_n20=PASS`、`required_method_success=PASS`、`minimum_group_n=20`
  - 限制：只有 TF14 主方法，不含 AKE/non-Koopman baseline，因此只能支撑证书和安全监测链条，不能单独支撑 baseline 优越性。
- E7 载荷连接安全统计：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e7_n20_connection_safety`
  - Gate 结果：`paired_n20=PASS`、`required_method_success=PASS`、`minimum_group_n=20`
  - 关键结论：TF14 非辅助方法在两个场景均 `20/20` 成功，连接违规为 0，连接利用率显著低于 AKE-M/baseline。
  - 重要边界：E7 不支持“货物受力峰值低于 baseline”；TF14 的受力峰值高于 baseline，只能写成力/力矩被记录、约束监测和安全审计。
- Runner 工程修正：
  - 文件：`tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`
  - 修正：新增 `_safe_status_print`，将长批量状态输出改为容错打印，避免工具 stdout 断开导致 `OSError: [Errno 22] Invalid argument` 中断实验。
  - 影响范围：只影响日志输出韧性，不改变 `_run_one`、`_summary_row`、CSV/JSON 指标定义和图生成逻辑。
- E0 targeted 主对比：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e0_n20_mixed_fault_main_comparison`
  - 状态：后台运行中，目标为 `sine_mixed_fault_noise` 下 `baseline`、`tf14_main`、`tf14_phase_role`、`zoh_consensus_surrogate` 的 20-seed 对比。

## 本轮新增文件

- `claim_method_proof_alignment_zh.md`
- `literature_evidence_matrix_zh.csv`
- `literature_evidence_summary_zh.md`
- `readiness_scorecard_round8_zh.md`
