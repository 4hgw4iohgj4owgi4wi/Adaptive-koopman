# Figure suitability audit for `manuscript_en_ch4_ch7_balanced_full_2026_05_26_forcefig.pdf`

审核对象：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_forcefig.pdf`

审核方式：重新渲染 PDF 第 3-14 页，逐页检查 Fig. 1-Fig. 11 的图面、图题、图注和正文论断一致性。重点复查上一版中 Fig. 11 缺少 force 面板的问题。

## 总体结论

这版比上一版明显好，尤其是 **Fig. 11 已经补回 payload resultant force 和 planar force components 面板**，上一版“图注写了 force、图里没有 force”的硬伤已解决。现在 Fig. 11 可以作为 hairpin/force trade-off 的候选主文图。

但仍然不建议把全部图直接作为主文最终版提交。主要剩余问题如下：

1. **Fig. 6 仍是最大风险。** 图面中的 `quality` 基本恒为 1，`upper-lower dropout` 和 `loss ratio` 基本恒为 0，但正文和图注仍在说 packet loss / link-quality / communication perturbation。第 8 页正文甚至写到 `nonzero delay and packet loss`，这和 Fig. 6 的可见曲线冲突。
2. **图内标题仍有内部实验编号残留。** 例如 Fig. 3 的 `E1 training evidence`、Fig. 5 的 `E9 closed-loop...`、Fig. 6 的 `R42...`、Fig. 7 的 `E0...`、Fig. 8 的 `E3...`、Fig. 9-11 的 `stress-style panel`。这些像内部调试图，不像最终投稿图。
3. **Fig. 9-Fig. 11 仍然偏密。** 它们适合说明诊断过程，但在主文 A4 双栏/单栏缩放后，车辆级曲线、图例和局部细节会让审稿人难以快速读出结论。
4. **Fig. 11 的论断要收窄。** 该图可以证明 NR-KDCC 相对 `NR-KDCC w/o payload protection / NR-KDCC-HC` 降低 force peak，并在 tracking 与 force cost 之间折中；但不应写成 force 全面优于 AKE-M degraded，因为表格和图面都显示 AKE-M degraded 的 force peak 更低，但 tracking 更差。

## 和上一版相比的变化

| 项目 | 上一版问题 | 这版状态 | 结论 |
|---|---|---|---|
| Fig. 11 force 面板 | 图注提到 force，但图里没有 force 面板。 | 已补回 `payload resultant force` 和 `payload planar force components`。 | 关键硬伤已修复。 |
| Fig. 11 论证能力 | 只能看到 tracking/input 诊断，无法验证 force trade-off。 | 现在可以支持 force trade-off，但图面很密。 | 可保留，但建议简化。 |
| Fig. 6 通信证据 | link quality/loss/dropout 曲线平，支撑不足。 | 仍然平，而且正文现在明确说 nonzero packet loss。 | 需要优先修。 |
| 内部图题 | 多处有 E0/E1/E3/E9/R42/stress-style。 | 仍然存在。 | 最终投稿前必须统一。 |

## 逐图意见

| 图号 | 当前判断 | 主要问题 | 建议 |
|---|---|---|---|
| Fig. 1 | 主文可保留 | 框架图清楚，风格较统一；局部小图标和小字略小。 | 保留。若版面允许，适当放大或跨栏；图内不要再塞更多说明。 |
| Fig. 2 | 主文可保留 | 方法流程完整，但图注过长，图中底部 dashed path 注释很小。 | 保留为核心方法图。caption 压缩，详细解释放正文；图内小注释可删除或放大。 |
| Fig. 3 | 补充材料优先 | 训练损失图属于训练收敛诊断，不能作为闭环稳定或鲁棒控制证据。图内 `E1 training evidence` 是内部标题。 | 可移至补充材料。若主文保留，改标题为 `Koopman lifting training and validation loss`，删除 `E1`。 |
| Fig. 4 | 主文应保留 | Koopman 预测、rollout audit、IRSP 半径审计都直接支撑方法。图中信息较多但可读。 | 保留。图内 `E1` 可删；caption 可略压缩。 |
| Fig. 5 | 补充材料优先 | 与 Table 2 重复；图内标题 `E9` 与 caption 的 Experiment 2 不一致。 | 建议移至补充材料。若保留，改标题为 `Closed-loop Koopman-setting ablation`，统一 K0/K1/K2/K3 名称和正文表述。 |
| Fig. 6 | **需要重画或改正文/图注** | 最大问题仍在。图中 upper-layer delay 非零，但 `quality=1`、`dropout=0`、`loss ratio=0`；保护动作也主要只有一个短暂 local path active，lateral priority 和 constraint tightening 几乎不动。正文却说 nonzero packet loss，caption 也写 packet loss。 | 如果确实有 packet loss，请重跑/重画让 loss/dropout 曲线显示出来；如果该样本只有 delay 和 measurement corruption，就把正文和 caption 改成 `delay-dominant communication stress`，删除 packet-loss 证据表述。 |
| Fig. 7 | 主文可保留但需排版清理 | FDI/FTC 时间线有价值，但右上子图坐标轴和 label 拥挤，左/右轴混排影响阅读。图内 `E0` 是内部编号。 | 保留但重排。建议用共享时间轴的 4 行图：fault flag/residual、FTC redistribution、vehicle correction、certificate/mode。删 `E0`。 |
| Fig. 8 | 补充材料或表格替代 | 图形信息量仍偏低，只展示两个 scenario 的 pass rate 和 positive margin。图内 `E3` 与 Experiment 5 不一致。 | 不建议主文保留。可用 Table 8 或一句正文解释替代；若保留，删除 `E3`，并加入 aggregate negative margin/positive mode-wise margin 的对照。 |
| Fig. 9 | 补充材料优先 | 2 m/s 和 5 m/s 的 same-seed 诊断图很完整，但车辆级曲线太密，主文读者不易快速读结论。图内 `stress-style panel` 不适合投稿。 | 放补充材料。主文若必须保留，只保留 trajectory、team lateral error、team longitudinal error 三个面板。 |
| Fig. 10 | 不宜作为正向主文证据 | 10 m/s 和 15 m/s 明显展示速度敏感性，尤其纵向误差较大。适合作为 limitation/sensitivity，而不是 robustness 主证据。 | 放补充材料或局限性讨论。不要用它证明“高速度下仍稳定优越”。 |
| Fig. 11 | **主文候选，但要简化和改标题** | force 面板已补齐，图注和图面基本一致。仍有三个问题：图面过密；图内标题 `stress-style panel` 和 `seed=2026` 像调试图；legend 中 `NR-KDCC w/o payload protection` 与 caption 中 `NR-KDCC-HC` 需要统一。 | 可作为主文 hairpin/force trade-off 图，但建议压缩成 4 个核心面板：trajectory、team errors、payload resultant force、force components 或 force peak bar。车辆级 steering/speed/acceleration 放补充材料。 |

## 推荐主文图组

### 精简版

1. Fig. 1：总体框架。
2. Fig. 2：在线信号流/控制流程。
3. Fig. 4：Koopman prediction + IRSP audit。
4. 修订后的 Fig. 6：只在重画或改成 delay-dominant 后保留。
5. 简化后的 Fig. 11：hairpin tracking 与 force trade-off。

### 完整版

1. Fig. 1。
2. Fig. 2。
3. Fig. 4。
4. 修订后的 Fig. 6。
5. 清理后的 Fig. 7。
6. 简化后的 Fig. 11。

Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 建议进 supplementary material。

## 必须优先改的地方

### 1. Fig. 6 与正文通信表述不一致

当前正文写法和图面不一致。第 8 页正文提到 Fig. 6 shows `nonzero delay and packet loss`，但 Fig. 6 中 packet loss/dropout 是 0。这个问题比上一版更明显，因为现在正文的表述更直接。

建议二选一：

- **重跑图**：让 packet loss、dropout、link quality drop 真正在曲线上出现，并对应到 delay compensation/protection action。
- **改文字**：如果代表性样本只有 high delay 和 corrupted measurement，则全部改成 `delay-dominant communication perturbation`，不要声称 packet loss 证据。

### 2. Fig. 11 要保留，但标题和方法名必须正式化

Fig. 11 现在可以支撑 force trade-off，但图内标题和 legend 需要改：

- `Same-initial degraded-baseline stress-style panel` 改为 `Hairpin tracking and payload-force trade-off under variable delay`。
- `seed=2026` 不建议放在图题里，可放实验设置或补充材料。
- `NR-KDCC w/o payload protection` 与 `NR-KDCC-HC` 选一个统一名称，不要图例和 caption 混用。
- 结论应写成：NR-KDCC 相对无 payload-protection 的 high-curvature branch 降低 force peak，并保持可接受 tracking；不要写成 force peak 全面低于 AKE-M degraded。

### 3. 删除所有内部图号/调试标题

最终投稿图中建议删除或替换：

- `E1 training evidence`
- `E1 Koopman prediction...`
- `E9 closed-loop...`
- `R42 delay compensation...`
- `E0 mixed fault/noise...`
- `E3 pressure-mode...`
- `Same-initial degraded-baseline stress-style panel`

统一改为正式图题，并与 caption 的 Experiment 编号一致。

## 最终建议

这版可以进入下一轮正文整合，但还不是最终投稿图版本。我的优先级判断是：

1. **先修 Fig. 6**，否则通信鲁棒性主线会被审稿人质疑。
2. **再简化 Fig. 11**，保留它作为 force trade-off 主图。
3. **统一所有图内标题和方法名**，去掉内部实验编号。
4. **把 Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 移到补充材料**，主文留下更清晰的证据链。

