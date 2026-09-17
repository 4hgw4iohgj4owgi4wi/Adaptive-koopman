# 回头弯高曲率横向误差诊断

- 输出目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_5mps_highcurv_speedcap_strong_20260513\diagnostics\high_curvature_lateral`
- 方法：`tf14_phase_role` vs `baseline`
- 曲率阈值：`abs(kappa) >= P75`
- 逐点容差：`0.010 m`

## 读取文件

- `high_curvature_segment_stats_tf14_phase_role.csv`：分段 RMSE/P95/峰值/win ratio。
- `high_curvature_worst_points_tf14_phase_role.csv`：高曲率窗口内 proposed 相对 baseline 最差的路径点。
- `hairpin_high_curvature_gap_seed_*_*.png`：局部轨迹和误差 gap 图。
