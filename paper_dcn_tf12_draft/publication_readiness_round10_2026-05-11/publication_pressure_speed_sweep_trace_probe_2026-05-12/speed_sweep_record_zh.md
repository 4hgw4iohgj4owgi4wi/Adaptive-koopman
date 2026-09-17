# 同一压力场景不同速度对比记录

## 实验设置

- 场景族：`sine_publication_mixed_pressure`。
- 变量：只改变参考速度上限 `sine_speed_cap/dlc_speed_cap`，路径形状、通信退化、故障注入参数保持一致。
- 速度档：8.3 m/s。
- 方法：Baseline Koopman-MPC。

## 汇总结果

| 速度(m/s) | 方法 | n | 成功率 | 横向RMSE(m) | 纵向RMSE(m) | 证书通过率 | 连接利用率 | 载荷力RMS(N) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 8.3 | Baseline Koopman-MPC | 1 | 1.000 | 0.0510 | 1.5460 | 0.070 | 0.294 | 1070.66 |

## 写作边界

- 第一段客观描述：按速度从低到高报告成功率、横向/纵向误差、安全证书和连接利用率的变化。
- 第二段机理分析：速度提高会放大曲率段横摆率需求与通信延迟造成的预测错位，本文方法依赖通信质量一致性、时延补偿、PPC/进度保护和证书监测维持安全裕度；若某个速度档未全面优于 baseline，只能写成速度敏感性边界，不能写成全速度绝对优势。

## 输出

- `data/speed_sweep_runs.csv`：逐种子原始结果。
- `data/speed_sweep_summary.csv`：按速度和方法聚合结果。
- `figures/speed_sweep_metric_summary.png`：速度敏感性汇总图。
