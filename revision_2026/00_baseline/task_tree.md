# VT-2026-05393 重投稿任务书：审稿意见闭环任务树

> 目标：在 120 天窗口内，把 AE 与三位审稿人的意见转化为可执行、可验收、可追溯的修改任务，并形成符合 IEEE TVT 新投稿要求的完整投稿包。  
> 原稿号：VT-2026-05393  
> 5080 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前论文源文件：`D:\PDxc\Review\TVT_upload_ready_20260706_14page\TVT_LaTeX_source\main.tex`

## 0. 任务书使用规则

### 0.1 唯一完成标准

任务不是以“代码已运行”或“文字已修改”为完成，而是以对应审稿意见被证据关闭为完成。每个任务必须同时具备：

1. 可复现代码或推导；
2. 冻结的配置、种子和版本号；
3. 自动生成的数据、图或表；
4. 统计或数学验收结果；
5. 论文修改位置；
6. response letter 中的逐条回复。

### 0.2 证据等级

- **E0：解释性文字**——只能用于澄清，不能支撑核心贡献。
- **E1：单次诊断**——只能发现问题，不能用于一般性结论。
- **E2：多种子统计**——可支撑实验性结论。
- **E3：强基线 + 多种子 + 效应量**——可支撑相对优势。
- **E4：严格推导/连续域证书 + E3**——可支撑理论性核心贡献。
- **E5：跨模型、高保真或 HIL/实物验证**——可支撑实际安全与工程适用性。

主贡献至少达到 E3；稳定性和 IRSP 的理论贡献必须达到 E4；实际载荷安全主张必须达到 E5。

### 0.3 审稿意见编号

- `AE-1`：新颖性、稳定性、bilinear/IRSP/delay 消融不足。
- `AE-2`：force、工作域、基线、参数、统计和表达不足。
- `R1-1…R1-6`：Reviewer 1 的六条意见。
- `R2-1…R2-7`：Reviewer 2 的七条意见。
- `R3-1…R3-7`：Reviewer 3 的七条意见。

## 1. 总任务树

```text
T0 立项、冻结原稿与审稿意见
├─ T1 贡献主线重构与范围决策
│  ├─ T1.1 建立 claim–evidence–reviewer 矩阵
│  ├─ T1.2 重做文献定位与新颖性对比
│  ├─ T1.3 决定 IRSP 是否保留为主贡献
│  ├─ T1.4 决定 Delay-Compensated 是否保留在标题
│  └─ G1 贡献主线冻结门
├─ T2 代码与复现实验基础设施
│  ├─ T2.1 代码、配置、数据与随机种子冻结
│  ├─ T2.2 统一实验 runner 和日志 schema
│  ├─ T2.3 指标、统计与自动制图流水线
│  └─ G2 可复现性门
├─ T3 IRSP 数学修正与实现
│  ├─ T3.1 复现并定位 Eq. (22) 错误
│  ├─ T3.2 连续输入域 IRSP 重新设计
│  ├─ T3.3 在线更新后的可行性处理
│  ├─ T3.4 IRSP 理论与数值验证
│  └─ G3 IRSP 去留门
├─ T4 闭环稳定性与递归可行性
│  ├─ T4.1 审计原 Theorem 1 的循环依赖
│  ├─ T4.2 建立误差集合、终端集和 fallback 不变集
│  ├─ T4.3 证明递归可行性与 ISS/UUB
│  ├─ T4.4 多种子证书日志验证
│  └─ G4 理论主张等级门
├─ T5 强基线建设与公平性协议
│  ├─ T5.1 Tube/robust MPC
│  ├─ T5.2 Delay/packet-loss-aware DMPC
│  ├─ T5.3 Network-aware consensus MPC
│  ├─ T5.4 AKE-M 公平复核
│  └─ G5 基线有效性门
├─ T6 核心机制多种子验证
│  ├─ T6.1 Bilinear Koopman/IRSP 实验
│  ├─ T6.2 Delay sweep 与 noDelay
│  ├─ T6.3 Communication-awareness 实验
│  ├─ T6.4 PPC、FDI/FTC、role、fallback 消融
│  ├─ T6.5 完整消融与交互效应
│  └─ G6 核心贡献证据门
├─ T7 Force、载荷安全与物理有效性
│  ├─ T7.1 Force proxy 定义和实现审计
│  ├─ T7.2 Tracking–force Pareto 实验
│  ├─ T7.3 高保真 multibody/HIL 验证
│  └─ G7 安全主张门
├─ T8 工作域与压力测试
│  ├─ T8.1 速度扩展和纵向 phase 修复
│  ├─ T8.2 曲率、网络、故障和模型失配矩阵
│  ├─ T8.3 成功域/失败域绘制
│  └─ G8 论文适用范围门
├─ T9 参数、引用和文字规范
│  ├─ T9.1 完整参数表
│  ├─ T9.2 引用逐条核验
│  ├─ T9.3 删除防御性写法和过度主张
│  └─ G9 表达与复现门
├─ T10 论文重写与投稿材料
│  ├─ T10.1 按证据重写论文
│  ├─ T10.2 逐条 response letter
│  ├─ T10.3 Supplement、代码与数据说明
│  └─ T10.4 16 页与投稿格式检查
└─ G10 最终重投稿门
```

## 2. T0：立项、冻结原稿与审稿意见

### T0.1 建立不可变基线

**对应意见：**全部。

**步骤：**

1. 在 5080 项目建立只读标签或快照 `VT-2026-05393-original`。
2. 保存原稿 PDF、LaTeX、图、表、补充材料、运行代码和产生原表格的数据。
3. 保存审稿信原文并逐条编号。
4. 生成 `original_claims.md`，逐句摘出摘要、贡献、定理和结论中的所有可检验主张。
5. 对每条主张记录原证据、证据等级和审稿人质疑。

**产物：**

- `revision_2026/00_baseline/original_claims.md`
- `revision_2026/00_baseline/reviewer_comments_index.md`
- 原稿代码/数据版本标识。

**验收：**原稿中的每个数字、表格和主要结论都可追溯到数据或明确标记为无法追溯。

## 3. T1：贡献主线重构与范围决策

### T1.1 建立 claim–evidence–reviewer 矩阵

**对应意见：**`AE-1`, `R1-1`, `R1-5`, `R2-3`, `R3-5`, `R3-7`。

**步骤：**

1. 将原稿模块拆为 bilinear Koopman、IRSP、MPC、consensus、communication awareness、delay compensation、PPC、FDI/FTC、role scheduling、4WS local path、fallback、certificate。
2. 对每个模块写明：解决的问题、数学变化、预期改善指标、当前证据、最接近既有方法。
3. 将“模块存在”与“构成创新”分开判断。
4. 只保留能达到 E3/E4 的模块为主贡献。

**产物：**`revision_2026/01_scope/claim_evidence_matrix.csv`。

**验收：**每项贡献至少对应一个唯一机制、一个主要指标、一组强基线和一个最终图表；无法对应者降为实现细节。

### T1.2 重做文献定位与新颖性对比

**对应意见：**`R1-1`, `R1-4`, `R2-4`, `R3-6`。

**步骤：**

1. 检索 Koopman-MPC、robust/tube MPC、packet-loss/delay-aware DMPC、DoS-resilient distributed control、secure platoon estimation、cooperative payload transport。
2. 优先核验审稿人建议的 resilient distributed optimization、digital-twin resilient consensus、secure distributed estimation。
3. 建立方法对比表：输入相关模型、连续输入域保证、delay、dropout/DoS、payload coupling、force constraint、recursive feasibility、验证层级。
4. 用“尚未同时解决的明确技术缺口”替换“把多个模块统一起来”的拼装式新颖性。

**产物：**文献表、BibTeX、related-work 对比表、1 页 gap memo。

**验收：**贡献描述不再依赖“首次组合多个现有模块”；每个新颖性主张都能指出与最接近工作的数学差异。

### T1.3 决定 IRSP 是否保留为主贡献

**依赖：**T3、T6.1 的预实验结果。

**通过条件：**连续输入域证书可行，且相较 bilinear-noIRSP 至少在鲁棒可行率、约束违反率或闭环稳定指标上获得统计和实际意义明确的改善。

**停止条件：**若 IRSP 迫使 bilinear 项接近零、只改善审计量而不改善闭环，或理论只能覆盖有限采样点，则删除 IRSP 主贡献和“certifiable predictor”措辞。

### T1.4 决定 Delay-Compensated 是否保留在标题

**依赖：**T6.2。

**通过条件：**在预先定义的现实 delay/burst-loss 范围内，full 相比 noDelay 和强延迟基线表现出稳定、显著且有实际意义的改善。

**停止条件：**若差异仍接近零，则从标题、简称和贡献中删除 Delay-Compensated；补偿只作为实现细节。

### G1 贡献主线冻结门

**门前必须完成：**T1.1、T1.2、T1.3/T1.4 的预决策。

**输出决策：**

- 方案 A：通信质量感知 MPC + 连续域 IRSP，两项贡献；
- 方案 B：只保留通信质量感知 robust Koopman-MPC；
- 方案 C：若强基线下优势不成立，停止 TVT 重投并重新选题/期刊。

## 4. T2：代码与复现实验基础设施

### T2.1 冻结代码、配置、数据和种子

**对应意见：**`R1-6`, `R2-5`。

**步骤：**

1. 从现有 `tf14_runtime.py`、`tf14_stage2_statistics_*`、`tf14_stage3_theory_*` 和 `tf14_remaining_experiments_*` 中梳理实际入口。
2. 建立 `revision_2026/configs/`，禁止论文参数继续散落在 notebook 和脚本中。
3. 固定训练、调参、测试三套互斥 seed。
4. 每次运行记录 Git commit、config hash、seed、Python/依赖版本、硬件和耗时。

**验收：**同一配置重复两次时，确定性指标一致；随机指标的随机流可重放。

### T2.2 统一 runner 和日志 schema

**步骤：**

1. 建立统一命令：`method × scenario × seed`。
2. 统一已有日志：`certificate.csv`、`comm.csv`、`connection.csv`、`payload_force.csv`、`fault.csv`、`fdi.csv`、`switch.csv`、`phase_role.csv`、`summary.json`。
3. 增加 schema version、单位、采样时间和缺失值检查。
4. 任何失败必须记录失败原因，而不是只写 success=0。

**验收：**任一 trial 可由 manifest 一键重跑；统计脚本不读取人工编辑文件。

### T2.3 指标、统计和自动制图流水线

**对应意见：**`R2-5`。

**步骤：**

1. 输出 trial-level 长表。
2. 计算 mean、SD、median、IQR、bootstrap 95% CI。
3. 配对连续指标执行 paired t-test 或 Wilcoxon，并报告效应量；成功率采用配对二项/McNemar；Holm 校正多重比较。
4. 自动生成 LaTeX 表格和出版图。
5. 图表脚本写入样本数、单位、CI 定义和失败样本处理规则。

**验收：**论文中每个主要数字均能自动追溯到 trial-level 数据。

### G2 可复现性门

在 G2 通过前不得启动最终大规模实验；允许少量 smoke test，不得用于论文结论。

## 5. T3：IRSP 数学修正与实现

### T3.1 复现 Eq. (22) 错误

**对应意见：**`R3-4`, `R2-2`。

**步骤：**

1. 构造 `||A+||₂ > r_u` 的最小数值例子。
2. 验证原式令 `gamma_c=0` 后仍有 `||A_eff||₂>r_u`。
3. 检查现有训练模型中该情况的出现频率。
4. 在修改记录中明确承认原公式不能保证所述界。

**产物：**单元测试、错误复现报告、受影响实验清单。

### T3.2 连续输入域 IRSP 重新设计

**步骤：**

1. 定义实际连续控制盒 `U=[u_min,u_max]`。
2. 第一阶段投影 `A`，强制 `||A+||_P≤r_A<r_u`；不能只限制谱半径。
3. 第二阶段求最大 `gamma`，使所有 `u∈U` 满足 `||A+ + gamma Σu_l N_l||_P≤r_u`。
4. 根据模型规模选择顶点 LMI、共同二次 Lyapunov 函数、加权 induced norm 或可验证上界。
5. 对非正规矩阵同时记录 spectral radius、最大奇异值和 transient amplification 指标。
6. 明确不可行返回值，不允许把 `gamma=0` 当成可行证书。

**验收：**随机采样只用于反例搜索；正式保证来自连续域推导/求解。所有测试输入均不得违反所声明的界。

### T3.3 在线更新后的可行性处理

**步骤：**

1. 每次 online Koopman 更新后重新认证。
2. 认证失败时依次执行：缩小更新步长 → 回滚最近可行模型 → 冻结学习 → fallback。
3. 记录每种处理的触发率、连续触发长度和闭环影响。

**验收：**不允许未认证模型进入 MPC；fallback 本身必须满足 T4 的可行性要求。

### T3.4 IRSP 理论与数值验证

**对应意见：**`R1-5`, `R2-2`, `R2-3`。

**步骤：**

1. 离线比较 linear、bilinear、bilinear+IRSP 的 1–H 步预测误差。
2. 闭环比较成功率、约束违反率、MPC 不可行率、tracking、connection、force proxy。
3. 报告 gamma 分布和 bilinear 项保留比例，防止“认证后实际退化为线性模型”。
4. 运行多种子、跨训练/测试模型失配实验。

**通过条件：**理论界正确且至少一项预先指定闭环主指标获得显著和实际有意义的改善。

### G3 IRSP 去留门

未通过则执行：删除 IRSP 主贡献、删除 certifiable/stability-projected 的强表述、简化标题和方法图，但保留诚实的消融结果。

## 6. T4：闭环稳定性与递归可行性

### T4.1 审计原 Theorem 1

**对应意见：**`R1-3`, `R2-1`。

**步骤：**

1. 标记 theorem 中哪些条件是设计可保证、哪些只能事后从日志估计。
2. 画出依赖图，识别“假设 passing step 已下降，再以 certificate pass 证明下降”的循环。
3. 对 nominal-clean ok ratio 0.360、single-fault 0.799 和负 margin 进行失败原因分解。

**产物：**`theorem_dependency_audit.md`。

### T4.2 建立先验可检查条件

**步骤：**

1. 定义 Koopman residual、delay error、communication error、model mismatch 的有界集合。
2. 构造 constraint tightening、terminal cost、terminal controller、terminal set。
3. 为 fallback 构造正不变安全集合。
4. 为 C0–C3 模式给出共同 Lyapunov 或 dwell-time/average-dwell-time 条件。

**验收：**条件在运行前可验证；不能依赖最终成功日志才能成立。

### T4.3 证明递归可行性与 ISS/UUB

**步骤：**

1. 用 shifted feasible sequence 证明下一步可行。
2. 推导价值函数下降，而不是把下降作为假设。
3. 将 disturbance、residual、delay、switching 明确进入最终界。
4. 给出适用域和不可保证的情况。
5. 由独立人员逐式检查符号、维度、不等式方向和隐含假设。

**通过条件：**证明链不依赖在线 certificate pass ratio；IRSP 条件与实际实现一致。

### T4.4 证书日志验证

**步骤：**

1. 多种子报告 pass ratio、minimum margin、最大连续失败步数、窗口失败密度、失败步增长率和 fallback recovery time。
2. 将 nominal-clean 低通过率作为待修复问题，不用“保守模式反而容易通过”来辩护。
3. 检查理论常数是否与实测量级一致，而非仅证明存在。

### G4 理论主张等级门

- 通过：保留严格限定范围内的 ISS/UUB 与 recursive feasibility。
- 未通过：删除 stability theorem，改称 empirical decrease monitor；摘要、标题和贡献不得出现 certificate-verified stability。

## 7. T5：强基线建设与公平性协议

### T5.1 Tube/robust MPC

**对应意见：**`R2-4`, `R3-6`。

使用相同车辆—载荷模型、输入/连接约束、采样周期和参考路径；明确 uncertainty set 与 tube 设计。

### T5.2 Delay/packet-loss-aware DMPC

实现时间戳邻居预测、delay bound 和 constraint tightening；不能使用明显弱于本文的信息或模型。

### T5.3 Network-aware consensus MPC

不使用 Koopman，但使用同样链路质量、通信观测和约束，使其隔离“通信感知”与“Koopman”贡献。

### T5.4 AKE-M 公平复核

1. 检查 AKE-M 是否被正确实现和充分调参。
2. 所有方法使用相同初态、故障、网络随机流。
3. 为每种方法给同等调参预算，并在 validation set 上调参。
4. ZOH-cons 只作为弱下界，不作为主要优越性证据。

### G5 基线有效性门

至少 3 个独立强基线通过单元测试和公平性审计，才允许开始最终主比较。

## 8. T6：核心机制多种子验证

### T6.1 Bilinear Koopman/IRSP

**对应意见：**`R1-5`, `R2-2`, `R2-3`。

**比较：**raw linear、lifted linear、bilinear、bilinear+sampled projection（仅诊断）、bilinear+continuous IRSP。

**主指标：**multi-step prediction、closed-loop constraint violation、MPC infeasibility、tracking、connection utilization、transient amplification。

**通过条件：**若 bilinear+IRSP 只改善谱半径而不改善任何闭环主指标，则不得列为核心贡献。

### T6.2 Delay sweep 与 noDelay

**对应意见：**`AE-1`, `R2-3`, `R3-7`。

**步骤：**

1. 固定时延：0/1/2/4/8 sampling steps。
2. 随机时延：定义分布与上界。
3. burst delay/dropout：使用 Gilbert–Elliott 或明确 burst length。
4. 比较 full、noDelay、timestamp-only、delay-aware DMPC。
5. 报告性能—delay 曲线、失败阈值和效应量。

**通过条件：**full 在预先定义的非零延迟区间相对 noDelay 有稳定改善；否则执行 T1.4 停止条件。

### T6.3 Communication-awareness

**对应意见：**`R1-4`, `R2-3`。

**步骤：**

1. 比较 full、noComm、network-aware consensus MPC、delay-aware DMPC。
2. 单独改变 packet loss、delay、quality-estimation bias、DoS burst。
3. 检查通信质量估计误差和更新频率敏感性。

**主指标：**connection utilization、constraint violation、tracking、成功率和恢复时间。

### T6.4 PPC、FDI/FTC、role、fallback

**对应意见：**`R1-6`, `R3-5`。

每个模块都必须预先规定触发场景和主要指标：

- PPC：envelope violation、成功率；
- FDI/FTC：检测延迟、误报/漏报、故障后恢复误差；
- role scheduling：负载分配和故障隔离收益；
- fallback：不可行/证书失败后的约束保持和恢复时间。

若模块只在单个精心选择场景有效，则降为案例机制，不列一般性贡献。

### T6.5 完整消融与交互效应

**步骤：**

1. 所有单模块消融使用相同 paired seeds，建议 `n≥20`。
2. 增加关键组合：noComm+noDelay、noIRSP+noPPC、noFDI+noFallback。
3. 使用两因素/多因素模型分析交互，避免把组合收益错误归因于单模块。

### G6 核心贡献证据门

每项最终贡献必须达到 E3；未达到者从摘要、贡献和标题删除。

## 9. T7：Force、载荷安全与物理有效性

### T7.1 Force proxy 审计

**对应意见：**`R1-2`, `R2-6`。

**步骤：**

1. 核对 spring–damper proxy 的单位、刚度、阻尼、采样和窗口定义。
2. 检查峰值是否来自数值瞬态、初始化或模式切换。
3. 区分单连接力、合力、方向分量、RMS、P95/P99、0.1 s peak、impulse 和超阈持续时间。
4. 全文统一称 connector-force proxy，除非完成 T7.3。

### T7.2 Tracking–force Pareto 实验

**步骤：**

1. 扫描 `lambda_F`、`lambda_c`、`lambda_u` 和 payload-protection 阈值。
2. 对 AKE-M、强基线和本文方法给出 Pareto 前沿。
3. 同时报告 lateral、longitudinal lag、connection utilization 和 force proxy。
4. 不选择性隐藏 NR-KDCC 更高的 force peak。

**验收：**正文以 Pareto 结果解释权衡；不能再用“仅作为 diagnostic”回避不利指标。

### T7.3 高保真 multibody/HIL

**步骤：**

1. 建立与训练模型不同的多体动力学或 HIL 环境。
2. 加入质量、惯量、连接刚度/阻尼、轮胎和网络时延失配。
3. 比较 proxy 与高保真 connector force 的相关性、偏差和峰值误差。
4. 若有条件，加入实测 connector force 和真实网络 delay trace。

### G7 安全主张门

- 达到 E5：可有限度讨论 practical payload safety。
- 未达到 E5：删除真实安全、真实力和工程成熟性主张，只保留 simulation proxy trade-off。

## 10. T8：工作域与压力测试

### T8.1 速度扩展与纵向 phase 修复

**对应意见：**`R2-7`。

**步骤：**

1. 定位 10 m/s 纵向 RMSE 约 6.91 m 和 15 m/s 全失败的根因：参考进度、纵向 phase、输入饱和、预测域、连接约束或数值不可行。
2. 使用日志逐项排除，不直接调参掩盖。
3. 修复后在独立 test seeds 上测试 2/5/8/10/12/15 m/s。

### T8.2 压力测试矩阵

至少覆盖：

- 多级速度与曲率；
- delay、dropout、burst loss、quality bias；
- actuator degradation、sensor/packet bias、DoS；
- payload mass/inertia、轮胎、连接参数和模型残差失配。

### T8.3 成功域/失败域

生成 speed–curvature、delay–dropout、fault–model-mismatch 成功率热图；预先定义成功标准和约束违反标准。

### G8 适用范围门

- 若 10–15 m/s 仍失败，标题、摘要、问题定义和结论必须明确 **low-speed**。
- 不得把失败域仅放到 future work；正文必须显示工作域边界。

## 11. T9：参数、引用和写作规范

### T9.1 完整参数表

**对应意见：**`R1-6`, `AE-2`。

必须列出：采样周期、预测/控制时域、全部权重、`kappa_off/kappa_on`、C0–C3 触发阈值、`q_df`、`eta_df`、PPC envelope、FDI 阈值/窗口、FTC 界、网络模型、Koopman 维数与训练量、online update、IRSP 输入域及 `r_A/r_u`、fallback、force proxy 刚度阻尼。

**验收：**论文表格与运行 config 自动对照；不存在未披露的关键 magic number。

### T9.2 引用逐条核验

**对应意见：**`R3-2`, `R3-3`。

**步骤：**

1. 以 DOI、IEEE Xplore 或出版社官网核验每条引用。
2. 重点核验原稿 [10]、[13]–[15]、[33]、[37]。
3. 原 Ref. [33] 的作者信息以正式来源为准，不能只照审稿人的候选作者列表修改。
4. 保存旧编号—新编号映射，供 response letter 使用。

**验收：**作者、题目、期刊、年份、卷期页码和 DOI 全部完整；无无法确认的引用。

### T9.3 删除防御性写法和过度主张

**对应意见：**`R3-1`, `R1-2`。

**步骤：**

1. 搜索 `not claimed`、`rather than`、`diagnostic`、`audit`、`certifiable`、`guarantee`、`stability`、`safety`。
2. 将辩护句改为直接的结果句，例如：方法降低 tracking/connection，但提高 force proxy peak。
3. 对每个 superiority、robust、resilient、stable、safe 主张要求证据编号。
4. 删除无法达到相应证据等级的形容词。

### G9 表达与复现门

引用零错误、参数可复现、全文主张与证据等级一致后通过。

## 12. T10：论文重写与投稿材料

### T10.1 按证据重写论文

**依赖：**G1–G9。

**顺序：**

1. 先冻结最终 claim–evidence matrix。
2. 重写标题、摘要和贡献。
3. 重写 related work 与 problem formulation。
4. 用实际实现更新算法和理论。
5. 按研究问题组织实验，不按模块堆叠。
6. 单列 limitations 和 operating envelope。
7. 最后重写结论，只总结达到 E3/E4 的结果。

### T10.2 逐条 response letter

每条采用统一模板：

1. **Reviewer comment**：原意见摘要；
2. **Assessment**：同意、部分同意或不同意，并给依据；
3. **Action**：代码/理论/实验/文字具体改动；
4. **Evidence**：新图表、统计量或定理；
5. **Location**：修订稿页码、节、公式、图表；
6. **Residual limitation**：仍未解决的问题及已收缩的主张。

禁止只回复 “We have clarified/revised accordingly”。

### T10.3 Supplement、代码与数据说明

Supplement 至少包含：完整参数、场景定义、统计方法、额外 CI、失败样本、消融、理论细节和复现命令。建立匿名代码/数据包或说明公开计划。

### T10.4 投稿格式检查

1. IEEE 双栏，字体不小于 10 pt。
2. regular paper 全部内容不超过 16 页，包括正文、图表、参考文献和作者简介。
3. 新投稿中引用 VT-2026-05393。
4. 提交 summary of changes、cover letter、clean manuscript、source 和 supplementary。

### G10 最终重投稿门

以下任一项未满足，不建议提交：

- [ ] 每条 AE/R1/R2/R3 意见有任务、证据和 response 对应。
- [ ] 标题中的每个机制都有 E3 以上证据。
- [ ] Eq. (22) 已修正，且有反例单测和连续域证书。
- [ ] 稳定性结论不存在循环假设；否则已降级。
- [ ] delay compensation 有实质收益；否则已从标题删除。
- [ ] 至少三个强基线完成公平比较。
- [ ] 核心实验均为 paired multi-seed，含 CI、检验和效应量。
- [ ] force proxy 劣化被正面报告并完成 Pareto 分析。
- [ ] 速度/曲率/网络/失配成功域已明确。
- [ ] 未完成高保真/HIL 时，已删除 practical safety 主张。
- [ ] 参数可由配置复现，引用均经正式来源核验。
- [ ] 全稿不超过 16 页，投稿材料齐全。

## 13. 审稿意见关闭矩阵

| 意见 | 主责任任务 | 关闭证据 |
|---|---|---|
| AE-1 | T1, T3, T4, T6 | 两项贡献冻结；IRSP/delay 多种子证据；非循环理论 |
| AE-2 | T5, T7, T8, T9 | 强基线、force Pareto、工作域、参数和写作修正 |
| R1-1 | T1.1–T1.2 | 新颖性对比表和精确数学差异 |
| R1-2 | T7 | force proxy 审计、Pareto、多种子结果 |
| R1-3 | T4 | recursive feasibility/ISS 推导或理论降级 |
| R1-4 | T1.2, T6.3 | 攻击/韧性文献定位和 DoS/burst 场景 |
| R1-5 | T3, T6.1 | bilinear/IRSP 连续域证书与闭环价值 |
| R1-6 | T2, T9.1 | 配置化与完整参数表 |
| R2-1 | T4 | 去循环证明、失败步统计和工作域 |
| R2-2 | T3 | 连续输入域 induced-norm/LMI 证书 |
| R2-3 | T6 | 全模块多种子消融与交互效应 |
| R2-4 | T5 | 3 个强基线与公平调参协议 |
| R2-5 | T2.3, T6–T8 | n≥20、CI、显著性、效应量 |
| R2-6 | T7 | 高保真/HIL或安全主张降级 |
| R2-7 | T8 | 高速修复、成功域/失败域、low-speed 限定 |
| R3-1 | T9.3 | 删除防御性措辞，直接报告权衡 |
| R3-2 | T9.2 | 缺失书目信息补全 |
| R3-3 | T9.2 | 作者信息按正式来源纠正 |
| R3-4 | T3.1–T3.2 | Eq. (22) 反例、修正公式、单元测试 |
| R3-5 | T1.1, T6.4–T6.5 | 模块降级或完整消融证据 |
| R3-6 | T5 | robust/delay/network-aware 基线 |
| R3-7 | T1.4, T6.2 | delay sweep；无收益则改标题 |

## 14. 120 天排期与关键路径

| 时间 | 关键任务 | 阶段产物 |
|---|---|---|
| 第 1 周 | T0、T1.1、T4.1 | 原稿冻结、主张矩阵、定理审计 |
| 第 2 周 | T1.2、T2.1–T2.2、T3.1 | 文献定位、配置框架、Eq. (22) 反例 |
| 第 3–4 周 | T3.2–T3.3、T5.1–T5.3 | 连续域 IRSP 原型、三个强基线原型 |
| 第 5 周 | T2.3、T4.2、基线单测 | 统计流水线、终端/误差集合设计 |
| 第 6 周 | T6.1、T6.2 预实验 | IRSP 与 delay 去留数据，完成 G1/G3 预判 |
| 第 7–8 周 | T4.3、T5.4、T6.3–T6.5 | 理论草案、公平性审计、完整消融预跑 |
| 第 9–11 周 | T6、T7.2、T8 最终多种子 | 冻结主数据、统计表图、成功域 |
| 第 12–13 周 | T7.3、T4.4 | 高保真/HIL、证书/理论验证 |
| 第 14 周 | G1–G9 总审查 | 最终贡献、标题和结论等级冻结 |
| 第 15–16 周 | T10.1–T10.3 | 修订稿、supplement、response letter |
| 第 17 周 | T10.4、G10 | 16 页合规投稿包 |

**关键路径：**`T0 → T2 → T3/T5 → T6 → G6 → T10`。  
理论路径：`T3 → T4 → G4 → T10`。  
标题决策路径：`T6.2 → T1.4 → G1 → T10`。  
安全主张路径：`T7.1 → T7.2 → T7.3/G7 → T10`。

## 15. 每周项目检查模板

每周只回答以下问题：

1. 本周关闭了哪些审稿意见？证据文件在哪里？
2. 哪些任务只是“跑完”但没有达到验收条件？
3. 是否出现应触发降级主张、改标题或停止路线的结果？
4. 新增实验是否遵守 frozen config、paired seeds 和公平性协议？
5. 论文中的哪个 claim 因新证据被保留、修改或删除？
6. 距离 G10 仍有哪三个最高风险阻塞项？

## 16. 最高风险提醒

1. **最大风险不是实验数量不够，而是核心机制可能确实无收益。** noDelay 与 noIRSP 的现有结果已经发出这一信号，应允许删贡献、改标题，不能无限调参追求预设结论。
2. **IRSP 的 Eq. (22) 是实质数学错误。** 必须先修正再跑最终实验，否则后续所有 certificate/stability 结论都不可靠。
3. **强基线可能消除现有优势。** 这是需要接受的科学结果；若发生，应重新定位为特定低速场景的工程方法或停止 TVT 重投。
4. **force proxy 与真实载荷安全不是同一件事。** 没有 E5 证据时，不能用“连接利用率低”替代“更安全”。
5. **120 天并不宽裕。** 高保真/HIL、三类基线、理论重构和大规模多种子实验并行度高；G1、G3、G4 的停止条件必须严格执行，避免在无效方向耗尽时间。

