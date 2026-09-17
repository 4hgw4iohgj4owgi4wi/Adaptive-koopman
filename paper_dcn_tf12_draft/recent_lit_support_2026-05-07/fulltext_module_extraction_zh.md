# 合规全文补充与模块机理提炼

生成时间：2026-05-07

本文档用于支撑中文稿中“四个贡献均建立在近三年已发表工作基础上，并进一步改进”的写法。整理原则是：优先使用开放获取 PDF、作者公开稿、出版社开放网页和 arXiv 预印本；未能合规获取全文的论文只保留 DOI 与作用，不展开细节。

## 1. 当前全文获取状态

已落地全文如下。

- Singh et al., Adaptive Koopman Embedding：arXiv 预印本已下载，正式 IJRR 版 DOI 已确认。本地文件为 `pdfs/Singh2024_arXiv_Adaptive_Koopman_Embedding.pdf`，用于支撑 baseline 与在线自适应 Koopman。
- Kennel-Maushart and Coros, Payload-Aware Trajectory Optimisation：作者公开稿已下载。本地文件为 `pdfs/Kern-Maushart2024_RAL_PayloadAware_Trajectory_Optimisation.pdf`，用于支撑载荷感知、受力约束与协同搬运。
- Abtahi et al., Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame：arXiv 预印本已下载，IEEE Access DOI 已确认。本地文件为 `pdfs/Abtahi2025_arXiv_Deep_Bilinear_Koopman_Frenet.pdf`，用于支撑 Frenet 车辆 Koopman 与实时 MPC。
- Shahab et al., Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities：MDPI 开放 PDF 已下载。本地文件为 `pdfs/Shahab2025_Robotics_WMR_FaultTolerance.pdf`，用于支撑轮式机器人编队容错与执行器有效性损失。
- Zou et al., Event-Triggered and Adaptive ADMM-Based DMPC for Vehicle Platoon：MDPI 开放 PDF 已下载。本地文件为 `pdfs/Vehicles2025_EventTriggered_ADMM_DMPC_Platoon.pdf`，用于支撑事件触发、分布式 MPC 与通信负载控制。
- Li et al., Data-Driven Event-Triggered Predictive Control with Time-Varying Delays：MDPI 开放 PDF 已下载。本地文件为 `pdfs/Li2026_ApplSci_DataDriven_EventTriggered_Predictive_Delay_MAS.pdf`，用于支撑数据驱动预测控制、通信时延与多智能体一致性。

尚未落地全文但已确认 DOI 或开放网页的文献如下。

- Muhammed et al., Real-Time Decentralized MPC for Cooperative Multi-Robot Object Transport：Nature 网页开放，脚本下载 PDF 被站点挑战页拦截；用于支撑协同运输实验验证。
- Muhammed et al., Multi-Robot Object Transport in Constrained Environments：DOI 与 Scholar 题录已确认，未找到合规全文；用于支撑受约束多机器人运输 MPC。
- Zhao et al., Deep Bilinear Koopman MPC：DOI 与题录已确认，未找到合规全文；用于支撑双线性 Koopman MPC。
- Zhao et al., Distributed Cloud MPC with Delay Compensation：DOI 与题录已确认，未找到合规全文；用于支撑时延补偿 distributed MPC。
- Huang et al., Distributed Predictive Control with Communication Delays：DOI 与题录已确认，未找到合规全文；用于支撑通信时延与多智能体预测控制。
- Hu et al., Fault Tolerant Control for UAV Formation Based on D-NMPC：DOI 与题录已确认，未找到合规全文；用于支撑分布式 NMPC 容错。
- Zhang et al., Virtual Coupling Train Fault-Tolerant Control：DOI 与题录已确认，未找到合规全文；用于支撑执行器有效性损失与交通系统容错。
- Li et al., Hierarchical Constraint-Based Formation Control：DOI 与题录已确认，未找到合规全文；用于支撑层级约束协同运输。

## 2. 逐篇提炼

### 2.1 Singh et al.: Adaptive Koopman Embedding

原文做了什么：该工作提出“离线 Koopman 嵌入 + 在线自适应修正”的控制框架。离线阶段用名义系统数据训练 Koopman lifting 与名义矩阵；在线阶段在部署过程中利用最新窗口数据修正 lifted dynamics 中的矩阵增量，使模型能够适应参数变化、测量噪声和未建模扰动。其实验对象包括耦合摆和 3R 机械臂，重点证明 adaptive Koopman 相比 nominal Koopman 在噪声、参数扰动和外部扰动下具有更强鲁棒性。

原文没有覆盖什么：验证对象仍然是单体或单系统动力学，没有处理多车共享刚性载荷时的角点几何一致性、连接误差、载荷受力约束、通信时延、丢包和单车执行器退化。它回答的是“模型失配下 Koopman 控制如何变稳”，还没有回答“多个执行体通过同一载荷耦合时，局部失配如何被团队吸收”。

本文怎么改进：本文以该工作作为 baseline 主线，但把自适应 Koopman 嵌入放入四车刚性载荷运输任务中。具体改进包括：将 lifted state 扩展到团队中心、单车角点、连接误差和载荷指标；使用 24 维可学习观测、31 维 lifted state、学习型解码矩阵和谱半径稳定投影；在在线自适应之外加入通信质量感知一致性、时延补偿、退化回退和故障重分配。

可写入论文的句子：在 Singh 等 adaptive Koopman embedding 的“离线名义模型 + 在线矩阵修正”框架基础上，本文进一步将 Koopman 自适应从单体非线性系统推广到四车刚性载荷运输系统，并通过稳定投影、团队几何状态组织和网络/故障补偿模块，使 lifted MPC 能够同时处理模型失配、通信不一致和执行器退化。

### 2.2 Kennel-Maushart and Coros: Payload-Aware Trajectory Optimisation

原文做了什么：该工作面向非完整移动多机器人操纵，提出载荷感知的双层轨迹优化方法。下层根据机器人和载荷构型计算支撑力、法向力和稳定性相关力学量，上层利用这些力学量形成转向和防倾覆约束，从而规划更适合真实载荷搬运的移动机器人轨迹。

原文没有覆盖什么：该工作主要是轨迹优化问题，重点在开环或规划层的载荷感知、安全约束和防倾覆效果，并没有把数据驱动动力学模型、在线自适应、通信退化和执行器故障统一进闭环 MPC。它说明“载荷受力应该进入规划”，但没有解决“载荷受力如何在网络退化和单车故障下被闭环控制器持续约束”。

本文怎么改进：本文吸收其“载荷受力不能被忽略”的思想，但将载荷指标从轨迹优化约束推进到闭环协同 MPC 评价链。本文显式构造四角点几何映射、连接柔顺误差、载荷纵横向力、偏航力矩和法向载荷指标，并在故障重分配后继续检查载荷受力是否被放大。

可写入论文的句子：受 Kennel-Maushart 和 Coros 的载荷感知轨迹优化启发，本文不再仅以团队中心轨迹误差评价协同运输，而是进一步将连接误差、载荷横纵向力、偏航力矩和法向载荷作为闭环验证指标，用以说明所提故障补偿并未以过大的载荷冲击为代价。

### 2.3 Abtahi et al.: Deep Bilinear Koopman Vehicle Control in Frenet Frame

原文做了什么：该工作面向自动驾驶车辆，在 Frenet 坐标系下构建 deep bilinear Koopman 车辆模型，并将其嵌入实时 MPC。其网络强调多步预测损失和双线性 lifted dynamics，并通过 cumulative error regulator 缓解长时域误差累积；实验使用 CarSim RT 与 dSPACE HIL 验证实时可行性。

原文没有覆盖什么：原文聚焦单车车辆控制，核心问题是车辆非线性动力学在 Frenet 坐标下如何被 Koopman 模型高效预测。它没有处理多车共同搬运刚性载荷时的相对构型、载荷受力闭合、通信时延和单车故障重分配。

本文怎么改进：本文继承“Frenet 坐标 + 双线性 Koopman + MPC”的技术路线，但将对象从单车路径跟踪扩展为四车载荷中心路径跟踪。本文的 lifted state 不只包含车辆状态，还包含团队中心误差、角点映射、连接误差和故障补偿后的团队控制量；同时用稳定投影约束 Koopman 主干，使其更适合长时域团队 MPC。

可写入论文的句子：与 Abtahi 等针对单车 Frenet 控制的 deep bilinear Koopman MPC 不同，本文将 Frenet Koopman 建模提升到四车刚性载荷运输层面，使 lifted 模型同时描述载荷中心运动、角点车辆误差和团队等效控制输入，并进一步加入通信与故障容错机制。

### 2.4 Shahab et al.: Fault-Tolerant Formation Control of Wheeled Mobile Robots

原文做了什么：该工作研究轮式移动机器人编队在执行器故障下的队形保持能力。作者建立 WMR 运动学模型，采用 leader-follower 编队控制，并系统注入不同程度的执行器有效性损失，例如 80%、60% 和 40% 容量，以分析故障强度对队形恢复时间、位置精度和控制器增益选择的影响。

原文没有覆盖什么：原文关注一般 WMR 编队在执行器损失下如何维持队形，但没有刚性载荷耦合，也没有把故障车辆的控制亏损重新分配给健康车辆来维持团队等效力和等效力矩。它说明“执行器损失会破坏编队”，但没有给出载荷运输中“故障亏损如何被团队冗余吸收”的控制结构。

本文怎么改进：本文将单车转角和加速度衰减建模为持续执行器退化，并通过故障重分配把故障车未能实现的控制命令映射给健康车辆承担。这样故障不再只是单车局部误差，而是被显式转化为团队等效控制闭合问题。

可写入论文的句子：在 Shahab 等关于轮式移动机器人执行器有效性损失对编队性能影响的分析基础上，本文进一步把单车故障建模为四车载荷运输中的团队控制亏损，并设计故障重分配机制，使健康车辆能够补偿故障车辆对载荷等效力和等效力矩的缺口。

### 2.5 Zou et al.: Event-Triggered and Adaptive ADMM-Based DMPC for Vehicle Platoon

原文做了什么：该工作提出事件触发与自适应 ADMM 结合的车队 distributed MPC 框架。其目标是降低分布式车队控制中的通信调用和计算负担，同时保持车距、速度和队列一致性。事件触发机制用于减少不必要的控制更新，自适应 ADMM 用于提高分布式优化求解效率。

原文没有覆盖什么：原文主要面向纵向车队，不涉及多车横向协同搬运、刚性载荷受力、角点几何约束或单车执行器退化。它解决的是“车队 DMPC 如何更省通信和计算”，但没有覆盖“通信质量下降时团队控制命令如何保持几何一致和载荷受力平顺”。

本文怎么改进：本文吸收其“通信/计算不应默认无限可靠”的思想，但没有简单采用事件触发降频，而是将通信质量、时延估计和退化回退写入团队 MPC 控制律。对于四车载荷运输，本文更关心通信退化是否放大连接误差、横向力和偏航力矩，因此通信保护模块与载荷受力指标绑定验证。

可写入论文的句子：与 Zou 等通过事件触发和自适应 ADMM 减少车队 DMPC 通信/计算负担不同，本文将通信质量直接转化为团队一致性权重和时延前推补偿，用于抑制多车载荷运输中由链路退化引发的角点命令离散、连接误差放大和载荷侧向冲击。

### 2.6 Li et al.: Data-Driven Event-Triggered Predictive Control with Time-Varying Delays

原文做了什么：该工作研究未知动力学和时变通信时延下的离散多智能体一致性问题，提出数据驱动事件触发预测控制框架。其核心思想是利用历史数据构造预测模型，结合动态阈值事件触发机制减少通信负载，并在理论上证明一致性。

原文没有覆盖什么：该工作关注一般离散多智能体一致性，系统层面较抽象，没有面向车辆动力学、Frenet 路径跟踪、载荷耦合、MPC 约束和执行器故障补偿。它说明“数据驱动预测控制可以处理时变通信时延”，但没有展示该思想如何落入具体车辆协同运输任务。

本文怎么改进：本文把“数据驱动预测 + 通信时延处理”的思想落到四车载荷运输中：预测模型由稳定投影 Koopman 网络提供，通信退化通过质量感知一致性和时延补偿进入控制律，最终用团队轨迹、单车误差、连接误差和载荷受力证明模块效果。

可写入论文的句子：受 Li 等数据驱动事件触发预测一致性工作的启发，本文将通信时延处理从抽象多智能体一致性问题推进到车辆-载荷耦合系统中，并用 Koopman lifted dynamics 作为可优化预测模型，使通信补偿能够直接服务于路径跟踪、连接保持和载荷受力约束。

### 2.7 Muhammed et al.: Real-Time Decentralized MPC for Cooperative Multi-Robot Object Transport

原文做了什么：该工作给出了实时去中心化 MPC 在多机器人物体运输中的实验验证，说明预测控制已成为协同搬运任务中的重要路线。它强调多机器人对象运输中的实时性、去中心化求解和实验可行性。

原文没有覆盖什么：该工作没有采用 Koopman 升维模型，也没有把通信质量感知、时延补偿、执行器退化和故障重分配统一进控制栈。其重点是协同运输 MPC 的实验验证，而不是网络受扰和单车持续退化条件下的学习型鲁棒控制。

本文怎么改进：本文以该类协同运输 MPC 为任务背景，但进一步将数据驱动 Koopman 预测模型、通信补偿和故障容错整合起来。相对单纯去中心化 MPC，本文更强调当某一车辆能力下降或链路质量下降时，团队控制如何通过模型自适应和冗余重分配维持任务完成。

可写入论文的句子：在 Muhammed 等实时去中心化 MPC 协同运输验证的基础上，本文进一步关注通信时延、链路质量波动和单车执行器退化共同存在的困难场景，并引入 Koopman 自适应预测与故障重分配机制，以提升团队级鲁棒性。

## 3. 四个贡献的最终支撑关系

贡献1：四车刚性载荷 Frenet 团队模型。
主要支撑文献为 Muhammed 2024/2026 和 Kennel-Maushart 2024。本文真正向前推进的点是：从一般协同运输 MPC 和载荷感知轨迹优化，推进到四车刚性载荷中心、角点、连接误差和载荷受力统一建模。

贡献2：稳定投影双线性 Koopman 主干。
主要支撑文献为 Singh 2025、Zhao 2024 和 Abtahi 2026。本文真正向前推进的点是：从单体 adaptive Koopman 和单车 Frenet Koopman，推进到团队 lifted dynamics 与稳定投影 Koopman MPC。

贡献3：通信补偿与故障重分配控制栈。
主要支撑文献为 Zhao 2025、Zou 2025、Li 2026、Huang 2025 和 Shahab 2025。本文真正向前推进的点是：从车队/多智能体通信时延与 WMR 容错，推进到四车载荷运输中的通信质量感知一致性、时延补偿、退化回退和故障重分配。

贡献4：分层实验证据链。
主要支撑文献为 Singh 2025、Muhammed 2026 和 Kennel-Maushart 2024。本文真正向前推进的点是：从单一跟踪指标，推进到离线学习、预测误差、团队轨迹、单车误差、连接误差、载荷受力、通信/故障时间线和消融机理的跨层验证。

## 4. 建议直接回填到正文的表述

1. Koopman 主干段：本文并非从零构造 Koopman 控制器，而是在 adaptive Koopman embedding、deep bilinear Koopman MPC 和 Frenet vehicle Koopman control 的基础上，将升维预测模型扩展到四车载荷中心与角点车辆共同组成的团队状态，并加入谱半径稳定投影以提高长时域 MPC 的滚动可用性。

2. 协同运输建模段：已有协同运输 MPC 和载荷感知轨迹优化工作说明，多机器人搬运不能只看中心轨迹，还必须考虑对象约束和载荷力学；本文进一步将这些因素写入四车刚性载荷 Frenet 团队模型，并用连接误差、载荷横向力和偏航力矩评价闭环控制质量。

3. 通信韧性段：近期车队 DMPC 和多智能体预测控制研究已经表明，通信时延、触发频率和带宽约束会影响协同控制稳定性；本文进一步把通信质量转化为一致性权重、时延前推预测和退化回退策略，用于抑制多车载荷运输中的角点命令离散和载荷冲击。

4. 故障容错段：已有 WMR 和交通系统容错研究证明执行器有效性损失会破坏编队和协同控制性能；本文进一步将单车转角/加速度衰减建模为团队控制亏损，并通过故障重分配把亏损映射给健康车辆，从而保持载荷等效力和等效力矩闭合。

## 5. 仍需全文的文献

下面文献已确认 DOI 和题录，但尚未通过合规渠道获得全文。它们仍可作为题录引用，但若要在正文中做更细的“原文机制比较”，建议后续通过机构 VPN、学校图书馆、作者主页或作者分享获取。

- 10.1109/MESA61532.2024.10704869：Multi-Robot Object Transport in Constrained Environments，用于贡献1。
- 10.1177/10775463251389027：Hierarchical Constraint-Based Formation Control Strategy，用于贡献1补充。
- 10.1109/TIE.2024.3390717：Deep Bilinear Koopman MPC，用于贡献2。
- 10.1109/TVT.2025.3555172：Distributed Cloud MPC with Delay Compensation，用于贡献3。
- 10.1109/TSMC.2025.3571743：Distributed Predictive Control with Communication Delays，用于贡献3。
- 10.1109/TMECH.2026.3662905：Fault Tolerant Control for UAV Formation Based on D-NMPC，用于贡献3。
- 10.1109/TITS.2025.3549162：Virtual Coupling Train Fault-Tolerant Control，用于贡献3。
