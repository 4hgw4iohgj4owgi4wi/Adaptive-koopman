# Koopman Dimension Ablation Record

## Scope

- Full model: 24D observation features and the learned lifted Koopman state (expected 31D).
- Ablation model: raw six-state identity lifting with a direct linear Koopman fit in closed loop.
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
- Summary compatibility: `pointwise_gap_vs_full` and `pointwise_max_gap_vs_full` are legacy aliases of `pointwise_worst_gap_vs_full`.
- `koopman_dim_ablation_quick_comparison.png`: quick visual comparison or fallback explanatory graphic.

## Run Selection

- Seeds: 2026.
- Variants: full_lifted, raw6_linear.

## Quick Numerical Snapshot

| scenario | variant | seed | RMSE_y(m) | RMSE_s(m) | worst_gap(m) | win_ratio | worst_s | worst_t |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| s0_clean_v5 | full_lifted | 2026 | 0.0323 | 0.4251 | +0.0000 | 1.000 | nan | nan |
| s0_clean_v5 | raw6_linear | 2026 | 0.2840 | 0.4282 | +0.5464 | 0.022 | 25.853 | 4.760 |
| s1_flt_v5 | full_lifted | 2026 | 0.0332 | 0.4171 | +0.0000 | 1.000 | nan | nan |
| s1_flt_v5 | raw6_linear | 2026 | 0.1819 | 0.4129 | +0.5028 | 0.053 | 24.572 | 4.520 |
| s2_hpin_d5_10_v5 | full_lifted | 2026 | 0.3357 | 3.9702 | +0.0000 | 1.000 | nan | nan |
| s2_hpin_d5_10_v5 | raw6_linear | 2026 | 0.4907 | 9.5838 | +0.7337 | 0.188 | 17.055 | 3.300 |
