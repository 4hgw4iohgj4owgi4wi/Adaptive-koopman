# Round4 Execution Report

## 1. What Was Executed

Round4 moved from planning to lightweight execution checks.

Executed:

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --help
```

Result:

- CLI is available.
- Supported experiments: `E0 E2 E3 E7`.
- `E1` is not supported by this runner; it needs a DNN runner.
- Final seeds are controlled by `--full-final-seeds`, i.e. `2026-2045`.
- Safe smoke option exists: `--quick`.

Created and executed read-only schema check:

```powershell
E:\anaconda\envs\pytorch_new\python.exe paper_dcn_tf12_draft\publication_readiness_round4_2026-05-11\check_remaining_schema_readiness.py
```

Output:

`paper_dcn_tf12_draft/publication_readiness_round4_2026-05-11/remaining_schema_readiness_report.md`

## 2. Current Data Gate Results

From the generated readiness report:

| Gate | Result |
|---|---|
| final statistics ready | `False` |
| minimum group n | `1` |
| groups with n < 20 | `42` |
| Round2 provenance columns | missing `comm_trace_id`, `fault_trace_id`, `topology_trace_id`, `method_id`, `success`, `failure_type`, `fallback_count`, `intervention_count`, `nan_class`, etc. |
| safety schema | missing `connection_util_max` under the Round2 expected name; current runner uses `connection_max_utilization`. |
| publication gate | FAIL paired `n>=20`; FAIL Round2 provenance schema; FAIL safety columns present. |

## 3. Important Finding

The current runner writes into the fixed data directory:

`tf14_remaining_experiments_20260509/data`

Even `--quick` may rewrite summary/manifest/figures after skipping or adding runs. Because this can alter the current evidence layer, Round4 did **not** run `--quick` directly in the source directory.

Before running smoke/final experiments, one of these should be done:

1. Add an output-root CLI option to the runner.
2. Copy the runner/data layer to a new dated smoke directory.
3. Accept that the source evidence package will be updated and record this in provenance.

## 4. Current Baseline State

Round3 Worker B concluded that the current local baseline must be treated as:

`AKE-M`

It cannot currently be called:

`AKE-A`

Therefore the manuscript cannot claim:

- superiority over the uploaded AKE baseline;
- superiority over task-adapted AKE;
- strict reproduction of the baseline paper.

## 5. Immediate Engineering Tasks Before Final Runs

| Priority | Task | Why |
|---|---|---|
| P0 | Add or derive T1 provenance fields | Required for fair baseline comparison. |
| P0 | Add credible non-Koopman baseline | Current method set lacks external-family networked-control baseline. |
| P0 | Create E1 fresh training-seed runner | Current E1 is cached/gap-closure only. |
| P0 | Add output-root or copied execution sandbox | Prevents smoke/final commands from overwriting current evidence layer. |
| P0 | Map safety column names and NaN classes | Current `connection_max_utilization` vs expected `connection_util_max` mismatch needs normalization. |
| P0 | Add dose-response/topology runner | DCN topic requires communication sweep and topology recovery evidence. |

## 6. Suggested Next Round

Round5 should perform code-level but bounded changes:

1. Add a non-destructive output root or copied-run workflow for remaining experiments.
2. Add a schema-normalization script that derives Round2-ready CSVs from current runner CSVs.
3. Add a T1 provenance ledger template.
4. If safe, run `--quick` in an isolated copy/output root.
5. Generate a normalized readiness report from the isolated smoke output.

This is the first step where code changes become useful. Until then, more final simulations would not solve the publication blockers.

## 7. Follow-Up Executed After This Report

An isolated runner workflow was created in Round5:

`paper_dcn_tf12_draft/publication_readiness_round5_2026-05-11/run_isolated_remaining_smoke.py`

It copied the remaining-experiment runner to:

`tf14_remaining_smoke_round6_20260511`

The copy excludes the original `data`, `figures`, and `logs` folders, so smoke outputs do not overwrite the source evidence package.

Executed isolated minimum smoke:

```powershell
E:\anaconda\envs\pytorch_new\python.exe paper_dcn_tf12_draft\publication_readiness_round5_2026-05-11\run_isolated_remaining_smoke.py --run-min-e3
```

Result:

- Completed `E3`, seed `2026`, scenario `sine_mixed_fault_noise`, method `tf14_phase_role`.
- Output location: `tf14_remaining_smoke_round6_20260511`.
- `full_path_reached=True`.
- `rmse_lat_mean=0.0395161970019421`.
- `rmse_long_mean=0.4671860941347358`.
- `certificate_ok_ratio=1.0`.
- `certificate_min_margin=0.0036767823770443298`.
- This is a smoke/environment validation only; it is not manuscript evidence.
