# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | 3 | 3.9328 | 0.0709 | 3.1653 | 10.5368 | 0.1616 |
| 5.00 | 18 | bilinear_no_projection | 3 | 5.3057 | 0.0463 | 2.9091 | 14.0145 | 0.1109 |
| 5.00 | 18 | full_lifted | 3 | 5.7220 | 0.0650 | 2.9794 | 14.7686 | 0.1465 |
| 5.00 | 18 | raw6_linear | 3 | 3.4737 | 0.2447 | 4.4004 | 6.3089 | 0.6096 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | vehicle_1 | 3 | 0.1584 | 0.3648 | 3.9065 | 3.0434 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_2 | 3 | 0.1551 | 0.3574 | 3.9737 | 3.2218 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_3 | 3 | 0.1486 | 0.2399 | 3.8909 | 3.2526 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_4 | 3 | 0.1569 | 0.2552 | 3.9612 | 3.1803 |
| 5.00 | 18 | bilinear_no_projection | vehicle_1 | 3 | 0.1601 | 0.3158 | 5.2774 | 2.7593 |
| 5.00 | 18 | bilinear_no_projection | vehicle_2 | 3 | 0.1571 | 0.3082 | 5.3404 | 2.9236 |
| 5.00 | 18 | bilinear_no_projection | vehicle_3 | 3 | 0.0980 | 0.1429 | 5.2745 | 3.0298 |
| 5.00 | 18 | bilinear_no_projection | vehicle_4 | 3 | 0.1054 | 0.1520 | 5.3312 | 2.9435 |
| 5.00 | 18 | full_lifted | vehicle_1 | 3 | 0.1878 | 0.3645 | 5.7032 | 2.8254 |
| 5.00 | 18 | full_lifted | vehicle_2 | 3 | 0.1842 | 0.3539 | 5.7542 | 2.9879 |
| 5.00 | 18 | full_lifted | vehicle_3 | 3 | 0.0740 | 0.1327 | 5.6864 | 3.1013 |
| 5.00 | 18 | full_lifted | vehicle_4 | 3 | 0.0819 | 0.1469 | 5.7448 | 3.0214 |
| 5.00 | 18 | raw6_linear | vehicle_1 | 3 | 0.3627 | 0.8101 | 3.4464 | 4.3836 |
| 5.00 | 18 | raw6_linear | vehicle_2 | 3 | 0.3540 | 0.7861 | 3.5249 | 4.5113 |
| 5.00 | 18 | raw6_linear | vehicle_3 | 3 | 0.2758 | 0.6237 | 3.4239 | 4.4824 |
| 5.00 | 18 | raw6_linear | vehicle_4 | 3 | 0.2830 | 0.6247 | 3.5047 | 4.3595 |

## 提取警告

- 无。
