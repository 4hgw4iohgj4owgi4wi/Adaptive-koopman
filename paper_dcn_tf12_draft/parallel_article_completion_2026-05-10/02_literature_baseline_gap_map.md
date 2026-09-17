# Worker B: Literature and Baseline Gap Map

## 0. Scope and Source Boundary

本文件只服务于 DCN 稿件 `Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC` 的文献支撑、baseline 差距写法和公平比较边界。

已读取输入：

- `00_task_tree.md`
- baseline PDF: `D:\LEARNING\ZNN\ZNN\+ Adaptive Koopman Embedding for Robust Control of Complex.pdf`

合规边界：

- 不使用 SciDown 或任何非合规下载路径。
- 本轮不实际下载新文献。
- 后续补文献时只记录“应检索类别”和“应记录字段”，优先使用出版社开放页、arXiv、作者主页、机构库、学校图书馆/VPN 等合法来源。

baseline 的可用定位：

- baseline 题名为 `Adaptive Koopman Embedding for Robust Control of Complex Nonlinear Dynamical Systems`。
- baseline 的主要机制是：离线 autoencoder 学习 nominal linear/bilinear Koopman embedding，再用在线 adaptive neural network 根据 lifted-state prediction error 修正 Koopman 矩阵 `A/B`，并与 MPC/NMPC 结合。
- baseline 的主要验证对象是 coupled pendulums、3R serial manipulator、planar quadrotor 等通用非线性系统或机器人系统。
- baseline 的鲁棒性扰动包括参数变化、测量噪声、输入扰动和风场扰动。
- baseline 未把问题设定为多车协同运输，也未把通信时延、丢包、拓扑退化、分布式一致性、故障隔离、控制重分配和安全降级作为主线。
- 返工新增约束：DCN 稿件不能只用控制类文献支撑 network-resilient 叙事，必须补入 V2X/CAV/CACC、wireless multi-robot control、QoS-aware control、communication-control co-design、asynchronous/timestamped exchange、bursty loss/jitter 和 resilient consensus/DMPC 等 DCN-native 文献线。

## 1. Literature Support Tree by Module

### 1.1 Koopman / Vehicle Control

文献树：

- Koopman operator foundations: Koopman operator, DMD, EDMD, DMDc, SINDYc, Koopman eigenfunction, finite-dimensional lifting approximation。
- Deep Koopman learning: autoencoder Koopman, dictionary learning, invertible/variational Koopman, control-aware Koopman embedding。
- Bilinear Koopman for control-affine systems: bilinear lifted dynamics, Kronecker product control term, compatibility with MPC or SQP-based control。
- Robust/adaptive Koopman control: online correction, adaptive Koopman, robust tube Koopman MPC, data-efficient Koopman model refinement。
- Koopman for vehicles and robots: quadrotor, ground vehicle, nonholonomic vehicle, manipulator, soft robot, cooperative robotic platforms。
- Koopman-MPC interface: linear Koopman MPC, bilinear Koopman MPC, NMPC with learned lifted model, constraint handling and computation cost。

应检索类别：

- `Koopman MPC robotic systems 2023 2024 2025 2026`
- `adaptive Koopman control online learning uncertainty`
- `bilinear Koopman control-affine robot MPC`
- `Koopman model predictive control autonomous vehicle ground robot`
- `robust tube MPC Koopman operator`
- `control-aware Koopman embedding`

应记录字段：

| 字段 | 记录要求 |
|---|---|
| Koopman 表示 | linear / bilinear / nonlinear latent / eigenfunction / autoencoder |
| 控制对象 | ground vehicle / quadrotor / manipulator / cooperative robot / generic nonlinear system |
| 控制器 | MPC / NMPC / tube MPC / LQR / CLF-CBF / other |
| 在线适应 | 是否在线修正模型；修正 lifting 还是 `A/B`；是否需要重新训练 |
| 鲁棒对象 | 参数变化、噪声、外扰、未建模动态、环境变化 |
| 约束 | 状态/输入/安全/碰撞/载荷/力约束 |
| 证明 | 稳定性、递归可行性、ISS/UUB、仅仿真 |
| 实验 | 仿真/实机；轨迹类型；误差指标；计算时间 |
| 与本文关系 | 可作 Koopman module 支撑、baseline close prior、或 gap reference |

差距写法：

- 已有 Koopman 控制工作能把非线性车辆或机器人动力学提升到线性/双线性空间，并与 MPC 结合以改善跟踪和约束处理。
- 但多数工作聚焦单体系统或可靠通信条件下的局部控制，不把多车载荷耦合、通信退化和协同一致性控制同时纳入 Koopman-MPC 闭环。
- 本文补充：面向协同运输的 bilinear Koopman learned model，并把 lifted dynamics 嵌入 delay-compensated consensus MPC，使学习模型服务于网络退化下的多车协同控制。
- 放置位置：Introduction 的 Koopman learning 段、Method 的 Koopman model 段、Experiments 的 model prediction / tracking baseline 段。

### 1.2 Cooperative Transport

文献树：

- Multi-robot cooperative payload transport: 多机器人共同搬运刚体或柔性载荷、载荷位姿跟踪、载荷力/力矩分配。
- Distributed cooperative manipulation: leader-follower、formation、consensus、virtual structure、distributed force control。
- Ground vehicle cooperative transport: differential-drive / Ackermann / omnidirectional vehicle，多车队形与载荷耦合。
- Payload dynamics and load sharing: 车辆-载荷耦合建模、接触/绳索/刚性连接、内力抑制、力平滑。
- Safety-aware cooperative transport: 碰撞、队形保持、载荷姿态边界、驱动力/力矩约束。

应检索类别：

- `multi robot cooperative transport payload control recent`
- `distributed cooperative manipulation mobile robots payload`
- `cooperative transportation ground robots load sharing MPC`
- `multi vehicle payload transport consensus control`
- `formation control cooperative payload transport communication delay`

应记录字段：

| 字段 | 记录要求 |
|---|---|
| 运输对象 | rigid payload / flexible payload / object manipulation / towing |
| 机器人类型 | ground vehicles / manipulators / aerial robots / heterogeneous team |
| 耦合方式 | rigid link / cable / contact force / virtual structure |
| 控制结构 | centralized / distributed / leader-follower / consensus / MPC |
| 通信假设 | all-to-all / graph topology / delay / packet loss / reliable channel |
| 动力学知识 | full model / uncertain model / learned model / adaptive model |
| 载荷指标 | payload pose error、yaw error、force smoothness、load sharing、constraint violation |
| 安全指标 | collision distance、force/torque bounds、fallback mode、failure recovery |

差距写法：

- 已有协同运输工作能处理多机器人队形、载荷跟踪和力分配。
- 但不少方法依赖已知动力学或可靠通信，学习型动力学建模、通信退化补偿和载荷安全约束之间缺少统一闭环。
- 本文补充：用 Koopman 表示吸收车辆-载荷非线性耦合，并在通信时延/丢包下通过 consensus MPC 保持载荷轨迹、队形一致性和约束满足。
- 放置位置：Introduction 的 cooperative transport 段、Method 的 vehicle-load model / consensus error 段、Experiments 的 cooperative transport scenarios 段。

### 1.3 MPC / DMPC

文献树：

- Model Predictive Control for nonlinear robots: nonlinear MPC、linearized MPC、learning-assisted MPC。
- Distributed MPC for multi-agent systems: local optimization、neighbor coupling、consensus constraints、terminal ingredients。
- Consensus MPC: leader trajectory tracking、formation consensus、graph Laplacian error、distributed reference propagation。
- Robust MPC and tube MPC: bounded disturbances、model mismatch、constraint tightening、recursive feasibility。
- Delay-compensated MPC: input delay、state delay、communication delay、prediction buffer、timestamped neighbor states。
- Learning-based MPC: Koopman-MPC、Gaussian process MPC、neural dynamics MPC、adaptive MPC。

应检索类别：

- `distributed MPC consensus multi-agent systems communication delay`
- `delay compensated MPC networked control systems packet loss`
- `robust distributed MPC cooperative robots constraints`
- `learning based MPC multi robot transport`
- `Koopman distributed MPC multi agent`

应记录字段：

| 字段 | 记录要求 |
|---|---|
| 架构 | centralized MPC / DMPC / consensus MPC / hierarchical MPC |
| 预测模型 | physics / learned / Koopman / linearized / hybrid |
| 通信处理 | delay compensation、dropout handling、topology switching、event-triggered |
| 约束处理 | state/input/safety/force constraints；soft or hard |
| 可行性 | recursive feasibility 是否证明；是否有 terminal set/cost |
| 稳定性 | Lyapunov / ISS / UUB / empirical only |
| 计算性 | solver、horizon、sampling time、real-time feasibility |
| 对比对象 | baseline controller、ablation without delay compensation、centralized oracle |

差距写法：

- 已有 MPC/DMPC 工作提供了多智能体约束优化、分布式决策和时延补偿工具。
- 但传统 DMPC 多依赖显式模型或线性化模型，难以直接覆盖复杂车辆-载荷耦合；学习型 MPC 又常弱化通信退化、分布式一致性和安全闭环。
- 本文补充：将 bilinear Koopman lifted model 与 delay-compensated consensus MPC 结合，使数据驱动模型、网络状态和约束优化成为同一控制问题的一部分。
- 放置位置：Introduction 的 MPC/DMPC 段、Method 的 MPC formulation 段、Experiments 的 delay/dropout ablation 段。

### 1.4 Communication Degradation / Network Resilience

文献树：

- Networked control systems: time-varying delay、packet dropout、jitter、sampled-data control。
- V2X / CAV / CACC communication degradation: C-V2X / DSRC / 5G / IEEE 802.11p 场景下的车队协同、协同自适应巡航、队列稳定性、邻车状态广播延迟、丢包和通信半径变化。
- Wireless multi-robot control: 多机器人在无线链路、带宽受限、链路中断、RSSI/SINR 变化和边缘网络下的控制性能退化。
- QoS-aware control: latency、jitter、packet delivery ratio、age of information、channel quality、network load 对控制权重、预测步长、约束收紧或触发策略的影响。
- Communication-control co-design: 通信资源分配、采样/触发策略、控制器预测补偿和网络调度的联合设计。
- Asynchronous / timestamped neighbor exchange: 异步邻居状态、时间戳对齐、out-of-order packet、state age、buffered prediction 和 stale-neighbor compensation。
- Bursty packet loss / jitter: Gilbert-Elliott 或 burst-loss 模型、随机/有界 jitter、连续丢包长度、恢复窗口和 worst-case link outage。
- Resilient consensus: switching topology、intermittent communication、neighbor loss、DoS or link-failure resilience。
- Resilient DMPC for networked agents: 网络退化下的分布式预测控制、局部可行性、邻居预测轨迹共享、约束一致性和通信恢复。
- Event-triggered and self-triggered control: communication-efficient consensus、trigger thresholds、Zeno-free conditions。
- Delay/dropout compensation: state prediction、buffered control、observer-based compensation、timestamp alignment。
- Multi-robot communication-aware control: quality-aware control、communication constraints、network-aware formation。
- DCN-facing network layer metrics: latency、loss rate、topology connectivity、recovery time、degraded mode stability。

应检索类别：

- `network resilient consensus control delay packet dropout multi robot`
- `communication degradation distributed MPC multi agent`
- `packet loss delay compensation cooperative control mobile robots`
- `resilient networked control systems switching topology`
- `event triggered cooperative transport communication constraints`
- `V2X CAV CACC communication delay packet loss control`
- `cooperative adaptive cruise control jitter burst packet loss`
- `wireless multi robot control QoS latency jitter`
- `QoS aware control networked multi robot systems`
- `communication control co-design multi agent MPC`
- `asynchronous timestamped neighbor exchange consensus control`
- `age of information control multi robot consensus`
- `bursty packet loss resilient distributed MPC`

应记录字段：

| 字段 | 记录要求 |
|---|---|
| 退化类型 | delay / packet loss / dropout burst / topology switching / DoS / bandwidth limit |
| 网络模型 | deterministic / stochastic / Markov / Gilbert-Elliott burst loss / bounded delay / graph connectivity |
| DCN 场景 | V2X / CAV / CACC / C-V2X / DSRC / 5G / wireless robot network / edge-assisted control |
| QoS 字段 | latency、jitter、PDR、PER、AoI、RSSI/SINR、bandwidth、network load、recovery time |
| 异步交换 | timestamp、state age、out-of-order packet、buffer length、neighbor prediction horizon |
| 控制响应 | compensation、fallback、observer、event-triggered、re-planning |
| 稳定条件 | maximum delay、dropout rate、dwell time、connectivity condition |
| 性能指标 | tracking error under delay/loss、recovery time、constraint violation、network load |
| 与协同运输关系 | 是否有 payload / force / formation evidence |
| 与学习模型关系 | 是否使用 learned dynamics；是否考虑 model uncertainty |

差距写法：

- 已有 DCN-native 工作从 V2X/CAV/CACC、wireless multi-robot control、QoS-aware control 和 communication-control co-design 角度刻画 latency、jitter、packet loss、AoI、链路质量和拓扑退化对协同行为的影响。
- 但许多通信侧工作不处理车辆-载荷协同动力学和学习预测模型；许多控制侧工作又把通信退化简化为有界扰动，而非使用时间戳、状态年龄、burst loss 和 QoS 指标驱动 MPC 预测与约束。
- 本文补充：把通信退化显式映射到 timestamped neighbor prediction、delay compensation、consensus error、constraint tightening 和 safe degraded mode，使网络韧性成为协同运输控制器的内生模块。
- 放置位置：Introduction 的 network resilience 段、Method 的 communication degradation model 段、Experiments 的 delay/dropout/topology stress tests 段。

### 1.5 FTC / Safety Stability

文献树：

- Fault detection and isolation: actuator fault、sensor fault、communication fault、residual-based or learning-based FDI。
- Fault-tolerant control: control allocation、redundancy management、graceful degradation、fallback controller。
- Safety-critical control: control barrier functions、safety MPC、collision avoidance、force/load constraints。
- Stability under switching and faults: Lyapunov, ISS, practical stability, uniform ultimate boundedness, dwell time。
- Cooperative safety: inter-vehicle collision, payload stability, internal force bound, degraded formation under partial failure。

应检索类别：

- `fault tolerant control multi robot cooperative transport`
- `safety MPC multi robot payload transport`
- `control barrier function cooperative mobile robots payload`
- `fault detection isolation distributed MPC multi agent`
- `Lyapunov stability packet dropout fault tolerant cooperative control`

应记录字段：

| 字段 | 记录要求 |
|---|---|
| 故障类型 | actuator / sensor / communication / vehicle dropout / payload disturbance |
| 诊断方法 | residual / observer / learning / threshold / consistency check |
| FTC 行为 | reallocation、constraint tightening、fallback、formation reshape、stop mode |
| 安全集合 | distance、force、load pose、input bounds、velocity bounds |
| 证明强度 | asymptotic / exponential / ISS / UUB / recursive feasibility / empirical only |
| 实验证据 | fault injection、recovery transient、safety margin、force components |
| 与本文位置 | safety layer、FTC module、stability proof、experiment ablation |

差距写法：

- 已有 FTC 和 safety-critical control 能为故障恢复、约束满足和安全集不变性提供理论工具。
- 但在学习型 Koopman-MPC 协同运输中，同时处理通信退化、执行器/车辆故障、载荷约束和稳定证书的工作仍不足。
- 本文补充：在 delay-compensated consensus MPC 外层或内层加入 FDI/FTC、控制重分配和安全降级，并将稳定结论限定为与假设匹配的 practical stability / UUB。
- 放置位置：Introduction 的 FTC/safety 段、Method 的 FDI/FTC and safety layer 段、Theory 的 stability certificate 段、Experiments 的 fault/safety ablation 段。

## 2. Baseline Comparison Dimensions and Gap Writing

### 2.1 Baseline Status and Allowed Claims

baseline 对比必须先声明处于哪一种状态。没有声明状态时，默认只能写机制对照，不能写数值优越性。

| baseline 状态 | 定义 | 允许的 claim | 不允许的 claim | 必须报告 |
|---|---|---|---|---|
| 原论文复现 | 在 baseline 原始任务或等价任务上复现其 adaptive Koopman-MPC 设置，包括原论文系统、扰动类型、采样周期、MPC 设置和评价指标 | 可写“复现结果与 baseline 报告趋势一致/不一致”；可用作代码和实现可信度说明 | 不允许据此声称本文在协同运输或通信退化任务上优于 baseline，因为任务域尚未迁移 | 原任务设置、数据量、网络结构、MPC horizon、solver、采样周期、误差指标、随机种子、均值/置信区间 |
| 任务适配实现 | 将 baseline 机制适配到本文协同运输任务，例如使用相同车辆-载荷数据训练 adaptive Koopman-MPC，但不加入本文的 delay-compensated consensus、QoS-aware compensation 或 FTC/safety 模块 | 在 fairness gate 全部满足时，可写“在本文定义的协同运输和通信退化评测下，本文方法相对适配 baseline 改善了指定指标” | 不允许写“原 baseline 方法失败”或“原论文结论错误”；不允许把未调参/弱实现当作 baseline 上限 | 适配细节、删去/保留的模块、同数据同约束说明、通信退化注入协议、每个指标的 seed/CI、求解时间 |
| 机制对照 | 未实现或未复现 baseline，只基于 baseline 论文的公开方法描述做范围和机制比较 | 可写“baseline 未覆盖通信退化、多车协同运输、QoS-aware control 或 FTC/safety 主线”；可写“本文补充这些模块” | 不允许写“本文数值上优于 baseline”；不允许写“baseline 在丢包/时延下不稳定/失败” | baseline 机制摘要、本文新增模块、不可比原因、需要后续实验验证的指标 |

推荐状态句：

> Unless a task-adapted implementation is built under the frozen fairness gate, the baseline is used only as a mechanism-level reference: it establishes adaptive Koopman-MPC for nonlinear systems, while this paper studies network-resilient cooperative transport under timestamped, delayed and lossy neighbor exchange.

### 2.2 Baseline Comparison Dimensions

| 维度 | baseline 做什么 | baseline 未覆盖什么 | 本文差距写法 |
|---|---|---|---|
| 问题对象 | 面向复杂非线性系统的 adaptive Koopman control；验证于 coupled pendulums、3R manipulator、planar quadrotor | 多车协同运输、车辆-载荷耦合、载荷位姿和队形一致性不是主任务 | baseline 解决“单体或通用系统在动力学变化下的 Koopman-MPC 鲁棒控制”，本文解决“通信退化下多车协同运输的学习预测控制” |
| Koopman 表示 | autoencoder nominal Koopman；linear/bilinear dynamics；在线修正 `A/B` | 未针对车辆-载荷协同动力学设计通信感知的 lifted state 或共识误差 | 本文可承接 baseline 的 adaptive Koopman 动机，但强调 bilinear Koopman 被嵌入协同运输和网络退化控制链路 |
| 控制器 | MPC/NMPC 跟踪控制，主要关注模型不确定和扰动下的跟踪 | 无 delay-compensated consensus MPC；无分布式邻居预测；无通信退化约束 | baseline 的 MPC 是控制接口，本文的 MPC 是网络韧性协同优化器 |
| 通信退化 | 未把 delay、packet loss、topology degradation 作为核心变量 | 无丢包/时延/链路失效建模，无网络指标 | 本文在 DCN 语境下补充通信退化建模、延迟补偿和拓扑韧性验证 |
| 协同运输指标 | 使用 tracking RMS、误差热图、计算时间等指标 | 无 payload pose、formation error、force sharing、inter-vehicle safety 等指标 | 本文需用载荷位姿、队形误差、力/力矩、约束违反率和恢复时间证明任务层优势 |
| 鲁棒对象 | 参数变化、测量噪声、输入扰动、风场 | 通信故障、局部车辆故障、安全降级、协同失配 | baseline 的鲁棒性是 dynamics uncertainty；本文的鲁棒性还包含 network-induced and cooperative-task uncertainty |
| FTC / safety | 可承受扰动，但未形成 FDI/FTC 或 safety layer 主贡献 | 无故障检测、隔离、控制重分配、安全 fallback 和安全集证明 | 本文补充故障注入、重分配和安全约束证据；避免说 baseline 没有安全性，只说其不以 FTC/safety 为主线 |
| 理论证明 | 给出 adaptive Koopman 在线修正的理论条件和 Koopman 表示假设 | 不覆盖通信退化、切换拓扑、故障模式下的协同闭环稳定 | 本文理论应写为 boundedness / ISS-practical stability / UUB，不能过度承诺 asymptotic stability |
| 实验形态 | 多类系统仿真，证明 adaptive Koopman 比 nominal Koopman 更鲁棒 | 未覆盖多车协同运输场景和网络退化场景 | 若不能复现 baseline，不做数值优劣比较；改为“scope gap + mechanism comparison + ablation evidence” |
| 计算公平性 | baseline 强调 linear adaptive Koopman 相对 bilinear 的实时优势 | 本文若使用 bilinear/DMPC，计算负担可能更高 | 必须报告 solver、horizon、sampling time、平均/最大求解时间，避免只报误差 |

### 2.3 Frozen Baseline Fairness Gate

若论文要写“本文优于 baseline / outperforms the baseline / reduces error compared with baseline”，以下 gate 必须全部冻结并在实验设置中公开。任一 gate 未满足时，只能降级为“机制对照”或“任务适配对照”，不能写直接优越性。

| Gate | 必须冻结的内容 | 不满足时的降级写法 |
|---|---|---|
| 同训练数据 | baseline-adapted 和 proposed 使用同一 offline dataset、同一 train/validation split、同一 excitation range、同一归一化和同一数据量 | “本文在更完整通信建模下表现更好”不能成立；只能写“需要同数据补测” |
| 同 MPC horizon | prediction horizon、control horizon、terminal cost/terminal constraints 一致或给出严格理由 | 不比较 tracking error，只报告不同设置下的消融趋势 |
| 同 solver | OSQP/SQP/NMPC solver、tolerances、max iterations、warm start、linearization/update policy 一致 | 不能把求解器差异导致的性能差异归因于方法 |
| 同采样周期 | control sampling time、communication sampling time、sensor update time 和 buffer update rate 一致 | 只能比较机制，不比较实时性能或误差 |
| 同约束 | state/input/payload/force/safety constraints、constraint tightening、soft penalty 权重一致 | 不能声称更安全或约束违反更少 |
| 同计算预算 | CPU/GPU、线程、最大 wall-clock time、每步求解预算、online adaptation epochs/window 一致 | 不能声称实时性或计算效率优势 |
| 同通信退化注入 | delay、jitter、packet loss、burst length、topology switching、AoI、timestamp disorder 的注入协议一致 | 不能声称 network resilience 优势 |
| 同 seed/CI | 至少多 seed；报告 mean/std 或 95% CI；同一随机扰动序列或配对统计 | 不能声称稳定改善，只能报告单例现象 |
| 同调参预算 | baseline-adapted 和 proposed 有相同调参搜索范围、验证集和停止准则 | 不能用弱调参 baseline 支撑优越性 |
| 同指标口径 | payload pose、formation/consensus error、force smoothness、constraint violation、recovery time、solver time 使用同一计算窗口 | 不能跨指标选择性比较 |

推荐差距段落模板：

> Adaptive Koopman embedding has shown that online corrections of Koopman matrices can improve MPC tracking under parametric variations, measurement noise and exogenous disturbances. However, this line of work is primarily formulated for generic nonlinear systems or single robotic platforms, and communication degradation is not part of the predictive control problem. For cooperative transport, the dominant uncertainty is not only model mismatch but also network-induced inconsistency among vehicles. Therefore, this paper extends the Koopman-MPC pipeline toward a network-resilient cooperative transport setting by combining bilinear Koopman learning, delay-compensated consensus MPC, and safety/fault-tolerant degradation logic.

中文写法模板：

> 现有 adaptive Koopman-MPC 能通过在线修正 lifted dynamics 提升模型失配、噪声和外扰下的轨迹跟踪性能，但其问题设定主要面向通用非线性系统或单体机器人平台，通信时延、丢包和拓扑退化并不是预测控制问题的内生变量。对于多车协同运输，性能退化不仅来自模型误差，还来自网络退化导致的邻居状态不一致、载荷耦合误差和安全约束收紧。因此，本文在 Koopman-MPC 框架上补充面向协同运输的 bilinear Koopman 学习模型、延迟补偿一致性 MPC 以及故障/安全降级机制。

## 3. Literature-to-Contribution Table Framework

后续主文献表建议采用以下框架。当前阶段不填虚构文献，只填“待检索类别”和论文落点。

| 模块 | 待检索代表工作类别 | 已有工作做什么 | 没考虑什么 | 本文补什么 | 放在论文哪里 | 需要的证据 |
|---|---|---|---|---|---|---|
| Koopman / vehicle control | adaptive Koopman, bilinear Koopman, Koopman-MPC, control-aware Koopman, robust tube Koopman | 学习非线性系统的 lifted representation，并与 MPC 或反馈控制结合 | 多车协同运输、通信退化、载荷约束和安全降级通常不是统一问题 | bilinear Koopman vehicle-load model；服务于协同运输的预测控制 | Introduction Koopman 段；Method Koopman learning 段 | prediction error、rollout stability、baseline Koopman comparison、computation time |
| Cooperative transport | multi-robot payload transport, distributed cooperative manipulation, load sharing | 处理载荷位姿跟踪、队形保持、力/力矩分配 | 可靠通信假设较强；较少结合 learned dynamics 和网络韧性 MPC | network-resilient cooperative transport under learned nonlinear dynamics | Introduction cooperative transport 段；Method vehicle-load model 段 | payload pose error、formation error、force smoothness、safety margins |
| MPC / DMPC | consensus MPC, robust DMPC, delay-compensated MPC, learning-based MPC | 在约束下优化多智能体或机器人跟踪；可处理部分扰动 | 学习模型、通信退化和协同运输载荷约束常分散处理 | delay-compensated consensus MPC with Koopman lifted dynamics | Method MPC formulation 段 | delay/dropout ablation、constraint violation、solver time |
| DCN-native network resilience | V2X/CAV/CACC degradation, wireless multi-robot control, QoS-aware control, communication-control co-design, asynchronous/timestamped exchange, bursty loss/jitter, resilient consensus/DMPC | 建模 latency、jitter、PDR/PER、AoI、链路质量、拓扑切换和异步邻居信息，并分析其对协同控制的影响 | 与载荷运输、Koopman learning、MPC 约束和 FTC/safety 集成不足 | 将 QoS/时间戳/状态年龄/丢包突发映射到预测补偿、共识误差、约束收紧和安全降级模块 | Introduction network resilience 段；Method communication model 段 | latency/jitter/loss/AoI sweeps、burst-loss test、recovery time、topology degradation results |
| FTC / safety stability | FDI/FTC, safety MPC, CBF, switched-system stability | 提供故障检测、重分配、安全约束或稳定性工具 | 少有工作同时覆盖 Koopman-MPC、网络退化和协同载荷安全 | FDI/FTC, control reallocation, safe fallback, practical stability certificate | Method FTC/safety 段；Theory stability 段 | fault injection、reallocation transient、safety constraint activity、certificate terms |

文献记录模板：

| Citation key | 合法来源 URL | 年份 | 模块 | 系统对象 | 控制器 | 通信/QoS 假设 | 异步/时间戳 | burst/jitter 模型 | 故障/安全 | 理论保证 | 实验指标 | 可引用句 | 本文 gap 句 | 放置位置 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TBD | publisher/arXiv/author/institutional | TBD | Koopman/MPC/DCN/etc. | TBD | TBD | latency/jitter/PDR/AoI/etc. | timestamp/state age/buffer | Gilbert-Elliott/bounded jitter/etc. | TBD | TBD | TBD | 该文做了什么 | 该文未覆盖什么 | Intro/Method/Exp/Theory |

## 4. Baseline Fairness Risks to Avoid

- 不要写“baseline 在通信退化下失败”，除非实际在同一场景、同一约束、同一采样周期和同一求解预算下复现并测试。当前安全写法是“baseline 未建模该维度”。
- 不要把 baseline 的单系统任务与本文多车协同运输任务直接做数值优劣比较。可做机制差异和适用范围差异，数值比较必须说明任务重构方式。
- 不要把本文独有的通信丢包、拓扑断连、车辆故障注入作为 baseline 的“失败证据”，除非说明这是 out-of-scope stress test。
- 不要用不同训练数据量、不同噪声强度、不同采样频率、不同 MPC horizon 或不同求解器设置来声称本文更优。
- 不要忽略 baseline 对 adaptive Koopman 的贡献。本文应承认其在线修正 `A/B` 的价值，再说明本文扩展到 network-resilient cooperative transport。
- 不要用“bilinear 必然优于 linear”作为泛化结论。baseline 已指出 bilinear 可能带来计算负担，本文若使用 bilinear 必须报告实时性。
- 不要把 baseline 的 robustness 与本文 network resilience 混为一谈。前者主要是 dynamics/model uncertainty，后者还包括 communication-induced inconsistency。
- 不要在稳定性上过度承诺。若存在持续丢包、切换拓扑或模型误差，应优先使用 ISS、practical stability 或 UUB 等与假设匹配的表述。
- 不要只比较 tracking error。协同运输还必须报告 payload pose、formation/consensus error、force smoothness、constraint violation、recovery time 和 solver time。
- 不要引用无法合法获取或无法核验的文献。每条新增文献必须保留合法来源 URL 和检索日期。

### 4.1 Conditions Where We Cannot Directly Claim Superiority over Baseline

以下任一条件成立时，论文不能直接写“本文优于 baseline”。应改写为“本文补充 baseline 未覆盖的网络协同机制”，或“在任务适配 baseline 下仍需公平补测”。

- 未完成原论文复现，也未完成任务适配实现，只做了机制阅读。
- baseline 没有使用与 proposed 相同的训练数据、训练/验证划分或数据归一化。
- proposed 使用了通信退化训练或补偿信息，而 baseline 没有获得同等通信退化输入。
- MPC horizon、solver、采样周期、约束、代价权重或终止条件不同。
- proposed 使用更宽松约束，或 baseline 被施加了 proposed 没有承受的额外约束。
- baseline 没有经过同等调参预算，或只采用默认参数。
- 通信退化注入只作用于 baseline，或两者的 delay/loss/jitter/burst/topology 序列不同。
- 只报告单 seed、单场景或无置信区间，无法排除随机扰动导致的偶然改善。
- 只比较 tracking error，缺少 payload pose、formation error、force smoothness、constraint violation、recovery time 和 solver time。
- proposed 的计算时间超过控制采样周期，但仍与实时 baseline 直接比较控制效果。
- baseline 被改造成不再代表原 adaptive Koopman-MPC 机制，却仍被称为原论文 baseline。
- 本文的新增模块包含 delay compensation、QoS-aware prediction、FTC 或 safety fallback，而 baseline 没有同等可用信息；此时只能声明“新增模块带来任务内收益”，不能声明“baseline 方法本身较差”。

## 5. Literature Completion Priority

### P0: 必须优先补齐

- DCN-native 通信控制文献：V2X/CAV/CACC 通信退化、wireless multi-robot control、QoS-aware control、communication-control co-design、asynchronous/timestamped neighbor exchange、bursty packet loss/jitter、resilient consensus/DMPC。该项优先级高于一般控制文献，因为 DCN 主题必须由通信网络文献支撑。
- 近三年 adaptive / robust / control-aware Koopman-MPC 文献：用于界定 baseline 附近的最近工作，防止 novelty 被认为只是 adaptive Koopman 的应用迁移。
- Koopman for vehicle / robot control 文献：用于支撑 bilinear Koopman learning 与车辆/机器人控制的合理性。
- Multi-robot cooperative transport 文献：用于证明本文不是普通轨迹跟踪，而是载荷耦合、多车协同和力/队形约束问题。
- Communication-delay/dropout resilient consensus or DMPC 文献：用于支撑 network-resilient consensus MPC 的控制侧理论。

### P1: 第二优先级

- Safety MPC / CBF / fault-tolerant cooperative control 文献：用于支撑 FTC、安全降级和约束稳定性段落。
- Distributed MPC with constraints and recursive feasibility 文献：用于补强方法和理论审稿风险。
- Communication-aware multi-robot control 文献：用于把网络指标与控制性能指标连接起来。

### P2: 补强型文献

- Switched/delayed networked control stability 文献：用于理论部分限定 dwell time、bounded delay、dropout rate 和 connectivity assumptions。
- Load force / internal force smoothing 文献：用于解释为什么只看位置误差不足。
- Real-time MPC solver and computation literature：用于支撑求解时间、sampling period 和在线可部署性讨论。

### 推荐检索顺序

1. 先检索 DCN-native 主题邻域：V2X/CAV/CACC delay/loss/jitter、wireless multi-robot QoS、AoI/timestamped exchange、communication-control co-design、bursty loss resilient consensus/DMPC。
2. 再检索 baseline 的直接邻域：adaptive Koopman、robust Koopman MPC、control-aware Koopman、bilinear Koopman robotics。
3. 再检索目标应用邻域：multi-robot cooperative transport、distributed payload manipulation、ground vehicle load sharing。
4. 最后检索 safety/FTC/theory：fault-tolerant multi-agent control、safety MPC、CBF、ISS/UUB under switching/delay。

## 6. Recommended Placement in the Manuscript

| 论文位置 | 应放内容 | 避免内容 |
|---|---|---|
| Introduction paragraph 1 | 非线性车辆/载荷系统需要学习型模型；Koopman 提供 lifted linear/bilinear 表示 | 不要一开始就讲本地 TF 版本历史 |
| Introduction paragraph 2 | Koopman-MPC 和 adaptive Koopman 的已有进展，以及 baseline 的贡献 | 不要贬低 baseline；写“未覆盖协同网络退化”即可 |
| Introduction paragraph 3 | 协同运输、多车载荷、队形一致性和安全约束 | 不要只讲单车 tracking |
| Introduction paragraph 4 | DMPC/consensus MPC 与通信退化韧性 | 不要把通信退化当作普通外扰一句带过 |
| Introduction paragraph 5 | FTC/safety/stability gap | 不要承诺强于证据的稳定性 |
| Contributions | 每条贡献绑定一个方法模块和一个实验/证明证据 | 不要写泛泛的“提高鲁棒性” |
| Related Work table | 用本文件第 3 节框架填充真实文献 | 不要填没有合法来源的条目 |
| Experiments intro | 说明 baseline comparison dimensions 和公平设置 | 不要在不同任务上做不加说明的数值横比 |
