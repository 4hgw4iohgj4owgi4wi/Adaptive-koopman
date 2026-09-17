# TF14 remaining experiments

- Generated: 2026-05-11T08:48:45
- Source plan: `D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- Runs: 5
- Experiments present: `E0`
- Final n>=20 ready: `False`
- Data: `D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\isolated_e0_allmethods_smoke\data`
- Figures: `D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\isolated_e0_allmethods_smoke\figures`
- Recommended Python environment: `E:\anaconda\envs\pytorch_new\python.exe`.

## P0 status

- Current rows may be smoke/partial rows unless generated with `--full-final-seeds`; do not cite them as final n=20 statistics.
- Runs are isolated by default: each run bootstraps a fresh notebook namespace. `--reuse-env` is only for fast debugging.
- E0 final multi-seed main comparison: implemented in this runner; use `--experiments E0 --full-final-seeds` for n=20.
- E1 Koopman DNN multi-seed prediction: still needs a separate DNN training/evaluation runner.
- E2 true module ablation: implemented; use `--experiments E2 --full-final-seeds` for n=20 on high-comm/mixed.
- E3 certificate validation: implemented for current certificate recorder; theory-level practical/ISS formula still needs paper-side confirmation.
- E7 same-disturbance payload/connection safety: implemented; smoke rows track force peak/RMS, force rate, connection utilization/violation, and corner load spread.

## Aggregated metrics

| experiment | scenario | method | n | RMSE_y | RMSE_s | full path | step p95 | cert ok | min margin |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| E0 | sine_nominal_clean | baseline | 1 | 0.0486 | 0.4980 | 1.000 | 0.0318 | 0.368 | -1.415e-02 |
| E0 | sine_nominal_clean | tf14_error_match | 1 | 0.0366 | 0.4808 | 1.000 | 0.0527 | 0.360 | -2.260e-02 |
| E0 | sine_nominal_clean | tf14_main | 1 | 0.0411 | 0.4821 | 1.000 | 0.0327 | 0.362 | -2.246e-02 |
| E0 | sine_nominal_clean | tf14_phase_role | 1 | 0.0414 | 0.4821 | 1.000 | 0.0328 | 0.362 | -2.246e-02 |
| E0 | sine_nominal_clean | zoh_consensus_surrogate | 1 | 0.0607 | 14.3059 | 0.000 | 0.0379 | 0.177 | -2.226e+00 |
