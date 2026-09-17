# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.4393 | 0.2411 | 8.7053 | 16.8529 | 0.4784 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 2.4948 | 0.1611 | 7.0362 | 4.1322 | 0.4301 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5971 | 1.0269 | 9.3711 | 8.3884 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5904 | 1.0194 | 9.5824 | 9.2864 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2172 | 0.4964 | 9.2791 | 8.6206 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2419 | 0.5326 | 9.5258 | 8.5522 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4430 | 0.9427 | 2.4226 | 6.9559 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4255 | 0.9031 | 2.6137 | 7.1345 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2140 | 0.4618 | 2.3723 | 7.0471 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2334 | 0.4981 | 2.5748 | 7.0101 |

## 提取警告

- 无。
