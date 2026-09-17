# Fig. 2 正交版模块数据流图审查意见

审查对象：`figures/fig2_nrkdcc_module_dataflow_orthogonal_20260528.png`

## 总体判断

这一版相比上一版已经明显接近论文可用图：大模块分层清楚，M1 作为离线学习层置顶，M2--M5 作为在线闭环链路置于下方，整体逻辑比原先更容易读。但是当前仍属于“结构正确、排版未最终打磨”的状态，主要问题集中在大模块贴得过紧、M3/M4 交界处线条重合、若干信号文字压线，以及部分箭头太短导致信息流方向不够明确。

建议再做一轮版式优化后进入稿件：保留现在的长矩形整体布局，但在大模块之间留出稳定缝隙，并把跨模块连接线分成不同通道，避免任何信号线压在模块边框上。

## 需要细化并固定的绘图规则

1. 大模块之间需要留缝隙，但不能让整体散开。
   - M1 与下方 M2--M5 之间建议留 `8 px` 左右的水平缝隙。
   - M2/M3/M4/M5 之间建议留 `8--12 px` 的竖向白色缝隙。
   - 所有大模块外边缘仍应对齐成一个整体长矩形：左边界、右边界、上边界、下边界保持齐整。
   - 缝隙应作为“模块边界”和“跨模块信号走廊”，不要再让连接线贴着模块边框走。

2. 所有连接线保持横平竖直，并分层走线。
   - 同一个边界处不能有两条或三条不同含义的线重合。
   - 平行线之间至少留 `10--14 px` 间距。
   - 连接线到大模块边框至少留 `8--10 px`，避免看起来像边框的一部分。
   - 箭头前应有至少 `24--32 px` 的可见直线段，不能箭头刚离开框就立刻进入另一个框。

3. 信号标识只用无背景文字，但必须避开线条。
   - 信号文字不要带灰色底框。
   - 每个信号标签距离最近的线至少 `6--8 px`。
   - 标签距离模块框或小模块框至少 `8--10 px`。
   - 标签不要放在拐角、箭头头部、两条线交汇处或模块边界线上。
   - 如果信号名较长，允许两行显示，但两行都要落在空白区域中，不能有线穿过文字。

4. 箭头和线段长度要统一。
   - 主要前向数据流建议使用较长直线，突出闭环主链路。
   - 短连接只用于模块内部紧邻小模块，不建议用于跨大模块连接。
   - 箭头大小、线宽、虚线间距要统一，避免同类信号视觉权重不一致。

## 具体问题与修改建议

### 1. 大模块贴合过紧

当前 M1 下边框、M2/M3/M4/M5 上边框基本贴在一起，M2/M3/M4/M5 之间也几乎无缝连接。这样虽然形成了长矩形，但模块边界太重，跨模块箭头容易被误认为边框的一部分。

建议：

- M1 与下方模块之间增加 `8 px` 缝隙。
- M2--M5 之间增加 `8--12 px` 缝隙。
- M2、M3、M4、M5 的高度保持一致，底边齐平。
- M1 的左右边界与下方整体外边界对齐，保持整体“长矩形”感。

### 2. M3/M4 边界处线条重合

第二张局部图中，M3/M4 交界附近出现了多条不同信号线共用同一竖向通道的问题，包括候选控制输出、红色保护/收紧边界返回线、灰色反馈虚线等。它们在视觉上重叠或贴边，读者很难判断每条线分别从哪里来、到哪里去。

建议把 M3/M4 之间固定为三条独立通道：

- 上通道：M3 到 M4 的前向候选控制与预测轨迹，标注 `u_i^*, predicted trajectory, margins`。
- 中通道：M4 内部 FDI/FTC 相关的诊断量输入，标注 `y_i, yhat_i, r_i`。
- 下通道：M4 回到 M3 的保护收紧信息，标注 `tightened bounds, contracted ref.`。

这三条通道不能重合，也不要直接压在 M3/M4 的大模块边框上。建议每条线在进入 M4 前有一段清楚的水平线，并在 M4 内部再转向对应小模块。

### 3. 第三张局部图中文字压线

第三张局部图中，`y_i, yhat_i, r_i` 的文字与竖向虚线重叠，同时靠近箭头和边界，导致读者会把文字、线和箭头混在一起。

建议：

- 将 `y_i, yhat_i, r_i` 移到竖向虚线左侧或右侧的空白区域。
- 文字不要跨越虚线，也不要贴在箭头头部。
- 如果空间不足，可将信号线先水平进入 M4，再向下转向 FDI residual monitoring；标签放在水平线的上方。
- 标签与线条保持 `6--8 px` 间距。

### 4. `u_i^*, predicted trajectory, margins` 标签位置不佳

当前该标签位于 M3/M4 边界附近，并被线条、边框和模块内部元素夹住，阅读不稳定。

建议：

- 让 Candidate control sequence 的输出线从 M3 右侧中下部水平进入 M4。
- 标签放在这条水平线的上方，保持两行以内。
- 推荐写法：`u_i^*, predicted trajectory, margins`。
- 如果正文中统一使用时刻索引，可以改为 `u_k^*, predicted trajectory, margins`，但全文和图注必须一致。

### 5. `tightened bounds, contracted ref.` 红色返回线不清楚

当前红色虚线在 M3/M4 边界附近与其他线靠得太近，还存在贴边、短折线和局部重合的问题。

建议：

- 红色返回线单独走下方通道，从 M4 的 Projection and tightening 输出，回到 M3 的 Communication-quality-aware Koopman-MPC。
- 不要让红色线沿 M3/M4 边框向上或向下贴边走。
- 标签 `tightened bounds, contracted ref.` 放在红线水平段上方，而不是放在转折处。
- 若空间不足，可把 Projection and tightening 稍微下移，给红色返回线留出完整横向通道。

### 6. M4/M5 边界处输出和反馈应拆开

M4 到 M5 的 `u_k^safe` 输出目前基本合理，但箭头和文字仍偏紧。M5 反馈 logs 的灰色虚线也在 M4/M5 边界附近压得较密。

建议：

- Safe command output 与 Command publication and communication 尽量中心线对齐，使 `u_k^safe` 成为一条较长、清楚的水平箭头。
- `u_k^safe` 标签放在线段上方或下方，距离箭头头部至少 `12 px`。
- M5 的反馈 logs 建议先汇入底部反馈总线，再分别分支到 M3/M4。
- 不要让反馈虚线贴着 M4/M5 边界竖直走，避免看成模块分隔线。

### 7. M2/M3 边界处两个输入信号需分开

M2 输出到 M3 的参考路径和通信质量信息是两类不同信息，但当前边界处箭头较短，标签也偏靠边。

建议：

- `P_{i,k-d}^{tmp}, r_ref` 作为参考/路径包输入，进入 Delay-compensated remote-state prediction。
- `q_{ij,k}, tau_{ij,k}, ell_{ij,k}` 作为通信质量输入，进入 Communication-quality-aware consensus。
- 两条线在 M2/M3 缝隙处上下分开，至少相隔 `14 px`。
- 标签放在 M3 内侧入口附近，而不是贴在大模块边框上。

## 命名与符号建议

下面这些名称建议统一到图、图注和正文中：

- `M1 Offline learning layer`
- `M2 Upper-layer reference and communication`
- `M3 Online prediction and consensus-MPC`
- `M4 Safety, FDI/FTC, and certificate`
- `M5 Vehicle-payload environment and feedback`
- `Koopman model interface`
- `Communication-quality-aware Koopman-MPC`
- `FDI residual monitoring`
- `FTC command reallocation`
- `Certificate metrics`
- `Projection and tightening`
- `Degraded fallback`
- `Safe command output`

信号标签建议采用“图中短写、正文/图注解释”的策略：

- 图中：`Phi_theta, A, B, N_l, C, bounds`
- 图中：`P_{i,k-d}^{tmp}, r_ref`
- 图中：`q_{ij,k}, tau_{ij,k}, ell_{ij,k}`
- 图中：`y_i, yhat_i, r_i`
- 图中：`u_i^*, trajectory, margins`
- 图中：`tightened bounds, contracted ref.`
- 图中：`u_k^safe`
- 图中：`V, margins, force proxy, g(x,u)`

如果图中符号太挤，可以在图内用更短标签，图注补充完整含义。例如图中写 `model package`，图注解释包含 `Phi_theta, A, B, N_l, C` and constraint bounds。

## 推荐的最终走线路径

1. M1 到 M3：
   - Model package 从 M1 内部向下出线。
   - 先进入 M1/M3 之间的水平缝隙，再向下进入 Koopman model interface。
   - 标签放在线段旁边，不要压在 M1 下边框或 M3 上边框上。

2. M2 到 M3：
   - Reference communication 输出参考包到 Delay-compensated remote-state prediction。
   - Link-quality monitor / Reference communication 输出通信质量到 Communication-quality-aware consensus。
   - 两条线分上下通道，不重合。

3. M3 到 M4：
   - Candidate control sequence 输出候选控制、预测轨迹和裕度到 M4。
   - 线条水平跨过 M3/M4 缝隙，标签放在水平段上方。
   - 进入 M4 后再分配到 FDI residual monitoring、FTC command reallocation 或 Certificate metrics。

4. M4 内部：
   - FDI residual monitoring 向 FTC command reallocation 输出故障残差信息。
   - FTC command reallocation 向 Certificate passes? 提供重分配后的命令。
   - Certificate passes? 的 `yes` 分支进入 Safe command output。
   - `no` 分支进入 Projection and tightening 或 Degraded fallback。
   - Projection and tightening 的结果返回 M3，作为 tightened bounds / contracted reference。

5. M4 到 M5：
   - Safe command output 输出 `u_k^safe` 到 Command publication and communication。
   - M5 内部依次为 Command publication and communication、Vehicle-payload system、Feedback logs/errors/forces/constraints。

6. M5 回到 M3/M4：
   - Feedback logs 先接到底部反馈总线。
   - 从反馈总线分别分支到 Observation fusion and lifting、FDI residual monitoring、Certificate metrics。
   - 不要让反馈虚线与 M3/M4 或 M4/M5 的大模块边框重合。

## 建议的版式参数

- 大模块间缝隙：`8--12 px`
- M1 与下排模块间缝隙：`8 px`
- 平行线间距：不少于 `10--14 px`
- 标签到线距离：不少于 `6--8 px`
- 标签到小模块边框距离：不少于 `8--10 px`
- 箭头头部前直线段：不少于 `24--32 px`
- 大模块边框线宽：约 `1.4--1.8 pt`
- 连接线线宽：约 `1.0--1.2 pt`
- 反馈虚线线宽：约 `1.0 pt`
- 模块标题字号：约 `9--10 pt`，加粗
- 小模块文字字号：约 `7.5--8 pt`
- 信号标签字号：约 `6.2--6.8 pt`

## 修改优先级

高优先级：

1. 给 M1/M2/M3/M4/M5 大模块之间增加缝隙。
2. 彻底拆开 M3/M4 边界处重合的蓝线、红线和灰色虚线。
3. 移开 `y_i, yhat_i, r_i`，避免文字压线。
4. 移开 `u_i^*, predicted trajectory, margins` 和 `tightened bounds, contracted ref.`，避免标签压边框或压线。

中优先级：

1. 拉长 M4 到 M5 的 `u_k^safe` 输出箭头。
2. 优化 M2 到 M3 的两个输入信号通道。
3. 统一箭头长度、箭头头部大小、虚线样式和线宽。

低优先级：

1. 微调 M2 与 M5 内部空白，使小模块分布更均匀。
2. 将过长信号标签移到图注解释，图中保留短标签。
3. 根据最终论文正文统一 `u_i^safe` / `u_k^safe`、`P_{i,k-d}^{tmp}` / `P_{i,k-\tau}^{tmp}` 等符号写法。

## 最终验收清单

- [ ] 大模块之间有清楚缝隙，但整体仍是长矩形布局。
- [ ] 所有跨模块连接线均横平竖直。
- [ ] M3/M4 边界没有任何两条不同信号线重合。
- [ ] M4/M5 边界的 `u_k^safe` 输出清楚，箭头不短。
- [ ] 所有信号标签均无背景色，且不与线条、箭头、边框重叠。
- [ ] 每个箭头的起点和终点都能直接判断。
- [ ] 所有小模块名称都能在正文或图注中找到对应表述。
- [ ] 图注解释了颜色、虚线、实线、红色保护链路和灰色反馈链路的含义。

## 建议图注补强方向

图注不宜只写“signal-flow diagram”，建议补充说明五个模块和三类线：

> Fig. 2. Online/offline module-level dataflow of the NR-KDCC architecture. M1 provides the offline Koopman model package; M2 supplies reference and communication-quality packets; M3 performs delay-compensated prediction and communication-quality-aware Koopman-MPC; M4 applies FDI/FTC, certificate checking, command reallocation, and constraint tightening; and M5 represents command publication, vehicle-payload execution, and feedback logs. Solid arrows denote forward command/data flow, red arrows denote safety reconfiguration or constraint-tightening feedback, and gray dashed arrows denote measured feedback, logs, forces, and constraint information.

这类图注可以降低读者对颜色的猜测，也能解释为什么图中存在红色返回线和灰色反馈线。
