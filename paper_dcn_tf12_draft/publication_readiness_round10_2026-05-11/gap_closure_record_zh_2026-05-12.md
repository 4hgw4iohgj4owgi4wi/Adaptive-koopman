# 证据链闭合记录：Koopman、时延补偿、FDI/FTC 与 Lyapunov 证书

日期：2026-05-12

## 本轮目标

针对“Koopman 学习、时延补偿、FDI/FTC 的证据链未闭合；Lyapunov 证明假设偏强且证书实验有负裕度”的问题，本轮只处理主稿中最影响投稿可信度的四条链路：

1. Koopman 学习不能只停留在方法描述，需要补可复查的预测与稳定投影证据。
2. 时延补偿不能写成无证据的强贡献，需要展示通信时延进入控制链路，并明确当前消融边界。
3. FDI/FTC 不能只写模块名，需要给出故障注入、诊断、切换和重分配的时间线证据。
4. Lyapunov 证明不能假设过强，也不能忽略旧版证书负裕度，需要改为分模式 ISS/UUB 和有限密度负裕度条件。

## 修改文件

- `make_nrkdcc_support_figures.py`
  - 新增 `fig_nrkdcc_koopman_prediction_evidence.png`：一步 RMSE、多步 rollout、谱半径投影审计。
  - 新增 `fig_nrkdcc_delay_mechanism_evidence.png`：通信时延/丢包/链路质量/约束收缩时间线与 w/o delay paired n=20 消融边界。
  - 新增 `fig_nrkdcc_fdi_ftc_timeline.png`：mixed fault/noise 单 run 中故障激活、FDI 诊断、FTC 切换、控制重分配和证书裕度。
  - 新增 `fig_nrkdcc_modewise_certificate_closure.png`：high-communication-noise 与 mixed fault/noise 的分模式证书 ok ratio、最小裕度和 95% 实践界。

- `build_dcn_latex_zh_round10.py`
  - 把新增四张图加入 LaTeX 复制清单。
  - 离线数据生成部分补充 `dt=0.02`、状态/输入维数、速度分层、初始扰动、snapshot 和 train/val 划分。
  - FDI/FTC 部分补充 EWMA+CUSUM 公式、残差阈值、CUSUM 阈值、连续触发/释放步数和双通道效率阈值。
  - Lyapunov 证明改为分模式 ISS/UUB：加入模式证书裕度公式、有限密度负裕度条件、fallback 可行边界，移除“无条件全局渐近稳定”的暗示。
  - 实验章新增“Koopman、时延与 FDI/FTC 机制证据”小节，逐图说明每张图能支撑什么、不能支撑什么。
  - 讨论和结论中更新 claim 边界：通信感知是当前最强证据；时延补偿已闭合机制证据，但独立性能优势仍需 dose-response；Koopman 仍需 fresh training 多 seed。

## 使用的数据

- Koopman 审计：`tf14_final_gap_closure_20260509/source/E1_koopman_prediction_validation.csv`
- 分模式证书：`tf14_final_gap_closure_20260509/source/E3_certificate_mode_margin_stats.csv`
- FDI/FTC 时间线：`tf14_remaining_experiments_20260509/data/diagnostics/E0/seed_2026/dlc_mixed_fault_noise_tf14_phase_role/{fault.csv,switch.csv,certificate.csv}`
- 时延机制图：`tf14_remaining_experiments_20260509/data/diagnostics/E0/seed_2026/dlc_mixed_fault_noise_tf14_phase_role/comm.csv`
- w/o delay 消融边界：`paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/e2_n20_comm_noise_key_ablation_merged/data/tf14_remaining_summary.csv`

## 当前可写结论

- Koopman：当前可写“稳定投影将谱半径从约 1.006 压到 0.999，并提供可审计的 lifted predictor”；不能写“长 horizon 全面优于线性模型”。
- 时延补偿：当前可写“时延/丢包进入链路质量估计、邻居预测和约束收缩”；不能写“当前消融已经证明时延补偿是主要性能来源”。
- FDI/FTC：当前可写“故障后约 10 个采样步出现非名义诊断，约 13 个采样步进入 reconfigured FTC mode，并出现控制重分配”；不能写“所有故障类型均已统计证明快速精确识别”。
- Lyapunov：当前可写“有界工作域、fallback 可行、有限密度负裕度条件下的分模式 ISS/UUB”；不能写“无条件全局渐近稳定”。

## 验证结果

- 已重新生成图片：`python paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/make_nrkdcc_support_figures.py`
- 已重新生成 LaTeX 包：`python paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/build_dcn_latex_zh_round10.py`
- 已完成编译：`xelatex -> bibtex -> xelatex -> xelatex`
- 输出 PDF：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/manuscript_zh_round10_gapclosure.pdf`
- `missing_assets_zh.txt` 为空。
- LaTeX 日志中未发现未定义引用或未定义文献。
- 正文可见文本中 `TF14/tf14` 残留计数为 0。
- PDF 共 11 页；已导出 QA 页面到 `paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages_gapclosure`。

## 剩余风险

- 页面仍有 Elsevier 模板与首页 TikZ 相关 overfull warning，不影响编译，但投稿前需要版式压缩。
- E1 仍是缓存数据审计，不是 fresh training 多 seed 最终证据。
- 时延补偿的独立性能优势仍需要 delay/dropout dose-response 和 topology recovery。
- FDI/FTC 目前新增的是单 run 时间线，多 seed 检测延迟、误报率和切换延迟统计仍需补。
- AKE-M 仍是任务对齐机制 baseline，不是上传原文 AKE-A 的严格复现。
