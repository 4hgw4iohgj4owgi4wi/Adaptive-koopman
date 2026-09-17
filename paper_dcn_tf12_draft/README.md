# DCN TF12 Draft Folder

This folder is a submission-oriented draft package for the manuscript:

`Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC`

It is built on top of the official `Digital Communications and Networks` LaTeX template files already included in this directory.

## Main files

- `manuscript_en.tex`
  - English submission draft in the DCN template style.
- `manuscript_zh.tex`
  - Chinese mirror draft using the same DCN template structure.
- `refs_tf12.bib`
  - BibTeX database used by both versions.
- `DCN-template.tex`
  - Original journal sample retained for reference.

## What is already filled in

- Title aligned with your requested submission direction.
- Abstract, motivation, method, experiment settings, same-task comparison, and conclusion.
- Quantitative comparison between:
  - the baseline paper `Adaptive Koopman Embedding for Robust Control of Complex Nonlinear Dynamical Systems`
  - the repository predecessor `TF11-A1`
  - the proposed repository method `TF12`
- A clean TikZ architecture figure that does not depend on the old mixed-language PNG assets.

## What you should replace before real submission

- Author names, affiliations, and corresponding author e-mail in both `.tex` files.
- Acknowledgements / funding information.
- Any wording you want to personalize for your research group.

## Compile

English version:

```bash
pdflatex manuscript_en.tex
bibtex manuscript_en
pdflatex manuscript_en.tex
pdflatex manuscript_en.tex
```

Chinese version:

```bash
xelatex manuscript_zh.tex
bibtex manuscript_zh
xelatex manuscript_zh.tex
xelatex manuscript_zh.tex
```

## Verification note

- MiKTeX was installed in the current workspace environment and both versions were compiled successfully.
- Generated outputs:
  - `manuscript_en.pdf`
  - `manuscript_zh.pdf`
- Bibliography and cross-references were resolved with the standard `LaTeX -> BibTeX -> LaTeX -> LaTeX` workflow.
- Remaining log messages are template/layout level warnings from the official DCN style, such as geometry over-specification, float placement adjustment (`h` to `ht`), and `balance` notices on the last page.

## Scope note

The current draft intentionally uses the completed cached A1 double-lane-change benchmark as the primary evidence base. The repository contains a hairpin extension, but that run was not fully completed in the cached notebook output, so it is mentioned only as future work instead of being claimed as a finished result.
