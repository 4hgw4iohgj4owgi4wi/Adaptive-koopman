# Worker A: Runner Capability Audit

Date: 2026-05-11

Scope: read-only audit of runner capability for Round 3 execution preparation. No expensive experiments were run. This file only inspects runner CLI/options/methods/scenarios/outputs and maps them to the Round 2 publication-readiness gates.

## 1. Executive Conclusion

The current runner stack can execute the existing TF14 remaining-experiment suites for `E0`, `E2`, `E3`, and `E7`, including `--full-final-seeds` for the hard-coded seed range `2026-2045`. It is usable as a closed-loop execution backbone, but it is not yet a complete publication/T1 runner because the mandatory T1 method set is incomplete and several final evidence gates are missing.

| Gate / capability | Current support | Audit verdict |
|---|---|---|
| CLI-controlled remaining experiments | `run_tf14_remaining_experiments.py` supports `--experiments`, `--seeds`, `--full-final-seeds`, `--scenarios`, `--quick`, `--force`, and `--reuse-env`. | Supported for existing E0/E2/E3/E7 suites. |
| `n>=20` closed-loop seeds | `P0_SEEDS = range(2026, 2046)` and `--full-final-seeds` select 20 seeds. | Supported mechanically, but final claim still blocked by incomplete method set and existing mixed smoke rows. |
| T1 AKE candidate / Frozen AKE | A method named/displayed as `baseline` / `AKE-baseline` exists, but it is not frozen as `AKE-R`, verified `AKE-A`, or declared `AKE-M`. | Not T1-ready. Name alone is insufficient. |
| Non-Koopman baseline | No `Physical-model DMPC`, `ZOH consensus MPC`, or `NonKoopman_Network_Control` method is present in the audited runner. | Missing. |
| Fresh E1 Koopman/AKE training seeds | The remaining runner explicitly says E1 needs a DNN runner; gap-closure E1 uses cached offline screening. | Missing. |
| Communication dose-response | Fixed high-communication scenarios exist; no CLI grid for delay/dropout/jitter/burst dose sweeps. | Missing for DCN bounded-grid evidence. |
| Topology recovery | No topology schedule/grid CLI, no `topology_trace_id`, and no complete/ring/path/recoverable-edge sweep. | Missing. |
| Diagnostics and outputs | Per-run CSV/NPZ/log/diagnostic exports exist for E0/E2/E3/E7. | Useful backbone, but schema lacks T1 ledger fields, CI fields, trace IDs, `failure_type`, and `nan_class`. |

Primary risk: the runner reads existing `tf14_remaining_runs.csv` and skips completed run IDs unless `--force` is used. Final runs can accidentally mix earlier smoke rows, old `dlc_*` rows, or pre-freeze configs with new `--full-final-seeds` rows. A clean output root or final-run label is needed before publication runs.

## 2. Audited Inputs

| File | Role in this audit |
|---|---|
| `paper_dcn_tf12_draft/publication_readiness_round3_2026-05-11/00_round3_task_tree.md` | Defines Worker A scope and no-expensive-run rule. |
| `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py` | Main closed-loop runner for E0/E2/E3/E7. |
| `tf14_final_gap_closure_20260509/run_tf14_final_gap_closure.py` | Figure/gap pack generator from existing paper/remaining data. |
| `tf14_final_gap_closure_20260509/FULL_FINAL_COMMANDS.md` | Existing final-statistics command list. |
| `tf14_remaining_experiments_20260509/README_zh.md` | Current remaining-run status and n=1 caveat. |
| `tf14_final_gap_closure_20260509/README_zh.md` | Gap-closure status and cached-E1 caveat. |
| `tf14_stage5_phase_role_scenarios_20260507/run_tf14_stage5_phase_role_suite.py` | Source of method/scenario specs imported by the remaining runner. |
| Round 2 readiness docs | Used only to map runner capabilities to T1/non-Koopman/fresh E1/dose/topology gates. |

## 3. Main Runner: CLI and Behavior

Runner: `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`

Evidence: `DATA_DIR`, `FIG_DIR`, and `LOG_DIR` are fixed under `tf14_remaining_experiments_20260509` at lines 22-30. `P0_SEEDS` and default scenario lists are defined at lines 38-42. CLI arguments are defined at lines 1144-1152.

| CLI option | Current behavior |
|---|---|
| `--experiments` | `nargs="+"`, default `["E0"]`; supported branches are `E0`, `E2`, `E3`, `E7`; unsupported experiment IDs are printed as skipped, not hard-failed. Help text states `E1 needs the DNN runner`. |
| `--seeds` | `nargs="+"`, integer list, default `[2026]`; used only when `--full-final-seeds` is not set. |
| `--full-final-seeds` | Replaces requested seeds with `P0_SEEDS = [2026, ..., 2045]`, giving 20 closed-loop seeds. |
| `--scenarios` | Optional list of scenario keys. If omitted, each experiment uses its default scenario list. It filters `stage5._scenario_specs()` and does not create new scenario parameters. Unknown keys appear to produce no new scenario rows rather than a clear error. |
| `--quick` | Sets one seed, scenario `sine_mixed_fault_noise`, and experiments `E0 E2 E3 E7`. This is useful for smoke testing but not publication evidence. |
| `--force` | Reruns existing `(experiment, seed, scenario, method)` rows. Without it, existing rows in `tf14_remaining_runs.csv` are reused/skipped. |
| `--reuse-env` | Reuses notebook namespace by `path_mode`; faster but less isolated. README says isolated default is preferred and `--reuse-env` is for debugging. |

Important behavior: `_run_suite()` reads existing `data/tf14_remaining_runs.csv` before running and builds `completed` from existing rows. This means final commands without `--force` can reuse old rows for overlapping run IDs.

## 4. Supported Experiments, Scenarios, and Methods

### 4.1 Experiment branches

Evidence: experiment branches and method orders are at `run_tf14_remaining_experiments.py` lines 1043-1071.

| Experiment | Default scenarios in runner source | Methods run by branch | Current purpose |
|---|---|---|---|
| `E0` | `sine_nominal_clean`, `sine_comm_noise_high`, `sine_single_fault_v2`, `sine_mixed_fault_noise` | `baseline`, `tf14_main`, `tf14_phase_role`, `tf14_error_match` | Main comparison skeleton. |
| `E2` | `sine_comm_noise_high`, `sine_mixed_fault_noise` | `full_tf14`, `no_bilinear`, `no_stable_projection`, `no_online_adapt`, `no_comm_aware`, `no_delay_compensation`, `no_fdi`, `no_ftc_switching`, `no_phase_role`, `no_realtime_scheduler`, `no_ppc_progress_guard` | Module ablation skeleton. |
| `E3` | `sine_nominal_clean`, `sine_comm_noise_high`, `sine_single_fault_v2`, `sine_mixed_fault_noise` | `tf14_phase_role` | Certificate validation skeleton. |
| `E7` | `sine_comm_noise_high`, `sine_mixed_fault_noise` | `baseline`, `no_comm_aware`, `no_ftc_switching`, `tf14_main`, `tf14_phase_role` | Payload/connection safety skeleton. |

### 4.2 Scenario definitions

Evidence: `stage5._scenario_specs()` defines the current source-level scenario keys and updates at `tf14_stage5_phase_role_scenarios_20260507/run_tf14_stage5_phase_role_suite.py` lines 220-288.

| Scenario key | Path mode | Main updates | Audit note |
|---|---|---|---|
| `sine_nominal_clean` | `sine` | No fault; packet loss and delay set to zero. | Supported by current source. |
| `sine_comm_noise_high` | `sine` | Packet-loss base/gain `0.10/0.28`, max delay `5` steps, delay bias `0.55`, tighten max fraction `0.28`. | Fixed high-comm scenario, not a dose grid. |
| `sine_single_fault_v2` | `sine` | Vehicle index `1`, both-channel fault, start step `260`, start time `24.0 s`, `ax/delta` scale `0.58`, no comm degradation. | Fixed fault scenario. |
| `sine_mixed_fault_noise` | `sine` | Same fault type plus packet-loss base/gain `0.09/0.26`, max delay `4` steps, delay bias `0.48`. | Fixed mixed scenario, not topology/dose. |

Current persisted data/README also show `dlc_comm_noise_high` and `dlc_mixed_fault_noise` smoke rows. However, the current audited `stage5._scenario_specs()` source exposes only `sine_*` keys. Treat existing `dlc_*` rows as legacy/existing evidence unless a current source path for fresh `dlc_*` generation is restored or confirmed.

### 4.3 Method definitions

Evidence: Stage5 base methods are at `run_tf14_stage5_phase_role_suite.py` lines 145-217. Remaining-runner method builders are at `run_tf14_remaining_experiments.py` lines 349-453.

| Method key | Current origin | Meaning in runner | T1 interpretation |
|---|---|---|---|
| `baseline` | Stage5 `MethodSpec("baseline", "AKE-baseline", baseline)` | Disables online adaptation, adaptive weight, dynamic PPC, comm-aware modules, FDI/FTC, and fault redistribution. | A local AKE-like/Koopman-MPC baseline label, but not proven `AKE-R`, verified `AKE-A`, or declared `AKE-M`. |
| `tf14_main` | Stage5 main config plus remaining-runner online adaptation enabled | Current proposed-ish TF14 main stack without phase-role scheduler. | Candidate `Proposed` component, but method ID/provenance not frozen. |
| `tf14_phase_role` | Stage5 phase-role config plus remaining-runner online adaptation enabled | TF14 with phase-role scheduler and comm tightening/fallback. | Best current full-method candidate, but not explicitly named `Proposed` in T1 schema. |
| `tf14_error_match` | Stage6 update on base method | Error-match tuned variant. | Development/comparison variant, not a mandatory T1 method. |
| `full_tf14` | E2 alias of `tf14_phase_role` updates | Full method for E2 ablation reference. | Useful ablation reference. |
| `no_bilinear` | E2 variant | Sets `koopman_structure = "linear"`. | Optional ablation; not a non-Koopman baseline. |
| `no_stable_projection` | E2 variant | Disables stable projected A. | Optional ablation. |
| `no_online_adapt` | E2 variant | Disables online model adaptation. | Optional ablation. |
| `no_comm_aware` | E2/E7 variant | Disables comm-quality consensus, delay compensation, comm constraint tightening, and degraded fallback. | Maps partly to `NoCommAware`; currently not fully formalized in T1 ledger. |
| `no_delay_compensation` | E2 variant | Disables delay compensation only. | Maps partly to `NoDelay`/delay ablation but does not set communication trace to no-delay nominal. |
| `no_fdi`, `no_ftc_switching`, `no_phase_role`, `no_realtime_scheduler`, `no_ppc_progress_guard` | E2/E7 variants | Module removals. | Optional/recommended ablations, not substitutes for T1 baseline or NonKoopman. |

## 5. Outputs and Current Schema

Evidence: core/diagnostic output functions are at `run_tf14_remaining_experiments.py` lines 278-336. Summary rows and aggregated metrics are at lines 491-587. Manifest outputs are at lines 1118-1139. Plot saving is at lines 590-592.

| Output | Current path / pattern | Contents |
|---|---|---|
| Runs CSV | `tf14_remaining_experiments_20260509/data/tf14_remaining_runs.csv` | Per-run summary rows including experiment, seed, scenario, method, display name, log path, tracking/runtime/comm/certificate/safety/force fields where available. |
| Summary CSV | `tf14_remaining_experiments_20260509/data/tf14_remaining_summary.csv` | Grouped by experiment/scenario/method with `num_runs`, mean, and std for selected metrics. |
| Manifest JSON | `tf14_remaining_experiments_20260509/data/tf14_remaining_manifest.json` | Requested experiments, scenarios/methods present, seeds, final-statistics readiness, output paths, and this-invocation runs. |
| Per-run log | `tf14_remaining_experiments_20260509/logs/<experiment>/seed_<seed>/<scenario>_<method>.log` | Redirected stdout/stderr for each run. |
| Core NPZ | `tf14_remaining_experiments_20260509/data/core/<experiment>/seed_<seed>/<scenario>_<method>_core.npz` | State/reference/input/runtime arrays. |
| Diagnostics | `tf14_remaining_experiments_20260509/data/diagnostics/<experiment>/seed_<seed>/<scenario>_<method>/` | Optional `certificate.csv`, `comm.csv`, `connection.csv`, `fault.csv`, `fdi.csv`, `switch.csv`, `control_spread.csv`, `payload_force.csv`, `phase_role.csv`, and `summary.json`. |
| Figures | `tf14_remaining_experiments_20260509/figures/*.png|pdf|svg` | R0/R2/R3/R7 plots generated from current runs and existing rows. |
| README | `tf14_remaining_experiments_20260509/README_zh.md` | Auto-written summary with status notes. |

Current schema gaps relative to Round 2/T1:

| Required field family | Current state | Needed change |
|---|---|---|
| T1 method provenance | No `method_id`, `ake_status`, `baseline_class`, config hash, frozen timestamp, or tuning budget fields. | Add T1 baseline/method ledger and join it into every run row. |
| Paired trace IDs | No explicit `comm_trace_id`, `fault_trace_id`, `topology_trace_id`, split hash, or same-trace guarantee columns. | Add seeded trace ledger and per-run trace IDs. |
| CI / paired deltas | Summary gives mean/std only; no 95% CI, paired test/bootstrap, or paired full-reference deltas. | Add post-processing or runner summary for CI and paired deltas. |
| Failure accounting | Has `fail_total` and solver counts, but no common `success`, `failure_type`, `missing_log`, or failure policy row. | Add explicit success/failure schema and keep failed rows. |
| NaN gate | No `nan_class` field. Some fields are structurally NaN for non-applicable diagnostics. | Add `nan_class = none/failure/not_applicable/missing` and figure-specific gates. |
| Topology | No topology fields. | Add topology schedule, trace ID, and recovery metrics. |

Current README/manifest status: `tf14_remaining_experiments_20260509/README_zh.md` says `Final n>=20 ready: False`, current rows are smoke/partial unless generated with `--full-final-seeds`, and E1 still needs a separate DNN runner. The current manifest shows `minimum_group_n = 1`, `final_statistics_ready = false`, and seeds `[2026]`.

## 6. Gap-Closure Runner Capability

Runner: `tf14_final_gap_closure_20260509/run_tf14_final_gap_closure.py`

This script has no argparse CLI. Running it always executes the same gap-pack workflow and writes multiple files/directories under `tf14_final_gap_closure_20260509`.

Evidence: input roots are at lines 22-39; E1 cached plot function is at lines 177-240; final command writer is at lines 520-536; README/granularity/manifest writing is at lines 539-672.

| Capability | Current behavior | Audit verdict |
|---|---|---|
| E1 figure | Reads `tf14_paper_figures_20260508/source/fig03_prediction_model_comparison.npz`, writes `E1_koopman_prediction_validation.csv` and figure. The title states cached offline screening. | Useful for mechanism illustration only; not fresh E1. |
| E2 heatmaps | Reads remaining summary CSV and writes positive=worse heatmaps. | Depends on existing remaining data; not final if remaining data are n=1. |
| E3 certificate distribution | Reads E3 diagnostic `certificate.csv` files. | Useful once E3 final data exist; current pack is smoke/evidence. |
| E7 force/corner timelines | Reads E7 `payload_force.csv` diagnostics. | Useful once E7 final data exist; current pack is smoke/evidence. |
| Final commands | Rewrites `FULL_FINAL_COMMANDS.md`. | Command list only; not a runner capability for missing T1/E1/dose/topology. |
| Copy/archive layer | Rebuilds `extra_saved_figures` via deletion and copy. | Do not run in Worker A; side effects exceed assigned output file. |

Gap-closure README and manifest both explicitly state that current gap figures are not a replacement for full `n>=20` final-statistics runs and that E1 uses cached offline screening rather than fresh multi-seed DNN retraining.

## 7. Directly Runnable Commands

These commands are directly supported by current scripts, but the final-statistics commands are expensive and were not run by Worker A.

### 7.1 Smoke / capability commands

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --quick
```

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --seeds 2026 --scenarios sine_nominal_clean
```

Notes: These commands still run simulations and write to the existing remaining-experiment data/figure/log directories. They are not pure dry-runs.

### 7.2 Existing full-final command list

These commands are in `FULL_FINAL_COMMANDS.md` and generated by the gap-closure script:

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E2 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E3 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E7 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_final_gap_closure_20260509\run_tf14_final_gap_closure.py
```

Publication caveat: these commands still do not include Frozen AKE status, NonKoopman baseline, fresh E1, dose-response, or topology recovery. Also, because existing rows are skipped by default, they should not be used as final publication commands until output isolation or `--force`/fresh-run policy is decided.

## 8. T1 / Publication-Gate Capability Assessment

### 8.1 T1 AKE candidate support

Current support: partial naming only.

The `baseline` method is displayed as `AKE-baseline`, but the audited code does not freeze or label it as `AKE-R`, verified `AKE-A`, or `AKE-M`. Its config disables multiple TF14/proposed modules, but there is no architecture-fidelity checklist, no canonical AKE reproduction record, no online `Delta A`/`Delta B` correction log, no T1 parameter row, and no frozen config hash. Therefore, it cannot yet be used as a primary AKE comparison.

Minimum interpretation today: `baseline` is a local AKE-like/Koopman-MPC comparator candidate. Whether it should become candidate `AKE-A` or downgraded `AKE-M` is a separate Worker B decision and requires implementation/provenance evidence not present in the runner.

### 8.2 Non-Koopman baseline support

Current support: missing.

No audited method corresponds to `NonKoopman_Network_Control`, `Physical-model DMPC`, `physical MPC + ZOH consensus`, or `ZOH consensus MPC`. Existing `no_bilinear` only changes Koopman structure to linear; it remains within the Koopman-family runner and is not a credible non-Koopman network-control baseline.

### 8.3 `n>=20` support

Current support: mechanically supported for E0/E2/E3/E7.

`--full-final-seeds` selects the 20 seeds `2026-2045`, and the manifest marks `final_statistics_ready = min(group_n) >= 20`. However, this is only a mechanical readiness flag. It does not verify T1 method set completeness, same trace policy, confidence intervals, no-NaN classification, or publication claim validity.

Operational issue: old rows can remain in the same CSV and be reused/skipped. Final runs should use a clean final output root or force rerun after method/config freeze.

### 8.4 Fresh E1 support

Current support: missing.

The remaining runner help text states that E1 needs a DNN runner. The gap-closure E1 figure is cached offline screening from an existing NPZ and the gap-closure manifest says it is not fresh multi-seed DNN retraining. No current audited script provides `train_seed` loops, fresh model directories, Frozen_AKE/proposed same-split training, or `E1_koopman_fresh_runs.csv`.

### 8.5 Communication dose-response support

Current support: fixed scenarios only.

The runner has fixed communication-degraded scenarios with hard-coded packet-loss and delay parameters. It does not expose `delay_ms`, `dropout_pct`, `jitter_ms`, `burst_length`, `comm_grid`, or trace-ID generation on the CLI. It therefore cannot directly run the Round 2 bounded communication grid `{0,50,100,200} ms x {0,5,10,20}% dropout` with paired trace reuse.

### 8.6 Topology recovery support

Current support: missing.

No audited runner exposes topology schedules such as `complete`, `ring`, `path`, `single_edge_loss_recoverable`, or `intermittent_edge_recoverable`. No output schema contains `topology_trace_id`, topology disconnect count, recovery time, dwell-time, or leader-lost/stress-test separation.

## 9. Minimal Code / Configuration Change List

These are the smallest changes needed before running expensive final experiments. They should be done before any `--full-final-seeds` publication run.

| Priority | Change | Minimal implementation target |
|---:|---|---|
| 1 | Add final output isolation | Add `--output-root` or `--run-label` so final frozen runs do not mix with existing smoke/legacy rows. Alternatively add a documented `--force` plus clean archive policy, but a separate output root is safer. |
| 2 | Add T1 method ledger | Emit `T1_baseline_fairness.csv/md` or equivalent with `method_id`, `display_label`, `baseline_class`, `ake_status`, `config_path`, `config_hash`, data/training budget, horizon, solver, constraints, allowed information, seed policy, and freeze timestamp. |
| 3 | Rename/formalize method IDs | Map current `tf14_phase_role` or `full_tf14` to `Proposed`; map current/future AKE comparator to `Frozen_AKE`; map `no_delay_compensation`/no-delay trace to `NoDelay`; map `no_comm_aware` to `NoCommAware`. Keep old display labels only as aliases. |
| 4 | Implement or freeze AKE comparator | If `AKE-A`, add architecture-fidelity evidence, online `Delta A`/`Delta B` adaptation logging, MPC coupling evidence, and same data/solver/constraint/trace policy. If not verifiable, freeze as `AKE-M` with explicit missing components. |
| 5 | Add Non-Koopman method | Implement at least `ZOH consensus MPC` as the lowest surrogate, or preferably `Physical-model DMPC`, under the same scenario/seed/trace/constraint/logging interface. |
| 6 | Add fresh E1 runner | New E1 script or branch with train seeds `3101-3105` minimum and `3101-3110` target; output `E1_koopman_fresh_runs.csv`, `E1_koopman_fresh_summary.csv`, model/log paths, split/config hashes, and training failure rows. |
| 7 | Add communication dose grid | Add CLI/config for bounded delay/dropout/jitter/burst grid, deterministic `comm_trace_id`, and `T4_comm_envelope.csv`; keep 400 ms/40% dropout as stress-test only. |
| 8 | Add topology recovery grid | Add topology schedule config/CLI, deterministic `topology_trace_id`, recovery/dwell metrics, and stress-test separation for leader-lost or unrecoverable disconnect. |
| 9 | Add final CSV schema fields | Add `run_id`, `method_id`, `ake_status`, `seed_train`, `seed_closed_loop`, `seed_comm`, `seed_disturbance`, `comm_trace_id`, `fault_trace_id`, `topology_trace_id`, `success`, `failure_type`, `nan_class`, config hash, and artifact hashes. |
| 10 | Add validation guards | Fail fast on unknown scenario keys, unsupported experiments requested as final, missing method rows, missing diagnostics, unclassified NaN, missing logs, or group `n<20` for main-claim outputs. |

## 10. Worker A Handoff

Safe to run now for development or smoke: existing E0/E2/E3/E7 runner commands, with the understanding that they write into the current data directory and are not publication-final.

Not safe to run as final publication evidence yet: any `--full-final-seeds` command, because T1 AKE status, NonKoopman baseline, fresh E1, dose grid, topology grid, trace ledger, and final schema gates are not closed.

Recommended next step before expensive runs: freeze the method schema and output isolation first, then add NonKoopman and T1/AKE status, then dry-run one seed to validate CSV/diagnostic schemas before launching `2026-2045`.
