# 最新稿件图件新问题与修改建议

审核对象：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.tex` 及其当前引用图件。

重点图件：

- Fig. 4: `figures/fig_nrkdcc_comm_mechanism_doublecol_20260528.pdf`
- Fig. 5: `figures/fig_nrkdcc_fdi_ftc_timeline_pub_20260528.pdf`
- Fig. 7: `figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260528.pdf`

## 总体判断

这次新出现的问题主要不是数据内容错误，而是期刊版面下的可读性问题：局部轴标互相挤压、图例进入曲线区域、子图编号框遮挡曲线，以及多面板图在缩放后过密。建议下一轮只做图件排版修正，不再大幅调整正文。

优先级排序：

1. 先改 Fig. 5 的轴标重叠、图例冲突和 `_child2` 错误图例项。
2. 再改 Fig. 4 的 `(a)-(d)` 标签位置，避免挡住曲线。
3. 最后处理 Fig. 7 的整体拥挤和顶部图例/标题间距。

## Fig. 5: FDI/FTC timeline

源图：`figures/fig_nrkdcc_fdi_ftc_timeline_pub_20260528.pdf`

主要生成位置：`regenerate_all_figures_r42_20260514.py` 的 FDI/FTC timeline 片段，约第 500-578 行。

### 问题 1：中间轴标重叠、模糊

当前左上子图使用了 `twinx()`，右侧轴标为 `deficit norm`；右上子图左侧轴标为 `deficit / command`。两个子图相邻后，这两个纵轴标签在中间区域互相挤压，缩放进论文后更明显。

推荐改法：

- 最稳妥：去掉左上子图右轴的完整 y-label，只保留右轴刻度，并通过图例说明 `fault deficit norm`。
- 同时把右上子图 y-label 缩短为 `deficit / cmd.` 或 `norm / cmd.`。
- 若仍保留双轴标签，则把 `fig.subplots_adjust(wspace=0.25)` 改到 `wspace=0.36` 或 `0.40`，并给右轴设置 `labelpad=8-10`。

建议代码方向：

```python
ax2.set_ylabel("")  # left-top twin axis; label already appears in legend
axes[1].set_ylabel("deficit / cmd.")
fig.subplots_adjust(..., wspace=0.36)
```

### 问题 2：图例位置与曲线冲突

右上子图的 legend 放在 `lower right`，正好压在 `delta redistribution` 和 `ax redistribution` 附近；右下子图 legend 位于左上，也压住了 certificate 曲线起始段。左下子图虽然没有严重挡线，但图例风格与右上不一致。

推荐改法：

- 四个子图统一使用同一种 legend 风格，优先采用“子图上方居中、无边框或统一浅边框”的方式。
- 不建议把 Fig. 5 的 legend 放在曲线内部，尤其是右上和右下子图。
- 右上子图可用 `bbox_to_anchor=(0.5, 1.18), ncol=3`。
- 右下子图可用 `bbox_to_anchor=(0.5, 1.18), ncol=3`，或把 mode/margin 说明移到 caption。

建议代码方向：

```python
def clean_legend(ax, handles=None, labels=None, ncol=2):
    if handles is None:
        handles, labels = ax.get_legend_handles_labels()
    pairs = [(h, l) for h, l in zip(handles, labels) if l and not l.startswith("_")]
    if not pairs:
        return
    handles, labels = zip(*pairs)
    ax.legend(
        handles, labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.18),
        ncol=ncol,
        frameon=False,
        fontsize=6.8,
        handlelength=1.4,
        columnspacing=0.8,
    )
```

### 问题 3：右下子图出现 `_child2`

右下子图 legend 中出现 `_child2`，这是 Matplotlib 自动对象被错误加入图例造成的。原因是 `ax2.axhline(0.0, ...)` 这类辅助线被 `ax.get_lines() + ax2.get_lines()` 收集后进入 legend。

推荐改法：

```python
ax2.axhline(0.0, color=ALT, ls=":", lw=0.85, label="_nolegend_")

handles = ax.get_lines() + ax2.get_lines()
labels = [h.get_label() for h in handles]
pairs = [(h, l) for h, l in zip(handles, labels) if not l.startswith("_")]
```

这个问题必须改，否则审稿人会直接认为图件没有认真检查。

### 问题 4：标题字号偏大

Fig. 5 的子图标题在论文中显得比 Fig. 4 更重，压缩后也会让图例更难放。建议统一为：

```python
plt.rcParams.update({
    "axes.titlesize": 8.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.6,
    "ytick.labelsize": 6.6,
})
```

如果标题仍占空间，可把长标题改短：

- `fault injection and identified degradation` -> `fault identification`
- `fault deficit and FTC command` -> `FTC command`
- `vehicle-level correction decomposition` -> `correction decomposition`
- `certificate and FTC mode monitor` -> `certificate/mode monitor`

## Fig. 4: communication-mechanism diagnostics

源图：`figures/fig_nrkdcc_comm_mechanism_doublecol_20260528.pdf`

生成脚本：`generate_fig4_doublecol_20260528.py`

### 问题 1：`(a)-(d)` 标签框挡住曲线

当前 `_panel_label()` 使用：

```python
ax.text(0.02, 0.94, text, transform=ax.transAxes, ...)
```

这个位置在每个坐标轴内部左上角，带白色背景框。在 panel (a)、(b)、(d) 中会压住高值区域或保护模式线条。这个问题在截图里已经比较明显。

推荐改法：

- 不要把 `(a)-(d)` 放在坐标轴内部。
- 改为放在坐标轴外侧左上角，或者直接写入 title。

首选方案：

```python
def _panel_label(ax, text):
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

然后每个 panel 用短标题：

```python
axes[0].set_title("delay/loss", loc="left", pad=3)
axes[1].set_title("MPC signals", loc="left", pad=3)
axes[2].set_title("command dispersion", loc="left", pad=3)
axes[3].set_title("protective modes", loc="left", pad=3)
```

这样 `(a)-(d)` 不挡曲线，标题也仍然保留。

### 问题 2：panel (d) 的竖线过密

`lateral priority` 在 panel (d) 中形成很多密集竖线，虽然表示模式开关，但视觉上像噪声。如果这个图是主文图，建议用半透明背景区间或稀疏 marker 替代密集 step 线。

推荐方案：

- `fault flag` 保留 step 线。
- `lateral priority` 改成浅紫色 `fill_between` 区间，透明度 `alpha=0.18-0.25`。
- `speed cap` 若一直为 0，可只保留 legend 或在 caption 中说明，不必占一条曲线。

### 问题 3：legend 与 panel label 的垂直空间冲突

当前 legend 在每个子图上方，panel label 又在图内左上角，两者在视觉上形成重复的“顶部元素”。若 label 外移，legend 位置可以保持；若 label 继续在图内，legend 就会显得压迫。

推荐改法：先外移 label，再保持现有 legend；不要同时把 legend 和 label 都放在图内。

## Fig. 7: hairpin diagnostic panel

源图：`figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260528.pdf`

关联生成脚本：`tf14_remaining_experiments_20260509/run_hairpin_r10c_tri_objective_supplement_20260519.py`，约第 512-594 行。

### 问题 1：主文中太密

Fig. 7 是一个包含轨迹、团队误差、车辆误差、转角、速度、加速度、合力、分力的多面板诊断图。当前最新稿件用：

```latex
\includegraphics[width=0.76\textwidth]{figures/fig_nrkdcc_nooffset_hairpin_5mps_panel_force_20260528.pdf}
```

这个宽度下，8 个子图会被压得太小。截图中局部还能看，但进入双栏论文后，底部 force legend、车辆曲线和坐标轴刻度都会吃力。

推荐改法：

- 如果 Fig. 7 保留主文，使用 `figure*` 并放大到 `0.92\textwidth` 或 `0.95\textwidth`。
- 如果版面紧张，主文只保留：轨迹、team lateral/longitudinal error、payload resultant force、payload planar force components。车辆级 steering/speed/acceleration 放 Supplementary。

### 问题 2：顶部 legend 与标题太近

当前源脚本中：

```python
fig.legend(..., bbox_to_anchor=(0.5, 0.958), ncol=5, ...)
```

legend 与 `Team-center trajectory on the 5 m/s hairpin` 标题距离过近，截图中已经接近挤压。建议把 legend 放到更上方，或者放在标题下方但独占一行。

推荐改法：

```python
fig.legend(..., bbox_to_anchor=(0.5, 0.985), ncol=5, ...)
ax_xy.set_title("Team-center trajectory on the 5 m/s hairpin", pad=12)
fig.subplots_adjust(top=0.90)
```

若仍然拥挤，改为两行 legend，`ncol=3`。

### 问题 3：底部 force legends 太小且压缩

底部两个 force 子图内部 legend 字号只有 `5.8-6.0`，缩放后容易不可读。建议改为：

- force resultant 子图只保留三条方法线 legend。
- planar force 子图 legend 改成 `ncol=2`，放到图内右上或图外上方。
- 若主文版面太小，分力图可以移到 Supplementary。

### 问题 4：车辆级曲线过密

`vehicle front steering` 和 `vehicle longitudinal acceleration input` 同时展示多车辆、多方法、多样式，信息量很大，但在主文缩放后会变成线团。建议主文里只保留团队级误差和 force，车辆级诊断作为机制补充图。

## 其它图件统一建议

### 统一图例风格

现在 Fig. 4 的 legend 是带浅边框外置，Fig. 5 有的无框、有的带框且在图内，Fig. 7 又是全局 legend + 局部 legend 混合。建议统一为：

- 主文多面板图：legend 尽量放子图外上方或全图上方。
- 不要把 legend 放在曲线密集区。
- 图例项过滤所有以下划线开头的自动 label。
- 同一张图内不要混用有框和无框 legend，除非有明确理由。

### 统一 panel label 风格

建议全稿采用一种方式：

```python
ax.text(-0.10, 1.08, "(a)", transform=ax.transAxes, clip_on=False, fontweight="bold")
ax.set_title("short panel title", loc="left", pad=3)
```

不要再用带白底框的 `(a) title` 放在数据区域内。

### 输出与插入建议

- 保留 PDF 矢量图作为论文插入文件。
- 每次改图后同步保存 PNG 预览，便于审查。
- 改图后重新编译最新稿件，并重点查看 PDF 中的实际缩放效果，而不是只看单独 PNG。

## 推荐下一轮操作顺序

1. 修改 Fig. 5 生成代码，解决轴标重叠、legend 冲突、`_child2` 错误项。
2. 修改 Fig. 4 `_panel_label()`，把 `(a)-(d)` 移到坐标轴外，并保留短标题。
3. 决定 Fig. 7 是否继续作为主文大图：若继续保留，改成 `figure*` + `0.92\textwidth`；若追求紧凑，拆分为主文精简图和 Supplementary 诊断图。
4. 重新生成 PDF/PNG 图件，重新编译 `figrev5` 后做一次整页视觉检查。

## 结论

Fig. 5 目前必须修；Fig. 4 的子图标签位置也应修；Fig. 7 不一定内容错误，但作为主文图过密，需要在“放大保留”和“拆分到 Supplementary”之间做选择。最推荐的路线是：Fig. 5 和 Fig. 4 直接修图，Fig. 7 主文保留精简版，完整诊断版放 Supplementary。
