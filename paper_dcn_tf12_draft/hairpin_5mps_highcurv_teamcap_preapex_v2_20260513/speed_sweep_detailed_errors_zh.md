# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.5185 | 0.2328 | 8.7340 | 17.1762 | 0.4678 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.2949 | 0.3190 | 8.9116 | 15.6029 | 0.8317 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5896 | 1.0231 | 9.4459 | 8.4556 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5822 | 1.0143 | 9.6641 | 9.3428 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2264 | 0.5027 | 9.3587 | 8.5715 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2506 | 0.5403 | 9.6067 | 8.5930 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6602 | 1.3560 | 9.2034 | 8.8204 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6352 | 1.3050 | 9.4493 | 9.0449 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2791 | 0.6082 | 9.1399 | 8.9287 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2971 | 0.6013 | 9.3887 | 8.8543 |

## 提取警告

- 无。
