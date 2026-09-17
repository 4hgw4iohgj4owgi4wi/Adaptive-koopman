# 合理通信消融图说明

本目录来自 `hairpin_stress_suite_2026-05-07_comm_ablation_retuned`。

已修正两点：

1. `no_comm` 现在真正关闭通信质量一致性、延迟补偿、约束收紧和退化 fallback。
2. 主方法通信保护参数重新调轻，避免过度平滑转向导致横向误差被 `no_comm` 反超。

修正后关键结果：

- `comm_protection_ablation`: main 横向 RMSE 0.07459 < no_comm 0.08275，纵向 RMSE 5.82545 < no_comm 9.15472。
- `mixed_fault_and_noise`: main 横向 RMSE 0.07683 < no_comm 0.07845，纵向 RMSE 5.41483 < no_comm 8.07965。

优先使用：

- `通信保护消融/tf13_comm_protection_ablation_system_lat_long_error_compare.png`
- `混合扰动消融/tf13_mixed_fault_and_noise_system_lat_long_error_compare.png`
- `关键汇总/N08_mixed_disturbance_ablation_heatmap.png`
