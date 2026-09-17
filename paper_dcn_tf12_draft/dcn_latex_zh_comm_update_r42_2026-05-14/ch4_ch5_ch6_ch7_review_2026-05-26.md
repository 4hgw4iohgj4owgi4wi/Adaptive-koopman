# 第四章复审、第六七章结构与第五章措辞修改建议

对象文件：`manuscript_en_ch4_reviewfix_2026_05_26.tex`

审阅范围：

- 第 4 章：`Stability Certificate and Practical Boundedness`，第 542--689 行。
- 第 5 章：`实验结果与分析`，第 692--1002 行。
- 第 6 章：`讨论`，第 1004--1008 行。
- 第 7 章：`结论`，第 1011--1013 行。

## 总体判断

第四章这次改得比较成功。上一轮指出的核心漏洞已经大部分修正：不再伪装成 terminal-set MPC 证明，而是改成 `certificate-verified practical ISS/UUB`；`d_k`、`z_k^\star`、mode 映射、两通道执行器效率、失败步有界增长、平均收缩条件和 `\bar V_{\mu,k}` 都补上了。现在第四章已经可以作为“证书驱动的实践有界性证明”使用。

第五章的问题主要不是实验结果，而是措辞仍像内部审稿记录。它反复使用“客观结果是”“造成上述结果的原因是”，并出现“最新”“调参”“回填”“主证据”“地板基线”等不适合投稿正文的表达。建议下一步重点清洗第 5 章语言，而不是再加实验。

第六章和第七章建议合并。当前第 6 章只有两段，第 7 章只有一段，且内容高度重叠。如果不扩展出真正的 limitation/future work，单独保留 Discussion 会显得薄。

## 第四章改得怎么样

### 已经修好的关键点

1. 第 544 行明确说证明目标不是 global asymptotic stability，而是 compact operating region 下的 practical stability/UUB。这比上一版安全。

2. 第 544 行明确说明 proof follows the implemented online certificate rather than a classical terminal-set MPC argument，解决了上一版 terminal controller 和 terminal invariant set 不存在的问题。

3. 第 551 行定义了 `d_k`，第 579--580 行定义了 `z_k^\star=\Phi_\theta(\chi_k^{ref})`，解决了上一版符号突现。

4. 第 561--570 行把 C0--C3、FTC flag、payload switch、FTC bounded degradation 明确写进假设，和第 3 章衔接更好。

5. 第 584--598 行定义了 `V_{\mu,k}` 和 `\bar V_{\mu,k}`，并给出 mode certificates 的 mutual comparability。这比上一版直接跳到 `\bar V_{\mu,k}` 稳很多。

6. 第 616--625 行把 IRSP 改成严格采样收缩，并加入 residual small-gain 条件，补上了状态相关残差吸收问题。

7. 第 635--645 行加入 failing-step bounded growth 和 average contraction condition，修掉了上一版“有限失败密度不足以推出 UUB”的漏洞。

8. 第 662--688 行证明已经从证书裕度出发，不再强行从 `J_k^\star` 推 `\bar V_k`。这个方向是正确的。

### 第四章仍建议微调的点

#### 1. `\alpha` 在 small-gain 条件中未显式定义

位置：第 622--625 行。

当前写：

```latex
\alpha_c:=\alpha-c_w\bar w_\chi^2L_\chi^2>0 .
```

但 `\alpha` 在前文没有正式说明是什么。建议改成：

> Let `\alpha>0` denote the nominal certificate decrease rate before absorbing the state-dependent residual term.

或者直接写：

```latex
\alpha_c:=\alpha_{\mathrm{cert}}-c_w\bar w_\chi^2L_\chi^2>0 .
```

#### 2. `\rho_P,c_P` 没有显式进入平均收缩条件

位置：第 597--598、640--645、674--688 行。

你已经写了 mode certificates mutually comparable，这是对的。但 average contraction condition 只写了 `(1-\bar\nu)\alpha_V>\bar\nu\rho_f`，没有体现 mode switching comparability 带来的跳增。严格一点，应说明 `\rho_P,c_P` 已经 absorbed into `\rho_f,c_f`，或把它们写入平均条件。

建议加一句：

> The constants `\rho_f` and `c_f` include the worst-case mode-comparison factors `\rho_P` and `c_P`.

#### 3. sampled IRSP 与 continuous input envelope 的证明边界要说清

位置：第 616--622 行。

第 616 行用的是 sampled contraction bound。只有 when norm certificate is enabled 时，才覆盖连续输入 envelope。这个写法可以，但结论要明确：

- 默认证明覆盖 sampled control envelope。
- 若要覆盖 continuous input box，需要启用 norm certificate。

建议在 theorem 后补一句：

> Without the norm certificate, the claim is limited to the sampled input envelope used by the controller audit.

#### 4. 第四章已经英文，但第五章以后还是中文

现在第 1--4 章基本进入英文稿状态，第 5--7 章仍是中文。若目标是完整英文稿，后面必须统一翻译；如果当前只是分章修稿，第四章本身已经过关。

## 第六章和第七章是否合并

建议合并。

原因：

1. 第 6 章 `讨论` 只有两段，第 7 章 `结论` 只有一段，结构上太短。

2. 第 6 章第 1006 行已经总结了主结果、消融、力峰值权衡和证据链；第 7 章第 1013 行又重复方法、主对比、消融、速度、回头弯和结论，信息重叠明显。

3. 当前 Discussion 没有真正展开 limitations、applicability、failure cases、future work。如果不扩展这些内容，单独 Discussion 的必要性不足。

推荐方案：

### 方案 A：合并为 `Discussion and Conclusion`

适合当前稿件。结构建议三段：

1. 概括方法与主要证据。
2. 讨论边界和权衡：force peak 未相对 AKE 同步降低、高速纵向误差、single-seed 与 paired 统计层级不同、证书是实践有界而非全局稳定。
3. 总结贡献和下一步：多 seed 重跑、真实机器人/更复杂通信扰动、纵向相位控制和载荷力代理验证。

### 方案 B：只保留 `Conclusion`

如果版面紧，直接删掉 Discussion，把关键限制写进 Conclusion 中间一段。这样最简洁。

### 方案 C：保留独立 Discussion，但必须扩展

如果坚持保留第 6 章，建议至少扩成四个小点：

- Why communication-aware MPC is the main source of improvement.
- Payload force trade-off and why it is not claimed as a primary improvement over AKE.
- Speed sensitivity and longitudinal-phase limitation.
- Certificate interpretation: practical boundedness under logged certificate conditions, not global stability.

当前版本不建议保留独立 Discussion。

## 第五章整体措辞问题

### 1. 章节语言仍是中文

位置：第 692--1002 行。

如果文件名 `manuscript_en...` 对应英文稿，第 5 章需要整体翻译为英文。现在第 4 章已经英文，第 5 章突然回到中文，读者会认为稿件未完成。

### 2. “客观结果/造成上述结果”句式重复

位置：第 710、712、721、723、757、759、768、770、779、781、790、792、829、831、860、862、909、911、942、944、974、976、998、1000 行。

这种写法适合内部审稿记录，但论文正文读起来机械。建议改成：

- `Figure/Table X shows that ...`
- `These results indicate that ...`
- `This behavior is consistent with ...`
- `The main observation is ...`
- `A plausible explanation is ...`

尤其注意不要把相关性写成强因果。很多段落的“造成上述结果的原因是”应改成“这种现象与...一致”。

### 3. 内部流程词需要删除

位置：第 697、759、860、911、915、977 行。

不建议在投稿正文中出现：

- `最新`
- `调参`
- `回填`
- `主证据`
- `原实验`
- `内部审稿材料`
- `当前核心`

这些词暴露了稿件迭代过程。建议改为：

- `updated` -> 如果不是方法贡献，直接删。
- `调参结果` -> `single-seed diagnostic results`
- `回填` -> `pooled with` 或 `merged into`
- `主证据` -> `mechanistic diagnostic evidence`
- `内部审稿材料` -> 删掉，或写 `supplementary visualization`。

### 4. “证明”用得过强

位置：第 706、781 行。

图不能“证明”机制，只能 support / verify / indicate。建议：

- `该图用于证明网络训练过程...` -> `该图用于检查网络训练过程是否收敛并排除明显发散。`
- `该图证明 FDI/FTC 与证书监测已经接入闭环` -> `该图表明 FDI/FTC 与证书监测已接入闭环。`

### 5. single-seed 结果要降级为机制诊断

位置：第 697、727、860、866、909、915、942 行。

现在写得很诚实，但仍有“single-seed 参数重新生成”“同初始条件核验表作为主证据”等表述。建议统一说：

> Same-initial-condition single-seed diagnostics are used to inspect process-level behavior and module mechanisms, whereas paired multi-seed tables are used for statistical comparisons.

这样既不隐藏统计层级，也不让读者觉得你在用 single-seed 证明总体优势。

### 6. force peak trade-off 处理是对的，但措辞可更稳

位置：第 820、825、829、831、942、944、1006、1013 行。

你已经承认 `\Method{}` 的力峰值高于 AKE，这是正确做法。建议继续保持，但把“受力代价边界”“安全--受力补充模式”写得更清楚：

> Force-related quantities are treated as audit metrics and trade-off indicators rather than as primary improvement claims against AKE.

不要写成“载荷受力保护能力全面提升”。当前稿件基本没犯这个错误，后续翻译时要守住。

## 第五章逐处建议

### 第 696 行：实验总览太长

问题：一句话列完 11 个实验、所有缩写、所有统计层级，读者负担很大。

建议拆成三段：

1. 定义 ZOH、PPC、ablation suffix。
2. 列出实验 1--11。
3. 说明 paired statistics 与 single-seed diagnostics 的区别。

推荐改写方向：

> This section reports eleven experiments and diagnostics. Experiments 6, 10, and 11 use paired multi-seed statistics, whereas Experiments 2--5, 8, and 9 are diagnostic tests used to inspect mechanisms and trajectories. The latter are not pooled with the paired statistics because their seed count and controller configuration differ.

### 第 697 行：数据源说明过于内部化

问题词：`最新`、`参数重新生成`、`调参结果`、`回填`。

建议改成：

> The paired statistical tables and the same-initial-condition diagnostics are reported separately because they differ in seed count and controller configuration. The single-seed diagnostics are used only to inspect trajectory-level behavior and are not merged into the paired statistics.

不要写“若后续要求...需要重新运行”，这像项目备注。可以放到 limitations。

### 第 699 行：`地板基线`不自然

建议：

> \ZOHcons{} is a low-order ZOH consistency baseline used to expose the degradation that occurs without learned prediction or network-aware protection.

中文则写：

> \ZOHcons{} 是低阶 ZOH 一致性基线，用于显示缺少学习预测和网络感知保护时的退化程度。

### 第 710--712 行：训练损失描述

当前可以，但“快速下降”“稳定平台”最好配合具体 epoch 和无发散结论，不要说“证明”。

建议：

> 图 \ref{fig:e1_koopman_training_loss} 显示三类损失在约 60 个 epoch 后进入平台区，且最后 10 个 epoch 的训练/验证均值处于同一量级。这说明训练过程没有出现明显发散或持续过拟合迹象。

### 第 721--723 行：Koopman 预测证据表述较稳，保留但压缩

这一段整体较好，因为已经承认 H=12 时置信区间重叠，且说明 IRSP 不是提高精度。建议保留核心，只压缩数字堆叠。

建议：

> The main point is not that bilinear Koopman uniformly minimizes rollout error, but that it provides comparable short-horizon prediction while IRSP reduces the sampled effective spectral radius below one.

### 第 757--759 行：K1/K2 均值低于 K3，要避免把 K3 写成全面最优

当前已经承认 K1/K2 的均值更低，这是好的。建议进一步把结论收成：

> K3 should be interpreted as the most conservative and certifiable predictor, not as the predictor with the lowest mean RMSE in every scenario.

中文：

> K3 的优势不应表述为所有 RMSE 均值最小，而应表述为在保持可比预测性能的同时提供输入相关放大风险边界。

### 第 768--770 行：`最新通信逻辑`应删

建议把：

> 最新通信逻辑把扰动从...

改成：

> 本文通信模型把扰动从...

### 第 779--781 行：`reconfigured FTC MPC` 与第 4 章 mode 体系不一致

第 4 章已经明确 FTC 是 execution-layer flag，不是独立 optimizer。这里不应写“全局控制模式进入 reconfigured FTC MPC”。

建议改成：

> controller-side fault flags and fault gaps increase after activation; the FTC reallocation flag then becomes active, producing nonzero steering/acceleration redistribution and changes in the vehicle-level control decomposition.

中文：

> 故障触发后，控制器侧故障标志和故障缺口同步上升；随后 FTC 重分配标志激活，并出现非零转角/加速度重分配以及车辆级控制分解变化。

### 第 790--792 行：证书表述要和第四章保持一致

建议把：

> 分模式证书与 ISS/UUB 保护逻辑一致

改成：

> 分模式统计与第 4 章的 certificate-verified practical ISS/UUB 条件一致

这样能避免读者理解成“实验统计证明了稳定性”。

### 第 829--831 行：主对比表述是安全的，但可更精确

当前说力峰值高于 AKE，这是好的。建议补一层边界：

> Therefore, the main comparison supports tracking and connection-utilization improvements, while force-related quantities are reported as trade-off audits.

这和第 6 章讨论保持一致。

### 第 860--862 行：速度敏感性要避免“修正后完成整条路段”冲突

第 860 行先说 paired 15 m/s 成功率为 0，又说 single-seed 修正后可检查是否完整跑完。这个逻辑可以，但要强调两者统计层级不同。

建议：

> The paired 15 m/s result remains a failure case under the original multi-seed protocol. The same-initial-condition diagnostic is reported separately to inspect whether the updated low-level speed clipping and progress supervision can remove this failure mode in a representative run.

### 第 909--911 行：15 m/s single-seed 改善很小，不要写得太正向

15 m/s 横向 RMSE 从 0.158565 到 0.157407，改善很小；逐点胜率 60.70%，仍有 gap。建议写成：

> At 15 m/s, the improvement is marginal and should be read as a failure-mode diagnostic rather than a robust performance gain.

中文：

> 15 m/s 下改善幅度很小，该结果更适合作为失败模式诊断，而不是作为稳健性能提升证据。

### 第 915 行：`主证据`应改

建议把：

> 本节保留同初始条件三阶段核验表作为主证据

改为：

> 本节保留同初始条件三阶段核验表作为机制诊断证据

因为这是 single-seed，不宜叫主证据。

### 第 917 行：`后续同初始条件核验`的“后续”不合适

这是正文当前位置，不是项目流程。建议改成：

> 因此，同初始条件核验同时比较 \AKEdeg{}、\MethodHC{} 和 \Method{}。

### 第 942--944 行：回头弯结果表述较好，但要强调 trade-off

当前写法已经承认横向误差回升。建议保留，并把结论收成：

> The full method trades part of the lateral tracking gain for lower connection utilization and lower force peak.

不要说 full method 在所有指标上更好。

### 第 974--977 行：消融结论可保留，但“内部审稿材料”删除

建议把第 977 行改成：

> Because the table already reports success, lateral/longitudinal error, connection utilization, and certificate statistics, additional bar plots are omitted from the main text to avoid redundant evidence.

### 第 998--1000 行：证书统计措辞要更审慎

当前说明负裕度原因是合理的。建议把“表现较好”改成更客观的：

> high-communication-noise and mixed fault/noise show positive aggregate margins, whereas nominal clean and single fault contain negative worst-case margins.

这样避免主观判断。

## 可直接替换的第 5 章开头写法

```latex
\section{Experimental Results and Analysis}

This section reports eleven experiments and diagnostics that correspond to the method modules in Sections 3 and 4. \ZOHcons{} denotes a low-order ZOH consistency baseline used to expose the degradation caused by removing learned prediction and network-aware protection. The ablation suffixes noComm, noDelay, noIRSP, and noPPC denote removal of communication-quality awareness, delay compensation, input-aware robust spectral projection, and the PPC guard, respectively.

Experiments 6, 10, and 11 use paired multi-seed statistics. Experiments 2--5, 8, and 9 are mechanism-oriented diagnostics or same-initial-condition trajectory checks. These diagnostic results are reported separately from the paired statistics because their seed count and controller configuration differ; they are used to inspect process-level behavior rather than to replace the multi-seed comparison.
```

## 第六七章合并后的建议写法

建议合并为：

```latex
\section{Discussion and Conclusion}
```

内容可按以下三段组织：

1. 方法和主要证据：
   - \Method{} integrates bilinear Koopman prediction, link-quality-aware consensus MPC, connection constraints, 4WS local-path publication, FDI/FTC, and certificate-based fallback.
   - Paired results support improvements in lateral tracking and connection utilization relative to AKE-style baselines under mixed fault/noise and high communication noise.

2. 边界和 trade-off：
   - Force peak is not uniformly lower than AKE; it is treated as an audit/trade-off metric.
   - High-speed cases expose longitudinal phase error.
   - Single-seed diagnostics are mechanism checks, not replacements for paired statistics.
   - Stability is certificate-verified practical boundedness, not global asymptotic stability.

3. 结论和后续：
   - The most supported claim is network-aware cooperative transport with better tracking/connection control under degradation.
   - Future work: rerun updated controller with multi-seed statistics, improve longitudinal phase control, validate force proxy with richer payload/load measurements.

## 最终建议优先级

1. 第四章只做小修：定义 `\alpha`，说明 `\rho_P,c_P` 是否并入 failure constants，澄清 sampled vs continuous IRSP 证明范围。

2. 第五章先统一语言：如果目标是英文稿，整体翻译；如果仍先保留中文，至少删掉内部流程词和强因果句。

3. 第六、七章合并。当前版本不值得分成两个 section。

4. 所有 single-seed 结果统一称为 mechanism-oriented diagnostics，不要称为主证据或统计证明。

5. 力峰值相关结论继续保持审慎：tracking/connection 是主改进，force 是 trade-off audit。
