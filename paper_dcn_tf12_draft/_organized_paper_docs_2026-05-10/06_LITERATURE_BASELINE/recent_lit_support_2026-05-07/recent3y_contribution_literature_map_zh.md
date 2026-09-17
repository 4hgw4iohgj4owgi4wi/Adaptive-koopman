# 近3年文献支撑与四个贡献对照

## 检索说明

- 检索时间：2026-05-07
- 检索入口：Google Scholar
- 本地保存的 Scholar 检索结果 HTML：`scholar_html_2026-05-07/`
- 原始候选汇总：`scholar_recent_literature_raw.csv`
- 说明：仅下载开放获取或公开作者稿；对付费版权文献只保留正式题录、DOI 与落地页信息，不使用 Sci-Hub / SciDown 等绕过版权限制的方式。

## 结论先行

- 你的四个贡献现在已经可以分别找到近 3 年的已发表相似原文作为“前作锚点”。
- 最稳的写法不是把贡献写成“凭空提出”，而是写成“在谁的什么框架基础上，针对四车刚性载荷运输中的哪条缺口做了扩展”。
- 我已经把这种写法直接改进了 `manuscript_zh_word_export.md` 的引言和四个贡献表述。

## 四个贡献怎么落

### Contribution 1

- 原文：Multi-Robot Object Transport in Constrained Environments: A Model Predictive Control Approach (2024, DOI: 10.1109/MESA61532.2024.10704869)
  作用：多机器人载荷运输 MPC 直接相似原文
  你的改进：从一般多机器人物体运输扩展到四车刚性载荷 Frenet 团队模型，并显式写入角点映射、柔性连接误差、载荷受力与团队冗余。
  建议放置：贡献1、引言协同运输段
  下载状态：Scholar 检到正式发表版本，未找到可合法直下 PDF。
- 原文：Real-Time Decentralized Model Predictive Control for Cooperative Multi-Robot Object Transport: Experimental Validation (2026, DOI: 10.1038/s41598-026-41881-w)
  作用：实时去中心化协同运输实验基线
  你的改进：从去中心化对象运输推进到含通信退化、持续执行器故障、载荷受力评估和团队容错重分配的车辆协同运输。
  建议放置：贡献1、贡献4、引言协同运输段
  下载状态：Nature 落地页可访问，但自动脚本直下 PDF 被站点风控拦截。
- 原文：Payload-Aware Trajectory Optimisation for Non-Holonomic Mobile Multi-Robot Manipulation With Tip-Over Avoidance (2024, DOI: 10.1109/LRA.2024.3427555)
  作用：载荷感知轨迹优化与安全约束原文
  你的改进：从轨迹优化推进到闭环协同控制，把载荷受力、连接误差和故障补偿一并纳入 MPC。
  建议放置：贡献1、引言协同运输段
  下载状态：ETH Zurich 公开作者稿，已下载。
- 原文：Hierarchical Constraint-Based Formation Control Strategy for Multi-Robot Cooperative Transportation System in Warehousing Scenarios (2025, DOI: 10.1177/10775463251389027)
  作用：层级约束运输 / 编队协同原文
  你的改进：从仓储编队运输推进到道路曲率路径、通信时延和执行器退化并存下的刚性载荷协同运输。
  建议放置：引言协同运输段、贡献1对照
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。

### Contribution 2

- 原文：Adaptive Koopman Embedding for Robust Control of Nonlinear Dynamical Systems (2025, DOI: 10.1177/02783649251341907)
  作用：你的 baseline 与最直接的 Koopman 祖线
  你的改进：从单体系统的离线 Koopman + 在线自适应，扩展到多车载荷运输，并新增稳定投影、车辆/载荷状态组织、通信韧性和故障重分配。
  建议放置：贡献2、贡献4、引言 Koopman 段
  下载状态：正式期刊版已确认；本地保存的是对应 arXiv 预印本。
- 原文：Deep Bilinear Koopman Model Predictive Control for Nonlinear Dynamical Systems (2024, DOI: 10.1109/TIE.2024.3390717)
  作用：双线性 Koopman + MPC 的直接相似原文
  你的改进：把双线性 Koopman 从一般非线性系统推进到四车载荷运输，并增加可学习观测、学习型解码矩阵、谱半径稳定投影和团队级状态组织。
  建议放置：贡献2、引言车辆 Koopman 段
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。
- 原文：Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame (2026, DOI: 10.1109/ACCESS.2026.3662607)
  作用：车辆 Frenet 坐标下最接近你的单车前身
  你的改进：从单车 Frenet 控制扩展到四车刚性载荷协同 Frenet 控制，并把通信一致性、载荷力学和故障容错耦合进 lifted MPC。
  建议放置：贡献2、引言车辆 Koopman 段
  下载状态：IEEE Access 正式发表版已确认，但自动脚本请求 PDF 被站点反爬返回 418。

### Contribution 3

- 原文：Distributed Cloud Model Predictive Control With Delay Compensation for Heterogeneous Vehicle Platoons (2025, DOI: 10.1109/TVT.2025.3555172)
  作用：时延补偿 distributed MPC 的最直接相似原文
  你的改进：从异构车队时延补偿推进到四车载荷运输的通信质量感知一致性、退化安全回退与团队级故障补偿。
  建议放置：贡献3、引言通信韧性段
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。
- 原文：Distributed Predictive Control for Multiagent Systems With Communication Delays via a Hybrid Data-Driven and Model-Based Approach (2025, DOI: 10.1109/TSMC.2025.3571743)
  作用：通信时延 + distributed predictive control 原文
  你的改进：把一般多智能体通信时延控制推进到车辆-载荷耦合系统，并增加链路质量感知权重、故障激活阶段补偿和载荷指标约束。
  建议放置：贡献3、引言通信韧性段
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。
- 原文：Fault Tolerant Control for Unmanned Aerial Vehicle Formation Based on Distributed Nonlinear Model Predictive Control (2026, DOI: 10.1109/TMECH.2026.3662905)
  作用：分布式 NMPC 容错编队原文
  你的改进：从 UAV 编队故障容错推进到车辆协同载荷运输，并把局部执行器亏损重映射成团队级等效力与等效力矩补偿。
  建议放置：贡献3、引言通信/故障段
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。
- 原文：Distributed Fault-Tolerant Control Strategy for Virtual Coupling Train System Against Measurement Errors and Loss of Actuator Effectiveness (2025, DOI: 10.1109/TITS.2025.3549162)
  作用：执行器有效性损失建模与补偿原文
  你的改进：将“执行器有效性损失”从列车虚拟编组推进到四车载荷运输中的单车持续退化，并结合故障重分配与进度监督。
  建议放置：贡献3、引言通信/故障段
  下载状态：正式发表版本已确认，未找到可合法直下 PDF。
- 原文：Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities (2025, DOI: 10.3390/robotics14050059)
  作用：轮式移动机器人容错协同原文
  你的改进：从一般 WMR 编队容错推进到刚性载荷耦合、通信时延与故障重分配并存的协同运输。
  建议放置：贡献3、引言通信/故障段
  下载状态：MDPI 正式发表版已确认，但自动脚本直下 PDF 被站点风控 403 拦截。

### Contribution 4

- 原文：Adaptive Koopman robustness evaluation + cooperative transport experimental validation (2025-2026, DOI: 10.1177/02783649251341907 ; 10.1038/s41598-026-41881-w)
  作用：实验组织方式与鲁棒性评估的参考组合
  你的改进：不只比较整体跟踪，而是把离线数据覆盖、升维预测误差、团队/单车误差、连接误差、载荷力、通信故障时间线和局部窗口机理图串成证据链。
  建议放置：贡献4
  下载状态：可作为你“实验部分为什么这样组织”的直接论据。

## 建议你在稿子里坚持的表述原则

- 贡献1不要只写“提出了团队模型”，而要写成“在协同运输 MPC 和载荷感知轨迹约束工作基础上，推进到四车刚性载荷 Frenet 团队建模”。
- 贡献2不要只写“改进了 Koopman 网络”，而要写成“在 adaptive Koopman embedding、deep bilinear Koopman MPC 和车辆 Frenet Koopman 控制基础上，推进到稳定投影的团队 lifted 模型”。
- 贡献3不要只写“加入了通信补偿和故障容错”，而要写成“在时延补偿 distributed MPC 与分布式容错控制基础上，推进到通信质量感知一致性 + 退化回退 + 故障重分配的统一协同控制栈”。
- 贡献4不要只写“做了很多实验”，而要写成“在 adaptive Koopman robustness 对比和 cooperative transport validation 的组织方式基础上，建立了更细粒度的跨层证据链”。

## 本地已落地的公开 PDF

- Payload-Aware Trajectory Optimisation for Non-Holonomic Mobile Multi-Robot Manipulation With Tip-Over Avoidance：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Kern-Maushart2024_RAL_PayloadAware_Trajectory_Optimisation.pdf`
- Adaptive Koopman Embedding for Robust Control of Nonlinear Dynamical Systems：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Singh2024_arXiv_Adaptive_Koopman_Embedding.pdf`
- Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Abtahi2025_arXiv_Deep_Bilinear_Koopman_Frenet.pdf`
- Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Shahab2025_Robotics_WMR_FaultTolerance.pdf`
- Event-Triggered and Adaptive ADMM-Based Distributed Model Predictive Control for Vehicle Platoon：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Vehicles2025_EventTriggered_ADMM_DMPC_Platoon.pdf`
- Data-Driven Event-Triggered Predictive Control for Consensus of Discrete-Time Multi-Agent Systems with Time-Varying Delays：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\pdfs\Li2026_ApplSci_DataDriven_EventTriggered_Predictive_Delay_MAS.pdf`

## 本轮新增的全文提炼

- 新增文档：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\recent_lit_support_2026-05-07\fulltext_module_extraction_zh.md`
- 该文档已经按“原文做了什么 / 原文没覆盖什么 / 本文怎么改进 / 可写入论文的句子”逐篇展开。
- 新增开放全文主要加强了两块证据：一是车辆 Frenet Koopman 控制对贡献2的支撑，二是通信韧性和执行器故障容错对贡献3的支撑。

## 自动下载失败但可用的正式题录

- Multi-Robot Object Transport in Constrained Environments: A Model Predictive Control Approach：Scholar 检到正式发表版本，未找到可合法直下 PDF。 DOI=10.1109/MESA61532.2024.10704869
- Real-Time Decentralized Model Predictive Control for Cooperative Multi-Robot Object Transport: Experimental Validation：Nature 落地页可访问，但自动脚本直下 PDF 被站点风控拦截。 DOI=10.1038/s41598-026-41881-w
- Hierarchical Constraint-Based Formation Control Strategy for Multi-Robot Cooperative Transportation System in Warehousing Scenarios：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1177/10775463251389027
- Deep Bilinear Koopman Model Predictive Control for Nonlinear Dynamical Systems：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1109/TIE.2024.3390717
- Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame：IEEE Access 正式发表版已确认，但自动脚本请求 PDF 被站点反爬返回 418。 DOI=10.1109/ACCESS.2026.3662607
- Distributed Cloud Model Predictive Control With Delay Compensation for Heterogeneous Vehicle Platoons：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1109/TVT.2025.3555172
- Distributed Predictive Control for Multiagent Systems With Communication Delays via a Hybrid Data-Driven and Model-Based Approach：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1109/TSMC.2025.3571743
- Fault Tolerant Control for Unmanned Aerial Vehicle Formation Based on Distributed Nonlinear Model Predictive Control：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1109/TMECH.2026.3662905
- Distributed Fault-Tolerant Control Strategy for Virtual Coupling Train System Against Measurement Errors and Loss of Actuator Effectiveness：正式发表版本已确认，未找到可合法直下 PDF。 DOI=10.1109/TITS.2025.3549162
- Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities：MDPI 正式发表版已确认，但自动脚本直下 PDF 被站点风控 403 拦截。 DOI=10.3390/robotics14050059
- Adaptive Koopman robustness evaluation + cooperative transport experimental validation：可作为你“实验部分为什么这样组织”的直接论据。 DOI=10.1177/02783649251341907 ; 10.1038/s41598-026-41881-w
