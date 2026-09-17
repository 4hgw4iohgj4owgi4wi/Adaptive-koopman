# TF14 剩余实验记录

- 生成时间：2026-05-11T16:31:52
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：84
- 已包含实验：`E2`
- 是否达到正式 n>=20：`False`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_shard_2039_2045\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e2_shard_2039_2045\figures`
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
| E2 | sine_mixed_fault_noise | full_tf14 | 7 | 0.0409 | 0.4677 | 1.000 | 0.0585 | 1.000 | 2.908e-03 |
| E2 | sine_mixed_fault_noise | no_bilinear | 7 | 0.0395 | 0.4674 | 1.000 | 0.0483 | 1.000 | 2.916e-03 |
| E2 | sine_mixed_fault_noise | no_comm_aware | 7 | 0.0413 | 0.5054 | 1.000 | 0.0538 | 0.784 | -1.152e-02 |
| E2 | sine_mixed_fault_noise | no_delay_compensation | 7 | 0.0409 | 0.4675 | 1.000 | 0.0541 | 1.000 | 2.905e-03 |
| E2 | sine_mixed_fault_noise | no_fdi | 7 | 0.0402 | 0.4561 | 1.000 | 0.0540 | 1.000 | 2.901e-03 |
| E2 | sine_mixed_fault_noise | no_ftc_switching | 7 | 0.0403 | 0.4564 | 1.000 | 0.0541 | 1.000 | 2.914e-03 |
| E2 | sine_mixed_fault_noise | no_online_adapt | 7 | 0.0411 | 0.4676 | 1.000 | 0.0536 | 1.000 | 2.908e-03 |
| E2 | sine_mixed_fault_noise | no_phase_role | 7 | 0.0414 | 0.4678 | 1.000 | 0.0534 | 1.000 | 2.910e-03 |
| E2 | sine_mixed_fault_noise | no_ppc_progress_guard | 7 | 0.0660 | 12.9195 | 0.000 | 0.0449 | 0.284 | -3.495e+01 |
| E2 | sine_mixed_fault_noise | no_realtime_scheduler | 7 | 0.0389 | 0.4666 | 1.000 | 0.0934 | 1.000 | 2.907e-03 |
| E2 | sine_mixed_fault_noise | no_stable_projection | 7 | 0.0387 | 0.4673 | 1.000 | 0.0542 | 1.000 | 2.915e-03 |
| E2 | sine_mixed_fault_noise | zoh_consensus_surrogate | 7 | 0.0964 | 14.0205 | 0.000 | 0.0612 | 0.177 | -1.881e+00 |
