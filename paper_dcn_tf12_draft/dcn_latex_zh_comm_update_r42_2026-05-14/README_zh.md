# DCN 中文 LaTeX Round10 包

- 生成日期：2026-05-11
- 源模板：`paper_dcn_tf12_draft/DCN-template.tex`
- 正文：`manuscript_zh_round10.tex`
- 参考文献：`core_references_round10.bib`

## 当前边界

- 当前主基线写作 `AKE-M`，不是上传原文 AKE-A 的严格复现。
- 力峰值作为代价监测，不写受力更小/更平滑。
- `no_delay_compensation` 当前独立消融收益较弱，时延补偿仍需 dose-response/topology recovery。
- 若要宣称 Koopman 远期开环优势，需要补 fresh training 多训练 seed、多步 rollout loss 或闭环滚动预测；强物理/DMPC baseline、C4 直接 FDI/FTC 文献仍需补齐。
- 论文方法名统一写作 `NR-KDCC`；`tf14` 仅作为本地代码/数据版本号保留在文件夹名中。

## 编译

建议使用 XeLaTeX：

```powershell
latexmk -xelatex -interaction=nonstopmode -halt-on-error manuscript_zh_round10.tex
```
