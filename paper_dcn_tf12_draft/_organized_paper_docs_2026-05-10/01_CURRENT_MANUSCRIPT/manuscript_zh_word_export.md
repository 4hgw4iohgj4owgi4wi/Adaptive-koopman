# 基于稳定投影双线性 Koopman 学习与故障容错时延补偿协同 MPC 的四车载荷运输控制

*Fault-Tolerant Cooperative Payload Transport Control via Stable-Projected Bilinear Koopman Learning and Delay-Compensated Consensus MPC*

## 摘要

本文面向存在通信时延与单车执行器退化的四车刚性载荷协同运输任务，提出一种将稳定投影双线性 Koopman 学习、在线双线性自适应、通信质量感知一致性、时延补偿、退化安全回退、故障容错重分配以及团队稳定保护统一起来的协同控制框架。最新 `tf13_pre.ipynb` 延续了增强 Koopman 主干：可学习观测维度为 24 维，lifted state 为 31 维，编码器采用 4 层宽度 128 的 `gelu` 网络，并结合绝对增量损失、特征值稳定损失、lifted loss 加权和谱半径稳定投影，以提高团队动力学在长时域 MPC 中的可用性。与上一版按 `tf12` 撰写的中文稿不同，当前 `tf13` 主方法已重新开启在线双线性自适应、通信质量感知一致性、时延补偿和退化回退，并新增单车执行器故障容错重分配：在主 DLC 实验中，第 2 辆车自第 160 步且团队推进量超过 18 m 后进入“转角与加速度同时衰减”的持续故障。A1 刚性载荷任务的最新缓存结果表明，所提方法在 100.0% 全路径完成率与 100.0% 求解成功率下，将横向跟踪均方根误差由 0.2075 m 降至 0.0354 m，将纵向均方根误差由 2.8703 m 降至 0.4813 m，并将载荷横向峰值力由 1305.56 N 降至 496.62 N、偏航力矩峰值由 1382.06 N·m 降至 410.30 N·m。进一步地，在 `tf13_ra_verify_feasible.json` 的右角回头弯故障验证中，该方法仍保持 `full_path=true`，并实现 $\mathrm{RMSE}(e_y)=0.1180~\mathrm{m}$、$\mathrm{RMSE}(e_s)=0.6980~\mathrm{m}$。结果说明，稳定 Koopman 主干负责提供可优化且可预测的动力学骨架，而在线自适应、通信补偿和故障重分配共同负责把单车故障与链路不一致约束在团队层面可吸收的范围内。

## 关键词

Koopman 学习；协同运输；模型预测控制；故障容错；在线自适应；通信补偿

# 1 引言

Koopman 算子理论为非线性系统控制提供了一条兼顾表达能力与优化友好性的建模路线：通过将原始状态提升到更高维的观测空间，非线性动力学可以在升维空间中近似写成线性或双线性形式，从而更容易嵌入 MPC 等优化控制器 [@singh2024adaptive; @bruder2021advantages; @folkestad2021koopman]。围绕这一主线，近期研究主要沿三个方向演化。第一类工作关注如何利用双线性 Koopman 结构更好地逼近控制仿射系统 [@bruder2021advantages]；第二类工作关注如何将 Koopman 模型直接耦合到 NMPC/MPC 中以获得更高的在线求解效率 [@folkestad2021koopman]；第三类工作则开始讨论当系统参数变化、外部扰动或训练分布外工况出现时，如何让升维模型在部署阶段继续保持有效 [@singh2024adaptive]。其中，Singh 等提出的 Adaptive Koopman Embedding baseline 证明了“离线名义嵌入 + 在线自适应修正”能够显著提高复杂非线性系统在参数漂移、噪声与扰动条件下的控制鲁棒性，其在耦合摆与 3R 机械臂上分别报告了约 87%--93% 和 92% 的跟踪误差改善 [@singh2024adaptive]。然而，这条研究线的验证对象仍集中于单体系统，尚未涉及多车协同运输中的刚性耦合、通信退化和团队一致性问题。

Koopman 方法在车辆控制中的应用近两年也明显加快。一方面，Yu 等将 Koopman 双线性车辆模型嵌入线性 MPC，用于自动驾驶场景下的轨迹跟踪与车辆横向稳定控制，说明以车辆动力学为对象构造 Koopman 双线性模型是可行的 [@yu2022koopmanvehicle]。另一方面，近三年这一路线开始朝“深度双线性升维 + 车辆 Frenet 控制”继续推进：Zhao 等在 2024 年提出 deep bilinear Koopman MPC，将双线性升维结构直接用于非线性预测控制 [@zhao2024deepbilinearmpc]；Abtahi 等在 2026 年进一步给出了 Frenet 坐标下的实时车辆控制结果 [@abtahi2026frenetkoopman]；Švec 等在 2025 年则完成了 Koopman 型预测扭矩矢量控制的实验验证 [@svec2025torquevectoring]。但现有车辆 Koopman 工作大多面向单车，关注的是路径跟踪、操稳或扭矩分配，并未显式处理“多车共同搬运同一刚性载荷”时的几何一致性、受力分配和通信可靠性问题。本文的方法正是在车辆 Frenet 动力学之上，进一步把团队中心、角点映射和连接误差纳入同一升维控制框架。

多机器人协同搬运方面，研究重点已经从简单的队形随动转向受约束物体搬运、接触一致性与通信协同。An 等在 2023 年综述中指出，多机器人协同搬运正在从基于行为的松耦合策略转向更依赖通信和预测的协调方法，通信拓扑、信息不一致和平台异构性已经成为实际部署中的核心瓶颈 [@an2023multirobotsurvey]。围绕这一趋势，Amanzadeh 等在 2024 年提出了带间接自适应律的预测控制框架，用于四足机器人载荷搬运 [@amanzadeh2024quadruped]；Li 与 Loianno 在 2023 年采用多四旋翼非线性 MPC 处理缆绳悬挂载荷的协同运输与操作 [@li2023multiquadrotor]；Muhammed 等在 2024 年首先针对受约束环境下的多机器人物体运输构建了 MPC 框架，并在 2026 年进一步给出了实时去中心化 MPC 的实验验证 [@muhammed2024constrained; @muhammed2026decentralized]；Kennel-Maushart 与 Coros 在 2024 年将载荷感知轨迹优化与倾覆规避约束引入非完整移动多机器人操纵 [@kernmaushart2024payloadaware]；Li 等在 2025 年则从仓储场景出发讨论了层级约束编队协同运输 [@li2025hierarchicaltransport]。这些工作表明，最新协同搬运方法的主流路线已经转向预测控制、去中心化优化、载荷约束感知和事件触发通信。但它们大多直接围绕原始高维模型构建优化器，对数据驱动升维模型与在线自适应的结合讨论有限；同时，面向轮式车辆载荷搬运、通信质量感知一致性和载荷受力平顺性的联合设计仍未充分展开。

MPC 仍是自动驾驶与多机器人协同中的主流决策内核。Charest-Finn 与 Pejhan 在 2024 年的综述中指出，车辆 MPC 的主流价值在于能够统一处理状态约束、输入约束、舒适性与稳定性指标，但其性能高度依赖模型质量与实时求解能力 [@charestfinn2024passengermpc]。这意味着，当系统同时面临模型失配、耦合载荷、通信时延与执行器退化时，单纯增强优化器而不提升预测模型的适配性仍然是不够的。本文因此采用“稳定投影 Koopman 主干 + 在线双线性自适应 + 通信补偿协同 MPC + 团队故障容错”的串联结构：先把非线性车辆模型转换为可优化的双线性 lifted 预测模型，再把链路质量、故障重分配和团队安全保护嵌入 MPC 回路。

针对通信干扰、时延和信息攻击的控制研究同样在快速推进。Gorospe 等在 2025 年总结了协同式自适应巡航控制中常见的脆弱点，指出丢包、时延、虚假信息和链路失配会直接破坏串稳性与安全间距 [@gorospe2025resilientcacc]。Wei 等在 2024 年提出了抗 Byzantine 攻击的分布式 MPC 编队控制框架 [@wei2024secureplatooning]；Wang 等在 2023 年给出了同时处理输入时延与通信时延的周期事件触发鲁棒分布式 MPC [@wang2023petdmpc]；Zhao 等在 2025 年进一步将时延补偿显式写入异构车队的 distributed cloud MPC [@zhao2025clouddelayplatoon]；Zou 等在 2025 年把事件触发机制和自适应 ADMM 引入车队 DMPC，以降低通信与计算调用频率 [@zou2025eventadmmplatoon]；Li 等在 2026 年面向未知动态和时变通信时延，构建了 data-driven event-triggered predictive consensus control [@li2026datadrivendelaymas]；Huang 等在 2025 年则面向带通信时延的多智能体系统构建了 hybrid data-driven 与 model-based 结合的 distributed predictive control [@huang2025hybriddelaymultiagent]。这些工作证明，通信退化不能只被视为“实现层噪声”，而应当进入控制律本身。另一方面，多车搬运系统还存在另一个常被忽略的脆弱点：当某一车辆的转角或驱动力受限时，若控制器仍按“每车独立最优、团队简单平均”执行，局部故障会被刚性载荷放大为整体姿态误差。近三年分布式容错控制已经开始面向这一问题补链：Hu 等在 2026 年将 distributed NMPC 用于 UAV 编队故障容错 [@hu2026faulttolerantuav]，Zhang 等在 2025 年把执行器有效性损失纳入虚拟编组列车的分布式容错控制 [@zhang2025virtualcouplingfault]，Shahab 等在 2025 年则验证了 wheeled mobile robots 编队的 fault-tolerance capabilities [@shahab2025wmrfault]。最新版 `tf13` 正是沿着这两条脆弱链路同时展开：一方面用质量感知一致性和时延补偿削弱链路失配带来的相位误差，另一方面用故障重分配把单车执行器亏损重新映射为健康车辆可承接的团队级补偿。

基于上述分析，本文的研究对象与比较逻辑可以明确为：不是把本文方法与“历史版本”做比较，而是把它与 Adaptive Koopman Embedding baseline 在相同任务上的任务化实现做比较，并同时说明本文相对于原始 baseline 论文在问题设定上的扩展。与上一版按 `tf12` 撰写的中文稿不同，最新 `tf13_pre.ipynb` 已经把在线自适应、通信补偿和故障容错真正纳入主实验，因此本文当前版本的贡献必须围绕“增强 Koopman 主干 + 网络补偿协同 + 故障容错重分配”来组织，而不能再把这些模块写成未启用的预留接口。本文的贡献与方法模块一一对应如下。

1. 在 Muhammed 等关于受约束环境下多机器人物体运输 MPC 与实时去中心化协同搬运验证 [@muhammed2024constrained; @muhammed2026decentralized]，以及 Kennel-Maushart 与 Coros 关于载荷感知轨迹优化和倾覆规避约束 [@kernmaushart2024payloadaware] 的基础上，建立了面向四车刚性载荷搬运的载荷中心 Frenet 团队模型，将单车动力学、角点映射、柔性连接误差、团队控制冗余与载荷受力指标统一到同一表述中，为“局部故障如何转化为团队可补偿亏损”提供了结构化状态基础。
2. 在 Singh 等的 adaptive Koopman embedding [@singh2025adaptiveijrr]、Zhao 等的 deep bilinear Koopman MPC [@zhao2024deepbilinearmpc] 以及 Abtahi 等的 Frenet 车辆 Koopman 控制 [@abtahi2026frenetkoopman] 基础上，构建了“24 维可学习观测 + 常数观测 + 原始状态”的 31 维稳定投影双线性 Koopman 升维模型，采用 4 层宽度 128 的 `gelu` 编码器、绝对增量损失、特征值稳定损失、学习型解码矩阵和谱半径投影，使名义预测模型既有更强表达能力，又能在长时域 MPC 中避免不稳定滚动预测。
3. 在 Zhao 等的时延补偿 distributed cloud MPC [@zhao2025clouddelayplatoon]、Zou 等的事件触发 ADMM-DMPC 车队控制 [@zou2025eventadmmplatoon]、Li 与 Huang 等的带通信时延多智能体 predictive control [@li2026datadrivendelaymas; @huang2025hybriddelaymultiagent]，以及 Hu、Zhang、Shahab 等针对执行器退化与编队容错的分布式/协同控制工作 [@hu2026faulttolerantuav; @zhang2025virtualcouplingfault; @shahab2025wmrfault] 基础上，设计了在线双线性自适应、通信质量感知一致性、时延补偿预测、退化安全回退与单车执行器故障重分配的协同控制栈，并在 `tf13` 主实验中实际启用。其核心思想是：先用在线自适应修正局部模型失配，再用质量感知一致性和时延补偿削弱跨车信息不一致，最后把故障车辆未能提供的控制亏损分配给健康车辆，从而维持团队级等效力与等效力矩。
4. 在 Singh 等针对 adaptive Koopman robustness 的对比评估思路 [@singh2025adaptiveijrr] 与 Muhammed 等协同运输实验验证组织方式 [@muhammed2026decentralized] 的基础上，在 A1 双移线主任务、复杂回头弯路径和故障注入场景上构建了完整仿真证据链，分别从离线数据、动力学学习、团队轨迹、单车误差、连接误差、载荷受力以及故障诊断等层面展示所提方法相对于 baseline 的收益，并说明相对于上一版 `tf12` 主稿，`tf13` 如何在激活更多模块的同时保持可接受的名义性能与更强的任务覆盖范围。

# 2 系统模型与问题描述

## 2.1 坐标系与参考路径

本文采用载荷中心路径坐标系进行建模。设参考路径在大地坐标系中的弧长参数化形式为

$$
\mathbf{p}_r(s)=\begin{bmatrix}X_r(s)\\Y_r(s)\end{bmatrix},\qquad \psi_r(s)=\operatorname{atan2}\!\left(\frac{dY_r}{ds},\frac{dX_r}{ds}\right),\qquad \kappa(s)=\frac{d\psi_r}{ds}.
$$

以载荷中心为团队代表点，定义团队中心状态为

$$
\mathbf{x}_c=\begin{bmatrix}s_c & e_{y,c} & e_{\psi,c} & v_{x,c} & v_{y,c} & r_c\end{bmatrix}^{\top},
$$

其中 $s_c$ 为沿参考路径的推进量，$e_{y,c}$ 为横向偏差，$e_{\psi,c}$ 为航向误差，$v_{x,c},v_{y,c}$ 分别为车体坐标系下的纵向与横向速度，$r_c$ 为横摆角速度。控制输入定义为

$$
\mathbf{u}_c=\begin{bmatrix}\delta_c & a_{x,c}\end{bmatrix}^{\top},
$$

其中 $\delta_c$ 是团队等效转角，$a_{x,c}$ 是团队等效纵向加速度。

## 2.2 团队中心动力学

单车与团队中心都采用动态自行车模型的 Frenet 形式。对团队中心，动力学可写为

$$
\dot s_c=\frac{v_{x,c}\cos e_{\psi,c}-v_{y,c}\sin e_{\psi,c}}{1-\kappa(s_c)e_{y,c}},
$$

$$
\dot e_{y,c}=v_{x,c}\sin e_{\psi,c}+v_{y,c}\cos e_{\psi,c},
$$

$$
\dot e_{\psi,c}=r_c-\kappa(s_c)\dot s_c,
$$

$$
\dot v_{y,c}= -\frac{2C_f+2C_r}{m v_x}v_{y,c}
\;+\;
\left(-v_x-\frac{2C_f l_f-2C_r l_r}{m v_x}\right)r_c
\;+\;\frac{2C_f}{m}\delta_c,
$$

$$
\dot r_c=
-\frac{2C_f l_f-2C_r l_r}{I_z v_x}v_{y,c}
-\frac{2C_f l_f^2+2C_r l_r^2}{I_z v_x}r_c
+\frac{2C_f l_f}{I_z}\delta_c,
$$

$$
\dot v_{x,c}=a_{x,c}+r_c v_{y,c},\qquad v_x=\max(v_{x,c},0.5).
$$

本文 A1 任务的名义车辆参数取为

$$
m=1500~\mathrm{kg},\quad I_z=2250~\mathrm{kg\,m^2},\quad l_f=1.2~\mathrm{m},\quad l_r=1.6~\mathrm{m},\quad C_f=C_r=8.0\times10^4~\mathrm{N/rad}.
$$

为生成模型失配数据，离线阶段还引入了变化参数组

$$
m'=1650~\mathrm{kg},\quad I_z'=2400~\mathrm{kg\,m^2},\quad C_f'=C_r'=7.0\times10^4~\mathrm{N/rad}.
$$

## 2.3 刚性载荷几何与角点车辆映射

被搬运载荷为矩形刚体，参数为

$$
m_p=2000~\mathrm{kg},\quad L_p=5.0~\mathrm{m},\quad W_p=2.0~\mathrm{m},\quad h_{\mathrm{com}}=1.2~\mathrm{m}.
$$

载荷四个角点相对于载荷中心的几何偏移为

$$
(\Delta x_i,\Delta y_i)\in\left\{
\left(\frac{L_p}{2},\frac{W_p}{2}\right),
\left(\frac{L_p}{2},-\frac{W_p}{2}\right),
\left(-\frac{L_p}{2},\frac{W_p}{2}\right),
\left(-\frac{L_p}{2},-\frac{W_p}{2}\right)
\right\}.
$$

在刚性理想连接下，角点车辆 $i$ 的参考状态由团队中心状态映射得到：

$$
s_i^{0}=s_c+\Delta x_i\cos e_{\psi,c}-\Delta y_i\sin e_{\psi,c},
$$

$$
e_{y,i}^{0}=e_{y,c}+\Delta x_i\sin e_{\psi,c}+\Delta y_i\cos e_{\psi,c},
$$

$$
e_{\psi,i}^{0}=e_{\psi,c},\qquad
v_{x,i}^{0}=v_{x,c}-r_c\Delta y_i,\qquad
v_{y,i}^{0}=v_{y,c}+r_c\Delta x_i,\qquad
r_i^{0}=r_c.
$$

也就是说，本文不是分别对四辆车独立建模再强行拼接，而是先建立载荷中心团队模型，再通过几何映射得到四个角点车辆的局部参考和局部误差。

## 2.4 柔性连接一致性与团队误差

为了避免把车辆与角点之间的耦合写成绝对刚锁，本文引入小范围柔性连接偏差

$$
\boldsymbol{\xi}_i=\begin{bmatrix}\Delta s_i & \Delta e_{y,i} & \Delta \psi_i\end{bmatrix}^{\top},
\qquad
\dot{\boldsymbol{\xi}}_i=\begin{bmatrix}\Delta v_{s,i} & \Delta v_{e,i} & \Delta r_i\end{bmatrix}^{\top},
$$

并采用弹簧-阻尼形式更新

$$
\ddot{\boldsymbol{\xi}}_i=\mathbf{G}\,\Delta\mathbf{u}_i-\mathbf{K}\boldsymbol{\xi}_i-\mathbf{C}\dot{\boldsymbol{\xi}}_i,
$$

其中 $\Delta \mathbf{u}_i=\mathbf{u}_i-\mathbf{u}_{\mathrm{team}}$，$\mathbf{K}=\operatorname{diag}(5.6,6.6,5.0)$，$\mathbf{C}=\operatorname{diag}(3.8,4.2,3.4)$。连接状态满足零均值约束

$$
\sum_{i=1}^{4}\boldsymbol{\xi}_i=\mathbf{0},\qquad
\sum_{i=1}^{4}\dot{\boldsymbol{\xi}}_i=\mathbf{0},
$$

并受限于

$$
|\Delta s_i|\le 0.07~\mathrm{m},\quad
|\Delta e_{y,i}|\le 0.07~\mathrm{m},\quad
|\Delta \psi_i|\le 0.035~\mathrm{rad}.
$$

实验中使用如下连接一致性指标：

$$
e_{\mathrm{conn}}^{\mathrm{rms}}=\sqrt{\frac{1}{12}\sum_{i=1}^{4}\|\boldsymbol{\xi}_i\|_2^2},
$$

并记录 $\max\lvert\Delta s_i\rvert,\max\lvert\Delta e_{y,i}\rvert,\max\lvert\Delta\psi_i\rvert$ 的峰值。

## 2.5 载荷受力与角点法向载荷指标

为评价搬运平顺性，本文从团队中心动力学导出载荷受力指标。设载荷等效转动惯量为

$$
I_{p,z}=m_p\frac{L_p^2+W_p^2}{12},
$$

则载荷在车体坐标系下的纵向与横向惯性力以及绕垂向力矩为

$$
F_{x,p}=m_p a_x^{b},\qquad
F_{y,p}=m_p a_y^{b},\qquad
M_{z,p}=I_{p,z}\dot r_c,
$$

其中

$$
a_x^{b}=\dot v_{x,c}-r_c v_{y,c},\qquad
a_y^{b}=\dot v_{y,c}+v_{x,c} r_c.
$$

进一步地，四角点法向载荷由静载和纵横向载荷转移共同决定：

$$
F_0=\frac{m_p g}{4},\qquad
\Delta F_{\mathrm{long}}=\frac{m_p a_x^{b} h_{\mathrm{com}}}{2L_p},\qquad
\Delta F_{\mathrm{lat}}=\frac{m_p a_y^{b} h_{\mathrm{com}}}{2W_p},
$$

$$
\begin{aligned}
F_{\mathrm{FL}}&=F_0-\Delta F_{\mathrm{long}}-\Delta F_{\mathrm{lat}},\\
F_{\mathrm{FR}}&=F_0-\Delta F_{\mathrm{long}}+\Delta F_{\mathrm{lat}},\\
F_{\mathrm{RL}}&=F_0+\Delta F_{\mathrm{long}}-\Delta F_{\mathrm{lat}},\\
F_{\mathrm{RR}}&=F_0+\Delta F_{\mathrm{long}}+\Delta F_{\mathrm{lat}}.
\end{aligned}
$$

因此，本文不仅考察位置跟踪，也考察搬运过程中的受力峰值与角点法向载荷波动。

# 3 离线数据生成与双线性 Koopman 升维模型

## 3.1 离线数据生成

本文首先生成覆盖名义与变化动力学的团队轨迹数据。采样时间固定为 $\Delta t=0.02~\mathrm{s}$，每条轨迹长度为 1400 个状态快照。离线数据的激励工况采用 5 组纵向速度与输入幅值配置：

| 表1 离线数据生成配置 | 数值 |
| --- | --- |
| 参考速度 $v_x^{\mathrm{ref}}$ | 2.2, 2.8, 3.2, 3.6, 4.0 m/s |
| 最大转角幅值 $\delta_{\max}$ | 0.34, 0.32, 0.30, 0.28, 0.25 rad |
| 最大纵向加速度 $a_{x,\max}$ | 1.10, 1.20, 1.20, 1.10, 1.00 m/s$^2$ |
| 激励频率 | 2.2, 2.0, 1.8, 1.6, 1.4 |
| 道路模式 | 双移线 |
| 输入模式 | `feedback-dominant`, `sinusoidal`, `mixed` |
| 输入模式概率 | 0.40, 0.30, 0.30 |
| 角点变化子集权重 | 1车:0.40, 2车:0.30, 3车:0.20, 4车:0.10 |

轨迹生成后，对每条样本随机叠加 $s\in[0,80]~\mathrm{m}$ 和 $e_y\in[-2,2]~\mathrm{m}$ 的平移扰动，以增加参考位置的覆盖范围。最终离线数据集规模为

$$
\mathbf{X}\in\mathbb{R}^{720\times 1400\times 6},\qquad
\mathbf{U}\in\mathbb{R}^{720\times 1399\times 2},
$$

并按 80/20 划分训练集与验证集。最新版 `tf13_pre.ipynb` 的 A1 数据集对应双线性 lifted fit 样本数为 805824，主运行加载的 bilinear Koopman 模型报告 lifted fit RMSE 为 $5.4932\times10^{-3}$。这一点非常重要，因为它说明当前版本相对于 AKE-baseline 的差异并不是“重新换了一批更容易的数据”，而是来自更强的 Koopman 表达能力、稳定投影以及后续真正启用的自适应/通信/故障协同控制栈。

**图1 离线数据在 $(s,e_y)$ 平面中的覆盖范围（占位）**  
此处插入：随机平移后的训练/验证样本分布图，突出 $s$ 与横向偏差的覆盖范围。

## 3.2 名义双线性 Koopman 升维网络

本文采用与 Adaptive Koopman baseline 一致的“可学习观测 + 结构化观测”思路，但最新版 `tf13_pre.ipynb` 对网络容量和解码方式作了更新。设神经网络输出的可学习观测为 $\boldsymbol{\eta}(\mathbf{x}_k)\in\mathbb{R}^{24}$，则本文实际用于控制的升维状态定义为

$$
\mathbf{z}_k=
\begin{bmatrix}
1\\
\mathbf{x}_k\\
\boldsymbol{\eta}(\mathbf{x}_k)
\end{bmatrix}\in\mathbb{R}^{31}.
$$

其中常数观测保证不变项的表示能力，原始 6 维状态直接并入升维空间。与旧版固定选择矩阵不同，最新版设置 `override_C=False`，即解码矩阵 $\mathbf{C}\in\mathbb{R}^{6\times31}$ 随 Koopman 模型一起学习：

$$
\mathbf{x}_{k+1}=\mathbf{C}\mathbf{z}_{k+1},\qquad \mathbf{C}\in\mathbb{R}^{6\times31}.
$$

这样做不再强行要求原始状态通道承担全部解码任务，而是允许网络在原始状态和可学习观测之间分配预测信息。相比 baseline 的 20/27 维结构与固定选择矩阵，这种设计能把车辆横摆、横向速度和柔性连接耦合等难以线性分离的模式更充分地吸收到 lifted 子空间中。升维网络采用 4 层宽度为 128 的全连接 `gelu` 编码器，优化器为 Adam，学习率为 $2\times10^{-4}$，训练轮数为 180，批大小为 4096，权重衰减为 $8\times10^{-5}$。名义双线性 Koopman 模型写为

$$
\mathbf{z}_{k+1}=\mathbf{A}\mathbf{z}_k+\mathbf{B}\left(\mathbf{z}_k\otimes \mathbf{u}_k\right),\qquad
\mathbf{x}_{k+1}=\mathbf{C}\mathbf{z}_{k+1}.
$$

离线训练损失采用绝对增量预测误差、lifted 增量误差和特征值稳定正则的组合，可写为

$$
\mathcal{L}_{\mathrm{nom}}
=
\|\Delta \hat{\mathbf{x}}_k-\Delta\mathbf{x}_k\|_1
\, + \,
\alpha \|\Delta \hat{\mathbf{z}}_k-\Delta\mathbf{z}_k\|_1
\, + \,
\lambda_{\rho}\max(\rho(\mathbf{A})-1,0)^2
\, + \,
\lambda_w\|\Theta\|_2^2,
$$

其中 lifted loss 权重 $\alpha=0.60$，特征值稳定损失系数 $\lambda_{\rho}=0.01$。这些项的机理并不是单纯“让训练指标更小”，而是分别对应三类闭环需求：状态绝对增量损失直接约束一步预测精度，lifted 损失抑制隐藏空间漂移累积，特征值稳定项则防止 $\mathbf{A}$ 在长时域滚动预测中出现谱半径外逸。网络训练完成后，本文进一步在 lifted snapshot 上使用岭回归重拟合 $\mathbf{A},\mathbf{B}$，岭回归正则系数为 $5\times10^{-5}$，并以 0.60 的线性重拟合融合系数和 0.20 的上一模型保留系数完成平滑更新。最终保存模型的矩阵维度为 $\mathbf{A}\in\mathbb{R}^{31\times31}$、$\mathbf{B}\in\mathbb{R}^{31\times2}$、$\mathbf{C}\in\mathbb{R}^{6\times31}$。为提升闭环可用性，主运行还启用了稳定投影，使 $\mathbf{A}$ 的谱半径由原始约 1.0024 投影到约 0.9990。与 AKE-baseline 相比，这意味着 MPC 在更高维但更稳定的 lifted 空间中预测，因而能在不显著放大求解困难的前提下获得更好的团队耦合可预测性。

**图2 离线训练与验证损失曲线（占位）**  
此处插入：总损失、状态预测损失和 lifted 损失的训练/验证曲线。

## 3.3 在线高置信双线性自适应

为了把 Adaptive Koopman baseline 的“在线纠偏”真正迁移到四车搬运任务中，`tf13` 在在线阶段不改变升维映射，只修正双线性动力学矩阵。记当前观测 lifted state 为 $\mathbf{z}_k^{\mathrm{obs}}$，名义模型预测为 $\hat{\mathbf{z}}_k$，则预测残差满足

$$
\Delta\mathbf{z}_k
=
\mathbf{z}_k^{\mathrm{obs}}-\hat{\mathbf{z}}_k
=
\Delta\mathbf{A}_k \mathbf{z}_{k-1}
\;+\;
\Delta\mathbf{B}_k(\mathbf{z}_{k-1}\otimes \mathbf{u}_{k-1}).
$$

本文采用长度为 18 的滑动窗口、每 6 步更新一次的双线性岭回归来估计 $\Delta\mathbf{A}_k,\Delta\mathbf{B}_k$，遗忘因子取 0.97，回归正则系数取 $2\times10^{-4}$。这一设置的机理是：18 步窗口足够覆盖故障起始和曲率变化后的短时动态偏差，而 0.97 的遗忘因子又让近期数据比远期数据更重要，从而使自适应集中补偿“当前正在发生的模型失配”，而不是被旧工况拖拽。为避免错误样本污染在线模型，只在以下条件同时满足时才接受样本：

$$
|e_y|\le 0.70,\quad
|e_{\psi}|\le 0.35,\quad
|v_y|\le 1.20,\quad
|r|\le 1.20,\quad
\|\Delta \mathbf{z}\|_2\le 1.60,
$$

并且默认仅使用领航车样本，且当团队推进量 $s>22~\mathrm{m}$ 后停止自适应。其内在机理是：故障或通信失配容易首先反映在跟驰车的相对误差上，若直接把所有车辆样本都送入在线回归，适应器会把“队形误差”误识别成“动力学失配”；限制为领航车高置信样本可以显著降低这一污染通道。更新后的增量矩阵还会经过 Frobenius 范数裁剪

$$
\|\Delta \mathbf{A}_k\|_F\le 0.06,\qquad
\|\Delta \mathbf{B}_k\|_F\le 0.06,
$$

以及谱半径不超过 0.998 的稳定性投影，再以 0.04 的融合系数并回名义模型。与 baseline 直接把自适应收益理解为“模型越变越准”不同，本文更强调它的安全机理：在线自适应不是为了无限追踪所有新现象，而是为了在局部可信域内快速吸收故障、载荷变化和高曲率引起的短时预测偏差，同时通过范数裁剪和谱投影把这种修正限制在不会破坏名义稳定性的范围内。

**图3 名义模型与在线自适应模型的一步预测误差对比（占位）**  
此处插入：名义模型与启用在线双线性自适应后的预测误差箱线图，建议重点展示故障触发前后和高曲率段前后的误差变化。

# 4 故障容错与网络韧性协同 Koopman MPC 设计

## 4.1 局部 Koopman MPC 与误差加权

每辆角点车辆都基于其局部参考轨迹求解 Koopman MPC，优化目标为

$$
\min_{\{\mathbf{u}_{i,k+j}\}}
\sum_{j=0}^{N-1}
\left\|
\mathbf{x}_{i,k+j|k}-\mathbf{x}_{i,k+j|k}^{\mathrm{ref}}
\right\|_{\mathbf{Q}_{i,k}}^2
\;+\;
\left\|
\mathbf{u}_{i,k+j|k}
\right\|_{\mathbf{R}_{i,k}}^2
\;+\;
\left\|
\mathbf{x}_{i,k+N|k}-\mathbf{x}_{i,k+N|k}^{\mathrm{ref}}
\right\|_{\mathbf{Q}_{N,i,k}}^2.
$$

主实验中使用的基准权重为

$$
\mathbf{Q}_{\mathrm{base}}=\operatorname{diag}(0,3500,1200,8,1,1),
$$

$$
\mathbf{Q}_{N,\mathrm{base}}=\operatorname{diag}(0,5000,2000,12,1,1),
$$

$$
\mathbf{R}_{\mathrm{base}}=\operatorname{diag}(120,12).
$$

`tf13` 主实验采用 22 步预测时域、2 次 SQP 迭代、前馈曲率增益 0.95，以及输入平滑参数 `delta_alpha=0.74`、`ax_alpha=0.72`。相比上一版 `tf12` 主稿的更长时域与更多迭代，这里主动压缩求解规模，是为了给在线自适应、通信补偿和故障容错留出运行余量，而不是简单追求更小的名义误差。为了在误差增大时强化横向和航向纠正，本文按

$$
\mu_{e_y}=1+1.8\left(\min\left(\frac{|e_y|}{1.8},1\right)\right)^{1.1},\qquad
\mu_{e_{\psi}}=1+1.8\left(\min\left(\frac{|e_{\psi}|}{0.7},1\right)\right)^{1.1}
$$

动态放大 $e_y$ 与 $e_{\psi}$ 相关权重，并通过速率限制 0.20 与平滑系数 0.82 抑制权重突变。相应地，输入罚矩阵会按

$$
\mu_R=\operatorname{clip}\left(1-0.22(\max(\mu_{e_y},\mu_{e_{\psi}})-1),\,0.76,\,1.0\right)
$$

做轻微收缩。其机理是：baseline 的固定权重无法区分“误差很小的平滑跟踪”与“故障后必须迅速拉回姿态”的不同控制阶段；这里则通过状态权重放大和输入罚收缩，把优化器优先级动态改写为“先把横向/航向误差压住，再谈输入平顺”，因此在故障触发或高曲率区间更容易保持团队可控。

## 4.2 曲率相关 PPC 软约束

为在弯道和高曲率区间中保持更紧的误差包络，本文使用预设性能控制思想设置动态软约束：

$$
\rho_{e_y}(k)=\rho_{e_y,\infty}+(\rho_{e_y,0}-\rho_{e_y,\infty})e^{-\lambda_{e_y}k\Delta t},
$$

$$
\rho_{e_{\psi}}(k)=\rho_{e_{\psi},\infty}+(\rho_{e_{\psi},0}-\rho_{e_{\psi},\infty})e^{-\lambda_{e_{\psi}}k\Delta t},
$$

其中基准参数为

$$
\rho_{e_y,0}=0.45,\quad \rho_{e_y,\infty}=0.035,\quad \lambda_{e_y}=1.25,
$$

$$
\rho_{e_{\psi},0}=0.22,\quad \rho_{e_{\psi},\infty}=0.025,\quad \lambda_{e_{\psi}}=1.35.
$$

当曲率增大时，误差包络按

$$
\gamma_{\kappa}=1+0.45\min\left(\frac{|\kappa|}{0.08},1\right)
$$

缩放，即用更小的 $\rho_{e_y,0},\rho_{e_{\psi},0},\rho_{e_y,\infty},\rho_{e_{\psi},\infty}$ 和更大的衰减速率来约束弯道误差。其机理是：高曲率路段对团队中心姿态误差和四角点刚体映射误差更敏感，若沿用直线路段的宽松误差容忍区间，则 MPC 会把本应提前修正的误差推迟到更靠后的时刻，进而在故障或时延存在时触发更大的纠偏动作。

## 4.3 通信质量感知一致性与时延补偿

`tf13` 主实验设置 `use_comm_quality_consensus=True`、`use_delay_compensation=True`，并采用 `comm_packet_loss_base=0.00`、`comm_packet_loss_gain=0.20`、`comm_delay_steps_max=1` 的轻度负载相关链路模型。也就是说，主 DLC 实验并不是在强通信攻击场景下做极限对抗，而是在近理想链路中让通信补偿机制真正进入闭环；复杂回头弯与故障验证再进一步放大这些机制的价值。设 $i\rightarrow j$ 链路在时刻 $k$ 的离散时延为 $d_{ij,k}\in\{0,1,2,3\}$，丢包事件记为 $\chi_{ij,k}\in\{0,1\}$，则其瞬时通信质量定义为

$$
\tilde q_{ij,k}=
\begin{cases}
\exp\!\left(-d_{ij,k}/\tau\right), & \chi_{ij,k}=1,\\
0.1\exp\!\left(-d_{ij,k}/\tau\right), & \chi_{ij,k}=0,
\end{cases}
\qquad \tau=3.0.
$$

平滑后的质量矩阵更新为

$$
q_{ij,k}=\beta q_{ij,k-1}+(1-\beta)\tilde q_{ij,k},\qquad \beta=0.80.
$$

丢包率并非固定常数，而是随系统“负载”变化：

$$
p_{\mathrm{loss},k}=\operatorname{clip}\!\left(p_0+p_1\,\mathrm{load}_k,0,1\right),\qquad p_0=0.00,\; p_1=0.20.
$$

定义车辆 $i$ 的平均入向通信质量为

$$
q_{i,k}^{\mathrm{in}}=\frac{1}{3}\sum_{j\ne i}q_{ji,k},
$$

则一致性混合系数为

$$
\alpha_{i,k}=\alpha_{\min}+\left(1-q_{i,k}^{\mathrm{in}}\right)(\alpha_{\max}-\alpha_{\min}),
\qquad
\alpha_{\min}=0.10,\ \alpha_{\max}=0.70.
$$

据此构造团队加权命令

$$
\bar{\mathbf{u}}_k=\frac{\sum_{i=1}^4 w_{i,k}\mathbf{u}_{i,k}}{\sum_{i=1}^4 w_{i,k}},
\qquad
w_{i,k}=q_{i,k}^{\mathrm{in}}+10^{-3},
$$

并得到一致性投影后的车辆命令

$$
\tilde{\mathbf{u}}_{i,k}=(1-\alpha_{i,k})\mathbf{u}_{i,k}+\alpha_{i,k}\bar{\mathbf{u}}_k.
$$

若某辆车接收到的是延迟状态而非实时状态，则接收端不直接使用旧数据，而是把远端状态向前预测：

$$
\hat s_{j\rightarrow i}=s_j+v_{x,j}d_{ij,k}\Delta t,\qquad
\hat e_{y,j\rightarrow i}=e_{y,j}+v_{y,j}d_{ij,k}\Delta t,\qquad
\hat e_{\psi,j\rightarrow i}=e_{\psi,j}+r_j d_{ij,k}\Delta t.
$$

其内在机理可以概括为两点。第一，若某辆车入向通信质量下降，则其一致性混合系数 $\alpha_{i,k}$ 自动增大，该车命令会被更强地拉向团队加权均值，从而抑制“信息越差、命令越离群”的恶性循环。第二，时延补偿不是简单复制旧状态，而是把远端状态向前外推到当前时刻后再做刚体相对误差校正，因此能显著减小延迟链路造成的相位滞后。相比 AKE-baseline 缺少显式链路质量映射的团队协调，`tf13` 把通信可靠性直接写进命令融合强度，因此在故障和高负载阶段更不容易出现车间相互拉扯。

## 4.4 团队级聚合、稳定保护与进度监督

由于四辆车同时牵引同一刚性载荷，团队命令不能简单取各车 MPC 解的算术平均。`tf13` 先根据车间控制离散度构造均值-中值混合聚合器。记四辆车命令堆叠为 $\mathbf{u}_{i,k}=[\delta_{i,k},a_{x,i,k}]^{\top}$，则团队聚合命令写为

$$
\mathbf{u}_{\mathrm{team},k}=
\begin{bmatrix}
(1-\gamma_{\delta,k})\operatorname{mean}(\delta_{i,k})+\gamma_{\delta,k}\operatorname{median}(\delta_{i,k})\\
(1-\gamma_{a,k})\operatorname{mean}(a_{x,i,k})+\gamma_{a,k}\operatorname{median}(a_{x,i,k})
\end{bmatrix},
$$

其中

$$
\gamma_{\delta,k}=0.45\operatorname{clip}\!\left(\frac{\sigma_{\delta,k}-0.045}{0.045},0,1\right),\qquad
\gamma_{a,k}=0.45\operatorname{clip}\!\left(\frac{\sigma_{a,k}-0.20}{0.20},0,1\right),
$$

$\sigma_{\delta,k}$ 和 $\sigma_{a,k}$ 分别为车辆转角命令与加速度命令的标准差。其机理是：当车辆间命令高度一致时，均值能最大化团队执行效率；当某辆车因为局部误差、延迟状态或故障补偿而产生离群命令时，聚合器自动向中值偏移，从而降低异常车辆对团队级载荷力矩的放大效应。

在聚合之后，本文再叠加团队稳定保护。令团队状态与团队参考的误差为 $\mathbf{e}_k=\mathbf{x}_{c,k}-\mathbf{x}_{c,k}^{\mathrm{ref}}$，侧偏角为 $\beta_k=\arctan(v_{y,c}/\max(v_{x,c},0.5))$，则稳定保护根据

$$
\varsigma_k=\max\left(\frac{|\beta_k|}{\beta_{\lim}},\frac{|r_k|}{r_{\lim}},\frac{|e_{y,k}|}{0.75},\frac{|e_{\psi,k}|}{0.28}\right)
$$

构造团队保护权重

$$
w_{\mathrm{guard},k}=\operatorname{clip}\!\left(\frac{\varsigma_k-0.85}{0.80},0,1\right),
$$

并在跟踪型保护律与稳定型保护律之间插值。这样做的机理是：当系统仍处在安全区域时，控制器优先跟踪；当侧偏角、横摆角速度或横向姿态误差逼近限制时，保护器自动提高“稳住车体姿态”的优先级，防止刚体载荷把局部横摆放大为团队整体失稳。

进一步地，进度监督器只在横向/航向状态稳定时才允许纵向恢复加速。若团队纵向滞后量为 $l_{s,k}=s_k^{\mathrm{ref}}-s_k$，速度滞后为 $l_{v,k}=v_{x,k}^{\mathrm{ref}}-v_{x,k}$，则其恢复加速度写为

$$
a_{x,k}^{\mathrm{rec}}=
\operatorname{clip}\!\left(
k_s l_{s,k}+k_v\max(l_{v,k},0)-k_{vy}|v_{y,k}|-k_r|r_k|,
\ a_{x,\min}^{\mathrm{rec}},\ a_{x,\max}^{\mathrm{rec}}
\right).
$$

在 `tf13` 主配置中，进度恢复于 $l_{s,k}>0.08~\mathrm{m}$ 时激活，并在 $0.60~\mathrm{m}$ 滞后处达到全强度。其机理是：故障补偿和稳定保护都可能导致系统过于保守，进度监督器则只在“横向已经稳住”的前提下回收纵向推进能力，避免为了追进度而重新引入横向失稳。

## 4.5 通信退化回退与单车执行器故障容错

`tf13` 主 DLC 实验设置 `use_comm_constraint_tightening=False`、`use_comm_degraded_fallback=True`。也就是说，名义主实验中主要启用的是退化回退，而更激进的输入约束收紧保留给复杂回头弯覆盖实验。若全局通信质量下降到阈值以下，则输入命令会在名义团队命令与保守安全命令之间混合。设全局平均通信质量为

$$
q_k^{\mathrm{global}}=\frac{1}{12}\sum_{i\ne j}q_{ij,k},
$$

并定义退化评分

$$
\sigma_k=\max\left(\frac{0.45-q_k^{\mathrm{global}}}{0.45},\frac{\rho_k^{\mathrm{loss}}-0.30}{0.70}\right),\qquad
\eta_k=\operatorname{clip}(\sigma_k,0,1),
$$

则保守安全命令为

$$
\delta_k^{\mathrm{safe}}=-0.85 e_{y,c}-1.35 e_{\psi,c}-0.45 r_c,
$$

$$
a_{x,k}^{\mathrm{safe}}=\max\left(0.22\max(s_k^{\mathrm{ref}}-s_c,0)-0.10|v_{y,c}|-0.10|r_c|,\,-0.15\right),
$$

最终团队命令写为

$$
\mathbf{u}_k^{\mathrm{mix}}=(1-\eta_k)\mathbf{u}_{\mathrm{team},k}+\eta_k\mathbf{u}_k^{\mathrm{safe}}.
$$

其机理是：链路一旦显著退化，控制器不再完全相信多车分布式最优解，而是逐步退回到一个更偏稳定和保守的团队级命令，从而阻断“低质量通信 + 激进控制”共同触发的姿态发散。

`tf13` 的另一个关键修正是把单车执行器故障直接纳入主方法，而不是仅做离线鲁棒性讨论。设故障车辆为 $f$，其无故障命令为 $\mathbf{u}_{f,k}^{\mathrm{nom}}$，故障后实际可执行命令为

$$
\mathbf{u}_{f,k}^{\mathrm{fault}}=
\begin{bmatrix}
\gamma_{\delta} & 0\\
0 & \gamma_{a}
\end{bmatrix}
\mathbf{u}_{f,k}^{\mathrm{nom}},
\qquad 0<\gamma_{\delta},\gamma_a\le 1.
$$

定义故障亏损

$$
\mathbf{d}_{f,k}=\mathbf{u}_{f,k}^{\mathrm{nom}}-\mathbf{u}_{f,k}^{\mathrm{fault}},
$$

则健康车辆 $j\neq f$ 的补偿命令更新为

$$
\mathbf{u}_{j,k}^{+}
=
\mathbf{u}_{j,k}^{\mathrm{nom}}
+\operatorname{clip}\!\left(
\frac{\kappa_f}{N-1}\mathbf{d}_{f,k},
\begin{bmatrix}
-\bar d_{\delta}\\
-\bar d_{a}
\end{bmatrix},
\begin{bmatrix}
\bar d_{\delta}\\
\bar d_{a}
\end{bmatrix}
\right),
$$

其中 $\kappa_f$ 为故障补偿增益，$\bar d_{\delta},\bar d_a$ 为补偿裁剪上界。`tf13` 主实验中，第 2 辆车在 $k\ge160$ 且 $s\ge18~\mathrm{m}$ 后进入双执行器衰减故障，取 $\gamma_{\delta}=0.90$、$\gamma_a=0.88$、$\kappa_f=1.35$、$\bar d_{\delta}=0.07$、$\bar d_a=0.80$。这一步之所以能比 baseline 更强，不是因为“故障车被修好了”，而是因为四车刚性搬运本身具有团队级控制冗余：载荷所感受到的是团队等效力和等效力矩，只要健康车辆在不越界的前提下接管一部分亏损，团队级外力矩就能被重新闭合，单车能力下降就不必等价于整车队失效。

## 4.6 相对 baseline 的主方法增量与机理总结

如果把 AKE-baseline 概括为“离线 Koopman 主干 + 在线自适应 + MPC”，那么 `tf13` 的主方法增量并不是简单叠加几个补丁模块，而是沿着三条失效链路逐层补全闭环。第一条链路是预测失配：当路径曲率、载荷耦合和故障扰动共同出现时，名义 lifted 模型会把误差带入预测时域；对此，`tf13` 用更高维的稳定投影双线性 Koopman 主干和受限在线自适应来抑制误差累积。第二条链路是协同失配：即使单车预测足够好，通信质量波动和时延也会让团队命令逐步离散；对此，`tf13` 用通信质量感知一致性、时延前推预测和退化回退把链路不确定性写进控制律。第三条链路是执行失配：即使前两层都工作正常，单车执行器退化仍可能破坏团队等效力闭合；对此，`tf13` 进一步加入团队聚合、稳定保护、进度监督和故障重分配，使故障不再直接等价于任务失败。

这三条链路并不是彼此独立的。更准确地说，稳定投影 Koopman 主干负责减少“送入 MPC 的名义预测偏差”，通信补偿模块负责减少“从 MPC 输出到团队执行之间的协调偏差”，故障容错模块负责减少“从团队命令到实际载荷受力之间的执行偏差”。因此，`tf13` 相比 baseline 的提升不是某一个局部指标偶然变好，而是把“预测-协调-执行”三个串联环节中的主要失效源都做了结构化闭合。对四车刚性运输这类强耦合任务而言，只有这三层同时成立，团队中心误差、单车误差和载荷受力才会同步改善。

从审稿视角看，这也是 `tf13` 与 AKE-baseline 最本质的区别。AKE-baseline 的强项在于回答“模型失配后如何继续维持 Koopman 控制有效”；`tf13` 则进一步回答“当这种 Koopman 控制被放入一个存在通信退化、执行器故障和载荷刚性耦合的多车系统时，怎样把模型层优势真正转化为团队级任务完成能力”。因此，本文后续实验中观察到的更低横向误差、更低载荷横向力和更低连接误差，本质上都是上述三层闭环共同作用后的外在表现。

**图4 所提控制框架的信息流与模块关系图（占位）**  
此处插入：从车辆局部状态、Koopman 升维、在线自适应、通信一致性、时延补偿、团队聚合、稳定保护、进度监督、退化回退到故障重分配与团队执行的整体框图。

# 5 仿真实验设计与结果

## 5.1 比较对象与实验设置

为避免“方法版本号比较”带来的歧义，本文定义两个清晰的比较对象。

1. 原始 baseline 论文：指 Singh 等的 Adaptive Koopman Embedding 工作，其贡献是针对单体非线性系统的离线 Koopman 嵌入与在线自适应修正 [@singh2024adaptive]。
2. AKE-baseline：指本文在 A1 协同运输任务上实现的任务化 baseline，对应旧版 `tf11_A1_pre` 配置。它采用 20 维可学习观测、27 维 lifted state、宽度 96 的 `tanh` 编码器、140 轮训练、在线双线性自适应、PPC、误差自适应权重和连接一致性约束，但不启用通信质量感知一致性、时延补偿、退化回退与故障容错。

因此，AKE-baseline 与本文方法之间的差异不是“历史版本互比”，而是同一 A1 协同运输任务下的任务化 baseline 与最新版 `tf13` 主配置对比。相对于上一版按 `tf12` 撰写的中文稿，`tf13` 的核心变化不在于继续堆大名义模型，而在于把在线自适应、通信补偿与故障容错真正纳入主实验。

| 表2 AKE-baseline 与本文方法的模块对比 | AKE-baseline | 本文方法 |
| --- | --- | --- |
| 可学习观测维度 | 20 | 24 |
| lifted state 维度 | 27 | 31 |
| 编码器宽度/激活函数 | 96 / `tanh` | 128 / `gelu` |
| 训练轮数 | 140 | 180 |
| 解码矩阵 $\mathbf{C}$ | 固定选择矩阵 | 学习型 $\mathbf{C}$ |
| 稳定投影 Koopman A | 未作为主干强调 | 开启，谱半径约 0.9990 |
| 在线双线性自适应 | 开启 | 开启，18 步窗口/6 步更新/0.998 投影 |
| 动态 PPC 软约束 | 开启 | 开启 |
| 误差自适应权重 | 开启 | 开启 |
| 通信质量感知一致性 | 关闭 | 开启 |
| 时延补偿预测 | 关闭 | 开启 |
| 通信退化回退 | 关闭 | 开启 |
| 通信触发约束收紧 | 关闭 | 主 DLC 关闭，复杂回头弯覆盖实验可开启 |
| 团队稳定保护与进度监督 | 无显式团队级机制 | 开启 |
| 单车执行器故障容错重分配 | 关闭 | 开启 |
| MPC 时域 / SQP 迭代 | 30 / 2 | 22 / 2 |
| 转角 / 加速度约束 | $\pm0.12$ rad / $\pm1.20$ m/s$^2$ | $\pm0.52$ rad / $\pm4.00$ m/s$^2$ |

表2列出的是“配置差异”，但对于本文来说，更重要的是把 `tf13` 相对 AKE-baseline 的“新差距”解释为哪些能力缺口被补上，以及为什么补上后会更好。换言之，`tf13` 不是单纯“参数更大”，而是把 baseline 原本主要针对模型失配的控制骨架，扩展成了可同时应对预测误差、通信误差和执行亏损的团队级闭环。

| 表2-补充 TF13 相对 AKE-baseline 的新增差距与作用机理 | 新增差距 | 对应模块 | 内在机理 | 为什么相对 baseline 会更好 |
| --- | --- | --- | --- | --- |
| 模型表达层 | AKE-baseline 的 lifted 表达容量和稳定性约束较弱 | 24 维可学习观测、31 维 lifted state、学习型 $\mathbf{C}$、稳定投影 $\mathbf{A}$ | 更高维 lifted 空间吸收横摆、横向速度、连接柔顺和载荷耦合等难分离模式，谱投影抑制长时域滚动发散 | MPC 接收到的名义预测更稳，误差不易在时域内累积放大 |
| 在线修正层 | AKE-baseline 的在线自适应未针对四车载荷耦合和故障场景做显式可信域限制 | 18 步滑窗、6 步更新、0.97 遗忘因子、0.998 投影半径的双线性在线自适应 | 只在高置信样本上修正局部动力学，并用范数裁剪与谱投影限制更新幅度 | 遇到曲率突变和故障触发时，模型能继续纠偏，但不会因为过度自适应而破坏稳定性 |
| 通信协同层 | baseline 默认团队信息交换可靠，缺少对丢包和时延的显式反馈链 | 通信质量感知一致性、时延前推预测、退化回退 | 差链路车辆的命令被更强地拉回团队加权均值，延迟远端状态先前推再参与校正，严重退化时切回保守团队命令 | 车间命令离散与相位滞后被抑制，连接误差和载荷横向冲突力更小 |
| 执行容错层 | baseline 没有把单车执行器退化映射成团队级补偿问题 | 团队聚合、稳定保护、进度监督、故障重分配 | 故障车命令亏损被健康车辆分担，稳定保护先兜住横向/航向安全，进度监督再回收纵向推进能力 | 单车能力下降不会直接演化为团队失稳或任务中断，全路径完成率更高 |

主实验采用双移线参考路径，路径长度 60 m。当前 `tf13` 主运行对第 2 辆车注入持续故障：当 $k\ge160$ 且 $s\ge18~\mathrm{m}$ 后，同时施加转角缩放 $\gamma_{\delta}=0.90$ 和纵向加速度缩放 $\gamma_a=0.88$。实验关注以下几类指标：团队全路径完成率、求解成功率、横向/纵向跟踪误差、单车误差、连接一致性指标、载荷合力与力矩峰值、角点法向载荷范围以及故障激活诊断。

## 5.2 离线数据、动力学学习与在线纠偏设置

最新版 `tf13` 与 AKE-baseline 共享同一 A1 任务和相近的数据生成流程，但不再共享同一名义 Koopman 模型。AKE-baseline 使用 20 维可学习观测与 27 维 lifted state；最新版 `tf13` 使用 24 维可学习观测与 31 维 lifted state，主运行报告 bilinear fit RMSE 为 $5.4932\times10^{-3}$，样本数为 805824。因此，后续闭环差异应解释为“增强 Koopman 主干 + 在线自适应 + 通信/故障协同控制”的综合效果，而不是数据集差异。

从机理上看，`tf13` 在离线学习之后又增加了三层闭环纠偏。第一，在线双线性自适应利用 18 步滑窗与 6 步更新周期，吸收故障起始和高曲率段的局部模型偏差。第二，通信一致性和时延补偿抑制车间相对误差被链路时延放大。第三，故障重分配把单车命令亏损重新映射给健康车辆，使名义 Koopman 模型学到的团队级动力学仍然可被近似维持。换言之，离线模型负责给出“可预测骨架”，而 `tf13` 的闭环附加模块负责让这个骨架在故障和不一致信息下仍然不散架。

本节建议至少展示以下三类图，以把 method 中的离线学习部分和实验部分完全对齐。

**图5 离线训练集与验证集的一步 lifted 预测误差分布（占位）**  
此处插入：名义模型在训练集/验证集上的 lifted prediction error 直方图或箱线图。

**图6 名义模型与在线自适应模型的一步状态预测误差对比（占位）**  
此处插入：故障触发前后以及高曲率区间内 $e_y,e_{\psi},v_x,v_y,r$ 的一步预测误差对比图。

**图7 角点变化子集覆盖与工况覆盖统计图（占位）**  
此处插入：1车、2车、3车、4车变化比例，以及 5 组速度/输入配置的样本占比图。

## 5.3 团队闭环性能与 baseline 对比

表3给出 A1 主任务的闭环主指标。需要强调的是，这里比较的不是“TF13 对历史版本”，而是“本文方法对 task-aligned Adaptive Koopman baseline”。

| 表3 A1 主任务闭环结果对比 | AKE-baseline | 本文方法 | 变化 |
| --- | ---: | ---: | ---: |
| 全路径完成率 | 100.0% | 100.0% | 0 |
| 求解成功率 | 100.0% | 100.0% | 0 |
| 横向 RMSE e_y / m | 0.2075 | 0.0354 | -82.9% |
| 纵向 RMSE e_s / m | 2.8703 | 0.4813 | -83.2% |
| 失败次数 | 1 | 0 | 改善 |
| 平均单步耗时 / s | 0.2661 | 0.2389 | -10.2% |

结果表明，`tf13` 在横向和纵向跟踪精度上仍显著优于 AKE-baseline，同时把失败次数从 1 次降至 0 次。与 baseline 相比，这组收益不能简单归因于“某个模块单独起作用”，而是多层机制叠加的结果：更强的 Koopman lifted 表达降低名义预测偏差，在线自适应在故障与曲率变化下继续修正局部模型，通信一致性与时延补偿抑制车间命令离散，故障重分配则把单车执行器亏损吸收到团队冗余中。

相对于本线程上一版按 `tf12` 撰写的主稿，`tf13` 的“新差距”也应如实写出。上一版 `tf12` 在无故障主实验中取得 $\mathrm{RMSE}(e_y)=0.0342~\mathrm{m}$、$\mathrm{RMSE}(e_s)=0.2644~\mathrm{m}$，而当前 `tf13` 在真正启用在线自适应、通信补偿和持续故障注入后，横向 RMSE 仅小幅上升到 0.0354 m，但纵向 RMSE 升至 0.4813 m；与此同时，失败次数由 5 次降到 0 次，求解成功率回到 100%，平均单步耗时由 0.7633 s 降至 0.2389 s。这说明 `tf13` 的改动不是“白拿更高精度”，而是在激活更多鲁棒机制后，用可接受的纵向精度代价换来了更好的任务完整性、零失败和更接近在线运行的求解效率。

**图8 团队中心轨迹与参考路径对比（占位）**  
此处插入：AKE-baseline 与本文方法的团队中心轨迹叠加图。

**图9 团队位置跟踪误差对比（占位）**  
此处插入：团队中心在全路径上的二维位置误差或累计位置误差曲线。

**图10 横向误差对比（占位）**  
此处插入：AKE-baseline 与本文方法的 $e_y$ 随时间或随路径进度变化曲线。

**图11 纵向误差对比（占位）**  
此处插入：AKE-baseline 与本文方法的 $e_s$ 随时间或随路径进度变化曲线。

**图12 通信质量、平均时延与故障激活轨迹（占位）**  
此处插入：$q^{\mathrm{global}}$、mean delay steps、loss ratio 以及 fault active/deficit norm 的时间历程图。

## 5.4 单车误差、连接一致性与载荷受力分析

为了说明收益并非只来自“团队平均指标变好”，表4给出四辆车各自的误差对比。

| 表4 单车误差结果 | 指标 | 车1 | 车2 | 车3 | 车4 |
| --- | --- | ---: | ---: | ---: | ---: |
| AKE-baseline | RMSE(e_y) / m | 0.2680 | 0.2669 | 0.1484 | 0.1468 |
| 本文方法 | RMSE(e_y) / m | 0.0444 | 0.0475 | 0.0234 | 0.0264 |
| AKE-baseline | RMSE(e_s) / m | 2.8869 | 2.8620 | 2.8794 | 2.8528 |
| 本文方法 | RMSE(e_s) / m | 0.4810 | 0.4810 | 0.4804 | 0.4830 |

可以看到，本文方法在四辆车上的横向和纵向误差都显著降低，而且领航侧与跟随侧都受益。这说明 `tf13` 的收益不是“把某一辆车调得特别好”，而是通过团队级聚合、时延补偿和故障重分配同时改善了四个角点车辆的局部误差传播。

| 表5 载荷受力与连接一致性对比 | AKE-baseline | 本文方法 | 变化 |
| --- | ---: | ---: | ---: |
| 载荷纵向峰值力 / N | 1103.03 | 984.59 | -10.7% |
| 载荷横向峰值力 / N | 1305.56 | 496.62 | -61.9% |
| 载荷偏航力矩峰值 / N·m | 1382.06 | 410.30 | -70.3% |
| 角点法向载荷最小值 / N | 4468.24 | 4654.54 | 改善 |
| 角点法向载荷最大值 / N | 5341.76 | 5155.46 | 改善 |
| 角点载荷波动范围 / N | 873.51 | 500.91 | -42.7% |
| $\max\lvert\Delta s_i\rvert$ / m | 0.02774 | 0.00354 | -87.2% |
| $\max\lvert\Delta e_{y,i}\rvert$ / m | 0.01245 | 0.01128 | -9.4% |
| $\max\lvert\Delta\psi_i\rvert$ / rad | 0.01021 | 0.00925 | -9.5% |
| 连接相对 RMS 均值 | 0.00510 | 0.00401 | -21.4% |

这些结果和各创新模块的作用机理是一一对应的。

1. 横向峰值力和偏航力矩显著下降，对应的是通信质量感知一致性、时延补偿和团队聚合共同降低了离群转角命令，减少了四车对载荷施加的相互冲突侧向力矩。
2. 四辆车纵向误差整体下降到约 0.48 m，对应的是在线自适应和进度监督在故障触发后继续修正局部模型偏差，并在横向稳定前提下回收纵向推进能力。
3. 连接指标全面优于 baseline，对应的是刚体几何映射、柔性连接约束和故障重分配共同抑制了“某一故障车独自掉队”对团队相对构型的破坏。

**图13 单车横向误差对比（占位）**  
此处插入：四辆车各自的 $e_y$ 曲线，建议 2×2 子图。

**图14 单车纵向误差对比（占位）**  
此处插入：四辆车各自的 $e_s$ 曲线，建议 2×2 子图。

**图15 货物纵向力、横向力与偏航力矩对比（占位）**  
此处插入：$F_{x,p},F_{y,p},M_{z,p}$ 三条曲线的 baseline vs 本文方法对比图。

**图16 四角点法向载荷对比（占位）**  
此处插入：$F_{\mathrm{FL}},F_{\mathrm{FR}},F_{\mathrm{RL}},F_{\mathrm{RR}}$ 的时间历程图。

**图17 连接误差 $\Delta s,\Delta e_y,\Delta\psi$ 对比（占位）**  
此处插入：连接一致性误差峰值与时间历程图。

## 5.5 与原始 baseline 论文的能力定位对比

为了把“task-aligned AKE-baseline”与“原始 baseline 论文”区分清楚，表6给出两者与本文方法在问题设定上的对应关系。

| 表6 与原始 Adaptive Koopman baseline 的能力定位对比 | 原始 baseline 论文 [@singh2024adaptive] | 本文方法 |
| --- | --- | --- |
| 研究对象 | 耦合摆、3R 机械臂、平面四旋翼 | 四车刚性载荷协同运输 |
| Koopman 模型 | 离线名义 Koopman 嵌入 + 在线自适应修正 | 稳定投影双线性 Koopman，24 维可学习观测、31 维 lifted state、学习型 $\mathbf{C}$，并配合在线双线性自适应 |
| 已验证鲁棒性 | 参数变化、测量噪声、外部扰动 | 参数变化、通信质量波动、时延补偿、单车执行器退化、复杂回头弯路径 |
| 通信建模 | 未涉及 | 显式质量矩阵、时延预测、一致性投影、退化回退 |
| 多车协同 | 未涉及 | 显式建模四车角点映射、团队聚合与连接一致性 |
| 故障容错 | 未涉及 | 显式建模单车转角/加速度双执行器退化与团队重分配 |
| 载荷受力评价 | 未涉及 | 显式评估 Fx、Fy、Mz 与角点法向载荷 |
| 已报道代表性效果 | 耦合摆误差改善约 87%--93%；3R 机械臂 RMSE 从 1.27 rad 降至 0.189 rad | A1 任务横向 RMSE 下降 82.9%，纵向 RMSE 下降 83.2%，横向峰值力下降 61.9%，偏航力矩下降 70.3% |

这张表的意义不在于证明“本文效果一定大于原始 baseline 论文”，而在于说明两者解决的是不同层级的问题。原始 baseline 解决的是“模型失配下如何保持 Koopman 控制有效”；本文当前版本解决的是“当 Koopman 控制内核被放入四车载荷搬运任务时，如何通过更强的 lifted 表达、在线自适应、通信补偿和故障重分配，在链路与执行器都不完美的条件下仍保持团队级可控”。

## 5.6 复杂路径与故障验证

除了主 DLC 任务外，最新版 `tf13` 还引入了右角回头弯路径库与故障验证脚本。与上一版 `tf12` 中文稿中“仅预留图位”的状态不同，这一部分现在已经有实际数值结果。本轮图件来自 `figures_reasonable_comm_ablation_2026-05-07`，其中 `no_comm` 已修正为真正关闭通信质量一致性、时延补偿、约束收紧与退化 fallback，同时主方法通信保护参数经过重新调轻，因此比 2026-05-06 图包更适合作为正文证据。

| 表7 TF13 复杂路径故障验证摘要 | 全路径完成 | 横向 RMSE / m | 纵向 RMSE / m | 平均单步耗时 / s | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| `tf13_ra_verify` | 100.0% | 0.1318 | 0.8442 | 0.2797 | 右角回头弯，持续故障 |
| `tf13_ra_verify_feasible` | 100.0% | 0.1180 | 0.6980 | 0.2672 | 右角回头弯，持续故障 |
| `tf13_ra_verify_precision` | 100.0% | 0.1258 | 0.8417 | 0.5288 | 右角回头弯，更高精度权衡 |

进一步地，在 `tf12_tf13_post_patch_metrics.json` 的 silent post-patch hairpin 统计中，`tf13` 的故障激活比例达到 93.7%，故障亏损峰值范数约为 0.237。这说明故障并不是一两个时刻的点状扰动，而是贯穿大部分复杂路径跟踪过程的持续能力退化。即便如此，控制器仍能保持 `full_path=true`，这正是通信补偿、故障重分配和进度监督协同起效的直接证据。

若进一步对照 `tf12_tf13_autotune_summary.json` 中同一 single-hairpin family 的结果，可以看到 `tf12` 在无故障情况下的 best-current hairpin 指标约为 $\mathrm{RMSE}(e_y)=0.9441~\mathrm{m}$、$\mathrm{RMSE}(e_s)=4.9538~\mathrm{m}$，而 `tf13` 在带中等故障的对应配置下仍维持 $\mathrm{RMSE}(e_y)=0.9415~\mathrm{m}$、$\mathrm{RMSE}(e_s)=4.9703~\mathrm{m}$ 且 `full_path=true`。这说明 fault-tolerant 模块并没有把原有控制骨架“破坏掉”，而是在保持同量级复杂路径能力的基础上，把“无故障能跑”扩展为“有故障仍能跑”。

**图18 回头弯混合扰动工况下的团队中心轨迹对比。**  
参考路径、AKE-baseline、去通信保护、去故障重分配与 `TF13` 主方法的团队中心轨迹如图18所示。在故障和通信噪声共同存在时，`TF13` 仍能沿参考回头弯完整推进，并保持比两类消融版本更平滑的外侧转弯轨迹。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_team_center_traj_compare.png){ width=95% }

**图19 回头弯混合扰动工况下的系统横纵向误差对比。**  
图19给出了同一 `mixed_fault_and_noise` 场景下的系统级 $e_y$ 和 $e_s$。与 AKE-baseline 相比，`TF13` 主方法在故障阶段显著压低横向偏差；在均方误差统计上，主方法横向 RMSE 为 0.07683 m，低于 AKE-baseline 的 0.18267 m、去通信保护的 0.07845 m 与去故障重分配的 0.10415 m。纵向误差方面，主方法维持在 5.41483 m，显著低于 AKE-baseline 的 10.79265 m，并接近去故障重分配版本的 5.27793 m，但同时保留了更低横向峰值误差与更完整的容错链路。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_system_lat_long_error_compare.png){ width=95% }

**图20 通信噪声剂量-响应汇总图。**  
为了避免只依赖单一回头弯样例，图20进一步汇总了 `none`、`medium` 和 `heavy` 三档通信噪声下的横向 RMSE、纵向 RMSE、完成率与链路丢包指标。可以看到，随着通信噪声增强，AKE-baseline 的纵向误差保持在约 10 m 量级，而 `TF13` 在中等与强通信噪声下分别保持约 5.446 m 和 5.304 m 的纵向 RMSE，并在三档噪声下保持接近 1 的完成率。用于离线样本与闭环相图覆盖对比的 `raw_phase_summary` 工具仍保留在 notebook 中，但当前补图包未提供适合直接写入主文的导出版本，因此本轮中文稿优先回填更直接支撑网络韧性结论的 stress suite 图件。

![](figures_reasonable_comm_ablation_2026-05-07/关键汇总/N07_comm_noise_dose_response.png){ width=95% }

## 5.7 消融实验与模块贡献验证

仅给出“full model 优于 baseline”的总结果还不足以支撑一区 top 审稿中对创新归因的要求，因此本文进一步设计模块化消融实验，验证每一个新增环节是否都在其对应的物理链路上产生了可解释收益。消融的核心原则是：除被移除模块外，其余数据集、参考路径、故障注入时刻、MPC 代价权重和求解预算保持不变，从而把性能差异尽量归因于单一功能缺失，而不是训练数据或调参偶然性。

考虑到 `tf13` 的创新是分层叠加的，本文建议采用“两级消融”结构。第一级用于回答“增强 Koopman 主干本身是否值得”；第二级用于回答“在增强主干已经存在的前提下，在线自适应、通信补偿、稳定保护和故障重分配各自贡献了什么”。这样可以避免把 backbone 改动与闭环附加模块混在一起解释。

**表8 消融实验矩阵设计（正文版）。**  
为避免宽表在 Word 中压缩失真，本稿将消融矩阵按 case 分项列出。

1. `Backbone-0 / AKE-baseline`：20 维观测、27 维 lifted state、固定 $\mathbf{C}$，作为任务化 baseline。
2. `Backbone-1 / TF13-backbone-only`：24 维观测、31 维 lifted state、学习型 $\mathbf{C}$ 和稳定投影 $\mathbf{A}$；关闭在线自适应、通信补偿、稳定保护和故障重分配，用于验证增强 Koopman 主干本身的名义收益。
3. `Full-0 / TF13-full`：完整主方法，作为所有消融的参照。
4. `Abl-1 / TF13-w/o-adapt`：设置 `use_online_model_adaptation=False`，用于验证在线双线性自适应对故障与高曲率段预测修正的贡献。
5. `Abl-2 / TF13-w/o-comm`：设置 `use_comm_quality_consensus=False`、`use_delay_compensation=False`、`use_comm_degraded_fallback=False`，用于验证网络韧性模块对连接一致性和载荷侧向冲突的贡献。
6. `Abl-3 / TF13-w/o-guard`：设置 `use_team_stability_guard=False`、`use_progress_supervisor=False`，用于验证团队稳定保护与进度监督对零失败和姿态恢复的贡献。
7. `Abl-4 / TF13-w/o-fault-redist`：设置 `fault_tolerant_redistribution=False`，用于验证故障重分配对持续故障场景任务完成率的贡献。
8. `Abl-5 / TF13-w/o-conn`：设置 `use_connection_compliance=False`、`use_rigid_coord_correction=False`，用于验证连接柔顺与刚体相对误差校正对构型保持的贡献。

上述矩阵与 `tf13_pre.ipynb` / `tf12_runtime.py` 中已有的模块开关是一一对应的，因此它不是“论文层面的理想化设想”，而是可以直接在现有工程中复现的实验计划。建议每个 case 至少在主 DLC 任务和右角回头弯持续故障任务上各运行一组，以分别覆盖名义路径跟踪能力与复杂故障工况能力。

为了让消融结论真正对应到模块功能，指标不应只看单一 RMSE，而应按照“任务完成、团队协调、载荷安全、故障恢复”四类证据同时报告。建议的核心指标包括：全路径完成率、求解成功率、横向/纵向 RMSE、单车误差、$\max|\Delta s_i|$、$\max|\Delta e_{y,i}|$、$\max|\Delta\psi_i|$、连接相对 RMS 均值、载荷 $F_x/F_y/M_z$ 峰值、角点法向载荷波动范围、故障激活比例以及亏损峰值范数。只有当一个模块被移除后，其对应物理量出现方向一致的恶化，才能说明该模块的贡献是可信的。

从机理上看，各消融 case 的预期现象也应该是明确的。去掉在线自适应后，误差首先应在故障触发点和高曲率区间放大，说明模型修正层失效；去掉通信一致性与时延补偿后，连接误差、横向峰值力和偏航力矩应首先恶化，说明协调层失效；去掉稳定保护与进度监督后，系统可能在个别区间出现更激进但更不稳的纵向推进，失败次数和姿态峰值更容易增加；去掉故障重分配后，故障车局部亏损会直接传递为团队推进缺口与路径完成能力下降；去掉连接柔顺与刚体校正后，四车角点相对位形误差和载荷法向载荷波动更可能变大。这样的“指标恶化方向”与模块物理作用之间存在一一映射关系，正是审稿人最关心的证据形式。

**表9 消融实验结果汇总（待回填字段）。**  
后续真实回填时，每个 case 至少应报告全路径完成率、求解成功率、横向 RMSE、纵向 RMSE、$\max|\Delta s_i|$、$F_{y,p}^{\max}$、$M_{z,p}^{\max}$ 和失败次数。本轮图包已经能回填 `TF13-full`、`TF13-w/o-comm` 与 `TF13-w/o-fault-redist` 的 mixed disturbance 结果，但 `TF13-w/o-adapt`、`TF13-w/o-guard` 与 `TF13-w/o-conn` 仍需单独运行。

**表10 消融模块与关键受影响物理量映射（正文版）。**  
各模块的贡献不应只用总 RMSE 描述，而应落到它最直接影响的物理量上。

1. 在线双线性自适应：首要观察故障后 $e_s/e_y$ 与一步预测误差，次要观察求解成功率和单车误差；它支撑“模型修正层能吸收局部时变失配”的论点。
2. 通信质量感知一致性、时延补偿和退化回退：首要观察 $\Delta s,\Delta e_y,\Delta\psi$ 与 $F_{y,p},M_{z,p}$，次要观察全路径完成率和单车横摆相关误差；它支撑“网络韧性层能抑制链路退化导致的协调发散”的论点。
3. 团队稳定保护与进度监督：首要观察失败次数、姿态峰值和纵向恢复时间，次要观察纵向 RMSE 与单步耗时；它支撑“安全层能在不稳定边界前切换优先级，并在稳定后恢复推进”的论点。
4. 故障重分配：首要观察 full path、故障后纵向落后量和故障车局部误差，次要观察连接 RMS 与载荷力矩峰值；它支撑“执行容错层把单车亏损转化为团队级冗余调配”的论点。
5. 连接柔顺与刚体校正：首要观察角点相对误差和法向载荷波动范围，次要观察团队中心 RMSE 与横向峰值力；它支撑“几何一致性层能抑制局部构型破坏向载荷受力扩散”的论点。

**图21 混合扰动消融热力图。**  
图21给出了 `AKE-baseline`、`w/o-comm`、`w/o-fault-redist` 与 `TF13-full` 在 mixed disturbance 场景下的归一化指标热力图。该图有两个价值：第一，它直观表明 `TF13` 并不是在所有指标上都单调最优，而是在横纵向 RMSE、最大纵向落后量与任务完成性之间取得更均衡的折中；第二，它说明通信保护和故障重分配分别沿不同物理链路起作用，不能用单一指标替代整体评估。

![](figures_reasonable_comm_ablation_2026-05-07/关键汇总/N08_mixed_disturbance_ablation_heatmap.png){ width=95% }

**图22 通信保护能力消融的系统级横纵向误差对比。**  
图22聚焦通信保护模块本身，在相同回头弯、强通信噪声和故障阶段下比较 AKE-baseline、去通信保护与 `TF13` 主方法。修正版图包中，去通信保护版本的横向 RMSE 为 0.08275 m、纵向 RMSE 为 9.15472 m，而主方法分别降低到 0.07459 m 和 5.82545 m。这说明通信质量一致性、时延补偿和退化 fallback 并非只改变曲线平滑性，而是直接减少了链路退化下的横向协调震荡与纵向推进滞后。

![](figures_reasonable_comm_ablation_2026-05-07/通信保护消融/tf13_comm_protection_ablation_system_lat_long_error_compare.png){ width=95% }

**图23 混合扰动故障阶段局部放大。**  
图23进一步在故障阶段给出局部时序放大图。上半部分比较纵向进度误差，下半部分比较横向误差。可以看到，AKE-baseline 在故障窗口内出现明显纵向滞后和横向偏移；去通信保护版本虽能保持一定推进能力，但横向误差更容易产生振荡；去故障重分配版本则在局部推进回补上更被动。`TF13` 主方法通过通信保护和故障重分配的共同作用，在故障窗口内形成更均衡的横纵向恢复。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_fault_window_zoom.png){ width=95% }

**图24 混合扰动工况下的通信时延、丢包与故障诊断时间线。**  
图24用于说明图19--图23中的性能差异确实发生在通信退化和执行器故障共同存在的窗口内，而不是来自无扰动区间的偶然误差差异。该图应与故障阴影区、通信 delay steps、loss ratio、fault active ratio 和 fault deficit norm 联合阅读：当链路质量下降且故障亏损非零时，主方法仍能维持较小的系统误差，这才构成网络韧性控制的有效证据。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_comm_delay_fault_timeline.png){ width=95% }

**图25 混合扰动工况下的连接一致性误差对比。**  
图25给出了连接相对误差随时间的变化，用于补足仅靠团队中心误差无法证明“载荷协同运输安全”的问题。若通信保护或故障重分配失效，单车局部相位滞后会首先表现为连接误差和构型一致性恶化；因此该图直接支撑本文关于刚体载荷协同约束、通信一致性和故障重分配协同作用的论点。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_connection_error_compare.png){ width=95% }

**图26 混合扰动工况下的载荷受力与偏航力矩对比。**  
图26给出载荷纵向力、横向力与偏航力矩的时间历程，用于回答“跟踪误差降低是否会以更大载荷冲击为代价”。从机理上看，若通信保护仅靠激进修正换取路径误差降低，载荷 $F_y$ 和 $M_z$ 往往会出现更高峰值；而本文希望证明的是，`TF13` 通过协调层和容错层减少车间相互冲突输入，使跟踪改善与载荷受力改善具有一致方向。

![](figures_reasonable_comm_ablation_2026-05-07/混合扰动消融/tf13_mixed_fault_and_noise_payload_force_moment_compare.png){ width=95% }

加入这一板块后，实验部分就不再只是“本文方法优于 baseline”的静态比较，而是进一步回答“每个创新点分别改善了哪条失效链路，以及如果去掉它会首先坏在哪里”。这对于支撑本文的机理论证、提升创新点可信度和满足高水平期刊审稿预期都是必要的。

# 6 结论

本文围绕四车刚性载荷协同运输任务，构建了一套从系统建模、离线数据生成、稳定投影双线性 Koopman 升维、在线双线性自适应、通信质量感知一致性、时延补偿、退化回退到单车执行器故障容错重分配的完整控制框架。最新版 `tf13_pre.ipynb` 保留了 24 维可学习观测、31 维 lifted state、宽度 128 的 `gelu` 编码器、学习型解码矩阵与谱半径稳定投影，并把上一版中文稿中尚未启用的网络/故障模块真正纳入了主实验。

与 task-aligned AKE-baseline 相比，当前 `tf13` 主运行在保持 100% 全路径完成率和 100% 求解成功率的同时，将团队横向 RMSE 降低 82.9%，纵向 RMSE 降低 83.2%，载荷横向峰值力降低 61.9%，偏航力矩降低 70.3%。更重要的是，相对于本线程上一版按 `tf12` 撰写的主稿，`tf13` 虽然在持续故障注入下牺牲了部分纵向名义精度，但换来了零失败、更高求解成功率、更低平均步耗时，以及“复杂路径下带故障仍可完成任务”的真实能力提升。这说明本文最核心的增量不再只是更强的名义 Koopman 主干，而是把模型、通信和执行器三条脆弱链路同时纳入一个可解释的协同控制闭环。

下一步工作应至少沿三条路线推进。第一，补齐本稿预留的所有图件，并将 5.7 节给出的消融矩阵全部回填为真实统计结果。第二，在更多随机种子、不同故障强度、不同丢包率与时延等级下扩展统计置信区间，证明所提收益并非特定场景偶然现象。第三，继续优化故障场景下的纵向精度、连接误差权重和实时求解效率，并补充稳定性证明，使该方法更接近一区 top 期刊对完整性、可解释性和可信度的要求。
