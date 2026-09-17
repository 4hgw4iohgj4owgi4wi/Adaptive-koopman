# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3786 | 0.2521 | 8.4712 | 14.2824 | 0.4704 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 8.3573 | 0.2988 | 8.8555 | 16.8944 | 0.6814 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6005 | 0.9878 | 8.3335 | 8.2475 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5940 | 0.9841 | 8.5070 | 9.0634 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2035 | 0.4960 | 8.2199 | 8.3037 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2246 | 0.5328 | 8.4548 | 8.3018 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6638 | 1.0790 | 8.2618 | 8.7186 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6388 | 1.0376 | 8.5155 | 8.9388 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2092 | 0.4339 | 8.2003 | 8.9175 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2293 | 0.4594 | 8.4535 | 8.8495 |

## 提取警告

- 无。
