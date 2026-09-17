# TF14 DCN Article Completion Task Tree

## Goal

Prepare the remaining work plan for completing the DCN manuscript:

`Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC`

The output must support a baseline-facing, DCN-oriented paper narrative. The baseline is the uploaded paper:

`D:\LEARNING\ZNN\ZNN\+ Adaptive Koopman Embedding for Robust Control of Complex.pdf`

## Non-Negotiable Rules

- Do not modify existing manuscript DOCX, LaTeX, experiment scripts, or figure folders in this pass.
- Each worker writes only its assigned file.
- Reviewers do not modify files; reviewers output issue lists and revision recommendations only.
- The main agent decides whether revision is needed and integrates the final result.
- The paper must be framed around network-resilient cooperative transport under communication degradation, not local TF version history.

## Parallel Worker Tasks

### Worker A: Storyline and Contribution Tree

- Output file: `01_storyline_contribution_tree.md`
- Scope: topic cut-in, title angle, abstract logic, introduction narrative, contribution-to-method mapping.
- Must not edit: literature tables, method formulas, experiment specs.

### Worker B: Literature and Baseline Gap Map

- Output file: `02_literature_baseline_gap_map.md`
- Scope: recent literature categories, baseline comparison dimensions, citation-to-contribution mapping, legal-source reminder.
- Must not edit: method formulas, experiment specs, final integration.

### Worker C: Method and Theory Completion Tasks

- Output file: `03_method_theory_completion_tasks.md`
- Scope: model symbols, coordinate systems, TF14 Koopman network, MPC, FTC/safety, Lyapunov consistency tasks.
- Must not edit: literature map, experiment figures, final integration.

### Worker D: Experiment, Figure, and Ablation Task Plan

- Output file: `04_experiment_figure_ablation_plan.md`
- Scope: required experiments, figure list, ablations, metrics, plot style, evidence-to-claim mapping.
- Must not edit: storyline, literature map, method formulas.

## Reviewer Tasks

### Reviewer 1: Narrative and Novelty Review

- Reads worker A and B outputs.
- Checks: DCN fit, baseline fairness, contribution novelty, missing citations, overclaiming.
- Does not modify files.

### Reviewer 2: Technical and Evidence Review

- Reads worker C and D outputs.
- Checks: method-experiment consistency, symbol/proof gaps, missing ablations, validation risks.
- Does not modify files.

## Main-Agent Integration Output

- Final integrated file: `05_integrated_parallel_execution_plan.md`
- Includes: task tree, dependencies, deliverables, validation gates, risks, and immediate next actions.
