# TF14 剩余实验记录

- 生成时间：2026-05-11T17:50:45
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：20
- 已包含实验：`E0`
- 是否达到正式 n>=20：`False`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e0_comm_key_shard_2041_2045\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e0_comm_key_shard_2041_2045\figures`
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
| E0 | sine_comm_noise_high | baseline | 5 | 0.0511 | 0.5139 | 1.000 | 0.0677 | 0.335 | -1.492e-02 |
| E0 | sine_comm_noise_high | tf14_main | 5 | 0.0419 | 0.4705 | 1.000 | 0.0670 | 1.000 | 4.053e-03 |
| E0 | sine_comm_noise_high | tf14_phase_role | 5 | 0.0423 | 0.4706 | 1.000 | 0.0735 | 1.000 | 4.051e-03 |
| E0 | sine_comm_noise_high | zoh_consensus_surrogate | 5 | 0.1158 | 14.1719 | 0.000 | 0.0772 | 0.177 | -2.103e+00 |
