# 需要进一步获取全文的 DOI 清单

说明：我不能代替你使用 SciDown / Sci-Hub 等绕过版权限制的服务下载付费论文。下面清单用于你通过学校图书馆、机构 VPN、出版社个人/机构订阅、作者公开稿、ResearchGate 作者分享或馆际互借等合规方式获取全文。若你自行使用其他工具，这份清单也可作为 DOI 输入顺序。

## 优先级 A：正文贡献已直接引用，建议尽量拿到全文

1. 10.1109/MESA61532.2024.10704869
   - Multi-Robot Object Transport in Constrained Environments: A Model Predictive Control Approach
   - 用途：贡献1，多机器人载荷运输 MPC 的直接相似原文。
   - 为什么重要：它能支撑“本文不是凭空做协同搬运，而是在受约束多机器人运输 MPC 基础上推进到四车刚性载荷 Frenet 团队模型”。

2. 10.1038/s41598-026-41881-w
   - Real-Time Decentralized Model Predictive Control for Cooperative Multi-Robot Object Transport: Experimental Validation
   - 用途：贡献1和贡献4，协同运输实验验证与实时去中心化 MPC。
   - 为什么重要：它是近三年协同搬运实验验证里最贴近本文实验组织方式的文献之一。

3. 10.1177/02783649251341907
   - Adaptive Koopman Embedding for Robust Control of Nonlinear Dynamical Systems
   - 用途：baseline 主文献，贡献2和贡献4。
   - 为什么重要：它是本文 baseline 的正式期刊版本；本地已有 arXiv 版本，但正式 IJRR 版本最好也核对一遍。

4. 10.1109/TIE.2024.3390717
   - Deep Bilinear Koopman Model Predictive Control for Nonlinear Dynamical Systems
   - 用途：贡献2，双线性 Koopman + MPC 的近三年直接相似原文。
   - 为什么重要：它能支撑本文 Koopman 主干不是孤立设计，而是在 deep bilinear Koopman MPC 路线上的车辆/载荷协同扩展。

5. 10.1109/ACCESS.2026.3662607
   - Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame
   - 用途：贡献2，车辆 Frenet 坐标 Koopman 控制。
   - 为什么重要：它与本文的 Frenet 建模和车辆控制对象高度接近，适合用来说明本文相对单车 Koopman 控制的扩展。

## 优先级 B：支撑通信韧性与故障容错模块

6. 10.1109/TVT.2025.3555172
   - Distributed Cloud Model Predictive Control With Delay Compensation for Heterogeneous Vehicle Platoons
   - 用途：贡献3，通信时延补偿 distributed MPC。
   - 为什么重要：它支撑本文“时延补偿不是实现层补丁，而应进入预测控制回路”的论证。

7. 10.1109/TSMC.2025.3571743
   - Distributed Predictive Control for Multiagent Systems With Communication Delays via a Hybrid Data-Driven and Model-Based Approach
   - 用途：贡献3，带通信时延的多智能体预测控制。
   - 为什么重要：它能支撑本文“数据驱动预测 + 通信时延处理”的组合逻辑。

8. 10.1109/TMECH.2026.3662905
   - Fault Tolerant Control for Unmanned Aerial Vehicle Formation Based on Distributed Nonlinear Model Predictive Control
   - 用途：贡献3，分布式 NMPC 容错编队。
   - 为什么重要：它能支撑本文故障容错层的分布式预测控制背景。

9. 10.1109/TITS.2025.3549162
   - Distributed Fault-Tolerant Control Strategy for Virtual Coupling Train System Against Measurement Errors and Loss of Actuator Effectiveness
   - 用途：贡献3，执行器有效性损失与分布式容错。
   - 为什么重要：它与本文“单车执行器退化”设定最接近，可用于解释故障重分配为什么必要。

10. 10.3390/robotics14050059
    - Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities
    - 用途：贡献3，轮式移动机器人容错编队。
    - 为什么重要：它支撑本文从一般 WMR 容错编队推进到刚性载荷耦合协同运输。

## 优先级 C：可作为扩展引用或备选

11. 10.1177/10775463251389027
    - Hierarchical Constraint-Based Formation Control Strategy for Multi-Robot Cooperative Transportation System in Warehousing Scenarios
    - 用途：贡献1，仓储协同运输与层级约束编队。
    - 为什么重要：可作为协同运输工程场景的近三年补充文献。

## 本地已有全文

1. `pdfs/Kern-Maushart2024_RAL_PayloadAware_Trajectory_Optimisation.pdf`
   - 对应 DOI：10.1109/LRA.2024.3427555

2. `pdfs/Singh2024_arXiv_Adaptive_Koopman_Embedding.pdf`
   - 对应正式 DOI：10.1177/02783649251341907
   - 说明：这是 arXiv 预印本，不是正式 IJRR 版。

