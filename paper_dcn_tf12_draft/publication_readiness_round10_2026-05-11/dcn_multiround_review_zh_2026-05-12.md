# DCN 中文稿多轮内审问题清单

审稿对象：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/manuscript_zh_round10.tex`

对应 PDF：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/manuscript_zh_round10_layout_analysis_fixed.pdf`

审稿日期：2026-05-12

目标期刊：Digital Communications and Networks，以下简称 DCN。

## 0. 依据与总判定

本轮按 DCN/Elsevier 作者指南做“编辑部初筛 + 外审专家 + 格式技术审查”的多轮内审。DCN 明确聚焦 communication systems and networks；官网列出的相关方向包括 AI-Driven Communications and Networks、Cyber-Physical Systems、Intelligent Communications and Networking Systems、Networked Control Systems、Vehicular Communications and Networks、Wireless Communications and Networking 等。作者指南还说明：稿件可能因 out of scope、ethical conflicts、high similarities、lack of originality、flaws in research design or methods 等原因被 desk reject；方法部分需要足够细节以便独立研究者复现；结果应清楚简洁，讨论应解释结果意义而不是重复结果；图表、引用、声明、数据/代码可用性也有明确要求。

本稿当前结论：**不建议直接投稿。若按当前中文稿提交，最大概率是技术退稿或编辑部退修；若转成英文但不补实验和 baseline，仍有较高 desk reject 风险。**

主要原因有六个：

- 当前稿是中文，DCN 指南要求英文稿件。
- 期刊契合点仍偏“车辆控制论文”，通信网络贡献需要再前置、量化和理论化。
- 主 baseline 是任务对齐 AKE-M，不是上传原文 AKE-A 的严格复现，比较说服力不足。
- Koopman 学习、时延补偿、FDI/FTC 三个模块的关键证据没有完全闭合。
- Lyapunov 证明假设强、证书实验存在负裕度，理论和实证之间仍有不一致。
- 投稿声明、数据/代码可用性、生成式 AI 声明、作者贡献、利益冲突、基金等 submission package 不完整。

## 1. 第一轮：编辑部初筛/Scope 审查

### P0-1 中文稿不满足 DCN 语言要求

位置：`manuscript_zh_round10.tex:115-120`、`125-680`

问题：全文为中文，关键词也为中文。DCN 作者指南要求稿件使用 good English。即使这是内部中文稿，若作为投稿源稿仍不合规。

影响：技术退修或直接不进入正式外审。

修复：完成英文版，标题、摘要、关键词、图表标题、变量说明、声明部分全部英文；中文稿只能作为内部底稿。

### P0-2 Scope 叙事仍像控制/机器人论文，通信网络贡献不够“DCN 化”

位置：`manuscript_zh_round10.tex:127-137`、`213-224`、`362-391`、`481-668`

问题：稿件提到了通信质量、时延、丢包，但核心指标仍主要是车辆轨迹 RMSE、连接误差和受力。DCN 读者会问：本文对 communication systems and networks 的新知识是什么？目前通信模块更像控制器内部调参项，而不是网络退化建模、网络资源约束、通信协议/拓扑恢复、网络控制系统性能边界的系统研究。

影响：编辑初筛可能认为“网络只是应用扰动”，主题偏离 DCN。

修复：把文章切入改成“networked cooperative transport under degraded communication”，并补通信网络侧指标：packet loss rate、delay distribution、link-quality transition、topology recovery time、communication-aware weight evolution、message availability、network load/communication cost。实验至少要有 delay/dropout dose-response 和 topology degradation/recovery。

### P0-3 摘要主动暴露“尚未闭合”的缺口，削弱投稿可信度

位置：`manuscript_zh_round10.tex:116`

问题：摘要最后写“仍需补充严格 AKE-A 复现、强物理/DMPC 基线、delay dose-response 和 E1 Koopman fresh training 统计”。这对内部记录是诚实的，但投稿摘要不能把未完成项作为结论的一部分。编辑会直接判断研究尚未完成。

影响：高概率 desk reject 或要求完善后重投。

修复：投稿版摘要只能写已完成、可支撑的结论。未完成事项应转化为实际补齐的实验或放到“Limitations”中以更克制方式表达。

### P0-4 结论仍称“中文 LaTeX 初稿”，不是正式研究结论

位置：`manuscript_zh_round10.tex:672`

问题：结论开头“本文形成了……中文 LaTeX 初稿”属于工作记录，不是论文结论。

影响：直接暴露稿件未成熟。

修复：改为研究结论：提出了什么框架、在什么条件下验证了什么、主要数值收益和限制是什么。

## 2. 第二轮：贡献与创新性审查

### P0-5 贡献链条仍有“模块堆叠”风险

位置：`manuscript_zh_round10.tex:142-145`

问题：四个贡献分别是 Koopman、通信 MPC、联合审计、FDI/FTC+证书。每个模块本身已有大量文献，当前稿的“统一集成”如果没有强实验和理论闭环，容易被外审认为是工程堆叠，而不是 DCN 级别创新。

影响：外审会质疑 originality。

修复：每个贡献都要写成“已有文献做了什么 -> 本文在它基础上增加什么 -> 为什么这个增加解决了 DCN 相关缺口 -> 哪个实验/图表证明”。特别要避免只说“集成”。

### P0-6 主 baseline 不是上传原文严格复现

位置：`manuscript_zh_round10.tex:137`、`486-487`、`666`

问题：稿件承认当前 baseline 是任务对齐 AKE-M，不是上传原文 AKE-A 的严格复现。这是最大科学比较风险。外审会认为：如果题目和引言把上传 baseline 当作对照基础，那么必须复现其核心设置或解释为什么无法直接复现，并给出公平转写规则。

影响：comparison unfair / baseline mismatch，可能大修或拒稿。

修复：至少补一个严格 AKE-A 复现分支，或将主 baseline 改为“published AKE-inspired mechanism baseline”，并在补充材料给出映射表：状态、控制输入、学习模型、约束、训练数据、任务差异。

### P1-1 强物理/DMPC baseline 缺失

位置：`manuscript_zh_round10.tex:486-487`、`666-668`

问题：ZOH surrogate 太弱，只能作为地板基线；AKE-M 又不是严格原文复现。因此缺少一个能说服 DCN/控制外审的强 baseline，例如 robust DMPC、tube MPC、networked predictive control、delay-aware DMPC 或 CBF/CLF-QP 类安全控制。

影响：即使结果数值好，也会被认为对比不充分。

修复：增加至少一个强 baseline，保持同样网络扰动、同样故障、同样约束、同样种子数；报告 tracking、connection utilization、force peak、constraint violation、computation time。

### P1-2 FDI/FTC 贡献证据弱

位置：`manuscript_zh_round10.tex:135`、`399-410`、`145`、`668`

问题：稿件自己承认 FDI/FTC 缺近三年直接文献和故障效率估计/重分配图。方法里只有效率模型和投影式，缺少检测器残差定义、阈值设计、误报/漏报、估计收敛、控制重分配前后力/误差变化。

影响：该贡献容易被要求降级或删除。

修复：补 fault injection 实验：效率下降曲线、估计值 \hat eta_i、残差、触发时刻、重分配输入、单车故障前后连接误差和 force components。

## 3. 第三轮：方法可复现性审查

### P0-7 离线数据生成不可复现

位置：`manuscript_zh_round10.tex:312-314`

问题：只写了四类工况和“随机转角、加速度扰动、曲率变化、通信扰动”，没有给采样周期、仿真时长、run 数、状态维度、输入范围、噪声分布、时延分布、丢包过程、链路质量生成模型、随机种子、训练/验证/测试划分。

影响：不满足作者指南中“方法应足够细节让独立研究者复现”的要求。

修复：新增“Simulation and dataset generation”表格，列出所有参数；提供伪代码或算法框。

### P0-8 Koopman 网络细节不足

位置：`manuscript_zh_round10.tex:316-353`

问题：定义了 lifting 和岭回归，但没有给神经网络结构：层数、宽度、激活函数、归一化、训练轮数、优化器、学习率、batch size、ridge 系数 \lambda 的数值、稳定投影频率、谱半径阈值、残差边界估计方式。

影响：Koopman 模块无法复现，且“稳定投影双线性 Koopman”创新难以评估。

修复：补网络结构表、训练超参表、loss 公式、validation rollout 误差图、不同 seed 的均值/方差。

### P1-3 通信退化模型定义过抽象

位置：`manuscript_zh_round10.tex:213-224`、`377-391`

问题：链路质量 q、时延 tau、丢包 ell 都被定义了，但没有说明它们如何生成、如何测量、如何 EWMA 平滑、如何映射成权重和约束收缩。公式 \omega_{ij,k} 只有线性权重，无法体现复杂通信网络退化。

影响：DCN 外审会认为网络模型过简化。

修复：给出 q 的物理或统计来源，例如 Gilbert-Elliott/Markov loss、log-normal delay、DoS burst、distance/SINR-inspired link quality；补权重、约束收缩、fallback 的完整函数和参数。

### P1-4 MPC 求解设置缺失

位置：`manuscript_zh_round10.tex:362-391`

问题：MPC 代价完整性尚可，但缺 horizon H、采样周期、求解器、QP/NLP 形式、约束线性化方式、warm start、失败处理、实时计算时间。

影响：无法判断可部署性，也无法判断 DCN 场景下的实时网络控制意义。

修复：补求解器参数表和 computation time 统计；至少报告 mean/max solve time、infeasible rate、fallback rate。

### P1-5 载荷受力模型过粗

位置：`manuscript_zh_round10.tex:205-209`、`658`

问题：连接力用刚度/阻尼近似，但实验只报告 force peak；没有 F_x、F_y、M_z 分量和物理单位/阈值来源。

影响：不能宣称载荷安全，只能宣称连接几何约束利用率下降。

修复：补三方向受力曲线、峰值/均方/频域或 jerk 指标，并解释力阈值来源。

## 4. 第四轮：理论证明审查

### P0-9 Lyapunov 证明假设过强且部分结论近似循环

位置：`manuscript_zh_round10.tex:421-478`

问题：假设 3 直接假设递归可行和安全可行输入集合非空；定理又假设 fallback 模式下存在下降不等式。这样证明更像“如果存在稳定下降，则系统稳定”，而不是由本文控制律推出稳定性。外审会要求证明如何由 MPC 代价、终端集、约束收缩和投影机制推出这些条件。

影响：理论贡献说服力不足。

修复：将证明降级为 proposition 或 certificate consistency；若保留 theorem，需要补终端集构造、局部控制律、收缩约束证明和切换 dwell-time 的明确界。

### P0-10 证书实验与理论存在冲突

位置：`manuscript_zh_round10.tex:628`、`656`

问题：图 7 和正文承认 nominal 与 single-fault 场景出现负最小裕度。虽然稿件已限制为实践有界，但如果理论中给出统一输入到状态实践有界，外审会问为什么 nominal 场景反而证书负裕度。

影响：稳定性部分可能被要求重写。

修复：把 E3 从“证明验证”改成“运行时监测指标”；解释负裕度发生的具体时间段、是否触发 fallback、误差是否仍有界；补 V_k 时间序列而不仅是 ok ratio。

### P1-6 稳定投影不等于闭环稳定

位置：`manuscript_zh_round10.tex:344-353`

问题：谱半径投影只限制 A 矩阵，但双线性项 \sum u_l N_l z、MPC 约束、网络延迟和执行器效率共同决定闭环稳定。当前文字虽有提醒，但贡献中仍容易让人误解“稳定投影 Koopman”保证稳定。

影响：审稿人会质疑命名和理论严谨性。

修复：把“稳定投影”改成“spectral regularization/stabilized predictor”，不要把它写成闭环稳定保证；闭环稳定由 MPC/Fallback/ISS 共同提供。

## 5. 第五轮：实验与统计审查

### P0-11 E1 Koopman fresh training 未闭合

位置：`manuscript_zh_round10.tex:314`、`668`

问题：Koopman 是方法核心之一，但稿件承认 E1 fresh training 多 seed 未完成。没有 prediction RMSE、rollout error、baseline Koopman 对比、消融“无双线性/无线性/无谱投影”。

影响：Koopman 贡献缺直接证据。

修复：至少补 5-10 个训练 seed，报告 one-step、multi-step rollout、closed-loop prediction residual、spectral radius before/after projection；对比 EDMD/linear Koopman/neural Koopman no-bilinear。

### P0-12 时延补偿 claim 证据不足

位置：`manuscript_zh_round10.tex:586`、`598`、`666`

问题：稿件承认 no-delay-compensation 与 full NR-KDCC 差异很小。这意味着“Delay-Compensated Consensus MPC”出现在题目中会被挑战。

影响：题目和贡献不匹配。

修复：做 delay/dropout dose-response：不同平均时延、突发丢包率、拓扑恢复时间、通信质量 EWMA 窗口；如果仍无明显收益，应从题目中弱化 delay-compensated。

### P0-13 主对比只有两个压力场景

位置：`manuscript_zh_round10.tex:491-526`

问题：表 1 只列 mixed fault/noise 与 high-communication-noise。讨论里也承认 E0 all-scenarios 未完整闭合。

影响：不能证明一般性，容易被认为挑选有利场景。

修复：补 nominal clean、single fault、mixed、high comm 全场景 paired n=20 或更高；报告均值、标准差、置信区间和显著性检验。

### P1-7 缺统计显著性和方差

位置：`manuscript_zh_round10.tex:493-520`、`550-580`、`610-644`

问题：表中只给均值/比例，没有标准差、置信区间、p-value/effect size。paired n=20 的价值没有发挥。

影响：性能提升幅度较小时，例如 lateral RMSE 0.0453 到 0.0408，外审会问是否显著。

修复：增加 paired difference mean、95% CI、Wilcoxon 或 paired t-test、Cliff's delta；图中可加 error bars。

### P1-8 计算复杂度缺失

位置：全文无 solve time/complexity 统计。

问题：MPC + Koopman + 通信预测 + FDI/FTC 的实时性没有证明。

影响：工程可部署性不足。

修复：报告每步平均/最大求解时间、CPU/GPU、失败率、fallback 触发次数。

### P1-9 缺通信成本与网络负载指标

位置：全文无 communication overhead 指标。

问题：既然投 DCN，不能只讨论通信质量如何影响控制，还应说明方法是否增加通信开销、需要传输哪些状态、消息频率、每步字节数、拓扑变化下负载。

影响：DCN 读者会认为网络侧贡献不足。

修复：补 communication payload size、update rate、dropped message ratio、stale-neighbor ratio、communication-aware control benefit vs overhead。

## 6. 第六轮：图表与版式审查

### P1-10 图表含义已改善，但部分图更适合作为补充材料

位置：`manuscript_zh_round10.tex:588-599`、`625-653`

问题：消融柱状图、证书图和连接/受力审计图对内部分析有用，但在主文中信息密度偏低。若页数紧张，建议主文保留主对比轨迹/误差图、关键消融表和连接-受力权衡图，其余放 supplement。

影响：主线叙事可能被图表拖散。

修复：主文图控制在“方法框架 + 控制流程 + 主结果 + 关键消融 + 安全权衡”五类；其余作为 supplementary diagnostics。

### P1-11 图中文字仍含英文场景名和方法名混排

位置：图 3--图 8；`manuscript_zh_round10.tex:531-653`

问题：中文稿里图标题/图内标签大量 mixed fault/noise、high communication degradation、w/o 等英文。投稿英文版无问题，但中文内部稿视觉上不统一。

影响：中文答辩/汇报可读性下降。

修复：中文稿统一中文标签；英文投稿稿统一英文标签，不要中英混排。

### P2-1 LaTeX 日志仍有 overfull warning

位置：`manuscript_zh_round10_layoutfix2.log`

问题：最终编译无引用错误，但仍有模板/字体引起的 overfull hbox/vbox。

影响：不一定影响投稿，但最终排版前应清理。

修复：缩小 TikZ 图、调整首页布局、避免过宽框图。

## 7. 第七轮：投稿材料与伦理/声明审查

### P0-14 致谢仍有待补项

位置：`manuscript_zh_round10.tex:674-676`

问题：正文仍保留红色 `[待补：补充基金项目、课题编号和作者贡献声明。]`。

影响：技术退修；若漏投会显得稿件未完成。

修复：补 Acknowledgements、Funding、CRediT authorship contribution statement。

### P0-15 缺 competing interests statement

位置：全文未见 Declaration of interest / competing interests。

问题：DCN/Elsevier 指南要求即使无利益冲突也要声明。

影响：投稿系统或技术审查退修。

修复：加入 `Declaration of competing interest: The authors declare that they have no known competing financial interests or personal relationships...`

### P0-16 缺 data/code availability statement

位置：全文未见 Data availability。

问题：DCN 鼓励数据/代码/模型/算法/协议共享，并可给 data statement。本文大量依赖仿真数据、训练代码和图表数据，没有说明是否公开。

影响：可复现性评价降低。

修复：新增 Data and code availability，说明代码仓库、数据集、仿真配置、随机种子和不可公开原因。

### P1-12 缺 generative AI 声明

位置：全文未见 Declaration of generative AI。

问题：若后续英文稿使用 AI 辅助润色或撰写，Elsevier 要求在文末声明使用情况；如果未使用则无需添加。

影响：合规风险。

修复：根据实际情况添加或不添加；若添加，严格按 Elsevier 模板写明工具、用途和作者审校责任。

### P1-13 缺通信/控制实验数据权限与第三方图权限说明

位置：全文未见 permission statement。

问题：若使用网络下载论文图、第三方图、模板图或改编图，需要权限说明。当前图似乎多为自制，但应明确图表均由作者生成。

影响：出版合规风险。

修复：在 cover letter 或声明中写明所有图表为作者原创，若有改编图则列出授权。

## 8. 第八轮：写作逻辑与可读性审查

### P1-14 引言已经按模块展开，但“最新研究”还不够具体

位置：`manuscript_zh_round10.tex:129-135`

问题：目前每个方向只列举少量工作，且多为概括性表述。需要更明确地回答：近三年 DCN/IEEE/Automatica/T-ITS/T-IV/T-CST 相关工作分别做了什么，本文在哪一点超过它。

影响：novelty 不够锋利。

修复：每个模块至少 2-3 篇近三年直接相关文献；贡献段落中点名“在某类工作基础上增加某模块”。

### P1-15 讨论章像内部风险清单，不像论文讨论

位置：`manuscript_zh_round10.tex:662-668`

问题：当前讨论把不能过度书写的结论直接列出，这对内部审稿有用，但正式论文讨论应更学术化：解释适用边界、失败原因、工程权衡和未来工作。

影响：投稿版显得未完成。

修复：把“当前不能过度书写”改成“Limitations and future work”，以结果机理解释为主，不直接说“还没补齐”。

### P1-16 摘要和结论应删除内部版本痕迹

位置：`manuscript_zh_round10.tex:116`、`672`

问题：摘要和结论仍出现“当前稿件仍需补充”“中文 LaTeX 初稿”等内部开发语气。

影响：严重削弱正式性。

修复：投稿版只能出现研究目标、方法、结果、结论、限制。

## 9. 建议返修优先级

### 必须先做，否则不应投稿

1. 完成英文投稿版。
2. 删除摘要、结论、讨论中的内部未完成语气。
3. 补严格 AKE-A 复现或强 DMPC/robust MPC baseline。
4. 补 E1 Koopman 多 seed 预测/rollout 证据。
5. 补 delay/dropout dose-response，若无效果则改题目和贡献。
6. 补数据生成、网络模型、MPC 求解器、训练超参完整表。
7. 补 competing interests、author contribution、funding、data/code availability。

### 建议做完后再投 DCN

1. 增加通信网络侧指标和拓扑恢复实验。
2. 增加力分量 $F_x,F_y,M_z$ 和力平滑权重消融。
3. 增加计算时间/实时性统计。
4. 增加显著性检验和置信区间。
5. 将一部分诊断图移至 supplementary，主文保持简洁。

### 可后续优化

1. 清理 overfull warning。
2. 统一图中文字语言。
3. 补 ORCID、highlights、graphical abstract、referee suggestions。

## 10. 当前内审结论

如果以 DCN 审稿口径判断，本稿目前处于“有清晰研究方向和初步证据，但尚未达到投稿级闭合”的阶段。最强可保留 claim 是：

> 在四车刚性载荷协同运输的通信退化与混合故障场景中，NR-KDCC 通过通信质量感知一致性 MPC 显著降低连接最大利用率，并改善横向/纵向跟踪误差。

暂时不能强写的 claim 是：

- 全面优于上传 AKE-A 原文。
- 时延补偿是主要性能来源。
- FDI/FTC 是独立强创新。
- 载荷受力更小或更平滑。
- 全局渐近稳定。

下一轮最有效的工作不是继续润色，而是补齐 `baseline + E1 + delay dose-response + data/code reproducibility + declarations` 这五类硬缺口。

