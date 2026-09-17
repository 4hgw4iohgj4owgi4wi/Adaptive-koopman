# D0 GPU入口核对与D1 P1后期跟踪分析执行记录

执行日期：2026-09-15。执行范围严格限定为更新任务书第31节的D0/D1；没有续跑或重跑旧P1，没有运行GPU数值资格、动力学或闭环。

## 身份与输出

- 冻结协议：`protocol/D0_D1_P1_GPU_GATE_20260915_v2.json`，SHA-256 `9756ce4d0a569c96fcc79f06eee6f73576c695b8c770a3c2bf5c7122ec371025`。
- 正式输出：`analysis/20260915_D0_D1_GPU_GATE_P1_02`。
- 总状态：`PASS_D0_D1_READ_ONLY`。
- 原始P1接受段保持2200/2379周期、0—44 s；最后179周期未观测且未补画。

## D0结果

本机识别到NVIDIA GeForce RTX 5080；旧G0报告为PASS，GPU迁移源码仍逐项匹配v3登记身份。当前任务书与旧GPU协议锁定的任务书SHA不同，且没有更新后的G1、G2通过报告。故D0结论为：

`GPU_ENTRY_PRESENT_QUALIFICATION_PENDING / GPU_G1_G2_AND_CLOSED_LOOP_BLOCKED`

这不是GPU硬件失败；它表示现有证据只覆盖设备、G0和源码身份，不能替代CPU/GPU物理、Jacobian、QP首控制等价及计时资格。

## D1结果与效果

用户指定的实验裁决保持`FAIL_LATE_TRACKING_DIVERGENCE`，同时保留原执行事实`EXTERNAL_INTERRUPTION_INCOMPLETE`。只读分解显示：

- 全接受段位置RMSE 0.193774 m，末值/最大值0.542481 m；航向RMSE 0.850615°。
- 末段直线35.58—44.00 s的位置RMSE 0.390565 m，位置误差从0.188306 m增至0.542481 m，拟合绝对误差增长率0.041080 m/s。
- 末值误差以横向为主：横向0.534510 m，纵向-0.092653 m；不是主要由纵向速度失配构成，末端前向速度误差仅-0.005941 m/s。
- 出口过渡30.08—35.56 s的航向RMSE为1.356370°；末段直线航向RMSE为1.307695°。误差增长与参考出口/转向回正时序相邻，但相关性不作为因果证明。
- 最大请求/实际转角分别为15.000000°/14.998608°，最大执行器差0.599045°；请求与solver首控制逐项最大差为0。
- 已观测物理硬门未触发：点力峰值263.373107 N，内部力175.920914 N，轮胎利用率0.0474157，最小支承4209.518916 N。
- `previous_u`可由闭合前缀重建，但`beta`记忆未保存；不存在完整恢复状态。因此不能从44 s拼接D3短窗。
- 缺失证据包括未来179周期、完整预测域控制/数值QP松弛量、原P1预注册的后期发散阈值。

D2据此只定义为“先验证同算法GPU加速”，不能把显卡迁移写成P1跟踪修复。控制修正若实施，必须另设候选ID、修改模块、依据和对照。D3在G1/G2通过且取得完整状态/记忆前保持阻断。

## 遇到的问题、解决方法与效果

第一次用正确协议身份执行只读统计时，`finite_stats`调用了不存在的`ndarray.square()`，在生成D0图后以`AttributeError`停止。失败目录`analysis/20260915_D0_D1_GPU_GATE_P1`原样保留，没有启动GPU或动力学。

解决方法：把RMSE表达式改为`np.square(value)`，重新编译通过；冻结v2协议、更新脚本哈希，并使用新输出目录执行。效果：D0/D1 JSON、三组PNG/SVG、manifest和README完整生成；三张PNG已人工打开检查，`figure_status=PASS_VISUAL_QA`。该修复只恢复只读RMSE计算，没有改变数据、模型、阈值或科学结论。

## 当前决定

`D0_COMPLETE_QUALIFICATION_PENDING / D1_COMPLETE / D2_ACCELERATION_ONLY_CANDIDATE_DEFINED / D3_BLOCKED / NO_OLD_CPU_RERUN / NO_GPU_CLOSED_LOOP`
