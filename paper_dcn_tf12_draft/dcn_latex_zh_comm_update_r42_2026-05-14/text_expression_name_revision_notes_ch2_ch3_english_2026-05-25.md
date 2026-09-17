# 第 2、3 章文字表述与命名连续性修改说明

对象文件：

- 输入基础：`manuscript_en_symbolfix_ch2_ch3_2026_05_25.tex`
- 修改输出：`manuscript_en_ch2_ch3_textfix_2026_05_25.tex`
- 参考审计：`text_expression_name_audit_ch2_ch3_2026-05-25.md`

修改范围：第 2 章 `System Modeling and Problem Definition` 与第 3 章 `\Method{} Method`。本轮不改第 4 章及后文实验章节。

## 总体处理原则

本轮不是继续改公式，而是把前一版已经修好的符号系统转成英文投稿正文，并清理审计文件指出的术语跳变、内部实现口吻和实验标签前置问题。公式编号、标签、核心变量名、图文件路径和表格结构均保留，以避免破坏后文引用。

## 自查后新增或确认的问题

1. 第 2、3 章仍为中文正文，但文件名和前文已经按英文稿组织，导致稿件语言层级不一致。
2. 第 2 章提前出现 `Koopman 残差补偿`，在 Koopman predictor 尚未定义前抢先声明方法模块。
3. 通信模型中直接使用 `\Pi_x`、lifted state 和 `\hat z`，但 Koopman lifting 到第 3 章才定义，缺少过渡。
4. “载荷/团队中心”混用。若不定义独立 team center，会让读者误以为有两个中心量。
5. 方法总览中把 high-communication-noise、6D/raw Koopman 等实验标签提前放进方法章，容易显得像内部实验说明。
6. “风险触发式货物保护”和公式中的曲率窗口触发条件不完全一致。
7. 图题中存在工程口语：`模型子程序集`、`安全 veto`、`plant`。
8. 离线数据工况名、batch/snapshot/run 等代码词没有作为数据标签解释。
9. `路径上下文变量`过于抽象，不利于复现 Koopman observation 结构。
10. `严格证书模式`像代码开关，方法章需要改成审计设置。
11. `horizon`、`fallback`、`degraded fallback`、`trim` 等术语未统一。
12. 第 3 章硬编码“3.6/3.7”，重排后不稳。
13. “相位角色调度器”突然出现，前文没有定义“相位”的技术含义。

## 实际修改策略

1. 语言层面：第 2、3 章标题、正文、表题、图题全部改成英文；保留后文中文部分不动。
2. 模块铺垫：第 2 章只定义物理模型、通信图和退化变量，不提前声称 Koopman 残差补偿已经构成预测模型。
3. Predictor 过渡：在通信退化模型中明确 `\eqref{eq:delay_prediction}` 是第 3 章 lifted predictor 的预留接口；不开启 Koopman 时可退化为运动学外推或 ZOH。
4. 中心量统一：明确 rigid payload center is used as the representative team center，后文 team-level tracking 默认指 payload-center quantity。
5. 方法总览改写：用 method-module 语言替换实验标签堆叠，把 learning、communication、high-curvature、payload protection、FDI/FTC 和 certificate 分别对应到后文证据。
6. 货物保护命名：将 risk-triggered wording 改为 curvature-window payload-protection switch，与 `\sigma_k` 的曲率窗口公式一致。
7. 图题术语：把 `model subprogram set` 类表达改成 `model submodules`，把 `veto` 写成 `safety-veto signals`，把 `plant` 改成 `controlled vehicle system`。
8. 离线数据：将 nominal clean、high communication noise、single fault、mixed fault/noise 明确写成 scenario tags；batch/snapshot/run 作为数据生成术语解释。
9. Koopman observation：补充 path context examples，包括 reference curvature、reference heading、path progress、local path preview points 和 high-curvature window indicators。
10. 证书措辞：把 strict certificate mode 改成 conservative audit setting，避免像主方法的必需开关。
11. MPC 术语：统一为 prediction horizon、degraded fallback、conservative fallback、bounded trim term。
12. 执行层：删除硬编码章节号，用 previous subsection / this subsection 表达上下文关系。
13. 角色调度：删除未定义的 phase-role wording，统一为 role scheduler。

## 关键替换结果

- 第 2 章标题改为 `System Modeling and Problem Definition`。
- 第 2.1 节改为 `Vehicle Dynamics in the Global Frame`。
- 第 2.2 节改为 `Path-Coordinate Errors`。
- 第 2.3 节改为 `Rigid Payload and Connection Errors`。
- 第 2.4 节改为 `Communication Graph and Degradation Model`。
- 第 3 章标题改为 `\Method{} Method`。
- 第 3.1 节改为 `Method Overview and Naming`。
- 第 3.2 节改为 `Upper-Layer Equivalent 4WS and Local Path Publication`。
- 第 3.3 节改为 `Offline Data Generation`。
- 第 3.4 节改为 `Bilinear Koopman Lifting`。
- 第 3.5 节改为 `Input-Aware Stability Projection and Residual Bound`。
- 第 3.6 节改为 `Base Koopman-MPC and Parallel Protection Branches`。
- 第 3.7 节改为 `Execution-Layer Fault Protection and Role Scheduling`。

## 保留不动的内容

1. 所有公式标签和编号逻辑保留，如 `eq:world_kinematics`、`eq:delay_prediction`、`eq:bilinear_koopman`、`eq:mpc_cost` 等。
2. 图文件本身未重绘，因此图内嵌文字若来自原始图片仍保持原样；本轮只英文化图题和正文引用。
3. 第 4 章及后文实验/结论仍沿用原稿语言，等待后续单独英文化。

## 编译前检查结果

第 2、3 章范围内已做中文字符扫描，未发现中文正文残留。后文第 4 章及实验部分仍有中文，这是本轮刻意不改的范围外内容。

## 下一步建议

若要形成完整英文投稿稿件，下一轮应继续处理第 4 章稳定性证明、实验章节、结论、图内嵌中文标签和参考文献标题。否则当前 PDF 会呈现“引言 + 第 2/3 章英文，后续章节中文”的中间状态。
