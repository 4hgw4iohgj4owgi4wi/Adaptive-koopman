# Round10 文献证据与贡献映射补强报告

生成日期：2026-05-11  
工作范围：仅基于 `literature_round10_status_zh.md`、`core_references_round10.bib`、Round8 `literature_evidence_matrix_zh.csv`，并用合法开放页面/DOI 页面补充少量元数据。  
适用稿件主题：Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC

## 0. 总体判断

当前证据链已经可以支撑“组合式贡献”的写法：本文不是单独首次提出 Koopman-MPC、协同运输、CAV 通信鲁棒 DMPC 或容错控制，而是把这些近三年分散发展的方向组合到四车刚性载荷协同运输问题中，并把预测学习、通信退化、连接/受力安全和故障降级放进同一个可审计闭环。

主文建议采用以下边界：

- 可以写：近三年 Koopman 车辆 MPC 多聚焦单车横向/轨迹跟踪，CAV/DMPC 多聚焦纵向 platoon/string stability，协同运输多聚焦 formation/分布式控制或平台验证；在“载荷协同运输 + Koopman 预测 + 通信退化 + 容错/安全证书”的联合问题上仍缺少闭环证据链。
- 不建议写：本文是第一个研究通信退化协同运输，或全面优于所有 CAV/DMPC/协同运输方法。
- 建议把创新表述为：从已有单线工作出发，本文补齐跨模块耦合，即学习预测器如何服务载荷运输 MPC，网络质量如何进入一致性和约束，故障/退化如何触发安全降级，实验如何用载荷中心、连接误差、受力和通信扰动指标共同审计。

## 1. 贡献 C1：稳定投影双线性 Koopman-MPC 用于多车载荷协同运输

### 近三年相似工作

1. Jin Sung Kim, Yingshuai Quan, Chung Choo Chung, Woo Young Choi, "K-SMPC: Koopman Operator-Based Stochastic Model Predictive Control for Enhanced Lateral Control of Autonomous Vehicles", IEEE Access, 2025. DOI: `10.1109/ACCESS.2025.3530984`; 开放记录：<https://research.chalmers.se/en/publication/545084>; arXiv: <https://arxiv.org/abs/2310.10214>
2. Xinglong Chen, Chen Lv, "Incorporating ESO into Deep Koopman Operator Modelling for Control of Autonomous Vehicles", arXiv, 2024. 链接：<https://arxiv.org/abs/2405.10157>
3. Fabian Philipp, Manuel Schaller, Karl Worthmann, Sebastian Peitz, Feliks Nueske, "Error Bounds for Kernel-Based Approximations of the Koopman Operator", arXiv, 2023. 链接：<https://arxiv.org/abs/2301.08637>
4. Vojtech Cibulka, Milan Korda, Tomas Hanis, Martin Hromcik, "Model Predictive Control of a Vehicle Using Koopman Operator", arXiv, 2021. 链接：<https://arxiv.org/abs/2103.04978>。该文早于近三年，只适合作为基础背景，不应作为“最新相似工作”的核心证据。

### 原文做了什么

Kim 等 2025 用 EDMD 近似 Koopman 算子来表示车辆非线性动力学，并把 Koopman 近似误差作为概率信号纳入 stochastic MPC；其开放记录还说明作者讨论了递归可行性、显式首步状态约束和鲁棒控制不变集，并用 CarSim 验证单车动态车道保持性能。Chen 和 Lv 2024 用深度 Koopman basis 表示自动驾驶车辆动力学，并将 ESO 用于补偿建模残差，服务单车轨迹跟踪控制。Philipp 等 2023 从理论层面讨论有限数据下 Koopman 近似误差/预测误差界，为“学习预测器需要误差边界或保守保护”提供依据。

### 本文在其基础上改了什么

本文不只把 Koopman 预测器用于单车横向或轨迹跟踪，而是将双线性 Koopman lifting 嵌入四车刚性载荷协同运输 MPC。相对于 K-SMPC 的单车概率误差处理，本文应强调三点增量：一是稳定投影/谱约束用于避免长 horizon 预测漂移；二是双线性结构显式保留控制输入对 lifted dynamics 的影响；三是预测误差不只影响车辆轨迹，还通过连接点误差、载荷中心误差和受力指标进入安全审计。

### 应写入引言/贡献/方法的句子

引言可写：

> Recent Koopman-MPC studies have demonstrated the value of data-driven linear predictors for autonomous-vehicle control, especially in lateral or trajectory-tracking tasks. However, these studies are mostly formulated for a single vehicle and do not address payload-coupled multi-vehicle transport under degraded V2V communication.

贡献可写：

> 本文提出稳定投影双线性 Koopman-MPC，将车辆-载荷耦合动力学提升为可用于约束预测控制的双线性模型，并通过谱投影和闭环证书限制学习预测误差在长时域协同运输中的放大。

方法可写：

> Koopman 预测器的作用不是替代物理约束，而是为 MPC 提供局部可优化的 lifted dynamics；连接误差、载荷中心误差和控制约束仍在原始物理空间中审计，以避免学习模型误差被隐藏在 lifted space 中。

### 还缺哪些全文/元数据

- `core_references_round10.bib` 中 K-SMPC 作者字段与开放记录不一致：开放记录显示为 Jin Sung Kim、Yingshuai Quan、Chung Choo Chung、Woo Young Choi；当前 BibTeX 写作 Hyunki Kim、Yujiao Quan、Chung Choo Chung。正式提交前应以 IEEE/Crossref 元数据为准更新，但本 worker 不修改 bib。
- Chen 和 Lv 2024、Philipp 等 2023 当前是 arXiv 条目；若 2026 年已有期刊/会议正式版本，应在最终参考文献中替换为正式版本。
- 本文若主张“稳定投影”带来闭环收益，需要在实验或附录中给出无投影/无证书 gate 的 ablation，否则只能写成方法设计而非已充分证明的性能贡献。

## 2. 贡献 C2：载荷协同运输建模、连接误差与受力审计

### 近三年相似工作

1. Henrik Ebel, Mario Rosenfelder, Peter Eberhard, "Cooperative Object Transportation with Differential-Drive Mobile Robots: Control and Experimentation", Robotics and Autonomous Systems, 2024. DOI: `10.1016/j.robot.2023.104612`; 链接：<https://doi.org/10.1016/j.robot.2023.104612>
2. Quanwei Wu, Xiangyu Wang, Xuechao Qiu, "Embedded Technique-Based Formation Control of Multiple Wheeled Mobile Robots with Application to Cooperative Transportation", Control Engineering Practice, 2024. DOI: `10.1016/j.conengprac.2024.106002`; 链接：<https://doi.org/10.1016/j.conengprac.2024.106002>
3. "Multi-Objective Cooperative Transportation for Reconfigurable Robot Using Isomorphic Mapping Multi-Agent Reinforcement Learning", Mechatronics, 2024. DOI: `10.1016/j.mechatronics.2024.103206`; 链接：<https://doi.org/10.1016/j.mechatronics.2024.103206>
4. Agung, "Advancements in Cooperative Mobile Robots Control Strategies for Large-Scale Material Transport: Review", Kinetik, 2024. DOI: `10.22219/kinetik.v9i4.1992`; 链接：<https://doi.org/10.22219/kinetik.v9i4.1992>
5. "Intelligent Multi-Robot Collaborative Transport System", Urban Lifeline, 2024. DOI: `10.1007/s44285-024-00026-z`; 链接：<https://doi.org/10.1007/s44285-024-00026-z>

### 原文做了什么

Ebel 等 2024 面向差速移动机器人非抓取式协同运输，强调分布式决策、非完整约束、多体动力学、分布式预测控制和分布式优化，并包含真实硬件实验。Wu 等 2024 研究多轮式移动机器人通过 formation control 搬运共享物体，用 embedded technique 将通信拓扑和 WMR 动力学分开处理，由分布式信号发生器生成各机器人期望轨迹。Mechatronics 2024 条目以同构映射多智能体强化学习处理可重构机器人多目标运输决策，更偏重任务决策与重构机制。Kinetik 2024 综述则用于说明多移动机器人在大规模物料运输中的应用背景和控制策略谱系。

### 本文在其基础上改了什么

本文的增量不应写成“比协同运输控制更通用”，而应写成“把协同运输安全指标与网络化预测控制耦合”。已有协同运输工作多关注 formation、分布式决策、非完整约束或平台实验；本文把四车-刚性载荷的团队中心、角点连接误差、载荷受力和车辆控制量放入同一个 MPC 证据链，并进一步把通信质量、时延/丢包和故障降级纳入这些指标的闭环影响分析。

### 应写入引言/贡献/方法的句子

引言可写：

> Recent cooperative-transport studies have advanced formation-based, optimization-based, and learning-based coordination for mobile robots. Nevertheless, most of them treat communication as an ideal or secondary implementation condition, while the interaction between communication degradation, payload connection safety, and force/load auditing remains insufficiently characterized.

贡献可写：

> 本文面向四车刚性载荷协同运输建立统一的控制审计指标，将载荷中心跟踪、角点连接误差、车辆输入约束和载荷受力共同纳入评价，而不是只报告 formation error 或单车轨迹误差。

方法可写：

> 在 MPC 目标函数和约束中，团队中心误差用于描述任务完成度，角点连接误差用于描述几何安全，载荷受力/方向分量用于审计运输过程中的物理可接受性；三类指标应分别报告，避免用单一轨迹误差替代载荷安全。

### 还缺哪些全文/元数据

- Mechatronics 2024、Urban Lifeline 2024 条目的作者元数据仍需从 publisher/Crossref 正式导出补全；当前 Round10 bib 用 `note` 标记是合理的临时状态。
- 若使用 Ebel 等 2024 作为强相似工作，建议最终稿引用其硬件实验和分布式预测控制/优化亮点，但不要暗示其考虑了本文的通信退化和故障容错。
- 若本文方法没有真实硬件实验，应避免与 RAS 2024 的硬件验证正面对标；可表述为“面向网络退化和故障注入的仿真闭环审计补充”。

## 3. 贡献 C3：通信退化、时延补偿与质量感知一致性 MPC

### 近三年相似工作

1. Yuhang Bian 等, "Distributed Model Predictive Control of Connected and Automated Vehicles With Markov Packet Loss", IEEE Transactions on Transportation Electrification, 2025. IEEE 链接：<https://ieeexplore.ieee.org/document/10770256/>
2. Hao Zeng, Zehua Ye, Dan Zhang, "Dynamic Event-Triggering-Based Distributed Model Predictive Control of Heterogeneous Connected Vehicle Platoon Under DoS Attacks", ISA Transactions, 2024. DOI: `10.1016/j.isatra.2024.07.011`; 链接：<https://doi.org/10.1016/j.isatra.2024.07.011>
3. Lei Yang, Zhanbo Sun, Yafei Liu, Linbin Chen, "Robust Control for Connected Automated Vehicle Platoon with Multiple-Predecessor Following Topology Considering Communication Loss", Transportation Research Part B: Methodological, 2025. DOI: `10.1016/j.trb.2025.103212`; 链接：<https://doi.org/10.1016/j.trb.2025.103212>
4. Jiading Bao, Zishan Lin, Hui Jing, Huanqin Feng, Xiaoyuan Zhang, Ziqiang Luo, "Research on Longitudinal Control of Electric Vehicle Platoons Based on Robust UKF-MPC", Sustainability, 2024. DOI: `10.3390/su16198648`; 链接：<https://doi.org/10.3390/su16198648>
5. Sidharth Bhanu Kamtam, Qian Lu, Faouzi Bouali, Olivier C. L. Haas, Stewart Birrell, "Network Latency in Teleoperation of Connected and Autonomous Vehicles: A Review of Trends, Challenges, and Mitigation Strategies", Sensors, 2024. DOI: `10.3390/s24123957`; 链接：<https://doi.org/10.3390/s24123957>
6. Xiaoran Dai, G. P. Liu, Wenshan Hu, Qijun Deng, "Distributed Predictive Control for Networked DC Microgrids With Communication Delays and Packet Dropouts", IEEE Transactions on Industrial Informatics, 2024. DOI: `10.1109/TII.2024.3498095`

### 原文做了什么

Bian 等 2025 研究 Markov packet loss 下 CAV 分布式 MPC。Zeng 等 2024 针对异构 connected vehicle platoon 在 DoS 攻击下的 DMPC，设计动态事件触发机制以降低通信和计算负担，并面向纵向车队安全控制。Yang 等 2025 针对多前车跟随拓扑下通信损失提出鲁棒控制方法，并推导局部稳定和 string stability 条件。Bao 等 2024 在 V2V 随机通信延迟、数据丢失和外部扰动下设计 robust UKF-MPC 纵向队列控制，并用 CarSim/Simulink 验证。Kamtam 等 2024 综述 CAV 远程驾驶中的网络延迟、影响链路和缓解策略，是 DCN/网络延迟动机的背景证据。Dai 等 2024 虽然对象是 DC 微电网，但说明“通信时延/丢包进入分布式预测控制设计”是更广泛的网络化控制问题。

### 本文在其基础上改了什么

这些 CAV/DMPC 工作主要服务纵向 platoon、车距安全和 string stability；本文不应与其争夺 platoon 理论优越性，而应转到协同运输问题。本文的增量是把 delay/dropout/quality 从“前车信息是否可用”扩展为“协同运输连接安全和载荷跟踪质量的调权变量”：通信质量影响一致性项、邻居状态预测、fallback 权重和安全约束激活；评价指标从 spacing/string stability 改为载荷中心误差、角点连接误差、车辆/载荷受力、控制平滑性和约束满足。

### 应写入引言/贡献/方法的句子

引言可写：

> Communication-aware DMPC for CAVs has recently considered Markov packet loss, DoS attacks, communication loss, and random delays, but the dominant evaluation target remains longitudinal platooning, spacing regulation, or string stability. Cooperative payload transport imposes different safety variables because communication degradation can directly distort payload geometry and contact/connection forces.

贡献可写：

> 本文提出时延补偿一致性 MPC，将链路质量、时延预测和丢包降级映射到协同运输的一致性权重与安全约束中，使通信退化不再只是外部扰动，而是闭环优化中可审计的调度变量。

方法可写：

> 当邻居信息延迟或丢失时，控制器使用预测邻居状态和通信质量权重构造一致性误差；若链路质量低于阈值，则降低对不可靠邻居的跟踪权重并触发保守约束/fallback，以优先保持连接误差和载荷受力在可接受范围内。

### 还缺哪些全文/元数据

- Bian 等 2025 的 DOI 仍需从 IEEE/Crossref 正式页面补全；当前只有 IEEE document 链接。
- Zeng 等 2024 的作者已从开放索引补为 Hao Zeng、Zehua Ye、Dan Zhang；正式 bib 仍需以 ScienceDirect/Crossref 导出为准。
- Dai 等 2024 在 Round10 bib 中作者写作 Lingling Dai、Shichao Liu、Jianqiang Hu、Fang Deng，但开放索引显示 Xiaoran Dai、G. P. Liu、Wenshan Hu、Qijun Deng；正式提交前必须核对 IEEE 元数据，避免引用作者错误。
- 本文若写“delay-compensated”，方法中必须给出时延状态外推、邻居预测或补偿公式；如果只有随机退化仿真而无明确补偿项，应降级为“delay/dropout-aware”。

## 4. 贡献 C4：FDI/FTC、执行器效率估计与证书保护

### 近三年相似工作

1. Hao Sun, Li Dai, Giuseppe Fedele, Boli Chen, "A Convex and Robust Distributed Model Predictive Control for Heterogeneous Vehicle Platoons", European Journal of Control, 2024/2025 issue. DOI: `10.1016/j.ejcon.2024.101023`; 链接：<https://doi.org/10.1016/j.ejcon.2024.101023>
2. Jiading Bao 等 2024 robust UKF-MPC 纵向队列控制。DOI: `10.3390/su16198648`; 链接：<https://doi.org/10.3390/su16198648>
3. Giovanni Gasparino, Harsh Mishra, Girish Chowdhary, "Unmatched Uncertainty Mitigation Through Neural Network Supported Model Predictive Control", arXiv, 2023. 链接：<https://arxiv.org/abs/2304.11315>
4. Dai 等 2024 网络化预测控制。DOI: `10.1109/TII.2024.3498095`

### 原文做了什么

Sun 等 2024/2025 面向异构车辆队列提出凸化、tube-based robust DMPC，考虑 time-varying leader speed、多维不确定性、建模不确定性和测量扰动，并给出理论性质和数值比较。Bao 等 2024 通过 robust UKF 状态估计和 MPC 反馈补偿处理 V2V 延迟、丢包和扰动。Gasparino 等 2023 用神经网络支持 MPC 缓解 unmatched uncertainty，为 learning + MPC 的不确定性补偿思路提供背景。Dai 等 2024 说明网络约束下预测控制可显式处理通信时延和丢包。

### 本文在其基础上改了什么

Round8/round10 证据中还没有一条足够贴近“多车协同运输执行器 FDI/FTC”的近三年核心文献，因此 C4 的外部支撑目前偏弱。可防守写法是把 FDI/FTC 作为本文闭环安全机制的一部分，而不是作为独立超越现有 FTC 文献的主创新。本文可强调：执行器效率估计、控制重分配、故障切换与 Lyapunov/ISS 型证书记录被嵌入 Koopman-MPC 闭环，并与通信退化和载荷连接约束共同触发 fallback。

### 应写入引言/贡献/方法的句子

引言可写：

> Robust and learning-supported MPC methods have addressed model uncertainty, communication disturbance, and estimation errors in networked vehicles, yet actuator-efficiency degradation and safety-certificate-triggered fallback are rarely studied together with payload-coupled cooperative transport.

贡献可写：

> 本文将执行器效率估计、容错控制重分配和证书保护嵌入同一 Koopman-MPC 闭环，使通信退化或执行器故障发生时，控制器可从性能优先切换到连接/受力安全优先的降级模式。

方法可写：

> FDI/FTC 模块不改变任务层目标，而是修正可用控制效率并重分配输入约束；当证书项显示预测误差、约束裕度或故障残差超过阈值时，控制器进入保守 fallback，优先保证连接误差、载荷受力和输入约束。

### 还缺哪些全文/元数据

- 需要额外补 1-2 篇近三年“车辆/多机器人 actuator fault tolerant MPC 或 FDI/FTC”正式期刊/会议文献，否则 C4 的文献基础比 C1-C3 弱。
- 需要明确本文 FDI 是残差检测、效率参数估计、还是故障模式分类；FTC 是控制重分配、约束收缩、还是备用控制律切换。没有这两个定义，贡献句会显得像工程功能堆叠。
- 需要在实验中对应故障注入、效率估计曲线、控制重分配、载荷受力/连接误差恢复和证书触发时刻。若没有，主文中只能写“包含安全降级机制”，不要写“系统性解决执行器故障”。

## 5. 可直接写入主文的贡献映射段落

### 引言末尾总括段

可写：

> 综上，Koopman-MPC 已在单车预测控制中显示出处理非线性车辆动力学的潜力，协同运输研究已发展出 formation、分布式优化和学习型协调方法，CAV/DMPC 文献也开始处理 packet loss、DoS、communication loss 和 network latency。然而，这些方向通常分别处理单车控制、纵向 platoon 或理想/弱通信假设下的协同运输，尚缺少一个面向载荷耦合任务的统一闭环框架，将学习预测、通信退化、连接/受力安全和故障降级同时纳入可验证控制链。为此，本文提出稳定投影双线性 Koopman 学习与时延补偿一致性 MPC 相结合的协同运输控制方法，并通过连接误差、载荷中心误差、受力审计、通信退化和故障注入实验验证其网络韧性。

### 贡献列表建议

1. 提出稳定投影双线性 Koopman 预测器，并将其嵌入四车刚性载荷协同运输 MPC，使数据驱动模型不仅服务单车轨迹预测，还服务载荷中心、连接误差和输入约束的联合优化。
2. 提出通信质量感知的时延补偿一致性 MPC，将 packet loss/delay/link quality 映射为邻居预测、一致性权重和保守 fallback 触发条件，面向协同运输而非单纯 longitudinal platoon 评价网络退化影响。
3. 建立载荷协同运输安全审计链，将团队中心跟踪、角点连接误差、载荷受力/方向分量和控制平滑性共同作为主指标，避免只用 formation error 或 spacing error 证明运输安全。
4. 集成执行器效率估计、FTC 重分配和证书保护机制，在通信退化或执行器故障下触发保守降级模式；该点目前应作为“安全增强模块”表述，除非补齐专门 FDI/FTC 文献和故障 ablation。

## 6. 推荐引用位置

| 稿件位置 | 建议引用 | 用途 |
|---|---|---|
| 引言第 1 段：Koopman 学习与车辆控制 | Kim et al. 2025; Chen and Lv 2024; Philipp et al. 2023 | 说明 Koopman 车辆预测控制和误差处理已有基础，但多为单车/理论问题。 |
| 引言第 2 段：协同运输 | Ebel et al. 2024; Wu et al. 2024; Mechatronics 2024; Kinetik 2024 review | 说明协同运输已由 formation/优化/RL 推进，但网络退化耦合不足。 |
| 引言第 3 段：通信退化与 DMPC | Bian et al. 2025; Zeng et al. 2024; Yang et al. 2025; Bao et al. 2024; Kamtam et al. 2024 | 说明 packet loss、DoS、communication loss 和 latency 是 CAV/网络控制热点。 |
| 方法 Koopman 小节 | Kim et al. 2025; Philipp et al. 2023 | 支撑误差、递归可行性/保守保护、稳定投影动机。 |
| 方法 DCC-MPC 小节 | Zeng et al. 2024; Yang et al. 2025; Bao et al. 2024 | 支撑时延/丢包/通信损失进入 MPC 或鲁棒控制。 |
| 方法安全/FTC小节 | Sun et al. 2024/2025; Gasparino et al. 2023; Dai et al. 2024 | 暂时支撑 robust/learning/networked MPC，不足以独立支撑 FDI/FTC，需要追加专门文献。 |
| 实验讨论 | Ebel et al. 2024; CAV/DMPC 组文献 | 解释本文评价指标为何不是 string stability，而是载荷中心、连接误差和受力审计。 |

## 7. 仍缺的全文/元数据清单

| 缺口 | 影响 | 建议处理 |
|---|---|---|
| K-SMPC BibTeX 作者与开放记录不一致 | 会造成引用错误，影响可信度 | 正式提交前从 IEEE/Crossref 导出并替换 bib。 |
| Dai et al. 2024 作者元数据疑似不一致 | 会造成网络预测控制引用错误 | 以 IEEE Xplore DOI `10.1109/TII.2024.3498095` 元数据为准核对。 |
| Bian et al. 2025 缺 DOI | CAV Markov packet loss 证据不完整 | 从 IEEE 记录或 Crossref 检索 DOI。 |
| Mechatronics 2024、Urban Lifeline 2024 作者未完全确认 | 协同运输相关工作表不完整 | 从 publisher/Crossref 导出正式 BibTeX。 |
| C4 缺近三年 actuator FDI/FTC 直接文献 | 容错贡献外部支撑弱 | 追加车辆/多机器人 actuator fault tolerant MPC、FDI、control allocation 文献。 |
| arXiv 条目可能已有正式版本 | 参考文献档次偏弱 | 检查 Chen and Lv 2024、Philipp et al. 2023、Gasparino et al. 2023 是否已有期刊/会议版。 |
| 缺全文核验的条目 | 无法精确写“定理/假设/实验设置” | 主文避免过细描述，只写开放摘要/页面可验证内容。 |

## 8. 最终写作红线

- 不要写“首次提出通信退化协同运输控制”；应写“联合处理 Koopman 预测、通信退化、故障降级和载荷安全的证据链仍不足”。
- 不要写“全面优于现有 DMPC/CAV 方法”；除非有公平同场 baseline，否则只写“在本文载荷协同运输场景下改善连接/受力/跟踪指标”。
- 不要把 CAV platoon 的 string stability 直接等同为本文稳定性；本文更适合写 input-to-state practical stability、uniform ultimate boundedness 或证书约束下的实践有界。
- 不要把协同运输文献说成没有考虑安全；应具体说其安全指标与本文不同，通常不是通信质量、载荷受力和 FTC/fallback 的联合审计。
- C4 在补文献前应降低语气：从“主要理论贡献”降为“安全增强与降级保护模块”。
