# TF14 剩余实验记录

- 生成时间：2026-05-11T19:29:04
- 来源实验方案：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\tf14_remaining_experiments_figures_plan_zh_2026-05-09.docx`
- 当前 run 行数：40
- 已包含实验：`E0`
- 是否达到正式 n>=20：`False`
- 数据目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e0_nominal_fault_shard_2026_2030\data`
- 图片目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\e0_nominal_fault_shard_2026_2030\figures`
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
| E0 | sine_nominal_clean | baseline | 5 | 0.0499 | 0.5153 | 1.000 | 0.1551 | 0.331 | -1.386e-02 |
| E0 | sine_nominal_clean | tf14_main | 5 | 0.0459 | 0.4827 | 1.000 | 0.1319 | 0.361 | -2.238e-02 |
| E0 | sine_nominal_clean | tf14_phase_role | 5 | 0.0467 | 0.4829 | 1.000 | 0.1419 | 0.360 | -2.244e-02 |
| E0 | sine_nominal_clean | zoh_consensus_surrogate | 5 | 0.1628 | 14.3886 | 0.000 | 0.1508 | 0.177 | -2.314e+00 |
| E0 | sine_single_fault_v2 | baseline | 5 | 0.0449 | 0.4868 | 1.000 | 0.0711 | 0.360 | -1.536e-02 |
| E0 | sine_single_fault_v2 | tf14_main | 5 | 0.0443 | 0.4777 | 1.000 | 0.0794 | 0.799 | -1.112e-02 |
| E0 | sine_single_fault_v2 | tf14_phase_role | 5 | 0.0442 | 0.4778 | 1.000 | 0.0746 | 0.799 | -1.111e-02 |
| E0 | sine_single_fault_v2 | zoh_consensus_surrogate | 5 | 0.1003 | 14.0095 | 0.000 | 0.1002 | 0.177 | -1.872e+00 |
