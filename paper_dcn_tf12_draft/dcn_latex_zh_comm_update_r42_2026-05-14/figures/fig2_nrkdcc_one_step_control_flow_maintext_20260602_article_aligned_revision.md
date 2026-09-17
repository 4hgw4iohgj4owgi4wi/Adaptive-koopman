# fig2_nrkdcc_one_step_control_flow_maintext_20260602.drawio 贴合正文修改稿

审查对象：

- 图文件：`fig2_nrkdcc_one_step_control_flow_maintext_20260602.drawio`
- 对照文章：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.pdf`
- 对照源文件：`manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.tex`
- 审查时间：2026-06-02

## 总体判断

这版比上一版更接近主文图：节点数从详细版的 28 个降到 15 个，边从 27 条降到 10 条，主路径也基本变成了离线模型、参考/通信、Koopman-MPC、安全执行层、四车载荷系统反馈这一条线。

但按你现在提出的标准，当前版本仍不能直接进主文。主要问题如下：

1. 图内有若干短语不是最终英文稿的精确命名，例如 `Offline model package`、`certificate templates`、`force-risk switch`、`Link-quality monitor`、`Mode/role scheduler`、`quality-aware weights and constraints`。
2. 主流程同层级框尺寸不统一。当前主行中 `m2=250x112`，`m3=310x112`，`m4=300x136`，`m5=245x112`，视觉层级会被误读为 M4 更重要或更复杂。
3. 切换逻辑没有真正画出来。`fail -> Projection, tightening or degraded fallback -> safe command` 只是写在 M4 内部，审稿人看不到 `certificate pass/fail` 的分支。
4. 右下角 legend/abbreviation 框占用太多空间，破坏长矩形比例，也让底部反馈线拥挤。
5. `M1--M5` 编号本身在最终文章正文中没有出现。若坚持“文章没有出现的不能有”，这些编号应删除；除非同步在正文或图注中声明它们是图内模块编号。

建议分类：`Needs main-text redraw, not only wording polish`。

## 正文贴合性核查

最终稿中可直接支撑图的核心表述如下：

- 方法命名：`Network-Resilient Koopman Delay-Compensated Consensus Control (NR-KDCC)`。
- 方法总览：离线数据覆盖 curvature variation、communication degradation、actuator efficiency degradation；训练 bilinear Koopman predictor；通过 input-aware spectral projection 稳定；嵌入 communication-quality-aware consensus MPC loop；包含 upper-layer 4WS local path publication、FDI/FTC、constraint tightening、degraded fallback、Lyapunov/ISS certificate。
- 控制模式：C0 nominal tracking and connection preservation，C1 high-curvature lateral priority，C2 payload protection，C3 conservative degraded fallback。
- 多触发优先级：C3 safety feasibility > C2 force protection > C1 lateral robustness > C0 nominal tracking。
- 执行层：FDI/FTC、role scheduling、PPC guard、certificate fail 后 reference contraction / tightening / C3。
- 稳定证书：certificate passing condition 为 `m_k >= -epsilon_m`。
- 实验边界：payload force 是 trade-off audit，不能画成默认“force minimization superiority”。

因此图中允许出现的主术语应优先使用正文原词，而不是另造近义词。

## 必须替换或删除的图内文字

| 当前图内文字 | 正文中是否为精确命名 | 修改动作 | 建议替换文字 |
|---|---:|---|---|
| `M1 Offline model package` | 否 | 删除 M1；替换 `package` | `Offline data and bilinear Koopman predictor` |
| `Data coverage for training/stress cases` | 否 | 换成正文原句结构 | `offline data covering curvature, communication degradation, and actuator degradation` |
| `IRSP projection` | 否，正文用完整名 | 首次出现写完整 | `input-aware robust spectral projection (IRSP)` |
| `model, bounds and certificate templates` | `certificate templates` 未出现 | 删除 templates | `model, residual bound, and certificate terms` |
| `completed before deployment` | 正文未用 deployment 口径 | 删除 | 不放图内，放图注可写 offline stage |
| `Reference path and payload progress` | 不精确 | 替换 | `Reference path, payload-center progress, and temporary path packet` |
| `M2 Reference and network layer` | M2 未定义 | 删除 M2 | `4WS local paths and communication degradation` |
| `Link-quality monitor` | 正文主要用 link quality / link-quality-aware | 避免 monitor | `link quality, delay, packet loss` |
| `delay/loss compensation` | loss compensation 不精确 | 换成正文词 | `delay compensation and packet loss` |
| `M3 Koopman prediction and consensus MPC` | M3 未定义 | 删除 M3 | `Koopman prediction and communication-quality-aware consensus MPC` |
| `Mode/role scheduler` | 不精确 | 换成正文模式逻辑 | `C0--C3 schedules and role scheduling` |
| `quality-aware weights and constraints` | 不精确 | 换成正文词 | `consensus weights and constraint tightening` |
| `M4 Safety / FDI / FTC / certificate guard` | M4 未定义；guard 不精确 | 拆成执行层框 + 证书判断菱形 | `Execution-layer protection` + `Certificate passes?` |
| `payload-protection / force-risk switch` | `force-risk switch` 未出现 | 替换 | `curvature-window payload-protection switch` |
| `certificate guard` | 正文用 certificate / certificate protection | 替换 | `Lyapunov/ISS certificate check` |
| `fail -> Projection, tightening or degraded fallback -> safe command` | 内容对，但不能只放框内 | 画成红色分支 | `fail` 箭头到 `Projection / tightening / C3 degraded fallback` |
| `M5 4-vehicle payload plant and feedback` | M5 未定义；4-vehicle 建议用全文术语 | 替换 | `Four-vehicle rigid-payload system and feedback` |
| `4 vehicles + rigid payload` | 不如正文术语 | 替换 | `four-vehicle rigid-payload transport` |
| `certificate-fail protection path` | 可以，但更贴近正文 | 替换 | `certificate-failing path` |
| `equivalent four-wheel steering` | 可用，但正文首次定义是 upper-layer 4WS local path publication | 简化或移到图注 | `4WS: upper-layer four-wheel steering local path publication` |

## 推荐最终图内文字

图内不要放大段定义。主文版每个框最多 3 行，全部用正文已经出现或直接等价的词。

### 顶部离线框

```text
Offline data and bilinear Koopman predictor
curvature / communication / actuator-degradation data
input-aware robust spectral projection (IRSP)
model, residual bound, and certificate terms
```

说明：

- 删除 `M1`。
- 删除 `package` 和 `deployment`。
- `certificate terms` 比 `certificate templates` 更贴合正文，因为正文中记录的是 certificate terms / margin / function。

### 主流程输入框

```text
Reference path, payload-center progress,
and temporary path packet
p_L^ref(s), psi_L^ref, kappa_r, P_i,k^tmp
```

说明：

- 比 `payload progress` 更精确。
- 必须加入 `temporary path packet`，因为正文把上层路径通信作为五节点图的一部分。

### 参考与通信框

```text
4WS local paths and communication degradation
link quality, delay, packet loss
q_ij,k, q_k^net, tau, ell_ij,k
```

说明：

- 删除 `Link-quality monitor`。
- `communication degradation`、`delay`、`packet loss`、`link quality` 都是正文高频词。

### Koopman-MPC 框

```text
Koopman prediction and
communication-quality-aware consensus MPC
z_{k+1|k}, C0--C3 schedules
consensus weights and constraint tightening
```

说明：

- `communication-quality-aware consensus MPC` 是正文精确说法。
- `C0--C3 schedules` 对应正文的四种模式，避免 `Mode/role scheduler` 这种没有精确定义的合成词。
- role scheduling 不建议放在这个框；正文把 role scheduling 放在 execution layer。

### 执行层保护框

```text
Execution-layer protection
FDI/FTC, PPC guard, role scheduling
curvature-window payload-protection switch
```

说明：

- 这个框只写执行层保护模块，不把证书 pass/fail 写死在框内。
- `PPC guard` 在实验协议和方法段中出现，且 noPPC 是消融项，建议保留。
- `curvature-window payload-protection switch` 是正文原词，比 `force-risk switch` 安全。

### 证书判断菱形

```text
Certificate
passes?
m_k >= -epsilon_m
```

说明：

- 该菱形必须独立出现，不能只作为 M4 内文字。
- 这是切换逻辑的核心视觉证据。

### fallback 下层框

```text
Projection / tightening /
C3 degraded fallback
reference contraction if needed
```

说明：

- 对应正文：certificate fail 后 execution layer either contracts reference progress, tightens connection/input constraints, or switches to C3。
- 该框只在 fail 分支出现，用红色边框或红色箭头。

### plant 反馈框

```text
Four-vehicle rigid-payload
system and feedback
states, errors, forces, constraints, logs
```

说明：

- 用正文题目和摘要中的 `four-vehicle rigid-payload`，不要写 `4 vehicles + rigid payload`。

## 版面与尺寸修改方案

保持长矩形主文图比例。建议画布从当前 `1600 x 560` 改为：

```text
pageWidth = 1600
pageHeight = 520
```

若保留当前高度 560，也不要让 legend 占一块大矩形；底部只放一行线型说明。

### 统一尺寸原则

- 顶部离线框是独立层：长矩形，可宽可高，不参与主行等尺寸约束。
- 主流程同层级的 5 个矩形必须统一：`235 x 108`。
- 求和圆、证书菱形不是矩形模块，不参与统一矩形尺寸。
- fallback 框是 fail 分支下层，宽度与执行层框一致，建议 `235 x 72`。

### 推荐坐标表

| 元素 | x | y | w | h | 备注 |
|---|---:|---:|---:|---:|---|
| title | 250 | 10 | 1100 | 24 | 建议直接删掉；若保留，字号 14 |
| offline | 70 | 52 | 1460 | 84 | 顶部长矩形 |
| ref_input | 50 | 210 | 235 | 108 | 主流程同层级矩形 |
| sum | 310 | 238 | 60 | 60 | 求和圆 |
| network | 395 | 210 | 235 | 108 | 主流程同层级矩形 |
| koopman_mpc | 660 | 210 | 235 | 108 | 主流程同层级矩形 |
| execution | 925 | 210 | 235 | 108 | 主流程同层级矩形 |
| cert_decision | 1200 | 225 | 86 | 78 | 菱形，独立判断节点 |
| plant | 1330 | 210 | 235 | 108 | 主流程同层级矩形 |
| fallback | 925 | 365 | 235 | 72 | fail 分支，和 execution 对齐 |
| line_legend | 395 | 485 | 1120 | 20 | 仅一行文字；也可完全移到图注 |

这样主流程在一条横线上，所有主模块都是长矩形，不会出现当前 M4 过高、M3 过宽的问题。

### 当前尺寸必须修正

当前 drawio 中：

```text
m2 = 250 x 112
m3 = 310 x 112
m4 = 300 x 136
m5 = 245 x 112
m0 = 220 x 92
```

修改后应为：

```text
ref_input = 235 x 108
network = 235 x 108
koopman_mpc = 235 x 108
execution = 235 x 108
plant = 235 x 108
```

## 字号与文字排版

建议统一：

- 图内标题：删除；若保留，`fontSize=14`。
- 模块标题：`fontSize=10`，加粗。
- 模块内说明：`fontSize=8`。
- 箭头标签：`fontSize=7` 或 `8`，尽量 2--4 个词。
- legend：`fontSize=7` 或 `8`。
- 数学符号只保留必要项，不要超过一行。

不要再使用当前 M1 框内三段长句式文字。顶部离线框应分成 3 行短语，避免在缩放到 `0.92\textwidth` 后变成小字。

## 箭头位置与切换逻辑

### 正常在线主路径

| 箭头 | 起点 | 终点 | 标签 | 样式 |
|---|---|---|---|---|
| e_ref_sum | `ref_input` east center | `sum` west center | 无 | 黑/灰实线 |
| e_sum_net | `sum` east center | `network` west center | `tracking error` | 黑/灰实线 |
| e_net_mpc | `network` east center | `koopman_mpc` west center | `path packet, q, tau, loss` | 黑/灰实线 |
| e_mpc_exec | `koopman_mpc` east center | `execution` west center | `u_k^mpc` | 黑/灰实线 |
| e_exec_cert | `execution` east center | `cert_decision` west center | `candidate command` | 黑/灰实线 |
| e_cert_pass | `cert_decision` east center | `plant` west center | `pass: u_k^safe` | 黑/灰实线 |

注意：

- 所有主路径箭头都从框的右中点出、左中点入。
- 不要让箭头从框角进入。
- 标签放在箭头上方或中点，不压住框边。

### 证书失败路径

| 箭头 | 起点 | 终点 | 标签 | 样式 |
|---|---|---|---|---|
| e_cert_fail | `cert_decision` south | `fallback` north | `fail` | 红色实线 |
| e_fallback_plant | `fallback` east | `plant` south 或 west-lower side | `degraded safe command` | 红色实线 |

推荐走线：

```text
cert_decision south -> fallback north
fallback east -> x=1310,y=401 -> plant south
```

这样 fail 分支在主线下方，不和 pass 分支交叉。

### 离线加载虚线

| 箭头 | 起点 | 终点 | 标签 | 样式 |
|---|---|---|---|---|
| e_off_mpc | `offline` bottom, x≈800 | `koopman_mpc` top | `Phi_theta, A, B, N_l, residual bound` | 灰色虚线 |
| e_off_cert | `offline` bottom, x≈1220 | `cert_decision` top | `IRSP and certificate terms` | 灰色虚线 |

注意：

- 离线箭头不要连接到 `execution` 框内部，否则会暗示 FDI/FTC 由离线训练直接生成。
- `certificate templates` 不要作为标签。

### 闭环反馈虚线

| 箭头 | 起点 | 终点 | 标签 | 样式 |
|---|---|---|---|---|
| fb_main | `plant` bottom center | `sum` bottom 或 `ref_input` bottom | `closed-loop feedback: states, errors, forces, constraints, logs` | 灰色虚线 |
| fb_to_network | feedback bus | `network` bottom | 无 | 灰色虚线 |
| fb_to_cert | feedback bus | `cert_decision` bottom | 无 | 灰色虚线 |

推荐走线：

```text
plant bottom center -> y=455 -> x=340 -> sum bottom
branch at x=512 -> network bottom
branch at x=1243 -> cert_decision bottom
```

不要把反馈线从 `m5` 直接斜穿到 `m2` 或 `m4`；统一走底部总线更稳。

## 切换逻辑应如何体现在图中

必须把正文的 C0--C3 逻辑和 certificate pass/fail 逻辑拆开：

1. `koopman_mpc` 框内写 `C0--C3 schedules`。
2. 在图注或框内小字说明 C0--C3：
   - C0: nominal tracking and connection preservation
   - C1: high-curvature lateral priority
   - C2: payload protection
   - C3: conservative degraded fallback
3. `execution` 框内写 `FDI/FTC, PPC guard, role scheduling, curvature-window payload-protection switch`。
4. `cert_decision` 菱形写 `m_k >= -epsilon_m`。
5. pass 分支直接到 plant。
6. fail 分支到 `Projection / tightening / C3 degraded fallback`，再到 plant。

这里不能把 C0--C3 画成四个并列控制器。正文已经明确：这些不是 four independent controllers，而是同一 MPC objective and constraint set 的 parallel weight and constraint schedules。

## Legend 处理

当前 legend 框太大，应删除 `legend`、`legend_title`、`legend_text`、`abbr` 四个对象，改为以下二选一。

方案 A：放到图注，不放图内。

```text
Solid arrows denote online data/command flow, dashed arrows denote offline loading or closed-loop feedback, and red arrows denote certificate-failing protection paths.
```

方案 B：图底部一行小字。

```text
solid: online data/command flow; dashed: offline loading or feedback; red: certificate-failing path
```

若采用方案 B，坐标建议：

```text
x = 395, y = 485, w = 1120, h = 20, fontSize = 7 or 8
```

不要保留大白框；它会压缩主图比例。

## 建议最终图注

英文主文图注建议：

```tex
\caption{Offline data and online signal flow of \Method{}. The offline stage generates data covering curvature variation, communication degradation, and actuator-efficiency degradation, trains the bilinear Koopman predictor, and applies input-aware robust spectral projection (IRSP) to obtain the model, residual bound, and certificate terms used online. During one sampling period, the reference path, payload-center progress, and temporary path packet enter the upper-layer 4WS local-path and communication-degradation block. Link quality, delay, and packet loss schedule neighbor prediction, consensus weights, and constraint tightening in the communication-quality-aware consensus MPC. The execution layer applies FDI/FTC, the prescribed-performance-control (PPC) guard, role scheduling, and the curvature-window payload-protection switch before the Lyapunov/ISS certificate check. If the certificate passes, the safe command is issued to the four-vehicle rigid-payload system; otherwise, projection, tightening, or C3 degraded fallback is triggered before command application. Dashed arrows denote offline loading or closed-loop feedback.}
```

注意：

- 图注没有写 `force-risk switch`。
- 图注没有写 `certificate templates`。
- 图注没有把 payload protection 写成 force 全面优化，只写为 switch。
- 图注把 C3 fallback 只放在 certificate fail 或 degradation 保护路径里。

## 最终 LaTeX 引用建议

导出干净 PDF/SVG 后，LaTeX 建议使用：

```tex
\begin{figure*}[t]
\centering
\includegraphics[width=0.92\textwidth]{figures/fig2_nrkdcc_one_step_control_flow_maintext_20260602.pdf}
\caption{...}
\label{fig:nrkdcc_flowchart}
\end{figure*}
```

如果图按 `1600 x 520` 导出，`0.92\textwidth` 应能保持长矩形比例。若字仍小，优先减少图内文字，而不是继续放大字体或提高图高。

## 修改优先级

### 必做

1. 删除 M1--M5 编号，除非正文同步解释。
2. 替换所有正文未精确出现的短语，尤其是 `certificate templates`、`force-risk switch`、`Link-quality monitor`。
3. 主流程矩形统一为 `235 x 108`。
4. 增加独立证书判断菱形。
5. 增加红色 fail 分支：certificate fail -> projection/tightening/C3 fallback -> plant。
6. 删除右下角大 legend/abbr 框。
7. 反馈线统一走底部总线。

### 建议做

1. 图内标题删除，依靠 caption 说明。
2. 离线框文字控制在 4 行以内。
3. 主模块文字控制在 3 行以内。
4. 箭头标签全部压缩到 2--4 个词。
5. 导出 PDF 和 SVG 后插入 LaTeX 编译检查。

## 最终安全结论

按以上修改后，这张图可以作为主文 `Fig. 2` 或在线控制流程图使用。当前 drawio 版本不宜直接入稿，因为它仍存在术语不完全贴合正文、同层级尺寸不统一、切换逻辑未图形化、底部 legend 破坏长矩形比例四个问题。

