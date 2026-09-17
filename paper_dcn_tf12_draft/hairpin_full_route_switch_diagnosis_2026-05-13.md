# 5 m/s 回头弯全路段逐点误差与切换段诊断

## 1. 目标

用户目标是“全路段 100% 横向误差小于 baseline”。本轮诊断不是只看总体 RMSE，而是把 `|e_y^{ours}|-|e_y^{baseline}|` 沿路径进度 `s` 展开，并按每 5 m 路段统计该段对总体平方误差的贡献。

## 2. 主要结论

真正把总体横向 RMSE 压下来的不是 `tf14_switcher` 的 global mode 切换。诊断显示 `tf14_global_mode` 全程基本都是 `nominal_koopman_mpc`。

实际起作用的是三类“隐式切换”：

- 路径相位调度：`turn_core` 内的 role trim。
- progress supervisor：进度滞后时的推进恢复。
- fault/progress 叠加后的相位角色调度。

## 3. 哪一段把总体误差压下来

以 `paper_dcn_tf12_draft/hairpin_5mps_lateral_priority_20260513` 的 n=3 结果为准，平均正贡献最大的路段如下：

| 路段 | 平均 RMSE 差值 | 平均逐点胜率 | 平均平方误差贡献 | 主要状态 |
|---|---:|---:|---:|---|
| `s=60--65 m` | `-0.0706 m` | `0.790` | `+3.7229` | fault active + turn core，部分 progress boost |
| `s=50--55 m` | `-0.0800 m` | `0.613` | `+3.4062` | fault active + progress boost |
| `s=65--70 m` | `-0.0898 m` | `1.000` | `+2.6321` | fault active + turn core |
| `s=70--75 m` | `-0.1181 m` | `1.000` | `+2.0000` | fault active + turn core |
| `s=25--30 m` | `-0.0871 m` | `0.890` | `+1.2997` | fault 刚开始后的 role/progress 响应 |

因此，目前“总误差低于 baseline”的主要来源是 `s=50--75 m` 的后半段回头弯，尤其是 `s=60--65 m`。这个区间内 role schedule 相对 w/o-role 也有最大额外收益。

## 4. 哪一段破坏全路段 100% 逐点小于 baseline

平均负贡献最大的路段如下：

| 路段 | 平均 RMSE 差值 | 平均逐点胜率 | 平均平方误差贡献 | 主要状态 |
|---|---:|---:|---:|---|
| `s=40--45 m` | `+0.3709 m` | `0.000` | `-23.9108` | fault active + turn core + progress boost |
| `s=35--40 m` | `+0.2394 m` | `0.000` | `-19.1945` | fault active + turn core |
| `s=45--50 m` | `+0.1977 m` | `0.080` | `-8.9437` | fault active + progress boost |
| `s=30--35 m` | `+0.0287 m` | `0.493` | `-1.3858` | 进入高曲率段前后 |

最严重逐点劣化集中在 `s≈43.0--44.7 m`。以 seed 2026 为例，baseline 的 `|e_y|` 约 `0.07--0.11 m`，NR-KDCC 的 `|e_y|` 约 `0.46--0.50 m`，差值约 `0.39--0.40 m`。

## 5. 已验证的切换尝试

### 5.1 窗口式 MPC 权重切换

实现内容：

- 在 `tf14_runtime.py` 中加入 `windowed_mpc_weight_enabled`。
- 只在 `s=35--50 m` 且 `|kappa|>=0.070` 时提高横向/航向权重、终端权重，并降低转角惩罚和转角平滑。

结果：

- seed 2026 全程横向 RMSE：`0.3590 < 0.4061`，总体仍优于 baseline。
- 但 `s=35--45 m` 仍明显差于 baseline，说明单纯改 MPC 权重不足。

### 5.2 局部团队末端限速切换

实现内容：

- 只在 `s=34--45.5 m` 打开高曲率团队 speed cap。

结果：

- seed 2026 全程横向 RMSE：`0.4104 > 0.4060`。
- 该配置让横向全程结果变差，因此已回退，不保留。

## 6. 下一步应改哪里

要实现“全路段 100% 逐点小于 baseline”，核心不是再提高全局横向权重，也不是硬限速，而是要针对 `s=35--45 m` 的 progress/fault 叠加做一个横向优先切换：

- 在 `s=35--45 m` 且 `fault_active=True`、`turn_core=True`、`|e_y|` 持续偏大时，降低 progress supervisor 的加速恢复权重。
- 该切换不能关闭 `s=50--75 m` 的 progress/role 收益，因为后半段正是总体 RMSE 下降的主要来源。
- 建议新增 `critical_lateral_priority_switch`，触发窗口为 `s=35--45 m`，退出窗口为 `s>45 m` 或 `|e_y|` 回落到阈值以下。

## 7. 文件

- 全路段诊断脚本：`tf14_remaining_experiments_20260509/analyze_hairpin_full_route_gap_switches.py`
- n=3 诊断目录：`paper_dcn_tf12_draft/hairpin_5mps_lateral_priority_20260513/diagnostics/full_route_gap_switches`
- 窗口 MPC 候选目录：`paper_dcn_tf12_draft/hairpin_5mps_windowed_mpc_switch_20260513`
- 局部限速失败候选目录：`paper_dcn_tf12_draft/hairpin_5mps_windowed_mpc_speed_switch_20260513`
