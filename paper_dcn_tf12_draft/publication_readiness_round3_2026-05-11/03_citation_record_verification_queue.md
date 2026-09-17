# Round3 Worker C: Citation Record Verification Queue

生成日期：2026-05-11  
工作边界：只生成 citation record 核验队列，不下载全文，不使用 SciDown / Sci-Hub / 非授权下载站。  
输入：

- `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/02_recent_literature_evidence_matrix.md`
- `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/`

## 0. 使用规则

### 0.1 核验目标

本队列的目标不是把候选文献直接写成终稿引用，而是把 Round2 文献矩阵和 `recent_lit_support_2026-05-07` 中的候选条目转成可执行的 citation record 核验任务。每条记录必须完成题名、作者、年份、出版源、DOI 或官方无 DOI 状态、合法 URL、来源类型、同行评议状态、访问日期、BibTeX、可支撑正文句和 gap 句之后，才能进入终稿引用。

### 0.2 核验等级

| target_level | 放行条件 | 允许进入正文的程度 |
|---|---|---|
| V3 | peer-reviewed / accepted publication 已核；DOI 或官方 no-DOI 状态已核；BibTeX、URL、access date、used sentence、gap sentence 完整 | 可作为终稿 citation 支撑具体 literature claim |
| V2 | arXiv、作者公开稿、机构库、标准组织、政府/实验室页面或官方网页已核，但 peer-review / DOI / BibTeX 字段尚未全部完成 | 只能作为 source-verified candidate，不写成终稿已支撑结论 |
| V1 | 只有题名、检索方向、摘要页或 Round2 占位 | 只能作为 search lead，不进入正文具体 claim |

### 0.3 required_fields 字段码

| 字段码 | 必填项 |
|---|---|
| FULL_ARTICLE | `authors`; `year`; `venue`; `DOI`; `DOI URL`; `publisher_or_official_URL`; `source_type`; `peer_review_status`; `access_date`; `BibTeX`; `local_fulltext_status`; `used_sentence`; `gap_sentence`; `no_SciDown_note` |
| OPEN_OR_PREPRINT | `authors`; `year`; `venue_or_arXiv_id`; `DOI_if_any`; `open_URL`; `version`; `source_type`; `peer_review_status`; `access_date`; `BibTeX`; `used_sentence`; `gap_sentence`; `preprint_not_peer_reviewed_note`; `no_SciDown_note` |
| OFFICIAL_SOURCE | `organization`; `document_number_or_report_id`; `version`; `year`; `official_URL`; `DOI_or_NA_official_no_DOI`; `access_date`; `citation_format_or_BibTeX_equivalent`; `allowed_scope`; `no_SciDown_note` |
| SEARCH_TO_RECORD | `search_queries`; `candidate_URLs`; `selected_legal_source`; then complete `FULL_ARTICLE`, `OPEN_OR_PREPRINT`, or `OFFICIAL_SOURCE` as applicable |

## 1. P0-A: 主文贡献和 baseline 必须优先核验的 citation records

这些条目来自 `recent_lit_support_2026-05-07`，已经有 DOI、开放全文、作者稿、预印本或题录线索。优先把它们补成 V3/V2 citation record；未补齐前只能使用“候选支撑线”写法。

| priority | citation_key | claim_slot | title_to_verify | source_url_or_search | source_type | target_level | required_fields | allowed_claim_before_verified |
|---|---|---|---|---|---|---|---|---|
| P0-A1 | `singh2025adaptiveijrr` | baseline; C2 Koopman; C4 robustness evidence | Adaptive Koopman Embedding for Robust Control of Nonlinear Dynamical Systems | DOI: `https://doi.org/10.1177/02783649251341907`; local preprint: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Singh2024_arXiv_Adaptive_Koopman_Embedding.pdf` | peer-reviewed article plus arXiv/preprint local copy | V3 for IJRR record; V2 for local preprint | FULL_ARTICLE + compare official IJRR metadata against local preprint version | 可写“adaptive Koopman embedding 是 baseline/相邻路线候选”；不可写已完成正式期刊全文机制核验 |
| P0-A1 | `zhao2024deepbilinearmpc` | C2 deep bilinear Koopman MPC | Deep Bilinear Koopman Model Predictive Control for Nonlinear Dynamical Systems | DOI: `https://doi.org/10.1109/TIE.2024.3390717`; legal search: title + DOI + publisher page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“deep bilinear Koopman MPC 是相邻研究线候选”；不可写具体网络结构、损失函数或实验结论 |
| P0-A1 | `abtahi2026frenetkoopman` | C2 vehicle Frenet Koopman | Deep Bilinear Koopman Model for Real-Time Vehicle Control in Frenet Frame | DOI: `https://doi.org/10.1109/ACCESS.2026.3662607`; local preprint: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Abtahi2025_arXiv_Deep_Bilinear_Koopman_Frenet.pdf` | peer-reviewed article plus arXiv/preprint local copy | V3 for IEEE Access record; V2 for preprint | FULL_ARTICLE + OPEN_OR_PREPRINT version match | 可写“Frenet-frame vehicle Koopman is an adjacent line”；不可把预印本细节直接当正式版本结论 |
| P0-A1 | `kernmaushart2024payloadaware` | C1 payload-aware cooperative transport; payload force metrics | Payload-Aware Trajectory Optimisation for Non-Holonomic Mobile Multi-Robot Manipulation With Tip-Over Avoidance | DOI: `https://doi.org/10.1109/LRA.2024.3427555`; local author manuscript: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Kern-Maushart2024_RAL_PayloadAware_Trajectory_Optimisation.pdf` | peer-reviewed article plus author manuscript | V3 | FULL_ARTICLE + author-manuscript legality/version note | 可写“载荷感知和防倾覆约束是相邻动机”；不可写具体实验数值或正式页码 |
| P0-A1 | `muhammed2026decentralized` | C1 cooperative transport MPC; C4 experimental validation | Real-Time Decentralized Model Predictive Control for Cooperative Multi-Robot Object Transport: Experimental Validation | DOI: `https://doi.org/10.1038/s41598-026-41881-w`; legal source: Nature/Sci Rep landing page | peer-reviewed open article; PDF script blocked locally | V3 | FULL_ARTICLE + legal fulltext acquisition note | 可写“实时去中心化协同搬运 MPC 是近邻任务背景”；不可写其算法细节或实验结论已核 |
| P0-A1 | `muhammed2024constrained` | C1 constrained multi-robot object transport | Multi-Robot Object Transport in Constrained Environments: A Model Predictive Control Approach | DOI: `https://doi.org/10.1109/MESA61532.2024.10704869`; legal search: title + DOI + IEEE/MESA page | conference paper; full text pending | V3 | FULL_ARTICLE | 可写“受约束多机器人物体运输 MPC 是候选前作”；不可写具体约束/控制结构 |
| P0-A1 | `zhao2025clouddelayplatoon` | C3 delay-compensated distributed MPC | Distributed Cloud Model Predictive Control With Delay Compensation for Heterogeneous Vehicle Platoons | DOI: `https://doi.org/10.1109/TVT.2025.3555172`; legal search: title + DOI + IEEE page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“车队 distributed MPC 已显式研究 delay compensation”；不可把它说成已覆盖载荷协同运输 |
| P0-A1 | `huang2025hybriddelaymultiagent` | C3 communication-delay multi-agent predictive control | Distributed Predictive Control for Multiagent Systems With Communication Delays via a Hybrid Data-Driven and Model-Based Approach | DOI: `https://doi.org/10.1109/TSMC.2025.3571743`; legal search: title + DOI + IEEE page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“通信时延下的多智能体预测控制是候选支撑线”；不可写其理论条件已适配本文系统 |
| P0-A1 | `li2026datadriveneventtriggered` | C3 data-driven predictive consensus with time-varying delays | Data-Driven Event-Triggered Predictive Control for Consensus of Discrete-Time Multi-Agent Systems with Time-Varying Delays | DOI: `https://doi.org/10.3390/app16041723`; local PDF: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Li2026_ApplSci_DataDriven_EventTriggered_Predictive_Delay_MAS.pdf` | peer-reviewed open article | V3 | FULL_ARTICLE | 可写“数据驱动预测控制可处理时变通信时延的一般 MAS 问题”；不可写其已覆盖车辆-载荷耦合 |
| P0-A1 | `zou2025eventtriggeredadmmdmpc` | C3 communication/computation-aware vehicle DMPC | Event-Triggered and Adaptive ADMM-Based Distributed Model Predictive Control for Vehicle Platoon | DOI: `https://doi.org/10.3390/vehicles7040115`; local PDF: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Vehicles2025_EventTriggered_ADMM_DMPC_Platoon.pdf` | peer-reviewed open article | V3 | FULL_ARTICLE | 可写“事件触发和分布式优化可降低车队 DMPC 通信/计算负担”；不可写其证明本文 payload tracking 有效 |
| P0-A1 | `shahab2025wmrfault` | C3/C4 WMR fault tolerance | Formation Control of Wheeled Mobile Robots with Fault-Tolerance Capabilities | DOI: `https://doi.org/10.3390/robotics14050059`; local PDF: `paper_dcn_tf12_draft/recent_lit_support_2026-05-07/pdfs/Shahab2025_Robotics_WMR_FaultTolerance.pdf` | peer-reviewed open article | V3 | FULL_ARTICLE | 可写“WMR 编队在执行器有效性损失下需要容错控制”；不可写其覆盖刚性载荷/团队力矩重分配 |
| P0-A1 | `zhang2025virtualcouplingfault` | C3 actuator effectiveness loss; transportation fault tolerance | Distributed Fault-Tolerant Control Strategy for Virtual Coupling Train System Against Measurement Errors and Loss of Actuator Effectiveness | DOI: `https://doi.org/10.1109/TITS.2025.3549162`; legal search: title + DOI + IEEE page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“交通系统中执行器有效性损失是相关容错问题”；不可写其控制律细节或适用于本文 |
| P0-A2 | `hu2026faulttolerantuav` | C3 distributed NMPC fault-tolerant formation | Fault Tolerant Control for Unmanned Aerial Vehicle Formation Based on Distributed Nonlinear Model Predictive Control | DOI: `https://doi.org/10.1109/TMECH.2026.3662905`; legal search: title + DOI + IEEE page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“分布式 NMPC 可作为 formation fault tolerance 的相邻路线”；不可写其已支撑本文车辆载荷场景 |
| P0-A2 | `li2025hierarchicaltransport` | C1 hierarchical constrained cooperative transport | Hierarchical Constraint-Based Formation Control Strategy for Multi-Robot Cooperative Transportation System in Warehousing Scenarios | DOI: `https://doi.org/10.1177/10775463251389027`; legal search: title + DOI + SAGE page | peer-reviewed article; full text pending | V3 | FULL_ARTICLE | 可写“层级约束协同运输是候选补充前作”；不可写仓储场景机制已核 |

## 2. P0-B: DCN-native / communication-resilience records from Round2 matrix

这些条目用于补齐 DCN 语境、AoI/QoS、V2X/CACC、通信-控制协同设计、bursty loss 和 resilient DMPC。它们大多还不是终稿引用；未完成 citation record 前，只能作为候选来源或背景线索。

| priority | citation_key | claim_slot | title_to_verify | source_url_or_search | source_type | target_level | required_fields | allowed_claim_before_verified |
|---|---|---|---|---|---|---|---|---|
| P0-B1 | `TimestampOutOfOrderDirectPending` | direct evidence gate for timestamped neighbor state and out-of-order packet handling | To be selected: timestamped neighbor state exchange / out-of-order packet control source | Search: `timestamped neighbor state exchange consensus control`; `out-of-order packet networked control MPC`; `packet reordering multi-agent consensus control` | search lead | V2 then V3 | SEARCH_TO_RECORD | 只能写本文实现“带时间戳缓存”；不可写成强 novelty 或文献已证明 |
| P0-B1 | `BufferedNeighborPredictionPending` | direct evidence gate for buffered neighbor prediction / state-age aligned MPC | To be selected: buffered neighbor prediction / state-age aligned DMPC source | Search: `buffered neighbor prediction distributed MPC delay compensation`; `state age neighbor prediction MPC`; `stale neighbor state prediction distributed MPC` | search lead | V2 then V3 | SEARCH_TO_RECORD | 只能写“用预测前推对齐 stale states”；不可写成已由近邻文献支撑的主要贡献 |
| P0-B1 | `AsyncDMPCReorderingPending` | direct evidence gate for asynchronous DMPC under delay/reordering | To be selected: asynchronous DMPC / packet reordering source | Search: `asynchronous distributed MPC packet reordering`; `distributed MPC out-of-order packets`; `asynchronous networked MPC packet delay dropout` | search lead | V2 then V3 | SEARCH_TO_RECORD | 只能写成限制项/待补文献；不可写“first asynchronous timestamped exchange” |
| P0-B1 | `ETSI2024BasicSetApplications` | V2X/CAV/CACC communication degradation context | Intelligent Transport Systems; Vehicular Communications; Basic Set of Applications; Release 2 | `https://www.etsi.org/deliver/etsi_tr/102600_102699/102638/02.01.01_60/tr_102638v020101p.pdf` | official standard / technical report | V2 official source; V3-equivalent citation only if official no-DOI record is complete | OFFICIAL_SOURCE | 可支撑 V2X/CACC 场景和消息侧语境；不可支撑控制算法有效性 |
| P0-B1 | `BonabSargolzaei2024CACCDelay` | CACC time-varying communication delay | A Nonlinear Control Design for Cooperative Adaptive Cruise Control with Time-Varying Communication Delay | `https://www.mdpi.com/2079-9292/13/10/1875` | peer-reviewed open article | V3 | FULL_ARTICLE | 可写“CACC 文献显式讨论 time-varying communication delay”；不可外推到载荷运输 |
| P0-B1 | `NIST2023WirelessTSN` | wireless time-critical control / QoS context | Scheduling for Time-critical Applications Utilizing TCP in Software-based 802.1Qbv Wireless TSN | `https://www.nist.gov/publications/scheduling-time-critical-applications-utilizing-tcp-software-based-8021qbv-wireless-tsn` | government/lab publication page | V2 official source or V3 conference record if DOI/proceedings verified | OFFICIAL_SOURCE or FULL_ARTICLE | 可支撑 latency/jitter/time-critical traffic 语境；不可写成机器人载荷控制证明 |
| P0-B1 | `Pang2024WNCSCodesign` | communication-control co-design | Communication-Control Codesign for Large-Scale Wireless Networked Control Systems | `https://arxiv.org/abs/2410.11316` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 可写 WNCS co-design 是相邻方向；不可写同行评议结论 |
| P0-B1 | `Ayan2024CommControl6G` | 6G communication-control co-design | Enabling Communication and Control Co-Design in 6G Networks | `https://arxiv.org/abs/2402.16462` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 可写 6G/NCS cross-layer co-design 背景；不可写成熟标准或定理支撑 |
| P0-B1 | `RolichTurcanuBaiocchi2024AoINRV2X` | AoI / cooperative awareness freshness | AoI-Aware and Persistence-Driven Congestion Control in 5G NR-V2X Sidelink Communications | `https://ion-turcanu.net/publication/rolich2024aoi/` | author page / conference record | V3 if proceedings DOI verified; otherwise V2 | FULL_ARTICLE | 可支撑 AoI/cooperative awareness freshness 背景；不可写 AoI 必然改善 payload tracking |
| P0-B1 | `YehVarmaElayoubi2024AoISwitching` | AoI safe switching / stale information | AoI-based switching control for safe haptic teleoperation over a wireless network | `https://zenodo.org/records/15682687` | repository / conference artifact | V2 or V3 if CDC proceedings metadata verified | OPEN_OR_PREPRINT or FULL_ARTICLE | 可支撑 stale information 与 safe switching 相邻语境；不可等同于本文安全证明 |
| P0-B2 | `ORNL2024TrajectoryShaper` | disrupted CACC | Trajectory Shaper: A Solution for Disrupted Cooperative Adaptive Cruise Control | `https://www.ornl.gov/publication/trajectory-shaper-solution-disrupted-cooperative-adaptive-cruise-control` | government/lab publication page | V2 official source or V3 if publication record complete | OFFICIAL_SOURCE or FULL_ARTICLE | 只能作为 disrupted CACC 语境候选 |
| P0-B2 | `Lan2024DataDrivenCACC` | data-driven CACC | Data-driven cooperative adaptive cruise control for unknown nonlinear vehicle platoons | `https://eprints.gla.ac.uk/324251/` | institutional repository / final venue pending | V3 if final record verified | FULL_ARTICLE | 只能作为 data-driven CACC 候选，不可写入具体 gap |
| P0-B2 | `TransmitPower2025WNCS` | QoS-aware / WNCS power-control coupling | Transmit power policies for stochastic stabilisation of multi-link wireless networked control systems | `https://www.ing.uc.cl/publicaciones/transmit-power-policies-for-stochastic-stabilisation-of-multi-link-wireless-networked-control-systems/` | university publication page | V3 if authors/venue/DOI verified | FULL_ARTICLE | 只能作为 WNCS QoS-control coupling search lead |
| P0-B2 | `ChenChenZhan2023ConsecutiveLoss` | bursty/consecutive packet losses | Consensus of discrete-time multi-agent systems with consecutive packet losses in directed communication topology | `https://journals.sagepub.com/doi/abs/10.1177/01423312221138892` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 consecutive packet loss 候选；不可写定理条件 |
| P0-B2 | `PhysicaA2024FractionalGroupConsensus` | random packet loss + communication delay consensus | Group consensus of fractional-order heterogeneous multi-agent systems with random packet losses and communication delays | `https://www.sciencedirect.com/science/article/abs/pii/S0378437124000554` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 packet loss + delay consensus 候选 |
| P0-B2 | `Automatica2024ResilientConstrainedDMPC` | resilient constrained DMPC | Resilient and constrained consensus against adversarial attacks: A distributed MPC framework | `https://www.sciencedirect.com/science/article/pii/S0005109823005848` | publisher page | V3 | FULL_ARTICLE | 只能作为 resilient constrained DMPC 候选；不可写本文已覆盖 adversarial attacks |
| P0-B2 | `ISATransactions2024EventTriggeredDMPCDoS` | connected-vehicle DMPC under DoS | Dynamic event-triggering-based distributed model predictive control of heterogeneous connected vehicle platoon under DoS attacks | `https://www.sciencedirect.com/science/article/pii/S0019057824003331` | publisher page | V3 | FULL_ARTICLE | 只能作为 connected vehicle DMPC under DoS 候选 |
| P0-B2 | `Neurocomputing2023MFIntegralSlidingMPC` | model-free predictive control with communication delay | Model-free distributed integral sliding mode predictive control for multi-agent systems with communication delay | `https://www.sciencedirect.com/science/article/abs/pii/S0925231223012560` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 predictive control with communication delay 候选 |
| P0-B2 | `Arxiv2025LyapunovMPCDelayDropout` | Lyapunov MPC under delays/dropouts | A Lyapunov-based MPC for Distributed Multi Agent Systems with Time Delays and Packet Dropouts using Hidden Markov Models | `https://arxiv.org/abs/2512.03708` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 只能作为 preprint evidence；不可写成成熟同行评议结论 |

## 3. P0-C: 控制/机器人补强 records from Round2 matrix

这些条目用于增强 Koopman-MPC、cooperative transport、DMPC、FTC/safety 的背景覆盖。若 P0-A 条目已经足够支撑主文，可把 P0-C 作为扩展或替代候选；若某个 P0-A 全文无法合法核验，应从本表选择替代。

| priority | citation_key | claim_slot | title_to_verify | source_url_or_search | source_type | target_level | required_fields | allowed_claim_before_verified |
|---|---|---|---|---|---|---|---|---|
| P0-C1 | `KanaiYamakita2023LiftedBilinearMPC` | Koopman / lifted bilinear MPC | Lifted Bilinear Model-based Linear Model Predictive Control with Scalability | `https://www.sciencedirect.com/science/article/pii/S2405896323005839` | proceedings / publisher page | V3 | FULL_ARTICLE | 可支撑 lifted bilinear model + MPC 相邻语境；不可写成车辆载荷证据 |
| P0-C1 | `KoopmanMultiModel2024PredictiveControl` | Koopman predictive control / multi-model | Koopman operator-based multi-model for predictive control | `https://link.springer.com/article/10.1007/s11071-024-09615-7` | peer-reviewed article | V3 | FULL_ARTICLE | 可支撑 Koopman-MPC 预测误差传播语境；不可写本文结构已由其证明 |
| P0-C1 | `AMC2024LearningMPCTimeVaryingKoopman` | adaptive/time-varying Koopman MPC | Learning model predictive control of nonlinear systems with time-varying parameters using Koopman operator | `https://www.sciencedirect.com/science/article/pii/S0096300324000493` | publisher page | V3 | FULL_ARTICLE | 只能作为 adaptive/online Koopman-MPC 候选 |
| P0-C1 | `Ebel2024CooperativeObjectTransportation` | cooperative object transportation | Cooperative object transportation with differential-drive mobile robots: Control and experimentation | `https://www.sciencedirect.com/science/article/abs/pii/S0921889023002518` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 cooperative object transportation 候选 |
| P0-C1 | `Turrisi2024PACC` | collaborative carrying + MPC | PACC: A Passive-Arm Approach for High-Payload Collaborative Carrying with Quadruped Robots Using Model Predictive Control | `https://arxiv.org/abs/2403.19862` | arXiv / conference candidate | V2 or V3 if IROS record verified | OPEN_OR_PREPRINT then FULL_ARTICLE | 可支撑 collaborative carrying + MPC 的候选语境 |
| P0-C1 | `Manesh2025FaultTolerantDNMPC` | distributed nonlinear MPC + fault estimation | Fault-tolerant multi-agent formation control using distributed nonlinear MPC with discrete-time super-twisting sliding mode fault estimation | `https://www.sciencedirect.com/science/article/pii/S2773186325000593` | peer-reviewed open article | V3 | FULL_ARTICLE | 可支撑 distributed nonlinear MPC + fault estimation 相邻语境；不可写覆盖载荷运输 |
| P0-C1 | `Li2025EventTriggeredAFTPC` | event-triggered active fault-tolerant predictive control | Event-Triggered Active Fault-Tolerant Predictive Control for Networked Multi-Agent Systems with Actuator Faults and Random Communication Constraints | `https://www.mdpi.com/2076-3417/15/11/6317` | peer-reviewed open article | V3 | FULL_ARTICLE | 只能作为 random communication constraints + FTC 候选 |
| P0-C2 | `Fu2025ResidualKoopmanVehicleMPC` | vehicle residual Koopman-MPC | Residual Koopman Model Predictive Control for Enhanced Vehicle Dynamics with Small On-Track Data Input | `https://arxiv.org/abs/2507.18396` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 只能作为 vehicle residual Koopman-MPC preprint 候选 |
| P0-C2 | `SuBhowmickLanzon2023RobustAdaptivePayload` | cooperative payload transport / networked UAV | A robust adaptive formation control methodology for networked multi-UAV systems with applications to cooperative payload transportation | `https://www.sciencedirect.com/science/article/abs/pii/S0967066123001776` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 networked multi-UAV payload 候选 |
| P0-C2 | `KargarTasooji2025EventBasedPayloadNMPC` | event-based NMPC payload transport | Cooperative Control of Multi-Quadrotors for Transporting Cable-Suspended Payloads: Obstacle-Aware Planning and Event-Based Nonlinear Model Predictive Control | `https://arxiv.org/abs/2503.19135` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 只能作为 event-based NMPC payload preprint 候选 |
| P0-C2 | `Sambhus2026SafetyCriticalPayloadNMPC` | safety-critical payload NMPC | Safety-Critical Centralized Nonlinear MPC for Cooperative Payload Transportation by Two Quadrupedal Robots | `https://arxiv.org/abs/2604.03200` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 只能作为 safety-critical payload NMPC preprint 候选 |
| P0-C2 | `NgoTsaiLiu2024FaultTolerantAllocation` | cooperative transport actuator FTC allocation | Actuator fault-tolerant control allocation for cooperative transportation of multiple omnidirectional mobile robots | `https://www.tandfonline.com/doi/abs/10.1080/01691864.2023.2300695` | publisher abstract page | V3 | FULL_ARTICLE | 只能作为 actuator FTC allocation 候选 |
| P0-C2 | `WangZhangWang2025SafetyCriticalDMPC` | safety-critical DMPC / CBF | Distributed Safety-Critical MPC for Multi-Agent Formation Control and Obstacle Avoidance | `https://arxiv.org/abs/2508.19678` | arXiv preprint | V2 | OPEN_OR_PREPRINT | 只能作为 safety-critical DMPC preprint 候选 |

## 4. 最小可用文献集

### 4.1 主文安全集 MVLS-Core

在写入具体正文 citation claim 前，至少应完成下列记录。若其中任一条无法合法核验，必须从 P0-C 中选择同 claim_slot 的替代记录。

| 模块 | 最小记录 | 放行标准 | 未达标时处理 |
|---|---|---|---|
| Baseline and adaptive Koopman | `singh2025adaptiveijrr` | IJRR V3 record 完整；local arXiv 与正式版差异已标注 | baseline 只写“corresponding adaptive Koopman line/preprint candidate” |
| Bilinear / Frenet Koopman MPC | `zhao2024deepbilinearmpc`; `abtahi2026frenetkoopman` | 至少 1 条 V3 + 1 条 V2/V3；必须区分单体/单车与本文团队载荷 | 不写“本文沿两篇正式文献扩展”的强表述 |
| Cooperative transport and payload metrics | `muhammed2026decentralized`; `kernmaushart2024payloadaware` | 2 条 V3；其中至少 1 条能支撑协同运输实验，1 条支撑 payload-aware metrics | 不写“协同运输 MPC 实验基线已完整支撑” |
| Delay / communication-aware predictive control | `zhao2025clouddelayplatoon`; `huang2025hybriddelaymultiagent`; plus one of `li2026datadriveneventtriggered` or `zou2025eventtriggeredadmmdmpc` | 至少 2 条 V3；必须明确这些文献不覆盖刚性载荷 | 通信补偿只写本文机制，不写 literature gap 的具体结论 |
| FTC / actuator degradation | `shahab2025wmrfault`; plus one of `zhang2025virtualcouplingfault`, `hu2026faulttolerantuav`, `Manesh2025FaultTolerantDNMPC`, `Li2025EventTriggeredAFTPC` | 至少 2 条 V3；必须覆盖 actuator effectiveness/fault-tolerant predictive/formation control 中两类证据 | 故障容错只写“相邻问题”，不写完整支撑 |
| DCN-native context | at least two of `ETSI2024BasicSetApplications`, `NIST2023WirelessTSN`, `RolichTurcanuBaiocchi2024AoINRV2X`, `BonabSargolzaei2024CACCDelay`, `Pang2024WNCSCodesign` | 官方/V3/V2 记录完整；source type 明确 | 不写 DCN-native framing，只保留 generic networked control wording |

### 4.2 Timestamp/out-of-order/buffered 额外门槛

若正文想把 `timestamped neighbor state + out-of-order packet handling + buffered neighbor prediction` 写成主要 novelty，必须另外完成：

| direct gate | 最小记录数 | 要求 | 未达标时安全写法 |
|---|---:|---|---|
| timestamped neighbor state exchange | 1 V2/V3 direct source | 来源必须直接涉及 timestamp/state age/stale neighbor state in control or consensus | 只写本文实现“每个邻居状态带时间戳存入 buffer” |
| out-of-order packet handling / packet reordering | 1 V2/V3 direct source | 来源必须直接涉及 out-of-order/reordering/delay-varying packet processing in control/MPC | 只写实验退化条件，不写 literature novelty |
| buffered neighbor prediction / state-age aligned MPC | 1 V2/V3 direct source | 来源必须直接涉及 prediction propagation of stale neighbor states or buffer alignment | 只写“stale states are propagated before entering MPC” |

结论：在这三个 direct gates 未满足前，timestamp/out-of-order/buffered exchange 只能是实现机制、实验变量或 limitation，不能作为强贡献标题。

## 5. 未核验前必须删除或降级的 claim

| claim | 处理方式 | 允许替代表述 |
|---|---|---|
| “本文首次/第一个同时解决 Koopman、DMPC、AoI、协同运输和 FTC” | 删除 | “本文将 bilinear Koopman prediction、delay-compensated consensus MPC 和 FTC/safety fallback 集成并在本文场景下验证。” |
| “timestamped/out-of-order/buffered neighbor exchange 是强 novelty” | 降级 | “本文实现 timestamped neighbor buffers and stale-state propagation；direct literature record remains a citation-gate item.” |
| “V2X/CACC 文献证明本文多机器人载荷运输有效” | 删除 | “V2X/CACC 文献用于说明 delay/dropout/AoI 等通信退化语境。” |
| “AoI/QoS 优化必然降低 payload tracking error” | 删除 | “本文实验需要报告 AoI/QoS sweep 与 payload tracking/force metrics 的关联。” |
| “baseline 在通信退化下失败/不稳定” | 删除 | “baseline comparison remains mechanism-level until T1 fairness gate is complete.” |
| “本文优于 Adaptive Koopman baseline” | 删除 | 只有完成同数据、同 solver、同 horizon、同通信退化注入、同 seed/CI 后，才可写数值优越性 |
| “Koopman bilinear 模型必然优于 linear/adaptive Koopman” | 删除 | “本文将比较 prediction error、tracking、solver time 和 robustness metrics。” |
| “本文保证任意持续丢包或任意拓扑断连下渐近稳定” | 降级 | “在 bounded delay/loss/dwell-time 与有界 prediction error 假设下讨论 practical stability/UUB。” |
| “FTC/safety 覆盖传感器、执行器、通信和整车失效所有故障类型” | 删除 | “本文覆盖实验和理论实际定义的 actuator degradation / communication degradation modes。” |
| “安全约束从未违反” | 降级 | “报告 constraint violation rate、worst-case margin 和 recovery time 后再给结论。” |
| “协同运输性能由 tracking error 单独证明” | 删除 | “必须同时报告 payload pose、formation/consensus error、force smoothness、constraint violation、recovery time 和 solver time。” |
| “closed/abstract-only 文献的具体算法细节已经核验” | 删除 | “只写题名/摘要页可支撑的范围性背景，细节待合法全文或正式记录核验。” |
| “arXiv/preprint 等同于 peer-reviewed final article” | 删除 | “标注为 preprint/source-verified candidate，除非已核正式发表版本。” |

## 6. 执行顺序

1. 先补 P0-A1：这些记录直接影响四个贡献和 baseline，是最小可用文献集的主体。
2. 并行检索 P0-B1 三个 direct gates：若找不到 timestamp/out-of-order/buffered direct source，主文必须保守降级。
3. 补 DCN-native 背景：优先 `ETSI2024BasicSetApplications`, `BonabSargolzaei2024CACCDelay`, `NIST2023WirelessTSN`, `RolichTurcanuBaiocchi2024AoINRV2X`, `YehVarmaElayoubi2024AoISwitching`。
4. 用 P0-C 替代失败的 P0-A 条目：优先选 V3 或合法开放全文条目，不用非授权下载。
5. 每完成一条 citation record，必须把 `allowed_claim_before_verified` 升级为 `verified_used_sentence` 和 `verified_gap_sentence`，否则仍按未核验处理。

## 7. 当前可写入稿件的安全边界

在上述队列完成前，主文可以写：

- 近年工作分别覆盖 adaptive Koopman、bilinear/Frenet Koopman-MPC、cooperative transport、communication-delay predictive control、event-triggered/communication-aware DMPC 和 fault-tolerant formation control 等相邻方向。
- 本文的安全表述应强调“集成到四车刚性载荷、通信退化与故障重分配并存的实验场景中验证”，而不是声称文献已经证明本文所有模块。
- 所有 V1/V2 条目只能作为 candidate/source-verified lead；只有完成 V3 或官方 V2-equivalent record 后，才可在终稿中作为具体 citation claim。
