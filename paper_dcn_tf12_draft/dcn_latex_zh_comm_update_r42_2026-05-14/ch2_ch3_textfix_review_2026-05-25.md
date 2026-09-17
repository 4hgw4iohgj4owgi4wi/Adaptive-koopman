# `manuscript_en_ch2_ch3_textfix_2026_05_25` 第二、三章复审意见

对象文件：`manuscript_en_ch2_ch3_textfix_2026_05_25.tex`

审阅范围：第 2 章和第 3 章，约第 182--537 行。

审阅重点：本轮主要看文字表述、术语连续性、是否还有突然出现的名称，以及新版相对上一版是否真正修掉了第 2、3 章的问题。

## 总体评价

这版比上一版明显好。第 2、3 章已经整体改成英文，章节标题、表题、图题和正文都完成了英文化；上一轮指出的“Koopman residual compensation 过早出现”“team center/load center 混用”“risk-triggered payload protection 与曲率触发不一致”“3.6/3.7 硬编码章节号”“plant/veto/trim 等词突兀”等问题，大部分已经处理。

从审稿人角度看，现在第 2、3 章已经从“不能直接作为英文稿”提升到“基本可读，但仍需一次术语和方法边界精修”。当前不再是大面积翻译问题，而是几个关键术语还不够正式、若干方法句子带有实验结果口吻、PPC/fallback/role scheduling 的定义还不够完整。

## 已经修得比较好的地方

1. 第 2、3 章没有中文正文残留。第 182--537 行内未检出 CJK 字符。

2. 第 230 行已把上一版的“Koopman 残差补偿提前出现”改成过渡句：第 2 章只说明第 3 章会引入 Koopman predictor and residual bound。这是正确改法。

3. 第 249 行已经明确 payload center 是 representative team center，解决了“团队中心/载荷中心”突然切换的问题。

4. 第 266 行已经把 force proxy 的性质说清楚：不是 direct force-sensor measurement，也不是 globally accurate force estimate。这能降低审稿人对力传感器和真实力估计的质疑。

5. 第 279 行已经给 `\Pi_x` 和 lifted predictor 做了“Section 3 interface”的过渡，不再像上一版那样突然出现 Koopman/运动学预测器。

6. 第 299--303 行方法总览比上一版更顺，实验标签没有直接硬塞进方法链条，`risk-triggered payload protection` 也改成了 `curvature-window payload-protection switch`。

7. 第 371 行已把 5 m/s 回头弯的具体窗口参数移出方法定义，只说数值在实验设置中报告，这一点非常重要。

8. 第 512 行已经去掉硬编码的“3.6/3.7”，改成 previous subsection，结构更稳。

## 仍需修改的主要问题

### P1. `degraded fallback` 仍是名称，但没有正式定义触发阈值和动作集合

位置：第 299、315、482、527 行。

现在 `degraded fallback` 已经统一成英文术语，但仍然像一个实现口令。第 482 行只说 link quality falls below the threshold，第 527 行说 severe-degradation threshold，但没有给出阈值符号，也没有说明 fallback 到底包含哪些动作：降低邻居权重、收缩输入边界、切换 C3、收缩参考推进、还是保持上一控制量。

建议在第 482 行附近补一个简短正式定义：

> The degraded fallback is the C3 execution mode triggered when $q_k^{\mathrm{net}}<q_{\mathrm{df}}$ or the actuator-efficiency estimate falls below $\eta_{\mathrm{df}}$. In this mode, unreliable-neighbor weights are reduced, connection-error and input constraints are prioritized, and the reference progress may be contracted to keep the feasible input set nonempty.

这样第 299、315、527 行再提 degraded fallback 就不会显得没定义。

### P1. PPC 仍是突然出现的保护项

位置：第 490 行。

第 490 行写到 prescribed performance control (PPC) envelope `\rho_y` is tightened，但前文没有定义 PPC envelope 的形式，也没有说明 `\rho_y` 是随时间变化、随路径进度变化，还是固定边界。后续实验中还有 PPC guard，因此这个术语不能只用一句话带过。

建议至少增加一句：

> The PPC guard monitors whether $|e_{y,i}|$ approaches a prescribed envelope $\rho_y(k)$ and triggers additional tightening when the normalized error approaches the envelope boundary.

如果有公式，最好给出归一化误差，例如 `|e_{y,i}|/\rho_y(k)`。否则审稿人会问 PPC guard 到底是控制律、约束、还是启发式安全开关。

### P1. 第 536 行在方法章提前宣称实验结果

位置：第 536 行。

原文：

> The hairpin results later show that this module improves lateral RMS error, longitudinal RMS error, and certificate pass ratio ...

方法章不应提前写“results later show”，这属于实验结果描述。审稿人会觉得方法和结果混在一起。这里应只说明 role scheduler 的作用边界，不要先宣称改善。

建议改为：

> The effect of this role scheduler is evaluated in the later hairpin study using lateral RMS error, longitudinal RMS error, certificate pass ratio, connection utilization, and force-cost metrics.

这样方法章只说明验证方式，不抢实验结论。

### P1. `role correction`、`role scheduling`、`role scheduler` 三个名称还需要统一

位置：第 315、303、514、536 行。

第 315 行图题用 `role correction`，第 303/514 行用 `role scheduling`，第 536 行用 `role scheduler`。这三个词接近但不完全一样。建议统一主术语为 `role scheduling`，图题中也写 `role-scheduling correction` 或直接 `role scheduling`。

推荐统一：

- module name: `role scheduling`
- component: `role scheduler`
- correction term: `bounded role-scheduling trim`

第 315 行建议把 `role correction` 改为 `role-scheduling correction`。

### P1. `safety-veto signals` 仍然偏口语化

位置：第 308 行。

英文稿里 `veto` 可以用，但在方法图题中仍显得偏工程口语。若图中标签不是必须叫 veto，建议改成更论文式的：

- `safety-interlock signals`
- `safety override signals`
- `certificate-based rejection signals`

如果图中已经写了 veto，正文第一次可写 `safety-interlock/veto signals`，后文统一成 `safety interlock`。

### P1. `R_u^{hc}` 的矩阵写法仍有潜在数学问题

位置：第 486--490 行。

现在文字说 input order 与 `u=[a_x,\delta]` 一致，这解决了输入顺序问题。但公式

```latex
R_u^{\mathrm{hc}}=\mathrm{diag}(1,\eta_\delta)R_u
```

如果 `R_u` 不是对角矩阵，左乘一个对角缩放矩阵不一定保持对称半正定，和前面 `R_u\succeq0` 的设定不完全一致。

建议二选一：

1. 明确 `R_u` is diagonal，然后当前写法可接受。
2. 改成对称缩放：

```latex
D_\delta=\mathrm{diag}(1,\sqrt{\eta_\delta}),\qquad
R_u^{\mathrm{hc}}=D_\delta R_u D_\delta .
```

这个问题不是纯文字问题，但会被认真审公式的审稿人抓住。

### P2. `low-order consistency floor` 表达不自然

位置：第 303 行。

`\ZOHcons{} uses zero-order hold (ZOH) and is only a low-order consistency floor for ablation.`

`floor` 在这里有口语感，含义也不够清楚。建议改成：

> \ZOHcons{} uses zero-order hold (ZOH) as a low-order consistency baseline for ablation.

### P2. `task-aligned mechanism baseline` 仍有一点虚

位置：第 303 行。

`\AKE{} or \AKEdeg{} denotes a task-aligned mechanism baseline derived from the adaptive Koopman embedding idea of Singh et al.`

这句话比上一版安全，但 `mechanism baseline` 不够学术。建议说明它是“adapted baseline”，并点明不是复现原论文实验。

推荐改为：

> \AKE{} and \AKEdeg{} denote task-adapted AKE-style baselines derived from the adaptive Koopman embedding idea of Singh et al.; they adapt the lifted prediction-correction mechanism to the present cooperative-transport setting rather than reproducing the original AKE experiments one-to-one.

### P2. `scenario tags` 说明还不够可复现

位置：第 377 行。

现在写了 nominal clean operation、high communication noise、single actuator fault、mixed fault/noise，这比上一版好。但这些工况只作为 tag 出现，没有给出噪声、时延、丢包、故障效率的采样范围或指向实验设置。

建议加一句：

> Their delay, packet-loss, bias, noise, and actuator-efficiency ranges are specified in the experiment protocol.

如果实验设置中没有表，应补一个表，否则数据生成的可复现性仍弱。

### P2. `path-context variables` 已经列举，但缺少维度闭合

位置：第 381 行。

现在已经列出 reference curvature、reference heading、path progress、preview points、high-curvature indicators，这是进步。但 `\chi_k\in\mathbb R^{n_\chi}` 仍未给出实际维数。后文实验说当前观测是 24 维/31 维提升，方法章最好提前给出或说明“dimension used in experiments is reported in Section ...”。

建议补一句：

> The concrete dimension used in the experiments is reported with the Koopman ablation protocol.

更好的是在方法章直接列出 `n_\chi=24`、`n_z=31`，如果这确实是最终设置。

### P2. 第 469 行语法连接可以更自然

位置：第 469 行。

原文：

> $\bar q_{ij,k}$ is the smoothed link quality.

在公式后单独起句可以读，但更标准是：

> where $\bar q_{ij,k}$ is the smoothed link quality.

或者把平滑方式一句交代清楚，例如 EWMA 或 moving average。

### P2. 第 527 行具体阈值放在方法章略显实现化

位置：第 527 行。

残差阈值 0.18、CUSUM 阈值 0.30、连续检测保持 5 步、释放保持 10 步，这些更像 experiment protocol 或 implementation settings。方法章可以保留阈值符号，具体数值放实验设置。

建议方法章写：

> Warm-up, consecutive-trigger, and release-hold counters are used to suppress transient noise. The numerical thresholds are reported in the experiment settings.

若审稿倾向工程实现，也可以保留数值，但需要说明这些是 `current implementation settings`，不属于理论必要条件。

### P2. 图题仍偏长，可能影响版式和目录/图目录

位置：第 308、315 行。

两个 `figure*` 的 caption 过长，`.aux` 中也记录了整段长 caption。日志里第 303--304 行附近有 underfull warning，和图题/长段有关。建议使用短标题可选参数：

```latex
\caption[Four-layer architecture of \Method{}]{Four-layer cooperative-control architecture of \Method{}. ...}
```

这样 List of Figures 和 PDF 书签更干净，也减少长 caption 带来的排版风险。

## 低风险语言润色建议

1. 第 321 行 `payload-center layer` 可改为 `payload-center-level planner`，更自然。

2. 第 348 行 `payload-centered team should turn` 可以改为 `the payload-centered team should negotiate high-curvature segments`，表达更工程化。

3. 第 490 行 `This mode is designed to demonstrate...` 建议改成 `This mode is intended to improve...`。方法章不宜使用 demonstrate，因为 demonstrate 更像实验章节。

4. 第 514 行 `safely published or degraded` 中 `degraded` 作动词略别扭，可改为 `safely issued or replaced by a degraded-mode command`。

5. 第 299 行 `providing protection around the same vehicle-level optimizer` 语义略抽象，可改为 `wrapped around the same vehicle-level optimizer` 或 `connected to the same vehicle-level optimizer`。

## 编译和范围观察

1. 第 2、3 章范围内没有中文残留。

2. 编译日志没有发现 Undefined Citation 或 Undefined Reference。

3. 日志仍有版式警告，主要包括：
   - 第 208 行附近公式 overfull；
   - 第 303--304 行和第 445--446 行附近 underfull；
   - 后文中文章节导致 SimSun/xeCJK 字体警告。

4. 第 4 章以后仍是中文。如果这份最终目标是完整英文稿，则第 4 章以后还不能提交；如果本轮只处理第 2、3 章，这一点不影响本轮结论。

## 审稿结论

这次第 2、3 章的修改方向是对的，属于有效修订。上一轮的大问题基本都被处理掉了，尤其是章节英文化、载荷中心定义、force proxy 边界、Koopman predictor 过渡、实验窗口移出方法章这几项。

下一轮不用再大改第 2 章。第 3 章建议集中修四类问题：

1. 正式定义 degraded fallback/C3 的触发和动作。
2. 给 PPC guard/envelope 一个最小定义。
3. 删除方法章中的结果性句子，尤其是第 536 行。
4. 统一 role scheduling、fallback、safety interlock/veto、AKE-style baseline 这些术语。

完成这些后，第 2、3 章从文本连续性角度基本可以进入下一轮全稿英文一致性检查。
