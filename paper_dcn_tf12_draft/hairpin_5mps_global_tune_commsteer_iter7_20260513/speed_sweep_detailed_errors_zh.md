# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.6747 | 0.1840 | 7.3673 | 6.4158 | 0.4636 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4671 | 0.9922 | 3.6030 | 7.2938 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4483 | 0.9493 | 3.7916 | 7.4800 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2409 | 0.5174 | 3.5539 | 7.3729 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2610 | 0.5559 | 3.7544 | 7.3243 |

## 提取警告

- 无。
