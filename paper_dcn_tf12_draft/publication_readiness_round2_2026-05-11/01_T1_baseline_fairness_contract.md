# T1 Baseline Fairness Contract

Date: 2026-05-11

Scope: This contract freezes the minimum fairness requirements before the manuscript may claim experimental superiority over the uploaded baseline paper, *Adaptive Koopman Embedding for Robust Control of Complex Nonlinear Dynamical Systems* (AKE). It is written for direct use in the experiment setting section or appendix.

T1 status: not passed until the AKE baseline status, mandatory method set, parameter table, run logs, paired seeds, and confidence intervals are frozen and archived.

## 1. AKE Baseline Status Definitions

The manuscript must label every AKE comparison as one of the following three states. The label must appear in the experiment table, figure caption provenance, and supplementary run log.

| Label | Definition | Minimum evidence | Allowed manuscript wording |
|---|---|---|---|
| `AKE-R` | Strict reproduced AKE baseline. The authors' released code/data/config or an independently validated reimplementation reproduces the baseline paper's nominal AKE behavior on at least one canonical setting before being run on our cooperative-transport task. | Baseline source/commit, canonical reproduction result, fixed AKE hyperparameters, same plant/task adaptation protocol, run logs. | "Reproduced AKE baseline" and "compared with reproduced AKE under the same T1 protocol." |
| `AKE-A` | Candidate task-adapted AKE baseline state. It records an intended AKE adaptation, but it is not a primary baseline until AKE architecture fidelity, online `Delta A`/`Delta B` correction, MPC coupling, and the same data/horizon/solver/dt/constraints/communication traces/seeds/tuning budget are all verified. The original paper's exact experimental results are not claimed as reproduced. | Written mapping from AKE modules to our plant, architecture fidelity checklist, online adaptation logs for `Delta A`/`Delta B`, MPC integration evidence, frozen implementation/config, same data/horizon/solver/dt/constraints/communication traces/seeds/tuning budget as Proposed. | Before verification: "candidate task-adapted AKE baseline pending fidelity checks." After all checks pass: "verified task-adapted AKE baseline under identical cooperative-transport/DCN settings." |
| `AKE-M` | Matched surrogate baseline. A Koopman-MPC baseline is matched for capacity, data, solver, and tuning budget, but one or more essential AKE components cannot be verified or faithfully adapted. | Explicit missing AKE component list, matched model capacity, equal budget, frozen config, run logs. | "Matched Koopman-MPC surrogate inspired by AKE"; do not call it reproduced AKE. |

Round-2 working rule for this manuscript: do not treat `AKE-A` as the recommended primary baseline by default. Use `AKE-A` only as a candidate baseline state while fidelity checks are pending. Promote it to a primary T1 baseline only after all four verification items pass: the AKE architecture is faithful, online `Delta A`/`Delta B` correction is implemented and logged, the adapted model is actually coupled into MPC, and data/constraints/horizon/solver/dt/communication traces/seeds/tuning budget are identical to the Proposed method. If any item cannot be verified, or if the method requires unmatched data, privileged measurements, different constraints, or incompatible MPC coupling, the frozen baseline must be downgraded to `AKE-M`. Upgrade to `AKE-R` only after canonical reproduction is documented.

The frozen AKE baseline must not include any proposed communication-aware modules, including delay-compensated consensus prediction, timestamp-based neighbor prediction, link-quality consensus weighting, communication-aware fallback, or proposed safety/FTC logic unless the same module is also part of the original AKE algorithm or is explicitly marked as a shared outer wrapper.

## 2. Main-Text Claim Boundary

Before T1 passes, the main text may claim only mechanism-level differences:

| Allowed before T1 | Not allowed before T1 |
|---|---|
| The proposed method adds communication-aware cooperative-transport modules not present in the AKE paper's original scope. | "The proposed method outperforms AKE." |
| The AKE paper provides an adaptive Koopman-MPC reference point for nonlinear robust control. | "The proposed method is superior to the state of the art." |
| A fair comparison requires identical data, horizon, solver, sampling period, constraints, communication traces, seeds, and tuning budget. | "AKE fails under degraded communication" unless shown under T1 and limited to the tested task. |
| Current experiments are pending or preliminary until T1 logs and confidence intervals are complete. | Any abstract/conclusion claim of baseline superiority based on smoke, cached, single-seed, or mismatched settings. |

After T1 passes, the main text may claim only the following, and only for the reported scenarios:

| Condition | Allowed claim |
|---|---|
| `AKE-R` or verified `AKE-A` passes all fairness gates with paired statistics. | "Under the T1 protocol, the proposed method reduces [specific metric] relative to [AKE-R/verified AKE-A] on [specific scenario], with [95% CI or paired-test result]." |
| `AKE-M` is the only available AKE-like comparator. | "The proposed method is compared with a matched Koopman-MPC surrogate; this does not constitute a reproduced comparison against the original AKE implementation." |
| A credible non-Koopman networked-control baseline is included and passes gates. | "The improvement is not only relative to a Koopman-family baseline; it is also evaluated against [Physical-model DMPC or equivalent networked-control baseline] under the same network traces." |
| Only `ZOH consensus MPC` is available as the non-Koopman comparator. | "ZOH consensus MPC is reported as a lowest network-control surrogate; it does not justify a general claim of superiority over networked-control methods." |

The manuscript must not claim global asymptotic stability, arbitrary delay/dropout tolerance, complete fault tolerance, guaranteed safety under all network failures, exact finite-dimensional Koopman representation, or failure of the original AKE paper outside the tested cooperative-transport protocol.

## 3. Fairness Gates

T1 passes only if all gates below are satisfied or explicitly marked as a downgrade that weakens the claim.

### 3.1 Causal Information Boundary

All methods, including `Proposed`, `Frozen_AKE`, non-Koopman baselines, ablations, fallback policies, and post-processors, must respect the same causal observation boundary.

| Boundary item | Required rule | Forbidden use |
|---|---|---|
| Future communication degradation | Controllers may use only current and past timestamps, received packets, estimated delays, and link-quality histories available at decision time. | Future dropout, future delay, future jitter, future topology switches, or future recovery times. |
| Future leader or neighbor loss | A method may react to loss only after it is observable through the same trace and timestamp rules. | Future leader-loss labels, oracle disconnect duration, or scripted knowledge of reconnection time. |
| Recovery and fallback | Recovery logic must be triggered by causal measurements or declared estimates shared under the same protocol. | Oracle recovery flags, perfect fault classification unavailable to other methods, or post-hoc switching based on full-run outcomes. |
| Measurements | Every compared method receives the same delayed/lost/noisy measurements unless a field is explicitly marked as unavailable to that method and the row is downgraded. | Clean privileged measurements, clean neighbor states, or proposed-only latent variables supplied to a baseline. |

Any violation of this boundary invalidates primary T1 claims. The affected row must be marked `claim_level = preliminary` or removed from main-text comparisons.

### 3.2 Gate Table

| Gate | Contract |
|---|---|
| Same plant and task | All methods run on the same cooperative-transport plant, payload, vehicle count, reference trajectory, initial-condition distribution, disturbance model, and evaluation window. |
| Same data | Offline Koopman/AKE training uses the same state-input observations, excitation policy, train/validation/test split, normalization, measurement noise model, and data budget. Proposed-only labels or communication features must not be given to AKE unless marked as shared observations available to all methods. No method may receive clean privileged measurements outside the causal boundary. |
| Same horizon | MPC prediction horizon, control horizon, terminal handling, simulation length, warm-up period, and evaluation interval are identical across compared methods. |
| Same solver | Use the same solver family and settings whenever technically possible: solver name/version, tolerances, maximum iterations, warm start, infeasibility handling, and timeout policy. If a solver mismatch is unavoidable, the comparison is not a primary superiority claim. |
| Same sampling period | Control sampling period, plant integration step, communication update step, zero-order hold policy, and logging frequency are identical. |
| Same constraints | State, input, payload force, connection, collision, actuator, and safety constraints are identical. If a method cannot encode a constraint internally, violations must still be measured against the same constraint set. |
| Same communication trace | Delay, dropout, burst loss, jitter, topology changes, link quality, timestamp availability, and leader/neighbor-loss events come from the same trace files or seeded generator outputs. AKE and non-comm-aware baselines receive the same delayed/lost observations, not clean privileged measurements or future trace labels. |
| Same seed and CI | Closed-loop evaluation uses paired seeds for initial conditions, references, disturbances, communication traces, and training seeds. Minimum `n_closed_loop >= 20` paired runs for main metrics; fresh Koopman/AKE training seeds `n_train >= 5`, target `n_train >= 10`. Report mean, standard deviation, 95% CI, and paired test or bootstrap CI. |
| Same tuning budget | Each method receives the same predeclared hyperparameter-search budget: number of trials, time budget, validation scenarios, selection metric, and early-stop rule. No method may be tuned on the final test set. |
| Same failure policy | Solver failure, timeout, collision, payload/connection violation, fallback activation, and out-of-bound tracking are logged with the same failure criteria. Failed runs remain in aggregate statistics. |
| Same compute accounting | Hardware, software environment, solver runtime, p95 solve time, overrun count, and communication/message overhead are logged for all methods. |
| Freeze before test | Configs, code commits, seeds, traces, and selected hyperparameters are frozen before final test runs. Any post-hoc change restarts T1. |

## 4. Mandatory Method Set

The main T1 comparison must include all methods below. Missing any required method downgrades the main claim to preliminary.

| Method ID | Required role | Definition | Use in claims |
|---|---|---|---|
| `Proposed` | Primary method | Full proposed bilinear Koopman learning and delay-compensated consensus MPC with communication-aware prediction/weights, safety/fallback, and FTC modules that are claimed in the manuscript. | May support main claims only after all gates pass. |
| `Frozen_AKE` | Primary Koopman baseline | Frozen `AKE-R`, verified `AKE-A`, or `AKE-M` baseline. Must use offline nominal Koopman learning, verified online adaptive correction when claimed, and MPC, but no proposed communication-aware modules. | Primary baseline only if status is `AKE-R` or verified `AKE-A`; surrogate-only if `AKE-M`. |
| `NonKoopman_Network_Control` | Required external-family baseline | At least one non-Koopman networked-control baseline, preferably `Physical-model DMPC` if a credible physical model is available. `ZOH consensus MPC` is permitted only as the lowest surrogate when no credible physical-model DMPC or equivalent networked-control method is available. | Prevents the paper from claiming superiority only over a Koopman-family comparator. If only ZOH is available, claims are limited to "relative to a lowest surrogate" and must not generalize to "networked-control methods." |
| `NoDelay` | Communication upper-bound ablation | Proposed control stack under identical scenario with communication delay/dropout/jitter removed or set to the nominal no-delay trace. | Used to calibrate the cost of communication degradation; not a degraded-network baseline. |
| `NoCommAware` | Mechanism ablation | Proposed stack with communication-aware modules disabled: no delay compensation, no timestamp-based neighbor prediction, no link-quality consensus weighting, and no communication-aware fallback logic, while receiving the same degraded traces. | Supports the claim that the DCN-specific module matters. |

Optional but recommended ablations: `NoBilinear`, `NoFTC`, `NoSafetyGuard`, and `OnlineAdaptationOff`. These are not substitutes for the mandatory method set.

## 5. T1 Parameter Table Schema

The paper appendix should include one row per method-scenario pair. Every field below is required unless marked `optional`.

| Field | Type/example | Requirement |
|---|---|---|
| `experiment_id` | string | Unique T1 experiment identifier. |
| `method_id` | enum | `Proposed`, `Frozen_AKE`, `NonKoopman_Network_Control`, `NoDelay`, `NoCommAware`, or approved optional ablation. |
| `ake_status` | enum/null | `AKE-R`, `AKE-A`, `AKE-M`, or `null` for non-AKE methods. |
| `scenario_id` | string | Nominal, bounded communication, single fault, mixed degradation, or stress-test scenario. |
| `plant_config_id` | string/hash | Vehicle count, payload, physical parameters, integration step, disturbance model. |
| `reference_id` | string/hash | Reference trajectory and timing profile. |
| `training_data_id` | string/hash | Dataset source, excitation policy, split, normalization, noise model. |
| `n_train_seeds` | integer | Number of fresh training seeds used for Koopman/AKE models. |
| `n_closed_loop_seeds` | integer | Number of paired closed-loop seeds; main claims require at least 20. |
| `dt_control` | seconds | Control sampling period. |
| `dt_plant` | seconds | Plant integration step. |
| `dt_comm` | seconds | Communication update/logging period. |
| `mpc_prediction_horizon` | integer | Same value across primary methods. |
| `mpc_control_horizon` | integer | Same value across primary methods. |
| `solver_name_version` | string | Solver family and version, e.g., OSQP/SQP wrapper if used. |
| `solver_settings` | JSON/string | Tolerances, max iterations, warm start, timeout, infeasibility handling. |
| `cost_weights` | JSON/hash | Tracking, force, input, smoothness, terminal, and consensus weights. |
| `constraint_set_id` | string/hash | State/input/force/connection/collision/safety bounds. |
| `comm_trace_id` | string/hash | Delay/dropout/burst/jitter/topology/link-quality/timestamp trace. |
| `koopman_representation` | enum/null | Linear, bilinear, adaptive linear, adaptive bilinear, or null. |
| `lift_dim` | integer/null | Lifted-state dimension. |
| `network_architecture` | string/null | Encoder/lifting/projection/adaptation architecture. |
| `online_adaptation` | boolean | Whether online `Delta A`/`Delta B` adaptation is enabled. |
| `adaptation_window` | integer/null | Online adaptation window size. |
| `adaptation_epochs` | integer/null | Epochs/steps per online adaptation update. |
| `regularization` | JSON/null | L1/L2 or ridge penalties for nominal/adaptive networks. |
| `tuning_budget_id` | string/hash | Hyperparameter grid/trials/time budget/selection metric. |
| `frozen_config_hash` | string/hash | Hash of the final config used for test runs. |
| `code_commit_or_snapshot` | string/hash | Code version or archived snapshot. |
| `frozen_at` | timestamp | Time when this row was frozen before testing. |
| `claim_level` | enum | `main`, `supplement`, `surrogate_only`, `representative`, `stress_test`, or `preliminary`. |

## 6. Experiment Log Field Schema

Each run must produce a machine-readable log row. The log schema below is the minimum needed for reviewer audit and CI aggregation.

| Field | Type/example | Requirement |
|---|---|---|
| `run_id` | string | Unique run identifier. |
| `experiment_id` | string | Links to the parameter table. |
| `timestamp_start`, `timestamp_end` | timestamp | Run timing. |
| `method_id`, `ake_status`, `scenario_id` | enum/string | Must match parameter table. |
| `code_commit_or_snapshot`, `frozen_config_hash` | string/hash | Must match frozen T1 config. |
| `seed_train`, `seed_closed_loop`, `seed_comm`, `seed_disturbance` | integer | Paired seed traceability. |
| `training_data_hash`, `reference_hash`, `comm_trace_hash`, `constraint_set_hash` | string/hash | Provenance for data, task, network, and constraints. |
| `initial_state` | JSON/array | Initial vehicle/load state. |
| `payload_config` | JSON/hash | Payload parameters and load distribution. |
| `solver_status_sequence` | string/array | Per-step solver status. |
| `solve_time_mean`, `solve_time_p95`, `solve_time_max` | seconds | Runtime evidence. |
| `solver_iteration_mean`, `solver_iteration_max` | numeric | Solver workload. |
| `overrun_count` | integer | Number of control steps exceeding `dt_control`. |
| `tracking_rmse_total` | numeric | Main tracking metric. |
| `tracking_rmse_lateral`, `tracking_rmse_longitudinal`, `tracking_max_error` | numeric | Directional and worst-case tracking metrics. |
| `payload_force_rms`, `payload_force_max` | numeric | Payload/connection force evidence. |
| `control_effort`, `control_smoothness` | numeric | Input cost and smoothness. |
| `constraint_violation_count` | integer | Count over common constraint set. |
| `constraint_violation_max`, `constraint_violation_duration` | numeric | Magnitude and duration of violations. |
| `collision_violation_count`, `connection_violation_count`, `force_violation_count` | integer | Safety-specific violation breakdown. |
| `fallback_count`, `fallback_duration` | integer/numeric | Safety/fallback activation. |
| `ftc_event_count`, `actuator_fault_events` | integer/JSON | Fault and FTC records. |
| `packet_drop_count`, `delay_mean`, `delay_p95`, `jitter_rms`, `burst_loss_max` | numeric | Realized communication trace statistics. |
| `topology_disconnect_count`, `leader_lost_count` | integer | Network degradation events. |
| `failure_flag` | boolean | Whether the run failed under the common policy. |
| `failure_reason` | enum/string | Timeout, infeasible, collision, constraint violation, divergence, NaN, or none. |
| `nan_detected` | boolean | Any NaN in state, control, metric, or safety diagnostic invalidates main-text use until resolved. |
| `artifact_paths` | JSON/list | Paths to raw logs, processed metrics, and figures. |
| `ci_group_id` | string | Grouping key for paired CI/statistical analysis. |
| `notes` | string | Manual notes; cannot override metrics. |

## 7. Downgrade Wording If AKE Cannot Be Fully Reproduced

Use the strongest wording justified by evidence, and no stronger.

| Baseline state | Required wording | Claim downgrade |
|---|---|---|
| `AKE-R` available | "We reproduced the AKE baseline and evaluated it under the same cooperative-transport/DCN protocol." | Full T1 baseline comparison allowed after CI gates pass. |
| Verified `AKE-A` available, `AKE-R` not available | "Because the original AKE experiments target different nonlinear systems, we implement a task-adapted AKE baseline following its offline Koopman learning, online adaptive correction, and MPC structure. This is not a bitwise reproduction of the original reported experiments." | Claims must say "relative to verified task-adapted AKE", not "relative to the original AKE results." |
| Candidate `AKE-A` pending verification | "The AKE adaptation is currently a candidate baseline state. It will become a primary baseline only after architecture fidelity, online `Delta A`/`Delta B`, MPC coupling, and shared data/constraint checks pass." | No primary AKE superiority claim. If any fidelity item fails, downgrade to `AKE-M`. |
| Only `AKE-M` available | "The original AKE baseline could not be fully reproduced or faithfully adapted with the available information. We therefore report a matched Koopman-MPC surrogate with equal data, model capacity, solver, and tuning budget." | Move comparison to supplement if possible. Main text may not claim superiority over AKE; only surrogate comparison is allowed. |
| No usable AKE-like baseline | "T1 baseline comparison remains pending. Current results are internal ablations and should not be interpreted as evidence of superiority over AKE." | No baseline-superiority language in abstract, introduction, conclusion, or figure captions. |

If any fairness gate fails, the affected table row must be marked `claim_level = preliminary` or `surrogate_only`. The abstract and conclusion must then use mechanism language only, for example: "The proposed controller is designed to address delayed and lossy communication through delay-compensated consensus MPC; quantitative superiority over AKE remains subject to the frozen T1 protocol."

## 8. T1 Downgrade Decision Table

If one or more required evidence items are missing, use the most restrictive row that applies.

| Missing item | Allowed claim | Forbidden claim | Required downgrade |
|---|---|---|---|
| AKE fidelity check missing: architecture, online `Delta A`/`Delta B`, MPC coupling, or shared data/constraints not verified | "Candidate AKE adaptation remains under verification" or "matched Koopman-MPC surrogate inspired by AKE" | "Primary AKE baseline", "outperforms AKE", or "reproduced/adapted AKE proves superiority" | `AKE-A` stays candidate; if unresolved for final results, set `ake_status = AKE-M` and `claim_level = surrogate_only` |
| Non-Koopman networked-control baseline missing | Koopman-family comparison only, explicitly limited to AKE/AKE-like methods | "Superior to networked-control methods", "state-of-the-art network control comparison", or cross-family generalization | `claim_level = preliminary` for general baseline claims |
| Only `ZOH consensus MPC` available as non-Koopman comparator | "Compared with a lowest ZOH consensus MPC surrogate under the same traces" | "Superior to physical-model DMPC", "superior to networked-control methods", or "external-family baseline fully covered" | Keep ZOH in supplement or label as lowest surrogate in main text |
| `n_closed_loop < 20` paired runs | Representative trend, smoke test, or qualitative case study | Statistical superiority, failure-rate reduction, robust performance claim, or main quantitative conclusion | `claim_level = representative` or `preliminary`; no abstract/conclusion superiority |
| Fresh training seeds missing or `n_train < 5` | Single-model or cached-model mechanism evidence | Learning-performance superiority, predictor robustness, or training-stability claim | Mark learning evidence as `representative`; keep predictor claims descriptive |
| Safety/fallback/violation log missing, incomplete, or contains unresolved NaN | No safety claim; at most "safety logging pending" | "Guaranteed safety", "constraint-safe", "reduces violations", or "fault-tolerant safety verified" | Remove safety result from main text or mark `pending` |
| Causal information boundary violated | Internal debugging result only after disclosure | Any T1 comparison, robustness claim, or baseline-superiority statement | Invalidate row for T1; rerun under causal traces |

## 9. T1 Pass Checklist

| Item | Pass condition |
|---|---|
| AKE label frozen | `AKE-R`, verified `AKE-A`, or `AKE-M` assigned with evidence; candidate `AKE-A` cannot support primary claims. |
| Mandatory method set complete | Proposed, Frozen AKE, credible non-Koopman network baseline, NoDelay, and NoCommAware all run or explicitly downgraded. ZOH alone is marked as a lowest surrogate. |
| Fairness gates satisfied | No unreported mismatch in data, horizon, solver, sampling period, constraints, traces, seeds, or tuning budget. |
| Causal boundary satisfied | No method uses future dropout/delay/topology, future leader-loss, oracle recovery, or clean privileged measurements. |
| Statistics complete | `n_closed_loop >= 20` paired runs and 95% CI for main metrics; fresh training seeds reported. |
| Logs complete | Every run has the schema fields above, no hidden failed runs, no NaN in main-text metrics. |
| Claims frozen | Main text, captions, abstract, and conclusion use wording consistent with the achieved AKE status. |
