# 发表 Gate 派生表记录

- 生成时间：`2026-05-11T09:42:42`
- run 明细来源：`paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\smoke_matrix\data\tf14_remaining_runs.csv`
- summary 来源：`paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\smoke_matrix\data\tf14_remaining_summary.csv`
- manifest 中 final_statistics_ready：`False`
- manifest 中 minimum_group_n：`1`

## 输出文件
- `T2_T3_T5_normalized_existing_runs.csv`
- `group_count_gate_existing_runs.csv`
- `T1_gate_status_existing_runs.csv`
- `figure_provenance_ledger_existing_runs.csv`

## Gate 摘要
- AKE_status: PARTIAL (已有 AKE 家族 surrogate，但仍缺原文 AKE-A)
- NonKoopman_baseline: PARTIAL (只有低阶 ZOH surrogate，仍不能替代可发表的物理 DMPC baseline)
- paired_n20: FAIL (min_group_n=1)
- required_method_success: PASS (所有非辅助底线方法均成功)
- trace_ids: PARTIAL (runner 已输出确定性工况/seed trace id，但仍未链接外部原始 trace 文件)
- method_set_seen: INFO (ABL-NO_BILINEAR; ABL-NO_COMM_AWARE; ABL-NO_DELAY_COMPENSATION; ABL-NO_FDI; ABL-NO_FTC_SWITCHING; ABL-NO_ONLINE_ADAPT; ABL-NO_PHASE_ROLE; AKE-M; TF14-FULL; TF14-MAIN; ZOH-CONSENSUS-SUR)

## 使用限制
这些表由当前已有的 smoke 或部分数据派生，主要用于检查 schema、证据链和 gate 状态；在 n=20 正式批次完成前，不能作为论文最终证据。
