# Round5 Derived Publication Gate Tables

- generated_at: `2026-05-11T08:49:21`
- source_runs: `paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\isolated_e0_allmethods_smoke\data\tf14_remaining_runs.csv`
- source_summary: `paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\isolated_e0_allmethods_smoke\data\tf14_remaining_summary.csv`
- source_manifest_final_statistics_ready: `False`
- source_manifest_minimum_group_n: `1`

## Outputs
- `T2_T3_T5_normalized_existing_runs.csv`
- `group_count_gate_existing_runs.csv`
- `T1_gate_status_existing_runs.csv`
- `figure_provenance_ledger_existing_runs.csv`

## Gate Summary
- AKE_status: PARTIAL (AKE-family surrogate present, but original AKE-A still absent)
- NonKoopman_baseline: PARTIAL (only low-order ZOH surrogate present; still not a publishable physical DMPC baseline)
- paired_n20: FAIL (min_group_n=1)
- trace_ids: PARTIAL (runner exports deterministic scenario/seed IDs; raw external trace files are still not linked)
- method_set_seen: INFO (AKE-M; TF14-ERROR-MATCH; TF14-FULL; TF14-MAIN; ZOH-CONSENSUS-SUR)

## Use Limit
These tables are derived from existing smoke/partial data. They are useful for schema debugging only and must not be used as final manuscript evidence.
