# Round4 Remaining Schema Readiness Check

## Manifest
- `generated_at`: `None`
- `final_statistics_ready`: `False`
- `minimum_group_n`: `1`
- `num_runs`: `None`
- `experiments`: `None`

## CSV Presence
- summary exists: `True`, rows: `42`, columns: `60`
- runs exists: `True`, rows: `42`, columns: `62`

## Current Required Columns
- missing summary columns: `['RMSE_s', 'RMSE_y', 'full_path_reached']`
- missing Round2 derived/provenance columns: `['comm_trace_id', 'constraint_violation_count', 'failure_type', 'fallback_count', 'fault_trace_id', 'intervention_count', 'method_id', 'nan_class', 'success', 'topology_trace_id']`

## Group Counts
- groups: `42`
- min group n: `1`
- max group n: `1`
- groups with n<20: `42`

## Experiment/Method Coverage
- `E0` methods: `['baseline', 'tf14_error_match', 'tf14_main', 'tf14_phase_role']`
- `E0` scenarios: `['dlc_comm_noise_high', 'dlc_mixed_fault_noise']`
- `E2` methods: `['full_tf14', 'no_bilinear', 'no_comm_aware', 'no_delay_compensation', 'no_fdi', 'no_ftc_switching', 'no_online_adapt', 'no_phase_role', 'no_ppc_progress_guard', 'no_realtime_scheduler', 'no_stable_projection']`
- `E2` scenarios: `['dlc_comm_noise_high', 'dlc_mixed_fault_noise']`
- `E3` methods: `['tf14_phase_role']`
- `E3` scenarios: `['dlc_comm_noise_high', 'dlc_mixed_fault_noise']`
- `E7` methods: `['baseline', 'no_comm_aware', 'no_ftc_switching', 'tf14_main', 'tf14_phase_role']`
- `E7` scenarios: `['dlc_comm_noise_high', 'dlc_mixed_fault_noise']`

## Safety NaN Scan
- missing safety columns in run CSV: `['connection_util_max']`

## Publication Gate Verdict
- FAIL paired n>=20
- FAIL Round2 provenance schema
- FAIL safety columns present
