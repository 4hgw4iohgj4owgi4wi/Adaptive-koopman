# Ch4--Ch7 Figure and Text Revision Checklist

Source review: `ch4_ch5_ch6_ch7_review_2026-05-26.md`

Current manuscript checked: `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex`

Purpose: this file is a proposed change list only. No manuscript text has been changed. Each item gives the current location, the remaining issue, and the exact proposed action or replacement for review.

## 0. Current State After Previous Edits

The current English manuscript has already fixed the main issues raised in the review:

- Ch. 4 now frames the result as certificate-verified practical ISS/UUB rather than global asymptotic stability.
- `\alpha_{\mathrm{cert}}`, `\rho_P,c_P`, sampled IRSP versus norm-certificate coverage, and failure-step growth are already present.
- Ch. 6 and Ch. 7 have already been merged into `Discussion and Conclusion`.
- The most obvious Chinese/internal expressions such as "客观结果", "造成上述结果", "最新", "调参", "回填", "主证据", and "内部审稿材料" are no longer present in Ch. 5--7.

Therefore, the remaining work should be a targeted figure/text polishing pass, not another full rewrite.

## 1. High-Priority Items

### P0-1. Fix Fig. 11 caption/content mismatch

Location: `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex`, lines 991--995.

Current issue:

The current Fig. 11 image shows trajectory, team errors, vehicle lateral errors, steering, speed, and acceleration. It does not visibly show planar payload resultant force or force components. However, the caption says:

```latex
... the lower diagnostic panels report vehicle-wise lateral error, front steering angle, longitudinal speed, longitudinal acceleration input, planar payload resultant force $\sqrt{F_x^2+F_y^2}$, and the components $|F_x|$ and $|F_y|$.
```

Risk:

This is a direct evidence mismatch. A reviewer may conclude that the force claim is being visually supported by a panel that is not actually present.

Recommended action A, if no new plot is generated:

Replace the caption with:

```latex
\caption{Experiment 9: same-initial-condition three-stage diagnostic on the 5 m/s hairpin with fault and variable high delay. The top row shows team-center $x$--$y$ trajectories, the middle row shows team lateral and longitudinal errors, and the lower panels report vehicle-wise lateral error, front steering angle, longitudinal speed, and longitudinal acceleration input. Dashed, starred, and solid curves denote \AKEdeg{}, \MethodHC{}, and \Method{}, respectively. The panel inspects the tracking and control behavior of the high-curvature branch and the payload-protection branch; the corresponding force peaks are reported in Table~\ref{tab:nooffset_degraded_hairpin}.}
```

Also revise line 998 from:

```latex
Table~\ref{tab:nooffset_degraded_hairpin} and Fig.~\ref{fig:nooffset_hairpin_5mps_panel} show two effects.
```

to:

```latex
Table~\ref{tab:nooffset_degraded_hairpin} and Fig.~\ref{fig:nooffset_hairpin_5mps_panel} show complementary effects: the table quantifies tracking, connection, and force metrics, while the figure shows the corresponding trajectory and control behavior.
```

Recommended action B, if a new plot can be generated:

Regenerate `fig_nrkdcc_nooffset_hairpin_5mps_panel.pdf` with an additional force row containing:

- planar payload resultant force $\sqrt{F_x^2+F_y^2}$,
- $|F_x|$,
- $|F_y|$,
- consistent line styles for \AKEdeg{}, \MethodHC{}, and \Method{}.

Then the current caption can be retained with only minor shortening.

### P0-2. Prevent Tables 3--8 from drifting as a block to page 14

Location: lines 852--1051.

Current issue:

In the compiled PDF, Tables 3--8 collect on page 14 after the related explanatory text has already appeared. This weakens the evidence chain because readers encounter the interpretation before the corresponding numerical tables.

Recommended action:

Review these float-level changes:

1. Convert small tables that fit one column to `table` instead of `table*` where possible.
2. Add `\FloatBarrier` after major subsections if table locality is more important than perfect float packing.
3. Keep only the largest evidence tables as `table*`.

Suggested table handling:

| Table | Current | Proposed | Reason |
|---|---|---|---|
| Table 3 main comparison | `table*` | keep `table*`, place near subsection start | central evidence |
| Table 4 speed sensitivity | `table*` | keep `table*` or compress to one-column only if readable | many rows |
| Table 5 same-initial sine diagnostics | `table*` | convert to `table` if column width permits, otherwise keep | compact but 6 columns |
| Table 6 hairpin diagnostic | `table*` | keep `table*` | force/trade-off evidence |
| Table 7 core ablation | `table*` | keep `table*` | central ablation |
| Table 8 certificate statistics | `table` | keep `table`; place before Discussion | already compact |

Possible LaTeX action after each subsection:

```latex
\FloatBarrier
```

Use this sparingly after `Main Comparison Results`, `Speed Sensitivity...`, and `High-Curvature Hairpin Comparison` if the table block still drifts.

### P0-3. Repair Fig. 7 y-axis/label overlap

Location: lines 828--832 and figure file `figures/fig_nrkdcc_fdi_ftc_timeline.pdf`.

Current issue:

In the top-right panel of Fig. 7, the y-axis labels and secondary-axis labels overlap visually. The panel title and legend remain interpretable, but the axis labeling is not publication-clean.

Recommended figure regeneration:

- Move the secondary y-axis label farther right or remove the secondary y-axis label if the legend already names the quantities.
- Shorten axis labels:
  - `norm / command` -> `normalized command`
  - `control spread / trim` -> `spread / trim`
- Increase right margin of the top-right subplot.

Caption replacement:

```latex
\caption{Experiment 4: FDI/FTC and safety-monitoring timeline in the mixed fault/noise scenario. In one representative run, the figure shows fault activation, controller-side fault flags, fault gaps, FTC reallocation commands, vehicle-level control decomposition, and certificate/execution-mode monitoring. The panel illustrates how degradation signals enter the execution layer after the Koopman-MPC candidate command has been generated.}
```

Reason:

This removes `reconfiguration-mode`, which can sound like a separate optimizer and conflict with the Ch. 3/4 statement that FTC is an execution-layer flag.

## 2. Text Replacements

### T1. Compress and de-duplicate the experiment overview

Location: lines 749--755.

Current issue:

`\ZOHcons{}` is defined twice. The future-work sentence appears too early in the experiment protocol and is repeated again in the conclusion.

Replace lines 749--755 with:

```latex
This section reports eleven experiments and diagnostics corresponding to the method modules in Sections 3 and 4. \ZOHcons{} denotes a low-order zero-order-hold (ZOH) consistency baseline used to expose degradation without learned prediction or network-aware protection. The prescribed-performance-control (PPC) guard triggers constraint tightening or conservative control when the tracking error approaches the prescribed envelope. The ablation suffixes noComm, noDelay, noIRSP, and noPPC denote removal of communication-quality awareness, delay compensation, input-aware robust spectral projection, and the PPC guard, respectively.

Experiments 1--5 evaluate Koopman learning, prediction/projection, communication-delay mechanisms, FDI/FTC execution, and mode-wise certificate behavior. Experiments 6, 10, and 11 use paired $n=20$ statistics, Experiment 7 uses paired $n=3$ speed-stress statistics, and Experiments 2--5, 8, and 9 are mechanism-oriented diagnostics or same-initial-condition trajectory checks. These diagnostics inspect process-level behavior and are not treated as replacements for the paired statistical comparisons.

The task-aligned baseline \AKE{} is derived from the adaptive Koopman embedding idea of Singh et al.~\cite{singh2025adaptiveKoopman}. It transfers offline Koopman representation learning, online prediction-error correction, and Koopman-MPC control to the four-vehicle rigid-payload transport task.
```

Effect:

Cuts one paragraph and removes the local workflow phrase "updated diagnostic controller settings" from the protocol section.

### T2. Soften the causal claim in the FDI/FTC explanation

Location: lines 835--837.

Current issue:

The wording "The FTC module compensates..." is slightly strong for a single-run diagnostic.

Replace lines 835--837 with:

```latex
Figure~\ref{fig:fdi_ftc_timeline} shows that, after fault activation in the mixed fault/noise run, the controller-side fault flags and fault gaps increase together. The FTC reallocation flag then becomes active, producing nonzero steering/acceleration redistribution and changes in the vehicle-level control decomposition. The certificate function and margin continue to be logged during this transition.

This behavior is consistent with actuator-efficiency loss changing the closed-loop consistency between commanded and realized inputs. The reallocation signals indicate that the execution layer redistributes input demand inside the conservative feasible set, rather than switching to an independent main optimizer. The figure supports FDI/FTC integration into the closed-loop execution layer, but remains a single-run mechanism diagnostic.
```

Effect:

Avoids implying that one diagnostic plot proves FTC performance.

### T3. Soften the force interpretation in the main comparison

Location: lines 885--887.

Current issue:

The force paragraph is already cautious, but "show that the current weights can use stronger transient control actions" still reads like a causal explanation.

Replace line 887 with:

```latex
These results indicate that link-quality weighting, connection-geometry constraints, and Koopman-MPC prediction mainly improve tracking and connection utilization. The higher force peaks are consistent with stronger transient control actions used to preserve connection geometry; force-related quantities are therefore treated as trade-off audits rather than primary superiority claims.
```

Effect:

Changes a causal statement into a consistency statement.

### T4. Remove "updated" from the speed diagnostic paragraph

Location: line 916.

Current issue:

`updated low-level speed clipping` reads like an internal revision note.

Replace the last sentence of line 916:

```latex
The same-initial-condition diagnostic below is therefore reported separately to inspect whether updated low-level speed clipping, balanced progress supervision, and local lateral trimming can remove this failure mode in a representative run.
```

with:

```latex
The same-initial-condition diagnostic below is therefore reported separately to inspect whether a speed-clipped, balanced-progress diagnostic configuration with local lateral trimming can remove this failure mode in a representative run.
```

### T5. Remove "original/background evidence" wording in the hairpin paragraph

Location: line 971.

Current issue:

`original paired` and `background evidence` sound like internal manuscript history.

Replace line 971 with:

```latex
The paired $n=3$ hairpin stress statistics show that \AKE{}, \MethodBase{}, and \Method{} complete the full path. \Method{} reduces lateral and longitudinal RMSE and improves the certificate pass ratio relative to \AKE{}, but its payload-force RMS remains higher. To avoid duplicate hairpin tables, this subsection uses the same-initial-condition three-stage table as mechanism-oriented diagnostic evidence, while the paired statistics provide contextual multi-run evidence.
```

### T6. Shorten the hairpin result text after fixing Fig. 11

Location: lines 998--1000.

Current issue:

The text is defensible but long and repeats the trade-off message already in the conclusion. It should also separate table-based force evidence from figure-based trajectory evidence.

Replace lines 998--1000 with:

```latex
Table~\ref{tab:nooffset_degraded_hairpin} and Fig.~\ref{fig:nooffset_hairpin_5mps_panel} show complementary effects: the table quantifies tracking, connection, and force metrics, while the figure shows the corresponding trajectory and control behavior. \MethodHC{} reduces team-center lateral RMSE from $0.298869$ m to $0.085119$ m relative to \AKEdeg{}, but increases the force peak from $5544.45$ N to $15487.33$ N. After activating the payload-protection switch, \Method{} reduces maximum connection utilization from $0.778074$ to $0.403050$ and force peak from $15487.33$ N to $8874.04$ N relative to \MethodHC{}, while lateral RMSE increases to $0.264159$ m. Thus, the full method trades part of the high-curvature lateral-tracking gain for lower connection utilization and lower force peak.
```

Effect:

Keeps the core numbers but removes one explanatory sentence.

### T7. Compress Discussion and Conclusion

Location: lines 1061--1065.

Current issue:

The section is now structurally correct, but it still repeats many metrics and module names. A tighter conclusion would read more like a final manuscript section.

Replace lines 1061--1065 with:

```latex
In the mixed fault/noise and high-communication-noise cooperative-transport scenarios, \Method{} mainly improves tracking and connection-constraint utilization relative to the task-aligned \AKE{} baseline. The paired evidence shows that maximum connection utilization decreases from $0.2999$ to $0.0513$ under mixed fault/noise and from $0.3757$ to $0.0452$ under high communication noise, with lower lateral RMSE in both cases. The ablation study identifies communication-aware consensus MPC as the dominant contributor, supporting the mechanism that link quality should enter consensus weighting, neighbor trust, and constraint tightening rather than remain a passive diagnostic signal.

The results also delimit the method. Force-related quantities are not uniformly better than \AKE{} and are treated as trade-off audits rather than primary improvement claims. The hairpin diagnostic shows that high-curvature tracking can reduce lateral error while increasing payload-force demand, whereas the payload-protection branch lowers force peak and connection utilization at the cost of some lateral-error recovery. The speed study shows that longitudinal phase error becomes dominant beyond 10 m/s. Same-initial-condition diagnostics are mechanism checks, not replacements for paired statistics, and the stability result is certificate-verified practical boundedness rather than global asymptotic stability.

This paper proposed \Method{}, a network-resilient cooperative-transport framework combining a stability-projected bilinear Koopman predictor, communication-quality-aware consensus MPC, adjacent-distance regulation, upper-layer 4WS local-path publication, FDI/FTC execution-layer protection, and a Lyapunov/ISS certificate. The supported claim is better network-aware tracking and connection control under degradation. Future work should rerun the updated diagnostic controller settings with multi-seed statistics, improve high-speed longitudinal phase control, and validate the payload-force proxy with richer load measurements or physical experiments.
```

Optional extra compression:

If the paper is over length, remove the first sentence of the third paragraph and start directly with "The supported claim...".

## 3. Figure and Caption Changes

### F1. Fig. 1 framework figure

Location: lines 305--312.

Current state:

The user VSDX framework figure is now a single-column figure. This matches the latest instruction that it should not occupy both columns.

Proposed action:

No structural change. Only consider shortening the caption:

```latex
\caption[Overall architecture of \Method{}]{Overall architecture of \Method{}. The offline layer builds the Koopman model; the online layer combines 4WS local-path publication with delay-compensated Koopman-MPC; and the environment block represents the four-vehicle rigid-payload transport system.}
```

### F2. Fig. 2 online signal-flow figure

Location: lines 312--368.

Current issue:

The figure is readable but the caption is very long. Since the visual itself is already dense, the caption should only state the main flow and fallback logic.

Proposed caption:

```latex
\caption[Online signal flow of \Method{}]{Online signal-flow diagram of \Method{} within one sampling period. Vehicle states, link quality, references, and fault residuals are fused into communication-aware consensus and Koopman prediction. The resulting MPC command is checked by FDI/FTC, safety filtering, and the Lyapunov/ISS certificate before being applied or replaced by projection, reference contraction, or degraded fallback. Dashed lines denote communication-degradation, certificate-feedback, and fallback channels.}
```

Optional layout change:

If page 4 still feels crowded, reduce `\resizebox{0.92\textwidth}{!}` to `\resizebox{0.86\textwidth}{!}`.

### F3. Fig. 3 Koopman training loss

Location: lines 759--763.

Current state:

Main-text safe. It has clear axes and supports training convergence/audit, not stability.

Proposed caption shortening:

```latex
\caption{Experiment 1: Koopman lifting training and validation losses. The left panel reports total, prediction, and lifted losses; the right panel compares the last-10-epoch train/validation means. The figure checks convergence and excludes obvious divergence, rather than proving closed-loop stability.}
```

### F4. Fig. 4 Koopman prediction/projection audit

Location: lines 770--774.

Current issue:

Caption is accurate but long. Keep the figure in the main text because it links directly to the IRSP proof.

Proposed caption:

```latex
\caption{Experiment 1: Koopman prediction and IRSP audit. The left panel reports one-step state RMSE, the middle panel reports 1--12 step rollout errors with 95\% confidence intervals, and the right panel reports sampled spectral radii of $A_{\mathrm{eff}}(u)$ before and after IRSP over 96 normalized training-input samples. The audit concerns the input-dependent operator $A_{\mathrm{eff}}(u)$, not only the main matrix $A$.}
```

### F5. Table 2 and Fig. 5 Koopman ablation duplication

Location: Table 2 lines 781--804; Fig. 5 lines 806--810.

Current issue:

Table 2 already contains the numeric result. Fig. 5 visualizes a subset of the same evidence and occupies the top of page 9. This is not wrong, but it may be redundant in a compressed manuscript.

Recommended options:

- Option A, keep both: if the paper needs a quick visual summary of K0/K1/K2/K3.
- Option B, move Fig. 5 to supplementary material and keep Table 2 in the main text.
- Option C, keep Fig. 5 but remove Table 2 if visual trend is more important than exact numbers.

Recommended choice:

Use Option B. Keep Table 2 because the review emphasizes fair interpretation of K1/K2/K3 and the exact values matter.

If keeping Fig. 5, use this shorter caption:

```latex
\caption{Experiment 2: closed-loop Koopman-setting ablation. K3 is the current bilinear+IRSP predictor, K2 removes projection, K1 is the AKE-style linear adaptive predictor, and K0 is the raw 6D linear Koopman predictor.}
```

### F6. Fig. 6 communication-delay evidence

Location: lines 817--821.

Current issue:

The figure mainly shows upper-to-lower delay activation, while adjacent delay/dropout channels appear near zero in this representative run. The caption should avoid implying all communication channels are degraded simultaneously.

Proposed caption:

```latex
\caption{Experiment 3: communication perturbation and delay-compensation diagnostics in the 5 m/s high-delay hairpin scenario. The figure reports the active upper-to-lower path delay, link-quality/dropout indicators, corrupted tracking channels seen by the controller, and protective actions including 4WS local-path activation, lateral-priority weighting, and constraint tightening.}
```

Proposed text adjustment at lines 824--826:

```latex
Figure~\ref{fig:delay_mechanism_evidence} shows that the representative high-delay run mainly activates the upper-to-lower desired-path delay while recording link-quality, packet-loss, relative-distance, and team-lateral-error channels for audit. The controller responds through 4WS local-path activation, lateral-priority weighting, and communication-aware constraint tightening.
```

### F7. Fig. 8 mode-wise certificate closure

Location: lines 839--843.

Current issue:

The figure has only two bar panels and could fit a single column. Keeping it as `figure*` costs too much page space.

Recommended action:

Change from:

```latex
\begin{figure*}[!t]
\includegraphics[width=0.92\textwidth]{figures/fig_nrkdcc_modewise_certificate_closure.pdf}
...
\end{figure*}
```

to:

```latex
\begin{figure}[!t]
\centering
\includegraphics[width=\columnwidth]{figures/fig_nrkdcc_modewise_certificate_closure.pdf}
...
\end{figure}
```

Only accept this change if the labels remain readable in the compiled PDF.

Caption can remain, or be shortened to:

```latex
\caption{Experiment 5: mode-wise Lyapunov/ISS certificate closure. The figure separates nominal and FTC-flagged steps in pressure scenarios and reports certificate ok ratio and minimum positive margin. The statistics check consistency with the practical ISS/UUB certificate without claiming global stability.}
```

### F8. Figs. 9--10 same-initial sine diagnostic panels

Location: lines 937--963.

Current issue:

Figs. 9--10 are readable but very dense. They are single-seed diagnostics, while the review recommends not treating single-seed panels as primary evidence. They also consume a full page.

Recommended options:

- Option A, keep both figures in the main text because they document the 2/5/10/15 m/s behavior.
- Option B, keep only one combined representative figure in the main text, e.g., 5 m/s and 15 m/s, and move 2 m/s and 10 m/s to supplementary material.
- Option C, keep Table 5 in the main text and move both Figs. 9--10 to supplementary material.

Recommended choice:

Option B if page length matters; Option A if the manuscript must show the full speed sweep visually.

If keeping both, shorten captions:

```latex
\caption{Experiment 8: same-initial-condition \AKEdeg{} diagnostics at 2 m/s and 5 m/s. The panels report team trajectory, team errors, vehicle-wise lateral errors, steering, speed, and acceleration input. Dashed curves denote \AKEdeg{} and solid curves denote \Method{}.}
```

```latex
\caption{Experiment 8: same-initial-condition \AKEdeg{} diagnostics at 10 m/s and 15 m/s. The layout follows Fig.~\ref{fig:nooffset_fault_low_speed_panel}. The 15 m/s panel is used as a failure-mode diagnostic for the speed-clipped, balanced-progress configuration.}
```

### F9. Fig. 11 hairpin panel

Location: lines 991--995.

This is the same as P0-1 and should be handled before any other hairpin wording changes.

Recommended decision:

- If force curves can be regenerated: add force panels.
- If not: revise caption and text so force evidence is attributed only to Table 6.

### F10. Table captions are too long when many tables float together

Location: Tables 3--8, lines 852--1051.

Current issue:

Many table captions include scenario descriptions, metric descriptions, and interpretation. When the tables drift together, this creates a dense page.

Recommended action:

Keep table captions as identification only. Move interpretation to nearby prose.

Example for Table 3:

Current:

```latex
\caption{Experiment 6: paired $n=20$ main comparison under mixed fault/noise and high-communication-noise scenarios. The table compares the proposed method, task-aligned Koopman baselines, and a low-order auxiliary baseline in terms of success rate, full-path success, tracking error, connection-constraint utilization, and force peak.}
```

Proposed:

```latex
\caption{Experiment 6: paired $n=20$ main comparison under mixed fault/noise and high-communication-noise scenarios.}
```

Apply the same principle to Tables 4--8 unless the extra caption sentence is needed to define a nonstandard metric.

## 4. Items That Do Not Need More Changes Now

### N1. Ch. 4 proof framing

Location: lines 594--742.

Decision:

No further substantive rewrite is needed. The review's three micro-issues are already addressed:

- `\alpha_{\mathrm{cert}}` is defined at line 675.
- `\rho_P,c_P` are explicitly absorbed into failure constants at lines 649--651 and 725.
- sampled IRSP versus norm-certificate coverage is stated at lines 669--675.

Only optional polish:

Replace line 741:

```latex
This proves practical input-to-state boundedness and UUB under the stated certificate and fallback assumptions.
```

with:

```latex
This establishes practical input-to-state boundedness and UUB under the stated certificate and fallback assumptions.
```

Reason: `establishes` is slightly less absolute than `proves`, although this is inside a formal proof and the current wording is acceptable.

### N2. The force trade-off boundary

Location: lines 876--887, 998--1000, 1063--1065.

Decision:

The manuscript already avoids claiming uniform force improvement over \AKE{}. Keep this boundary. Do not rewrite force results as a primary superiority claim.

## 5. Review Checklist for User Approval

Please review these decisions one by one:

- [ ] P0-1: Fix Fig. 11 by either regenerating force panels or revising caption/text to attribute force evidence only to Table 6.
- [ ] P0-2: Adjust table float locality so Tables 3--8 do not collect as one block on page 14.
- [ ] P0-3: Regenerate Fig. 7 to remove y-axis/secondary-axis label overlap.
- [ ] T1: Compress experiment overview and remove duplicate \ZOHcons{} definition.
- [ ] T2: Soften FDI/FTC causal wording.
- [ ] T3: Soften main-comparison force interpretation.
- [ ] T4: Replace "updated low-level speed clipping" with neutral diagnostic wording.
- [ ] T5: Replace "original/background evidence" in the hairpin paragraph.
- [ ] T6: Shorten the hairpin result text after deciding how to fix Fig. 11.
- [ ] T7: Compress Discussion and Conclusion.
- [ ] F2--F4: Shorten long figure captions for Figs. 2--4.
- [ ] F5: Decide whether Fig. 5 stays in main text or moves to supplementary material.
- [ ] F7: Decide whether Fig. 8 becomes single-column.
- [ ] F8: Decide whether Figs. 9--10 stay in main text or only representative speed panels remain.
- [ ] F10: Shorten table captions.

Recommended minimal approval set:

Approve P0-1, P0-2, P0-3, T1--T6, F2--F4, and F10. Defer F5/F7/F8 if you want to preserve all current evidence in the main text.
