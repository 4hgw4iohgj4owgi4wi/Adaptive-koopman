# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | 1 | 0.4214 | 0.0079 | 0.7680 | 1.0227 | 0.0165 |
| 5.00 | 18 | bilinear_no_projection | 1 | 0.6234 | 0.0072 | 0.7663 | 3.3612 | 0.0154 |
| 5.00 | 18 | full_lifted | 1 | 0.7478 | 0.0084 | 0.7634 | 4.0837 | 0.0180 |
| 5.00 | 18 | raw6_linear | 1 | 0.4118 | 0.1668 | 1.6725 | 0.5906 | 0.5146 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | ake_linear_net_koopman | vehicle_1 | 1 | 0.0346 | 0.0637 | 0.4219 | 0.6566 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_2 | 1 | 0.0376 | 0.0645 | 0.4209 | 0.7684 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_3 | 1 | 0.0296 | 0.0535 | 0.4214 | 0.8637 |
| 5.00 | 18 | ake_linear_net_koopman | vehicle_4 | 1 | 0.0305 | 0.0581 | 0.4221 | 0.8304 |
| 5.00 | 18 | bilinear_no_projection | vehicle_1 | 1 | 0.0342 | 0.0652 | 0.6243 | 0.6264 |
| 5.00 | 18 | bilinear_no_projection | vehicle_2 | 1 | 0.0367 | 0.0696 | 0.6223 | 0.7228 |
| 5.00 | 18 | bilinear_no_projection | vehicle_3 | 1 | 0.0284 | 0.0518 | 0.6239 | 0.8834 |
| 5.00 | 18 | bilinear_no_projection | vehicle_4 | 1 | 0.0287 | 0.0517 | 0.6236 | 0.8565 |
| 5.00 | 18 | full_lifted | vehicle_1 | 1 | 0.0345 | 0.0619 | 0.7485 | 0.6284 |
| 5.00 | 18 | full_lifted | vehicle_2 | 1 | 0.0369 | 0.0656 | 0.7469 | 0.7229 |
| 5.00 | 18 | full_lifted | vehicle_3 | 1 | 0.0284 | 0.0519 | 0.7482 | 0.8772 |
| 5.00 | 18 | full_lifted | vehicle_4 | 1 | 0.0292 | 0.0563 | 0.7482 | 0.8495 |
| 5.00 | 18 | raw6_linear | vehicle_1 | 1 | 0.1941 | 0.6553 | 0.4105 | 1.6989 |
| 5.00 | 18 | raw6_linear | vehicle_2 | 1 | 0.1884 | 0.6339 | 0.4165 | 1.7171 |
| 5.00 | 18 | raw6_linear | vehicle_3 | 1 | 0.1745 | 0.4830 | 0.4077 | 1.8018 |
| 5.00 | 18 | raw6_linear | vehicle_4 | 1 | 0.1707 | 0.4616 | 0.4168 | 1.7024 |

## 提取警告

- 无。
