# Worker B: Recent Literature Evidence Matrix

生成日期：2026-05-11  
目标稿件：`Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC`  
输入文件：

- `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/00_round2_task_tree.md`
- `paper_dcn_tf12_draft/parallel_article_completion_2026-05-10/02_literature_baseline_gap_map.md`

## 0. Round2 Reviewer 1 合规边界

本文件只服务于 DCN 投稿前的文献证据矩阵。近三年按 2023-2026 处理。所有条目只允许来自合法可访问路径：出版社摘要页、开放获取全文、arXiv、机构库、作者主页、标准组织、政府/实验室页面，或后续可通过学校图书馆/VPN 合法访问的出版社页面。未使用 SciDown 或任何非合规下载路径。

本轮不实际下载全文，不新增或虚构 DOI，不生成伪 BibTeX。由于原矩阵中的具体条目均未同时记录 DOI、BibTeX 和 access date，当前没有任何条目可标为终稿已支撑引用。

### 0.1 新核验等级

| 等级 | 定义 | 论文中可怎么用 | 终稿状态 |
|---|---|---|---|
| V3 | verified peer-reviewed with DOI/BibTeX/access date；已核同行评议状态、DOI、BibTeX 和访问日期 | 可支撑终稿中的具体文献句、gap 句和参考文献表 | final-ready |
| V2 | open source/preprint/official source verified；已定位合法开放全文、预印本、标准或官方页面，但尚未补齐 V3 字段 | 只能作为 source-verified candidate；可提示后续人工阅读全文和补 BibTeX | pending-final |
| V1 | candidate/meta only；只核到题名、摘要页、机构页、检索方向或元数据 | 只能作为 candidate/search lead；不得写入终稿具体结论 | pending |

强制门槛：没有 DOI/BibTeX/access date 的条目不得作为已支撑终稿，只能作为 candidate。若官方标准或政府/实验室页面确无 DOI，也必须在 citation record 中明确记录 `DOI: N/A, official source checked`、BibTeX/等价引用格式和 access date；否则仍为 candidate。

### 0.2 当前状态总览

| 状态 | 数量 | 说明 |
|---|---:|---|
| V3 final-ready | 0 | 原矩阵未记录 DOI/BibTeX/access date，本轮不补造元数据 |
| V2 source-verified candidate | 16 | 有开放/预印本/官方来源线索，但终稿字段未补齐 |
| V1 meta/search candidate | 16 | 包含 13 条具体候选和 3 条 timestamp/out-of-order/buffered direct-evidence 检索占位 |

### 0.3 进入论文前 citation record 必填字段表

| 字段 | 必填内容 | 未填时处理 |
|---|---|---|
| Citation key | 与 BibTeX 一致的唯一键，例如 `AuthorYearShortTopic` | 不进入正文引用 |
| title | 论文、标准或报告完整题名 | 不进入正文引用 |
| authors | 作者、组织作者或标准组织 | 不进入正文引用 |
| year | 发表年、版本年或预印本年份 | 不进入正文引用 |
| venue | 期刊、会议、标准号、arXiv、机构库或报告系列 | 不进入正文引用 |
| DOI | DOI；若官方确认无 DOI，写 `N/A` 并说明原因 | 非 V3，保持 candidate |
| BibTeX | 可复现引用条目，需与 citation key 一致 | 非 V3，保持 candidate |
| URL | 出版社页、DOI、arXiv、机构库、作者主页、标准组织或政府/实验室页面 | 不进入正文引用 |
| source type | peer-reviewed article、conference paper、preprint、standard、government/lab page、institutional repository 等 | 不进入正文引用 |
| peer-review status | peer-reviewed、accepted preprint、preprint only、standard、unknown 等 | 未确认时不得写成同行评议证据 |
| access date | 合法访问和核验日期，格式 `YYYY-MM-DD` | 非 V3，保持 candidate |
| used sentence | 论文正文准备使用的一句话，必须被来源直接支撑 | 不写具体 claim |
| gap sentence | 与本文差异的一句话，只能写“未显式覆盖本文组合问题” | 不写 novelty/gap claim |

### 0.4 写作安全原则

- 文献矩阵里的“已有工作做什么”只写题名、摘要、标准页面能支撑的范围性信息。
- “未考虑什么”只能写“未显式覆盖本文组合问题”，不能写“该工作失败/无效”。
- baseline 仍按上一轮文件处理：未冻结 T1 fairness gate 前，只能做机制范围对照，不能写数值优越性。
- 所有 `V2` 和 `V1` 条目在主文中均需标注为 pending citation，直到补齐 citation record。

## 1. Citation-key 候选池

下表给出本矩阵可追踪的 citation-key 占位。`V2` 表示已有合法开放/预印本/官方来源线索；`V1` 表示候选或元数据线索。由于 DOI/BibTeX/access date 尚未补齐，所有条目的 `Final support` 当前均为 `No`。

### 1.1 DCN-native 候选池

| Citation key | 类别 | 条目和合法来源线索 | Level | Final support | 安全用途 |
|---|---|---|---:|---|---|
| `ETSI2024BasicSetApplications` | V2X/CAV/CACC 通信退化 | ETSI TR 102 638 V2.1.1, `Intelligent Transport Systems; Vehicular Communications; Basic Set of Applications; Release 2`, 2024, https://www.etsi.org/deliver/etsi_tr/102600_102699/102638/02.01.01_60/tr_102638v020101p.pdf | V2 | No: BibTeX/access date/official no-DOI status pending | 只支撑 C-ACC/V2X 场景和消息侧语境 |
| `BonabSargolzaei2024CACCDelay` | V2X/CAV/CACC 通信退化 | Bonab and Sargolzaei, `A Nonlinear Control Design for Cooperative Adaptive Cruise Control with Time-Varying Communication Delay`, Electronics, 2024, https://www.mdpi.com/2079-9292/13/10/1875 | V2 | No: DOI/BibTeX/access date pending | 只支撑 CACC 研究显式讨论 time-varying communication delay |
| `ORNL2024TrajectoryShaper` | V2X/CAV/CACC 通信退化 | ORNL, `Trajectory Shaper: A Solution for Disrupted Cooperative Adaptive Cruise Control`, 2024, https://www.ornl.gov/publication/trajectory-shaper-solution-disrupted-cooperative-adaptive-cruise-control | V1 | No: publication metadata/DOI/BibTeX/access date pending | 只能作为 disrupted CACC 语境候选 |
| `Lan2024DataDrivenCACC` | V2X/CAV/CACC + data-driven control | Lan, `Data-driven cooperative adaptive cruise control for unknown nonlinear vehicle platoons`, IET ITS, 2024, https://eprints.gla.ac.uk/324251/ | V1 | No: DOI/BibTeX/access date and final venue record pending | 只能作为 data-driven CACC 候选 |
| `NIST2023WirelessTSN` | wireless multi-robot control / QoS-aware control | NIST, `Scheduling for Time-critical Applications Utilizing TCP in Software-based 802.1Qbv Wireless TSN`, WFCS 2023, https://www.nist.gov/publications/scheduling-time-critical-applications-utilizing-tcp-software-based-8021qbv-wireless-tsn | V2 | No: DOI/BibTeX/access date pending | 支撑无线机器人/time-critical traffic 场景必要性 |
| `TransmitPower2025WNCS` | QoS-aware / WNCS | `Transmit power policies for stochastic stabilisation of multi-link wireless networked control systems`, 2025, https://www.ing.uc.cl/publicaciones/transmit-power-policies-for-stochastic-stabilisation-of-multi-link-wireless-networked-control-systems/ | V1 | No: authors/venue/DOI/BibTeX/access date pending | 只能作为 WNCS QoS-control coupling 检索候选 |
| `Pang2024WNCSCodesign` | communication-control co-design | Pang et al., `Communication-Control Codesign for Large-Scale Wireless Networked Control Systems`, arXiv:2410.11316, 2024, https://arxiv.org/abs/2410.11316 | V2 | No: BibTeX/access date and peer-review status pending | 支撑 WNCS communication-control co-design 预印本语境 |
| `Ayan2024CommControl6G` | communication-control co-design / 6G | Ayan et al., `Enabling Communication and Control Co-Design in 6G Networks`, arXiv:2402.16462, 2024, https://arxiv.org/abs/2402.16462 | V2 | No: BibTeX/access date and peer-review status pending | 支撑 6G/NCS cross-layer co-design 预印本语境 |
| `RolichTurcanuBaiocchi2024AoINRV2X` | AoI / V2X | Rolich, Turcanu and Baiocchi, `AoI-Aware and Persistence-Driven Congestion Control in 5G NR-V2X Sidelink Communications`, MedComNet 2024, https://ion-turcanu.net/publication/rolich2024aoi/ | V2 | No: DOI/BibTeX/access date pending | 支撑 AoI/cooperative awareness freshness 语境 |
| `YehVarmaElayoubi2024AoISwitching` | AoI / safety switching | Yeh, Varma and Elayoubi, `AoI-based switching control for safe haptic teleoperation over a wireless network`, CDC 2024, https://zenodo.org/records/15682687 | V2 | No: DOI/BibTeX/access date pending | 支撑 stale information 和 safe switching 的相邻证据 |
| `ChenChenZhan2023ConsecutiveLoss` | bursty/consecutive loss | Chen, Chen and Zhan, `Consensus of discrete-time multi-agent systems with consecutive packet losses in directed communication topology`, 2023, https://journals.sagepub.com/doi/abs/10.1177/01423312221138892 | V1 | No: full text/BibTeX/access date pending | 只能作为 consecutive packet losses 候选 |
| `PhysicaA2024FractionalGroupConsensus` | random loss + delay consensus | `Group consensus of fractional-order heterogeneous multi-agent systems with random packet losses and communication delays`, Physica A, 2024, https://www.sciencedirect.com/science/article/abs/pii/S0378437124000554 | V1 | No: authors/DOI/BibTeX/access date pending | 只能作为 packet loss + delay consensus 候选 |
| `Automatica2024ResilientConstrainedDMPC` | resilient consensus/DMPC | `Resilient and constrained consensus against adversarial attacks: A distributed MPC framework`, Automatica, 2024, https://www.sciencedirect.com/science/article/pii/S0005109823005848 | V1 | No: authors/DOI/BibTeX/access date pending | 只能作为 resilient constrained DMPC 候选 |
| `ISATransactions2024EventTriggeredDMPCDoS` | resilient connected-vehicle DMPC | `Dynamic event-triggering-based distributed model predictive control of heterogeneous connected vehicle platoon under DoS attacks`, ISA Transactions, 2024, https://www.sciencedirect.com/science/article/pii/S0019057824003331 | V1 | No: authors/DOI/BibTeX/access date pending | 只能作为 connected vehicle DMPC under DoS 候选 |
| `Neurocomputing2023MFIntegralSlidingMPC` | predictive control under communication delay | `Model-free distributed integral sliding mode predictive control for multi-agent systems with communication delay`, Neurocomputing, 2023, https://www.sciencedirect.com/science/article/abs/pii/S0925231223012560 | V1 | No: authors/DOI/BibTeX/access date pending | 只能作为 predictive control with communication delay 候选 |
| `Arxiv2025LyapunovMPCDelayDropout` | delay/dropout LMPC | `A Lyapunov-based MPC for Distributed Multi Agent Systems with Time Delays and Packet Dropouts using Hidden Markov Models`, arXiv:2512.03708, 2025, https://arxiv.org/abs/2512.03708 | V2 | No: BibTeX/access date and peer-review status pending | 只能作为 preprint evidence，不能当成熟同行评议结论 |

### 1.2 控制/机器人候选池

| Citation key | 类别 | 条目和合法来源线索 | Level | Final support | 安全用途 |
|---|---|---|---:|---|---|
| `KanaiYamakita2023LiftedBilinearMPC` | Koopman vehicle/MPC | Kanai and Yamakita, `Lifted Bilinear Model-based Linear Model Predictive Control with Scalability`, IFAC PapersOnLine, 2023, https://www.sciencedirect.com/science/article/pii/S2405896323005839 | V2 | No: DOI/BibTeX/access date pending | 支撑 lifted bilinear Koopman model 与 MPC 的相邻语境 |
| `KoopmanMultiModel2024PredictiveControl` | Koopman / MPC prediction | `Koopman operator-based multi-model for predictive control`, Nonlinear Dynamics, 2024, https://link.springer.com/article/10.1007/s11071-024-09615-7 | V2 | No: authors/BibTeX/access date pending | 支撑 Koopman-MPC 多步预测误差传播语境 |
| `AMC2024LearningMPCTimeVaryingKoopman` | adaptive Koopman-MPC | `Learning model predictive control of nonlinear systems with time-varying parameters using Koopman operator`, Applied Mathematics and Computation, 2024, https://www.sciencedirect.com/science/article/pii/S0096300324000493 | V1 | No: authors/DOI/BibTeX/access date pending | 只能作为 adaptive/online Koopman-MPC 候选 |
| `Fu2025ResidualKoopmanVehicleMPC` | Koopman vehicle/MPC | Fu et al., `Residual Koopman Model Predictive Control for Enhanced Vehicle Dynamics with Small On-Track Data Input`, arXiv:2507.18396, 2025, https://arxiv.org/abs/2507.18396 | V2 | No: BibTeX/access date and peer-review status pending | 只能作为 vehicle residual Koopman-MPC 预印本候选 |
| `Ebel2024CooperativeObjectTransportation` | cooperative transport / DMPC | Ebel et al., `Cooperative object transportation with differential-drive mobile robots: Control and experimentation`, Robotics and Autonomous Systems, 2024, https://www.sciencedirect.com/science/article/abs/pii/S0921889023002518 | V1 | No: DOI/BibTeX/access date pending | 只能作为 cooperative object transportation 候选 |
| `SuBhowmickLanzon2023RobustAdaptivePayload` | cooperative payload transport | Su, Bhowmick and Lanzon, `A robust adaptive formation control methodology for networked multi-UAV systems with applications to cooperative payload transportation`, Control Engineering Practice, 2023, https://www.sciencedirect.com/science/article/abs/pii/S0967066123001776 | V1 | No: DOI/BibTeX/access date pending | 只能作为 networked multi-UAV payload 候选 |
| `Turrisi2024PACC` | cooperative carrying / MPC | Turrisi et al., `PACC: A Passive-Arm Approach for High-Payload Collaborative Carrying with Quadruped Robots Using Model Predictive Control`, IROS 2024/arXiv, https://arxiv.org/abs/2403.19862 | V2 | No: DOI/BibTeX/access date and final venue status pending | 支撑 collaborative carrying + MPC 的预印本/会议候选 |
| `KargarTasooji2025EventBasedPayloadNMPC` | cooperative payload / NMPC | Kargar Tasooji et al., `Cooperative Control of Multi-Quadrotors for Transporting Cable-Suspended Payloads: Obstacle-Aware Planning and Event-Based Nonlinear Model Predictive Control`, arXiv:2503.19135, 2025, https://arxiv.org/abs/2503.19135 | V2 | No: BibTeX/access date and peer-review status pending | 只能作为 event-based NMPC payload preprint 候选 |
| `Sambhus2026SafetyCriticalPayloadNMPC` | cooperative payload / safety MPC | Sambhus et al., `Safety-Critical Centralized Nonlinear MPC for Cooperative Payload Transportation by Two Quadrupedal Robots`, arXiv:2604.03200, 2026, https://arxiv.org/abs/2604.03200 | V2 | No: BibTeX/access date and peer-review status pending | 只能作为 safety-critical payload NMPC preprint 候选 |
| `NgoTsaiLiu2024FaultTolerantAllocation` | cooperative transport / FTC | Ngo, Tsai and Liu, `Actuator fault-tolerant control allocation for cooperative transportation of multiple omnidirectional mobile robots`, Advanced Robotics, 2024, https://www.tandfonline.com/doi/abs/10.1080/01691864.2023.2300695 | V1 | No: DOI/BibTeX/access date pending | 只能作为 actuator FTC allocation 候选 |
| `Manesh2025FaultTolerantDNMPC` | FTC / DMPC / Lyapunov | Manesh et al., `Fault-tolerant multi-agent formation control using distributed nonlinear MPC with discrete-time super-twisting sliding mode fault estimation`, Franklin Open, 2025, https://www.sciencedirect.com/science/article/pii/S2773186325000593 | V2 | No: DOI/BibTeX/access date pending | 支撑 distributed nonlinear MPC + fault estimation 相邻语境 |
| `Li2025EventTriggeredAFTPC` | FTC / random communication constraints | Li et al., `Event-Triggered Active Fault-Tolerant Predictive Control for Networked Multi-Agent Systems with Actuator Faults and Random Communication Constraints`, Applied Sciences, 2025, https://www.mdpi.com/2076-3417/15/11/6317 | V1 | No: DOI/BibTeX/access date and page validation pending | 只能作为 random communication constraints + FTC 候选 |
| `WangZhangWang2025SafetyCriticalDMPC` | safety / CBF / Lyapunov | Wang, Zhang and Wang, `Distributed Safety-Critical MPC for Multi-Agent Formation Control and Obstacle Avoidance`, arXiv:2508.19678, 2025, https://arxiv.org/abs/2508.19678 | V2 | No: BibTeX/access date and peer-review status pending | 只能作为 safety-critical DMPC preprint 候选 |

### 1.3 P0 direct-evidence placeholders

这些不是已支撑文献，而是 Reviewer 1 要求补强的直接检索槽位。补到 V3/V2 之前，不得把 timestamp/out-of-order/buffered exchange 写成强 novelty claim。

| Citation key | 缺口 | Level | Final support | 推荐检索方向 |
|---|---|---:|---|---|
| `TimestampOutOfOrderDirectPending` | timestamped neighbor state exchange + out-of-order packet handling | V1 | No | `timestamped neighbor state exchange consensus control`, `out-of-order packet networked control MPC` |
| `BufferedNeighborPredictionPending` | buffered neighbor prediction / state-age aligned MPC | V1 | No | `buffered neighbor prediction distributed MPC delay compensation`, `state age neighbor prediction MPC` |
| `AsyncDMPCReorderingPending` | asynchronous DMPC under packet reordering and delay | V1 | No | `asynchronous distributed MPC packet reordering`, `packet reordering multi-agent consensus control` |

## 2. DCN-native 主题矩阵

| DCN-native 类别 | Citation keys | 当前支撑状态 | 本文可补什么 | 放在论文哪里 | 优先级 |
|---|---|---|---|---|---:|
| V2X/CAV/CACC 通信退化 | `ETSI2024BasicSetApplications`; `BonabSargolzaei2024CACCDelay`; `ORNL2024TrajectoryShaper`; `Lan2024DataDrivenCACC` | V2 source-verified: ETSI, Bonab; V1 pending: ORNL, Lan; V3: none | 把 V2X/CACC 退化变量转译为 delay/dropout/topology/AoI stress tests，但不声称其证明 cooperative payload control 有效 | Introduction network-resilient motivation; Method communication model; Experiments delay/dropout/topology protocol | P0 |
| wireless multi-robot control | `NIST2023WirelessTSN` | V2 source-verified; V3: none | 把 latency、jitter、PDR、buffer age 和 recovery time 作为控制实验指标，而不仅是网络指标 | Introduction DCN-native paragraph; Experiments network metrics table | P0 |
| QoS-aware control | `TransmitPower2025WNCS`; `Pang2024WNCSCodesign`; `Ayan2024CommControl6G` | V2 source-verified: Pang, Ayan; V1 pending: TransmitPower; V3: none | 让 QoS 指标进入 MPC 的 prediction freshness、constraint tightening 或 fallback trigger | Method QoS-to-control mapping; Ablation QoS sweep | P0 |
| communication-control co-design | `Pang2024WNCSCodesign`; `Ayan2024CommControl6G` | V2 source-verified; V3: none | 将通信退化建模为控制优化链路内的状态新鲜度、邻居预测和安全降级变量 | Introduction co-design gap; Method algorithm overview | P0 |
| asynchronous/timestamped exchange | `YehVarmaElayoubi2024AoISwitching`; `RolichTurcanuBaiocchi2024AoINRV2X`; `TimestampOutOfOrderDirectPending`; `BufferedNeighborPredictionPending`; `AsyncDMPCReorderingPending` | V2 adjacent only: Yeh, Rolich; direct evidence pending: 3 placeholders; V3: none | 可写为本文方法实现细节和待补文献缺口，不可写成强 novelty claim | Method communication buffer / timestamp alignment; Algorithm box; Limitations | P0 |
| AoI | `RolichTurcanuBaiocchi2024AoINRV2X`; `YehVarmaElayoubi2024AoISwitching` | V2 source-verified adjacent; V3: none | 把 AoI 作为 stale-neighbor compensation 和 safe degraded mode 的触发/权重变量，并用本文实验报告 AoI-error 曲线 | Introduction AoI gap; Method AoI variable; Experiments AoI sweep | P0 |
| bursty loss / jitter | `ChenChenZhan2023ConsecutiveLoss`; `PhysicaA2024FractionalGroupConsensus`; `Arxiv2025LyapunovMPCDelayDropout` | V2 source-verified: arXiv LMPC; V1 pending: Chen, Physica A; V3: none | 加入 burst-length、Gilbert-Elliott 或 bounded outage window，并报告 recovery time | Experiments communication stress protocol; Theory assumptions maximum burst/dwell-time | P0 |
| resilient consensus / DMPC | `Automatica2024ResilientConstrainedDMPC`; `ISATransactions2024EventTriggeredDMPCDoS`; `Neurocomputing2023MFIntegralSlidingMPC`; `Arxiv2025LyapunovMPCDelayDropout` | V2 source-verified: arXiv LMPC; V1 pending: Automatica/ISA/Neurocomputing; V3: none | 合并 resilient consensus/DMPC、bilinear Koopman prediction、载荷约束和 FTC/safety | Introduction DMPC/resilience paragraph; Method consensus MPC; Theory UUB/practical stability | P0 |

## 3. 控制/机器人主题矩阵

| 控制/机器人类别 | Citation keys | 当前支撑状态 | 本文可补什么 | 放在论文哪里 | 优先级 |
|---|---|---|---|---|---:|
| Koopman vehicle/MPC | `KanaiYamakita2023LiftedBilinearMPC`; `KoopmanMultiModel2024PredictiveControl`; `AMC2024LearningMPCTimeVaryingKoopman`; `Fu2025ResidualKoopmanVehicleMPC` | V2 source-verified: Kanai, KoopmanMultiModel, Fu; V1 pending: AMC; V3: none | 面向车辆-载荷耦合构建 bilinear Koopman predictor，并服务于 consensus MPC 而非单车 tracking | Introduction Koopman paragraph; Method Koopman model; Experiments prediction/rollout table | P0 |
| cooperative transport | `Ebel2024CooperativeObjectTransportation`; `SuBhowmickLanzon2023RobustAdaptivePayload`; `Turrisi2024PACC`; `KargarTasooji2025EventBasedPayloadNMPC`; `Sambhus2026SafetyCriticalPayloadNMPC` | V2 source-verified: Turrisi, Kargar, Sambhus; V1 pending: Ebel, Su; V3: none | 绑定 cooperative transport 的 payload/formation/force 指标与 DCN 通信退化指标 | Introduction cooperative transport paragraph; Method vehicle-load model; Experiments payload/force plots | P0 |
| DMPC/MPC | `KanaiYamakita2023LiftedBilinearMPC`; `Turrisi2024PACC`; `Manesh2025FaultTolerantDNMPC`; `Automatica2024ResilientConstrainedDMPC`; `ISATransactions2024EventTriggeredDMPCDoS` | V2 source-verified: Kanai, Turrisi, Manesh; V1 pending: Automatica, ISA; V3: none | 用 delay-compensated consensus MPC 统一 learned dynamics、neighbor prediction、constraints 和 safety fallback | Method MPC formulation; Theory feasibility/stability boundary; Ablation without compensation | P0 |
| FTC/safety/Lyapunov | `NgoTsaiLiu2024FaultTolerantAllocation`; `Manesh2025FaultTolerantDNMPC`; `Li2025EventTriggeredAFTPC`; `WangZhangWang2025SafetyCriticalDMPC`; `Sambhus2026SafetyCriticalPayloadNMPC` | V2 source-verified: Manesh, Wang, Sambhus; V1 pending: Ngo, Li; V3: none | 加入 FDI/FTC、控制重分配、安全降级，并把理论结论限制为 practical stability/UUB | Method FTC/safety layer; Theory certificate; Experiments fault/safety ablation | P0/P1 |

## 4. 贡献点到 citation-key 支撑矩阵

每个贡献点映射 3-5 条 citation-key 占位。`Verified-source` 仅表示 V2 来源线索已存在；它仍不是 V3 final-ready。`Pending` 包括所有 V1 候选和所有尚未补 DOI/BibTeX/access date 的条目。

| 贡献点 | 3-5 条 citation-key 占位 | Verified-source | Pending / 不可终稿使用 | 写作边界 |
|---|---|---|---|---|
| C1. Bilinear Koopman vehicle-load predictor for cooperative transport | `KanaiYamakita2023LiftedBilinearMPC`; `KoopmanMultiModel2024PredictiveControl`; `Turrisi2024PACC`; `Ebel2024CooperativeObjectTransportation`; `AMC2024LearningMPCTimeVaryingKoopman` | V2: Kanai, KoopmanMultiModel, Turrisi | V1: Ebel, AMC; all keys missing V3 fields | 可写 Koopman-MPC、collaborative carrying 和 cooperative object transport 是相邻研究线；不能写这些文献已支撑本文 vehicle-load bilinear predictor 的终稿 claim |
| C2. Delay-compensated consensus MPC with timestamped neighbor prediction | `BonabSargolzaei2024CACCDelay`; `Pang2024WNCSCodesign`; `YehVarmaElayoubi2024AoISwitching`; `ISATransactions2024EventTriggeredDMPCDoS`; `TimestampOutOfOrderDirectPending` | V2: Bonab, Pang, Yeh | V1: ISA, TimestampOutOfOrderDirectPending; all keys missing V3 fields | 可写 delay/loss/AoI 是相邻问题；direct timestamp/out-of-order 证据未补前，不能把 timestamped neighbor prediction 写成强 novelty claim |
| C3. DCN-native QoS/AoI/bursty-loss resilience layer | `NIST2023WirelessTSN`; `Ayan2024CommControl6G`; `RolichTurcanuBaiocchi2024AoINRV2X`; `ChenChenZhan2023ConsecutiveLoss`; `Arxiv2025LyapunovMPCDelayDropout` | V2: NIST, Ayan, Rolich, arXiv LMPC | V1: Chen; all keys missing V3 fields | 可写 DCN 指标和控制韧性需要桥接；不能写 AoI/QoS 必然改善 payload tracking，必须由本文实验证明 |
| C4. FDI/FTC and safety fallback under network/fault degradation | `Manesh2025FaultTolerantDNMPC`; `WangZhangWang2025SafetyCriticalDMPC`; `Sambhus2026SafetyCriticalPayloadNMPC`; `NgoTsaiLiu2024FaultTolerantAllocation`; `Li2025EventTriggeredAFTPC` | V2: Manesh, Wang, Sambhus | V1: Ngo, Li; all keys missing V3 fields | 可写 FTC/safety/DMPC 是相邻支撑线；不能写覆盖所有故障类型或保证任意通信故障下渐近稳定 |
| C5. Publication-safe baseline and experiment evidence protocol | `KanaiYamakita2023LiftedBilinearMPC`; `AMC2024LearningMPCTimeVaryingKoopman`; `ETSI2024BasicSetApplications`; `RolichTurcanuBaiocchi2024AoINRV2X`; `Turrisi2024PACC` | V2: Kanai, ETSI, Rolich, Turrisi | V1: AMC; all keys missing V3 fields | baseline 只能做机制范围对照；若要写 outperforms，必须冻结同数据、同 solver、同 horizon、同通信退化注入、同 seed/CI |

## 5. Timestamped/out-of-order/buffered exchange 的 P0 风险门禁

Reviewer 1 特别关注 timestamped/out-of-order/buffered neighbor exchange。当前矩阵只有 AoI、delay/loss、co-design 和 asynchronous/safe-switching 的相邻文献线索，没有直接支撑 `timestamped neighbor state + out-of-order packet + buffered prediction alignment` 的 V3 或 V2 近邻文献。

| 风险项 | 当前证据 | 论文前门禁 | 安全写法 |
|---|---|---|---|
| timestamped neighbor state | `RolichTurcanuBaiocchi2024AoINRV2X`; `YehVarmaElayoubi2024AoISwitching` 仅相邻支撑 AoI/stale information | 需补 `TimestampOutOfOrderDirectPending` 至 V2/V3 | “Each received neighbor state is stored with a timestamp and propagated before entering the local MPC.” |
| out-of-order packet handling | 直接文献为空 | 需补 out-of-order packet / packet reordering control 文献至 V2/V3 | 只能作为实现机制或实验条件，不写成 literature novelty |
| buffered neighbor prediction | 直接文献为空 | 需补 buffered prediction / state-age aligned DMPC 文献至 V2/V3 | “Buffered neighbor prediction is used to align stale measurements under bounded delay/loss.” |
| strong novelty claim | 当前不可支撑 | 至少补 2-3 条 V3/V2 直接近邻文献，并完成 gap sentence | 不写 “first/novel timestamped out-of-order neighbor exchange”；可写 “we integrate timestamped buffers with the proposed Koopman-consensus MPC and evaluate it under communication stress tests.” |

结论：在补齐直接文献前，timestamp/out-of-order/buffered exchange 只能作为本文控制器的实现机制和实验变量，不能作为强 novelty claim 或“首次解决”的主要贡献。

## 6. 推荐检索关键词和优先级

| 优先级 | 主题 | 推荐关键词 | 目标来源 |
|---:|---|---|---|
| P0 | timestamp/out-of-order/buffered neighbor exchange | `timestamped neighbor state exchange consensus control`; `out-of-order packet networked control MPC`; `buffered neighbor prediction distributed MPC`; `asynchronous distributed MPC packet reordering` | IEEE TCNS/TAC/CDC, Automatica, IFAC, arXiv |
| P0 | V2X/CAV/CACC 通信退化 | `CACC communication delay packet loss jitter 2024`; `CAV platoon DoS packet loss distributed MPC`; `V2X cooperative adaptive cruise control AoI` | IEEE Xplore, Transportation Research, IET ITS, ETSI, ORNL, arXiv |
| P0 | wireless multi-robot control | `wireless multi robot control latency jitter QoS`; `wireless TSN collaborative robots object transport`; `communication-aware multi-robot systems control` | IEEE, ACM, NIST, ICRA/IROS/RSS workshops, author pages |
| P0 | QoS-aware control | `QoS-aware networked control systems latency jitter packet delivery ratio`; `wireless networked control stability QoS`; `control-aware scheduling WNCS` | IEEE TWC/TCNS/TAC, Automatica, arXiv |
| P0 | communication-control co-design | `communication control co-design 6G networked control systems`; `large-scale wireless networked control co-design scheduling control`; `integrated sensing communication control co-design` | IEEE JSAC/TWC/TCNS, arXiv, publisher pages |
| P0 | AoI | `Age of Information control multi-agent consensus`; `AoI safe switching control wireless teleoperation`; `AoI V2X sidelink cooperative awareness` | IEEE, CDC, MedComNet, arXiv, institutional repositories |
| P0 | bursty loss/jitter | `bursty packet loss consensus multi-agent`; `Gilbert Elliott packet loss distributed MPC`; `consecutive packet losses directed communication topology consensus`; `packet delay variation control` | Automatica, Information Sciences, Sage/IJC, IEEE |
| P0 | resilient consensus/DMPC | `resilient consensus distributed MPC adversarial attacks`; `DMPC connected vehicle platoon DoS attacks`; `network predictive control multi-agent communication delay` | Automatica, ISA Transactions, Neurocomputing, IEEE |
| P0 | Koopman vehicle/MPC | `Koopman MPC vehicle dynamics 2024`; `bilinear Koopman MPC control affine robot`; `adaptive Koopman MPC time-varying parameters` | ScienceDirect, Springer, IEEE, arXiv |
| P0 | cooperative transport | `cooperative object transportation mobile robots DMPC`; `multi robot payload transport MPC`; `cooperative payload transportation safety MPC` | RAS, IROS, ICRA, RSS, arXiv, Springer |
| P1 | FTC/safety/Lyapunov | `fault tolerant distributed MPC multi-agent`; `control allocation cooperative transportation actuator fault`; `distributed safety critical MPC CBF CLF multi-agent` | Advanced Robotics, Franklin Open, IEEE, arXiv |

## 7. 合法来源类型

| 来源类型 | 可用性 | 注意事项 |
|---|---|---|
| 出版社开放摘要页 | V1 | 只能写摘要级事实；不能下载付费全文 |
| Open Access 全文 | V2，补齐 DOI/BibTeX/access date 后可升 V3 | 记录 license、DOI、BibTeX、访问日期和 peer-review status |
| arXiv / institutional repository | V2 或 V1 | 标注 preprint/accepted status，不把预印本当作已发表结论 |
| 标准组织和政府/实验室页面 | V2 或 V1 | 不等同于控制算法证明；若无 DOI，需记录 official no-DOI status |
| 作者主页 / ResearchGate 作者上传 | V1/V2，需谨慎 | 只使用作者合法上传版本；避免 request-only 或不明来源 PDF |
| 学校图书馆/VPN | 可用于 V3 核验 | 由用户配置后合法访问；不得绕过授权 |
| SciDown / 非授权下载站 | 禁用 | 不记录、不访问、不作为来源 |

## 8. 不能写进论文的未核验 claim 清单

- 不能写“本文优于 Adaptive Koopman baseline”，除非 T1 fairness gate 完成同数据、同 solver、同 horizon、同采样周期、同通信退化注入、同 seed/CI。
- 不能写“baseline 在通信退化下失败/不稳定”，除非在同一任务适配、同一约束和同一退化序列下实测。
- 不能写“本文是第一个/首次同时解决 Koopman、DMPC、AoI、协同运输和 FTC 的方法”，除非完成系统性检索并证明没有近邻工作。
- 不能写“timestamped/out-of-order/buffered neighbor exchange 是本文强 novelty”，除非补到直接 V3/V2 文献并完成 citation record。
- 不能写“V2X/CACC 文献已经证明本文多机器人载荷运输有效”；V2X/CACC 只能支撑网络退化语境。
- 不能写“AoI 优化必然降低 payload tracking error”；必须用本文 AoI sweep 或 ablation 证明。
- 不能写“QoS-aware control 等同于安全稳定性保证”；QoS 是通信侧输入，稳定性需本文理论和实验支撑。
- 不能写“bursty loss/jitter 模型来自真实 5G/V2X 分布”，除非引用真实数据集或标准参数并说明映射。
- 不能写“Koopman bilinear 模型必然优于 linear Koopman 或 adaptive Koopman”；必须报告 prediction、tracking、solver time 和 fairness gate。
- 不能写“本文保证任意持续丢包或任意拓扑断连下渐近稳定”；更安全写法是 bounded delay/loss/dwell-time 假设下的 practical stability/UUB。
- 不能写“FTC/safety 模块覆盖传感器、执行器、通信和整车失效所有故障类型”；只写实验和理论实际覆盖的 fault modes。
- 不能写“安全约束从未违反”，除非实验统计报告 constraint violation rate 和 worst-case margin。
- 不能写“协同运输性能只由 tracking error 证明”；必须同时报告 payload pose、formation/consensus error、force smoothness、constraint violation、recovery time 和 solver time。

## 9. 论文插入建议

| 论文位置 | 应插入内容 | 安全句式 |
|---|---|---|
| Introduction: DCN motivation | V2X/CACC、wireless robot、AoI、QoS、bursty loss、resilient DMPC 作为 DCN-native 背景 | “Recent DCN-facing studies characterize cooperative control degradation through latency, packet loss, AoI, link quality and DoS/topology changes; however, these metrics are rarely integrated with learned cooperative transport dynamics.” |
| Introduction: Koopman paragraph | Koopman-MPC 和 vehicle/robot Koopman work | “Koopman lifting enables MPC-friendly prediction for nonlinear systems, but most recent Koopman-MPC studies do not make timestamped lossy neighbor exchange an internal variable of the controller.” |
| Introduction: cooperative transport paragraph | payload transport, distributed optimization, MPC, force/safety metrics | “Cooperative transport studies define the payload and formation metrics needed by this paper, while their communication assumptions are often stronger than the DCN setting studied here.” |
| Method: communication model | timestamp, AoI/state age, delay, dropout, burst, topology | “Each received neighbor state is stored with a timestamp; stale states are propagated through the local predictor before entering the consensus MPC.” |
| Method: MPC and safety | delay-compensated consensus MPC, constraint tightening, safe fallback | “The controller treats communication degradation as a prediction and constraint-management problem rather than as an unmodeled disturbance only.” |
| Theory | bounded delay/loss, dwell time, model mismatch, UUB/practical stability | “Under bounded communication degradation and prediction error assumptions, the closed loop is argued toward practical boundedness rather than unconditional asymptotic stability.” |
| Experiments | communication stress suite and DCN metrics | “Report delay, jitter, packet loss, burst length, AoI, topology degradation, recovery time, payload pose, formation error, force smoothness, constraint violation and solver time.” |
| Limitations | timestamp/out-of-order direct literature not yet V3/V2 | “Direct literature on timestamped out-of-order neighbor-buffer prediction remains a citation-gate item before the claim can be framed as a strong novelty.” |

## 10. Immediate P0 follow-up for main integration

1. For every candidate source, complete citation record fields: title, authors, year, venue, DOI, URL, source type, peer-review status, access date, used sentence, gap sentence, and BibTeX.
2. Promote only sources with peer-reviewed status, DOI/BibTeX/access date and checked used/gap sentences to V3.
3. Add at least 2-3 direct timestamp/out-of-order/buffered neighbor prediction sources before making any strong novelty claim around timestamped exchange.
4. Keep all V1 and V2 entries out of final reference-supported claims until the citation record is complete.
5. Keep the baseline claim boundary from `02_literature_baseline_gap_map.md`: mechanism-level comparison is safe now; numerical superiority is not.
