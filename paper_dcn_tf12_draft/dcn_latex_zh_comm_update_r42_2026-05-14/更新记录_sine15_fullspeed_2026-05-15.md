# 15 m/s 正弦工况完整路段修复记录

时间：2026-05-15

## 本轮目标

只处理 15 m/s 正弦故障/干扰工况，回头弯不动。目标是解释并修复原图中只跑到约半段、团队纵向误差 \(e_s\) 线性下降的问题，并更新 LaTeX 文稿中的对应图和文字。

## 根因

原 15 m/s 结果不是单纯 MPC 权重导致，而是底层存在两个固定速度裁剪：

- `control_files/tf11_a1/core_utils.py` 的闭环状态裁剪把 \(v_x\) 固定限制在 8 m/s。
- `dynamics/cacalv3_payload_a1.py` 的真实四车-载荷动力学状态裁剪把 \(v_x\) 固定限制在 10 m/s。

这会导致 15 m/s 参考速度下车辆实际进度跟不上参考进度，因此图中 \(e_s\) 近似线性下降，且 x-y 轨迹只显示到半段附近。

## 代码修改

- 将闭环状态速度上限改为读取环境变量 `TF12_CLOSED_LOOP_VX_MAX`，默认保持原 8 m/s。
- 将真实载荷动力学速度上限改为读取环境变量 `TF12_CLOSED_LOOP_VX_MAX`，默认保持原 10 m/s。
- 在速度扫频启动函数中按场景速度设置 `TF12_CLOSED_LOOP_VX_MAX=max(8.0, speed_mps)`。
- 新增 15 m/s 诊断候选：
  - `s15full_phase_role_default`
  - `s15full_phase_keep_progress`
  - `s15full_baseline_progress_supervisor`
  - `s15full_baseline_progress_soft`

最终选用 `s15full_baseline_progress_soft` 更新文稿图，因为它在完整路段闭合和横向扰动之间最平衡。

## 关键结果

新批次路径：

`paper_dcn_tf12_draft/comm_architecture_sine15_fullspeed_progress_soft_20260515`

15 m/s 正弦 single-seed 指标：

- baseline 横向 RMSE：0.158565 m
- proposed 横向 RMSE：0.166643 m
- 横向最大逐点差距：0.033658 m
- 逐点胜率：27.36%
- baseline 纵向 RMSE：0.885665 m
- proposed 纵向 RMSE：0.645707 m

结论：修复后 15 m/s 能覆盖完整正弦路段，纵向进度滞后明显缓解；但横向 RMSE 略高于 baseline，因此该工况只能作为“完整路段与纵向推进修复”证据，不能作为“横向误差优于 baseline”的证据。

## 文稿更新

- 更新图：`figures/fig_nrkdcc_nooffset_fault_15mps_panel.png`
- 更新生成脚本：15 m/s 场景改为读取 `comm_architecture_sine15_fullspeed_progress_soft_20260515` 的 baseline/proposed 核心。
- 更新表 `tab:nooffset_degraded_multi` 的 15 m/s 行。
- 更新摘要、速度敏感性分析、15 m/s 图注和 no-offset 分析段落，删除旧 r16 的横向优势表述。

## 输出文件

- 审稿高亮版：`manuscript_zh_comm_update_review_sine15_fullspeed_2026_05_15.pdf`
- 最终版：`manuscript_zh_comm_update_final_sine15_fullspeed_2026_05_15.pdf`

## 验证

- 已重新生成 no-offset 面板图。
- 已用 XeLaTeX + BibTeX 编译审稿高亮版和最终版。
- 编译日志无 LaTeX Error、Emergency stop 或未定义 citation；仅保留 SimSun 粗体/斜体替代等字体警告。

