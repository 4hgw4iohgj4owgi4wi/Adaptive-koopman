# 实验分析两段式改写记录

时间：2026-05-12

## 用户要求

实验分析部分改为两段式：第一段客观描述图表所示内容，第二段分析出现这些内容的原因。

## 已修改内容

- 修改 `build_dcn_latex_zh_round10.py` 中的中文稿正文模板。
- 对 E1 Koopman 训练损失图、E1 预测/谱投影图、时延机制图、FDI/FTC 时间线、分模式证书图、E0 主对比表、团队中心轨迹/误差图、E2 消融表与消融图、E3 证书表图、E7 连接/受力表图进行两段式改写。
- 第一段统一采用“客观结果是”式写法，只描述数值、趋势、场景和图表现象。
- 第二段统一采用“造成上述结果/现象/差异的原因是”式写法，解释通信质量权重、约束收缩、Koopman 短窗口预测、谱投影、PPC guard、FDI/FTC、ISS/UUB 证书和力峰值权衡等内在机理。

## 验证结果

- 已重新生成 LaTeX 包，`missing_assets_zh.txt` 为空。
- 原 `manuscript_zh_round10.pdf` 被外部程序占用，无法覆盖写入。
- 已使用不冲突 jobname 编译得到验证版 PDF：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/manuscript_zh_round10_twopara.pdf`。
- 编译流程：`xelatex -> bibtex -> xelatex -> xelatex`。
- 最终 `manuscript_zh_round10_twopara.log` 未检出未定义引用或未定义文献引用；仅剩 SimSun 字体替代和少量 overfull/underfull 版式警告。
- 当前 `.tex` 中检出 22 处两段式分析标记，覆盖主要实验图表组。

## 注意事项

如果需要主文件名仍为 `manuscript_zh_round10.pdf`，需要先关闭当前打开该 PDF 的阅读器或预览窗口，再重新编译覆盖。
