# Round6 收口记录

- 时间：2026-05-11
- 目标：收口前几轮发现的“实验执行、证据记录、审稿可追溯字段”缺口。
- 变更文件：
  - `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`
  - `paper_dcn_tf12_draft/publication_readiness_round5_2026-05-11/derive_publication_gate_tables.py`
  - `paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/run_publication_final_batches.ps1`
  - `paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/round6_closure_record.md`

## 已完成内容

- 给 TF14 剩余实验 runner 增加 `--output-root`，正式实验和 smoke 实验可以输出到隔离证据目录，不再需要复制整套实验包，也避免污染原始结果目录。
- 增加 `--methods`，支持只跑指定方法，便于单独验证某个对照算法或某个模块是否出问题。
- 增加 `--include-zoh-surrogate` 和 `zoh_consensus_surrogate`，作为低阶非 Koopman 辅助底线对照。该方法已明确标记为 `nonkoopman_low_order_surrogate`，不能在论文中写成严格的物理模型 DMPC baseline。
- 给 `tf14_remaining_runs.csv` 增加审稿可追溯字段：`method_id`、`baseline_class`、`publication_role`、`ake_status`、方法/工况配置哈希、确定性的 `comm_trace_id`、`fault_trace_id`、`topology_trace_id`、`trace_id_status`、`success`、`failure_type`、`nan_class`、`constraint_violation_count`、`fallback_count`、`intervention_count`、`connection_util_max`。
- 将 JSON 写出改为严格 JSON：非有限数值写成 `null`，不再写 Python 风格的 `NaN`。
- 更新 gate 派生脚本，使其优先读取 runner 原生 provenance 字段；识别 ZOH surrogate 并标成 `PARTIAL`；对确定性 trace id 标成 `PARTIAL`，不再用 `PENDING_*` 覆盖已有字段。

## 验证结果

- 语法检查已通过：
  - `E:\anaconda\envs\pytorch_new\python.exe -m py_compile .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py`
  - `E:\anaconda\envs\pytorch_new\python.exe -m py_compile .\paper_dcn_tf12_draft\publication_readiness_round5_2026-05-11\derive_publication_gate_tables.py`
- CLI 检查已通过：
  - `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --help`
- ZOH surrogate 单方法 smoke：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/isolated_zoh_smoke`
  - 命令：`--experiments E0 --seeds 2026 --scenarios sine_nominal_clean --methods zoh_consensus_surrogate --include-zoh-surrogate --output-root ... --force`
  - 结果：runner 完成；manifest 为严格 JSON；CSV 行包含 provenance 字段；`failure_type=path_not_completed`、`success=0`，符合弱底线 surrogate 在该工况下不能完整跟踪的预期。
- TF14 证书 smoke：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/isolated_tf14_e3_smoke`
  - 命令：`--experiments E3 --seeds 2026 --scenarios sine_mixed_fault_noise --methods tf14_phase_role --output-root ... --force`
  - 结果：runner 完成；`method_id=TF14-FULL`、`success=1`、`failure_type=none`、`nan_class=none`、`certificate_ok_ratio=1.0`、`certificate_min_margin=0.0036639140140306004`。
- Gate 检查：
  - ZOH smoke：`NonKoopman_baseline=PARTIAL`、`trace_ids=PARTIAL`、`paired_n20=FAIL`。
  - TF14 E3 smoke：`trace_ids=PARTIAL`、`paired_n20=FAIL`。
- E0 全方法单种子 smoke：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/isolated_e0_allmethods_smoke`
  - 命令：`--experiments E0 --seeds 2026 --scenarios sine_nominal_clean --include-zoh-surrogate --output-root ... --force`
  - 结果：5 个方法均完成并重新生成 R0 图。单种子结果为：`baseline/AKE-M success=1`，`zoh_consensus_surrogate success=0 path_not_completed`，`tf14_main success=1`，`tf14_phase_role success=1`，`tf14_error_match success=1`。
  - Gate：`AKE_status=PARTIAL`、`NonKoopman_baseline=PARTIAL`、`trace_ids=PARTIAL`、`paired_n20=FAIL`。

## 仍未闭合的发表风险

- 上传原文 baseline 仍没有被严格复现为 `AKE-A`；当前 runner 中的 baseline 仍是 `AKE-M`/机制 surrogate。若论文主张“超过原文方法”，还需要实现或复现可信的原文 baseline。
- ZOH baseline 只是低阶 surrogate。它可以用于说明“去掉 Koopman/通信/自适应能力后的底线效果”，但不能替代严格物理模型 DMPC 或其它正式非 Koopman 对照算法。
- `trace_id_status` 目前来自实验编号、工况、seed 的确定性生成，能保证可复现索引，但不是外部通信/故障/拓扑原始 trace 文件账本。
- 正式统计仍未完成；必须跑完 E0/E2/E3/E7 的 n=20 配对 seed 才能作为论文主证据。
- E1 Koopman DNN 预测实验不在当前 runner 中。如果正文继续声称神经 Koopman 预测精度，需要单独补 DNN 训练/测试脚本。

## 正式证据生成命令

机器可以长时间运行时执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\run_publication_final_batches.ps1
```

该脚本可断点续跑：已有 run ID 默认会跳过；若要强制重跑，需要在 runner 命令中额外加 `--force`。
