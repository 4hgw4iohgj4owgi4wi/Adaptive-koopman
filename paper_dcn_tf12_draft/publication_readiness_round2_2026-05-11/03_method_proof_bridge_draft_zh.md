# Worker C 方法-证明桥接草稿（中文稿可集成版）

目标文件：`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

本稿只提供可插入中文稿的方法-证明桥接文本，不修改 DOCX。核心修补点是：先把局部 Koopman MPC、通信补偿、FTC、安全聚合与团队中心物理系统串成完整闭环，再把该非光滑混合闭环在模式 `sigma_k` 下抽象为局部增益界或 Lipschitz 增益不等式。证明主结论限定为 conditional practical boundedness / UUB，不宣称全局渐近稳定、任意通信故障稳定、未知故障完全恢复，也不把固定活动集下的局部线性化等同于全局闭环模型。

## 1. 建议插入位置与公式编号

| 插入项 | 建议位置 | 目的 | 建议公式号 |
|---|---|---|---|
| 控制链桥接段 | 放在现稿第 4.5 节“通信退化回退、在线 FDI 与执行器故障容错”末尾，当前段落“进入低激进度安全一致性模式”之后；也可单独成小节“4.6 控制链到团队闭环的桥接”，原 4.6 顺延。 | 在 baseline 总结前先明确本文控制栈如何从单车命令进入团队中心闭环。 | 式 (C1a)--(C1e)、(C2) |
| `A_sigma/B_sigma` 诱导说明 | 替换或扩展现稿第 4.8.1 中直接定义 `A_sigma`、`B_sigma` 的段落。 | 先用局部 Lipschitz 增益界作为主证明线；若保留 `A_sigma/B_sigma`，只把它限定为固定活动集或局部线性化下的辅助对象。 | 式 (C3)--(C6) |
| 扰动/通信/FTC/求解误差递推 | 放在现稿第 4.8.5“有扰动与辨识误差情形”开头，先于现有 `q_k` 加权不等式。 | 将有界扰动、通信质量、执行器估计误差、求解误差四类项显式分开。 | 式 (C7)--(C8) |
| Lyapunov practical/UUB 结论 | 替换现稿第 4.8.7 末尾和第 4.8.8 总结中可能过强的“零扰动退化为指数稳定”主叙事。 | 将理论边界固定为 conditional practical boundedness / UUB，避免 ISS 等价 UUB 或指数收敛主声明。 | 式 (C9)--(C12) |
| 理论覆盖区间表 | 建议放在第 4.8 节稳定性结论之后，或放在实验设置中理论声明边界说明之前。 | 区分 0--200 ms/0--20% dropout/recoverable topology 主声明候选与 400 ms/40% dropout/leader-lost stress-test。 | 表 C1 |
| 符号硬门禁表 | 建议放在第 2 节系统模型之后，或第 4.8.1 前作为“符号约定与证明变量”。 | 统一 `q/Gamma/delta/tau/x/z/G/A/B` 等高冲突符号。 | 表 C2 |

注：上表使用 `C` 编号仅为本桥接草稿内部标号。正式集成到 DOCX 时应按全文公式顺序改为连续编号，建议保留 `(a)--(e)` 子式以展示链式控制流。

## 2. 可插入正文：控制链到团队闭环

建议插入第 4.5 节末尾，或作为新小节“控制链到团队闭环的桥接”。

> 为了使后续 Lyapunov 型证明与实际控制栈一致，本文不直接把局部 MPC 的预测矩阵或 Koopman 训练矩阵当作团队闭环矩阵。四车闭环的执行顺序为“局部 MPC 生成名义命令、通信质量补偿与时延前推修正命令、FDI/FTC 按执行器效率重构命令、团队聚合和安全保护形成载荷中心等效命令、物理团队系统推进到下一采样时刻”。对第 `i` 辆角点车，先由局部 lifted state 与局部参考轨迹得到
>
> \[
> u_{i,k}^{\mathrm{mpc}}
> =
> K_i^{\mathrm{mpc}}\!\left(z_{i,k},x_{i,k}^{\mathrm{ref}},Q_i,R_i,\mathcal U_i\right),
> \qquad i=1,\ldots,4 ,
> \tag{C1a}
> \]
>
> 其中 `z_{i,k}` 是第 `i` 车 Koopman 升维状态，`Q_i,R_i` 为 MPC 代价权重，`\mathcal U_i` 为输入约束集合。随后，通信质量感知一致性模块根据链路质量、入向质量、全局质量、时延预测状态和时变通信图对四车命令做一致性修正：
>
> \[
> u_{i,k}^{\mathrm{comm}}
> =
> \Pi_i^{\mathrm{comm}}\!\left(
> \{u_{j,k}^{\mathrm{mpc}}\}_{j=1}^{4},
> \{\hat x_{j|i,k}\}_{j=1}^{4},
> q_{ij,k},q_{i,k}^{\mathrm{in}},q_{g,k},
> \tau_{ij,k}^{\mathrm{comm}},G_k
> \right).
> \tag{C1b}
> \]
>
> 当在线 FDI 给出执行器效率估计后，FTC 层把通信补偿后的命令映射为故障感知命令：
>
> \[
> u_{i,k}^{\mathrm{ftc}}
> =
> \Pi_i^{\mathrm{ftc}}\!\left(
> u_{i,k}^{\mathrm{comm}},
> \hat\Gamma_{i,k},
> c_{i,k}^{\mathrm{fdi}},
> \sigma_k,
> \mathcal U_i
> \right),
> \tag{C1c}
> \]
>
> 其中 `\hat\Gamma_{i,k}` 为执行器效率估计，`c_{i,k}^{fdi}` 为诊断置信度，`\sigma_k` 表示当前全局控制模式。四车 FTC 输出再经均值-中值混合聚合、稳定保护、进度监督和安全限幅得到团队中心等效命令：
>
> \[
> u_{c,k}^{\mathrm{agg}}
> =
> \Pi^{\mathrm{agg}}\!\left(
> \{u_{i,k}^{\mathrm{ftc}}\}_{i=1}^{4},
> x_{c,k},
> q_{g,k},
> \sigma_k
> \right).
> \tag{C1d}
> \]
>
> 团队中心物理系统最终在该等效命令和有界外部项作用下更新为
>
> \[
> x_{c,k+1}
> =
> F_c\!\left(
> x_{c,k},
> u_{c,k}^{\mathrm{agg}},
> d_{k}^{\mathrm{phys}}
> \right).
> \tag{C1e}
> \]
>
> 因此，本文实际闭环不是单一 MPC 模块，而是由
>
> \[
> u_{i,k}^{\mathrm{mpc}}
> \rightarrow
> u_{i,k}^{\mathrm{comm}}
> \rightarrow
> u_{i,k}^{\mathrm{ftc}}
> \rightarrow
> u_{c,k}^{\mathrm{agg}}
> \rightarrow
> x_{c,k+1}
> \tag{C2}
> \]
>
> 构成的组合映射。后续稳定性证明中的团队等效闭环矩阵只能从式 (C1)--(C2) 所定义的完整控制链诱导得到，而不能直接等同于 Koopman 训练矩阵、单车 lifted 预测矩阵或单车 MPC 的局部反馈矩阵。

## 3. 可插入正文：`A_sigma/B_sigma` 的诱导含义

建议替换或扩展现稿第 4.8.1 中“其中 `A_sigma` 为当前模式下的等效闭环误差矩阵，`B_sigma` 为输入通道矩阵”相关段落。

> 令团队中心跟踪误差统一定义为
>
> \[
> e_k=x_{c,k}-x_{c,k}^{\mathrm{ref}} .
> \tag{C3}
> \]
>
> 在模式 `\sigma_k\in\{N,R,S\}` 下，将式 (C1)--(C2) 的局部 MPC、通信补偿、FTC、安全聚合和团队中心动力学组合为闭环映射
>
> \[
> e_{k+1}
> =
> \Phi_{\sigma_k}\!\left(
> e_k,
> d_k,
> s_{q,k},
> \tilde\Gamma_k,
> \xi_k
> \right),
> \tag{C4}
> \]
>
> 其中 `d_k` 汇总 Koopman 预测残差、物理模型误差和外部扰动，`s_{q,k}=1-q_{g,k}` 表示全局通信退化程度，`\tilde\Gamma_k=\operatorname{blkdiag}(\Gamma_{1,k}-\hat\Gamma_{1,k},\ldots,\Gamma_{4,k}-\hat\Gamma_{4,k})` 表示执行器效率估计误差，`\xi_k` 汇总 MPC 近似求解误差、部分车辆跳步求解、phase-role 有界 trim、聚合残差和数值误差。由于式 (C1)--(C2) 包含输入投影、饱和、安全模式切换、FDI/FTC 逻辑和通信图切换，`\Phi_{\sigma_k}` 一般是非光滑混合映射，证明中不应把它优先写成全局近似线性等式。主线应采用局部增益界：在参考轨迹邻域 `\Omega_\sigma` 内，若闭环组合映射对各输入通道存在局部 Lipschitz 或 one-step 增益上界，则有
>
> \[
> \|e_{k+1}\|
> \le
> \rho_{\sigma_k}\|e_k\|
> +
> L_{d,\sigma_k}\|d_k\|
> +
> L_{q,\sigma_k}s_{q,k}
> +
> L_{\Gamma,\sigma_k}\|\tilde\Gamma_k\|_F
> +
> L_{\xi,\sigma_k}\|\xi_k\|
> +
> \bar r_{\sigma_k}.
> \tag{C5}
> \]
>
> 式 (C5) 是后续 Lyapunov 论证的主要入口，其中 `\rho_{\sigma_k}` 是误差通道的一步局部增益，`L_{d,\sigma_k}`、`L_{q,\sigma_k}`、`L_{\Gamma,\sigma_k}`、`L_{\xi,\sigma_k}` 分别刻画模型/外扰、通信退化、执行器效率估计误差和求解误差对下一步误差的放大程度，`\bar r_{\sigma_k}` 表示高阶余项、聚合残差和离散化残差在工作域内的上界。
>
> 若正文仍希望保留 `A_\sigma/B_\sigma` 记号，只能把它们限定为固定活动集和局部线性化下的辅助解释。具体地，在 MPC 约束活动集、安全投影活动集、FTC 分支、通信图模式和切换模式均固定，且 `\Phi_\sigma` 在参考轨迹邻域可微时，才可对增量变量写成
>
> \[
> \Delta e_{k+1}
> =
> A_{\sigma,\mathcal A}\Delta e_k
> +
> B_{\sigma,\mathcal A}^{d}\Delta d_k
> +
> B_{\sigma,\mathcal A}^{q}\Delta s_{q,k}
> +
> B_{\sigma,\mathcal A}^{\Gamma}\operatorname{vec}(\Delta\tilde\Gamma_k)
> +
> B_{\sigma,\mathcal A}^{\xi}\Delta\xi_k
> +
> r_{\sigma,\mathcal A,k},
> \tag{C6}
> \]
>
> 其中 `\mathcal A` 表示当前固定活动集。`A_{\sigma,\mathcal A}` 和 `B_{\sigma,\mathcal A}^{(\cdot)}` 由团队中心物理模型 `F_c` 与完整控制链 `K_i^{mpc}`、`\Pi_i^{comm}`、`\Pi_i^{ftc}`、`\Pi^{agg}` 共同诱导；它们不是 Koopman 训练中的 `A_K,B_{0,K},B_{m,K}`，也不是第 `i` 辆车局部 MPC 优化问题中的预测矩阵。活动集、饱和分支、通信图或安全模式变化时，式 (C6) 不再是全局模型，正文应回到式 (C5) 的局部增益界来陈述 boundedness 结论。

## 4. 可插入正文：四类误差项的递推边界

建议放在现稿第 4.8.5 开头，作为 Lyapunov 不等式之前的误差来源分解。

> 在工作域 `\Omega` 内，假设输入投影与安全限幅为有界非扩张映射，通信时延和连续丢包长度有界，`G_k=(\mathcal V,\mathcal E_k)` 满足给定窗口内的联合连通性或最大失联时长上界，MPC 在局部工作域内保持可行，且 Koopman 残差、执行器效率估计误差和求解误差分别满足
>
> \[
> \|d_k\|\le \bar d,\qquad
> 0\le s_{q,k}=1-q_{g,k}\le \bar s_q,\qquad
> \|\tilde\Gamma_k\|_F\le \bar\Gamma,\qquad
> \|\xi_k\|\le \bar\xi .
> \tag{C7}
> \]
>
> 结合式 (C5) 的局部增益界，可把每一步误差推进写成如下可验证上界
>
> \[
> \|e_{k+1}\|
> \le
> \rho_{\sigma_k}\|e_k\|
> +
> c_{d,\sigma_k}\|d_k\|
> +
> c_{q,\sigma_k}s_{q,k}
> +
> c_{\Gamma,\sigma_k}\|\tilde\Gamma_k\|_F
> +
> c_{\xi,\sigma_k}\|\xi_k\|
> +
> \bar r_{\sigma_k},
> \tag{C8}
> \]
>
> 其中 `\bar r_{\sigma_k}` 表示未建模聚合误差、固定活动集切换导致的局部余项和离散化残差在工作域内的上界。式 (C8) 的含义是：通信退化不会被证明“完全消除”，而是通过 `s_{q,k}=1-q_{g,k}` 进入最终误差界；FTC 也不被证明“完全恢复未知故障”，而是在 `\tilde\Gamma_k` 有界、输入未严重饱和且健康车辆仍有补偿余量时，把执行亏损转化为有界扰动；实时 MPC 的有限迭代和跳步求解则通过 `\xi_k` 进入 practical bound。

## 5. 可插入正文：Lyapunov practical/UUB 结论

建议用于替换或收紧现稿第 4.8.7 和 4.8.8 的结论段。

> 对每个模式构造多 Lyapunov 函数
>
> \[
> V_{\sigma}(e)=e^\top P_{\sigma}e,\qquad P_{\sigma}=P_{\sigma}^\top\succ0 .
> \tag{C9}
> \]
>
> 若在相应工作域内存在常数 `\alpha_\sigma>0`、`c_{d,\sigma},c_{q,\sigma},c_{\Gamma,\sigma},c_{\xi,\sigma}>0`，使得同一模式下满足
>
> \[
> V_{\sigma_k}(e_{k+1})-V_{\sigma_k}(e_k)
> \le
> -\alpha_{\sigma_k}\|e_k\|^2
> +
> c_{d,\sigma_k}\|d_k\|^2
> +
> c_{q,\sigma_k}s_{q,k}^2
> +
> c_{\Gamma,\sigma_k}\|\tilde\Gamma_k\|_F^2
> +
> c_{\xi,\sigma_k}\|\xi_k\|^2
> +
> \epsilon_{\sigma_k},
> \tag{C10}
> \]
>
> 且模式切换满足最小驻留时间或平均驻留时间条件，并有
>
> \[
> V_{\sigma^+}(e)\le \mu V_{\sigma^-}(e),\qquad \mu\ge1 ,
> \tag{C11}
> \]
>
> 则在上述假设、驻留时间约束和证书常数均成立时，可推出切换闭环的条件性实用有界性；若初值位于工作域且闭环轨迹不离开该工作域，则团队中心误差最终进入由扰动和切换跳变决定的有界邻域。可写成
>
> \[
> \limsup_{k\to\infty}\|e_k\|
> \le
> R_\infty(\bar d,\bar s_q,\bar\Gamma,\bar\xi,\bar\epsilon,\mu,T_d),
> \tag{C12}
> \]
>
> 其中 `R_\infty` 随 Koopman/物理模型残差上界 `\bar d`、通信退化上界 `\bar s_q`、执行器效率估计误差上界 `\bar\Gamma`、实时求解误差上界 `\bar\xi`、高阶余项 `\bar\epsilon`、切换跳变因子 `\mu` 增大而增大，并随有效驻留时间 `T_d` 和收缩裕度改善而减小。因此，本文稳定性结论应表述为 conditional practical boundedness 或 UUB：在有界扰动、有界通信退化、有界执行器辨识误差、MPC 局部可行、闭环轨迹留在紧致工作域且切换驻留条件成立时，团队误差最终进入一个可解释的有界邻域。指数衰减型结论只可作为固定模式、固定活动集、零扰动或扰动可忽略、严格局部收缩等更强名义假设下的附注，不能作为本文主结论。
>
> 需要特别说明，代码中的 Lyapunov 证书记录器并不是数学证明本身，而是把理论量投影到仿真闭环中的在线诊断。常数可通过 E3 certificate fields 做如下估计或核验：`V` 对应式 (C9) 的二次函数值；`predicted_upper` 对应由式 (C10) 推出的下一步上界；`contraction_margin = predicted_upper - V_{k+1}` 或等价裕度用于检查该步是否仍有收缩/有界余量；`disturbance_level` 用于估计 `\bar d` 和通信退化残差的合并上界；`identification_error` 用于估计 Koopman/物理模型残差和执行器效率辨识误差对应的 `\bar d,\bar\Gamma`；`solver_error` 或可用的求解残差 proxy 用于估计 `\bar\xi`；`certificate_ok` 只表示该步数据与上界一致。即使某次仿真中的 `certificate_ok` 比例为 1，也只能说明该运行与 conditional practical/UUB 上界一致，不能替代数学证明、边界条件检查或多 seed 统计。

## 6. 理论覆盖区间与 stress-test 区间（建议作为表 C1）

建议放在第 4.8 节稳定性结论之后，或放在实验设置中理论声明边界说明之前。

| 场景维度 | 主理论声明候选区间 | 需要满足的证明条件 | 边界外 stress-test 区间 | 稿件表述要求 |
|---|---|---|---|---|
| 通信时延 | `0--200 ms` | 时延补偿后残余误差可被 `\bar d` 或 `\bar s_q` 吸收，且证书中的 `contraction_margin` 在该区间内保持非负或有足够裕度。 | `400 ms` 大时延 | 只作为经验鲁棒性或压力测试结果，不写入 Lyapunov/UUB 保证。 |
| 丢包率 | `0--20% dropout` | 连续丢包长度有界，窗口内仍满足联合连通或最大失联时长上界，`s_{q,k}` 有可验证上界。 | `40% dropout` | 可报告性能退化和恢复现象，但不能声称理论保证覆盖。 |
| 拓扑退化 | recoverable topology、短时链路退化、可恢复 leader/follower 通信 | 每个证明窗口内存在恢复路径或备用一致性链路，MPC 局部可行性和输入余量未被破坏。 | leader-lost、长时间窗口不连通、不可恢复拓扑断裂 | 标为边界外压力测试；若结果稳定，只能说明经验鲁棒性较强。 |
| 执行器故障 | 效率估计误差有界、健康车辆有补偿余量、输入未严重饱和 | `\|\tilde\Gamma_k\|_F\le\bar\Gamma` 且 FTC 重构后的命令仍落在局部可行域。 | 严重饱和、不可辨识故障、多车同时失效且无补偿余量 | 不进入主理论保证，只能作为 failure-mode 或 stress-test 讨论。 |

## 7. 符号硬门禁表（建议作为表 C2）

| 符号 | 唯一允许含义 | 允许下标/变体 | 禁止混用 | 最终稿检查点 |
|---|---|---|---|---|
| `q` | 通信质量，只能表示链路、入向或全局质量。 | `q_{ij,k}`、`q_{i,k}^{in}`、`q_{g,k}`、`s_{q,k}=1-q_{g,k}`。 | 不表示 MPC 状态权重、概率密度或广义坐标。 | MPC 权重统一写 `Q_i,Q_c,R_i`；证明中通信退化写 `s_{q,k}`。 |
| `Gamma` | 执行器效率矩阵及其估计。 | `\Gamma_{i,k}`、`\hat\Gamma_{i,k}`、`\tilde\Gamma_{i,k}=\Gamma_{i,k}-\hat\Gamma_{i,k}`。 | 不表示通信图、增益矩阵或 Koopman lifted 特征。 | FTC 和证明均把 `\tilde\Gamma_k` 作为执行器估计误差项。 |
| `delta` | 前轮转角输入。 | `\delta_{i,k}`、`\delta_{c,k}`。 | 不表示扰动、变化量、Dirac 项或 Lyapunov 差分。 | 变化量写 `\Delta u`、`\Delta A`；扰动写 `d_k`。 |
| `tau` | 通信离散时延。 | `\tau_{ij,k}^{comm}`、最大时延 `\bar\tau^{comm}`。 | 不表示载荷力矩、时间常数或采样周期。 | 力矩写 `M_z`；采样周期写 `T_s` 或 `dt`。 |
| `x` | 物理状态，必须带层级下标。 | 团队中心 `x_{c,k}`；第 `i` 车 `x_{i,k}`；参考 `x_{c,k}^{ref},x_{i,k}^{ref}`。 | 不表示 Koopman lifted state、通信质量或误差。 | 证明中禁止裸写 `x_k`；团队误差固定为 `e_k=x_{c,k}-x_{c,k}^{ref}`。 |
| `z` | Koopman 升维状态。 | `z_{i,k}`、必要时 `z_{c,k}`。 | 不表示物理状态、通信状态或证书变量。 | Koopman/MPC 预测用 `z`；团队物理闭环和 Lyapunov 用 `x_c/e`。 |
| `G` | 时变通信图。 | `G_k=(\mathcal V,\mathcal E_k)`。 | 不表示扰动输入矩阵、增益矩阵或 Gram 矩阵。 | 证明扰动矩阵写 `D_\sigma`、`W_\sigma` 或 `B_\sigma^d`，不用 `G_\sigma`。 |
| `A` | 必须区分 Koopman 预测矩阵、聚合映射和局部线性化矩阵。 | Koopman 写 `A_K`；固定活动集局部线性化写 `A_{\sigma,\mathcal A}`；聚合写 `\Pi^{agg}` 或 `\operatorname{Agg}`。 | 不允许用同一个 `A` 同时表示训练矩阵和团队闭环矩阵。 | `A_{\sigma,\mathcal A}` 必须说明只在固定活动集/局部线性化下有效；不可写成 `A_K` 的谱投影直接推出闭环稳定。 |
| `B` | 必须区分 Koopman 输入矩阵、双线性矩阵组和局部线性化扰动通道。 | Koopman 线性输入写 `B_{0,K}`；双线性项写 `B_{m,K}` 或 `\mathcal B_K`；局部线性化通道写 `B_{\sigma,\mathcal A}^d,B_{\sigma,\mathcal A}^q,B_{\sigma,\mathcal A}^\Gamma,B_{\sigma,\mathcal A}^\xi`。 | 不允许把单车 MPC 或 Koopman 的 `B` 直接当作团队证明中的 `B_\sigma`。 | 第 4.8 节首次出现 `B_\sigma` 时必须注明它不是全局模型；主证明仍使用局部增益常数 `\rho,L_d,L_q,L_\Gamma,L_\xi`。 |
| `sigma` | 全局切换控制模式。 | `\sigma_k\in\{N,R,S\}`。 | 不表示 Koopman 奇异值、噪声方差或路径曲率。 | `N/R/S` 分别映射到 `nominal_koopman_mpc`、`reconfigured_ftc_mpc`、`safe_degraded_consensus`。 |
| `d` | 有界扰动和模型残差汇总项。 | `d_k`、`\bar d`、必要时 `d_k^{phys}`。 | 不表示距离、数据集或 dropout 指示变量。 | 通信退化单独写 `s_{q,k}`；丢包指示写 `\ell_{ij,k}`。 |

## 8. 集成时应删除或收紧的过强表述

| 现稿风险表述 | 建议替换 |
|---|---|
| “当外部项为零时，结论退化为指数稳定。” | “在理想无扰动、固定模式、固定活动集且局部线性化满足严格收缩的名义情形下，可讨论局部名义收缩；本文主结论仍为 conditional practical boundedness / UUB。” |
| “通信补偿消除时延和丢包影响。” | “通信补偿降低相位滞后和命令离散度；残余通信影响通过 `s_{q,k}=1-q_{g,k}` 进入最终界。” |
| “未知故障完全恢复。” | “在效率估计误差有界、输入未严重饱和且健康车辆仍有补偿余量时，FTC 将执行亏损转化为有界扰动并保持团队误差最终有界。” |
| “证书 ok ratio 为 1 证明闭环稳定。” | “证书 ok ratio 表明该仿真运行与 Lyapunov 型上界一致，不能替代数学证明、边界条件或多 seed 统计。” |
| “任意通信退化/leader-lost 下稳定。” | “主理论保证仅覆盖有界时延、有界连续丢包或窗口联合连通、MPC 局部可行的情形；边界外压力测试只作为经验鲁棒性证据。” |

## 9. 最终可用结论句

建议在第 4.8 节末尾使用如下结论句：

> 综上，在紧致工作域、MPC 局部可行、输入投影非扩张、Koopman/物理模型残差有界、通信时延和丢包满足给定上界或窗口联合连通性、执行器效率估计误差有界、模式切换满足驻留时间约束，且 E3 证书中的 `V`、`predicted_upper`、`contraction_margin`、`disturbance_level`、`identification_error` 与 `solver_error`/proxy 所估计的常数满足式 (C10)--(C12) 的条件时，可推出 TF14 切换容错闭环的条件性实用有界性，即团队中心误差最终进入一个可解释的有界邻域。最终误差邻域由模型残差、通信退化程度、执行器辨识误差、实时求解误差和切换跳变共同决定；边界外强通信退化或严重故障实验只能作为经验鲁棒性证据，不扩大上述理论保证。
