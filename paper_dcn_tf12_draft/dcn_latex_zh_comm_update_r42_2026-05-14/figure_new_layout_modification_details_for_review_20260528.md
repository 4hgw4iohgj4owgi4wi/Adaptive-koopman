# Figure Layout Revision Details for Review

Review basis: `figure_new_layout_issues_fix_plan_20260528.md`

Target manuscript for the next approved edit: `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.tex`

Principle: this round should be a visual-layout correction only. It should not change experiment data, reported numerical values, method claims, or baseline interpretation. To preserve traceability, all regenerated figures should be saved with a new suffix such as `_layoutfix_20260528`, and the next manuscript should be copied to a derivative source before changing figure paths.

## Proposed File Strategy

| Item | Current file | Proposed new file after approval | Reason |
|---|---|---|---|
| Manuscript source | `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.tex` | `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev6_layoutfix_20260528.tex` | Keep the currently compiled PDF/source unchanged. |
| Fig. 4 | `figures/fig_nrkdcc_comm_mechanism_doublecol_20260528.pdf` | `figures/fig_nrkdcc_comm_mechanism_doublecol_layoutfix_20260528.pdf` | Preserve the old visual version for comparison. |
| Fig. 5 | `figures/fig_nrkdcc_fdi_ftc_timeline_pub_20260528.pdf` | `figures/fig_nrkdcc_fdi_ftc_timeline_layoutfix_20260528.pdf` | Fix axis/legend problems without overwriting. |
| Fig. 7 full diagnostic | `figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260528.pdf` | `figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_layoutfix_20260528.pdf` | Keep full diagnostic but improve spacing/legends. |
| Optional Fig. 7 compact main-text version | none | `figures/fig_nrkdcc_nooffset_hairpin_5mps_compact_main_layoutfix_20260528.pdf` | Use only if you approve splitting Fig. 7 into main + supplementary. |

## Fig. 5: FDI/FTC Timeline, Must Fix

Current LaTeX insertion:

- Source line: `manuscript...figrev5...tex:818-823`
- Current file: `figures/fig_nrkdcc_fdi_ftc_timeline_pub_20260528.pdf`
- Generator: `regenerate_all_figures_r42_20260514.py`, function `plot_fdi_ftc()`, around lines 494-578.

### Change 5.1: remove center y-label collision

Current code:

```python
ax2.set_ylabel("deficit norm")
axes[1].set_ylabel("deficit / command")
fig.subplots_adjust(..., wspace=0.25)
```

Proposed code-level change:

```python
ax2.set_ylabel("")
axes[1].set_ylabel("deficit / cmd.")
fig.subplots_adjust(top=0.88, bottom=0.10, left=0.065, right=0.985,
                    hspace=0.62, wspace=0.36)
```

Expected effect: the two middle y-axis labels no longer collide after the figure is inserted at `0.92\textwidth`.

### Change 5.2: filter `_child2` and all automatic legend labels

Current risky code around lines 568-570:

```python
ax2.axhline(0.0, color=ALT, ls=":", lw=0.85)
lines = ax.get_lines() + ax2.get_lines()
ax.legend(lines, [l.get_label() for l in lines], loc="upper left", ...)
```

Proposed replacement:

```python
ax2.axhline(0.0, color=ALT, ls=":", lw=0.85, label="_nolegend_")
lines = ax.get_lines() + ax2.get_lines()
pairs = [(h, h.get_label()) for h in lines
         if h.get_label() and not h.get_label().startswith("_")]
handles, labels = zip(*pairs)
ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.18),
          ncol=3, frameon=False, fontsize=6.8,
          handlelength=1.35, columnspacing=0.75)
```

Expected effect: remove the visible `_child2` legend item and keep auxiliary zero lines out of the legend.

### Change 5.3: move legends out of dense curve regions

Current problem points:

- Right-top subplot legend uses `loc="lower right"` and overlaps FTC command curves.
- Right-bottom subplot legend uses `loc="upper left"` and overlaps the certificate curve.
- Left-bottom subplot uses a different legend style from the other panels.

Proposed helper:

```python
def clean_legend(ax, ncol=2, anchor=(0.5, 1.18)):
    handles, labels = ax.get_legend_handles_labels()
    pairs = [(h, l) for h, l in zip(handles, labels)
             if l and not l.startswith("_")]
    if not pairs:
        return
    handles, labels = zip(*pairs)
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=anchor,
              ncol=ncol, frameon=False, fontsize=6.8,
              handlelength=1.35, columnspacing=0.75)
```

Apply:

```python
clean_legend(axes[0], ncol=3)
clean_legend(axes[1], ncol=3)
clean_legend(axes[2], ncol=2)
clean_legend(axes[3], ncol=3)
```

Expected effect: legends become consistent and stop covering important curves.

### Change 5.4: shorten panel titles and reduce visual weight

Current titles:

- `fault injection and identified degradation`
- `fault deficit and FTC command`
- `vehicle-level correction decomposition`
- `certificate and FTC mode monitor`

Proposed titles:

- `fault identification`
- `FTC command`
- `correction decomposition`
- `certificate/mode monitor`

Proposed rcParams:

```python
plt.rcParams.update({
    "axes.titlesize": 8.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.6,
    "ytick.labelsize": 6.6,
})
```

Expected effect: more room for out-of-axis legends without making the figure look crowded.

### Change 5.5: LaTeX update after regeneration

Current:

```latex
\includegraphics[width=0.92\textwidth]{figures/fig_nrkdcc_fdi_ftc_timeline_pub_20260528.pdf}
```

Proposed:

```latex
\includegraphics[width=0.92\textwidth]{figures/fig_nrkdcc_fdi_ftc_timeline_layoutfix_20260528.pdf}
```

Caption can remain unchanged unless the legend content changes substantially.

## Fig. 4: Communication-Mechanism Diagnostics, Should Fix

Current LaTeX insertion:

- Source line: `manuscript...figrev5...tex:807-812`
- Current file: `figures/fig_nrkdcc_comm_mechanism_doublecol_20260528.pdf`
- Generator: `generate_fig4_doublecol_20260528.py`

### Change 4.1: move panel labels outside axes

Current code around lines 59-76:

```python
ax.text(0.02, 0.94, text, transform=ax.transAxes, ..., bbox={...})
```

Proposed:

```python
def _panel_label(ax: plt.Axes, text: str) -> None:
    ax.text(
        -0.10, 1.08, text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.2,
        fontweight="bold",
        color="#243B53",
        clip_on=False,
    )
```

Expected effect: `(a)-(d)` no longer cover the high-value data area in panels (a), (b), and (d).

### Change 4.2: split label and title text

Current calls:

```python
_panel_label(axes[0], "(a) delay/loss")
_panel_label(axes[1], "(b) MPC signals")
_panel_label(axes[2], "(c) command dispersion")
_panel_label(axes[3], "(d) protective modes")
```

Proposed:

```python
_panel_label(axes[0], "(a)")
axes[0].set_title("delay/loss", loc="left", pad=3)

_panel_label(axes[1], "(b)")
axes[1].set_title("MPC signals", loc="left", pad=3)

_panel_label(axes[2], "(c)")
axes[2].set_title("command dispersion", loc="left", pad=3)

_panel_label(axes[3], "(d)")
axes[3].set_title("protective modes", loc="left", pad=3)
```

Expected effect: labels are still clear, but data regions stay unobstructed.

### Change 4.3: reduce visual noise in protective-mode panel

Current lines 138-140:

```python
axes[3].step(t, lateral_priority, where="post", ...)
axes[3].step(t, speed_cap, where="post", ...)
axes[3].step(t, fault, where="post", ...)
```

Proposed moderate option:

```python
axes[3].fill_between(t, 0, lateral_priority, step="post",
                     color=colors["purple"], alpha=0.20,
                     label="lateral priority")
if np.nanmax(speed_cap) > 0:
    axes[3].step(t, speed_cap, where="post", color=colors["green"],
                 lw=0.9, label="speed cap")
axes[3].step(t, fault, where="post", color=colors["red"],
             lw=0.95, label="fault flag")
```

Expected effect: dense purple switching is shown as a light activation band instead of many vertical lines. If `speed_cap` is always zero, it is not plotted as a meaningless flat line.

### Change 4.4: adjust top margin

Current:

```python
fig.subplots_adjust(left=0.075, right=0.985, top=0.92, bottom=0.12,
                    hspace=0.52, wspace=0.25)
```

Proposed:

```python
fig.subplots_adjust(left=0.085, right=0.985, top=0.90, bottom=0.12,
                    hspace=0.58, wspace=0.28)
```

Expected effect: external panel labels and top legends have enough air.

### Change 4.5: LaTeX update after regeneration

Current:

```latex
\includegraphics[width=0.88\textwidth]{figures/fig_nrkdcc_comm_mechanism_doublecol_20260528.pdf}
```

Proposed:

```latex
\includegraphics[width=0.88\textwidth]{figures/fig_nrkdcc_comm_mechanism_doublecol_layoutfix_20260528.pdf}
```

## Fig. 7: Hairpin Diagnostic Panel, Needs a Decision

Current LaTeX insertion:

- Source line: `manuscript...figrev5...tex:919-924`
- Current file: `figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260528.pdf`
- Current width: `0.76\textwidth`
- Original generator: `tf14_remaining_experiments_20260509/run_hairpin_r10c_tri_objective_supplement_20260519.py`, plotting block around lines 512-594.

### Option 7A: keep the full diagnostic in the main text, but make it larger

LaTeX change:

```latex
\includegraphics[width=0.90\textwidth]{figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_layoutfix_20260528.pdf}
```

Plot-level changes:

```python
fig.legend(handles, labels, loc="upper center",
           bbox_to_anchor=(0.5, 0.985),
           ncol=5, frameon=False, fontsize=7.0)
ax_xy.set_title("Team-center trajectory on the 5 m/s hairpin", pad=12)
fig.subplots_adjust(left=0.075, right=0.985, top=0.895, bottom=0.075,
                    hspace=0.66, wspace=0.32)
```

Force legends:

```python
ax_force_norm.legend(..., loc="upper center", bbox_to_anchor=(0.5, 1.20),
                     ncol=3, frameon=False, fontsize=6.5)
ax_force_xyz.legend(..., loc="upper center", bbox_to_anchor=(0.5, 1.20),
                    ncol=2, frameon=False, fontsize=6.4)
```

Pros: preserves all current diagnostic content in the main manuscript.

Cons: likely pushes more text to the next page and may reintroduce page 11/12 blank-space pressure.

### Option 7B: recommended route, split Fig. 7 into a compact main figure plus supplementary full diagnostic

Main-text Fig. 7 should keep only panels needed for the paper claim:

1. team-center trajectory,
2. team lateral error,
3. team longitudinal error,
4. payload resultant force,
5. payload planar force components.

Move these panels to supplement:

- vehicle lateral error,
- vehicle front steering,
- vehicle longitudinal speed,
- vehicle longitudinal acceleration input,
- vehicle color/method style legend if it only explains vehicle-level panels.

Proposed main-text file:

```latex
\includegraphics[width=0.86\textwidth]{figures/fig_nrkdcc_nooffset_hairpin_5mps_compact_main_layoutfix_20260528.pdf}
```

Proposed full diagnostic file for supplement:

```latex
Supplementary Fig. S3: figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_layoutfix_20260528.pdf
```

Proposed Fig. 7 caption:

```latex
\caption{Experiment 9: compact same-initial 5 m/s hairpin diagnostic. The panels show the centroid path, team lateral and longitudinal errors, payload resultant force, and planar force components. Dashed, starred, and solid curves denote \AKEdeg{}, \MethodHC{}, and \Method{}, respectively, separating high-curvature tracking from payload-force protection. Vehicle-level steering, speed, and acceleration diagnostics are retained in Supplementary Fig. S3.}
```

Pros: main text becomes readable and more compact; vehicle-level details are still preserved.

Cons: requires generating one additional compact figure and updating supplement references.

Reviewer-facing recommendation: choose Option 7B unless you strongly want the complete 8-panel diagnostic in the main text.

## Text Changes If Option 7B Is Approved

Current text in Section 5.5 can remain mostly unchanged. Only add one sentence after the Fig. 7 sentence:

```latex
Vehicle-level steering, speed, and acceleration traces are retained in Supplementary Fig.~S3 to keep the main diagnostic readable.
```

Do not add extra discussion; the current Section 5.5 is already compact.

## Validation Checklist After Approval

1. Regenerate Fig. 4, Fig. 5, and the approved Fig. 7 version as both `.pdf` and `.png`.
2. Compile the derivative source twice with XeLaTeX.
3. Render pages containing Fig. 4, Fig. 5, Fig. 7, Table 5, and references to PNG.
4. Check that:
   - no legend overlaps dense curves;
   - no `_child2` or other automatic legend label remains;
   - Fig. 7 is still on page 11 if this is required;
   - Table 5 is not split or visually truncated;
   - no `LaTeX Error`, missing figure, undefined reference, or undefined citation appears in the log.
5. Run PDF text checks for known bad strings:

```powershell
pdftotext <new_pdf> - | Select-String -Pattern "Systemsdoi|Transactionsdoi|Technologydoi|Sustainabilitydoi|Sensorsdoi|Informaticsdoi|tab:nooffset_degraded_sine|tab:nooffset_degraded_hairpin|tab:e3_certificate|single-column communication|Author Name|To add|stable_bilinear|raw6|_child"
```

## Approval Choices

Recommended selection:

- Approve Fig. 5 full fix: yes.
- Approve Fig. 4 panel-label and protective-mode fix: yes.
- Choose Fig. 7 Option 7B: compact main figure + full diagnostic in supplement.

Conservative selection:

- Approve Fig. 5 full fix.
- Approve Fig. 4 label-only fix, keep panel (d) step lines.
- Choose Fig. 7 Option 7A with larger full diagnostic in the main text.

