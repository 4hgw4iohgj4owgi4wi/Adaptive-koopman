# 并行任务完成情况对照表

- 对照来源：`parallel_article_completion_2026-05-10/05_integrated_parallel_execution_plan.md`
- 当前核对时间：2026-05-11
- 当前执行记录：Round2/Round3/Round4/Round5/Round6/Round7 readiness 记录

## 状态标记

| 标记 | 含义 |
|---|---|
| 已完成 | 任务已有可用产物，并通过基本验证。 |
| 部分完成 | 有计划、草稿、脚本或 smoke 证据，但还不能支撑投稿主结论。 |
| 未完成 | 仍缺核心实现、数据或文献记录。 |
| 暂缓/降级 | 任务被判断为不适合当前主线，或只能作为弱证据/辅助项。 |

## A. Topic 与论文主线

| 子任务 | 当前状态 | 已有产物/证据 | 剩余动作 |
|---|---|---|---|
| A1 固定主 topic | 部分完成 | 已将主线固定为“退化数字通信网络下的多车协同运输控制”，Round2/Round3 均确认 DCN 网络问题驱动叙事可以安全集成。 | 需要回填到最新中文 DOCX 和英文 LaTeX。 |
| A2 重排贡献点 | 部分完成 | 已形成 4 个贡献方向：网络感知 DCC-MPC、协同运输建模、Koopman predictor、安全韧性扩展。 | 需要与最终 method、experiment、citation 一一绑定；未有最终稿件集成版。 |
| A3 压低 claim | 已完成 | 已冻结 claim 边界：只能写 practical boundedness/UUB、bounded degradation，不能写任意通信故障稳定或全局渐近稳定。 | 后续写稿时继续执行，不再扩 claim。 |
| A4 删除内部版本叙事 | 部分完成 | 记录中已明确禁止用 TF12/TF13/TF14 作为论文创新来源。 | 需要检查中文 DOCX 全文，清掉残留版本叙事。 |

## B. 文献与 Baseline 公平性

| 子任务 | 当前状态 | 已有产物/证据 | 剩余动作 |
|---|---|---|---|
| B1 补 DCN-native 文献 | 未完成 | 已建立文献类别和 citation queue，但 Round2 记录显示 `V3 final-ready = 0`。 | 需要补近三年 V2X/CAV/CACC、QoS/AoI、resilient DMPC、burst/jitter 等可核验 citation record。 |
| B2 补 Koopman/MPC/协同运输文献 | 未完成 | 已有写作要求和矩阵框架。 | 需要每条贡献绑定 DOI/URL/BibTeX/access date/used sentence。 |
| B3 冻结 T1 baseline | 部分完成 | 已把当前 baseline 明确降级为 `AKE-M`，不能称为原文 `AKE-A`；gate 脚本能输出 `AKE_status=PARTIAL`。 | 若要主张优于原文，必须实现/复现可信 `AKE-A`；否则论文中只能写 AKE-style mechanism surrogate。 |
| B4 增加非 Koopman baseline | 部分完成/降级 | 已在 runner 中加入 `zoh_consensus_surrogate`，gate 识别为 `NonKoopman_baseline=PARTIAL`。 | 该 baseline 只是低阶 surrogate，不能替代可信 physical-model DMPC；若要顶刊级说服力仍需真实非 Koopman 网络控制基线。 |
| B5 写 fairness gate | 部分完成 | `derive_publication_gate_tables.py` 已输出 T1 gate、group count、method provenance、success rate。 | 还缺严格训练 split hash、外部 trace 文件账本和原文 baseline 复现合同。 |

## C. 方法与理论闭环

| 子任务 | 当前状态 | 已有产物/证据 | 剩余动作 |
|---|---|---|---|
| C1 统一坐标系与符号 | 部分完成 | 之前已多次修正文稿方法/公式方向，Round2 也形成符号硬门禁。 | 需重新检查最新中文 DOCX 中符号表、角点编号、模式表是否一致。 |
| C2 重写车辆-载荷模型 | 部分完成 | 已有建模写作要求和连接/载荷受力指标；E7 runner 可导出 force/connection 指标。 | 需要把代码层指标和中文稿公式逐项对齐。 |
| C3 重写通信模型 | 部分完成 | 已确定 delay/dropout/burst/jitter/topology/link quality/timestamp 是 DCN 主线。 | 当前 runner 未完成 dose-response/topology grid；通信模型公式还需最终稿集成。 |
| C4 重写 Koopman 网络 | 部分完成 | 中文稿此前按 tf14 做过方法修正；当前 readiness 中仍要求 fresh E1 验证。 | E1 fresh Koopman/AKE 多训练种子 runner 未完成。 |
| C5 重写 DCC-MPC | 部分完成 | 方法桥接草稿已要求写清 delay compensation、consensus weights、约束。 | 需在中文 DOCX 中核查是否已经完整、严谨落地。 |
| C6 桥接控制链到证明 | 部分完成 | Round2 已把证明主线改为局部增益/Lipschitz，不再把 `A_sigma/B_sigma` 直接等同全局闭环。 | 需要最终中文稿/英文稿里严格写出 `u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}`。 |
| C7 修正 Lyapunov 证明 | 部分完成 | 已有 TF14 Lyapunov 证明文本，并完成 claim 降级。 | 仍需最终公式 QA，确保证明假设与实际 runner/gate 一致。 |

## D. 实验与图表

| 子任务 | 当前状态 | 已有产物/证据 | 剩余动作 |
|---|---|---|---|
| D1 T1 主 baseline 实验 | 部分完成 | 当前 runner baseline 标成 `AKE-M`，gate 可识别。 | 未实现可信 `AKE-A`，不能写优于 uploaded baseline。 |
| D2 非 Koopman baseline | 部分完成/降级 | 已加入 `zoh_consensus_surrogate`，E0 smoke 可跑，失败会记录 `path_not_completed`。 | 仍缺可信 physical-model DMPC 或同等级网络控制 baseline。 |
| D3 主闭环统计 | 部分完成 | runner 支持 `--full-final-seeds`，批处理脚本已写好，E0 单种子全方法 smoke 已通过。 | n=20 正式批次未完成，不能作为论文主结论。 |
| D4 fresh Koopman 学习统计 | 未完成 | Round3/Round5 均确认 E1 不在当前 runner 中。 | 需要单独 DNN/Koopman 训练评估 runner，至少多训练 seed。 |
| D5 通信 dose-response | 未完成 | 已列为 DCN 主线必需。 | 需要新增 0/50/100/200 ms、0/5/10/20% dropout、jitter/burst grid。 |
| D6 stress-test 分离 | 部分完成 | 理论覆盖区间 vs stress-test 区间已在记录中明确。 | 需要最终图表和正文标注，不得把 400 ms/40% dropout 当理论覆盖。 |
| D7 安全诊断修复 | 部分完成 | runner 已导出 force/connection、`nan_class`、`constraint_violation_count`、`fallback_count`、`intervention_count`；gate 增加 success/exception 统计。 | 需跑 E7 n=20 并检查所有方法无未分类 NaN。 |
| D8 消融实验 | 部分完成 | E2 方法集已有：no bilinear、no stable projection、no online adapt、no comm-aware、no delay、no FDI/FTC 等。 | E2 n=20 未跑完，不能写最终消融结论。 |
| D9 正文图冻结 | 未完成 | 已有 8 张主图建议和若干 smoke 图。 | 必须等待 n=20、baseline/fresh E1/dose/topology 完成后再冻结正文图。 |

## E. 稿件集成与投稿

| 子任务 | 当前状态 | 已有产物/证据 | 剩余动作 |
|---|---|---|---|
| E1 中文稿集成 | 部分完成 | 之前已有多版中文稿和 TF14/Lyapunov 插入；当前 Round6/Round7 未继续改 DOCX。 | 需要基于最新 gate 状态再出一版“安全集成中文稿”。 |
| E2 DOCX 公式/图表 QA | 部分完成 | 之前做过公式图片/PDF 渲染检查。 | 新一版中文稿生成后必须重新 QA。 |
| E3 英文 LaTeX | 未完成 | 早期有 DCN LaTeX 初稿框架，但未按最终 TF14/gate 状态完成。 | 中文稿稳定后再迁移英文，不应机械翻译。 |
| E4 终审 | 未完成 | 已有多轮 top reviewer 风险清单。 | 等最终稿和最终数据后再做终审。 |
| E5 投稿包 | 未完成 | 暂无最终 cover letter/highlights/data availability。 | 需在英文稿定稿后完成。 |

## P0 工作完成情况

| P0 编号 | 工作 | 当前状态 | 结论 |
|---|---|---|---|
| P0-1 | 冻结 T1 baseline fairness | 部分完成 | `AKE-M` 已明确，`AKE-A` 未完成。 |
| P0-2 | 至少加入一个非 Koopman 网络控制基线 | 部分完成/降级 | 已有 ZOH surrogate，但不是可信正式 baseline。 |
| P0-3 | 完成 `n>=20` paired closed-loop 统计 | 未完成 | runner 和批处理已准备，正式结果未跑完。 |
| P0-4 | 完成 fresh Koopman/AKE 多训练种子 | 未完成 | E1 runner 缺失。 |
| P0-5 | 修复安全诊断 NaN 和 intervention log | 部分完成 | schema 和字段已补，E7 n=20 no-NaN gate 未完成。 |
| P0-6 | 方法-证明闭环桥接 | 部分完成 | 草稿和边界已完成，最终稿待集成/QA。 |
| P0-7 | 补真实近三年文献 | 未完成 | citation records 仍 pending。 |

## P1 工作完成情况

| P1 编号 | 工作 | 当前状态 | 结论 |
|---|---|---|---|
| P1-1 | topology recovery sweep | 未完成 | runner 未实现恢复拓扑 grid。 |
| P1-2 | online adaptation on/off paired ablation | 部分完成 | E2 有 no online adapt 方法，但 n=20 paired 未完成。 |
| P1-3 | dwell-time/switching stress sweep | 未完成 | 仅有证明边界和证书 smoke，未形成 sweep。 |
| P1-4 | payload mass / friction OOD | 未完成 | 未见正式 OOD 统计。 |
| P1-5 | runtime/message-size overhead | 部分完成 | runner 有 step/solve time；message size/packet rate 未补。 |

## P2 工作完成情况

| P2 编号 | 工作 | 当前状态 | 结论 |
|---|---|---|---|
| P2-1 | 4/6/8 车规模扩展 | 未完成 | 当前主线仍是四车协同运输。 |
| P2-2 | 更真实 burst loss / correlated jitter | 未完成 | 尚未实现系统 sweep。 |
| P2-3 | 作者公开稿/机构库全文归档 | 部分完成 | 做过合法来源路线，但 citation record 未完成。 |

## 当前总体判断

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 论文主线和 claim 边界 | 70% | 方向清楚，但还需集成进最终中文稿。 |
| 方法/证明框架 | 60% | 证明边界正确，但最终公式和代码指标仍需 QA。 |
| 实验 runner 工程能力 | 70% | 隔离输出、provenance、异常续跑、ZOH surrogate、gate 表已补。 |
| 投稿级数据证据 | 25% | 仍缺 n=20、AKE-A/fair baseline、fresh E1、dose/topology。 |
| 文献证据 | 25% | 文献类别清楚，但 final-ready citation records 未完成。 |
| 稿件投稿包 | 30% | 中文稿有基础，但未按最终 gate 状态重集成；英文稿/投稿包未完成。 |

## 下一步最应该做的 5 件事

1. 决定是否投入实现可信 `AKE-A`；如果不做，论文中所有 baseline claim 固定降级为 `AKE-M`。
2. 决定是否实现正式 physical-model DMPC；如果不做，只能把 ZOH surrogate 放在 supplement 或弱底线对照。
3. 启动 `run_publication_final_batches.ps1` 跑 E0/E2/E3/E7 的 n=20，并用 gate 表检查 success rate、NaN、exception。
4. 单独补 E1 fresh Koopman/AKE 多训练 seed runner。
5. 建立最终 citation record CSV，再回填中文稿。
