# 文献证据阶段性总结

## 覆盖情况

本轮建立了 `literature_evidence_matrix_zh.csv`，覆盖 20 条可写入 related work 的记录：

- Koopman/车辆 MPC：5 条。
- 多机器人/多车协同运输：5 条。
- CAV/DMPC/通信丢包/时延/DoS：8 条。
- 网络延迟综述和学习 MPC 背景：2 条。

## 当前可支撑的写法

- 可以写“近年 Koopman-MPC 已用于自动驾驶车辆轨迹跟踪和约束控制，但多数工作集中在单车动力学预测，不处理多车载荷协同、通信退化和故障重构”。
- 可以写“协同运输研究已有 formation control、distributed predictive control、MARL 和系统平台，但通信时延/丢包与载荷安全约束的联合处理仍不足”。
- 可以写“CAV/vehicle platoon 领域已有 Markov packet loss、DoS、communication loss、UKF-MPC 和鲁棒 DMPC 工作，但多数关注纵向 platoon/string stability，而本文转向载荷中心跟踪、连接约束和货物受力安全”。

## 当前不能支撑的写法

- 不能写“本文是第一个处理通信退化的多机器人运输控制方法”，因为协同运输和网络控制已有相关工作。
- 不能写“本文优于所有 CAV/DMPC 方法”，因为当前没有完整 physical-model DMPC baseline。
- 不能把 arXiv/ResearchGate 条目全部当作 final-ready peer-reviewed citation。最终英文稿需要优先引用 publisher/IEEE/Elsevier/Springer/MDPI 官方页或作者公开稿。

## 还需补充

- 每条文献的 BibTeX。
- 对 `ISA Transactions` DoS DMPC 条目的 DOI 精确核验。
- 将 V2 条目中 publisher 页不足的条目升级为 V3。
- 结合最终贡献段，压缩为 14-18 条核心引用，其他放补充材料或相关工作长表。
