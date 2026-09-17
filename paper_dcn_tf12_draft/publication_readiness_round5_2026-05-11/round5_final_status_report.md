# Round5 Final Status Report

## 1. What Changed

Round5 added practical execution tooling without modifying the core controller or original evidence package.

New files:

| File | Purpose |
|---|---|
| `derive_publication_gate_tables.py` | Derive normalized publication-gate CSVs from existing runner outputs. |
| `run_isolated_remaining_smoke.py` | Copy the remaining-experiment runner into an isolated stage and run safe smoke commands there. |
| `T2_T3_T5_normalized_existing_runs.csv` | Derived normalized run rows from existing smoke/partial data. |
| `group_count_gate_existing_runs.csv` | Group-count gate table showing current `n` per experiment/scenario/method. |
| `T1_gate_status_existing_runs.csv` | T1 fairness gate status from current evidence. |
| `figure_provenance_ledger_existing_runs.csv` | Minimal provenance ledger for current representative figures. |
| `isolated_e3_gate_tables/*` | Gate tables derived from the isolated E3 smoke run. |

Created isolated runner directory:

`tf14_remaining_smoke_round6_20260511`

This directory is separate from `tf14_remaining_experiments_20260509`, so smoke testing does not overwrite the original evidence package.

## 2. What Was Verified

### Original Evidence Package

Derived gate report from existing remaining-experiment data:

`round5_derived_gate_report.md`

Gate result:

| Gate | Result |
|---|---|
| AKE status | FAIL: current baseline is `AKE-M` surrogate; no verified `AKE-A` row. |
| Non-Koopman baseline | FAIL: no Physical-model DMPC or ZOH consensus MPC method row. |
| paired `n>=20` | FAIL: `min_group_n=1`. |
| trace IDs | FAIL: trace IDs are derived placeholders, not runner-exported provenance. |

### Isolated Smoke Run

Executed:

```powershell
E:\anaconda\envs\pytorch_new\python.exe paper_dcn_tf12_draft\publication_readiness_round5_2026-05-11\run_isolated_remaining_smoke.py --run-min-e3
```

Result:

| Field | Value |
|---|---|
| experiment | `E3` |
| seed | `2026` |
| scenario | `sine_mixed_fault_noise` |
| method | `tf14_phase_role` |
| full path reached | `True` |
| lateral RMSE | `0.0395161970019421` |
| longitudinal RMSE | `0.4671860941347358` |
| certificate ok ratio | `1.0` |
| certificate min margin | `0.0036767823770443298` |
| output root | `tf14_remaining_smoke_round6_20260511` |

This verifies that the runner can execute a minimal isolated E3 smoke case in the current environment.

## 3. What This Means for Publication Readiness

Still not publication-ready.

The isolated smoke run proves execution viability, not scientific evidence. The paper still cannot claim:

- superiority over uploaded AKE baseline;
- superiority over task-adapted AKE;
- superiority over networked control methods;
- statistical improvement;
- final safety robustness;
- final DCN communication dose-response robustness.

## 4. Current Hard Blockers

| Blocker | Status | Required Fix |
|---|---|---|
| Verified AKE baseline | Current local status is `AKE-M` only | Implement and verify `Frozen_AKE` / `AKE-A` or keep all baseline claims downgraded. |
| Non-Koopman baseline | Missing | Add Physical-model DMPC or at least ZOH consensus MPC as explicitly weak surrogate. |
| Final statistics | Missing | Run paired `n>=20` only after method set/provenance is fixed. |
| Fresh E1 | Missing | Add DNN training/evaluation runner for Koopman/AKE multi-seed prediction validation. |
| Communication dose/topology | Missing | Add runner grid for delay/dropout/jitter/burst and recoverable topology schedules. |
| Provenance schema | Partial | Add real `comm_trace_id`, `fault_trace_id`, `topology_trace_id`, `method_id`, config hashes, and `nan_class`. |
| Safety T5 | Partial | Ensure no unclassified NaN and same safety fields for all compared methods. |
| Citation records | Pending | Fill DOI/BibTeX/access-date records before writing citation-supported novelty claims. |

## 5. Recommended Next Engineering Step

The next useful code change should be one of:

1. Add `--output-root` to `run_tf14_remaining_experiments.py` so all smoke/final runs can be isolated without copying directories.
2. Add a `NonKoopman_ZOH_consensus` method row as a clearly labeled weak surrogate.
3. Add provenance fields to run rows: `method_id`, `baseline_class`, `comm_trace_id`, `fault_trace_id`, `topology_trace_id`, `success`, `failure_type`, `nan_class`.

Best order:

1. Add `--output-root`.
2. Add provenance fields.
3. Add non-Koopman surrogate.
4. Then run isolated smoke for E0/E2/E3/E7.
5. Only then consider final `n>=20`.

## 6. Safe Manuscript Action Now

Create a Chinese manuscript safety-integration version that:

- updates the narrative and method-proof bridge,
- labels baseline as `AKE-M` unless upgraded,
- includes T1 gates as pending,
- includes figure/table placeholders with `evidence_status`,
- removes or downgrades superiority/statistical/safety claims.

Do not insert current smoke metrics as evidence.
