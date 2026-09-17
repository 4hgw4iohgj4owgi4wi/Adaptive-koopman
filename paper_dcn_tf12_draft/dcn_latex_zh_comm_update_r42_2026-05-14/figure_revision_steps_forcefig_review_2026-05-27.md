# 拟修改步骤细节：基于 `figure_suitability_audit_forcefig_2026-05-27.md`

目标版本：英文 LaTeX 稿 `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex`  
处理范围：只改英文版本的图、图注、正文图文对应关系；中文稿暂不动。  
总体原则：优先消除“图面证据和正文论断不一致”的硬伤，然后压缩主文图组，最后统一图内标题和方法名。

## 0. 审核前结论

建议执行“稳妥压缩版”：

1. Fig. 6 不强行声称 packet loss，先改成 `delay-dominant communication-stress diagnostics`，除非后续决定重跑出真正有 loss/dropout 的通信样本。
2. Fig. 11 保留为主文核心图，但重画为 4 个核心面板：trajectory、team errors、payload resultant force、force peak 或 force components。车辆级 steering/speed/acceleration 放补充材料。
3. Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 不再作为主文正向证据图；其中 Fig. 3、5、8、9 可转补充材料，Fig. 10 只作为 limitation/sensitivity 证据。
4. 全部图内标题删除 `E0/E1/E3/E9/R42/stress-style/seed=2026` 这类内部调试残留。

## 1. 必改项 A：修正 Fig. 6 的通信证据口径

### 问题

当前 Fig. 6 图面中 `quality` 基本为 1，`dropout` 和 `loss ratio` 基本为 0；但正文和图注写了 packet loss。审稿风险是“正文声称的通信退化类型没有被图证明”。

### 默认修改方案 A1：不重跑，只收窄文字

适用条件：接受当前 Fig. 6 只证明 delay + measurement/channel perturbation，不证明 packet-loss events。

修改位置：

- `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex:820`
- `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex:824--826`

拟替换图注：

```latex
\caption{Experiment 3: delay-dominant communication-stress diagnostics. In the 5 m/s high-delay hairpin sample, the figure reports adjacent and upper-to-lower transmission delays, logged link-quality and loss indicators, perturbed relative-distance and team-lateral-error channels, and the protective actions induced by 4WS local paths, lateral-priority weighting, and constraint tightening. In this representative run, the visible communication stress is delay and channel perturbation rather than packet-loss events.}
```

拟替换正文第 824--826 行：

```latex
Figure~\ref{fig:delay_mechanism_evidence} shows a delay-dominant communication-stress sample: adjacent relative-information channels and upper-to-lower desired-path communication have nonzero delay, while the logged loss/dropout indicators remain inactive in this representative run. The controller records relative-distance error, team lateral-error channel error, and upper-layer command bias, while activating 4WS local paths, lateral-priority weighting, and communication-aware constraint tightening.

The communication model treats these signals as auditable link-level perturbations rather than as unstructured internal controller noise. In this sample, delay compensation affects neighbor prediction, local-path preview, link-weight scheduling, and constraint tightening; packet-loss robustness is supported by the model/protocol and ablation tables rather than by this particular diagnostic trace.
```

保留不改的位置：

- 第 279 行的 packet-loss variable 定义可保留，因为这是模型定义。
- 第 429 行的 training/scenario protocol 里 `delay/loss variables` 可保留，因为它描述实验协议，不是 Fig. 6 的单图证据。
- 第 603 行稳定性假设中的 packet loss 可保留，因为它是理论扰动项，不依赖 Fig. 6 单条曲线。

### 可选修改方案 A2：重跑 Fig. 6

适用条件：希望 Fig. 6 本身也直接显示 packet loss/dropout。

执行步骤：

1. 找到 Fig. 6 生成源：`regenerate_all_figures_r42_20260514.py:425--486`。
2. 重跑或选择一个已有诊断样本，要求图中至少出现：
   - `q_k^{net}` 或 link quality 明显低于 1；
   - dropout/loss ratio 非零；
   - delay 和 loss/dropout 与 protection action 在时间上有对应关系。
3. 重新生成 `figures/fig_nrkdcc_delay_mechanism_evidence.pdf`。
4. 如果重跑后 loss/dropout 确实可见，则保留 `packet loss` 表述；否则仍按 A1 收窄。

默认建议：先执行 A1。A2 成本较高，而且若新图不够清楚，反而会扩大风险。

## 2. 必改项 B：统一图内标题，删除内部实验编号

### 目标

最终投稿图内不应出现 `E1`, `E3`, `E9`, `E0`, `R42`, `stress-style`, `seed=2026` 这类内部调试标识。

### 需要修改的生成脚本

`regenerate_all_figures_r42_20260514.py`

拟替换：

```python
fig.suptitle("E1 training evidence", ...)
```

改为：

```python
fig.suptitle("Koopman lifting training and validation loss", ...)
```

```python
fig.suptitle("E1 Koopman prediction and input-aware stability projection", ...)
```

改为：

```python
fig.suptitle("Koopman prediction and input-aware stability projection", ...)
```

```python
fig.suptitle("E9 closed-loop Koopman-setting ablation", ...)
```

改为：

```python
fig.suptitle("Closed-loop Koopman-setting ablation", ...)
```

```python
fig.suptitle("R42 delay compensation and upper-lower communication evidence", ...)
```

改为：

```python
fig.suptitle("Delay-compensation and communication-channel diagnostics", ...)
```

```python
fig.suptitle("E0 mixed fault/noise FDI/FTC and safety-monitor timeline", ...)
```

改为：

```python
fig.suptitle("FDI/FTC and safety-monitoring timeline", ...)
```

```python
fig.suptitle("E3 pressure-mode Lyapunov/ISS certificate closure", ...)
```

改为：

```python
fig.suptitle("Mode-wise Lyapunov/ISS certificate closure", ...)
```

可同步清理但不作为主文重点：

```python
fig.suptitle(f"R42 same-path speed panel: {speed} m/s", ...)
```

改为：

```python
fig.suptitle(f"Same-path speed-sensitivity diagnostic at {speed} m/s", ...)
```

```python
fig.suptitle("R42 upper/lower communication restructure and speed-gated validation", ...)
```

改为：

```python
fig.suptitle("Communication-architecture and speed-sensitivity summary", ...)
```

### Fig. 11 相关脚本

`tf14_remaining_experiments_20260509/run_hairpin_r10c_tri_objective_supplement_20260519.py`

拟替换：

```python
"r10c": "NR-KDCC w/o payload protection",
```

改为：

```python
"r10c": "NR-KDCC-HC",
```

图例：

```python
label="NR-KDCC w/o payload protection (*)"
```

改为：

```python
label="NR-KDCC-HC (*)"
```

标题：

```python
ax_xy.set_title("Hairpin team-center x-y trajectory, v=5 m/s, seed=2026")
```

改为：

```python
ax_xy.set_title("Hairpin team-center trajectory at 5 m/s")
```

总标题：

```python
fig.suptitle("Same-initial degraded-baseline stress-style panel", ...)
```

改为：

```python
fig.suptitle("Hairpin tracking and payload-force trade-off under variable delay", ...)
```

## 3. 必改项 C：简化 Fig. 11 为主文图

### 问题

当前 Fig. 11 已补回 force 面板，但图面过密。主文里应快速证明两个结论：

1. `NR-KDCC-HC` 相对 `AKE-M degraded` 改善高曲率 tracking；
2. full `NR-KDCC` 相对 `NR-KDCC-HC` 降低 force peak，但牺牲部分 lateral tracking gain。

不应把 Fig. 11 写成 full `NR-KDCC` 的 force peak 全面优于 `AKE-M degraded`。

### 拟重画文件

新建主文简化图：

```text
figures/fig_nrkdcc_hairpin_force_tradeoff_compact_20260527.pdf
figures/fig_nrkdcc_hairpin_force_tradeoff_compact_20260527.png
```

数据来源不重跑，只复用已有数据：

```text
paper_dcn_tf12_draft/hairpin_r10c_tri_objective_supplement_2026-05-19/data/
paper_dcn_tf12_draft/hairpin_r10c_tri_objective_supplement_2026-05-19/data/hairpin_r10c_tri_objective_summary.csv
```

拟保留 4 个面板：

1. team-center x-y trajectory；
2. team lateral/longitudinal error；
3. payload resultant force；
4. force peak bar，显示 `AKE-M degraded`, `NR-KDCC-HC`, `NR-KDCC` 三者峰值。

车辆级 lateral error、steering、speed、acceleration 不放主文图，转入补充材料或保留在完整诊断图文件中。

### LaTeX include 替换

修改位置：

- `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex:993`

由：

```latex
\includegraphics[width=0.88\textwidth]{figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260527.pdf}
```

改为：

```latex
\includegraphics[width=0.82\textwidth]{figures/fig_nrkdcc_hairpin_force_tradeoff_compact_20260527.pdf}
```

### Fig. 11 caption 替换

修改位置：

- `manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex:994`

拟替换为：

```latex
\caption{Experiment 9: hairpin tracking and payload-force trade-off under fault and variable delay. The figure compares \AKEdeg{}, \MethodHC{}, and \Method{} from the same initial condition on the 5 m/s hairpin. The panels report the team-center trajectory, team lateral/longitudinal errors, planar payload resultant force, and force-peak summary. The diagnostic supports two bounded claims: \MethodHC{} improves high-curvature tracking relative to \AKEdeg{}, whereas full \Method{} reduces the force peak relative to \MethodHC{} by activating payload protection at the cost of part of the lateral-tracking gain.}
```

### 正文保留/微调

第 998--1000 行目前已经基本正确，建议只做术语统一，把 `tracking-priority variant` 明确为 `\MethodHC{}`，并把 `force peak` 结论继续限定为相对 `\MethodHC{}`。

拟替换第 998 行：

```latex
Table~\ref{tab:nooffset_degraded_hairpin} and Fig.~\ref{fig:nooffset_hairpin_5mps_panel} show two effects. First, \MethodHC{} reduces team-center lateral RMSE from $0.298869$ m to $0.085119$ m and maximum lateral error from $0.587425$ m to $0.180423$ m relative to \AKEdeg{}, supporting the role of the high-curvature local-path and lateral-priority Koopman-MPC branch under variable delay. Second, \MethodHC{} increases the planar payload resultant-force peak to $15487.33$ N, compared with $5544.45$ N for \AKEdeg{}, indicating that aggressive lateral correction transfers part of the cost to the payload-force channel.
```

第 1000 行可保留，或压缩为：

```latex
After activating payload protection, \Method{} reduces maximum connection utilization from $0.778074$ to $0.403050$ and force peak from $15487.33$ N to $8874.04$ N relative to \MethodHC{}, while longitudinal RMSE decreases from $8.071913$ m to $6.341244$ m. Lateral RMSE increases from $0.085119$ m to $0.264159$ m, so the full method should be described as a tracking--force trade-off rather than a uniform improvement on all metrics.
```

## 4. 主文图组压缩方案

### 建议保留在主文的图

1. Fig. 1：总体框架。
2. Fig. 2：在线信号流/控制流程。
3. Fig. 4：Koopman prediction + IRSP audit。
4. Fig. 6：按 A1 修正后的 delay-dominant communication diagnostic。
5. Fig. 7：FDI/FTC timeline，清理标题后保留。
6. 简化 Fig. 11：hairpin tracking 与 force trade-off。

### 建议转补充材料或从主文移除的图

1. 当前 Fig. 3：训练 loss 图，转补充材料；正文保留一句训练收敛说明即可。
2. 当前 Fig. 5：Koopman setting ablation 图，与 Table 2 重复，转补充材料；正文以 Table 2 为主。
3. 当前 Fig. 8：mode-wise certificate closure，可用正文和 Table 11 承接；若保留则转补充材料。
4. 当前 Fig. 9：2/5 m/s same-seed full diagnostic，转补充材料；正文保留 Table 8 和一句代表性说明。
5. 当前 Fig. 10：10/15 m/s 高速诊断，不作为正向主文证据；转补充材料或只在 limitation 中引用。

注意：如果把这些图移出主文，图号会重排。执行时应优先使用 `\label{...}` 交叉引用，不手写图号。

## 5. 对正文交叉引用的具体处理

### Fig. 3 转补充后的替换

当前：

```latex
Figure~\ref{fig:e1_koopman_training_loss} shows that ...
```

建议改为：

```latex
The training and validation losses decrease and plateau after about 60 epochs, with no obvious sustained train--validation separation; the full loss trace is provided in the supplementary diagnostics.
```

### Fig. 5 转补充后的替换

当前：

```latex
Table~\ref{tab:e9_koopman_dim} and Fig.~\ref{fig:e9_koopman_dim_ablation} show that ...
```

建议改为：

```latex
Table~\ref{tab:e9_koopman_dim} shows that ...
```

### Fig. 8 转补充后的替换

当前：

```latex
The mode-wise decomposition in Fig.~\ref{fig:modewise_certificate_closure} further shows positive margins ...
```

建议改为：

```latex
A mode-wise diagnostic, reported in the supplementary material, further separates pressure-scenario nominal and FTC-flagged steps and shows positive margins for those logged modes.
```

### Fig. 9 和 Fig. 10 转补充后的替换

当前：

```latex
Table~\ref{tab:nooffset_degraded_sine} and Figs.~\ref{fig:nooffset_fault_low_speed_panel}--\ref{fig:nooffset_fault_high_speed_panel} show that ...
```

建议改为：

```latex
Table~\ref{tab:nooffset_degraded_sine} summarizes the same-initial-condition sine diagnostics. At 5 m/s, \Method{} reduces team-center lateral RMSE from $0.044080$ m to $0.029711$ m, with zero maximum pointwise gap and a 100\% pointwise win rate. At 15 m/s, the improvement is marginal, so the high-speed run is treated as a limitation diagnostic rather than robustness evidence; the full trajectory panels are provided in the supplementary diagnostics.
```

## 6. 编译和检查步骤

执行修改后按以下顺序检查：

1. 重新生成被改标题的图 PDF/PNG。
2. 编译英文稿：

```powershell
xelatex -interaction=nonstopmode -halt-on-error manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex
bibtex manuscript_en_ch4_ch7_balanced_full_2026_05_26
xelatex -interaction=nonstopmode -halt-on-error manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex
xelatex -interaction=nonstopmode -halt-on-error manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex
```

如果正式 PDF 被占用，则临时使用：

```powershell
xelatex -jobname=manuscript_en_ch4_ch7_balanced_full_2026_05_26_figclean -interaction=nonstopmode -halt-on-error manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex
```

3. 检查日志：

```powershell
Select-String -Path .\manuscript_en_ch4_ch7_balanced_full_2026_05_26*.log -Pattern "Undefined|Citation.*undefined|LaTeX Error|Emergency stop|Fatal|Rerun to get"
```

4. 渲染并检查 Fig. 6、Fig. 7、简化 Fig. 11 所在页：

```powershell
pdftoppm -png -r 140 -f 8 -l 14 .\manuscript_en_ch4_ch7_balanced_full_2026_05_26.pdf .\qa_figclean_page
```

5. 最终人工检查点：
   - Fig. 6 不再出现“图面 loss/dropout 为 0，但正文说 packet loss”的矛盾。
   - 所有主文图内不再出现 `E0/E1/E3/E9/R42/stress-style/seed=2026`。
   - Fig. 11 图例统一使用 `NR-KDCC-HC`，不再和 `NR-KDCC w/o payload protection` 混用。
   - Fig. 11 的文字只声称 full `NR-KDCC` 相对 `NR-KDCC-HC` 降低 force peak，不声称 force peak 全面优于 `AKE-M degraded`。
   - 主文图数量减少后，图号、交叉引用、浮动位置没有乱。

## 7. 需要你审核确认的决策点

1. Fig. 6 走 A1 文字收窄，还是 A2 重跑出可见 packet loss/dropout？
2. Fig. 11 是否接受 4 面板主文简化版？若接受，完整 8 面板 force 诊断图作为补充材料保留。
3. 是否同意把当前 Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 移出主文？
4. 方法名统一采用 `NR-KDCC-HC`，不再在图例中写 `NR-KDCC w/o payload protection`，是否确认？

