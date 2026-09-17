# 本仓库的范围与使用须知

这个仓库是 **Adaptive-koopman 四车协同运输项目的代码与文本规范**，不是完整实验树。
建立时间 2026-09-17。

## 1. 收录范围

| 项 | 数值 |
|---|---|
| 工作树总量（建库时实测） | 26.19 GB / 91,839 文件 |
| 本仓库收录 | 约 252 MB / 3,755 文件 |
| 压缩后 pack | 约 144 MiB |
| 最大单文件 | 9.34 MB（未触及 GitHub 100 MB 硬限） |

**收录**：`*.py`、`*.ipynb`、`*.md`、`*.tex`、`*.txt`、`*.json`（规范与配置）、
`*.yaml/.yml/.toml/.cfg/.ini`、`*.sh/.cmd/.ps1/.bat`、`*.m`。

**排除**（见 `.gitignore`）：全部实验产物与大文件——`results/`、`analysis/`、
`logs/`、`data/`、`saved_data/`、`saved_models/`、`datasets/`、`archives/`，
以及 `*.npz *.csv *.pkl *.pt *.pth *.png *.pdf *.docx *.zip *.log` 等。
原始数据、模型权重与运行结果**仍在实验机上，不在版本库内**，因此：

> 本仓库不含任何可用于论文主张的数值证据。论文证据以实验机上的
> `revision_2026/paper_v4/results/**` 与 `analysis/**` 原始文件 + SHA 为准。

## 2. clone 前必须知道的两件事

### (a) 用短路径 clone，并开启长路径支持

本仓库仍有少量较长路径（最长 187 字符）。若 clone 到较深的目录，
Windows 会报 `Filename too long`（MAX_PATH=260）。请：

```powershell
git config --global core.longpaths true
git clone <URL> D:\ak          # 目标目录尽量短
```

### (b) 绝对不要让 git 做换行符转换

本项目的**证据是工作树字节本身**：`revision_2026/paper_v4/protocol/*.json`
里的每条 `identity_files` 都钉死了对应文件的 SHA-256。一旦发生 CRLF/LF 转换，
被钉住文件的 SHA 改变，历史协议与结果的身份校验会全部失败。

本仓库已用 `.gitattributes` 写入 `* -text`（对所有文件禁用 EOL 归一化，
它同时覆盖 `core.autocrlf` 设置），并在仓库级设 `core.autocrlf=false`。
本机 system 级默认是 `core.autocrlf=true`，因此请注意：

- 不要执行 `git config --global core.autocrlf true`；
- 不要"顺手统一换行符"或对文件做格式化后再提交；
- 现状是**混合**的，必须保持原样：例如
  `physical_tracking_pilot.py`、`experiment.md`、`protocol/*.json` 是 CRLF，
  而 `plant/four_vehicle_common.py` 是 LF。

## 3. 如何自查身份是否被破坏

`revision_2026/paper_v4/tools/verify_tree_identity.py`（只读）会逐份协议核对
`identity_files` 的 SHA：

```powershell
cd <clone>\revision_2026\paper_v4
python tools\verify_tree_identity.py --out analysis\tree_identity_audit.json
```

在**完整实验树**上，2026-09-17 的基线是 `protocols_total=55 / match=12 /
stale=37 / no_identity_files=6`。在**本仓库（代码子集）**里，数字会更差，因为
很多被钉住的文件（如 `results/**` 的 npz）本来就不入库——这属于预期，不代表
clone 损坏。判断 clone 是否无损的正确基准是：与实验机上同一脚本的输出
**逐字段比对**。

## 4. 未收录但需要单独处理的内容

| 内容 | 说明 |
|---|---|
| `revision_2026/nkca_v1/worktree/` | 一个自带 `.git` 的**独立本地仓库**（分支 `exp/no-koopman-control-v1-20260824`、`snapshot/no-koopman-base`，无 remote）。外层仓库若收录它只会得到空的 gitlink，故排除；需要版本化时应作为独立仓库单独推送。 |
| `pinn/`、`专利/`、`专利撰写参考/`、`ALL_codehub/`、`A1_snapshot_*`、`tf10_*`–`tf14_*`、`paper_ieee_sensors_*` | 历史批次目录（含大量数据与压缩包），未收录。如需版本化请单列范围。 |
| `data/` 目录（3,572 个 JSON，30.9 MB） | 纯数据记录。排除它同时消除了绝大部分超长路径。 |
