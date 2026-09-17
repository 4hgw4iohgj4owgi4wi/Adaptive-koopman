# Layout and fix-check review for `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev2_20260528.pdf`

审核对象：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev2_20260528.pdf`

对应源文件：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev2_20260528.tex`

检查重点：排布是否美观、上一轮指出的问题是否改对、是否还有明显图文/符号/文字不一致。

## 总体判断

这版的内容修改大体是对的，前一轮指出的主要硬伤基本已修：

1. **摘要 force 数字已改对。** 旧的 `15487.33 N -> 8874.04 N` 已改成 `6240.14 N -> 4373.90 N`，与 Table 6/Fig. 7 的 0.10 s moving-mean force peak 口径一致。
2. **`pressure run/scenario` 基本改成了 `communication-stress run/scenario`。** 这比原来的 `pressure` 更准确，也避免和 payload force/pressure 混淆。
3. **Fig. 4 的通信证据现在能支撑正文。** 图中有 delay、packet loss、link quality、constraint tightening、lateral priority 等曲线；caption 也明确说明 mean delay 用 steps，packet loss 用 ratio。
4. **内部图题大多清掉了。** PDF 中没有再看到 `E0`、`E1`、`R42`、`stress-style panel`、`seed=2026` 这类明显调试标题。
5. **`stable_bilinear` 已改成 `IRSP-stabilized bilinear`，`raw6` 已改成 `raw-6D`。** 这两个修改是正确的。
6. **Table 3 和 Table 6 的 force 口径已说明。** Table 3 现在写 raw logged force-cost peak，Table 6 写 0.10 s moving-mean force peak，比上一版清楚。

但是，从版面美观角度看，这版还不是最终理想状态。最明显的问题是 **Fig. 4 单栏图独占第 11 页，右侧和下方留白太大**。

## 必须优先处理的排版问题

### 1. 第 11 页 Fig. 4 单独占页，非常不美观

第 11 页只有一个单栏 Fig. 4 放在左侧，上半页到中下部有图，右半页和下半页大面积空白。这个页面会给审稿人一种“浮动体排版失控”的感觉。

建议二选一：

- **方案 A：把 Fig. 4 改成双栏图 `figure*`。** 将四个子图横向或 2x2 排布，宽度用 `0.82--0.90\textwidth`，放在相关正文附近。这样页面会更均衡。
- **方案 B：保留单栏图，但让正文继续填右栏。** 调整 Fig. 4 的浮动位置，不要让它单独形成 float page。可以尝试把该 figure 放到更早的位置，或改 float 参数，避免它被 LaTeX 单独推到一页。

当前版最需要先修这个。

### 2. 第 10 页表格堆叠太重

第 10 页连续放了 Table 5、Table 6、Table 7、Table 8，视觉上像“表格墙”。虽然没有明显错位，但审稿体验不够好，读者会觉得实验结果压得很密。

建议：

- 如果版面允许，把 Table 8 移到第 13 页讨论附近，或放补充材料。
- Table 5 和 Table 6 都是 single-seed diagnostic，若主文篇幅紧张，可考虑 Table 5 保留，Table 6 和 Fig. 7 绑定；不要让四个表连续堆在一页。
- 如果不想动内容，至少增加一点表间距，使 Table 6/7/8 视觉分组更清楚。

### 3. 第 9 页小节开头和表格关系略别扭

第 9 页顶部是 Table 3 和 Table 4，下面正文从 `15 m/s, the paired protocol...` 这种半句续接开始，随后 `5.5 High-Curvature Hairpin Comparison` 出现在左栏底部，右栏已经开始讨论 Table 6/Fig. 7。技术上可读，但版面逻辑不够顺。

建议：

- 尽量让 `5.5 High-Curvature Hairpin Comparison` 不要从页底开始。
- 可通过调整 Table 4 的浮动位置或在 5.5 前加 `\FloatBarrier`/调整浮动参数来让小节标题和正文靠得更自然。

### 4. Fig. 5 右上子图仍有轴标/图例拥挤

Fig. 5 整体比上一版好，但右上 `fault deficit and FTC command` 子图仍能看到 y 轴标注和曲线说明略挤。不是硬伤，但视觉上不如其他图干净。

建议：

- 右上子图拆成 `fault deficit` 和 `FTC command` 两个小子图，或
- 简化 y 轴 label，减少图例文字。

## 内容复查：改对的地方

| 项目 | 上轮问题 | 本轮状态 | 结论 |
|---|---|---|---|
| 摘要 force 数字 | 旧数值与 Table 6/Fig. 7 不一致 | 已改成 6240.14 N -> 4373.90 N | 已修好 |
| Fig. 4 通信证据 | loss/dropout 不支撑正文 | 新图显示 delay/loss/link quality degradation | 已修好 |
| `pressure` 用词 | 容易与物理压力混淆 | 已改为 communication-stress | 已修好 |
| force 指标口径 | raw peak 和 moving-mean peak 混用 | Table 3/Table 6 已区分 | 基本修好 |
| Fig. 7 caption | 过于委婉 | 已写 `tracking degradation explicit` | 已修好 |
| 内部图题 | E0/E1/stress-style/seed 残留 | PDF 中基本消失 | 已修好 |
| `stable_bilinear` | 像代码变量 | 改为 IRSP-stabilized bilinear | 已修好 |
| `raw6` | 像代码变量 | 改为 raw-6D | 已修好 |

## 仍需复查的小问题

### 1. Supplementary Fig. S1/S2 必须真实存在

正文仍引用：

- Supplementary Fig. S1：训练损失完整曲线。
- Supplementary Fig. S2：10 m/s diagnostic panel。

如果最终投稿包没有 supplementary PDF，这两个引用会成为悬空说明。建议同步生成 supplement，或者改为 `not shown in the main text`。

### 2. 参考文献 DOI 前缺空格，影响观感

第 14-15 页参考文献里多处出现：

- `Systemsdoi`
- `Transactionsdoi`
- `Technologydoi`
- `Sustainabilitydoi`
- `Sensorsdoi`
- `Informaticsdoi`

这不是正文技术问题，但版面很丑，属于投稿前必须清理的格式问题。需要检查 `.bib` 条目的 journal/booktitle 字段末尾是否缺标点或空格，或者 `.bst` 输出是否需要微调。

### 3. 编译日志仍有 overfull/underfull

没有看到 undefined reference/citation 这类硬错误，但日志仍有：

- Overfull hbox: 32.47 pt、170.47 pt、241.0 pt。
- Overfull vbox: 40.90 pt、14.91 pt 等。

这和第 11 页浮动图、参考文献长 DOI、少数长句/公式有关。最终提交前建议再做一次 layout pass。

### 4. Acknowledgments 仍是占位性质

PDF 中写的是：

`Funding and author-contribution statements will be finalized in the submission metadata.`

如果这是匿名审稿阶段，可以接受；如果是最终投稿文件，最好按期刊要求写真实 funding 或删到 submission system 里。

## 图文匹配度复查

| 图号 | 当前评价 | 说明 |
|---|---|---|
| Fig. 3 | 匹配，排布可以 | 图内名称已正式化，和正文 IRSP 表述一致。 |
| Fig. 4 | 内容匹配，但排布很差 | 图本身能支撑正文，但单栏独占一页最不美观。 |
| Fig. 5 | 内容匹配，轻微拥挤 | FDI/FTC 机制能看懂，右上轴标仍略挤。 |
| Fig. 6 | 匹配，排布可接受 | 2/5 m/s 诊断图仍密，但内部调试标题已清理，主文可用。 |
| Fig. 7 | 匹配，排布可接受 | force 面板和 Table 6 匹配；caption 对 tracking degradation 的说明比上一版安全。 |

## 最终建议

这版“改对了”，但“排布还没完全美观”。如果只从内容一致性看，可以进入终稿前最后润色；如果从审稿观感看，建议至少再修三件事：

1. 解决第 11 页 Fig. 4 单栏独占页的大留白。
2. 清理参考文献中的 `...doi` 粘连格式。
3. 调整第 9-10 页表格/小节排布，减少表格墙和小节标题贴页底的问题。

完成这三项后，这版实验部分的图文一致性和版面观感会比较稳。

