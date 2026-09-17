# 发表 Gate 派生表记录

- 生成时间：`2026-05-11T16:33:17`
- run 明细来源：`paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_n20_mixed_fault_ablation_merged\data\tf14_remaining_runs.csv`
- summary 来源：`paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_n20_mixed_fault_ablation_merged\data\tf14_remaining_summary.csv`
- manifest 中 final_statistics_ready：`True`
- manifest 中 minimum_group_n：`20`

## 输出文件
- `T2_T3_T5_normalized_existing_runs.csv`
- `group_count_gate_existing_runs.csv`
- `T1_gate_status_existing_runs.csv`
- `figure_provenance_ledger_existing_runs.csv`

## Gate 摘要
- AKE_status: FAIL (没有 AKE 家族 baseline 行)
- NonKoopman_baseline: PARTIAL (只有低阶 ZOH surrogate，仍不能替代可发表的物理 DMPC baseline)
- paired_n20: PASS (min_group_n=20)
- required_method_success: FAIL (20 个非辅助方法行失败或崩溃)
- trace_ids: PARTIAL (runner 已输出确定性工况/seed trace id，但仍未链接外部原始 trace 文件)
- method_set_seen: INFO (ABL-NO_BILINEAR; ABL-NO_COMM_AWARE; ABL-NO_DELAY_COMPENSATION; ABL-NO_FDI; ABL-NO_FTC_SWITCHING; ABL-NO_ONLINE_ADAPT; ABL-NO_PHASE_ROLE; ABL-NO_PPC_PROGRESS_GUARD; ABL-NO_REALTIME_SCHEDULER; ABL-NO_STABLE_PROJECTION; TF14-FULL; ZOH-CONSENSUS-SUR)

## 使用限制
当前表已满足 paired n>=20 的基本统计门槛；仍需结合 T1 baseline fidelity、trace provenance 和具体指标方向判断能否写入主文。
