# Round 2 Publication-Readiness Task Tree

## Goal

Move from the previous planning document to concrete P0 artifacts required before the manuscript can credibly claim publication readiness.

Previous integration file:

`paper_dcn_tf12_draft/parallel_article_completion_2026-05-10/05_integrated_parallel_execution_plan.md`

Current latest Chinese manuscript:

`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

## Rules

- Do not modify the existing Chinese DOCX, LaTeX, experiment code, or figure folders in this worker round.
- Each worker may only write its assigned output file.
- Reviewers do not edit files.
- The main agent integrates after reviewer feedback.
- No SciDown or unauthorized paywall bypass workflows.
- No claim of superiority over the uploaded baseline before the T1 fairness gate is frozen and evidence is available.

## Worker Assignments

### Worker A: T1 Baseline Fairness Contract

- Output: `01_T1_baseline_fairness_contract.md`
- Scope: define AKE baseline status, fairness gates, required method set, table schema, allowed/disallowed claims.
- Do not inspect or edit experiment code beyond reading existing plan files.

### Worker B: Recent Literature Evidence Matrix

- Output: `02_recent_literature_evidence_matrix.md`
- Scope: identify recent legal-source literature categories and a fillable evidence matrix for each contribution.
- Must include DCN-native communication/network categories.
- Do not download paywalled files or use unauthorized tools.

### Worker C: Method-Proof Bridge Draft

- Output: `03_method_proof_bridge_draft_zh.md`
- Scope: draft Chinese manuscript-ready text for the missing control-chain-to-Lyapunov bridge.
- Must include symbol constraints and practical/UUB stability boundary.
- Do not modify the DOCX.

### Worker D: Experiment Execution and Figure Readiness Audit

- Output: `04_experiment_execution_readiness_audit.md`
- Scope: inspect existing folders/scripts if needed; produce exact run priorities, expected outputs, missing data, figure readiness gate.
- Do not run expensive experiments or modify code.

### Worker E: Chinese Manuscript Integration Patch Plan

- Output: `05_chinese_manuscript_integration_patch_plan.md`
- Scope: produce a section-by-section plan for integrating Round 2 outputs into the Chinese DOCX.
- Include where to insert T1, literature, method bridge, experiment gates, and claim limitations.
- Do not modify the DOCX.

## Reviewer Assignments

### Reviewer 1

Reads outputs 01, 02, and 05.
Checks baseline fairness, literature sufficiency, manuscript integration risk.

### Reviewer 2

Reads outputs 03 and 04.
Checks technical consistency, proof boundaries, experiment readiness, missing tests.

## Main-Agent Output

- `06_round2_integrated_publication_readiness_report.md`
- Must summarize what is ready, what remains P0, what can be integrated into the Chinese manuscript, and what cannot yet be claimed.
