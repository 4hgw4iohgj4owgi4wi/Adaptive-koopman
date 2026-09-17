# RTX 5080迁移执行记录（2026-09-15）

## 授权范围

按`protocol/P1中断数据分析与RTX5080迁移任务说明_20260915.md`只实施G0—G2，不续跑/重跑P1，不启动G3/G4闭环。

## 已实现

- `gpu_port/physics_torch.py`：P1预测所需连接器、载荷转移、轮胎、四车—货物动力学及RK4的float64批量Torch实现。
- `gpu_port/rollout_batch.py`：保持10次2ms执行器/植物更新的20ms批量预测。
- `gpu_port/gpu_worker.py`与`ipc_backend.py`：单一常驻RTX 5080 worker，CPU父进程保留SciPy/OSQP，通过IPC传送固定输入及85项批量差分结果。
- `tools/gpu_g0_g2_qualify.py`：G0环境、六类G1物理样本、两组G2固定QP及分阶段计时/出图入口。
- 事前冻结float64的rhs、RK4、rollout、f0、A/B、QP矩阵/边界和首控制误差门；未在失败后放宽。

全部新增Python文件通过`py_compile`。错误协议SHA负例均在创建输出前拒绝。

## 遇到的问题、处理与效果

1. **v1双OpenMP冲突**：同一进程实际运行SciPy/OSQP与PyTorch CUDA时，`libomp.dll`和`libiomp5md.dll`冲突。没有采用`KMP_DUPLICATE_LIB_OK`不安全绕过。
2. **v2进程隔离仍不充分**：改为CPU父进程加单一CUDA worker，G0通过；但worker内仍有NumPy转换，G1前再次冲突。
3. **v3纯Torch worker仍受阻**：移除worker内NumPy和`.numpy()`，改Python列表IPC。G0再次PASS，但G1前仍出现同一错误。按协议“两轮工程修复后停止”，不再修改第三轮。

## 实际结果

- G0：PASS。DESKTOP-9IUUGEO、RTX 5080、PyTorch 2.12.0.dev20260304+cu128、CUDA构建12.8、设备能力[12,0]、float64测试结果3680且有限。
- G0图：PNG/SVG已打开，清晰无裁切，`figure_status=PASS_G0_VISUAL_QA_ONLY`。
- G1：NOT_RUN。
- G2：NOT_RUN。
- P1续跑/重跑：未发生。
- 闭环：未启动。

最终裁决：`GPU_IMPLEMENTATION_CREATED / G0_PASS / G1_G2_BLOCKED_OPENMP / NO_GPU_EQUIVALENCE_OR_SPEED_CLAIM / NO_CLOSED_LOOP`。
