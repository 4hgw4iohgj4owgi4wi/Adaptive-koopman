# Paper Document Organization Index

This folder is a safe organized copy of the key paper documents. It does not move or delete the original files in `paper_dcn_tf12_draft`.

## Open This First

Current Chinese manuscript:

`01_CURRENT_MANUSCRIPT/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

This is the latest known Chinese version with TF14 integration and the Lyapunov proof inserted.

## Folder Map

### 00_README_INDEX

Navigation and manifests.

- `paper_dcn_tf12_draft_file_manifest.csv`: original root-file inventory.
- `paper_dcn_tf12_draft_directory_manifest.csv`: original subfolder inventory.
- `tf14_external_folder_manifest.csv`: TF14 result folders located at repository root.

### 01_CURRENT_MANUSCRIPT

Current and direct manuscript lineage.

- Latest working Chinese manuscript.
- Previous TF14-integrated manuscript.
- 2026-05-08 Chinese base manuscript.
- Current Chinese LaTeX draft and Markdown export.

Use this folder when editing the actual paper text.

### 02_DCN_TEMPLATE_LATEX

Digital Communications and Networks / Elsevier LaTeX material and English draft files.

Use this folder when migrating the Chinese manuscript into the final English LaTeX submission.

### 03_METHOD_THEORY_STABILITY

Method, TF14 update, gap-closure, and stability proof documents.

Use this folder when revising:

- vehicle/load modeling,
- Koopman network description,
- delay-compensated consensus MPC,
- FTC/safety layer,
- Lyapunov proof consistency.

### 04_EXPERIMENT_FIGURE_PLANS

Required experiment and figure specification documents.

Use this folder to decide which experiments and figures are still missing.

### 05_FIGURE_SCREENING_REPORTS

Existing figure audit documents and safe-supplement screening notes.

Use this folder to decide whether a figure is safe for the main text, supplement, or should be rerun.

### 06_LITERATURE_BASELINE

Recent literature support, BibTeX files, and baseline-related citation material.

Use this folder to align claims with published work and compare against the uploaded baseline paper.

### 07_SCRIPT_TRACEABILITY

Scripts used to generate manuscript variants, equation images, figure plans, and screening reports.

These scripts are copied for traceability only. Prefer editing the original scripts in `paper_dcn_tf12_draft` if a rerun is needed.

### 08_RENDER_QA_REFERENCES

Contact sheets and render checks for important DOCX/PDF outputs.

Use this folder to quickly inspect whether formulas and pages rendered correctly.

## Version Rule

When creating a new document, do not overwrite existing files. Use a dated suffix:

`*_YYYY-MM-DD.docx`

or, for a specific revision:

`*_tf14_<topic>_YYYY-MM-DD.docx`

## Main Risk

This is a readability organization folder, not a complete archive. Large raw experiment folders and render page dumps remain in their original locations to avoid duplicating unnecessary data.
