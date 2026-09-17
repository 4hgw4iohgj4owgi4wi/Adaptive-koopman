# TF14 剩余实验记录

- 生成时间：2026-05-11T16:22:54
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：72
- 已包含实验：`E2`
- 是否达到正式 n>=20：`False`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_shard_2027_2032\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_shard_2027_2032\figures`
- 推荐 Python 环境：`E:\anaconda\envs\pytorch_new\python.exe`。

## P0 状态

- 除非使用 `--full-final-seeds` 生成，否则当前行可能只是 smoke 或部分数据，不能作为最终 n=20 统计引用。
- 默认每个 run 使用隔离 notebook 命名空间；`--reuse-env` 仅用于快速调试。
- E0 多 seed 主对比已在本 runner 中实现；正式统计使用 `--experiments E0 --full-final-seeds`。
- E1 Koopman DNN 多 seed 预测仍需要单独的 DNN 训练/评估 runner。
- E2 模块消融已实现；正式统计使用 `--experiments E2 --full-final-seeds`。
- E3 证书验证已基于当前证书记录器实现；论文中的实践稳定性/ISS 表达仍需与理论段落保持一致。
- E7 同扰动货物受力与连接安全已实现；记录字段包括受力峰值/RMS、受力变化率、连接利用率/违规次数和角点载荷差。
- 正式长批次建议启用 `--continue-on-error --retry-exceptions`，保证单个异常 case 有记录且不会中断整批。

## 聚合指标

| 实验 | 工况 | 方法 | n | RMSE_y | RMSE_s | 完整路径率 | 单步 p95 | 证书通过率 | 最小裕度 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| E2 | sine_mixed_fault_noise | full_tf14 | 6 | 0.0409 | 0.4681 | 1.000 | 0.0629 | 1.000 | 3.832e-03 |
| E2 | sine_mixed_fault_noise | no_bilinear | 6 | 0.0398 | 0.4681 | 1.000 | 0.0501 | 1.000 | 3.833e-03 |
| E2 | sine_mixed_fault_noise | no_comm_aware | 6 | 0.0414 | 0.5090 | 1.000 | 0.0561 | 0.787 | -1.155e-02 |
| E2 | sine_mixed_fault_noise | no_delay_compensation | 6 | 0.0412 | 0.4681 | 1.000 | 0.0565 | 1.000 | 3.822e-03 |
| E2 | sine_mixed_fault_noise | no_fdi | 6 | 0.0403 | 0.4565 | 1.000 | 0.0568 | 1.000 | 3.826e-03 |
| E2 | sine_mixed_fault_noise | no_ftc_switching | 6 | 0.0406 | 0.4565 | 1.000 | 0.0565 | 1.000 | 3.828e-03 |
| E2 | sine_mixed_fault_noise | no_online_adapt | 6 | 0.0405 | 0.4679 | 1.000 | 0.0564 | 1.000 | 3.826e-03 |
| E2 | sine_mixed_fault_noise | no_phase_role | 6 | 0.0414 | 0.4682 | 1.000 | 0.0563 | 1.000 | 3.827e-03 |
| E2 | sine_mixed_fault_noise | no_ppc_progress_guard | 6 | 0.0672 | 12.9374 | 0.000 | 0.0475 | 0.287 | -3.516e+01 |
| E2 | sine_mixed_fault_noise | no_realtime_scheduler | 6 | 0.0389 | 0.4670 | 1.000 | 0.0971 | 1.000 | 3.813e-03 |
| E2 | sine_mixed_fault_noise | no_stable_projection | 6 | 0.0390 | 0.4679 | 1.000 | 0.0568 | 1.000 | 3.829e-03 |
| E2 | sine_mixed_fault_noise | zoh_consensus_surrogate | 6 | 0.0986 | 14.0225 | 0.000 | 0.0642 | 0.177 | -1.883e+00 |
