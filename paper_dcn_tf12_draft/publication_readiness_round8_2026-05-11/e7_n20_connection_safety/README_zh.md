# TF14 剩余实验记录

- 生成时间：2026-05-11T13:31:31
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：240
- 已包含实验：`E7`
- 是否达到正式 n>=20：`True`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\e7_n20_connection_safety\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round8_2026-05-11\e7_n20_connection_safety\figures`
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
| E7 | sine_comm_noise_high | baseline | 20 | 0.0503 | 0.4966 | 1.000 | 0.0344 | 0.361 | -1.574e-02 |
| E7 | sine_comm_noise_high | no_comm_aware | 20 | 0.0440 | 0.5296 | 1.000 | 0.0355 | 0.343 | -1.229e-02 |
| E7 | sine_comm_noise_high | no_ftc_switching | 20 | 0.0416 | 0.4708 | 1.000 | 0.0359 | 1.000 | 4.880e-03 |
| E7 | sine_comm_noise_high | tf14_main | 20 | 0.0415 | 0.4708 | 1.000 | 0.0369 | 1.000 | 4.882e-03 |
| E7 | sine_comm_noise_high | tf14_phase_role | 20 | 0.0416 | 0.4708 | 1.000 | 0.0365 | 1.000 | 4.881e-03 |
| E7 | sine_comm_noise_high | zoh_consensus_surrogate | 20 | 0.0808 | 14.3019 | 0.000 | 0.0411 | 0.177 | -2.225e+00 |
| E7 | sine_mixed_fault_noise | baseline | 20 | 0.0453 | 0.4719 | 1.000 | 0.0355 | 0.362 | -1.887e-02 |
| E7 | sine_mixed_fault_noise | no_comm_aware | 20 | 0.0414 | 0.4960 | 1.000 | 0.0367 | 0.793 | -1.132e-02 |
| E7 | sine_mixed_fault_noise | no_ftc_switching | 20 | 0.0392 | 0.4566 | 1.000 | 0.0376 | 1.000 | 3.302e-03 |
| E7 | sine_mixed_fault_noise | tf14_main | 20 | 0.0412 | 0.4681 | 1.000 | 0.0368 | 1.000 | 3.302e-03 |
| E7 | sine_mixed_fault_noise | tf14_phase_role | 20 | 0.0407 | 0.4680 | 1.000 | 0.0370 | 1.000 | 3.301e-03 |
| E7 | sine_mixed_fault_noise | zoh_consensus_surrogate | 20 | 0.0896 | 14.0488 | 0.000 | 0.0424 | 0.177 | -1.909e+00 |
