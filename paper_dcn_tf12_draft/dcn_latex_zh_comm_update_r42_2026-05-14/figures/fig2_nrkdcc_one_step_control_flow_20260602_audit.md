# fig2_nrkdcc_one_step_control_flow_20260602.drawio 图件审计

审计对象：

- `fig2_nrkdcc_one_step_control_flow_20260602.drawio`
- 同目录预览：`fig2_nrkdcc_one_step_control_flow_20260602_browser_preview.png`
- 当前 LaTeX 主文仍引用：`figures/fig_nrkdcc_control_flow_visio_crop.pdf`
- 审计时间：2026-06-02

## 总体结论

当前图的技术覆盖面是对的：它把离线 Koopman 学习与 IRSP 投影、在线参考发布、通信质量处理、Koopman rollout、一致性 MPC、FDI/FTC、证书检查、回退与 plant 反馈放进了同一张图，基本对应 NR-KDCC 的核心模块。

但当前版本不建议直接替换主文图。更合适的分类是：`Needs redraw before main text`。原因不是概念错误，而是主文图的可读性、语义层级和投稿导出状态还不够安全。若直接放入双栏论文，审稿人很可能看成“术语堆叠图”，而不是一张能快速说明方法机制的流程图。

建议处理方式：

- 主文版：保留模块级信号流，压缩到 8-12 个核心框，去掉大部分公式和小符号块。
- 补充材料版：保留当前 one-step 细节，但改成清晰泳道图，并配一个缩写/信号表。
- 当前 drawio 文件：作为详细机制草图保留，不要直接用浏览器截图入稿。

## 主要不足

### 1. 标题与内容存在语义冲突

图题写的是 `One-step control flow of NR-KDCC within one sampling period`，但图上方包含 `OFFLINE BAND`，包括 offline scenario data、bilinear regression、IRSP stability projection 和 model/certificate package。离线训练与稳定投影不是单个采样周期内发生的动作。

这会带来两个审稿风险：

- 读者可能误解为每个采样周期都重新训练 Koopman 模型和 IRSP 投影。
- “one-step control flow” 与“offline band”混在同一时间轴上，时间层级不清。

建议把图题改为：

`Offline model package and online one-step control flow of NR-KDCC`

或者删除图内标题，把时间层级放入图注说明：离线层在部署前完成，在线层在第 k 个采样周期执行。

### 2. 主文可读性偏低

drawio 中当前画布为 1800 x 680，包含 28 个节点、27 条边。多数框内字号是 8-10 pt，边标签也包含较多数学符号。若按当前主文 `width=0.92\textwidth` 缩放，实际阅读会比较吃力，尤其是：

- `Communication processing and link-quality monitor` 框内的 `q_ij,k, q_k^net, tau, loss, bias/noise`
- `Observation fusion and Koopman rollout` 框内的 lifted-state 公式链
- `C-mode scheduler and consensus MPC` 中的 `C0/C1/C2/C3, min J, tightened constraints`
- 底部 feedback bus 的长标签
- 右侧证书、FDI/FTC、fallback、plant 之间的多条红色/灰色箭线

这类信息密度适合内部设计文档，不适合主文第一张方法流程图。主文图应让读者先看清“模块如何连接”，公式细节放到正文、图注或补充表中。

### 3. 缺少图例，颜色和线型语义不自解释

当前图用了蓝色、绿色、浅蓝、红色、紫色和灰色虚线，大体上能对应离线、通信/参考、预测/MPC、安全、plant、反馈等层级，但图中没有图例。读者需要猜：

- 蓝色浅底是否代表离线模型包；
- 绿色是否代表参考与通信；
- 红色是否代表故障/安全；
- 灰色虚线是否代表模型包输入、反馈总线，还是非实时通道；
- 红色实线是否代表 failure path；
- 黑/灰实线是否代表正常数据流。

建议在主文版中加一个极简图例，或直接把 lane 标题写成：

- M1 Offline learning package
- M2 Reference and network layer
- M3 Koopman prediction and consensus MPC
- M4 Safety / FDI / FTC / certificate guard
- M5 Vehicle-payload plant and feedback

这样颜色只是辅助，不承担唯一解释功能。

### 4. 模块层级和算法分支混在一起

当前图把大模块和小操作放在同一视觉层级，例如：

- `Communication processing and link-quality monitor` 是模块；
- `z^{-tau}`、`loss?` 是局部信号处理；
- `C-mode scheduler and consensus MPC` 是模块；
- `risk compare`、`sat[0,1]` 是局部计算；
- `FDI/FTC and command projection` 是模块；
- `FDI residual`、`FTC realloc.` 是子操作。

这种混合会让读者难以判断哪些是本文贡献模块，哪些只是实现细节。建议主文版只保留大模块，子操作用 1-2 个关键词写在模块内部，或者编号到图注中说明。

### 5. 右侧安全闭环过密，容易误读

右侧从 `FDI/FTC and command projection` 到 `Certificate passes?`，再到 `Safe command publication`、`Projection/tightening/fallback`、`Vehicle-payload plant` 的区域信息最重要，但也是当前最拥挤的区域。

具体问题：

- `pass` 与 `fail` 分支视觉距离太近，且 fail 后的 fallback 线绕行较长。
- `m6 -> m7` 的 fallback/tightened command 线在底部绕行，容易和 feedback bus 混淆。
- `FDI residual` 与 `FTC realloc.` 小框看起来像独立模块，但实际更像 `FDI/FTC and command projection` 的内部步骤。
- `Certificate passes?` 中的 `m_k >= -epsilon_m` 需要和正文稳定性证明的符号约定完全一致，否则容易被审稿人抓住问“margin 正负号如何定义”。

建议把安全层重画成一个清晰的局部闭环：

`candidate command -> FDI/FTC projection -> certificate guard -> safe command`

其中 certificate guard 下方只保留一条 `fail -> projection/tightening/fallback -> safe command` 的短回路。

### 6. 关键贡献模块没有被同等显式标出

当前图已经包含 Koopman、通信、FDI/FTC、证书，但以下模块在主文中很重要，却在图中不够醒目：

- 角色调度 / role scheduling
- 货物保护 / payload protection / force-risk switch
- 上层-下层路径通信与临时期望路径的跨层链路
- 连接几何约束与载荷受力审计

图中有 `C-mode scheduler`、`risk compare`、`force proxy` 等词，但这些词不足以让读者直接对应正文贡献。建议至少把 `C-mode scheduler` 改成：

`Mode / role scheduler and consensus MPC`

把 `risk compare + sat[0,1]` 合并或改成：

`payload-protection / force-risk switch`

否则图和正文贡献之间的映射不够清楚。

### 7. “四车协同运输”的物理对象不够直观

图里只有 `Vehicle-payload plant and environment feedback` 一个紫色框，没有表现四车、载荷、邻接连接或上层参考如何作用到车辆 i。对于 NR-KDCC 这篇稿件，审稿人需要马上知道这不是普通单车 MPC，而是四车刚性载荷协同运输。

建议主文图至少增加一个轻量提示：

- 在 plant 框内写 `4 vehicles + rigid payload`
- 或在通信/观测融合处明确 `neighbor states x_j, connection distances d_ij`
- 或在图注中明确“vehicle-payload plant 表示四车刚性载荷系统”

不要让读者到正文后面才知道协同运输对象是什么。

### 8. 反馈总线标签过长且与多条虚线重叠

底部 feedback bus 写了：

`x_{k+1}, xi_L,k+1, e_y, e_psi, e_c, F proxy, constraints, logs`

这个标签覆盖的变量很多，但其作用不清：有些反馈给误差计算，有些给通信监测，有些给 FDI，有些给证书。当前多条虚线从右下返回左侧，会让图显得线缆过多。

建议主文版只保留一条：

`closed-loop feedback: states, errors, forces, constraints, logs`

需要细分时，用图注说明各变量进入对应模块，不要在图内列完整变量。

### 9. 英文标签与中文主文需要统一策略

当前 LaTeX 文件是中文稿件家族，旧图也有较多中文标签；新图全部使用英文。两者都可以，但必须统一策略：

- 若最终中文稿：建议把主要模块中文化，英文缩写保留在括号中。
- 若最终英文/DCN稿：英文标签可保留，但图注需要定义 `IRSP`、`FDI`、`FTC`、`C0-C3`、`MUX`、`sat[0,1]` 等缩写和符号。

当前图内的 `MUX`、`risk compare`、`sat[0,1]`、`C-mode` 对普通审稿人不够自解释。

### 10. 预览图不是可投稿导出图

同目录的 `fig2_nrkdcc_one_step_control_flow_20260602_browser_preview.png` 是 diagrams.net 浏览器界面截图，含菜单栏、侧边栏和网格，不是论文插图。当前尚未看到同名干净 `pdf/svg/png` 导出版。

入稿前必须导出：

- `fig2_nrkdcc_one_step_control_flow_20260602.pdf`
- `fig2_nrkdcc_one_step_control_flow_20260602.svg`
- 可选高分辨率 PNG 仅用于预览

导出要求：

- 不带 diagrams.net UI；
- 白底或透明底；
- crop to content；
- 线宽和文字在 `0.92\textwidth` 下仍可读；
- PDF/SVG 中数学符号不乱码。

## 建议的主文版重构

主文版建议采用 5 个泳道或 5 个大模块，不要保留当前全部小框。

推荐结构：

```text
M1 Offline package:
data coverage -> bilinear Koopman lifting/regression -> IRSP projection -> model/certificate package

M2 Reference and network:
reference path + 4WS local path -> link-quality monitor / delay-loss processing

M3 Online prediction and MPC:
observation fusion -> Koopman rollout -> quality-aware consensus MPC

M4 Safety guard:
FDI/FTC projection -> role/payload protection -> certificate guard -> fallback if failed

M5 Plant and feedback:
safe command -> 4-vehicle payload plant -> states/errors/force/constraint logs
```

主文图中的每个框最多两行文字。公式只保留关键符号，例如 `q_ij,k, tau, loss`、`z_{k+1|k}`、`u_k^safe`。其余公式放入正文。

## 若保留详细版，建议改成补充图

若希望保留当前 28 节点版本，它更适合补充材料或内部方法说明。补充版应改成：

- 明确 `offline` 与 `online k -> k+1` 的时间分隔；
- 给每个大模块加编号 M1-M5；
- 把小操作放在对应模块内部，不和大模块平级；
- 右侧安全层改成局部闭环；
- 添加图例说明颜色、实线、虚线；
- 增加缩写表：IRSP、4WS、FDI、FTC、MUX、C-mode、U_s、w bounds、m_k、epsilon_m。

## 建议替换图内文字

可以按下表修改当前 drawio 文本。

| 当前文字 | 建议文字 | 原因 |
|---|---|---|
| One-step control flow of NR-KDCC within one sampling period | Offline package and online one-step NR-KDCC control flow | 避免离线训练被误解为单周期动作 |
| OFFLINE BAND | M1 Offline model package | 和在线泳道命名一致 |
| Offline scenario data | Data coverage for training and stress cases | 强调覆盖性，避免像实验场景堆叠 |
| Model and certificate package | Koopman model, bounds and certificate templates | 更准确，避免暗示证书完全由离线包闭式给出 |
| Environment-derived reference path | Reference path and payload progress | 更接近在线输入 |
| Upper 4WS local path publisher | Upper 4WS local-path publisher | 可保留，但应在图注定义 4WS |
| Communication processing and link-quality monitor | Link-quality monitor and delay/loss compensation | 突出网络韧性机制 |
| C-mode scheduler and consensus MPC | Mode/role scheduler and consensus MPC | 对应正文角色调度 |
| risk compare / sat[0,1] | payload-protection / force-risk switch | 对应货物保护贡献 |
| FDI/FTC and command projection | FDI/FTC command projection | 更短 |
| Projection / tightening / fallback | Projection, tightening or degraded fallback | 表示条件分支 |
| Vehicle-payload plant and environment feedback | 4-vehicle payload plant and feedback | 突出协同运输对象 |

## 推荐图注草案

若作为中文主文图，可用以下图注：

```tex
\caption{\Method{} 的离线模型包与在线单步控制信号流。离线阶段由覆盖名义、通信退化和故障扰动的数据训练双线性 Koopman 提升模型，并通过输入感知稳定投影得到预测模型、约束边界和证书模板。在线第 $k$ 个采样周期中，上层参考路径与 4WS 局部路径发布器生成车辆临时期望路径，链路质量监测器根据时延、丢包和噪声更新邻居状态外推与一致性权重；观测融合后的 Koopman rollout 进入通信质量感知一致性 MPC，输出候选控制。候选控制经 FDI/FTC 投影、角色/货物保护调度和 Lyapunov/ISS 证书检查后发布为安全命令；若证书未通过，则触发投影、约束收缩或 degraded fallback。执行后的四车载荷系统把状态、跟踪误差、连接误差、受力/约束和日志反馈到下一采样周期。}
```

若作为英文/DCN图，可用：

```tex
\caption{Offline model package and online one-step signal flow of \Method{}. The offline stage trains the bilinear Koopman lifting model and applies input-aware stability projection to obtain the prediction model, uncertainty bounds, and certificate templates. During sampling period $k$, the upper-layer 4WS path publisher and link-quality monitor provide temporary path packets, delay/loss-compensated neighbor states, and quality-aware consensus weights. Observation fusion and Koopman rollout feed the consensus MPC, whose candidate command is passed through FDI/FTC projection, role/payload-protection scheduling, and a Lyapunov/ISS certificate guard. If the certificate fails, projection, tightening, or degraded fallback is triggered before safe command publication. The four-vehicle payload plant returns states, tracking errors, connection errors, force/constraint proxies, and logs for the next sampling period.}
```

## 是否可以进主文

当前版本：不建议直接进主文。

修改后可以进主文的条件：

- 有干净 PDF/SVG 导出；
- 图内标题改掉或删掉；
- offline 与 online 时间层级明确；
- 节点数量压缩，主路径一眼可见；
- 右侧安全/fallback 回路重画；
- 角色调度、货物保护和四车载荷对象明确出现；
- 图注定义关键缩写和条件分支；
- LaTeX 中从旧 `fig_nrkdcc_control_flow_visio_crop.pdf` 切换到新导出文件后重新编译检查。

若不做上述修改，它更适合作为补充材料的详细流程图，而不是主文图2。

## 最小修改清单

1. 导出同名 clean PDF/SVG，不使用浏览器截图。
2. 把标题改为 `Offline package and online one-step NR-KDCC control flow`，或删除图内标题。
3. 加 M1-M5 泳道标题，明确颜色语义。
4. 把 `MUX`、`risk compare`、`sat[0,1]` 合并到 MPC/保护模块，不作为独立小框。
5. 把 `C-mode scheduler` 改成 `Mode/role scheduler and consensus MPC`。
6. 增加 `payload-protection / force-risk switch` 或在安全层中显式写出。
7. 把 plant 改成 `4-vehicle payload plant and feedback`。
8. 底部反馈总线缩短为 `closed-loop feedback: states, errors, forces, constraints, logs`。
9. 右侧 fail 分支改为短回路，减少绕行线和交叉。
10. 用图注解释 `IRSP`、`4WS`、`FDI/FTC`、`C0-C3`、`m_k` 的含义。

