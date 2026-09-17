# Round8 完成度评分

## 当前评分

| 维度 | Round7 估计 | Round8 当前 | 依据 |
|---|---:|---:|---|
| 主线/claim 边界 | 70% | 85% | 已形成主线、贡献、可写/不可写 claim 和证明边界包。 |
| 方法/证明 | 60% | 85% | 已明确完整控制链到局部闭环和 UUB/practical boundedness 证明口径；表述限定为有界扰动下的实践有界。 |
| 实验工程 | 70% | 85% | 已有 output-root、provenance、ZOH surrogate、异常续跑、success gate、E3/E7 n=20、后台日志容错。 |
| 投稿级数据 | 25% | 70% | E0 targeted 主对比、E3 证书统计和 E7 连接安全统计均已达 paired n=20；E2/E1/dose/topology 和 AKE-A/强 DMPC baseline 未完成。 |
| 文献证据 | 25% | 70% | 已有 20 条带来源链接、模块归属、限制和写法建议的证据矩阵。 |
| 投稿稿/投稿包 | 30% | 40% | 写作材料增强，但尚未回填最新中文 DOCX/英文 LaTeX。 |

## 为什么 70% 仍不等于可直接投稿

投稿级数据已经达到本轮停止线 70%，但还不能视为“投稿级数据全部完成”。完整投稿前仍建议满足：

- E0 或 E2 至少有一组 baseline-facing paired `n>=20` 主对比。
- E3/E7 主结果达到 paired `n>=20`。
- baseline 至少明确 `AKE-M` 并在所有表中固定，若要声称优于原文则必须有 `AKE-A`。
- 非 Koopman baseline 至少有一个比 ZOH surrogate 更可信的 physical-model DMPC 或等价网络控制方法。
- E1 fresh Koopman/AKE 多训练 seed 完成。
- dose-response/topology recovery 至少有一组可统计数据。

当前 Round8/Round9 已补到“E0 targeted 主对比 n=20 + E3/E7 正式 n=20 + gate 表 + 代表性 smoke”，所以投稿级数据从 25% 提升到 70%。但这不是“可直接投稿完成”，因为 E2 全量消融、E1 fresh、dose/topology 和更强 baseline 尚未完成。

## 已达到用户目标的部分

- 主线/claim 边界：达到约 85%。
- 方法/证明：达到约 85%。
- 实验工程：达到约 85%。
- 文献证据：达到约 70%。
- E3 证书统计：达到 paired n=20。
- E7 连接安全统计：达到 paired n=20。
- E0 mixed fault/noise targeted 主对比：达到 paired n=20。

## 未完全解决的部分

- 投稿级数据：当前约 70%，达到本轮停止线，但仍不是最终完成。主要阻塞是 E2 全量消融、AKE-A/E1/dose/topology 和 stronger non-Koopman baseline。

## 下一轮必须做什么才能从 70% 推到投稿前水平

1. 跑 `E2 --full-final-seeds --scenarios sine_mixed_fault_noise`，形成核心消融统计。
2. 补 E1 fresh Koopman/AKE 多训练种子，至少给出预测误差和训练 seed 方差。
3. 补 dose-response/topology recovery 至少一组统计数据。
4. E0 全场景全方法 n=20 作为最后的大批次，若算力不足，主文只写 targeted 主对比并把全场景放 pending。
5. 补 AKE-A 或 stronger physical-model/DMPC baseline，否则所有“优于原文 baseline”都必须继续降级。
