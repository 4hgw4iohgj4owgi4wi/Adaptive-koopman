# Hairpin Stress Suite 图件修正后使用说明

## 1 修正对象

修正目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_2026-05-06_030045`

本次针对旧说明中“不建议直接入主文”的图件做了代码级修正，主要覆盖：

1. 全局汇总图 `stress_suite_global_summary`
2. 货物受力与偏航力矩图 `payload_force_moment_compare`
3. 连接误差图 `connection_error_compare`

## 2 修正原则

旧版图件的问题不是数据完全不可用，而是图的表达口径容易支持错误结论：

1. 受力图不能写成“主方法受力一定更小”。
2. 连接图不能写成“主方法连接误差 RMS 全面更小”。
3. 全局汇总图不能存在空白进度子图或未闭合统计。

因此本次没有隐藏不利数据，而是把图改成它们真正能支撑的结论。

## 3 当前可用口径

### 3.1 全局汇总图

当前用途：可作为回头弯 stress-suite 的总览图。

已修正：

1. `progress_ratio` 已补齐。
2. `final_s` 已补齐。
3. `traj_length` 已补齐。
4. `comm_delay_mean` 与 `comm_loss_mean` 已补齐。
5. 完成度图不再为空。

注意：该图仍不用于证明主方法实时性更好，因为当前主方法求解时间并不小于 baseline。

### 3.2 货物受力图

当前用途：作为“受力需求与跟踪收益的 trade-off 机理图”。

已修正：

1. 原始 `F_x/F_y/M_z` 三通道尖峰图改为平滑稳健口径的归一化受力需求。
2. 增加团队位置误差曲线，用来展示受力需求与跟踪收益之间的关系。
3. 底部柱状图改为相对 `AKE-baseline` 的横向条形图，避免单位混杂和标签拥挤。

可写结论：TF13 在更强跟踪和故障恢复下可能需要更高受力需求，但换来了明显更低的位置误差。

不应写成：TF13 在所有场景下货物受力更小。

### 3.3 连接约束图

当前用途：作为“连接约束安全裕度图”。

已修正：

1. 原始连接误差曲线改为归一化连接约束占用率。
2. 增加约束边界线与安全裕度曲线。
3. 保留相对连接误差能量，作为内部机理参考。

可写结论：多方法均未触及连接约束边界，TF13 在误差改善时仍保持连接约束可行。

不应写成：TF13 的连接 RMS 在所有场景下都更小。

## 4 建议入文方式

推荐正文中优先使用：

1. `system_lat_long_error_compare`
2. `team_position_error_compare`
3. `fault_window_zoom`
4. `stress_suite_global_summary`

推荐补充材料中使用：

1. `payload_force_moment_compare`
2. `connection_error_compare`
3. `each_vehicle_lat_long_error_compare`
4. `comm_delay_fault_timeline`

## 5 一句话结论

修正后的图件可以支撑“TF13 在回头弯鲁棒工况中以更高的协调控制需求换取更小的横纵向误差，并保持连接约束可行”，但不用于支撑“求解更快”或“所有物理量都更小”。
