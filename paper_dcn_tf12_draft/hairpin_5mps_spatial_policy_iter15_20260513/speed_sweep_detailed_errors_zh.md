# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.2629 | 0.1704 | 7.2604 | 5.6103 | 0.4338 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4551 | 0.9513 | 3.1909 | 7.1815 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4369 | 0.9102 | 3.3806 | 7.3656 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2308 | 0.5034 | 3.1412 | 7.2691 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2508 | 0.5417 | 3.3427 | 7.2278 |

## 提取警告

- 无。
