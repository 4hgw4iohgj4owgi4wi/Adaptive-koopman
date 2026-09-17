# 近三年文献检索与引用支撑更新（2026-05-12）

## 1. 检索方式

本轮按 `sci-literature-scout` 流程执行：

1. 使用 OpenAlex 检索 2023-01-01 至 2026-05-12 的题名/摘要元数据。
2. 使用 LetPub 检索候选期刊信息。
3. 只尝试下载合法开放 PDF；关闭文章不使用绕过付费墙渠道。
4. 输出 CSV/XLSX/Markdown 报告，供后续人工筛选引用。

短路径输出目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\lit_scout_20260512`

原长路径输出目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\sci_literature_scout_2026-05-12`

短路径版本用于合法 OA PDF 下载，长路径版本保留在 round10 记录区。

## 2. 检索统计

| 项目 | 数量 |
|---|---:|
| OpenAlex raw article candidates | 63 |
| journal candidates | 40 |
| strict included journals | 0 |
| strict article methods | 0 |
| high-impact supplement | 38 |
| downloaded legal PDFs | 2 |

strict table 为 0 的原因：LetPub 自动解析未能稳定确认 CAS 1/2 区与 SCI/SCIE 状态，不能自动把 IEEE/Elsevier/Springer 文章放入 strict table。后续需要人工核对期刊分区后再进入主引用表。

## 3. 已合法下载全文

| 题名 | 来源 | DOI / URL | 备注 |
|---|---|---|---|
| Real-time decentralized model predictive control for cooperative multi-robot object transport: experimental validation | Scientific Reports | https://doi.org/10.1038/s41598-026-41881-w | 可用于“多机器人协同搬运 + decentralized MPC”研究现状与实验验证支撑 |
| Review of Smart Auto X: Autonomous Self Driving Car Using IoT and Deep Learning Technologies | IRE Journals | https://doi.org/10.64388/irev9i5-1712020 | 相关性较弱，只作为自动驾驶综述候选，不建议进入主文核心引用 |

PDF 目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\lit_scout_20260512\open_access_pdfs`

## 4. 高相关候选文献

这些文献目前进入 supplement table，后续需要逐篇核对出版社页、学校库/VPN 或作者公开稿：

| 模块 | 候选文献 | 年份 | 期刊/会议 | DOI |
|---|---|---:|---|---|
| 通信可靠性感知 DMPC | Distributed MPC for Connected Vehicle Platoons With Communication-Reliability Awareness and Attention-Based Trajectory Fusion | 2025 | IEEE Internet of Things Journal | https://doi.org/10.1109/jiot.2025.3630349 |
| 时延补偿/可见性退化 | Distributed Predictive Control of Vehicle Platoons Under Reduced Visibility With Delay Compensation: A Fog-Specific Approach | 2025 | conference metadata | https://doi.org/10.1109/icstcc66753.2025.11240354 |
| 异步采样与随机通信时延 | Distributed model predictive anti-disturbance control for vehicle platoon under asynchronous sampling and stochastic communication delay | 2025 | Engineering Research Express | https://doi.org/10.1088/2631-8695/adef92 |
| 多机器人协同运输 | Multi-Robot Cooperative Transportation of Irregular Objects by Multi-Objective Optimization With Distributed Control | 2025 | IEEE Robotics and Automation Letters | https://doi.org/10.1109/lra.2025.3597895 |
| 通信时延 tube-DMPC | Event-Triggered Tube-DMPC With Shrinking Ingredients for Vehicle Platoon Under Disturbance and Communication Delay | 2025 | IEEE Transactions on Intelligent Transportation Systems | https://doi.org/10.1109/tits.2025.3561134 |
| Koopman 车辆控制 | Incorporating ESO into Deep Koopman Operator Modeling for Control of Autonomous Vehicles | 2024 | IEEE Transactions on Control Systems Technology | https://doi.org/10.1109/tcst.2024.3378456 |
| 输入与通信时延多智能体 DMPC | Periodic Event-Triggered Robust Distributed Model Predictive Control for Multiagent Systems With Input and Communication Delays | 2023 | IEEE Transactions on Industrial Informatics | https://doi.org/10.1109/tii.2023.3245189 |
| Koopman + 通信时延安全 | KoopShield: A Koopman based Online Data-Driven Safety Framework for Truck Platoons Resilient to Communication Delays | 2026 | IEEE Internet of Things Journal | https://doi.org/10.1109/jiot.2026.3676126 |
| AKE 原文 baseline | Adaptive Koopman embedding for robust control of nonlinear dynamical systems | 2025 | The International Journal of Robotics Research | https://doi.org/10.1177/02783649251341907 |

## 5. 与本文贡献的对应关系

| 本文模块 | 可支撑文献线 | 文献已有内容 | 本文需要强调的增量 |
|---|---|---|---|
| Koopman / bilinear learning | AKE、ESO-Deep Koopman、Deep Bilinear Koopman vehicle control | 单体系统或车辆路径跟踪的 Koopman 表示和 MPC | 多车刚性载荷运输下的 lifted team model、连接力/团队误差闭环与通信/故障耦合 |
| delay-compensated consensus MPC | communication-aware DMPC、tube-DMPC、event-triggered DMPC | 车辆队列或多智能体系统中的时延、丢包、tube tightening | 把链路质量映射到团队命令融合、约束收紧和降级 fallback，并与载荷连接安全指标联动 |
| FDI/FTC | learning-based FTC MPC、fault-tolerant vehicle control | 单车或队列故障下的鲁棒控制/安全 MPC | 对四车载荷运输的执行亏损诊断、模式切换、命令重分配与连接安全证书闭合 |
| cooperative transport | decentralized MPC object transport、multi-objective distributed transport | 多机器人搬运中的分布式控制和实验验证 | 引入非完整车辆动力学、Frenet 路径跟踪、货物等效力和通信退化场景 |

## 6. 当前文献缺口

1. `strict_article_methods.csv` 为空，说明 LetPub 自动筛选不能直接作为投稿引用表；需要人工确认 IEEE TITS、TCST、TII、T-RO、RA-L、IJRR 等期刊的分区与 SCI/SCIE 状态。
2. 绝大多数高相关文献是 closed metadata，不能声称已全文研读；目前只能基于题名、摘要、DOI 页和合法 OA 信息写 preliminary literature map。
3. 下一步应优先获取并研读：AKE 原文、TCST Koopman 车辆控制、TITS Tube-DMPC 通信时延、TII input/communication delay DMPC、Scientific Reports decentralized MPC transport。

