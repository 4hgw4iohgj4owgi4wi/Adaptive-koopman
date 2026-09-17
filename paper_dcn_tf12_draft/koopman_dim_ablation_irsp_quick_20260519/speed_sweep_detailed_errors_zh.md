# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | 3 | 3.5550 | 0.0592 | 3.7294 | 9.3663 | 0.1633 |
| 5.00 | 18 | bilinear_no_projection | 3 | 4.8411 | 0.0480 | 2.9774 | 11.8109 | 0.1146 |
| 5.00 | 18 | full_lifted | 3 | 4.4097 | 0.0772 | 3.2145 | 10.9678 | 0.1892 |
| 5.00 | 18 | raw6_linear | 3 | 3.4737 | 0.2447 | 4.4004 | 6.3089 | 0.6096 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | vehicle_1 | 3 | 0.1955 | 0.3678 | 3.5219 | 3.6030 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_2 | 3 | 0.1884 | 0.3628 | 3.6130 | 3.7886 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_3 | 3 | 0.1416 | 0.2393 | 3.4945 | 3.8119 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_4 | 3 | 0.1546 | 0.2583 | 3.5918 | 3.7490 |
| 5.00 | 18 | bilinear_no_projection | vehicle_1 | 3 | 0.1610 | 0.3208 | 4.8122 | 2.8175 |
| 5.00 | 18 | bilinear_no_projection | vehicle_2 | 3 | 0.1578 | 0.3130 | 4.8782 | 2.9893 |
| 5.00 | 18 | bilinear_no_projection | vehicle_3 | 3 | 0.1055 | 0.1597 | 4.8072 | 3.1075 |
| 5.00 | 18 | bilinear_no_projection | vehicle_4 | 3 | 0.1133 | 0.1700 | 4.8678 | 3.0134 |
| 5.00 | 18 | full_lifted | vehicle_1 | 3 | 0.1864 | 0.4125 | 4.3830 | 3.1657 |
| 5.00 | 18 | full_lifted | vehicle_2 | 3 | 0.1811 | 0.4012 | 4.4498 | 3.2641 |
| 5.00 | 18 | full_lifted | vehicle_3 | 3 | 0.1267 | 0.1963 | 4.3701 | 3.2507 |
| 5.00 | 18 | full_lifted | vehicle_4 | 3 | 0.1356 | 0.2104 | 4.4370 | 3.1959 |
| 5.00 | 18 | raw6_linear | vehicle_1 | 3 | 0.3627 | 0.8101 | 3.4464 | 4.3836 |
| 5.00 | 18 | raw6_linear | vehicle_2 | 3 | 0.3540 | 0.7861 | 3.5249 | 4.5113 |
| 5.00 | 18 | raw6_linear | vehicle_3 | 3 | 0.2758 | 0.6237 | 3.4239 | 4.4824 |
| 5.00 | 18 | raw6_linear | vehicle_4 | 3 | 0.2830 | 0.6247 | 3.5047 | 4.3595 |

## 提取警告

- 无。
