# 回头弯高曲率横向误差调试记录（2026-05-13）

## 1. 本轮目标

目标是针对 5 m/s 回头弯压力场景，把图中大曲率区域的团队中心横向误差调到优于 AKE-M baseline。验收顺序为：

- 第一层：高曲率 entry / apex / exit 三段 RMSE 均优于 baseline。
- 第二层：高曲率全段 P95 优于 baseline。
- 第三层：entry / apex / exit 的 P95 与 Max 均优于 baseline。
- 第四层：逐点胜率接近 100%，且不牺牲全程完成率、连接安全和纵向推进。

## 2. 已完成的代码与诊断工具

- 在 `tf14_runtime.py` 中增加了团队级高曲率末端限速保护。
- 该保护位于通信降级 fallback、进度监督和团队控制聚合之后，最终输入裁剪之前，避免早期单车 `ax_cmd` 限速被后续模块覆盖。
- 在 `tf14_runtime.py` 中保留了可选的 pre-apex 横向修正接口，但当前最稳配置将其关闭。
- 在 `tf14_remaining_experiments_20260509/diagnose_hairpin_high_curvature_lateral.py` 中完成高曲率分段诊断：按 `|kappa| >= P75` 切出 high-curvature window，并拆分 entry / apex / exit。
- 已生成总任务树：`paper_dcn_tf12_draft/hairpin_high_curvature_lateral_tuning_task_tree_2026-05-13.md`。

## 3. 当前最稳候选

候选目录：

`paper_dcn_tf12_draft/hairpin_5mps_highcurv_teamcap_mpcgain_20260513`

当前保留到代码中的关键参数：

- `mpc_q_ey_scale = 1.55`
- `mpc_q_epsi_scale = 1.30`
- `mpc_qn_ey_scale = 1.75`
- `mpc_qn_epsi_scale = 1.38`
- `mpc_r_delta_scale = 0.68`
- `delta_alpha = 0.52`
- `high_curvature_team_speed_cap_gain = 1.35`
- `high_curvature_team_speed_cap_start_s = 29.0`
- `high_curvature_team_speed_cap_end_s = 45.5`
- `high_curvature_team_speed_cap_mps = 2.85`
- `high_curvature_team_speed_cap_ax_clip = 1.80`
- `high_curvature_preapex_ey_relief_gain = 0.0`

## 4. 当前最稳候选的诊断结果

`seed = 2026`，方法为 NR-KDCC，baseline 为 AKE-M。

| 区段 | baseline RMSE | NR-KDCC RMSE | RMSE 差值 | baseline P95 | NR-KDCC P95 | P95 差值 | baseline Max | NR-KDCC Max | Max 差值 | 逐点胜率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| high-curvature all | 0.2981 | 0.2009 | -0.0972 | 0.4578 | 0.3948 | -0.0630 | 0.4627 | 0.4833 | +0.0206 | 0.9319 |
| entry | 0.1993 | 0.1770 | -0.0223 | 0.2953 | 0.3085 | +0.0132 | 0.3003 | 0.3138 | +0.0136 | 0.8984 |
| apex | 0.2737 | 0.2359 | -0.0378 | 0.3014 | 0.3151 | +0.0137 | 0.3015 | 0.3152 | +0.0137 | 0.5000 |
| exit | 0.3723 | 0.2208 | -0.1515 | 0.4613 | 0.4406 | -0.0207 | 0.4627 | 0.4833 | +0.0206 | 0.9840 |

结论：

- 第一层验收已完成：entry / apex / exit 三段 RMSE 全部优于 baseline。
- 第二层验收基本完成：高曲率全段 P95 优于 baseline。
- 第三层未完成：entry / apex 的 P95/Max 仍高约 1.3 cm，exit 的 Max 高约 2.1 cm。
- 第四层未完成：apex 逐点胜率仍只有 50%，说明该段存在“前半段更差、后半段更好”的误差分布，不能写成逐点全优。

## 5. 已排除候选

| 候选目录 | 结果 | 不能保留的原因 |
|---|---|---|
| `hairpin_5mps_highcurv_teamcap_20260513` | 高曲率三段 RMSE 均优，整体 P95 优 | entry/apex 的 P95/Max 仍偏高，且全程横向/纵向 RMSE 变差 |
| `hairpin_5mps_highcurv_teamcap_preapex_20260513` | entry 的 P95/Max 得到压制 | apex RMSE 轻微劣化，exit Max 明显劣化 |
| `hairpin_5mps_highcurv_teamcap_preapex_v2_20260513` | 不稳定 | high-curvature P95/Max 变差，apex 全面劣化 |
| `hairpin_5mps_highcurv_teamcap_mpcgain_trim_20260513` | 不稳定 | 小 pre-apex trim 仍放大 exit Max |
| `hairpin_5mps_highcurv_teamcap_mpcgain_exitend_20260513` | 失败 | 提前结束出弯 relief 后无法完整跑完全路径 |
| `hairpin_5mps_highcurv_teamcap_mpcmid_20260513` | 失败 | 中等 MPC 权重无法完整跑完全路径 |

## 6. 剩余任务树

### A. 高曲率局部峰值闭合

- A1：固定当前最稳配置，只对 entry/apex 的局部 P95/Max 做小范围网格。
- A2：优先调 `mpc_r_delta_scale`、`delta_alpha`、`mpc_qn_ey_scale`，不再优先引入 pre-apex trim。
- A3：如果必须使用 pre-apex trim，限制为更窄窗口 `s=35.8--37.6 m`，clip 不超过 `0.006--0.010 rad`。
- A4：验收标准为 entry/apex 的 P95/Max 不高于 baseline，同时保持 full path 完成。

### B. 全程性能恢复

- B1：当前最稳候选虽然高曲率好，但全程团队横向 RMSE 仍高于 baseline，不能直接作为投稿主压力场景。
- B2：下一步应引入“曲率权重调度”，只在高曲率窗口提高横向权重，避免全局 MPC 权重变激进。
- B3：建议实现 `q_ey(s)=q_ey0*(1 + gamma_kappa*mask_kappa)`，其中 `mask_kappa` 由 `|kappa|` 平滑门控生成。

### C. 多 seed 验证

- C1：当前所有结论仅来自 `seed=2026` 快速验证。
- C2：通过 A/B 后，必须运行 seeds `2026/2027/2028`。
- C3：若 n=3 通过，再扩展到 n=20 投稿级统计。

### D. 图表输出

- D1：保留 `diagnostics/high_curvature_lateral/hairpin_high_curvature_gap_seed_2026_tf14_phase_role.png` 作为局部 gap 诊断图。
- D2：新增主文候选图应包含：局部轨迹放大、`|e_y|` 沿 `s` 的对比、`|e_y^{ours}|-|e_y^{baseline}|` gap 曲线。
- D3：只有当第三层或第四层验收通过后，才能把“高曲率处横向误差全面优于 baseline”写进正文。

## 7. 当前可写入论文的边界

可以写：

“在 5 m/s 回头弯高曲率窗口内，NR-KDCC 在 entry、apex 与 exit 三个子段的横向 RMSE 均低于 AKE-M，并在全高曲率窗口获得更低的 P95 横向误差。”

不能写：

“高曲率区域所有时刻横向误差均优于 baseline。”

原因：

entry/apex/exit 仍存在少量采样点峰值高于 baseline，apex 的逐点胜率尚未闭合。
