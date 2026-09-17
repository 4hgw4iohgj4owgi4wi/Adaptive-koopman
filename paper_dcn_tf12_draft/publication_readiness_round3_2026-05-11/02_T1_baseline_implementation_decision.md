# Round3 Worker B: T1 Baseline Implementation Decision

Date: 2026-05-11

Scope: read-only audit of the current local repository state for deciding whether the AKE-facing baseline can be treated as `AKE-A`, or must be downgraded to `AKE-M`.

## 1. Decision

Current local status: **downgrade to `AKE-M`**.

The current runner label `AKE-baseline` is not a verified task-adapted AKE implementation. It is a matched Koopman-MPC surrogate with proposed communication-aware, adaptive-weight, dynamic-PPC, online-FDI/FTC, and online model-adaptation switches disabled. It may be useful as a same-task Koopman-family comparator, but it must not be called reproduced AKE, verified task-adapted AKE, or primary AKE evidence.

Recommended frozen label for current local rows:

| Comparator row | Current local label | T1 label to use | Claim level |
|---|---|---|---|
| `baseline` / `AKE-baseline` | Stage5/remaining runner baseline | `AKE-M` | `surrogate_only` or `preliminary` |
| `tf14_main`, `tf14_phase_role`, `tf14_error_match` | Proposed-family variants | `null` | only after T1 gates pass |
| future dedicated AKE adaptation | not implemented as a frozen method row | `AKE-A candidate` until verified | no main superiority claim |

## 2. AKE Fidelity Requirements

To promote a local comparator from `AKE-M` to verified `AKE-A`, it must preserve the AKE mechanism at the method level:

| Required item | Minimum implementation/evidence |
|---|---|
| Nominal Koopman architecture | Offline autoencoder-based Koopman embedding trained from nominal input-output data, with documented lifted dimension, encoder/decoder/losses, normalization, nominal `A/B/C`, and mapping to the cooperative-transport state and input. |
| Online adaptive correction | A feed-forward/adaptive network or faithful equivalent that uses lifted-state prediction residuals to estimate online `Delta A` and `Delta B`; update window, epochs, regularization, clipping/projection, and update timing must be logged. |
| MPC coupling | The adapted matrices actually used by the MPC prediction model before solving, not merely computed as diagnostics. |
| No proposed-only modules | Frozen AKE must exclude TF14 delay-compensated consensus prediction, link-quality weighting, communication-aware fallback/tightening, FDI/FTC switching, phase-role scheduling, and safety/FTC logic unless explicitly shared as an outer wrapper for all methods. |
| Same T1 protocol | Same plant/task, offline data, split, horizon, solver, dt, constraints, communication traces, seeds, tuning budget, failure policy, and compute accounting as the proposed method. |
| Logs and freeze | Machine-readable parameter row and run log with `ake_status`, config hash/snapshot, train/closed-loop seeds, adaptation norms, solver status, violations, NaN gate, and paired statistics. |

`AKE-R` is stronger and would additionally require canonical reproduction of the original AKE paper/code or an independently validated reproduction before task adaptation.

## 3. Local Evidence

### 3.1 What exists locally

| Evidence | Interpretation |
|---|---|
| `README.md:3` states the baseline paper uses an offline autoencoder Koopman embedding, then augments the nominal architecture with a feed-forward network that modifies nominal dynamics from lifted-state prediction error, and integrates this with MPC. | This is the AKE mechanism that the comparator must preserve. |
| `tf14_pre.ipynb:58`, `tf14_pre.ipynb:262-270`, and `tf14_pre.ipynb:1948-2001` import `AdaptNet_linear`, define online adaptation settings, and add debug wrappers for `fit_delta_*` / `apply_online_delta`. | Adaptation building blocks exist in notebook context, but this is not a frozen AKE baseline row. |
| `control_files/tf11_a1/mpc_helpers.py:324-353` implements `fit_delta_linear_net`, and `control_files/tf11_a1/mpc_helpers.py:378-394` applies `Delta A/Delta B` to the dynamics object. | The codebase has reusable online correction primitives. |
| `tf14_runtime.py:1454-1492` can fit `Delta A/Delta B` and apply them when `use_online_adapt` is true. | MPC-coupled adaptation is possible for methods that enable it. |
| `tf14_runtime.py:1811-1814` returns `adapt_mode`, `adapt_A_norm_hist`, `adapt_B_norm_hist`, and `koopman_structure`. | Some adaptation evidence can be logged at result level. |

### 3.2 Why current baseline is not AKE-A

| Local evidence | Consequence |
|---|---|
| `tf14_stage5_phase_role_scenarios_20260507/run_tf14_stage5_phase_role_suite.py:165-183` defines `baseline` with `use_online_model_adaptation=False`, `use_adaptive_weight=False`, `use_dynamic_ppc=False`, communication-aware modules off, online FDI/FTC off, and FTC redistribution off. | This explicitly removes the online adaptive correction required by AKE-A. |
| `tf14_stage5_phase_role_scenarios_20260507/run_tf14_stage5_phase_role_suite.py:214` labels that disabled method as `AKE-baseline`. | The label is stronger than the implementation evidence supports. |
| `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py:352-365` carries forward `baseline`, `tf14_main`, and `tf14_phase_role`, but only `tf14*` methods get `use_online_model_adaptation=True` and `realtime_disable_online_adapt=False`. | The final comparison runner enables online adaptation for proposed-family methods, not for the baseline. |
| `tf14_runtime.py:333-338` default TF14 method includes online adaptation and communication modules, while `tf14_runtime.py:411-413` disables online adaptation in realtime mode if `realtime_disable_online_adapt=True`. | Adaptation is a configurable TF14/proposed feature, not a verified Frozen_AKE baseline feature. |
| `tf14_pre.ipynb:89-90` disables Koopman training and linear refit by default. | Current notebook defaults do not provide fresh AKE training evidence. |
| `tf14_remaining_experiments_20260509/README_zh.md` reports `Final n>=20 ready: False` and says E1 multi-seed Koopman DNN prediction still needs a separate runner. | Current local evidence is smoke/partial, not final T1 statistical or fresh-training evidence. |
| No searched runner or runtime file contains a `Frozen_AKE` method, `ake_status` field, frozen AKE config hash, AKE architecture fidelity checklist, canonical AKE reproduction record, or T1 parameter-table row. | The T1 contract fields needed to verify AKE-A are absent. |

## 4. Current Gaps Blocking AKE-A

P0 blocking gaps:

| Gap | Required fix |
|---|---|
| No frozen AKE method row | Add a dedicated `Frozen_AKE`/`ake_adapted` method spec rather than reusing `baseline` or proposed variants. |
| Online `Delta A/Delta B` disabled for baseline | Enable and log baseline online correction, preferably the AKE-faithful `AdaptNet_linear` path if that is the chosen adaptation mechanism, not only bilinear ridge unless justified as faithful. |
| MPC coupling not verified for baseline | Add log fields proving the adapted `A/B` are the matrices used by the controller at each solve/update interval. |
| AKE architecture mapping missing | Document state/input/lifting mapping from AKE to cooperative transport, nominal data generation, encoder/lift dimension, `A/B/C`, residual definition, adaptation network, and constraints. |
| Proposed modules not cleanly excluded | Ensure Frozen_AKE does not use delay compensation, QoS/link-quality weighting, communication-aware tightening/fallback, FDI/FTC, phase-role scheduling, or proposed safety logic except as an explicitly shared wrapper. |
| Fairness/provenance schema missing | Add `ake_status`, `claim_level`, training hashes, comm trace hashes, constraint hashes, seeds, solver settings, tuning-budget ID, config hash, and snapshot fields. |
| No final statistics | Run paired closed-loop `n>=20`, fresh train seeds `n_train>=5`, no-NaN checks, and confidence intervals after freezing configs. |

## 5. Upgrade Path to Verified AKE-A

1. Implement a dedicated `Frozen_AKE` method plan with `ake_status="AKE-A_candidate"` and no proposed communication/FTC/safety modules.
2. Freeze an architecture-fidelity document mapping AKE nominal Koopman learning, online `Delta A/Delta B` adaptation, and MPC coupling onto the cooperative-transport plant.
3. Choose and justify the online adaptation mechanism: use `fit_delta_linear_net`/`AdaptNet_linear` if claiming feed-forward AKE fidelity; if using ridge or bilinear ridge, label the deviation and keep `AKE-M` unless the fidelity argument is accepted.
4. Add run logging for adaptation update count, update times, `||Delta A||`, `||Delta B||`, post-clipping norms, matrix hashes before/after update, and whether the updated model entered the MPC solve.
5. Add T1 parameter/log schema fields and freeze same data, horizon, solver, dt, constraints, communication traces, paired seeds, and tuning budgets.
6. Run one cheap smoke check only to validate schema and no-NaN behavior; then run the final paired-seed protocol and fresh training-seed protocol before any main-text superiority claim.
7. If any AKE fidelity item remains unresolved, keep the frozen comparator as `AKE-M`.

## 6. Main-Text Wording Boundary

Allowed now:

- "The AKE paper is used as a mechanism-level reference for adaptive Koopman-MPC under nonlinear dynamics uncertainty."
- "Current local experiments include a matched Koopman-MPC surrogate inspired by AKE; this is not a reproduced or verified task-adapted AKE baseline."
- "A verified task-adapted AKE comparison remains pending architecture-fidelity, online `Delta A/Delta B`, MPC-coupling, and T1 fairness checks."

Allowed if current state remains `AKE-M`:

- "The proposed method is compared with a matched Koopman-MPC surrogate under the same cooperative-transport scenarios; this does not constitute a reproduced comparison against the original AKE implementation."

Allowed only after all AKE-A gates pass:

- "Because the original AKE experiments target different nonlinear systems, we implement a verified task-adapted AKE baseline following its nominal Koopman learning, online adaptive correction, and MPC structure under identical cooperative-transport/DCN settings."

Forbidden now:

- "The proposed method outperforms AKE."
- "The baseline is a reproduced AKE implementation."
- "The current `AKE-baseline` runner row is verified task-adapted AKE."
- "AKE fails under communication degradation."
- Any abstract/conclusion claim of superiority over AKE or over state-of-the-art networked control based on the current local baseline rows.
