# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.3546 | 0.2408 | 8.6799 | 16.6287 | 0.4852 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 4.7397 | 0.2082 | 7.5950 | 8.5898 | 0.5067 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5945 | 1.0363 | 9.2861 | 8.3677 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5877 | 1.0280 | 9.4970 | 9.2538 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2198 | 0.4979 | 9.1957 | 8.6025 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2439 | 0.5347 | 9.4409 | 8.5234 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5115 | 1.0300 | 4.6713 | 7.5059 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4925 | 0.9884 | 4.8553 | 7.7090 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2187 | 0.4448 | 4.6206 | 7.6085 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2382 | 0.4838 | 4.8152 | 7.5586 |

## 提取警告

- 无。
