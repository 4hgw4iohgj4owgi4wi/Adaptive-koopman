# Worker E：中文稿集成补丁计划

## 0. 集成目标与边界

目标文件是后续主 Agent 要处理的中文 DOCX：

`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

本文件只给出集成补丁计划，不修改 DOCX。Round 2 集成的核心目标是把当前“TF14 阶段性中文稿”改成“面向 DCN 投稿的 baseline-facing 中文主稿”：所有新颖性、文献、理论和实验结论都必须面向 `Adaptive Koopman Embedding` baseline 与近三年相关文献，而不是面向 TF12/TF13/TF14 内部历史。

集成前置条件：

| 门槛 | 必须满足后才能写进主结论 | 未满足时允许写法 |
|---|---|---|
| T1 baseline fairness gate | AKE baseline 状态、训练数据、通信 trace、约束、solver、dt、horizon、seed 和统计口径冻结 | 只能写机制差异和任务适配差异，不能写 superiority |
| 文献矩阵 | 每个贡献点至少对应合法来源文献、gap、本文模块和验证证据 | 只能写“需要补充文献支撑”，不能写“首次/显著创新” |
| 方法-证明桥接 | 从 `u_i^{mpc}` 到团队闭环 `A_\sigma/B_\sigma` 的链路写清 | Lyapunov 只能保留为证书记录或直观解释 |
| 实验门槛 | 主结论用 `n>=20` paired seeds、fresh training seeds、95% CI、failure count 和 provenance | `n=1` 只能作为代表性案例或趋势图 |
| claim 限制 | 稳定性、鲁棒性、安全性、baseline 对比均按假设边界写 | 删除或降级过强结论 |

证据状态字段硬规则：所有 Round 2 新增表、图、公式在清单、题注、表注或公式说明中必须带 `evidence_status` 字段，取值只能为 `ready`、`pending`、`representative`、`stress-test`。未标 `ready` 的材料不得写成已完成主证据。

| `evidence_status` | 使用边界 | 禁止写法 |
|---|---|---|
| `ready` | T1/文献/证明/实验/QA 门槛均已满足，可进入主文证据链 | 不得省略 provenance、seed、run id、公式 QA 或引用来源 |
| `pending` | 计划插入、待补数据、待补文献、待推导或待 QA | 不得作为结果、贡献或证明结论 |
| `representative` | 单 seed、少量 seed、示意图、代表性 run 或趋势图 | 不得写统计显著、failure rate 改善或主结论 |
| `stress-test` | 超出主理论假设或用于边界压力测试 | 不得支持一般性稳定性、鲁棒性或网络控制优越性 claim |

## 1. 逐章集成补丁计划

### 1.1 摘要

当前位置：DOCX 第 0 章摘要当前直接写“TF14 网络韧性协同控制框架”，并含有相对 baseline 的效果倾向。

应插入的 Round 2 内容：

| 内容 | 插入位置 | 写法要求 |
|---|---|---|
| T1 baseline | 摘要后半段结果句 | 只有 T1 冻结且主实验达标后，才写“相对 task-aligned AKE baseline 的量化结果”；否则改为“构建了可审计的 task-aligned AKE baseline 比较协议” |
| 文献矩阵 | 摘要第一句之后的 gap 句 | 用一句话概括 gap：现有 Koopman-MPC、协同搬运和网络韧性控制通常分开处理，缺少通信退化下的团队级闭环证据 |
| 方法-证明桥接 | 方法概述句 | 明确“从局部 Koopman-MPC、通信质量感知一致性、FTC 到团队闭环证书的控制链” |
| 实验门槛 | 结果句 | 结果必须带 paired seeds、95% CI 或 failure count；未完成时写“代表性仿真表明趋势，投稿前需多 seed 验证” |
| claim 限制 | 最后一句 | 稳定性写成“有界扰动和驻留时间假设下的 ISS-practical/UUB 保证”，不得写全局渐近稳定 |

删除或降级：

| 当前风险表述 | 处理 |
|---|---|
| “TF14 网络韧性协同控制框架”作为摘要开头 | 改为“本文提出一种面向退化通信网络的四车协同运输控制框架”，TF14 仅作为内部实现名，不进摘要 |
| “与 baseline 相比显著优于” | T1 和 `n>=20` 未冻结前删除“显著/优于”，改为“机制上补足 baseline 未覆盖的通信与执行退化链路” |
| “完整控制框架” | 若证据未闭合，改为“集成式控制框架” |

### 1.2 引言

当前位置：DOCX 第 1 章已有 Koopman、车辆控制、协同搬运、MPC、通信干扰段落，但仍夹杂“本文比较逻辑不是历史版本”“TF14 相对原始 AKE”等内部叙事。

应插入的 Round 2 内容：

| 内容 | 插入位置 | 写法要求 |
|---|---|---|
| 文献矩阵 | Koopman、协同搬运、MPC、DCN-native 通信控制段落之后 | 按 `已发表工作 -> 未覆盖 gap -> 本文模块` 写，每条文献必须来自合法来源 |
| T1 baseline | 引言末尾问题定义前 | 解释 baseline 选择：原始 AKE 是模型层 baseline，本文构建 task-aligned AKE 作为任务公平比较对象 |
| claim 限制 | 引言最后一段 | 明确本文不声称任意网络故障下稳定，也不声称所有指标优于 baseline |
| 实验门槛 | 引言贡献前的证据边界句 | 写明主结论将由 paired multi-seed 统计和公平 baseline gate 支撑 |

删除或降级：

| 当前风险表述 | 处理 |
|---|---|
| “TF14 相对于原始 AKE 思路...” | 改为“本文相对于 AKE 类 Koopman 自适应控制思路...” |
| “最新 TF14 主方法已经...” | 改为“本文方法将...纳入闭环” |
| 引言中对具体配置的过早描述 | 移到方法或实验设置，避免引言像版本说明 |

### 1.3 贡献

当前位置：贡献目前在引言末尾以 4 个紧凑段落呈现，内容基本覆盖模型、Koopman、控制栈、实验链，但缺少严格的“贡献-文献 gap-方法模块-证据”闭环。

应插入的 Round 2 内容：

| 贡献 | 需要插入的 Round 2 内容 | 证据边界 |
|---|---|---|
| 网络感知 DCC-MPC | 文献矩阵中的 DCN-native delay/dropout/jitter/topology gap；T1 fairness 中同 trace 比较要求 | 未完成 dose-response 前，只写机制和实验计划，不写鲁棒优越性 |
| 四车载荷协同模型 | 文献矩阵中的 cooperative transport / payload-aware MPC gap；方法-证明桥接中的团队状态定义 | 只声称“统一建模与指标”，不声称真实硬件泛化 |
| 双线性 Koopman predictor | T1 baseline 中 AKE-R/AKE-A/AKE-M 状态；fresh training seed 门槛 | fresh seeds 未完成前，不写学习器统计显著优于 |
| FDI/FTC/安全证书 | 方法-证明桥接、Lyapunov UUB 边界、实验门槛中的 violation/fallback/certificate log | 不写“完全容错/保证安全”，写“有界退化下的可诊断重构与安全降级” |

贡献改写模板：

> 在 [文献线索] 的基础上，本文增加 [具体模块]；其机理是 [为什么能缩小 gap]；该模块通过 [T1/表/图/消融/证明] 验证。在 [假设边界] 外，本文仅作为 stress-test 报告，不作保证性结论。

### 1.4 相关工作

当前位置：当前稿件没有单独“相关工作”章，相关工作融入第 1 章。建议在引言中新增 `1.1 相关工作与研究差距`，或在保持期刊格式时将其作为引言内部小节。

应插入的 Round 2 内容：

| 文献类别 | 插入位置 | 必须覆盖的 gap |
|---|---|---|
| Koopman learning / AKE / bilinear Koopman MPC | 相关工作第 1 组 | AKE 主要解决模型失配，未覆盖四车刚性载荷、退化通信和未知执行器故障的团队闭环 |
| Cooperative transport / payload-aware MPC | 相关工作第 2 组 | 现有搬运工作通常不把 Koopman predictor、通信质量和故障重构放入统一证据链 |
| DCN-native 通信控制 | 相关工作第 3 组 | delay、dropout、jitter、burst、topology、QoS/AoI 与控制闭环指标之间缺少 task-level baseline 比较 |
| Fault tolerance / safety constraints | 相关工作第 4 组 | 执行器退化、FDI、fallback 和 load safety 指标常与学习预测器分离 |
| Stability certificates | 相关工作第 5 组 | 现有证明通常不解释从分布式 MPC 命令到团队等效闭环矩阵的桥接 |

新增表：

| 表号建议 | 位置 | 内容 | `evidence_status` |
|---|---|---|---|
| 表 R1 | `1.1 相关工作与研究差距` 末尾 | 文献矩阵：类别、代表文献、处理的问题、未覆盖 gap、本文模块、对应实验/证明 | 初始 `pending`；所有文献来源合法且 gap-模块-证据闭合后改为 `ready` |
| 表 R2 | 引言贡献前，可选 | 贡献-证据矩阵：贡献、方法模块、理论支撑、实验门槛、允许 claim | 初始 `pending`；每个贡献都有方法、证明/实验和 claim 边界后改为 `ready` |

删除或降级：

| 风险 | 处理 |
|---|---|
| 使用“近三年研究已经证明本文方向必要”但无具体文献 | 必须替换为矩阵中的真实文献和具体 gap |
| 将原始 AKE 描述为“弱 baseline” | 改为“解决层级不同；本文构建 task-aligned baseline 做公平验证” |

### 1.5 方法

当前位置：第 2-4 章已包含系统模型、Koopman 模型、MPC、通信一致性、FTC、4.6 方法增量、4.7 TF14 新增、4.8 Lyapunov。主要问题是方法描述仍偏版本化，且从局部命令到团队闭环证明的桥接不够硬。

应插入的 Round 2 内容：

| 方法位置 | 插入内容 | 目的 |
|---|---|---|
| 第 2 章末尾 | 统一符号表：`x_i`、`x_c`、`z_i`、`q_{ij,k}`、`d_{ij,k}`、`u_i^{mpc}`、`u_i^{comm}`、`u_i^{ftc}`、`u_c^{agg}`、`e_k`、`\sigma_k` | 避免后文证明变量跳变 |
| 第 3.2 | 与 T1 baseline 对齐的 Koopman 结构差异表 | 区分任务化 AKE baseline 与本文 predictor，但不提前 claim superiority |
| 第 3.3 | 在线自适应降级说明 | 若主 preset 默认关闭在线更新，则只作为可选模块/消融，不作主贡献收益 |
| 第 4.3 | 通信模型补丁：delay/dropout/jitter/link quality/timestamp 和 neighbor prediction | 支撑 DCN 主题，而不是只写控制器内部权重 |
| 第 4.5 | FDI/FTC 与通信退化的判别边界 | 防止把网络抖动误写成执行器故障 |
| 第 4.6 后 | 新增 `4.x 控制链到团队闭环的证明桥接` | 把方法和 Lyapunov 证明连接起来 |

控制链桥接必须写清：

| 链路 | 必须说明 |
|---|---|
| `u_i^{mpc}` | 局部 Koopman-MPC 根据 lifted predictor、约束和本车误差求得 |
| `u_i^{comm}` | 通信质量感知一致性和时延补偿对局部命令/邻居状态做修正 |
| `u_i^{ftc}` | FDI/FTC 根据效率估计和故障模式重构可执行命令 |
| `u_c^{agg}` | 团队聚合器把四车命令映射为载荷中心等效力/力矩 |
| `e_{k+1}=A_{\sigma_k} e_k+B_{\sigma_k} w_k+r_{\sigma_k,k}` | 这是证明层的团队等效闭环，不得直接等同离线 Koopman 矩阵 |

删除或降级：

| 当前风险表述 | 处理 |
|---|---|
| “TF14 主实时配置...” | 改为“本文主实时配置...”，必要时脚注说明内部 preset |
| “相比 baseline 更强” | 改为“相对于 baseline 未显式覆盖的链路，本文增加...” |
| “在线自适应收益” | 若缺 paired on/off ablation，改为“保留接口；收益待消融验证” |

### 1.6 实验

当前位置：第 5 章已有比较对象、离线学习、闭环性能、单车误差、能力定位、最新图包与阶段性证据链。当前主要风险是 T1 baseline 未冻结、正文存在“显著优于”、部分图为占位或 `n=1`、历史 TF 版本叙事仍较多。

应插入的 Round 2 内容：

| 实验位置 | 插入内容 | 门槛 |
|---|---|---|
| `5.1 比较对象与实验设置` 开头 | T1 baseline fairness contract 表：AKE-R/AKE-A/AKE-M 状态、同数据/同 trace/同约束/同 seed/同 horizon/同 solver | 未冻结前不得进入结果 claim |
| `5.1` | 新增非 Koopman 网络控制 baseline：Physical-model DMPC 或 ZOH consensus MPC | 防止只比弱 Koopman baseline |
| `5.2` | fresh Koopman/AKE 多训练种子统计 | 目标 `n_train>=10`，最低 `n_train>=5` 才能写趋势 |
| `5.3` | 主闭环 paired seeds 统计 | `n>=20`，报告 mean、95% CI、failure count、paired test |
| `5.3/5.6` | 通信 dose-response | 0-200 ms、0-20% dropout、jitter、short burst、recoverable topology |
| `5.4` | 载荷受力和安全诊断 | 无 NaN，必须有 violation count、fallback/intervention log、constraint activity |
| `5.6` | 消融与 stress-test 分离 | 400 ms、40% dropout、leader-lost 只能标 stress-test，不能支撑一般性稳定 claim |

实验叙事替换规则：

| 原写法 | 替换写法 |
|---|---|
| “结果表明 TF14 显著优于 AKE-baseline” | “在 T1 公平设置和多 seed 统计通过后，结果可支持本文方法在指定指标上的改善；当前若为单 seed，仅说明代表性趋势” |
| “失败次数从 1 次降至 0 次” | 若 `n=1`：写“该代表性 run 未出现失败”；若 `n>=20`：写 failure rate 和 CI |
| “TF12/TF13/TF14 精度-实时性对比” | 移至内部开发说明或 supplement；正文只保留 task-aligned baseline 和 ablation |
| “所有力学指标优于 baseline” | 改为“故障恢复伴随 force-rate/jerk 代价，需报告权衡” |

### 1.7 Lyapunov

当前位置：第 4.7 和 4.8 已有 ISS-practical/UUB 倾向的证明，但仍出现“理想无扰动指数稳定”等容易被审稿人误读为更强保证的句子；同时证明层的 `A_\sigma/B_\sigma` 来源需要由方法桥接支撑。

应插入的 Round 2 内容：

| 位置 | 插入内容 | 写法要求 |
|---|---|---|
| 4.8 前 | 方法-证明桥接小节 | 明确 `A_\sigma/B_\sigma` 是完整控制链诱导的局部等效团队闭环 |
| 4.8.2 假设 | 有界扰动、效率估计误差、通信退化、驻留时间、工作域、约束可行性 | 每个假设必须能在实验日志或配置中找到对应检查项 |
| 4.8.5-4.8.7 | UUB / ISS-practical bound | 给出最终有界半径，说明与 `w_k`、建模误差和估计误差有关 |
| 4.8.8 | 证书记录对应关系 | `certificate_ok` 是仿真一致性证据，不替代理论证明 |

删除或降级：

| 当前风险表述 | 处理 |
|---|---|
| “当外部项为零时退化为指数稳定” | 可保留为受限推论，但必须写成“在无建模误差、无通信扰动、无估计误差且固定工作域内的理想特例” |
| “不会破坏有界性” | 改为“在补偿裁剪、输入约束可行和误差有界假设下不破坏 UUB 递推” |
| “保证安全” | 改为“在约束可行且 fallback 正常触发时降低 violation 风险；安全性由实验 violation/fallback log 支撑” |

### 1.8 结论

当前位置：第 6 章已承认 `minimum_group_n=1` 和需要补统计，但仍把 TF14 作为主语，且对 baseline 改善的边界可以更明确。

应插入的 Round 2 内容：

| 内容 | 写法要求 |
|---|---|
| T1 baseline | 只有 T1 和统计完成后才总结量化优势；否则写“建立了公平比较协议和待完成实验门槛” |
| 文献矩阵 | 回扣本文补足的 literature gap，但不写“首次” |
| 方法-证明桥接 | 总结局部 Koopman-MPC 到团队 UUB 证书的闭环链路 |
| 实验门槛 | 明确哪些结果已达投稿主结论，哪些仍是 representative/stress/supplement |
| claim 限制 | 最后一段列出适用边界：有界 delay/dropout、可恢复拓扑、输入约束可行、估计误差有界、驻留时间满足 |

删除或降级：

| 当前风险表述 | 处理 |
|---|---|
| “TF14 的核心增量...” | 改为“本文方法的核心增量...” |
| “能够保持完整路径推进” | 若无多 seed，改为“代表性 run 中保持完整路径推进” |
| “下一步应...” | 投稿主稿结论中避免写成未完成任务清单；未完成项移到 limitations |

## 2. 必删或必须降级的现有表述

| 类别 | 必删/降级对象 | 推荐处理 |
|---|---|---|
| TF 历史版本 | 摘要、引言、方法、实验、结论中把 TF14/TF12/TF13 当作创新来源的句子 | 正文统一改为“本文方法/主配置/消融配置”；历史版本只可作为内部 provenance，不作论文叙事 |
| TF 历史版本 | “相对于上一版 TF12/TF13...” | 主文删除；若必须保留，放 supplement 的 implementation evolution note |
| 过强稳定性 | “全局渐近稳定”“任意时延/丢包稳定”“所有扰动下保证安全” | 改为“有界扰动、驻留时间和可行约束假设下的 ISS-practical / UUB” |
| 过强稳定性 | “不会破坏有界性”“稳定保护保证...” | 加入裁剪、约束可行、扰动有界和工作域条件 |
| 未证实 superiority | “显著优于 baseline”“全面优于”“更强” | T1 和 `n>=20` 未完成前改为“机制差异”“代表性趋势”“待公平统计验证” |
| 未证实 superiority | “Koopman predictor 全面胜出” | 改为“在指定 horizon/工况/指标下改善；长时开环风险由稳定投影和 MPC 保护约束” |
| `n=1` 统计 | “失败率下降”“显著降低”“统计证明” | 改为“该 run 中未失败/趋势降低”；主统计必须使用 `n>=20` paired seeds |
| 安全 claim | “载荷安全指标全面改善” | 改为“报告 force/jerk/角点载荷/violation 权衡，禁止隐藏代价” |

## 3. 新增表、图、公式清单与位置

集成时必须把 `evidence_status` 写入每个新增表的最后一列、每个新增图的题注/图注 provenance、每个新增公式的公式说明或公式后审计句。没有该字段时，主 Agent 不得把对应材料插入为完成证据。

### 3.1 新增表

| 编号 | 建议位置 | 表名 | 必填字段 | 状态字段要求 |
|---|---|---|---|---|
| 表 R1 | `1.1 相关工作与研究差距` | 近三年文献证据矩阵 | 类别、代表文献、问题设置、未覆盖 gap、本文模块、证据位置、`evidence_status` | 初始 `pending`；文献来源、gap 和证据位置全部核验后才可标 `ready` |
| 表 R2 | 引言贡献之后 | 贡献-方法-理论-实验闭环表 | 贡献、方法模块、证明/假设、实验门槛、允许 claim、`evidence_status` | 初始 `pending`；缺 T1、证明或实验任一链路时不得标 `ready` |
| 表 M1 | 第 2 章末或第 4 章开头 | 符号与控制链变量表 | 状态、lifted 变量、通信变量、控制变量、切换模式、扰动项、`evidence_status` | 初始 `pending`；与全文符号和公式引用一致后改为 `ready` |
| 表 M2 | 第 3.2 或 `5.1` | T1 AKE baseline fairness 表 | AKE-R/AKE-A/AKE-M 状态、数据、horizon、dt、solver、约束、通信 trace、seed、`evidence_status` | `AKE-A` 未完成 fidelity 检查时为 `pending`；若降为 `AKE-M` 则标 `representative` 或 `pending`，不得标主证据 `ready` |
| 表 E1 | `5.1` | 实验门槛与 provenance 表 | scenario、method set、seed 数、fresh/cached、figure id、run id、是否可主张结论、`evidence_status` | 未冻结 T1 或缺 provenance 时为 `pending`；单 seed 条目为 `representative` |
| 表 E2 | `5.3` | 主闭环 paired statistics 表 | mean、95% CI、paired delta、failure count、overrun、p95 solve time、`evidence_status` | `n>=20` paired seeds、CI 和 failure log 完整后才可标 `ready`；否则 `representative` |
| 表 E3 | `5.6` 或 supplement | stress-test 与主结论边界表 | stress 条件、是否超出理论假设、允许写法、禁止写法、`evidence_status` | 超出理论假设的条目固定标 `stress-test`，不得转为主结论 `ready` |

### 3.2 新增或替换图

| 编号 | 建议位置 | 图名 | 准入条件 | 状态字段要求 |
|---|---|---|---|---|
| 图 1 | 第 2 章 | 四车载荷、通信边和退化链路示意图 | 标出 delay/dropout/jitter/timestamp/link quality | 图注写 `evidence_status=pending/ready`；与方法符号和通信假设一致后才可标 `ready` |
| 图 2 | 第 3.2 / `5.2` | Koopman fresh training 多 seed 预测验证 | AKE 与本文 predictor 同数据口径，至少 `n_train>=5` | `n_train<5` 时为 `representative`；同数据和 fresh seeds 核验后才可标 `ready` |
| 图 3 | 第 4.6 后 | 方法-证明控制链桥接图 | 展示 `u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}->A_\sigma/B_\sigma` | 初始 `pending`；与公式 C5-C6 和 Lyapunov 假设一致后改为 `ready` |
| 图 4 | `5.3` | T1 主闭环轨迹与误差统计 | Proposed、T1 AKE、非 Koopman baseline、关键消融同图或同表 | `n<20` 或 AKE/非 Koopman 未冻结时为 `representative`；T1 全通过后才可标 `ready` |
| 图 5 | `5.3/5.6` | 通信 dose-response | delay/dropout/jitter/burst/topology，报告 CI | 主假设范围内且有 CI 时可标 `ready`；超出理论边界的曲线标 `stress-test` |
| 图 6 | `5.4` | 载荷受力、连接一致性和安全 violation | 无 NaN，含 force components、jerk/force-rate、violation/fallback log | 缺 safety log 或有未解释 NaN 时为 `pending`；完整日志和约束统计通过后才可标 `ready` |
| 图 7 | `5.6` | 消融热力图或森林图 | `n>=20` 前只可标 representative trend | `n<20` 时固定 `representative`；多 seed 统计完整后才可改 `ready` |
| 图 8 | `4.8.8/5.6` | Lyapunov/certificate margin 与 practical bound | 字段必须与证明变量一一对应 | 缺公式桥接或 certificate log 时为 `pending`；若仅展示极端边界则标 `stress-test` |
| 图 9 | `5.6` 或 supplement | runtime 与通信开销 | p95 solve time、overrun、message size、packet rate | 缺统一硬件/solver 口径时为 `pending`；完整 compute accounting 后可标 `ready` |

### 3.3 新增或重写公式

| 编号 | 建议位置 | 公式内容 | 用途 | 状态字段要求 |
|---|---|---|---|---|
| 公式 C1 | `4.3` | 链路质量 `q_{ij,k}` 与 delay/dropout/jitter/timestamp 状态更新 | 把 DCN 退化显式写入控制问题 | 公式说明写 `evidence_status=pending/ready`；通信 trace 字段核验后才可标 `ready` |
| 公式 C2 | `4.3` | 时延邻居状态前推 `\hat{x}_{j,k|k-d}` | 支撑 delay compensation claim | 必须注明只使用当前/过去 timestamp；因果边界核验后标 `ready`，否则 `pending` |
| 公式 C3 | `4.3` | 通信质量感知一致性权重/混合命令 `u_i^{comm}` | 说明通信质量如何改变命令融合 | 缺权重裁剪、约束或可用信息说明时为 `pending`；核验后 `ready` |
| 公式 C4 | `4.5` | 效率估计与 FTC 重构 `u_i^{ftc}` | 支撑故障重分配 | 缺 FDI/FTC 日志或故障假设时为 `pending`；若只在极端故障报告中使用则标 `stress-test` |
| 公式 C5 | `4.6 后新增桥接小节` | 团队聚合 `u_c^{agg}=G_\sigma(\{u_i^{ftc}\},x_k,q_k)` | 连接局部命令和载荷中心模型 | 与图 3 和表 M1 一致后才可标 `ready`；否则 `pending` |
| 公式 C6 | `4.8.1` | 等效闭环 `e_{k+1}=A_{\sigma_k}e_k+B_{\sigma_k}w_k+r_{\sigma_k,k}` | Lyapunov 证明入口 | 必须说明不是离线 Koopman 矩阵；证明桥接完成后 `ready`，否则 `pending` |
| 公式 C7 | `4.8.5-4.8.7` | `V_{\sigma_{k+1}}(e_{k+1})-V_{\sigma_k}(e_k) <= -\alpha||e_k||^2+c||w_k||^2+\epsilon` | UUB / ISS-practical 主递推 | 假设、常数含义和扰动界闭合后 `ready`；缺项时 `pending` |
| 公式 C8 | `4.8.7` | `limsup ||e_k|| <= rho(...)` | 明确最终有界半径和 claim 边界 | 只有 bound 与实验 certificate 字段对应时为 `ready`；若用于超边界情形则标 `stress-test` |

公式集成要求：最终 DOCX 中不得使用易损坏的纯文本 LaTeX 作为正式公式；使用高分辨率公式图片或可靠 OMML，并在 PDF 中逐页 QA。

## 4. DOCX 修改安全策略

后续主 Agent 修改 DOCX 时应采用以下安全流程：

1. 另存新文件，不覆盖输入稿。建议输出名：`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_round2_integrated_2026-05-11.docx`。
2. 修改前先做只读结构快照：段落数、表格数、图片数、题注列表、章节标题列表。
3. 分阶段编辑：先清理 TF 历史和过强 claim，再插入文献/T1/方法桥接，最后替换实验结果与图表。
4. 公式优先使用高分辨率透明或白底 PNG/SVG，或使用经验证可渲染的 Word OMML；禁止把最终公式写成裸 LaTeX、caret 上标或破碎 Unicode。
5. 每张表插入后做 table geometry check：每行单元格数、合并单元格、表头重复、宽度、跨页、题注和正文引用必须一致。
6. 每张图插入后检查 provenance：run id、seed、scenario、method set、是否 fresh、是否 `n=1`、是否允许主结论。
7. 每个新增表/图/公式插入后检查 `evidence_status`：只有 `ready` 可支撑主结论；`pending`、`representative`、`stress-test` 必须在正文中显式降级。
8. DOCX 导出 PDF 后做渲染 QA：全页 contact sheet、公式密集页、表格页、图题页和章节页重点检查。
9. PDF QA 必查项：公式上下标、希腊字母、范数、帽号/波浪号、表格边界、图例可读性、单位、页码、交叉引用。
10. 若 Word/WPS/LibreOffice 导出出现非致命 COM 关闭警告，但 PDF 完整生成，应以 PDF 渲染结果为准继续 QA。
11. 修改过程中不得删除未处理章节；任何未达门槛的结果必须显式标注为 `pending`、`representative` 或 `stress-test`，不得默认为 `ready`。

## 5. 最终集成验收 checklist

### 5.1 章节验收

| 检查项 | 通过标准 |
|---|---|
| 摘要 | 不出现 TF14 作为创新来源；不含未证实 superiority；稳定性为 UUB/ISS-practical 边界 |
| 引言 | DCN-native gap 清楚；baseline-facing，不再写内部版本演进 |
| 贡献 | 每个贡献都有文献 gap、方法模块、证明/实验证据和 claim 边界 |
| 相关工作 | 文献矩阵完整，来源合法，覆盖 Koopman、协同搬运、MPC、通信网络、FTC/safety |
| 方法 | 符号统一；通信模型、控制链、FTC 和团队聚合写成闭环 |
| 实验 | T1 fairness 表、非 Koopman baseline、多 seed 统计、stress-test 分离、provenance 完整 |
| Lyapunov | `A_\sigma/B_\sigma` 来源清楚；假设与实验日志对应；结论限制为 practical/UUB |
| 结论 | 总结已验证内容和边界，不把待完成项写成已完成贡献 |

### 5.2 Claim 验收

| 检查项 | 通过标准 |
|---|---|
| Baseline | T1 未冻结前全文无“优于/显著优于/全面优于 baseline” |
| 稳定性 | 全文无任意 delay/dropout、全局渐近稳定、完全容错、无条件安全保证 |
| 统计 | 所有主结论都有 `n>=20` 或明确标为 representative trend |
| 学习器 | fresh training seeds 未完成前，不写 Koopman predictor 统计显著胜出 |
| 安全 | force/jerk/载荷/violation 代价完整报告，不只报告有利指标 |
| 历史版本 | TF12/TF13/TF14 不作为论文 novelty；最多作为内部配置 provenance |

### 5.3 图表公式 QA 验收

| 检查项 | 通过标准 |
|---|---|
| 表格 | geometry check 通过，列宽可读，表题和正文引用一致 |
| 图片 | 主图 6-8 张以内，轴单位、图例、scenario、baseline/proposed 对齐 |
| 公式 | 公式图片或 OMML 渲染正确；PDF 中上下标、希腊字母和不等式无误 |
| PDF | contact sheet 和重点页人工检查通过 |
| Provenance | 每个主图/主表能追溯 run id、seed、method set、fresh/cached 状态和 `evidence_status`；只有 `ready` 可支撑主结论 |

### 5.4 投稿前硬门槛

| 编号 | 硬门槛 | 未通过处理 |
|---|---|---|
| P0-1 | T1 baseline fairness contract 冻结 | 删除 superiority claim，仅保留 protocol |
| P0-2 | 非 Koopman baseline 完成 | 主文不声称只对 AKE 的优势足够代表网络控制优势 |
| P0-3 | 主闭环 `n>=20` paired seeds | 主结果降级为 representative |
| P0-4 | fresh Koopman/AKE 多训练种子 | 学习器性能降级为单模型机制证据 |
| P0-5 | 安全诊断无 NaN 且有 violation/fallback log | 安全图不得进主文 |
| P0-6 | 方法-证明桥接完成 | Lyapunov 证明不得作为主理论贡献 |
| P0-7 | 近三年文献矩阵补齐 | 贡献 novelty 降级为工程集成说明 |

最终判定：只有当上述 P0 全部通过，中文稿才能进入英文 LaTeX 迁移；若任一 P0 未通过，中文稿可作为内部 round2 draft，但不能标为 publication-ready。
