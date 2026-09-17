# Connector R3.1 post-R2 protocol revision

> Frozen before new R3.1 results are generated on 2026-08-25.  
> Classification: `post-R2 protocol revision`; it is not the original preregistration.  
> Historical R3 status remains `BLOCKED_AFTER_R2_2MS_GATE`.

## 1. Scope and immutable history

R3.1 keeps the historical R3 formula, parameters and train-only width unchanged:

\[
F_N=k\delta+c\,g(\delta)[v_n]_+,\qquad
g=3s^2-2s^3,\quad s=\delta/\delta_s,
\]

with `delta_s = 0.0001776170305060031 m`. Historical R0--R2 source, results,
figures, manifests and stop status must not be overwritten. R3.1 writes only to:

```text
revision_2026/connector_r3_1/
revision_2026/connector_r3_1_results/
```

No validation, development or confirm data may be read. The only scientific input
for S1 is the immutable R0 train-only event table and its freeze/manifest metadata.

## 2. Sequential task gates

### S0 historical freeze

Copy the key historical protocol/source/result records into a snapshot directory and
write size/SHA-256 provenance. A mismatch or missing required file stops execution.

### S1 train contact-speed audit

For every valid historical R0 event save `trajectory_id`, `event_id`, `scenario`,
`connector_id`, `plant_step`, `vn_on_mps`, `delta_on_m`,
`tau_nominal_s = delta_s/vn_on_mps`, and whether the first 500 Hz sample lies inside
the smoothing zone. Report Q01/Q05/Q50/Q90/Q95/Q99/Q100 for speed and nominal time.
The support-domain test speeds are frozen as Q05/Q50/Q95/Q99. The fixed
`0.25/1.0 m/s` cases remain visible out-of-support stress diagnostics.

### S2/R2.1 repaired single-connector gate

The high-rate reference step is `20 us`. For every support speed, sweep 32 equally
spaced contact phases in `[0, dt_ref)`. The hard support-domain onset gate requires
the worst first-active-sample force reduction relative to V1 to be at least 50%.
The continuous boundary limit remains a separate analytic/numeric gate.

Energy case E1 starts at `delta0=0.25*delta_s`, `v0=0.1 m/s`, uses the physical
damping and a `2 us` integration step for `0.04 s`. It must have positive damping
power, a different trace hash from the zero-damping control, and satisfy

\[
r_E(t)=E(t)-E(0)+\int_0^t P_d\,dt.
\]

The maximum absolute residual must be at most `2e-4 J` and the scaled residual at
most `2e-4`. E2 is a prescribed full loading/unloading cosine cycle within the
smoothing zone; integrated damping work must be positive and unloading damping must
be zero to `1e-12 N`.

R2.1 also requires post-smoothing V1 equivalence, four-direction symmetry,
finite/nonnegative forces, deterministic replay, and uncapped 15 kN numerical stop.
The 2 ms endpoint reductions are reported separately for support and stress speeds
and are not a universal hard gate.

### S3/R3a plant-step resolvability and convergence

Only after R2.1 passes, compare `dt = 2, 1, 0.5 ms` against `0.1 ms` for support
Q50/Q95/Q99 and the `0.25/1.0 m/s` stress cases. Also compare releases initialized
at 2/8/12/14 kN numerical elastic loads.

For Q50/Q95/Q99, 32 contact phases are audited at the 2 ms plant grid. The smoothing
zone is considered resolvable only when every support speed has at least two
strictly-inside-zone integration samples at the median phase. This is a hard
engineering-sampling gate. Peak-force error must be at most 5%, impulse error at
most 2%, scaled terminal-state error at most 1%, and contact-time error at most one
2 ms step.

If the resolvability gate fails, stop before the four-vehicle R3b/R4/R5 chain and
write a solution report. A numerically stable but unresolvable boundary layer is not
evidence of an observable 500 Hz plant improvement.

### S4 and later

Four-vehicle representative-load convergence, paired 100 m/lane-change/hairpin/
directional runs, direction/internal-force audit, D0 data, Koopman and MPC remain
downstream. They may run only if all preceding gates pass. A hard failure produces
explicit `NOT_RUN` markers rather than synthetic downstream results.

## 3. Required outputs

R3.1 must produce CSV/JSON evidence and at least these figures for the stages reached:

```text
01_contact_speed_support.png
02_nominal_smoothing_time.png
03_phase_sweep_onset_reduction.png
04_e1_energy_balance.png
05_e2_prescribed_cycle.png
06_two_ms_support_vs_stress.png
07_dt_convergence.png
08_plant_step_resolution.png
```

It must also write `stage_status.json`, `work_log.md`, `solutions.md`, `report.md`,
and a SHA-256 `output_manifest.json`. Every report must state that the work is a
numerical-model audit, not a physical connector strength certification.

