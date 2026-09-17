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
| s0_clean_v5 | full_lifted | 2026 | 0.0428 | 0.4178 | +0.0000 | 1.000 | nan | nan |
| s0_clean_v5 | bilinear_no_projection | 2026 | 0.0310 | 0.4187 | +0.0016 | 0.938 | 49.310 | 9.460 |
| s0_clean_v5 | ake_linear_net_koopman | 2026 | 0.0324 | 0.4170 | +0.0030 | 0.975 | 49.259 | 9.460 |
| s0_clean_v5 | raw6_linear | 2026 | 0.2840 | 0.4282 | +0.5075 | 0.028 | 25.739 | 4.740 |
| s1_flt_v5 | full_lifted | 2026 | 0.0444 | 0.4156 | +0.0000 | 1.000 | nan | nan |
| s1_flt_v5 | bilinear_no_projection | 2026 | 0.0324 | 0.4158 | +0.0031 | 0.962 | 61.072 | 11.740 |
| s1_flt_v5 | ake_linear_net_koopman | 2026 | 0.0330 | 0.4145 | +0.0030 | 0.965 | 43.806 | 8.340 |
| s1_flt_v5 | raw6_linear | 2026 | 0.1819 | 0.4129 | +0.4643 | 0.098 | 24.495 | 4.500 |
| s2_hpin_d5_10_v5 | full_lifted | 2026 | 0.3529 | 3.2756 | +0.0000 | 1.000 | nan | nan |
| s2_hpin_d5_10_v5 | bilinear_no_projection | 2026 | 0.3219 | 3.8244 | +0.1447 | 0.815 | 26.594 | 5.640 |
| s2_hpin_d5_10_v5 | ake_linear_net_koopman | 2026 | 0.3530 | 2.7280 | +0.1169 | 0.715 | 42.858 | 9.140 |
| s2_hpin_d5_10_v5 | raw6_linear | 2026 | 0.4907 | 9.5838 | +0.7045 | 0.270 | 17.065 | 3.300 |
