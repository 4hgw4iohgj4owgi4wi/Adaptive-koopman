# TF14 剩余实验记录

- 生成时间：2026-05-11T09:42:22
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：15
- 已包含实验：`E2, E7`
- 是否达到正式 n>=20：`False`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\smoke_matrix\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\smoke_matrix\figures`
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
| E2 | sine_mixed_fault_noise | full_tf14 | 1 | 0.0406 | 0.4674 | 1.000 | 0.0351 | 1.000 | 3.664e-03 |
| E2 | sine_mixed_fault_noise | no_bilinear | 1 | 0.0388 | 0.4671 | 1.000 | 0.0332 | 1.000 | 3.687e-03 |
| E2 | sine_mixed_fault_noise | no_comm_aware | 1 | 0.0409 | 0.4944 | 1.000 | 0.0343 | 0.795 | -1.128e-02 |
| E2 | sine_mixed_fault_noise | no_delay_compensation | 1 | 0.0407 | 0.4674 | 1.000 | 0.0367 | 1.000 | 3.664e-03 |
| E2 | sine_mixed_fault_noise | no_fdi | 1 | 0.0393 | 0.4559 | 1.000 | 0.0349 | 1.000 | 3.664e-03 |
| E2 | sine_mixed_fault_noise | no_ftc_switching | 1 | 0.0391 | 0.4565 | 1.000 | 0.0358 | 1.000 | 3.664e-03 |
| E2 | sine_mixed_fault_noise | no_online_adapt | 1 | 0.0406 | 0.4673 | 1.000 | 0.0352 | 1.000 | 3.664e-03 |
| E2 | sine_mixed_fault_noise | no_phase_role | 1 | 0.0412 | 0.4675 | 1.000 | 0.0356 | 1.000 | 3.665e-03 |
| E2 | sine_mixed_fault_noise | zoh_consensus_surrogate | 1 | 0.0775 | 14.0462 | 0.000 | 0.0409 | 0.177 | -1.912e+00 |
| E7 | sine_mixed_fault_noise | baseline | 1 | 0.0450 | 0.4707 | 1.000 | 0.0341 | 0.361 | -1.930e-02 |
| E7 | sine_mixed_fault_noise | no_comm_aware | 1 | 0.0408 | 0.4941 | 1.000 | 0.0360 | 0.795 | -1.123e-02 |
| E7 | sine_mixed_fault_noise | no_ftc_switching | 1 | 0.0389 | 0.4560 | 1.000 | 0.0339 | 1.000 | 3.664e-03 |
| E7 | sine_mixed_fault_noise | tf14_main | 1 | 0.0407 | 0.4673 | 1.000 | 0.0341 | 1.000 | 3.670e-03 |
| E7 | sine_mixed_fault_noise | tf14_phase_role | 1 | 0.0400 | 0.4677 | 1.000 | 0.0346 | 1.000 | 3.682e-03 |
| E7 | sine_mixed_fault_noise | zoh_consensus_surrogate | 1 | 0.0746 | 14.0411 | 0.000 | 0.0392 | 0.177 | -1.909e+00 |
