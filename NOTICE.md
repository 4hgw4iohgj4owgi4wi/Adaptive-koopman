# 许可范围说明（NOTICE）

本文件补充 [LICENSE](LICENSE)（MIT）。MIT 授权**只覆盖本项目新增部分**，不覆盖下列内容。

## 1. 上游派生代码 — 授权状态未明确

仓库中有一部分派生自上游项目：

```
https://github.com/Rajpal9/Adaptive-koopman
R. Singh, C. K. Sah, J. Keshavan,
"Adaptive Koopman Embedding for Robust Control of Complex Dynamical Systems",
arXiv:2405.09101
```

该上游仓库**没有 LICENSE 文件**，即其授权状态未由原作者明确说明。因此 MIT 授权**不延伸**到
上游派生材料，至少包括：

| 路径 | 说明 |
|---|---|
| `core/` | Koopman 核心与自适应网络 |
| `models/` | `koop_model.py` 等模型封装 |
| `dynamics/` | 被控对象模型（单车、机器人、轨迹生成） |
| 根目录教程 notebook | `Coupled_pendulum_*`、`Serial_Manipulators_*`、`Planar_Quadrotor_*`、`single_vehicle_*`、`tf3`—`tf9`、`test_single_lv*`、`testlv7z*` 等 |

若你是上游作者，希望这些文件被移除或改以其它许可发布，请开 issue，相关路径会被调整。

## 2. 未发表论文稿件与投稿/审稿往来材料

仓库包含未发表的论文稿件与期刊往来函件：

- `paper_dcn_tf12_draft/`：论文 LaTeX 稿件各版本
- `revision_2026/00_baseline/`：原稿、期刊决定信
- `revision_2026/connector_r3_4/review_comments.txt`：编辑信与审稿意见
- `revision_2026/paper_v4/review/`：审稿意见映射

这些材料的著作权属作者本人。其中标注为期刊往来函件的内容属**保密通信**，
公开可读不等于可以转载或引用——请勿复制、转述或用于任何公开场合。

## 3. 第三方文献提取文本

`paper_dcn_tf12_draft/**/extracted_text/` 下是若干已发表论文的文本提取结果，
仅用于本项目内部的文献对照，**著作权属各自出版方**，不随本仓库授权。
