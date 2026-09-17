# Figure suitability audit for `manuscript_en_ch4_ch7_balanced_full_2026_05_26.pdf`

审核对象：`manuscript_en_ch4_ch7_balanced_full_2026_05_26.pdf`

审核方式：按 PDF 渲染页逐页检查主文图像，重点检查图面是否清楚、图注与图面是否一致、图像是否支撑正文论断、是否存在内部实验名残留、是否适合留在主文。

## 总体结论

当前图组的整体方向是可用的：Fig. 1、Fig. 2、Fig. 4 能支撑方法框架和 Koopman 预测能力；Fig. 6、Fig. 7、Fig. 11 对通信、故障、hairpin 场景很重要。但是不建议把现有所有图都作为主文强证据直接提交。主要问题有三类：

1. **部分图的证据和图注不完全一致。** 最明显的是 Fig. 6 和 Fig. 11。Fig. 6 的通信质量/丢包曲线几乎是常值，却用于支撑高通信干扰；Fig. 11 的图注提到了 payload resultant force 和力分量，但当前可见图面没有这些力相关面板。
2. **部分图过密。** Fig. 9、Fig. 10、Fig. 11 都是多面板诊断图，适合补充材料或内部审计，不适合作为主文核心图直接阅读。
3. **个别图像保留了内部实验命名或不够像最终论文图。** Fig. 8 标题中的 `E3` 与正文 Experiment 5/11 的命名体系不一致；Fig. 11 标题中的 `stress-style panel` 也像内部审计标题，不像正式论文图题。

建议主文保留精简图组：**Fig. 1、Fig. 2、Fig. 4、重画或改图注后的 Fig. 6、清理后的 Fig. 7、简化后的 Fig. 11**。Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 更适合放到 supplementary material，或用表格/一句话替代。

## 逐图意见

| 图号 | 当前判断 | 主要问题 | 建议 |
|---|---|---|---|
| Fig. 1 | 主文可保留 | 框架图整体清楚，但单栏显示时局部文字偏小。 | 保留。若版面允许，改为跨栏或略放大；确保车辆/网络/Koopman/MPC 模块文字在最终 PDF 中可读。 |
| Fig. 2 | 主文可保留 | 流程完整，但模块多、箭头多，属于高信息密度图。 | 保留为方法主图。建议保持跨栏宽度；删去非必要小字；图注改短，正文再解释细节。 |
| Fig. 3 | 补充材料优先 | 训练损失图只能证明训练收敛，不能直接证明闭环鲁棒性或控制性能。 | 如主文篇幅紧张，移到补充材料。正文只保留一句“training convergence was verified”。 |
| Fig. 4 | 主文应保留 | 预测证据和 IRSP/Koopman 有直接关系，是较强证据。 | 保留。图注可以再压缩，把“为什么这张图重要”放正文，不要让 caption 过长。 |
| Fig. 5 | 补充材料优先 | 与 Table 2 有重复，主文中视觉增益有限。 | 若保留在主文，应明确单位、维度含义、场景名称，并让颜色/线型与 Table 2 的方法名完全一致。否则移至补充材料。 |
| Fig. 6 | **需要重画或改图注** | 图注和正文想表达通信退化/高通信噪声，但上方通信质量、packet loss/dropout 几乎不变；下方保护动作也几乎只有一个短暂 4WS heading spike。当前图面不足以支撑“丢包/链路质量退化下仍鲁棒”的强表述。 | 两个选择：A. 重跑或重画，显示真实的 link-quality drop、packet loss/dropout、delay、constraint tightening/priority weight 的同步变化；B. 若该代表性样本确实只有 delay 起作用，则 caption 改成“delay-dominant representative run”，不要声称 packet-loss evidence。 |
| Fig. 7 | 主文可保留但需清理 | FDI/FTC 时间线有价值，但右上子图的轴和文字略拥挤，`deficit norm`、command、mode/flag 信息叠在一起会降低可读性。 | 保留前建议重排成 3-4 个横向共享时间轴子图；把 fault indicator、FTC mode、control response 分开；统一 fault start 标记。 |
| Fig. 8 | 补充材料或表格替代 | 图形信息量太低：只有 certificate ok 和 positive margin 几个柱。标题有 `E3` 内部编号残留，与正文实验编号不一致。 | 不建议作为主文图。改为表格或补充图；若保留，标题必须改成正式实验名，并展示 negative/positive margin 的对照，否则“certificate closure”说服力不足。 |
| Fig. 9 | 补充材料优先 | 2 m/s 和 5 m/s 两个多面板堆叠图过密，车辆级曲线和图例在主文尺度下难读。 | 主文最多保留一个简化版本：只放 x-y trajectory、team lateral error、team longitudinal error。车辆级 steering/speed/acceleration 放补充材料。 |
| Fig. 10 | 不宜作为正向主文证据 | 10 m/s 和 15 m/s 的 longitudinal error 很大，且 15 m/s 体现出明显速度敏感/失败趋势。若正文用它证明性能优势，会被审稿人抓住。 | 可作为“速度敏感性/局限性诊断”放补充材料或局限性段落。主文不要把它包装成鲁棒性能主证据。 |
| Fig. 11 | **需要修图注并简化** | 这张图很重要，但当前有两个明显问题：一是标题 `Same-initial degraded-baseline stress-style panel` 不像正式论文图；二是图注提到 payload resultant force 和力分量，但页面可见图面没有 force 面板。 | 必须先修正图注或补回 force 面板。若主文保留，建议只放 3 个核心面板：trajectory、team lateral/longitudinal error、force peak/trade-off。其余车辆级输入/速度曲线放补充材料。 |

## 主文图组建议

### 最小主文图组

1. **Fig. 1**：总体框架。
2. **Fig. 2**：控制/估计/重构流程。
3. **Fig. 4**：Koopman prediction evidence。
4. **修订后的 Fig. 6**：通信延迟/链路退化机制证据。
5. **清理后的 Fig. 7 或简化后的 Fig. 11**：二选一作为故障/高曲率综合诊断。

### 更完整主文图组

1. Fig. 1：framework。
2. Fig. 2：method flow。
3. Fig. 4：Koopman prediction。
4. 修订 Fig. 6：communication mechanism。
5. 清理 Fig. 7：FDI/FTC timeline。
6. 简化 Fig. 11：hairpin and force trade-off。

Fig. 3、Fig. 5、Fig. 8、Fig. 9、Fig. 10 建议进入 supplementary material。

## 需要新增或替代的图

1. **总体性能对比汇总图。** 当前主文大量依赖表格，缺少一张面向审稿人的一眼可读图。建议新增 grouped bar/point plot：success rate、lateral RMSE、longitudinal RMSE、max connection utilization、force peak，并带误差线或 paired-run 标记。
2. **通信退化真实时间线图。** 若论文要强调 network-resilient/control under communication degradation，必须有一张图同时显示 delay、packet loss/dropout、link quality、control protection action、tracking error。当前 Fig. 6 还不够。
3. **force trade-off 图。** 如果 payload protection 是贡献点，建议用简化图展示 Method/Method-HC/AKE degraded 的 force peak、tracking error、connection utilization 三者权衡。Fig. 11 的表格信息很好，但图面需要更聚焦。
4. **certificate 解释图或表。** Fig. 8 当前太弱。更好的方式是用表格列出 scenario、certificate ok ratio、minimum margin、是否 full path success，并在正文说明这是 logged practical boundedness evidence，不是 strict global stability proof。

## 统一制图规范

1. 最终版图内字体建议不小于 8 pt；多面板图的坐标轴、legend、caption 三者必须在最终 PDF 缩放后仍可读。
2. 所有图都统一方法名：不要混用 `NR-KDCC`、`\Method`、`NR-KDCC-HC`、`AKE-M degraded` 等不一致写法；图例中出现的名称要和正文表格完全一致。
3. 删除内部审计标题：如 `stress-style panel`、`E3 pressure-mode`、`seed=2026` 若不是论文结论所需，不应放在最终图题里。
4. 所有轴必须带单位：`m`、`s`、`m/s`、`m/s^2`、`rad`、`N`。
5. 多方法线型固定：baseline 用 dashed，proposed 用 solid，高曲率或保护模式用 starred/solid variant；不要每张图重新定义视觉规则。
6. 多面板图要有 `(a)`, `(b)`, `(c)` 标号，并在 caption 中逐项解释。现在部分图只有大标题，审稿人引用时不方便。
7. 图注不要替代正文论证。Caption 应说明“显示什么”，不要塞入过多解释性结论；关键因果解释放正文。
8. 对失败或敏感性图要诚实命名。Fig. 10 这类图如果保留，应命名为 speed-sensitivity 或 limitation diagnostic，不应作为 robust performance evidence。

## 最需要优先改的三处

1. **Fig. 6：重画或改图注。** 当前通信曲线太平，不能强支撑 packet loss/link quality degradation 论断。
2. **Fig. 11：修正图注与可见面板不一致。** 图注中的 force 面板目前在图面上不可见，这是审稿人很容易发现的硬伤。
3. **Fig. 8：移出主文或彻底重做。** 该图信息量不足且有内部编号残留，不适合作为主文证据图。

