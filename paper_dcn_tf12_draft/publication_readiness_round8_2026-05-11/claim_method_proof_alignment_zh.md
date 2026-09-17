# 主线、Claim 边界与方法-证明闭环包

## 1. 最终主线

本文主线应固定为：

> 面向退化数字通信网络的多车协同运输控制：在时延、丢包、链路质量下降和局部执行故障同时存在时，利用双线性 Koopman 预测、时延补偿一致性 MPC、在线故障识别/容错重构和安全证书，实现载荷中心跟踪、连接误差约束，并对货物受力/力矩进行约束化监测与安全评估。

这条主线的关键词是“网络退化驱动控制设计”，不是“TF14 比 TF12/TF13 更强”。

## 2. 四个贡献与方法模块映射

| 贡献 | 对应方法模块 | 内在机理 | 必须对应实验 |
|---|---|---|---|
| 网络感知的时延补偿一致性 MPC | `use_comm_quality_consensus`、`use_delay_compensation`、`use_comm_constraint_tightening`、`use_comm_degraded_fallback` | 通过链路质量调节一致性混合权重，用预测邻居状态补偿通信时延，并在通信退化时收紧约束/降级控制，降低过期邻居信息导致的连接误差和控制突变。 | E0 主对比、E2 `no_comm_aware`/`no_delay_compensation`、后续 dose-response。 |
| 面向载荷的多车协同运输建模 | 载荷中心、车辆角点、连接误差、货物受力/力矩记录 | 不只跟踪单车轨迹，而是把团队中心、各车相对位姿和载荷受力作为同一闭环监测对象，使控制效果能从“路径误差”扩展到“连接安全和载荷受力审计”。当前 E7 支持连接利用率降低和连接违规为 0，不支持“受力峰值优于 baseline”的强表述。 | E7 payload/connection safety、force norm、corner load spread、connection violation。 |
| 双线性 Koopman 预测与稳定投影 | `koopman_structure=bilinear`、`use_stable_projected_A`、ridge/online adaptation | 用升维线性/双线性结构近似非线性车辆动力学，稳定投影限制预测器的局部发散风险，使 MPC 可在较低计算成本下使用可优化的预测模型。 | E2 `no_bilinear`、`no_stable_projection`、E1 fresh prediction。 |
| FDI/FTC 与证书保护 | `use_online_fdi`、`use_online_ftc_switching`、`fault_tolerant_redistribution`、`tf14_certificate_enabled` | 在线识别执行效率衰减后重分配控制贡献，同时用一步收缩/裕度证书监控局部稳定性，避免故障车持续承担不可实现控制。 | E2 `no_fdi`/`no_ftc_switching`、E3 certificate、E7 force/connection。 |

## 3. 可写 Claim

| Claim | 当前状态 | 可写程度 |
|---|---|---|
| 本文构建了通信退化驱动的协同运输控制框架 | 可写 | 可以放摘要/引言。 |
| 本文提出网络感知 DCC-MPC，将链路质量、时延补偿和通信降级 fallback 纳入一致性控制 | 可写 | 需与 `no_comm_aware`、`no_delay_compensation` 消融绑定。 |
| 本文在指定有界时延/丢包和可恢复拓扑假设下给出 practical boundedness/UUB 类型证明 | 可写 | 不写任意通信故障稳定。 |
| 本文相对 AKE-style `AKE-M` surrogate 有更完整的网络/故障/安全机制 | 可写 | 不能写严格优于 uploaded AKE 原文。 |
| E3 证书统计在四个场景 `n=20` 下全部完成路径且无运行异常 | 可写 | 只能支撑证书/安全监测链条可运行，不能替代严格稳定性证明。 |
| E7 连接安全统计在两个场景 `n=20` 下全部非辅助方法成功，连接违规为 0 | 可写 | 可写连接约束满足和连接利用率改善；不能写货物受力峰值低于 baseline。 |
| ZOH surrogate 在 mixed/communication 工况下不能完成路径 | 可写为辅助观察 | 不能把它写成“物理 DMPC baseline 被击败”。 |

## 4. 不可写 Claim

| 禁止表述 | 原因 | 替代表述 |
|---|---|---|
| 本文严格优于原文 AKE baseline | `AKE-A` 未复现，当前仅 `AKE-M`。 | 本文相对 AKE-style mechanism comparator 展示了网络韧性机制，原文严格复现仍为 pending。 |
| 本文优于所有网络控制方法 | 只有 ZOH surrogate，缺 physical-model DMPC。 | 本文相对弱底线和模块消融显示机制有效；更强网络控制 baseline 待补。 |
| 任意通信故障下稳定 | 证明只覆盖有界退化和可恢复条件。 | 在给定时延/丢包/拓扑假设下保持实践有界。 |
| E3/E7 的 `n=20` 结果证明所有主对比统计显著 | 当前只有证书和连接安全两类 n=20，E0/E2 主对比仍未完整完成。 | 可写 E3/E7 的 paired n=20 统计；主对比和核心消融仍需 E0/E2 n=20。 |
| 货物受力峰值/受力 RMS 全面优于 baseline | E7 n=20 显示 TF14 的连接利用率更低、连接违规为 0，但力峰值高于 baseline。 | 写成“力/力矩被纳入记录、约束监测和安全审计；力平滑仍作为待优化指标”。 |
| Koopman 模型精度已最终验证 | E1 fresh 多训练种子未完成。 | 当前先给出方法定义，预测精度统计待 E1。 |

## 5. 方法到证明的闭环写法

应在证明前明确如下链条：

```text
车辆动力学与载荷几何约束
→ 离线/在线 Koopman 预测器
→ 单车 MPC 候选输入 u_i^mpc
→ 通信质量与时延补偿得到 u_i^comm
→ FDI/FTC 重构得到 u_i^ftc
→ 团队聚合输入 u_c^agg
→ 局部闭环映射 e_{k+1}=F_sigma(e_k,w_k)
→ 局部增益界 / Lyapunov 差分不等式
```

证明中不应把 `A_sigma/B_sigma` 直接说成 Koopman 训练矩阵，也不应说成全局闭环矩阵。更合适写法是：

> 在固定主动约束集合、固定通信模式和固定故障重构模式的局部邻域内，完整控制链诱导的误差闭环可由局部仿射化或增益界描述；`A_sigma` 和 `B_sigma` 仅用于表示该局部模式下的辅助线性化对象。

## 6. Lyapunov 结论边界

最终证明建议使用：

```text
V(e_{k+1}) - V(e_k) <= -alpha ||e_k||^2 + beta ||d_k||^2 + eta_sigma
```

其中：

- `e_k` 包含载荷中心误差、车辆相对连接误差、必要的控制/预测误差。
- `d_k` 聚合模型误差、通信时延预测误差、丢包导致的邻居状态误差和故障估计残差。
- `eta_sigma` 表示模式切换、约束激活变化和有限求解误差引入的残余项。

可得结论：

> 若扰动有界、通信退化满足指定上界、拓扑在给定窗口内可恢复、切换满足 dwell-time 或有限切换假设，则闭环误差是一致最终有界的；最终界随模型误差、通信扰动和求解残差增大而增大。

## 7. 稿件集成状态

| 模块 | 当前完成度 | 还差什么 |
|---|---:|---|
| 主线/claim 边界 | 85% | 已删除“货物受力平滑”等过强表述；仍需回填中文稿逐句 QA。 |
| 方法/证明闭环 | 85% | 与 DOCX 公式编号、符号表和最终实验字段做 QA。 |
| 实验工程 | 85% | 已有 E3/E7 n=20、E2 smoke、gate、异常续跑和后台日志容错；还差 dose/topology runner。 |
| 投稿级数据本体 | 70% | E0 targeted、E3、E7 已达到 paired n=20；仍缺 E2 全量消融、E1 fresh、AKE-A 或强 baseline。 |
| 文献证据 | 70% | 已有可写矩阵草案；仍需 BibTeX 和全文摘要精读。 |
