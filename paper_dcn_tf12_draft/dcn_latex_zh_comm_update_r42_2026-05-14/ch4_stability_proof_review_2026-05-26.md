# 第四章稳定性证明复审意见

对象文件：`manuscript_en_ch2_ch3_reviewfix_2026_05_26.tex`

审阅范围：第 4 章“稳定性证明”，约第 542--620 行，并回查第 3 章中与 MPC、IRSP、fallback、PPC、FTC 相关的定义。

审阅目标：检查证明是否闭合、假设是否足够、符号是否已定义、结论是否过强，以及与第 3 章方法定义是否一致。

## 总体判断

第四章的方向是对的：没有声称全局渐近稳定，而是收缩为有界工作域下的 ISS/UUB 型实践有界结论；也把 Koopman 残差、通信退化、执行器退化、fallback 和货物保护切换都放进了证明框架。这种定位比强行证明全局稳定更安全。

但如果按严格审稿标准，目前证明还不能算完全闭合。主要问题是：证明依赖了第 3 章没有正式实现或定义的终端控制律/终端集；把 MPC 最优值 `J_k^\star` 与自定义证书函数 `\bar V_k` 等价这一关键桥没有证明；状态相关 Koopman 残差没有给出小增益吸收条件；证书失败的“有限密度”不足以单独推出最终有界；多个模式的 Lyapunov 矩阵切换缺少比较条件。

另外，当前文件是 `manuscript_en...`，但第四章仍是中文。这对完整英文投稿是格式层面的硬伤；以下先聚焦数学证明本身。

## P0：必须修，否则证明容易被审稿人否掉

### 1. 终端控制律和终端集只在证明里出现，第 3 章 MPC 没有定义

位置：第 555、604 行。

证明假设存在局部控制律 `\kappa_f` 和终端集 `\mathcal X_f`，随后在第 604 行用“去掉首项并接上终端控制律”构造下一时刻可行序列。这是标准 MPC 稳定性证明套路，但第 3 章的 MPC 定义里只有终端代价 `P_L`，没有终端约束 `x_{k+H}\in\mathcal X_f`，也没有终端控制律 `\kappa_f` 的定义。

审稿风险：读者会认为证明使用了一个控制器中不存在的 terminal ingredient。

建议二选一：

1. 在第 3 章 MPC 约束中明确加入终端集和终端控制律，并说明实验中是否启用。
2. 如果实际代码没有终端集，则把证明改成“实践 MPC 证书证明”：不再使用标准 terminal-shift proof，而是假设在线证书直接验证一步下降，即以式 \eqref{eq:mode_certificate_margin} 作为可验证条件。

更安全的写法是第二种：

> Rather than claiming a classical terminal-set MPC proof, the theorem is stated for the implemented certificate: whenever the logged one-step certificate margin satisfies the stated finite-density condition, the closed-loop error is practically ultimately bounded.

### 2. `\bar V_k` 与 `J_k^\star` 等价没有依据

位置：第 619 行。

证明最后写：

```latex
\underline c\norm{\xi_k}^2\le \bar V_k\le \bar c\norm{\xi_k}^2+\bar c_0
```

并说由此得到式 \eqref{eq:iss_difference}。但前面下降的是 `J_k^\star`，而 `\bar V_k` 是另外定义的证书函数。二者并不自动等价。

具体不闭合点：

- `J_k^\star` 是有限时域 MPC 最优代价。
- `\bar V_k` 包含 lifted 预测误差 `\tilde z_k`、执行器效率项 `(1-\hat\eta)^2`、链路质量项 `(1-\bar q)^2`、受力代理项。
- 第 3 章的 MPC 代价并没有直接惩罚 `\tilde z_k`、`\hat\eta` 或 `\bar q` 的 Lyapunov 项。

因此“标准 MPC 下降 -> 证书函数下降”之间缺少一个引理。

建议增加一个 Assumption 或 Lemma：

> 在有界工作域内，MPC 最优值、证书函数和组合误差满足局部二次夹逼，并且证书附加项的单步变化由通信/故障/切换扰动有界。

如果不想加引理，就把定理表述改弱：证明不是从 `J_k^\star` 推出 `\bar V_k`，而是直接假设证书裕度 `m_k` 以有限密度通过。

### 3. stage cost 不能下界整个 `\xi_k`

位置：第 560、606--609 行。

组合误差定义为：

```latex
\xi_k=\mathrm{col}(e_L,e_c,e_{y,i},e_{\psi,i},\tilde z_k)
```

但 MPC stage cost 主要惩罚 `e_L`、车辆横向/航向误差、邻接一致性、连接误差、输入和输入增量。它没有显式惩罚 `\tilde z_k`。因此第 609 行：

```latex
\ell(\xi_k,u_k)\ge \underline q\norm{\xi_k}^2
```

一般不成立，除非额外假设 `\tilde z_k` 可以由物理误差和残差项上界，或者在 MPC/证书中显式加入 lifted-error penalty。

建议改为：

```latex
\ell(e_k,u_k)\ge \underline q\norm{e_k}^2
```

其中 `e_k` 只包含 MPC 代价实际惩罚的物理误差；然后单独证明 `\tilde z_k` 由 IRSP 和残差边界输入到状态有界。

更稳的结构是把证明拆成两步：

1. physical MPC error is practically bounded；
2. lifted prediction error is bounded by IRSP plus residual bound。

### 4. Koopman 残差中有状态相关项，但定理没有小增益条件

位置：第 438、614--616 行。

第 3 章 residual bound 为：

```latex
\norm{w_k}\le \bar w_0+\bar w_\chi\norm{\chi_k-\chi_k^\mathrm{ref}}+\bar w_q(1-q_k^{net})
```

证明中将 `w_k` 代入后说用 Young 不等式吸收交叉项。但 `\bar w_\chi\norm{\chi-\chi^{ref}}` 是状态相关项，代入 `c_w\norm{w_k}^2` 会产生一个与 `\norm{\xi_k}^2` 同阶的正项。如果没有小增益条件，它可能抵消甚至超过 `-\alpha_0\norm{\xi_k}^2`。

建议在 theorem 中加入条件：

```latex
\alpha_0 > c_w \bar w_\chi^2 L_\chi^2
```

或文字：

> the state-dependent residual gain is small enough to be absorbed by the MPC stage-cost decrease.

否则 ISS 差分不等式不能从当前推导推出。

### 5. 证书失败“有限密度”不足以推出 UUB

位置：第 595、619 行。

当前条件是：任意窗口内证书失败比例不超过 `\bar\nu<1`。这还不够。因为失败步如果可以造成任意大的增长，即使比例小也可能破坏最终有界。

需要补充失败步的增长上界和平均收缩条件，例如：

```latex
\bar V_{k+1}\le (1+\rho_f)\bar V_k+c_f
```

在失败步成立，并且

```latex
(1-\bar\nu)\alpha > \bar\nu\rho_f
```

或等价的平均 dwell-time / average contraction 条件。

否则第 619 行“有限密度负裕度约束排除了证书长期连续失败，因而切换增量可并入最终界”这个推理不够严谨。

## P1：需要修，否则严审会要求大修

### 6. IRSP 条件 `r_u<1+\epsilon_\rho` 太弱

位置：第 590 行。

定理写：

```latex
\max_{u\in\mathcal U_s}\rho(A_{\mathrm{eff}}^+(u))\le r_u<1+\epsilon_\rho
```

如果 `r_u` 可以大于 1，lifted predictor 并不收缩，只是“接近稳定”。这与后面的 ISS/UUB 结论之间需要额外解释。第 3 章实验里 IRSP 后谱半径约为 0.998，实际可以写得更强。

建议改为：

```latex
r_u\le 1-\epsilon_\rho,\qquad \epsilon_\rho>0
```

如果必须允许轻微超过 1，则需说明 MPC 反馈收缩和有限 horizon 误差限制共同吸收该增长，不要把它写成稳定投影本身的条件。

### 7. mode 记号与第 3 章不一致

位置：第 445、575--582 行。

第 3 章定义：

```latex
\mu_k\in\{\mathrm{C0},\mathrm{C1},\mathrm{C2},\mathrm{C3}\}
```

第 4 章又定义：

```latex
\mu_k\in\{\mathrm{nominal},\mathrm{lat},\mathrm{payload},\mathrm{FTC},\mathrm{degraded}\}
```

这会造成两套 mode 系统。建议统一，或者明确映射：

- C0 = nominal
- C1 = lat
- C2 = payload
- C3 = degraded
- FTC 是叠加的 execution-layer flag，而不是同一层级的 C-mode

如果 FTC 确实是独立 mode，则第 3 章也应把 mode 集合改成五类。

### 8. `\bar V_{\mu,k}` 没有定义

位置：第 570、575--579 行。

第 570 行定义的是：

```latex
\bar V_k=V_k+\mu_F\sigma_k\norm{\hat F_{L,k}^{xy}}^2
```

第 575 行又说在线证书采用 `P_{\mu_k}`，第 577--579 行使用 `\bar V_{\mu_k,k}`。但没有明确：

```latex
\bar V_{\mu,k}=\xi_k^\top P_\mu\xi_k+...
```

建议补定义。否则证书公式中的 `\bar V_{\mu_k,k}` 是突然出现的新函数。

### 9. 多 Lyapunov 矩阵切换缺少比较条件

位置：第 575--582 行。

如果每个 mode 用不同 `P_\mu`，切换时需要矩阵比较条件，例如：

```latex
\bar V_{\nu,k}\le \rho_{\mu\nu}\bar V_{\mu,k}
```

并配合平均驻留时间或有限切换密度。否则 mode 切换可能导致 Lyapunov 函数跳增，单步裕度不能直接推出全局最终有界。

建议增加：

> there exists `\rho_P\ge1` such that all mode certificates are mutually comparable in the compact operating set.

并把 `\rho_P` 纳入有限密度/平均收缩条件。

### 10. `d_k` 未定义

位置：第 578、592、595、611、616 行。

`d_k` 在第四章中作为外部扰动出现，但没有定义。前文有 `d_{x,i},d_{y,i},d_{r,i}`，也有通信噪声 `\epsilon`、偏置 `\beta`、执行噪声 `\nu`。审稿人不知道 `d_k` 是否包含这些全部扰动。

建议在第 558 行前后加一句：

> Let `d_k` collect model disturbances, communication bias/noise not already represented by `q_k^{net}` and `\tau_k`, and actuator implementation errors.

如果 `d_k` 只表示车辆动力学扰动，也要明确排除通信项。

### 11. `z_k^\star` 未定义

位置：第 563 行。

`\tilde z_k=z_k-z_k^\star` 中的 `z_k^\star` 没有定义。建议写成：

```latex
z_k^\star=\Phi_\theta(\chi_k^\mathrm{ref})
```

或者如果它是 Koopman 预测参考轨迹，应说明来自 MPC reference rollout。

### 12. `\gamma` 符号复用

位置：第 412--414、565 行。

第 3 章 IRSP 已用 `\gamma` 表示双线性输入矩阵缩放系数；第 4 章 Lyapunov 函数又用 `\gamma` 表示网络退化项权重。虽然上下文能区分，但在证明里容易混淆。

建议把第 4 章的 `\gamma` 改为 `\gamma_q` 或 `\gamma_{\mathrm{net}}`。

### 13. 执行器效率项与 FDI/FTC 模型不完全匹配

位置：第 565、520--531 行。

第 3 章 FDI 分别跟踪纵向加速度和转角通道：

```latex
\hat\eta_i^a,\quad \hat\eta_i^\delta
```

但第 4 章 Lyapunov 函数写：

```latex
\sum_i \beta_i(1-\hat\eta_{i,k})^2
```

这里 `\hat\eta_{i,k}` 是标量还是向量不清楚。如果是两通道向量，应写成：

```latex
\sum_i \norm{\mathbf 1-\hat\eta_{i,k}}_{B_i}^2
```

如果用最小效率代表，应定义：

```latex
\hat\eta_{i,k}=\min(\hat\eta_i^a,\hat\eta_i^\delta)
```

### 14. FTC projection 不保证连接误差下降

位置：第 529--538、619 行。

式 \eqref{eq:ftc_projection} 最小化：

```latex
\norm{u-u_k^{mpc}}_{R_s}^2+\alpha_e\norm{e_{c,k+1}(u)}^2
```

这说明它折中接近 MPC 命令和连接误差，但不自动保证连接误差下降。第 619 行说“并优先减小连接误差项”可以接受，但如果要用于证明下降，需要假设投影后满足：

```latex
\norm{e_{c,k+1}(u^{safe})}^2 \le \norm{e_{c,k+1}(u^{mpc})}^2 + c_\eta\|\tilde\eta_k\|^2
```

或类似有界劣化条件。

否则不能从 FTC projection 直接推出 Lyapunov 下降。

### 15. `c_F|\Delta\sigma_k|^2` 可能应为 `c_F|\Delta\sigma_k|`

位置：第 592、619 行。

货物保护项变化包含：

```latex
\mu_F(\sigma_{k+1}\|F_{k+1}\|^2-\sigma_k\|F_k\|^2)
```

其中由 `\Delta\sigma_k` 带来的部分通常先得到线性界 `C|\Delta\sigma_k|`，不是自然得到平方界。除非再引入额外条件，否则 `|\Delta\sigma|` 不能一般地被 `|\Delta\sigma|^2` 上界。

建议改为：

```latex
c_F|\Delta\sigma_k|
```

最终界中也相应写 `\overline{|\Delta\sigma|}`。

### 16. 证明中 `c_0` 没有进入最终界说明

位置：第 616、600 行。

第 616 行得到：

```latex
... + c_0
```

但第 600 行最终界 `\Omega` 只写了 `\bar w_0^2` 等项，没有明确 `c_0`。如果 `c_0` 来自 residual constant，可以写入 `\bar w_0^2`；如果还包含其他近似误差，应明确放入最终界。

建议最终界写：

```latex
\Omega=O(c_0+\bar d^2+...)
```

或说明 `c_0=O(\bar w_0^2)`。

## P2：文字和呈现层面建议

### 17. 第四章仍是中文

位置：第 542--620 行。

如果当前 PDF 是英文稿，第四章必须翻译成英文。现在第 2、3 章已英文，第四章和后续实验仍是中文，会显得稿件没有统一完成。

### 18. `ISS/UUB` 记号建议在第四章首次处再展开一次

位置：第 544、584 行。

虽然引言中已经展开 ISS/UUB，但第四章是证明核心，建议第一次出现时写：

> input-to-state stability (ISS) and uniform ultimate boundedness (UUB)

中文稿也可写“输入到状态稳定性（ISS）和一致最终有界性（UUB）”。

### 19. `nominal 工作域`、`finite horizon`、`degraded fallback` 中英混用

位置：第 555 行。

如果保留中文证明，建议统一：

- `nominal 工作域` -> `标称工作域`
- `finite horizon` -> `有限预测时域`
- `degraded fallback` -> `降级回退（degraded fallback）`

如果翻成英文，则整段自然解决。

### 20. `\Omega` 中带横线的上界记号不清楚

位置：第 600 行。

```latex
\overline{(1-q^{net})}^2,\quad \overline{|\Delta\sigma|}^2
```

需要说明横线表示 supremum、time average 还是 window bound。建议改成：

```latex
\|1-q^{net}\|_\infty^2,\quad \|\Delta\sigma\|_\infty
```

或明确 “where the overbar denotes the corresponding uniform bound.”

## 建议的证明重构路线

最稳妥的方式不是把现在的证明继续硬补成经典 MPC 终端集证明，而是把它改成“证书驱动的实践有界证明”。这样更符合当前代码和实验中的 certificate ok ratio。

建议结构：

1. 定义组合误差 `\xi_k`，但把 physical error 和 lifted error 分开。
2. 明确 `d_k`、`z_k^\star`、`\bar V_{\mu,k}`、mode 映射。
3. 把定理前提改成：若证书通过步满足式 \eqref{eq:mode_certificate_margin}，失败步满足有界增长，失败比例满足平均收缩条件。
4. 用 IRSP 和 residual small-gain 条件保证 lifted error 不爆。
5. 结论只说 practical ISS/UUB，不说全局稳定或严格递归可行。

可替换的定理核心前提可以写成：

```latex
Assume that, on certificate-passing steps,
\bar V_{\mu_{k+1},k+1}-\bar V_{\mu_k,k}
\le -\alpha\|\xi_k\|^2
+c_d\|d_k\|^2+c_q(1-q_k^{net})^2+c_\tau\tau_k^2+c_F|\Delta\sigma_k|.
On certificate-failing steps, assume
\bar V_{\mu_{k+1},k+1}\le (1+\rho_f)\bar V_{\mu_k,k}+c_f.
If the failing-step density satisfies an average contraction condition, then ...
```

这种写法更诚实，也更容易与实验中的 ok ratio 对上。

## 编译日志观察

1. 未发现 undefined citation/reference。
2. 第四章相关 label 正常生成，例如 `eq:mode_certificate_margin` 和 `eq:uub_bound`。
3. 日志主要是版式和 CJK 字体警告，不是证明引用错误。

## 审稿结论

第四章目前可以作为“证明草案”，但还不能作为严格证明直接提交。最大风险是证明使用了未在控制器中定义的 terminal set/control law，并且把 `J_k^\star`、`\bar V_k`、mode-wise certificate 三套对象之间的关系跳过了。

建议下一版不要追求更强结论，而是把证明收缩为“certificate-verified practical ISS/UUB”。只要补上 `d_k`、`z_k^\star`、`\bar V_{\mu,k}`、mode 映射、小增益条件、失败步有界增长和平均收缩条件，这一章会稳很多。
