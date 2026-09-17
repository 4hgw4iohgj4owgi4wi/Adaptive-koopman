# N2停止与解决方案

## 停止结论

固定S5受力优先保护未通过预注册门，停止进入单移线、回头弯和后续DoS矩阵。

失败门：`heavy_load_p99_not_worse_5pct, heavy_tracking_not_worse_10pct, heavy_force_or_load_improves_10pct`。

## 解决顺序

1. 不在3101–3105证据种子上继续调阈值；若重启，另建development网络种子与独立confirm种子。
2. 优先修正“预测控制与实际执行控制不一致”：当前每车用自己的延迟视图预测四车联合控制，却只执行本车一行。下一版必须采用共享联合方案、鲁棒可行域交集，或显式四车一致性约束；否则S5预测的力包络没有闭环含义。
3. medium下即使S5 blend几乎不触发，较严格的命令斜率仍造成跟踪RMSE增加32.19%。下一版应把纵向加速度和转角设置为不同松弛变量，并在新的development网络种子上做预注册tracking–force Pareto搜索。
4. heavy下连接力P99仅改善5.63%，但货物拉伸载荷P99恶化48.95%、跟踪RMSE恶化63.42%。目标函数必须同时约束四点Fx/Fy、`Q_FR/Q_LR`和联合控制一致性，不能只压连接力范数。
5. 当前N2 heavy没有形成可辨识的保护退出恢复事件；`recovery jump=0`是未观测，不是改善。新增具有明确故障结束时刻、至少1 s clean恢复窗的独立恢复工况，再评价恢复冲击。
6. 恢复场景确认可辨识后，再把AoI滞环、恢复斜率和力变化率共同放入优化，不再只靠固定命令限幅。
7. 暂定12/15 kN只能作为仿真参考；取得连接器与货物材料参数前不能作实际撕裂安全结论。

## 关键数值

- medium：连接力P99`-15.79%`、货物拉伸载荷P99`-10.74%`、力变化率P99`-27.83%`，但货物位置RMSE`+32.19%`。
- heavy：连接力P99`2685.26 → 2534.03 N`（`-5.63%`）；货物拉伸载荷P99`1336.10 → 1990.19 N`（`+48.95%`）；货物位置RMSE`0.36668 → 0.59921 m`（`+63.42%`）。
- 全部轨迹完成且有限，最大绝对连接力低于暂定12 kN；这是相对保护性能失败，不是材料已撕裂或已安全的结论。

## 完整数值

```json
{
  "gate": {
    "shared_trace_exact": true,
    "historical_N1_reproduced": true,
    "clean_transparent": true,
    "all_complete_finite_and_physical": true,
    "medium_force_p99_not_worse_5pct": true,
    "medium_load_p99_not_worse_5pct": true,
    "heavy_force_p99_not_worse_5pct": true,
    "heavy_load_p99_not_worse_5pct": false,
    "heavy_tracking_not_worse_10pct": false,
    "heavy_force_rate_not_worse_5pct": true,
    "heavy_recovery_jump_not_worse_5pct": true,
    "heavy_force_or_load_improves_10pct": false
  },
  "comparison": {
    "medium": {
      "payload_rmse_change_fraction": 0.32187686944276117,
      "force_p99_change_fraction": -0.15788140914484017,
      "load_p99_change_fraction": -0.10739840910388254,
      "force_rate_change_fraction": -0.27830859033865596,
      "recovery_jump_change_fraction": -1.0
    },
    "heavy": {
      "payload_rmse_change_fraction": 0.6341547336338484,
      "force_p99_change_fraction": -0.056319336876653026,
      "load_p99_change_fraction": 0.48954853489184846,
      "force_rate_change_fraction": -0.17890092290630522,
      "recovery_jump_change_fraction": -1.0
    }
  }
}
```
