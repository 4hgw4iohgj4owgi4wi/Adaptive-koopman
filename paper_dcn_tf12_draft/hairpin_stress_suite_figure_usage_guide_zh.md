# Hairpin Stress Suite 图件逐类与逐图使用指南

## 1 说明

本文件针对目录 `hairpin_stress_suite_2026-04-30_221215` 下的全部图件，重新整理为两层说明：

1. 每类图为什么能用、为什么不能用。
2. 每一张图单独适合放在哪里、主要风险是什么。

本次整理共覆盖 `134` 张 `png` 图。

## 2 总体判断

这套图件更适合作为“回头弯鲁棒性与消融的补充材料”，而不是当前中文主文第 5 节的核心实验图。

主要原因有三条：

1. 统计口径未完全闭合，进度相关量和部分通信统计存在空值。
2. 图件整体能支撑横纵向误差改善，但不能支撑“步耗时更优”和“连接一致性整体更优”。
3. 定向消融中存在 trade-off，不能把所有模块写成“去掉后所有指标都同步变差”。

当前逐图评估标签分布如下：

- `可作补充证据`: 15 张
- `可作局部补充证据`: 13 张
- `谨慎使用`: 15 张
- `仅可作补充图`: 45 张
- `仅诊断用途`: 15 张
- `不建议直接入主文`: 31 张

## 3 逐类说明

### 3.1 全局汇总图（1 张）

能用：可以作为作者内部筛查总览，快速查看不同回头弯场景下横向 RMSE 和纵向 RMSE 的总体变化趋势。

不能用：不能直接作为主文正式图件，因为当前第三子图为空，且没有置信区间、没有完整进度统计，统计口径不闭合。

建议：仅建议作为内部诊断图；如要入文，需先补齐进度和轨迹长度统计。

代表标签：
- `不建议直接入主文`: 1 张

### 3.2 团队中心轨迹对比图（15 张）

能用：可以用来定性说明“路径是否能跑通”“团队中心是否大体贴合参考曲线”。

不能用：不能单独证明鲁棒性优劣，因为大多数曲线几乎重合，肉眼难以分辨谁更优。

建议：适合放在补充材料，作为路径完成性示意图。

代表标签：
- `仅可作补充图`: 15 张

### 3.3 四车轨迹对比图（15 张）

能用：可以展示四车角点车辆在回头弯中的几何队形是否保持。

不能用：不能单独支撑性能结论，因为它缺少明确数值指标，也无法直接量化刚体构型误差。

建议：适合作为附录图，用来配合连接误差或法向载荷统计阅读。

代表标签：
- `仅可作补充图`: 15 张

### 3.4 团队位置误差对比图（15 张）

能用：可以辅助说明团队位置误差随时间的变化趋势，尤其适合配合轨迹图理解误差聚集区间。

不能用：如果没有表格数值配套，读者很难仅凭曲线精确判断优劣幅度。

建议：谨慎使用，最好和 RMSE 表格成对出现。

代表标签：
- `谨慎使用`: 15 张

### 3.5 系统横纵向误差对比图（15 张）

能用：这是当前 suite 里最有价值的一类图，能比较直接地支撑“TF13 在回头弯下横纵向误差整体更小”的结论。

不能用：仍然不能孤立下结论，因为部分消融图里不是所有维度都单调更优，容易把模块作用写得过满。

建议：适合做补充实验主图，但表述应限制在“某些误差维度/某类场景下改善明显”。

代表标签：
- `可作补充证据`: 15 张

### 3.6 单车横纵向误差对比图（15 张）

能用：可以支撑“收益是否在四辆车之间均匀分布”“故障车与健康车谁更敏感”这类分析。

不能用：图面信息量过大，不适合作为主文核心图，否则会把读者带进细节而忽略主结论。

建议：更适合补充材料或答审附录。

代表标签：
- `仅可作补充图`: 15 张

### 3.7 货物受力与偏航力矩对比图（15 张）

能用：可以帮助分析通信保护或故障重分配对载荷受力路径的影响，适合做机理讨论。

不能用：不适合直接进当前主文，因为部分场景中 TF13 的曲线尖峰更大，如果没有统一滤波与峰值口径，会直接冲掉“更平稳”的叙述。

建议：必须先统一峰值定义、滤波和稳健统计，再决定是否入文。

代表标签：
- `不建议直接入主文`: 15 张

### 3.8 连接误差对比图（15 张）

能用：理论上它最适合支撑连接柔顺、刚体校正和通信保护的作用机理。

不能用：当前 suite 中连接 RMS 的统计大多数场景并不支持 TF13 优于 baseline，因此这类图不能拿来支撑“连接一致性整体更好”的主张。

建议：暂不建议入主文，只能作为内部分析或附录反例材料。

代表标签：
- `不建议直接入主文`: 15 张

### 3.9 通信/时延/故障时间线图（15 张）

能用：非常适合解释“某段误差为什么突然变化”，也适合配合 fault-window 图做机理定位。

不能用：它不是性能优劣图，不能单独证明某个方法更好。

建议：保留为诊断或附录图。

代表标签：
- `仅诊断用途`: 15 张

### 3.10 故障窗口局部放大图（13 张）

能用：适合展示故障触发后的短时恢复、补偿和误差传播机理，是解释模块作用最直观的图之一。

不能用：它只覆盖局部窗口，不能代替全局统计；若只看局部，容易高估局部改善的重要性。

建议：适合作为补充实验的关键示意图，与全局误差表联合使用。

代表标签：
- `可作局部补充证据`: 13 张

## 4 逐图说明

下面按场景逐张列出图件用途和风险。

### 4.1 全局汇总

- `figures/summary/tf13_stress_suite_global_summary.png`
  图类：全局汇总图
  结论：不建议直接入主文
  说明：汇总图第三子图为空，且混合多场景但未给出置信区间，不能单独作为正式统计证据。

### 4.2 回头弯：中等通信噪声

- `figures/comm_noise/tf13_comm_noise_medium_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/comm_noise/tf13_comm_noise_medium_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/comm_noise/tf13_comm_noise_medium_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/comm_noise/tf13_comm_noise_medium_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/comm_noise/tf13_comm_noise_medium_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/comm_noise/tf13_comm_noise_medium_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/comm_noise/tf13_comm_noise_medium_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/comm_noise/tf13_comm_noise_medium_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/comm_noise/tf13_comm_noise_medium_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.3 回头弯：名义工况针对性对比

- `figures/targeted_ablations/tf13_nominal_adapt_ablation_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。 另外，主方法与去在线自适应几乎重合，不能据此证明在线自适应在名义场景下显著有效。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。 另外，主方法与去在线自适应几乎重合，不能据此证明在线自适应在名义场景下显著有效。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/targeted_ablations/tf13_nominal_adapt_ablation_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。 另外，主方法与去在线自适应几乎重合，不能据此证明在线自适应在名义场景下显著有效。

### 4.4 回头弯：强通信噪声

- `figures/comm_noise/tf13_comm_noise_heavy_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/comm_noise/tf13_comm_noise_heavy_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/comm_noise/tf13_comm_noise_heavy_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/comm_noise/tf13_comm_noise_heavy_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/comm_noise/tf13_comm_noise_heavy_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/comm_noise/tf13_comm_noise_heavy_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/comm_noise/tf13_comm_noise_heavy_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/comm_noise/tf13_comm_noise_heavy_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/comm_noise/tf13_comm_noise_heavy_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.5 回头弯：故障+通信噪声混合扰动对比

- `figures/targeted_ablations/tf13_mixed_fault_and_noise_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/targeted_ablations/tf13_mixed_fault_and_noise_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.6 回头弯：故障重分配能力对比

- `figures/targeted_ablations/tf13_fault_redist_ablation_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/targeted_ablations/tf13_fault_redist_ablation_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/targeted_ablations/tf13_fault_redist_ablation_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/targeted_ablations/tf13_fault_redist_ablation_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/targeted_ablations/tf13_fault_redist_ablation_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/targeted_ablations/tf13_fault_redist_ablation_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/targeted_ablations/tf13_fault_redist_ablation_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。 该图更适合支撑“去故障重分配会放大横向误差”，但不足以证明所有指标全面更优。
- `figures/targeted_ablations/tf13_fault_redist_ablation_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/targeted_ablations/tf13_fault_redist_ablation_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.7 回头弯：无噪声无故障

- `figures/nominal/tf13_nominal_clean_pair_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/nominal/tf13_nominal_clean_pair_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/nominal/tf13_nominal_clean_pair_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/nominal/tf13_nominal_clean_pair_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/nominal/tf13_nominal_clean_pair_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/nominal/tf13_nominal_clean_pair_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/nominal/tf13_nominal_clean_pair_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/nominal/tf13_nominal_clean_pair_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.8 回头弯：通信保护能力对比

- `figures/targeted_ablations/tf13_comm_protection_ablation_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/targeted_ablations/tf13_comm_protection_ablation_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/targeted_ablations/tf13_comm_protection_ablation_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/targeted_ablations/tf13_comm_protection_ablation_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/targeted_ablations/tf13_comm_protection_ablation_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/targeted_ablations/tf13_comm_protection_ablation_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。 当前图中货物侧向力/力矩尖峰较大，若不先解释峰值口径，容易被审稿人质疑。
- `figures/targeted_ablations/tf13_comm_protection_ablation_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。 该图中主方法主要改善纵向误差，而横向误差并非单调优于去通信保护版本。
- `figures/targeted_ablations/tf13_comm_protection_ablation_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/targeted_ablations/tf13_comm_protection_ablation_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.9 回头弯：随机单车失效故障（车1）

- `figures/fault_zero/tf13_rand_fault_zero_v1_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_zero/tf13_rand_fault_zero_v1_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_zero/tf13_rand_fault_zero_v1_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_zero/tf13_rand_fault_zero_v1_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_zero/tf13_rand_fault_zero_v1_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_zero/tf13_rand_fault_zero_v1_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_zero/tf13_rand_fault_zero_v1_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_zero/tf13_rand_fault_zero_v1_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_zero/tf13_rand_fault_zero_v1_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.10 回头弯：随机单车失效故障（车2）

- `figures/fault_zero/tf13_rand_fault_zero_v2_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_zero/tf13_rand_fault_zero_v2_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_zero/tf13_rand_fault_zero_v2_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_zero/tf13_rand_fault_zero_v2_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_zero/tf13_rand_fault_zero_v2_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_zero/tf13_rand_fault_zero_v2_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_zero/tf13_rand_fault_zero_v2_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_zero/tf13_rand_fault_zero_v2_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_zero/tf13_rand_fault_zero_v2_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.11 回头弯：随机单车失效故障（车3）

- `figures/fault_zero/tf13_rand_fault_zero_v3_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_zero/tf13_rand_fault_zero_v3_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_zero/tf13_rand_fault_zero_v3_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_zero/tf13_rand_fault_zero_v3_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_zero/tf13_rand_fault_zero_v3_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_zero/tf13_rand_fault_zero_v3_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_zero/tf13_rand_fault_zero_v3_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_zero/tf13_rand_fault_zero_v3_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_zero/tf13_rand_fault_zero_v3_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.12 回头弯：随机单车失效故障（车4）

- `figures/fault_zero/tf13_rand_fault_zero_v4_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_zero/tf13_rand_fault_zero_v4_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_zero/tf13_rand_fault_zero_v4_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_zero/tf13_rand_fault_zero_v4_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_zero/tf13_rand_fault_zero_v4_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_zero/tf13_rand_fault_zero_v4_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_zero/tf13_rand_fault_zero_v4_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_zero/tf13_rand_fault_zero_v4_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_zero/tf13_rand_fault_zero_v4_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.13 回头弯：随机单车降额故障（车1）

- `figures/fault_degraded/tf13_rand_fault_deg_v1_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v1_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.14 回头弯：随机单车降额故障（车2）

- `figures/fault_degraded/tf13_rand_fault_deg_v2_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v2_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.15 回头弯：随机单车降额故障（车3）

- `figures/fault_degraded/tf13_rand_fault_deg_v3_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v3_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

### 4.16 回头弯：随机单车降额故障（车4）

- `figures/fault_degraded/tf13_rand_fault_deg_v4_comm_delay_fault_timeline.png`
  图类：通信/时延/故障时间线图
  结论：仅诊断用途
  说明：适合说明通信质量、时延或故障阶段何时触发，不是性能优劣的直接证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_connection_error_compare.png`
  图类：连接误差对比图
  结论：不建议直接入主文
  说明：当前 suite 中连接 RMS 多数场景并不支持 TF13 优于 baseline，直接使用会与主文主张冲突。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_each_vehicle_lat_long_error_compare.png`
  图类：单车横纵向误差对比图
  结论：仅可作补充图
  说明：信息密度高，适合作为单车响应补充，不适合作为主文核心证据。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_fault_window_zoom.png`
  图类：故障窗口局部放大图
  结论：可作局部补充证据
  说明：适合说明故障阶段局部响应与恢复机理，但缺乏全局统计，宜与表格联合使用。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_four_vehicle_traj_compare.png`
  图类：四车轨迹对比图
  结论：仅可作补充图
  说明：可展示四车几何队形是否保持，但缺少定量统计，不能单独支撑结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_payload_force_moment_compare.png`
  图类：货物受力与偏航力矩对比图
  结论：不建议直接入主文
  说明：部分场景下 TF13 曲线存在更大尖峰或波动，若不先统一峰值定义和滤波规则，会冲掉稳定性叙述。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_system_lat_long_error_compare.png`
  图类：系统横纵向误差对比图
  结论：可作补充证据
  说明：能支持横纵向误差时序比较，但不同模块并非所有指标都单调更优，不能孤立下结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_team_center_traj_compare.png`
  图类：团队中心轨迹对比图
  结论：仅可作补充图
  说明：轨迹大面积重合，适合做定性路径完成展示，不足以支撑鲁棒性优劣结论。
- `figures/fault_degraded/tf13_rand_fault_deg_v4_team_position_error_compare.png`
  图类：团队位置误差对比图
  结论：谨慎使用
  说明：可辅助说明团队位置误差趋势，但需配合数值表，否则读者难以定量比较。

## 5 最后建议

如果后续要从这套 suite 中挑图进论文，建议优先顺序如下：

1. 优先挑 `system_lat_long_error_compare` 和 `fault_window_zoom`，因为它们最能支撑误差和机理。
2. `team_center_traj_compare`、`four_vehicle_traj_compare`、`team_position_error_compare` 只作为补充图。
3. `payload_force_moment_compare` 和 `connection_error_compare` 在当前口径下不要直接进主文。
4. `comm_delay_fault_timeline` 只保留作诊断图，不要当性能图。