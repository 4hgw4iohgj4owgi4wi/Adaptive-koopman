# Worker E：Safe Chinese Integration Draft Scope

## 0. 边界与输入

本文件只定义下一版中文稿的安全集成范围，不修改 DOCX、实验代码、图文件或 LaTeX。

目标中文稿基线：

`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`

本轮读取的 Round 2 输入：

| 输入 | 路径 | 用途 |
|---|---|---|
| Round 2 integrated report | `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/06_round2_integrated_publication_readiness_report.md` | 确认 ready/pending 总边界和 P0 阻塞项。 |
| Round 2 Chinese integration plan | `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/05_chinese_manuscript_integration_patch_plan.md` | 确认逐章插入位置、图表公式状态规则和 DOCX QA 流程。 |
| Round 2 method-proof bridge | `paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11/03_method_proof_bridge_draft_zh.md` | 提取可立即进入中文稿的方法-证明桥接文本和 Lyapunov 限制性结论。 |

核心判定：当前可以集成“叙事、协议、桥接、符号、状态门槛和 claim 降级规则”；不能集成“最终数值优势、统计显著、安全最终验证、强 novelty 或无条件稳定保证”。

## 1. 可立即集成的草案段落

以下段落可进入下一版安全中文稿，但必须保留对应 `evidence_status`，且不得把 `pending` 或 `representative` 内容写成主结论。

### 1.1 摘要安全改写段

`evidence_status=ready`

> 本文提出一种面向退化通信网络的四车协同运输控制框架，将双线性 Koopman 预测器、通信质量感知一致性 MPC、在线 FDI/FTC 重构和安全降级聚合到统一闭环中。相对于以模型误差自适应为中心的 AKE 类 Koopman 控制思路，本文当前可安全声明的是：建立了 task-aligned AKE baseline 的公平比较协议，并给出从单车 Koopman-MPC 命令到团队中心闭环证书的控制链桥接。相对 baseline 的量化优势、统计显著性和安全收益需在 T1 baseline 冻结、`n>=20` paired seeds、fresh training seeds 以及 no-NaN safety logs 全部通过后写入。

### 1.2 引言问题驱动段

`evidence_status=ready`

> 退化通信网络下的协同运输同时受到模型误差、时延、丢包、链路质量变化、执行器效率退化和安全约束的影响。现有 Koopman-MPC、协同搬运、网络控制与容错控制工作往往分别处理上述因素，而本文关注的是把学习预测器、通信质量感知控制、故障重构和团队级闭环证书放入同一条可审计证据链。为避免把内部 TF12/TF13/TF14 演进写成论文新颖性，本文将所有贡献表述为相对于 published AKE-style baseline 和近三年相关文献 gap 的方法增量。

### 1.3 Baseline fairness 安全段

`evidence_status=ready`

> 本文不直接把原始 AKE 实现视为弱 baseline，而是先定义 task-aligned AKE baseline 的公平比较合同。只有当 AKE baseline 与本文方法使用同一训练数据口径、通信 trace、约束、采样时间、预测 horizon、solver、seed 和统计规则时，才可作为 `AKE-A` 主 baseline；若在线自适应、MPC coupling 或通信退化接口不能等价复现，则降级为 `AKE-M` 机制对照或 `AKE-R` 参考模型，相关结果只能作为 representative 或 pending evidence，不支持 superiority claim。

### 1.4 方法-证明桥接段

`evidence_status=ready`

> 为了使 Lyapunov 型证明与实际控制栈一致，本文不直接把局部 MPC 的预测矩阵或 Koopman 训练矩阵当作团队闭环矩阵。四车闭环的执行顺序为：局部 Koopman-MPC 生成名义命令，通信质量补偿与时延前推修正命令，FDI/FTC 按执行器效率估计重构可执行命令，团队聚合与安全保护形成载荷中心等效命令，最后由团队中心物理系统推进到下一采样时刻。后续稳定性证明中的团队等效闭环矩阵只能由这条完整控制链诱导得到，而不能直接等同于 Koopman 训练矩阵、单车 lifted 预测矩阵或单车 MPC 的局部反馈矩阵。

### 1.5 局部增益与 Lyapunov 边界段

`evidence_status=ready`

> 由于控制链包含输入投影、饱和、安全模式切换、FDI/FTC 逻辑和通信图切换，闭环映射一般是非光滑混合映射。正文应以局部 Lipschitz 增益界或 one-step gain bound 作为理论主线；若保留 `A_sigma/B_sigma` 记号，只能解释为固定活动集和局部线性化下的辅助对象。本文稳定性结论应表述为 conditional practical boundedness 或 UUB：在有界扰动、有界通信退化、有界执行器辨识误差、MPC 局部可行、闭环轨迹留在紧致工作域且切换驻留条件成立时，团队中心误差最终进入一个可解释的有界邻域。

### 1.6 实验章节安全门槛段

`evidence_status=ready`

> 实验章节中的每张新表、每张新图和每个新增公式说明均必须显式标注 `evidence_status`。只有 `ready` 条目可支撑主文结论；`pending` 条目只能作为待完成计划或待核验材料；`representative` 条目只能说明单 seed 或少量 seed 的趋势；`stress-test` 条目只能报告边界外经验现象，不能扩大理论保证或一般鲁棒性结论。

### 1.7 结论安全改写段

`evidence_status=ready`

> 本文当前可总结为一种面向通信退化和执行器退化的协同运输控制链设计：双线性 Koopman predictor 提供局部预测，通信质量感知 DCC-MPC 处理时延与链路质量变化，FDI/FTC 与安全聚合将局部命令映射到团队中心闭环，并通过条件性 practical/UUB 证书给出有界性解释。最终投稿版的量化结论应等待 T1 baseline、公平非 Koopman baseline、多 seed 统计、通信 dose-response 和 safety diagnostics 全部通过后再写入。

## 2. 每个新增内容的 evidence_status

| 新增内容 | 建议位置 | evidence_status | 当前允许写法 | 禁止写法 |
|---|---|---|---|---|
| DCN 网络问题驱动叙事 | 摘要、引言 | `ready` | 写通信退化、协同运输和闭环证据链的任务动机。 | 写“首次解决”或无文献支撑的强 novelty。 |
| AKE-A candidate / AKE-M downgrade 规则 | 实验设置、baseline 表注 | `ready` | 写 baseline 状态门槛和降级规则。 | 在 T1 未冻结前写“显著优于 AKE”。 |
| T1 baseline fairness contract 表 | `5.1` 或附录 | `pending` | 写公平比较协议、字段和必须冻结的配置。 | 把协议当作已完成 baseline 结果。 |
| 方法-证明桥接文本 | 第 4.5 后或新增 4.x | `ready` | 写 `u_i^mpc -> u_i^comm -> u_i^ftc -> u_c^agg -> x_c,k+1` 控制链。 | 把 Koopman 训练矩阵直接当团队闭环矩阵。 |
| 局部增益 / Lipschitz 主线 | 第 4.8.1 | `ready` | 写局部增益界和 fixed active set 限制。 | 写全局线性闭环或无条件指数稳定。 |
| conditional practical/UUB 结论 | 第 4.8 末尾、结论 | `ready` | 写有界扰动、有界通信退化、局部可行和驻留时间条件下的 UUB。 | 写任意时延/丢包/leader-lost 下稳定。 |
| 符号硬门禁表 | 第 2 章末或第 4.8 前 | `ready` | 统一 `q/Gamma/delta/tau/x/z/G/A/B/sigma/d` 含义。 | 同一符号在证明、通信和 Koopman 中混用。 |
| 过强 claim 替换表 | 内部修订清单或附录 | `ready` | 用“机制差异、代表性趋势、待公平统计验证”替换过强说法。 | 保留“全面优于、完全容错、保证安全”。 |
| 文献证据矩阵 R1 | 引言相关工作小节 | `pending` | 可插入为待核验矩阵，列出 gap、模块和证据位置。 | 在 V3 citation record 为 0 时作为终稿 novelty 支撑。 |
| 贡献-证据矩阵 R2 | 引言贡献之后 | `pending` | 写贡献、方法模块、理论/实验门槛和允许 claim。 | 每项贡献缺实验证据时标成 `ready`。 |
| Koopman fresh training 多 seed 图 | `5.2` | `pending` | 写需要 fresh seeds 和同数据口径。 | 用 cached 或单模型图证明学习器统计胜出。 |
| 主闭环 paired statistics 表 | `5.3` | `pending` | 等 `n>=20` paired seeds、95% CI、failure count 完整后再写。 | 以 `n=1` 写显著改善、失败率下降或统计证明。 |
| 单 seed 或少量 seed 轨迹图 | `5.3` 或 supplement | `representative` | 写代表性 run 或趋势图。 | 支撑主结论、统计显著或 failure-rate claim。 |
| 通信 dose-response 图 | `5.3/5.6` | `pending` | 主理论区间为 0--200 ms、0--20% dropout、recoverable topology。 | 用 400 ms、40% dropout 或 leader-lost 扩大理论保证。 |
| stress-test 图表 | `5.6` 或 supplement | `stress-test` | 写边界外经验鲁棒性或 failure-mode。 | 标成主结果 `ready` 或支撑一般稳定性。 |
| 安全 force / violation / fallback 图 | `5.4` | `pending` | 等 no-NaN、violation count、fallback/intervention log 和 constraint activity 完整。 | 写“保证安全”或只报告有利 force 指标。 |
| runtime / communication overhead 图 | `5.6` 或 supplement | `pending` | 等统一硬件、solver、p95 solve time、overrun 和 message accounting 完整。 | 无统一口径时声称实时性最终达标。 |
| final gate checklist | 实验设置前、内部 readiness 附录 | `pending` | 作为投稿前硬门槛清单。 | 当作已完成 QA 结论。 |

## 3. 必须 pending 的段落、图表和统计

### 3.1 必须 pending 的正文段落

| 段落类型 | pending 原因 | 安全替代表述 |
|---|---|---|
| “本文显著优于 uploaded AKE baseline” | T1 baseline 尚未冻结，`AKE-A` 仍是 candidate state。 | “本文建立 task-aligned AKE baseline 的公平比较合同，最终量化结论等待 T1 final runs。” |
| “本文优于网络控制方法” | credible non-Koopman baseline 尚未完成，ZOH consensus MPC 只能作最低 surrogate。 | “当前只可报告相对特定 surrogate 或消融对照的代表性趋势。” |
| “n>=20 统计显著改善” | 主闭环 paired seeds、CI、failure count 尚未完成。 | “当前结果为 representative evidence，投稿前需多 seed 统计验证。” |
| “timestamped/out-of-order neighbor prediction 是强 novelty” | 直接 V3/V2 文献证据不足。 | “本文实现了 timestamped neighbor prediction 机制；强 novelty 需补直接文献后再写。” |
| “任意通信故障稳定” | 理论只覆盖 bounded degradation 和 recoverable topology。 | “在有界时延、丢包和可恢复拓扑假设下满足 conditional practical/UUB。” |
| “安全性能已最终验证” | T5 no-NaN、violation、fallback/intervention 和 constraint activity logs 未 final。 | “安全诊断门槛已定义，最终安全证据等待完整日志导出。” |

### 3.2 必须 pending 或降级的图表

| 图表 | 当前状态 | 处理 |
|---|---|---|
| 表 R1 近三年文献证据矩阵 | `pending` | 可插入为待核验矩阵；V3 citation record 完整前不得支撑 novelty。 |
| 表 R2 贡献-方法-理论-实验闭环表 | `pending` | 每项贡献缺 T1、证明或实验任一链路时不得标 `ready`。 |
| 表 M2 T1 baseline fairness / result 表 | `pending` | 可写协议字段；结果列留 pending。 |
| 图 2 Koopman fresh training 多 seed 预测验证 | `pending` | 等 `n_train>=5` 最低趋势门槛，`n_train>=10` 更稳妥。 |
| 图 4 主闭环轨迹与误差统计 | `pending` 或 `representative` | `n<20` 时只作为 representative；T1 全通过后才可 `ready`。 |
| 图 5 通信 dose-response | `pending` / `stress-test` | 主理论区间内待 CI；400 ms、40% dropout、leader-lost 固定为 `stress-test`。 |
| 图 6 载荷受力、安全 violation 和 fallback | `pending` | 有未解释 NaN 或缺 safety log 时不得进主文。 |
| 图 7 消融热力图或森林图 | `representative` 或 `pending` | `n<20` 固定为代表性趋势。 |
| 图 8 Lyapunov/certificate margin | `pending` | 缺公式桥接或 certificate fields 对应关系时不得作为主理论证据。 |
| 图 9 runtime 与通信开销 | `pending` | 硬件、solver 和 message accounting 未统一前不得写 realtime final claim。 |

### 3.3 必须 pending 的统计与 P0 门槛

| P0 | 必须完成的统计/证据 | 未完成时写法 |
|---|---|---|
| P0-1 | 冻结 T1 baseline fairness contract，确认 `AKE-A` 是否成立，否则降级 `AKE-M`。 | 删除 superiority claim，只保留 protocol。 |
| P0-2 | 完成 credible non-Koopman baseline，优先 Physical-model DMPC。 | 不声称优于网络控制方法。 |
| P0-3 | 主闭环 `n>=20` paired seeds，报告 mean、95% CI、failure count、paired delta。 | 主结果降级为 representative。 |
| P0-4 | fresh Koopman/AKE 多训练种子，最低 `n_train>=5`，推荐 `n_train>=10`。 | 学习器性能只写机制或单模型趋势。 |
| P0-5 | T5 safety diagnostics 无未分类 NaN，并有 violation/fallback/intervention/constraint logs。 | 安全图不得支撑主文结论。 |
| P0-6 | dose-response 和 topology recovery 覆盖 0--200 ms、0--20% dropout、recoverable topology。 | 只写 planned final validation 或 stress-test。 |
| P0-7 | 每条文献补齐 citation record、合法来源、gap sentence 和 used sentence。 | novelty 降级为工程集成说明。 |

## 4. 下一版输出文件名建议

建议下一版中文 DOCX 不覆盖基线稿，使用新的派生文件名：

`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_safe_integration_draft_2026-05-11.docx`

建议配套 QA 输出目录：

`paper_dcn_tf12_draft/render_safe_integration_draft_qa_20260511/`

若下一步只生成 Markdown 补丁而不写 DOCX，建议文件名：

`paper_dcn_tf12_draft/publication_readiness_round3_2026-05-11/05a_safe_chinese_integration_patch_text_2026-05-11.md`

## 5. QA 步骤

1. 修改前对基线 DOCX 做只读快照：段落数、表格数、图片数、章节标题、题注列表和文件 hash。
2. 另存为建议的新 DOCX 文件名，不覆盖 `manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`。
3. 先做全稿搜索替换审计：`TF14`、`TF12`、`TF13`、`显著优于`、`全面优于`、`保证安全`、`任意时延`、`全局渐近稳定`、`首次`。
4. 插入 ready 文本前确认每个新增表、图、公式、题注或公式说明带 `evidence_status`。
5. 表格插入后做 geometry check：每行单元格数、合并单元格、列宽、跨页、表题和正文引用一致。
6. 公式只用可靠 OMML 或高分辨率公式图片；禁止把裸 LaTeX 或易碎 Unicode 作为终稿公式。
7. 图片插入后检查 provenance：run id、seed、scenario、method set、fresh/cached、`n`、baseline 状态和 `evidence_status`。
8. 导出 PDF 后做 contact sheet 和重点页人工检查，重点看公式上下标、希腊字母、范数、表格边界、图例、单位、页码和交叉引用。
9. 运行 claim gate：T1 未冻结前全文不得出现 baseline superiority；`n<20` 的结果必须标 `representative`；400 ms、40% dropout、leader-lost 必须标 `stress-test`。
10. 最终记录 QA 结果到同目录 Markdown；若任一 P0 未通过，下一版只能称为 safe integration draft，不能称为 publication-ready。

## 6. 本 Worker 输出结论

可以立即进入下一版中文稿的内容是：DCN 问题驱动叙事、AKE baseline 状态门槛、方法-证明桥接、局部增益/UUB 限制性理论表述、符号硬门禁和 `evidence_status` 规则。

必须 pending 的内容是：所有最终 baseline 优势、非 Koopman 泛化优势、多 seed 统计、fresh training 统计、安全最终验证、dose-response 主结论、强 novelty 文献支撑和 stress-test 外推结论。

本任务未修改 DOCX。
