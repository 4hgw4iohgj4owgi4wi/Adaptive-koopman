# VS Code Overleaf 式实时预览

## 已配置效果

- 左侧编辑 `.tex`，右侧打开 LaTeX Workshop 内置 PDF 预览。
- 保存或文件变化后自动编译，PDF 预览自动刷新。
- PDF 默认按页面宽度显示。
- 编译后自动做一次正向 SyncTeX 定位。
- 在 PDF 预览中双击页面位置，可反向跳回对应 `.tex` 源码位置。
- Codex 侧同步监听 `manuscript_zh_comm_update_final.pdf`，自动生成 `codex_pdf_preview/page_*.png` 供排版检查。

## 打开方式

1. 在 VS Code 打开项目文件夹：
   `D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\dcn_latex_zh_comm_update_r42_2026-05-14`
2. 打开 `manuscript_zh_comm_update_final.tex` 或 `manuscript_zh_comm_update_core.tex`。
3. 按 `Ctrl+Alt+V` 打开 PDF 预览，预览会自动出现在右侧。
4. 编辑并保存 `.tex` 后，LaTeX Workshop 会自动编译刷新 PDF。

## 常用命令

- 编译：`Ctrl+Alt+B`
- 打开 PDF 预览：`Ctrl+Alt+V`
- 从源码跳到 PDF：`Ctrl+Alt+J`
- 从 PDF 跳回源码：在 PDF 中双击对应位置

## Codex 同步预览

当前已启动后台监听脚本：

```powershell
tools\start_codex_pdf_preview_bridge.ps1
```

刷新后的页面图在：

```text
codex_pdf_preview\page_001.png
codex_pdf_preview\page_002.png
...
```

后续可以直接让 Codex 检查某一页，例如：

```text
看最新 PDF 第 9 页，检查图和标题有没有重叠
```
