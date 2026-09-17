# Koopman Dimension Ablation Record

## Scope

- Current model: 24D observation features, 31D lifted bilinear Koopman state, stable spectral projection, and bilinear-ridge online correction.
- Koopman-setting baselines: bilinear without stable projection, AKE-style linear adaptive Koopman, and raw six-state identity linear Koopman.
- Non-Koopman controller modules are kept aligned with the current NR-KDCC controller for the isolated Koopman-setting comparison.
- Sampled point sign convention: `sampled point gap(s) = ablation_abs_ey(s) - full_abs_ey(s); positive means the ablation has larger absolute lateral error at that sampled s`.
- Summary worst-gap field: `summary pointwise_worst_gap_vs_full = max_s(ablation_abs_ey(s) - full_abs_ey(s)); positive means the ablation is worse at its worst sampled point. Summary fields pointwise_gap_vs_full and pointwise_max_gap_vs_full are retained as backward-compatible aliases of this worst/max value.`.
- Claim boundary: This ablation is evidence for the contribution of the 24D observation / 31D lifted Koopman state inside this closed-loop controller and communication/fault setting. It must not be stated as Koopman being universally better than all linear models.

## Cases

- `s0_clean_v5`: path=sine, speed=5 m/s, fault=False, comm=none.
- `s1_flt_v5`: path=sine, speed=5 m/s, fault=True, comm=none.
- `s2_hpin_d5_10_v5`: path=hairpin, speed=5 m/s, fault=True, comm=delay_5_10.

## Outputs

- `data/koopman_dim_ablation_summary.csv`: per-run summary and gap fields.
- `data/koopman_dim_ablation_pointwise_gaps.csv`: sampled pointwise gap series for non-reference variants.
- `data/koopman_dim_ablation_runs.csv`: raw run rows before final gap enrichment.
- `data/koopman_model_setting_diagnostics.csv`: offline AKE-style/current Koopman setting diagnostics.
- Summary compatibility: `pointwise_gap_vs_full` and `pointwise_max_gap_vs_full` are legacy aliases of `pointwise_worst_gap_vs_full`.
- `koopman_dim_ablation_quick_comparison.png`: quick visual comparison or fallback explanatory graphic.
- `koopman_model_setting_diagnostics.png`: offline Koopman setting diagnostic graphic.

## Run Selection

- Seeds: 2026.
- Variants: full_lifted, bilinear_no_projection, ake_linear_net_koopman, raw6_linear.

## Quick Numerical Snapshot

| scenario | variant | seed | RMSE_y(m) | RMSE_s(m) | worst_gap(m) | win_ratio | worst_s | worst_t |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| s0_clean_v5 | full_lifted | 2026 | 0.0323 | 0.4243 | +0.0000 | 1.000 | nan | nan |
| s0_clean_v5 | bilinear_no_projection | 2026 | 0.0318 | 0.4247 | +0.0058 | 0.652 | 56.583 | 10.860 |
| s0_clean_v5 | ake_linear_net_koopman | 2026 | 0.0325 | 0.4196 | +0.0045 | 0.442 | 25.884 | 4.740 |
| s0_clean_v5 | raw6_linear | 2026 | 0.2840 | 0.4282 | +0.5506 | 0.027 | 25.789 | 4.740 |
| s1_flt_v5 | full_lifted | 2026 | 0.0330 | 0.4225 | +0.0000 | 1.000 | nan | nan |
| s1_flt_v5 | bilinear_no_projection | 2026 | 0.0329 | 0.4215 | +0.0070 | 0.587 | 53.545 | 10.280 |
| s1_flt_v5 | ake_linear_net_koopman | 2026 | 0.0330 | 0.4170 | +0.0074 | 0.640 | 57.799 | 11.100 |
| s1_flt_v5 | raw6_linear | 2026 | 0.1819 | 0.4129 | +0.5005 | 0.053 | 24.525 | 4.500 |
| s2_hpin_d5_10_v5 | full_lifted | 2026 | 0.3366 | 4.1238 | +0.0000 | 1.000 | nan | nan |
| s2_hpin_d5_10_v5 | bilinear_no_projection | 2026 | 0.3189 | 3.6597 | +0.0225 | 0.845 | 24.346 | 5.100 |
| s2_hpin_d5_10_v5 | ake_linear_net_koopman | 2026 | 0.3415 | 2.5906 | +0.1830 | 0.500 | 41.075 | 8.700 |
| s2_hpin_d5_10_v5 | raw6_linear | 2026 | 0.4907 | 9.5838 | +0.7344 | 0.195 | 17.064 | 3.300 |
