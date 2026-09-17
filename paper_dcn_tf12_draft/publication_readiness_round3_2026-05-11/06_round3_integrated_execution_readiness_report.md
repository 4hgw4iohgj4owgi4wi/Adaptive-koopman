# Round 3 主 Agent 整合报告：Execution Readiness

## 1. 本轮结论

Round 3 已从“投稿 P0 计划”推进到“本地执行能力审计”。结论比较明确：

当前已有 runner 可以跑 `E0/E2/E3/E7` 的 TF14 remaining experiments，并支持 `--full-final-seeds` 生成 `2026--2045` 的 final seeds；但是投稿级 P0 仍未满足，因为 runner 目前缺少：

- verified `AKE-A` baseline；
- credible non-Koopman network-control baseline；
- fresh E1 Koopman/AKE multi-training-seed runner；
- communication dose-response grid；
- topology recovery grid；
- Round2 所需完整 provenance / trace ID / no-NaN schema。

因此，当前中文稿可以安全集成“方法桥接、T1 规则、claim 降级、pending gate”，但不能写 baseline superiority、统计显著改善或最终安全结论。

## 2. Round 3 产物

| 文件 | 状态 | 关键结论 |
|---|---|---|
| `01_runner_capability_audit.md` | ready | runner 支持 `E0/E2/E3/E7`、`--seeds`、`--full-final-seeds`、`--quick`；不支持 E1、non-Koopman、dose/topology grid。 |
| `02_T1_baseline_implementation_decision.md` | ready | 当前本地 baseline 必须降级为 `AKE-M`；不能称为 `AKE-A`。 |
| `03_citation_record_verification_queue.md` | ready | 建立 P0 citation queue；未核验前不能把 timestamp/out-of-order 等写成强 novelty。 |
| `04_dryrun_csv_schema_execution_plan.md` | ready | 给出 help/smoke/final 命令、CSV schema validation、no-NaN gate；final 命令只列出，不执行。 |
| `05_safe_chinese_integration_draft_scope.md` | ready | 列出可立即集成与必须 pending 的中文稿范围；未修改 DOCX。 |

## 3. 主 Agent 实际验证

已运行安全命令，不启动实验：

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --help
```

验证结果：

- CLI 可用。
- 支持 experiments：`E0 E2 E3 E7`。
- `E1 needs the DNN runner`，当前 runner 不支持 E1。
- 支持 `--seeds`。
- 支持 `--full-final-seeds`，即 final `n=20` seeds `2026-2045`。
- 支持 `--scenarios`。
- 支持 `--quick` smoke。
- 支持 `--force` 和 `--reuse-env`。

## 4. 当前 Baseline 状态

当前只能写：

> The current AKE-facing comparator is treated as an AKE-style mechanism comparator (`AKE-M`) rather than a verified task-adapted reproduction (`AKE-A`).

不能写：

- “本文优于 uploaded AKE baseline”；
- “本文优于 task-adapted AKE baseline”；
- “baseline 严格复现了原论文 AKE 方法”。

升级到 `AKE-A` 需要：

1. 实现 dedicated `Frozen_AKE` method row。
2. 明确 AKE embedding 架构与 baseline 论文机制一致或合理任务适配。
3. 明确 online `Delta A/Delta B` 机制。
4. 与 proposed 使用同训练数据、同 horizon、同 solver、同采样周期、同约束、同通信 trace、同 seeds。
5. 输出 `ake_status`、config hash、training split hash、trace ID 和 method provenance。

## 5. 当前 Runner 能跑什么

可直接运行，但不是投稿最终充分证据：

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --quick
```

用途：smoke check runner 是否可执行。不能作为论文结论。

当前 final 命令已经存在，但仍被 P0 gate 阻断：

```powershell
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E2 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E3 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E7 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise
```

阻断原因：

- method set 缺 verified `AKE-A`；
- method set 缺 credible non-Koopman baseline；
- CSV schema 缺 `comm_trace_id/fault_trace_id/topology_trace_id`；
- safety T5 仍需要 final no-NaN gate；
- E1 fresh seeds 不在该 runner 中。

## 6. 中文稿可安全集成范围

现在可以集成进中文稿：

- 网络退化驱动的 DCN 叙事；
- `AKE-M` 当前 baseline 降级说明；
- T1 fairness gate；
- 方法-证明桥接；
- `A_sigma/B_sigma` 来源修正；
- 局部增益界/Lipschitz 稳定性证明边界；
- 理论覆盖区间 vs stress-test 区间表；
- evidence status 字段；
- 过强 claim 替换。

必须 pending：

- baseline superiority；
- non-Koopman baseline superiority；
- `n>=20` 统计改善；
- dose-response/topology final conclusions；
- T5 safety final conclusions；
- citation-supported novelty claims，尤其 timestamped/out-of-order/buffered prediction。

## 7. 下一轮最有价值任务

为了继续向“可发表”推进，Round 4 应该开始做实际代码/配置层面的 P0 修复，而不是继续只写计划：

1. 创建 T1 method/provenance ledger 草案。
2. 在 runner 外层生成派生 CSV schema validator，不改核心实验逻辑也可以先检查已有 CSV。
3. 运行 `--quick` smoke，确认 runner 在当前环境能完成一次短跑。
4. 设计或实现最低 non-Koopman baseline。如果只能做 `ZOH consensus MPC`，明确它是 surrogate。
5. 建立 citation record CSV，先从本地 `recent_lit_support_2026-05-07` 已有 PDF/提取文本中补 V2/V3 记录。
6. 生成中文稿 safety-integration 版本，只插入 ready/pending 门槛，不插入未完成实验结论。

## 8. 风险

| 风险 | 当前判断 | 处理 |
|---|---|---|
| 继续跑 final seeds 但 method set 不合格 | 会得到更多数据，但仍不能投稿 | 先补 T1/non-Koopman/provenance。 |
| 把 `baseline` 当 AKE-A | 当前不成立 | 统一降级为 `AKE-M`。 |
| E1 cached 图被当主证据 | 不成立 | 必须单独 fresh DNN runner。 |
| 通信 dose/topology 未实现 | DCN 主线证据不足 | 需新增 runner 或扩展 scenario grid。 |
| 文献仍是候选 | 不能写强 related-work claim | 补 citation record。 |
| 中文稿过早集成实验结论 | 容易误导后续写作 | 使用 `evidence_status` gate。 |

## 9. 主 Agent 结论

Round 3 把关键事实确认清楚了：当前项目已经有较完整的 TF14 实验骨架和图层，但距离可发表还差的是“公平 baseline + 独立强 baseline + final statistics + fresh learning seeds + citation records”。下一步应进入小规模执行和 schema 验证，而不是继续扩写论文。
