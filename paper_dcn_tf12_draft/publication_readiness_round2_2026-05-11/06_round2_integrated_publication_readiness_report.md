# Round 2 主 Agent 整合报告：Publication Readiness

## 1. 本轮完成状态

Round 2 已完成 worker、reviewer、返工和主 Agent 文件级验证。所有产物位于：

`paper_dcn_tf12_draft/publication_readiness_round2_2026-05-11`

本轮未修改中文 DOCX、LaTeX、实验代码或图文件夹。

| 文件 | 状态 | 作用 |
|---|---|---|
| `00_round2_task_tree.md` | ready | 第二轮任务边界。 |
| `01_T1_baseline_fairness_contract.md` | revised-ready | T1 baseline 公平性合同，已把 `AKE-A` 降为 candidate state。 |
| `02_recent_literature_evidence_matrix.md` | revised-ready but citation-pending | 文献矩阵，已标注 `V3/V2/V1` 核验等级；当前 `V3 final-ready = 0`。 |
| `03_method_proof_bridge_draft_zh.md` | revised-ready for manuscript draft | 方法-证明桥接中文草稿，已改为局部增益界/Lipschitz 主线。 |
| `04_experiment_execution_readiness_audit.md` | revised-ready for execution planning | 实验执行审计，已补 seed、CSV schema、NaN gate、dose/topology grid 和 final gate checklist。 |
| `05_chinese_manuscript_integration_patch_plan.md` | revised-ready | 中文稿集成计划，已加入 `ready/pending/representative/stress-test` 状态门槛。 |

## 2. Reviewer 返工已解决的问题

| Reviewer 问题 | 返工处理 |
|---|---|
| `AKE-A` 不应直接作为推荐主 baseline | 改为 `candidate baseline state`；只有 AKE 架构、online `Delta A/Delta B`、MPC coupling、同数据同约束等全部核验后才可作为主 baseline；否则降级为 `AKE-M`。 |
| T1 缺因果信息边界 | 增加禁止未来 dropout/delay/topology、未来 leader-loss、oracle recovery、clean privileged measurements 的 gate。 |
| 非 Koopman baseline 过弱 | 明确 `ZOH consensus MPC` 只是最低 surrogate；无 Physical-model DMPC 或同等级 networked-control baseline 时，不能泛化为“优于网络控制方法”。 |
| 文献矩阵缺 DOI/BibTeX/access date | 改为 `V3/V2/V1` 分级；没有完整 citation record 的条目不得作为终稿支撑。 |
| timestamped/out-of-order 文献不足 | 标为 P0 direct-evidence gap；未补直接文献前，不能把 timestamp/out-of-order/buffered prediction 写成强 novelty。 |
| `A_sigma/B_sigma` 仍像全局线性闭环 | 改为局部增益界/Lipschitz 不等式主线；`A_sigma/B_sigma` 仅作为 fixed active set/local linearization 下的辅助对象。 |
| 稳定性结论过强 | 删除 ISS-practical 等价 UUB 和 `C lambda^k` 主结论；改为 conditional practical boundedness / UUB。 |
| 理论区间与 stress-test 混淆 | 增加理论覆盖区间 vs stress-test 区间表：`0--200 ms/0--20% dropout/recoverable topology` 为主声明候选，`400 ms/40% dropout/leader-lost` 仅 stress-test。 |
| 实验计划不够可执行 | 补主闭环 seeds `2026--2045`、fresh E1 训练种子、CSV schema、failure rules、NaN 分类、one-page final gate checklist。 |

## 3. 当前可以立即集成进中文稿的内容

以下内容可以进入中文稿，但仍需标注状态，不能写成实验已完成结论：

| 内容 | 可写入位置 | 证据状态 |
|---|---|---|
| DCN 网络问题驱动叙事 | 摘要、引言、贡献段 | ready |
| T1 baseline fairness contract | 实验设置或附录 | pending until baseline is implemented/frozen |
| `AKE-A` candidate / `AKE-M` downgrade 规则 | 实验设置、对比表说明 | ready |
| 方法-证明桥接段 | 方法末尾、Lyapunov 证明前 | ready |
| 符号硬门禁表 | 方法或附录 | ready |
| 过强 claim 替换表 | 内部写作约束或附录 | ready |
| 实验 final gate checklist | 实验设置前或内部任务表 | pending execution |

## 4. 当前不能写成主文结论的内容

| 不能写的结论 | 原因 | 替代表述 |
|---|---|---|
| 本文显著优于 uploaded AKE baseline | T1 baseline 尚未冻结到 runner，`AKE-A` 仍是 candidate | 本文建立了对 AKE-style baseline 的公平比较合同，最终数值结论等待 T1 final runs。 |
| 本文优于网络控制方法 | 非 Koopman baseline 尚未达到 Physical-model DMPC 或同等级 networked-control baseline | 可写为“相对最低 surrogate 或消融对照的代表性结果”。 |
| `n>=20` 统计显著改善 | 当前 remaining/gap 仍含 smoke/cached 证据 | 只能写 representative evidence 或 planned final statistical validation。 |
| timestamped/out-of-order neighbor prediction 是强 novelty | 直接文献仍不足 | 可写为本文实现机制；强 novelty 需补直接 V3/V2 文献。 |
| 任意通信故障稳定 | 理论只覆盖 bounded degradation 和可恢复拓扑 | 写 conditional practical boundedness / UUB under specified assumptions。 |
| 安全性能已最终验证 | T5 final no-NaN、violation/fallback/intervention log 尚未 final | 写 safety diagnostics gate and required final export。 |

## 5. 下一步 P0 工作

| P0 | 工作 | 目标产物 |
|---|---|---|
| P0-1 | 冻结 T1 baseline 到 runner | `T1_baseline_fairness.csv/md`，明确 AKE-A 是否可成立，否则降级 AKE-M。 |
| P0-2 | 实现或启用 credible non-Koopman baseline | Physical-model DMPC 优先；若做不到，ZOH consensus MPC 只能作 surrogate。 |
| P0-3 | 跑主闭环 `n>=20` paired seeds | `T2_main_closed_loop.csv`，seeds `2026--2045`。 |
| P0-4 | 跑 E1 fresh Koopman/AKE 多训练种子 | `T1/T2` 中 prediction/rollout 统计；当前 cached 图不能支撑主结论。 |
| P0-5 | 修复并跑 T5 safety diagnostics | 无未分类 NaN；完整 violation、fallback/intervention、constraint activity。 |
| P0-6 | 增加 communication dose-response 和 topology recovery | `0/50/100/200 ms`、`0/5/10/20% dropout`、recoverable topology；stress-test 分离。 |
| P0-7 | 补 citation record | 每条文献补 title、authors、year、venue、DOI、URL、source type、peer-review status、access date、used sentence、gap sentence。 |

## 6. Round 3 推荐目标

Round 3 不再继续写“泛化计划”，而应推进可执行落地：

1. 审计 runner 是否能加入 T1 method set 和 non-Koopman baseline。
2. 生成 baseline/method-set 配置文件或至少生成准确的待实现 patch plan。
3. 开始逐条核验 citation records，优先补 DCN-native 和 timestamped/out-of-order 直接文献。
4. 若可行，先运行一个小规模 final-gate dry run，验证 CSV schema 和 NaN gate。
5. 生成下一版中文稿的“安全集成版”，只写 ready/pending 状态，不伪装成最终证据。

## 7. 主 Agent 验证

已验证以下关键词或门槛存在于返工后的文件：

- `candidate baseline state`
- `downgrade`
- `future dropout`
- `oracle`
- `ZOH consensus MPC`
- `V3 final-ready = 0`
- `citation record`
- `timestamped/out-of-order`
- `Lipschitz`
- `局部增益`
- `fixed active set`
- `stress-test`
- `2026-2045`
- `CSV schema`
- `NaN`
- `one-page final gate`

结论：Round 2 已达到“投稿 P0 门槛清楚、不能误写的边界清楚、下一步执行入口清楚”的状态；但还没有达到“可以投稿”的状态。主要阻塞仍是 T1 baseline、non-Koopman baseline、n>=20/fresh seeds、T5 no-NaN、citation records。
