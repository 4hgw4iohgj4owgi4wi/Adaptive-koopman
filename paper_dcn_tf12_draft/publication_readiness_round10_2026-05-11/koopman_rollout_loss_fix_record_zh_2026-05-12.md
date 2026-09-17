# Koopman 中长期 rollout 与训练损失补强记录

时间：2026-05-12

## 问题判断

当前 E1 缓存数据中，双线性 Koopman 在一步预测和 1--8 步短窗口内略优于线性模型；但到 MPC 主配置 $H=12$ 时三类模型的 95% 置信区间高度重叠，10 步后均值不再稳定占优，远期开环 rollout 不能写成全面优于线性模型。因此本轮没有用文字掩盖问题，而是把主文 claim 改成“训练收敛、控制窗口内可比且短窗口略优、稳定投影限制谱半径、闭环 MPC 与安全保护共同产生性能优势”。

训练损失图确实遗漏。本轮已补入 Koopman lifting 网络训练/验证损失图，展示 total、prediction、lifted loss 的收敛过程和最后 10 个 epoch 的训练/验证差距。

## 已修改内容

- 修改 `make_nrkdcc_support_figures.py`：新增 `fig_nrkdcc_koopman_training_loss.png`，并将 `fig_nrkdcc_koopman_prediction_evidence.png` 的 rollout 子图限制到 1--12 步控制窗口，加入 95% 置信区间和 $H=12$ 标记。
- 修改 `build_dcn_latex_zh_round10.py`：将训练损失图加入 LaTeX 资源复制列表，并在“Koopman、时延与 FDI/FTC 机制证据”中新增训练损失图、图注和分析段落。
- 修改主文 E1 表述：删除“中长期 rollout 尚未全面优于线性模型”这类审稿人容易抓住的裸露弱点，改为定量说明边界：一步 RMSE 为 0.0339 vs 0.0350，1--8 步短窗口平均误差为 0.2716/0.2763 vs 0.2797，$H=12$ 置信区间重叠。
- 修改摘要和结论：不再写 TF14 版本号；明确 Koopman 模块不是远期开环性能 claim，而是受约束 MPC 的可审计预测结构。

## 验证结果

- 已重新生成 NR-KDCC 支撑图。
- 已重新生成中文 LaTeX 包。
- 已完成 `xelatex -> bibtex -> xelatex -> xelatex` 编译。
- 输出 PDF：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/manuscript_zh_round10.pdf`。
- `missing_assets_zh.txt` 为空。
- 最终 LaTeX 日志无未定义引用和未定义文献引用；仍有 SimSun 粗体/斜体替代和少量 overfull/underfull 版式警告。
- 主文 `.tex` 中未检出 `TF14`/`tf14` 和旧句“中长期 rollout 尚未全面优于”。

## 剩余风险

如果后续要把 Koopman claim 提升为“中长期/远期开环显著优于线性模型”，必须做算法级补强，而不是只改图：建议加入多步 rollout loss、scheduled rollout 训练、谱半径/contractive 正则、闭环 receding-horizon prediction 评估和多 seed fresh training。当前稿件应保持控制窗口内证据边界。
