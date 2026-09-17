# Overleaf 使用说明

主入口文件：`main.tex`

编译器：XeLaTeX

参考文献：已冻结为 `main.bbl`，Overleaf 编译时不再运行 BibTeX，以减少免费计划下的编译耗时。

上传方式：

1. 在 Overleaf 新建项目。
2. 上传本文件夹压缩包 `overleaf_nrkdcc_zh_2026-05-19.zip`。
3. Overleaf 菜单中将 compiler 设为 `XeLaTeX`。
4. 将 main document 设为 `main.tex`。
5. 如果首次编译交叉引用未完全刷新，点击 Recompile 两次。

说明：

- `local_compiled_reference.pdf` 是本地编译参考稿，不参与 Overleaf 编译。
- `figures/` 中只保留当前正文实际引用的图片。
- 该包已剔除本地 QA 页面、历史中间 PDF、脚本缓存和旧版本实验图。
- 快速版还移除了正文未实际使用的 TikZ/Soul 宏包加载，并冻结参考文献，解决免费版 Overleaf 容易超时的问题。
