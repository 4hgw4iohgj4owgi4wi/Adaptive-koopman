# Round9 执行记录：数据补强与审核返工

- 时间：2026-05-11
- 主目标：在不夸大 claim 的前提下，把投稿级数据从 smoke 推进到局部正式统计，并记录审核意见与返工结果。

## 1. 已完成的实验补强

### E3 证书统计

- 命令类型：`E3 --full-final-seeds`
- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e3_n20_certificate`
- 数据规模：4 个场景，每个场景 20 个 seed，方法为 `tf14_phase_role`
- Gate：
  - `paired_n20=PASS`
  - `required_method_success=PASS`
  - `minimum_group_n=20`
- 可支撑 claim：
  - 证书记录链、约束监测链和安全统计字段可在多场景 `n=20` 下稳定生成。
  - 闭环在这些设定下无运行异常、路径完成率为 1。
- 不能支撑 claim：
  - 不能作为优于 AKE 原文 baseline 的证据。
  - 不能替代 Lyapunov 证明，只能作为证书统计和数值验证。

### E7 载荷连接安全统计

- 命令类型：`E7 --full-final-seeds --include-zoh-surrogate`
- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e7_n20_connection_safety`
- 数据规模：2 个场景、6 类方法、每组 20 个 seed，共 240 行 run 记录
- Gate：
  - `paired_n20=PASS`
  - `required_method_success=PASS`
  - `AKE_status=PARTIAL`
  - `NonKoopman_baseline=PARTIAL`
- 可支撑 claim：
  - TF14 相关方法在通信退化/混合故障场景下保持 `20/20` 路径完成。
  - 连接违规计数为 0。
  - TF14-main/TF14-full 的连接最大利用率显著低于 AKE-M/baseline。
- 不能支撑 claim：
  - 不能写“货物受力峰值更低”或“货物受力更平滑”。E7 n=20 显示 TF14 的 force norm peak 高于 baseline。
  - 不能把 ZOH surrogate 写成物理 DMPC baseline。

## 2. 工程修正

- 文件：`tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`
- 问题：长批量运行超过交互工具等待上限后，stdout 管道断开，runner 在 `print(..., flush=True)` 处出现 `OSError: [Errno 22] Invalid argument`，导致未生成 summary/manifest。
- 修正：新增 `_safe_status_print`，所有状态输出改为容错打印；stdout 异常时写入 `logs/runner_status.log`。
- 影响边界：该修正只影响日志输出韧性，不改变算法、指标定义、CSV 字段、JSON 字段或图生成逻辑。
- 验证：`py_compile` 通过；续跑 E7 后成功生成 summary、manifest、figures 和 gate。

## 3. 审核意见与返工

- 审核 agent 结论：无 P0。
- P1 问题：原主线中的“货物受力平滑”过强，当前 E7 不支持受力峰值低于 baseline。
- 返工：已将主线改为“对货物受力/力矩进行约束化监测与安全评估”，并在可写/不可写 claim 中加入受力边界。
- P1 问题：方法/证明 85% 应限定为“证明口径/闭环草案 85%”。
- 返工：评分中保留 85%，但明确其含义是 UUB/practical boundedness 口径和控制链闭环草案，不是最终 Word 公式 QA 完成。

### E0 targeted 主对比

- 命令类型：`E0 --full-final-seeds --scenarios sine_mixed_fault_noise --methods baseline tf14_main tf14_phase_role zoh_consensus_surrogate`
- 输出目录：`paper_dcn_tf12_draft/publication_readiness_round8_2026-05-11/e0_n20_mixed_fault_main_comparison`
- 数据规模：1 个 mixed fault/noise 场景、4 类方法、每组 20 个 seed，共 80 行 run 记录
- Gate：
  - `paired_n20=PASS`
  - `required_method_success=PASS`
  - `AKE_status=PARTIAL`
  - `NonKoopman_baseline=PARTIAL`
- 可支撑 claim：
  - TF14-full 相对 AKE-M/baseline 的平均横向 RMSE 降低约 9.95%。
  - TF14-full 相对 AKE-M/baseline 的平均纵向 RMSE 降低约 0.95%。
  - TF14-full 相对 AKE-M/baseline 的连接最大利用率降低约 82.88%。
  - ZOH surrogate 在该工况下 `full_path_reached_mean=0`，只能作为弱底线失败观察。
- 不能支撑 claim：
  - TF14-full 的最大横向偏差高于 baseline，不能写“所有跟踪指标全面优于 baseline”。
  - TF14-full 的 force norm peak 和 force norm RMS 高于 baseline，不能写“受力更平滑/更小”。

## 4. 当前完成度

| 维度 | 当前估计 | 依据 |
|---|---:|---|
| 主线/claim 边界 | 85% | 已明确可写/不可写 claim，并删除受力平滑等过强说法。 |
| 方法/证明 | 85% | 已形成从车辆/载荷模型到 Koopman-MPC-FDI/FTC-证书-UUB 的证明链条。 |
| 实验工程 | 85% | runner 支持 output-root、provenance、异常续跑、后台日志容错、gate 和 E3/E7 n=20。 |
| 投稿级数据 | 70% | E0 targeted、E3、E7 已达 n=20；E2/E1/dose/topology 和 AKE-A/强 DMPC baseline 未完成。 |
| 文献证据 | 70% | 已有 20 条模块化证据矩阵，但仍需 BibTeX、全文精读和引用压缩。 |

## 5. 本轮停止线

本轮已达到用户设定的停止线：

- 主线/claim 边界约 85%。
- 方法/证明约 85%。
- 实验工程约 85%。
- 投稿级数据约 70%。
- 文献证据约 70%。

仍不能直接投稿，因为缺口集中在 E2 全量消融、E1 fresh、dose/topology、AKE-A/强 DMPC baseline 和中文 DOCX/英文 LaTeX 的最终回填。
