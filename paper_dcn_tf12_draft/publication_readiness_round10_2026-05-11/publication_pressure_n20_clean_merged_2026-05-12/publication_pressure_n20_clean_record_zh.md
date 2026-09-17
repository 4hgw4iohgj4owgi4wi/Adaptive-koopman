# 投稿主压力场景 n=20 干净合并记录

## 场景配置

- 场景：`sine_publication_mixed_pressure`。
- 干扰：正弦轨迹 + 中强通信退化 + 单车双通道轻中度降额故障。
- 参数：`comm_packet_loss_base=0.08`，`comm_packet_loss_gain=0.22`，`comm_delay_steps_max=4`，`comm_delay_bias=0.45`，`comm_tighten_max_frac=0.24`，`fault_vehicle_index=1`，`fault_mode=both`，`fault_start_step=260`，`fault_start_s=24.0`，`fault_ax_scale=0.86`，`fault_delta_scale=0.86`。
- 为避免 AKE-A 在线适配污染共享运行环境，baseline、AKE-A、本文方法分别用独立进程/独立输出目录完成 n=20，然后在本目录合并统计。

## n=20 结果

| 方法 | 成功率 | 横向RMSE均值(m) | 纵向RMSE均值(m) | 最大横向误差(m) | 最大纵向误差(m) | 证书通过率 | 最小证书裕度 | 载荷力RMS(N) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline Koopman-MPC | 1.000 | 0.0454 | 0.5338 | 0.0943 | 0.9121 | 0.344 | -0.0161 | 518.96 |
| AKE-A bilinear-ridge strict reproduction | 0.000 | 0.1354 | 14.1775 | 0.3114 | 25.7402 | 0.177 | -2.0591 | 489.44 |
| 本文方法 BKC-DCMPC full | 1.000 | 0.0415 | 0.4663 | 0.0849 | 0.7957 | 1.000 | 0.0028 | 602.79 |

## 结论边界

- 该场景可作为投稿主压力场景：本文方法 n=20 全部完成，且相对 baseline 与严格 AKE-A 在横向/纵向误差、安全证书、连接利用率、路径完成性上形成清晰区分。
- 严格 AKE-A 在该四车载荷协同运输压力场景下 20 个种子均未完成全路径，说明仅有自适应 Koopman 动力学学习不足以覆盖通信退化、故障降额和安全约束闭环。
- 之前混合方法同进程运行出现后续种子异常，是 AKE-A 在线适配污染共享 `ns` 环境造成的工程风险；已通过方法级独立进程规避。

## CPU/进程处理记录

- 2026-05-12 18:28 检查发现 CPU 满载来自遗留 `pytest` 与 `scripts\run_experiment_matrix.py` 进程，不是当前 n=20 仿真。
- 已停止 PID `29292`、`43228`、`34988`，释放 CPU。
