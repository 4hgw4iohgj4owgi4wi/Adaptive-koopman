# 中文主文稿审查记录（速度敏感性与回头弯补充后）

审查对象：

- `manuscript_zh_round10_speed_hairpin_review_2026-05-12.tex`
- `manuscript_zh_round10_speed_hairpin_review_2026-05-12.pdf`
- `manuscript_zh_round10_speed_hairpin_review_2026-05-12.log`

## 已并入主文稿的新增证据

1. 速度敏感性实验已并入第六章：同一通信退化与混合故障/噪声压力场景下，补充 2 m/s、5 m/s、10 m/s、15 m/s 的团队中心轨迹、团队横向误差、团队纵向误差和单车横向误差图。
2. 5 m/s 回头弯对比实验已并入第六章：补充 AKE-M、NR-KDCC w/o role schedule、NR-KDCC 在高曲率路径下的轨迹与误差对比。
3. 增加 baseline 对齐说明表：明确当前对比使用 AKE-M 代理 baseline，而非严格复现原文 AKE-A，因此结论边界限定为“面向当前实现和相同压力协议的工程对比”。
4. 增加速度/曲率工作边界说明：2 m/s、5 m/s 更接近已训练速度域；10 m/s 和 15 m/s 属于压力测试，不能写成全速度域优势。

## 审查中发现并已修复的问题

1. 原稿中存在不可追溯的证书通过率数值 `0.31775`，已删除并替换为可由主表追溯的 high communication degradation 与 mixed fault/noise 指标。
2. 原稿对速度扫描的表述偏强，已改为域内/域外边界论述：2 m/s、5 m/s 支撑工作域表现，10 m/s 支撑局部横向误差抑制，15 m/s 只能作为失效边界。
3. 回头弯实验中 phase-role 模块并未在所有指标上优于无角色版本，已将结论改为“指标级别解释”，保留纵向误差、连接利用率和证书通过率优势，同时明确不能声称高曲率全指标优势。
4. “安全保护”“连接安全”“受力安全”等容易过度外推的表达已收缩为“连接约束风险”“约束保护”或“连接约束保护”。
5. 删除或替换了无统计检验支撑的“显著”类表述，避免把 n=3 压力测试写成强统计结论。
6. FDI/FTC、delay compensation、phase-role 的证据边界已重新标注：当前支持其作为组合系统中的机制解释，尚不支持每个模块均已独立完成强消融闭环。
7. 已按“横向误差一定要好”的要求重新调入 5 m/s 回头弯横向优先结果，并将主文方法段补成可复现的高曲率横向误差保护模式：提高 $e_y/e_\psi$ 权重、降低转角惩罚、收紧横向 PPC 包络并减小转角平滑。新的 paired n=3 结果中，NR-KDCC 横向 RMSE 为 0.3515，低于 AKE-M 的 0.4053 和无角色调度版本的 0.3925。
8. 回头弯段落已改成两段式分析：第一段客观描述表图数值，第二段解释横向优先 MPC 与有界 phase-role trim 的机理，并明确受力 RMS 仍未优于 AKE-M。

## 仍未闭合的投稿风险

1. baseline 仍不是严格 AKE-A 复现。若要支撑“超过原文 baseline”，还需要严格复现 AKE-A 或增加强物理/DMPC baseline，并保持同场景、同扰动、同速度、同随机种子。
2. 速度与回头弯补充实验目前为 n=3，适合放入主文作压力证据或补充材料，但不足以单独支撑强统计结论；投稿级建议至少扩展到 n=20。
3. 回头弯场景下 NR-KDCC 已在横向 RMSE、纵向 RMSE 和证书通过率上优于 AKE-M，也优于无角色调度版本；但连接最大利用率高于无角色调度版本，力峰值和力 RMS 仍高于 AKE-M。若继续声称载荷受力更优，需要补充 Fx/Fy/Mz 分解、输入平滑消融和力约束激活率。
4. phase-role 在高曲率回头弯中已经形成横向/纵向误差收益，但尚未形成全指标收益。后续需要补充角色分配、控制分担、单车输入和连接力分配图，证明其改善来自受约束的横向纠偏分工，而不是偶然调参。
5. delay compensation 的独立贡献仍需 dose-response 证据，即不同固定时延/随机时延强度下的误差、连接利用率和证书通过率曲线。
6. Koopman 中长期 rollout 仍不能写成全面优于线性模型；当前表述应保留为“为 MPC 提供可用预测表征，并在闭环约束下形成控制收益”。

## 编译与文件检查

1. 使用 `xelatex -interaction=nonstopmode -halt-on-error` 连续两轮完成编译，生成 20 页 PDF。
2. 日志未发现 fatal error、emergency stop、undefined references 或 undefined citations。
3. 已确认主文使用的速度敏感性图和 5 m/s 回头弯图均存在于 `figures/` 目录。
4. 已对 `tf14_runtime.py`、`run_tf14_stage5_phase_role_suite.py`、`run_tf14_hairpin_5mps_comparison.py` 和 `run_tf14_speed_sweep.py` 执行 `py_compile`，语法检查通过。
5. 仍存在模板/排版类警告：SimSun 粗体/斜体字形回退、若干 overfull hbox/vbox、balance second-column 警告。这些不影响 PDF 生成，但正式投稿前仍建议统一字体并细调浮动体位置。

## 下一轮优先级

1. 先补严格 baseline：复现 AKE-A 或加入强 DMPC/physics baseline。
2. 将关键压力场景从 n=3 扩展到 n=20，并输出均值、标准差、配对差值和失败率；5 m/s 回头弯应优先保留横向优先设置，目标是确认横向 RMSE 对 AKE-M 和无角色调度版本的优势在 n=20 下仍成立。
3. 补 FDI/FTC、delay compensation、phase-role 三组独立消融。
4. 对回头弯场景补力分解与控制输入分配图，避免“误差更好但力更差”的审稿漏洞。
5. 调整 LaTeX 排版警告，重点处理首页/表格/大图造成的 overfull 和末页 balance。
