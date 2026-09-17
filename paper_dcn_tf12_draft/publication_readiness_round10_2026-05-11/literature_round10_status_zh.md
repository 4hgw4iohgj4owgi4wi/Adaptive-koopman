# Round10 文献证据状态

## 1. 已完成

- 修正 `literature_evidence_matrix_zh.csv` 中两个 DOI：
  - DoS-DMPC：`10.1016/j.isatra.2024.07.011`
  - EJC 鲁棒 DMPC：`10.1016/j.ejcon.2024.101023`
- 新增核心 BibTeX 草案：
  - `core_references_round10.bib`
- 当前 BibTeX 覆盖：
  - Koopman vehicle MPC
  - Koopman 误差理论
  - cooperative object transportation
  - CAV/DMPC/packet loss/DoS/communication loss
  - network latency review
  - learning MPC

## 2. 仍未达到 100% 的地方

- 部分 publisher 页面条目的作者姓名仍需从官方元数据补全，BibTeX 中已用 `note` 标出。
- arXiv 条目若最终有期刊版本，应优先换成期刊版本。
- 还需要把 20 条证据压缩为主文 14-18 条核心引用，并把其余条目放入补充或 related-work 长表。
- 需要逐条写入中文稿/英文稿中的引用位置，而不是只保留矩阵。

## 3. 可写入引言的贡献-文献映射

| 贡献 | 主要支撑文献 | 本文改进边界 |
|---|---|---|
| 稳定投影双线性 Koopman-MPC | Kim et al. 2025; Chen and Lv 2024; Philipp et al. 2023; Cibulka et al. 2021 | 从单车/车辆预测控制扩展到四车刚性载荷协同运输，并加入连接安全和故障/通信退化。 |
| 载荷协同运输建模 | RAS 2024 cooperative object transportation; CEP 2024 formation transport; Mechatronics 2024 MARL transport; Kinetik review | 不只做 formation 或平台验证，而是把团队中心、角点连接误差和载荷受力审计放入同一控制证据链。 |
| 通信退化与时延补偿 MPC | Bian et al. 2025; DoS-DMPC 2024; TRB 2025 communication loss; Sensors latency review | 从 longitudinal platoon/string-stability 场景转向协同运输中的连接约束、载荷中心跟踪和质量感知一致性权重。 |
| FDI/FTC 与证书保护 | Robust DMPC / learning MPC / networked predictive control works | 将执行器效率估计、切换容错和 Lyapunov 型证书记录嵌入 Koopman-MPC 闭环。 |

## 4. 引用写作边界

- 不能写“本文第一个处理通信退化协同运输”，只能写“联合处理 Koopman 预测、通信退化、执行器故障和载荷连接安全的组合仍不足”。
- 不能写“全面优于现有 DMPC/CAV 方法”，因为 stronger physical-model DMPC baseline 尚未完成。
- 可以写“现有 CAV/DMPC 通常关注纵向 platoon 和 string stability，而本文面向四车刚性载荷协同运输的连接约束和载荷受力审计”。
