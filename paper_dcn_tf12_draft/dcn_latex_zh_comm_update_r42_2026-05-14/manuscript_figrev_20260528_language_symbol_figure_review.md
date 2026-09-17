# Review of `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev_20260528.pdf`

审核对象：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev_20260528.pdf`

对应源文件：`manuscript_en_ch4_ch7_balanced_full_2026_05_26.tex`，修改时间为 2026-05-28 12:01:53。

检查重点：前后语言用词、符号/指标一致性、图片内容与正文匹配度。  
检查方式：抽取 PDF 全文、渲染第 3-13 页图表页、检查 LaTeX 编译日志和源文件关键段落。

## 总体评价

这版比 `forcefig` 版明显更接近可投稿状态。主要改进有：

1. 主文图数量压缩，PDF 从 16 页降到 14 页，证据链更集中。
2. 原来的训练损失图、Koopman ablation 图、mode-wise certificate 柱图、10/15 m/s 大型诊断图基本移出主文或转入补充材料，主文不再显得堆图。
3. Fig. 4 重新画成单栏通信机制图，已经能显示 delay、packet loss、link quality degradation，不再是上一版“loss/dropout 为 0 却声称通信退化”的问题。
4. Fig. 7 的 force 面板和 Table 6 的 0.10 s moving-mean force peak 已基本对应，图文匹配度比上一版好。
5. 正文多处已经主动收窄结论，例如“不声称 force 全面优越”“15 m/s 是 failure-mode audit”“stability 不是 global asymptotic stability”，这对审稿风险控制是正确的。

但这版仍有几个必须修的问题，其中最重要的是 **摘要里的 force 数字仍是旧版本**，与新版 Table 6/Fig. 7 不一致。

## 必须修改的问题

### 1. 摘要中的 hairpin force 数字还是旧版

源文件第 151 行和 PDF 摘要仍写：

`full NR-KDCC lowers peak resultant force from 15487.33 N to 8874.04 N relative to NR-KDCC-HC`

但新版 Table 6 和 Fig. 7 已改成 0.10 s moving-mean force：

- NR-KDCC-HC: 6240.14 N
- NR-KDCC: 4373.90 N

这属于高优先级硬伤。建议改成：

`in the revised 5 m/s hairpin diagnostic, full NR-KDCC lowers the 0.10 s moving-mean resultant-force peak from 6240.14 N to 4373.90 N relative to NR-KDCC-HC.`

如果摘要还想保留旧的 raw peak 数字，就必须在 Table 6 同时报告 raw peak 和 moving-mean peak，否则审稿人会认为摘要和实验表不一致。

### 2. 图内仍有内部调试标题

PDF 图内仍可见：

- Fig. 3 顶部：`E1 Koopman prediction and input-aware stability projection`
- Fig. 5 顶部：`E0 mixed fault/noise FDI/FTC and safety-monitor timeline`
- Fig. 6 两个子图顶部：`Same-initial degraded-baseline stress-style panel`
- Fig. 6 子图标题中：`seed=2026`

这些不是技术错误，但很像内部调试图，不像最终投稿图。建议：

- 删除 `E1`、`E0`。
- 将 `Same-initial degraded-baseline stress-style panel` 改成正式标题，例如 `Same-initial sine-path diagnostic`。
- `seed=2026` 不放在图内标题，放到 caption 或 supplementary setting。

### 3. Fig. 7 的摘要/正文用语要更谨慎

Table 6 显示完整 NR-KDCC 的结果是：

- Lat. RMSE: 0.287473，略低于 AKE-M-degraded 的 0.298869。
- Long. RMSE: 12.121556，高于 AKE-M-degraded 和 NR-KDCC-HC。
- Max lat. error: 1.002130，高于 AKE-M-degraded 和 NR-KDCC-HC。
- 0.10 s force peak: 4373.90，低于 AKE-M-degraded 和 NR-KDCC-HC。

正文第 965 行已经写得比较诚实，但 Fig. 7 caption 中的 `while keeping tracking errors interpretable` 仍偏委婉。建议改成：

`... reduces the force level while making the associated tracking degradation explicit.`

这样更符合表格事实，也更不容易被审稿人认为在掩盖 tracking cost。

### 4. `pressure run / pressure scenario` 这个词容易歧义

全文多处用 `pressure run`、`pressure scenario`。在本论文里还有 payload force、force peak、connection force，`pressure` 容易让读者误解为物理压力，而不是 stress-test 场景。

建议统一改为：

- `stress run`
- `communication-stress run`
- `high-communication-stress scenario`
- `hairpin stress scenario`

例如 Fig. 4 caption 中的 `5 m/s hairpin pressure run` 建议改成 `5 m/s hairpin communication-stress run`。

### 5. Fig. 4 的 y 轴混用了 delay steps 和 packet-loss ratio

Fig. 4 顶部面板 y 轴写 `steps / ratio`，同时画 mean delay 和 packet loss。可以接受，但作为最终图略显不精确。更稳妥的做法：

- caption 中写清楚 `mean delay is reported in steps, packet loss is reported as a ratio`。
- 图内 legend 保持 `mean delay [steps]` 和 `packet-loss ratio`。

正文第 810 行的 `maximum mean delay is 2.83 steps` 也有点别扭。建议改成：

`the peak of the edge-averaged delay trace is 2.83 steps`

或：

`the maximum averaged communication delay is 2.83 steps`

## 建议修改的问题

### 1. `stable_bilinear` 不适合直接出现在最终图和 caption

Fig. 3 图例和 caption 里有 `stable_bilinear`。技术上可理解，但英文论文里下划线像代码变量。

建议改成：

- `stabilized bilinear`
- `bilinear+IRSP`
- `IRSP-stabilized bilinear`

同时 caption 中不要写 `The label stable_bilinear denotes...`，直接用正式名称。

### 2. `K0 raw6 linear Koopman` 表述不够自然

Table 2 和正文中 `K0 raw6 linear Koopman` 建议改成：

- `K0 raw-state linear Koopman`
- `K0 raw-6D linear Koopman`
- `K0 six-state linear Koopman`

目前 `raw6` 像代码变量。

### 3. `Supplementary Fig. S1/S2` 要确认补充材料真实存在

正文现在引用：

- Supplementary Fig. S1: training/validation loss full trace。
- Supplementary Fig. S2: 10 m/s diagnostic panel。

如果最终投稿包没有 supplementary file，这两个引用会变成悬空承诺。建议同步生成 supplement PDF 或暂时改成：

`not shown in the main text`

### 4. Fig. 5 仍有坐标轴拥挤问题

Fig. 5 的右上子图 `FTC reallocation signals` 仍有 y 轴/label 视觉重叠，`deficit norm` 和 command-related axis 读起来不清楚。建议拆成两个子图：

- fault deficit
- delta/ax redistribution command

如果不拆，至少把右轴 label 简化，并减少 legend 内容。

### 5. Fig. 6 仍偏密，但比上一版好

Fig. 6 只保留 2 m/s 和 5 m/s，比上一版好很多。不过每个子图仍有多个小面板和长标题。作为主文图可以接受，但建议删除顶部内部标题和 `seed=2026`，否则会显得像实验记录截图。

## 符号和指标一致性检查

### 基本一致的部分

1. `NR-KDCC`、`NR-KDCC-base`、`NR-KDCC-HC`、`AKE-M`、`AKE-M-degraded` 的主文定义基本清楚。
2. `q_k^{net}`、`q_{ij,k}`、`\ell_{ij,k}`、`\tau`、`\beta`、`\epsilon` 的通信模型定义和后文通信机制图基本对应。
3. `\hat F_{L,k}^{xy}` 被定义为 planar payload resultant-force proxy，正文也反复说明它是 audit/shaping term，不是真实传感力，这个表述是安全的。
4. Table 6 已把 force 指标明确为 `0.10 s force peak [N]`，和 Fig. 7 的 `payload resultant force (0.10 s mean)` 对齐。
5. Table 8 的 certificate 结论已经收窄为 logged practical boundedness，不再过度声称 strict global stability。

### 仍需注意的部分

1. Table 3 的列名仍是 `Force peak`，Table 6 是 `0.10 s force peak`。二者可能不是同一计算口径。建议在 Table 3 注释中补一句 `Table 3 uses the raw logged force-cost peak, whereas Table 6 uses the 0.10 s moving-mean peak for the hairpin diagnostic`，或统一两处口径。
2. Fig. 4 的 `packet loss` 是 ratio，而模型中 `\ell_{ij,k}` 是 binary indicator。建议图例写 `packet-loss ratio`，避免把单边 indicator 和聚合统计混为一谈。
3. `force RMS` 在第 965 行出现，但 Table 6 没列 RMS。可以保留，但审稿人可能会问 RMS 数据来源。建议要么把 RMS 加入 Table 6，要么改成 `the logged force RMS, not shown in the table, decreases...`。

## 图片和正文匹配度

| 图号 | 匹配度 | 意见 |
|---|---|---|
| Fig. 1 | 好 | 框架图和方法命名对应，作为主文图合适。 |
| Fig. 2 | 好 | 在线信号流和 Section 3 对应。图注略长，但可接受。 |
| Fig. 3 | 好 | Koopman prediction/IRSP 证据与正文匹配。需删除图内 `E1` 和 `stable_bilinear` 下划线风格。 |
| Fig. 4 | 明显改善 | 通信图现在能支撑 delay/loss/link-quality degradation。需精确标注 delay steps 与 packet-loss ratio。 |
| Fig. 5 | 中等 | 能支撑 FDI/FTC 机制，但右上子图拥挤。图内 `E0` 需删除。 |
| Fig. 6 | 可接受 | 主文只留 2/5 m/s 是正确选择。需删除 `stress-style panel` 和 `seed=2026`。 |
| Fig. 7 | 可接受但要谨慎 | force 面板与 Table 6 匹配。问题是 NR-KDCC tracking cost 明显存在，caption 和正文不能弱化这个代价。 |

## 编译和版面

编译日志没有发现 undefined citation/reference 这类硬错误，但仍有明显版面警告：

- Overfull hbox: 32.47 pt、170.47 pt、241.0 pt。
- Overfull vbox: 40.90 pt 以及若干小幅 overfull vbox。
- 页眉仍是 `Author Name`。
- 源文件中仍有 `\todozh{Funding information, grant numbers, and author contribution statements will be added.}`，虽然当前 PDF 没明显显示红色 todo，但最终源文件不应保留这个占位命令。

建议最终提交前做一次 layout-only 清理：页眉作者、Acknowledgments、overfull boxes、supplementary references。

## 推荐优先级

1. **最高优先级：改摘要 force 数字。** 这是当前最明显的前后不一致。
2. **第二优先级：删除图内内部标题。** `E1`、`E0`、`stress-style panel`、`seed=2026` 都应清掉。
3. **第三优先级：统一 force 指标口径。** Table 3 的 raw force peak、Table 6 的 0.10 s moving-mean force peak、正文的 force RMS 要说清楚。
4. **第四优先级：把 pressure scenario 改成 stress scenario。**
5. **第五优先级：修 Fig. 5 坐标轴拥挤和 compile overfull warnings。**

## 结论

这版可以作为接近终稿的实验章节版本。与上一版相比，主文图组更克制，通信机制图已经补上真实 link degradation，hairpin force 图也和 Table 6 基本对齐。现在最大问题不是实验逻辑，而是最后一轮一致性清洗：摘要旧数字、内部图题、force 指标口径、少量英文措辞和版面警告。

