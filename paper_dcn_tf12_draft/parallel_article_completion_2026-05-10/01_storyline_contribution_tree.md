# Worker A: Storyline and Contribution Tree

## Reviewer-driven revisions

本次返工按 Reviewer 1 的 P0 意见重构叙事。核心变化如下：

1. DCN 主题从“控制器考虑通信退化”升级为“通信网络问题驱动控制设计”。论文入口必须是 degraded digital communication network，而不是 Koopman 或 MPC 本身。
2. 贡献排序改为：通信感知 delay-compensated consensus MPC 是核心 novelty；networked cooperative payload transport formulation 是支撑问题定义；bilinear Koopman learning 是预测模型支撑；fault redistribution / safety fallback 是 network-resilient transport 的 safety and resilience extension。
3. 全文贡献与任务描述使用 manuscript-facing language，不出现任何内部版本标签、内部工程产物名称或历史迭代表述。
4. 所有稳定性、网络韧性和容错 claim 均压到 bounded delay/dropout、bounded model error、feasible MPC、tested scenarios 条件下。
5. 每个贡献必须显式给出 method module、experimental validation 和 baseline difference。

## 0. 叙事边界

本文必须以 Digital Communications and Networks 读者能立即识别的问题为入口：在退化数字通信网络下，多辆地面车辆共同搬运刚性载荷时，链路时延、随机丢包、突发丢包、时延抖动、拓扑切换、链路质量下降、时间戳不一致和异步采样会导致邻居状态过期、车间命令离散、团队一致性下降，并进一步通过刚性载荷耦合放大为轨迹误差、连接误差和载荷冲突力。

Koopman 学习和 MPC 不是论文主问题，而是为了应对上述网络诱发失配而构造的控制工具。主线应写成“communication network degradation creates a control-design problem”，而不是“a controller is tested under communication degradation”。

baseline 为 `Adaptive Koopman Embedding for Robust Control of Complex Nonlinear Dynamical Systems`。baseline 的核心价值是离线 Koopman 嵌入、在线自适应修正和 MPC 可提升单体非线性系统在参数变化、噪声和扰动下的鲁棒控制性能。本文与 baseline 的差异应写成任务和闭环结构扩展：从单体系统的 model-level adaptive Koopman-MPC，扩展到由通信网络状态驱动的 networked multi-vehicle cooperative transport control。

推荐总叙事句：

> This paper addresses network-resilient cooperative payload transport as a communication-driven control problem: bounded delay, dropout, burst loss, jitter, topology switching, link quality variation, and asynchronous timestamped sampling are explicitly mapped into consensus weights, neighbor prediction, fallback decisions, and network-aware validation metrics.

## 1. 可投稿 Topic 切入树

### 1.1 顶层切入

**Communication-network-driven cooperative payload transport under degraded digital networks**

审稿人第一眼应看到的不是“又一个 Koopman 控制器”，而是“退化通信网络如何改变协同运输控制律本身”。本文的核心 novelty 是把网络状态变成 consensus MPC 的显式输入：链路质量决定一致性权重，时间戳和时延决定邻居状态前推预测，突发丢包和拓扑切换决定 fallback 触发，实验指标直接报告网络退化与运输性能之间的耦合关系。

### 1.2 一级问题树

1. **通信网络退化是控制设计入口**
   - delay：邻居状态到达控制器时已经过期，导致基于旧状态的一致性校正产生相位滞后。
   - dropout：单次数据包丢失导致局部邻居信息缺口，需要在 consensus update 中降低不可信链路权重。
   - burst loss：连续丢包会造成短时间拓扑断裂，需要触发保守 fallback 或保持上一次可信预测。
   - jitter：时延随机波动使固定补偿步长不足，需要使用 timestamp-aware prediction。
   - topology switching：可用通信边随时间变化，使 consensus graph 和邻居集合需要在线更新。
   - link quality：链路质量应从实现层日志上升为控制变量，进入权重、约束收紧或 fallback 逻辑。
   - timestamp / asynchronous sampling：不同车辆状态并非同一采样时刻，需要先对齐到当前控制时刻再参与一致性计算。

2. **网络退化如何进入控制器**
   - consensus weights：低质量、高时延或连续丢包链路权重降低；可靠链路和自车预测权重提高。
   - neighbor prediction：带时间戳的邻居状态先按 Koopman / vehicle-team predictor 前推到当前时刻，再用于相对误差和一致性校正。
   - fallback：当平均链路质量低于阈值、burst loss 持续超过窗口或拓扑连通性不足时，控制器向保守团队命令、安全速度和较低横摆响应过渡。
   - experiment metrics：实验不只报告 tracking error，还必须报告 delay distribution、dropout rate、burst length、jitter、active topology、link quality、timestamp age、consensus weight evolution、fallback activation 和 network-induced command dispersion。

3. **协同运输任务需求**
   - 多辆轮式车辆共同搬运同一刚性载荷。
   - 任务指标同时包含团队中心路径跟踪、角点车辆误差、连接一致性、载荷横向/纵向受力和偏航力矩。
   - 网络诱发的局部状态不一致会通过刚性载荷变成团队级姿态误差和冲突力。

4. **模型失配与学习支撑**
   - 协同运输包含车辆 Frenet 动力学、载荷刚性映射、柔性连接误差和受力约束，原始非线性模型直接嵌入 MPC 会带来求解和泛化压力。
   - baseline 的 adaptive Koopman embedding 已证明在线自适应对单体系统有效，但没有把 timestamped communication degradation 作为控制律输入。
   - 本文使用稳定投影双线性 Koopman predictor 支撑 neighbor prediction 和 MPC rollout，但 novelty 需要服务于网络韧性协同运输主线。

5. **安全与执行韧性扩展**
   - 单车转角或加速度通道降额会破坏团队等效力和等效力矩。
   - 在通信退化下，执行器降额更容易被误判或放大，因此 safety fallback、命令重分配和进度恢复应作为 network-resilient transport 的 extension。
   - 不应把论文改写成单独的 fault-tolerant control 主线；执行器降额只服务于“网络韧性协同运输在安全边界内继续完成任务”的叙事。

### 1.3 推荐投稿角度

首选标题角度：

**Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC**

可选增强角度：

1. **Communication-Aware Koopman Consensus MPC for Network-Resilient Cooperative Payload Transport**
2. **Delay-Compensated Consensus MPC for Koopman-Based Cooperative Payload Transport over Degraded Digital Networks**
3. **Network-Driven Cooperative Payload Transport Control with Timestamp-Aware Koopman Prediction**

不推荐标题角度：

1. 不使用任何本地版本号、阶段代号或内部工程产物名称。
2. 不把标题写成单纯 `Adaptive Koopman Control`，否则会被认为与 baseline 太近。
3. 不把标题写成只强调 `fault-tolerant`，否则会偏离 DCN 的通信网络主线。

## 2. 标题、摘要、引言主线重构任务

### 2.1 标题重构任务

标题应同时包含三类信息：

1. **通信网络问题**：network-resilient / communication-aware / delay-compensated / degraded digital networks。
2. **应用对象**：cooperative payload transport / multi-vehicle cooperative transport。
3. **技术抓手**：bilinear Koopman learning + consensus MPC。

建议最终标题：

**Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC**

如需更突出 DCN，可改为：

**Communication-Aware Koopman Consensus MPC for Network-Resilient Cooperative Payload Transport**

### 2.2 摘要重构任务

摘要建议按 6 句组织：

1. **网络问题句**：退化数字通信网络下，多车刚性载荷协同运输受到 bounded delay、dropout、burst loss、jitter、topology switching、link quality variation 和 asynchronous timestamped sampling 的共同影响。
2. **控制缺口句**：现有 adaptive Koopman-MPC 主要验证单体非线性系统鲁棒控制，现有协同运输/MPC 工作又较少把通信网络状态直接映射为 consensus weights、neighbor prediction 和 fallback decisions。
3. **核心方法句**：本文提出 communication-aware delay-compensated consensus MPC，并以 bilinear Koopman predictor 为 timestamp-aware neighbor prediction 和 team-level MPC 提供模型支撑。
4. **支撑模块句**：框架包括 networked cooperative transport formulation、稳定投影双线性 Koopman 预测、link-quality-aware consensus weighting、delay/jitter-aware neighbor prediction、burst-loss/topology-aware fallback、以及 safety-governed actuator-degradation handling。
5. **证据句**：用同一协同运输任务上的 task-aligned Adaptive Koopman Embedding baseline、网络退化场景和消融实验验证 tracking error、connection error、payload force/moment、consensus weight evolution、timestamp age、fallback activation、task completion 和 solver feasibility。
6. **结论句**：结果应表述为“improves network-resilient cooperative transport performance under the tested bounded network degradation scenarios”，不要写成任意通信故障、全局稳定或完全容错。

摘要中应删除或转移：

1. 删除内部版本号、内部工程产物名称和历史迭代表述。
2. 不在摘要中堆过多训练超参数，保留能支撑主张的核心结构即可。
3. 数值结果只放最核心的 3-4 个指标，并确保它们都有 baseline 对比和网络场景说明。

### 2.3 引言主线重构任务

引言建议采用“网络问题驱动，而非方法堆叠”的 7 段结构：

1. **段 1：DCN 场景入口**
   - 从联网多车、协同运输、退化数字通信网络切入。
   - 明确网络退化元素：delay、dropout、burst loss、jitter、topology switching、link quality、timestamp/asynchronous sampling。
   - 强调这些元素不是仿真噪声，而是会改变 consensus、prediction 和 fallback 的控制设计变量。

2. **段 2：网络化协同运输的控制难点**
   - 说明刚性载荷把车间信息不一致放大成连接误差、载荷冲突力和团队姿态误差。
   - 缺口：许多协同运输工作关注几何约束和预测控制，但默认通信足够可靠或只把通信退化作为外部扰动。

3. **段 3：通信韧性 MPC / consensus 现状**
   - 总结 delay compensation、event-triggered DMPC、resilient consensus、platoon/CACC 网络鲁棒控制。
   - 缺口：多数方法面向编队或纵向车队，较少把 timestamp-aware neighbor prediction、link-quality-dependent consensus weights 和 payload-force-aware transport metrics 放在同一闭环。

4. **段 4：Koopman-MPC 与 baseline 的位置**
   - 说明 Koopman lifting 使非线性动力学更容易进入 MPC，也可为 delayed neighbor prediction 提供滚动模型。
   - 公平承认 baseline 已解决单体系统模型变化、扰动和噪声下的在线自适应问题。
   - 明确 gap：baseline 不处理多车协同通信网络，不建模时间戳异步、拓扑切换、burst loss，也不将链路质量映射为控制权重。

5. **段 5：本文核心思路**
   - 将问题拆成三条网络驱动链路：network-to-consensus mismatch、prediction mismatch、execution/safety mismatch。
   - 对应闭环：通信质量感知时延补偿 consensus MPC、稳定投影双线性 Koopman predictor、safety fallback 和 bounded actuator-degradation handling。

6. **段 6：贡献点**
   - 贡献排序必须先写 communication-aware delay-compensated consensus MPC。
   - 每点都必须同时出现 method module、验证方式和 baseline 差异。
   - 不写“首次”“完全解决”“严格保证所有情况”等过强表述。

7. **段 7：文章结构**
   - Section II networked cooperative transport problem formulation。
   - Section III communication-aware delay-compensated consensus MPC。
   - Section IV bilinear Koopman prediction and team-level MPC embedding。
   - Section V safety/resilience extension and boundedness discussion。
   - Section VI network degradation experiments and ablations。

## 3. 四个贡献点及 method-evidence-baseline 映射

### Contribution 1: Communication-Aware Delay-Compensated Consensus MPC

推荐贡献表述：

> We develop a communication-aware delay-compensated consensus MPC framework that converts bounded delay, dropout, burst loss, jitter, topology switching, link quality, and timestamped asynchronous sampling into adaptive consensus weights, timestamp-aware neighbor prediction, and fallback decisions for network-resilient cooperative payload transport.

对应 method 模块：

1. 网络状态建模：bounded delay、dropout、burst loss、jitter、topology switching、link quality、timestamp age 和 asynchronous sampling。
2. link-quality-aware consensus weights：根据链路质量、时延、丢包和拓扑可用性调整邻居权重。
3. timestamp-aware neighbor prediction：对过期邻居状态按时间戳前推到当前控制时刻，再进入一致性误差。
4. burst-loss/topology-aware fallback：连续丢包、拓扑断连或平均链路质量低于阈值时，切换到保守团队命令和安全速度。
5. network-aware MPC objective：将团队跟踪、连接一致性、命令离散、控制平滑和网络质量共同纳入控制评价。

实验验证：

1. delay / dropout / burst loss / jitter / topology switching 分组实验。
2. link quality、timestamp age、active topology、consensus weights、fallback activation 与 tracking error 的时间对齐图。
3. 网络退化下的团队中心误差、四车角点误差、连接误差、载荷力/力矩、命令离散和求解可行性。
4. 消融：no delay compensation、no link-quality weighting、no timestamp-aware prediction、no burst-loss fallback、fixed topology assumption。
5. 与 task-aligned Adaptive Koopman Embedding baseline 在同一网络退化场景下比较。

baseline 差异：

1. baseline 主要处理单体系统的模型参数变化、测量噪声和外部扰动，不把车间通信网络状态作为控制律输入。
2. baseline 不包含 link-quality-dependent consensus weights、timestamp-aware neighbor prediction、topology switching handling 或 burst-loss fallback。
3. 本文的核心增量是把 degraded digital communication network 显式映射到 consensus MPC 机制和实验指标，而不是只在控制后端添加通信噪声测试。

### Contribution 2: Networked Cooperative Payload Transport Formulation

推荐贡献表述：

> We formulate a networked multi-vehicle cooperative payload transport problem in which payload-center Frenet dynamics, corner-vehicle geometric consistency, flexible connection errors, payload force metrics, and time-varying communication graph variables are represented in a unified team-level control objective.

对应 method 模块：

1. 载荷中心 Frenet 团队模型。
2. 四角点车辆几何映射。
3. 柔性连接一致性状态与约束。
4. 载荷横向/纵向受力、偏航力矩和角点法向载荷指标。
5. 带时间戳的通信图、可用邻居集合、链路质量和拓扑切换变量。

实验验证：

1. 主协同运输任务中的团队中心轨迹、四车角点轨迹和参考路径对齐。
2. 单车误差、连接误差、载荷横向/纵向力、偏航力矩和法向载荷范围。
3. 网络退化导致的 connection error、payload force peaks 和 command dispersion 变化。
4. baseline 与 proposed 在同一载荷、同一路径、同一车辆参数和同一网络退化场景下比较。

baseline 差异：

1. baseline 关注单体复杂非线性系统的 Koopman-MPC 鲁棒控制，不包含刚性载荷协同运输任务定义。
2. baseline 的验证对象不需要处理角点车辆几何一致性、载荷受力、通信图切换或时间戳异步。
3. 本文把 baseline 的单系统控制问题提升为 networked cooperative transport problem，使通信感知 consensus MPC 有明确的协同运输约束对象。

### Contribution 3: Stable-Projected Bilinear Koopman Predictor for Timestamp-Aware Team MPC

推荐贡献表述：

> We construct a stable-projected bilinear Koopman predictor for payload-centered team dynamics, supporting both long-horizon team MPC rollout and timestamp-aware prediction of delayed neighbor states under bounded model error.

对应 method 模块：

1. 双线性 Koopman lifted state。
2. 学习型观测函数与解码矩阵。
3. state / lifted prediction loss 和稳定性正则。
4. Koopman 矩阵岭回归重拟合。
5. 谱半径稳定投影。
6. 用于 delayed neighbor state forward prediction 的 rolling predictor 接口。

实验验证：

1. 离线 one-step 和 multi-step prediction error。
2. 不同 timestamp age 下的 neighbor prediction error。
3. 高曲率段、网络退化段、fallback 触发前后的预测误差变化。
4. 与 task-aligned Adaptive Koopman Embedding baseline 的预测精度、闭环轨迹误差和求解可行性对比。
5. 消融：no stable projection、lower-dimensional lifted state、no lifted loss、no online correction / refitting。

baseline 差异：

1. baseline 证明 adaptive Koopman embedding 对单体系统控制有效，但其 predictor 不服务于多车时间戳异步邻居预测。
2. baseline 没有把载荷耦合、车辆横摆、连接误差和通信诱发的 timestamp age 统一纳入 team-level prediction。
3. 本文强调“为 network-aware consensus MPC 提供 bounded-error prediction support”，而不是泛泛声称 Koopman 模型全局更准确。

### Contribution 4: Safety-Governed Resilience Extension for Network-Resilient Transport

推荐贡献表述：

> We add a safety-governed resilience extension that coordinates conservative fallback, actuator-effectiveness monitoring, bounded command redistribution, and progress recovery so that network-induced inconsistency and bounded actuator degradation do not directly propagate into payload-level instability in the tested scenarios.

对应 method 模块：

1. 通信退化安全回退：低链路质量、burst loss 或拓扑连通性不足时进入保守团队命令。
2. 执行器有效性监测：估计转角和加速度通道的 bounded effectiveness loss。
3. bounded command redistribution：在输入约束内由健康车辆分担部分团队级命令亏损。
4. safety envelope：横向误差、航向误差、横摆响应、载荷受力和输入约束保护。
5. progress recovery：安全回退后在条件满足时恢复纵向推进，避免保守模式导致任务停滞。

实验验证：

1. 网络退化叠加单车转角/加速度降额场景。
2. fallback activation、actuator effectiveness estimate、redistributed command、input saturation 和 progress recovery 时间序列。
3. 团队中心误差、单车误差、连接误差、载荷力/力矩、任务完成率和求解可行性。
4. 消融：no safety fallback、no command redistribution、no progress recovery、network fallback only。

baseline 差异：

1. baseline 的 adaptive update 可减小模型预测误差，但不处理通信退化下的团队安全回退和 bounded command redistribution。
2. baseline 没有把执行器降额放在 network-resilient transport 的 safety extension 中，也不报告载荷受力和团队级安全边界。
3. 本文不声称完全容错，而是说明在 tested bounded degradation scenarios 中，安全/韧性扩展可减少网络不一致和执行亏损向载荷级误差传播。

## 4. 贡献点逻辑顺序和依赖

建议按以下顺序写贡献和方法章节：

1. **Contribution 1 是核心 novelty：通信网络驱动 consensus MPC**
   - delay、dropout、burst loss、jitter、topology switching、link quality、timestamp/asynchronous sampling 先被定义为控制输入侧的信息质量变量。
   - consensus weights、neighbor prediction 和 fallback 都由这些网络变量驱动。

2. **Contribution 2 是问题定义支撑**
   - 没有载荷中心模型、角点映射、连接误差、载荷受力指标和通信图变量，就无法证明 consensus MPC 改善的是 networked cooperative transport，而不是普通单车跟踪。

3. **Contribution 3 是预测模型支撑**
   - Koopman predictor 为 MPC rollout 和 delayed neighbor prediction 提供 bounded-error model support。
   - 该贡献服务于网络感知 consensus MPC，不应抢占 DCN 主线。

4. **Contribution 4 是 safety/resilience extension**
   - fallback、bounded actuator redistribution 和 progress recovery 用于处理网络退化与执行降额叠加时的安全边界。
   - 该贡献不应变成独立 fault-tolerant control 主线，而应作为 network-resilient transport 的安全扩展。

逻辑链应写成：

**communication network degradation -> network-aware consensus MPC -> cooperative payload transport formulation -> Koopman-supported prediction -> safety/resilience extension -> network degradation experiments**

不要写成：

**old version -> newer version -> newest version**

也不要写成：

**Koopman model -> controller -> communication disturbance test**

## 5. 不能写成过强 claim 的内容

### 5.1 稳定性 claim

不能写：

1. “guarantees asymptotic stability under arbitrary delay and packet loss”
2. “ensures global stability for all communication failures”
3. “strictly proves convergence of the nonlinear learned closed-loop system”

建议写：

1. “provides a practical boundedness argument under bounded delay/dropout, bounded model error, feasible MPC solutions, and specified switching/fallback assumptions”
2. “maintains bounded tracking and connection errors in the tested degradation scenarios”
3. “supports network-resilient operation under the considered communication and actuator degradation models”

### 5.2 通信网络 claim

不能写：

1. “solves all digital communication network failures”
2. “robust to arbitrary cyber attacks”
3. “works under unlimited latency or complete communication blackout”
4. “guarantees consensus under arbitrary topology switching”

建议写：

1. “handles bounded delay, bounded dropout, bounded burst loss, jitter, topology switching, and link-quality variation modeled in the control loop”
2. “mitigates command inconsistency caused by delayed, missing, or low-quality timestamped neighbor information”
3. “switches toward conservative fallback under severe but modeled communication degradation”
4. “evaluates network-resilient transport under the tested delay/dropout/burst/jitter/topology scenarios”

### 5.3 Koopman learning claim

不能写：

1. “learns the exact nonlinear dynamics”
2. “guarantees globally valid Koopman representation”
3. “outperforms all Koopman methods”

建议写：

1. “learns a finite-dimensional bilinear approximation suitable for the tested cooperative transport regimes”
2. “reduces prediction drift for MPC and timestamp-aware neighbor prediction through lifted loss and stable projection”
3. “improves task-level closed-loop performance over the task-aligned Adaptive Koopman Embedding baseline in the tested scenarios”

### 5.4 safety / resilience claim

不能写：

1. “fully recovers from any actuator failure”
2. “guarantees normal performance after faults”
3. “repairs failed vehicles”
4. “makes the system safe under all network and actuator failures”

建议写：

1. “redistributes bounded actuator effectiveness loss to healthy vehicles within input constraints”
2. “keeps the team-level transport task feasible in the tested actuator degradation and communication degradation scenarios”
3. “reduces the propagation of local actuator loss and network-induced inconsistency into payload-level force and pose errors”
4. “coordinates conservative fallback and progress recovery under specified safety thresholds”

### 5.5 baseline claim

不能写：

1. “baseline is weak or obsolete”
2. “baseline cannot handle robustness”
3. “our method is simply better because it is newer”

建议写：

1. “baseline addresses adaptive Koopman robustness for single nonlinear systems”
2. “the task-aligned baseline does not include explicit link-quality consensus weighting, timestamp-aware delay compensation, burst-loss/topology-aware fallback, payload-force-aware team formulation, or bounded command redistribution”
3. “the proposed framework extends the baseline mechanism from model-level adaptation to communication-driven networked team-level resilience”

## 6. 引言中贡献段落建议稿

可将贡献段落写成以下 4 点，后续由 Worker B 补 citation、Worker C 补公式、Worker D 补图表证据：

1. We develop a communication-aware delay-compensated consensus MPC framework for cooperative payload transport over degraded digital networks. Bounded delay, dropout, burst loss, jitter, topology switching, link quality, and timestamped asynchronous sampling are mapped into adaptive consensus weights, timestamp-aware neighbor prediction, and conservative fallback decisions. This differs from the Adaptive Koopman Embedding baseline, which addresses model-level adaptation for single nonlinear systems but does not explicitly embed inter-vehicle network states into consensus control; the module is validated through delay/dropout/burst/jitter/topology ablations and network-aware transport metrics.

2. We formulate a networked cooperative payload transport problem that unifies payload-center Frenet dynamics, corner-vehicle geometric consistency, flexible connection errors, payload force metrics, and a time-varying communication graph in a team-level control objective. This formulation provides the transport-specific objective and metrics needed to evaluate network-induced command dispersion, connection error, and payload force propagation, which are not present in the single-system baseline.

3. We construct a stable-projected bilinear Koopman predictor for payload-centered team dynamics, supporting both long-horizon MPC rollout and timestamp-aware prediction of delayed neighbor states under bounded model error. Compared with the task-aligned Adaptive Koopman Embedding baseline, this module targets payload-coupled vehicle-team dynamics and asynchronous neighbor prediction rather than isolated system tracking; it is validated by prediction-error, timestamp-age, and closed-loop MPC comparisons.

4. We add a safety-governed resilience extension that coordinates conservative fallback, actuator-effectiveness monitoring, bounded command redistribution, and progress recovery under specified safety thresholds. This extension is not a standalone fault-tolerant-control claim; it supports network-resilient transport when communication degradation and bounded actuator effectiveness loss coexist, and is validated through combined network/actuator degradation experiments and ablations.

## 7. Worker A 交付给后续 worker 的接口

给 Worker B：

1. 请优先补通信网络驱动控制设计文献：delay/dropout/burst/jitter/topology switching/link-quality-aware consensus MPC、event-triggered / asynchronous DMPC、timestamp-aware multi-agent prediction。
2. cooperative payload transport 和 Koopman vehicle/MPC 文献应服务于核心网络问题，不要把 Koopman 写成唯一 novelty。
3. baseline gap 必须写成“single-system adaptive Koopman robustness -> communication-driven networked cooperative transport resilience”，不要写成版本差异。

给 Worker C：

1. method 章节建议顺序：network model and communication variables, delay-compensated consensus MPC, networked payload transport formulation, Koopman predictor, safety/resilience extension, boundedness assumptions。
2. 网络模型必须显式定义 delay、dropout、burst loss、jitter、topology switching、link quality、timestamp age、asynchronous sampling，以及它们进入 consensus weights、neighbor prediction 和 fallback 的接口。
3. 稳定性证明请使用 bounded delay/dropout、bounded model error、feasible MPC、bounded switching/fallback assumptions，不要证明任意通信故障或全局渐近稳定。

给 Worker D：

1. 每个贡献至少需要一个主图或主表支撑，核心主图应展示 network variables -> consensus weights / neighbor prediction / fallback -> transport metrics 的链路。
2. 实验矩阵必须包含 full method vs task-aligned Adaptive Koopman Embedding baseline，以及 no delay compensation / no link-quality weighting / no timestamp-aware prediction / no burst-loss fallback / no stable projection / no safety redistribution 等关键消融。
3. 图表指标应覆盖 tracking error、connection error、payload force/moment、delay distribution、dropout rate、burst length、jitter、active topology、link quality、timestamp age、consensus weight evolution、fallback activation、command dispersion、solver feasibility 和 task completion。
