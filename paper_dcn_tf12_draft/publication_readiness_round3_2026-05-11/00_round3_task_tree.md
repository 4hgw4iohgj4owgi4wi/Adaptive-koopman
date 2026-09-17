# Round 3 Execution-Preparation Task Tree

## Goal

Convert Round 2 publication-readiness gates into concrete execution inputs:

- runner capability audit,
- T1 baseline implementation decision,
- citation record verification queue,
- dry-run command plan,
- safe Chinese manuscript integration draft scope.

## Inputs

- Round 2 report: `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/06_round2_integrated_publication_readiness_report.md`
- Runner: `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`
- Gap closure runner: `tf14_final_gap_closure_20260509/run_tf14_final_gap_closure.py`
- Final commands: `tf14_final_gap_closure_20260509/FULL_FINAL_COMMANDS.md`
- Latest Chinese manuscript: `paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

## Rules

- Do not run expensive final `n>=20` experiments in worker tasks.
- Workers may read code and READMEs.
- Workers may only write their assigned markdown output.
- Reviewers do not edit files.
- The main agent may run lightweight dry-run/help commands after worker audit if safe.

## Workers

### Worker A: Runner Capability Audit

- Output: `01_runner_capability_audit.md`
- Scope: inspect runner CLI/options/methods/scenarios/outputs; identify whether T1/non-Koopman/n>=20/fresh seeds/dose/topology are currently runnable.

### Worker B: T1 Baseline Implementation Decision

- Output: `02_T1_baseline_implementation_decision.md`
- Scope: decide AKE-A vs AKE-M current feasible status from local files; list exact implementation gaps to upgrade candidate baseline.

### Worker C: Citation Record Verification Queue

- Output: `03_citation_record_verification_queue.md`
- Scope: convert Round2 literature matrix into a prioritized citation queue with citation keys, fields to verify, legal source URLs/search strings, and claim restrictions.

### Worker D: Dry-Run and CSV Schema Execution Plan

- Output: `04_dryrun_csv_schema_execution_plan.md`
- Scope: produce safe dry-run/help commands, expected CSV files, schema validation checks, and no-NaN checks.

### Worker E: Safe Chinese Integration Draft Scope

- Output: `05_safe_chinese_integration_draft_scope.md`
- Scope: identify text that can be integrated now without final experiments, and text that must remain pending.

## Main Output

- `06_round3_integrated_execution_readiness_report.md`
