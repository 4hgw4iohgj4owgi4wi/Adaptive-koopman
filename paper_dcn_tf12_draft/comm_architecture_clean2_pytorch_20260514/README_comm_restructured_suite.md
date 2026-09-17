# Communication Restructured Scenario Suite 20260513

This runner compares baseline and `tf14_phase_role` under identical scenario overlays.
Fault activation is requested by path coordinate `s`, not by time step.

## Outputs

- `data/comm_restructured_runs.csv`: all per-method run summaries.
- `data/comm_restructured_pointwise_summary.csv`: one baseline-vs-main row per case and seed.
- `data/scenarios/*_summary.csv`: per-case summary CSVs with method rows and pair metrics.
- `data/pointwise/*_pointwise.csv`: per-step lateral-error comparisons.
- `data/core/E9_COMM_RESTRUCT/seed_*/*_core.npz`: core arrays saved by the existing remaining runner.

## Requested Runtime Keys

- Primary Worker 2 communication keys: `comm_restructure_enabled`, `comm_fault_trigger_mode`, `comm_fault_start_s`, `comm_fault_end_s`, `comm_relative_state_delay_steps`, `comm_relative_state_variable_delay_max_steps`, `comm_relative_state_dropout_prob`, `comm_relative_state_noise_std`, `comm_relative_state_bias`, `comm_relative_state_scale`, `comm_relative_distance_noise_std`, `comm_relative_distance_bias`, `comm_relative_distance_scale`, `comm_team_ey_delay_steps`, `comm_team_ey_variable_delay_max_steps`, `comm_team_ey_dropout_prob`, `comm_team_ey_noise_std`, `comm_team_ey_bias`, `comm_team_ey_scale`, `upper_lower_comm_enabled`, `upper_lower_comm_trigger_mode`, `upper_lower_comm_start_s`, `upper_lower_comm_end_s`, `upper_lower_comm_delay_steps`, `upper_lower_comm_variable_delay_max_steps`, `upper_lower_comm_dropout_prob`, `upper_lower_comm_noise_std`, `upper_lower_comm_bias`, `upper_lower_comm_scale`, `upper_lower_comm_ref_delay_steps`, `upper_lower_comm_ref_variable_delay_max_steps`, `upper_lower_comm_ref_dropout_prob`, `upper_lower_comm_ref_noise_std`, `upper_lower_comm_ref_bias`, `upper_lower_comm_ref_scale`.
- Legacy compatibility keys retained for old summaries, not as the delay-scenario criterion: `comm_delay_steps_max`, `comm_delay_bias`, `comm_packet_loss_base`, `comm_packet_loss_gain`, `comm_tighten_max_frac`.
- Fault injection uses existing path-coordinate keys: `fault_trigger_mode='s'` and `fault_start_s`.

## Matrix

- `s0_clean_v2`: path=sine, speed=2 m/s, fault=False, comm=none

Seeds: 2026
