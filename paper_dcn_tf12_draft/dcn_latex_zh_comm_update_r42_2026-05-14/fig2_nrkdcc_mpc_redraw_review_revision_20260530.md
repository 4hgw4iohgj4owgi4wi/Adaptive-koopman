# Fig. 2 重画审查与详细修改稿

审查对象：`figures/fig2_nrkdcc_mcp_redraw_20260530.drawio`

结论：这版比前面拥挤的多模块图更简洁，主流程也更清楚，但目前压缩过度，已经弱化了论文方法的核心逻辑。它更像一个“摘要流程图”，还不能充分承担 Fig. 2 的作用。Fig. 2 应该让审稿人看出 NR-KDCC 不是简单地把 Koopman、MPC、FDI/FTC 和 certificate 堆在一起，而是一个有明确数据流、信号流和执行闭环的控制架构。

## 1. 当前图中的主要问题

### 1.1 文件命名有拼写风险

当前文件名是 `fig2_nrkdcc_mcp_redraw_20260530.drawio`，其中 `mcp` 很可能是 `mpc` 的误写。建议改为：

`fig2_nrkdcc_mpc_redraw_20260530.drawio`

否则后续容易在论文、脚本和图注中出现 `MCP/MPC` 混用。

### 1.2 图过度压缩，缺少内部机制

当前图只有 5 个大块：

- Offline Bilinear Koopman Predictor & IRSP Projection
- Upper-Layer Reference & Path Publisher
- Network
- Link-Quality-Aware Consensus MPC + Koopman Predictor
- FDI/FTC, Command Projection & Certificate Check
- Vehicle-Payload System & Feedback

这些名称能表达大方向，但没有说明每个大模块内部做了什么。论文方法部分真正强调的是：

- offline data generation
- bilinear Koopman fitting
- IRSP projection/residual audit
- equivalent 4WS local path publication
- communication degradation processing
- observation fusion and lifting
- delay-compensated neighbor prediction
- consensus-MPC cost and constraints
- C0/C1/C2/C3 mode scheduling
- FDI residual monitor
- FTC command projection/reallocation
- certificate margin
- projection/tightening/fallback
- command publication
- vehicle-payload system
- feedback logs

这些机制如果在 Fig. 2 中完全看不到，审稿人会觉得图没有支撑方法章节，只是泛泛画了一个 pipeline。

### 1.3 Network cloud 的含义不够准确

当前 `Network (delay, loss, noise)` 放在 Upper-Layer Reference 和 Online MPC 之间，容易造成误解：好像只有上层路径包经过网络。实际论文中通信退化影响至少三类信号：

- adjacent distance: \(\hat d_{ij,k}\)
- payload-center lateral error: \(\hat e_{y,L,k}\)
- temporary path packet: \(\hat{\mathcal P}_{i,k}^{\mathrm{tmp}}\)

此外，邻车状态预测、链路质量 \(q_{ij,k}\)、整体网络质量 \(q_k^{\mathrm{net}}\)、delay \(\tau\)、loss \(\ell\)、bias/noise \(\beta,\epsilon\) 都要进入 MPC 调度。建议不要把 Network 画成一个孤立 cloud，而是画成 M2 或 M3 内部的 “Communication processing / link-quality monitor” 小模块。

### 1.4 Offline 到 Online 的箭头几何有问题

当前 `A` 箭头从 offline 出发，但没有绑定到 online 目标对象，而是使用 targetPoint。XML 中还出现了空 y 坐标的中间点：

- `(225,68)`
- `(225,)`
- `(630,)`

这类线在 draw.io 或导出 PDF 时可能出现非预期折线、贴边或越界。建议改为绑定对象的正交连接线：

`M1 model package -> M3 model interface`

标签建议写为：

`\(\Phi_\theta,A,B,N_\ell,\bar w,\mathcal U_s\)`

不要只写 `model package`，因为这个标签太泛。

### 1.5 多数箭头没有绑定 source/target

当前 `B/C/D/E/F1/F2/G` 多数是用 sourcePoint 和 targetPoint 画出来的，并未绑定到具体模块对象。这样后续修改模块位置时，箭头不会自动跟随，容易错位。建议所有主流程箭头都设置明确的 source/target：

- M1 -> M3
- M2 -> M3
- M3 -> M4
- M4 -> M5
- M5 -> M2
- M5 -> M3
- M5 -> M4
- M4 -> M3

内部小模块之间也应尽量绑定 source/target，而不是只用绝对坐标。

### 1.6 信号标签格式不规范

当前标签包括：

- `q_ij,k, q_k^net`
- `u_i*`
- `u_i^safe`
- `packets + q`

这些在图中不是数学格式，容易显得粗糙。建议改为 HTML 上下标，或使用普通文字加规范符号：

- `q<sub>ij,k</sub>, q<sub>k</sub><sup>net</sup>`
- `u<sub>0:H-1</sub><sup>mpc</sup>`
- `u<sub>i,k</sub><sup>safe</sup>`
- `P<sub>i,k</sub><sup>tmp</sup>, d<sub>ij,k</sub>, e<sub>y,L,k</sub>, q, τ, ℓ`

如果 draw.io 的 math 渲染不开启，就不要直接写 `q_ij,k`、`u_i^safe` 这种伪 LaTeX。

### 1.7 标签背景色不符合之前要求

你之前要求“信号标识就无背景色的文字”。当前多个标签使用：

- `fillColor=#FFFFFF`
- `opacity=88`

这会形成白底贴片，视觉上像小白框，容易挡线。建议：

- 所有信号标签 `fillColor=none`
- `strokeColor=none`
- `labelBackgroundColor=none`
- 不要使用半透明白底

若担心线条穿过文字，就通过正交布线避开标签，而不是给标签加背景。

### 1.8 缺少 command publication / communication

当前 `FDI/FTC...` 直接输出 `u_i^safe` 到 `Vehicle-Payload System & Feedback`。论文中 M5 里应有 `Command publication / communication`，表示安全命令发布后才进入车辆-载荷系统。建议 M5 拆成：

- Command publication / communication
- Vehicle-payload system
- Feedback logs

这样才和方法文字一致，也能说明安全命令不是抽象地“直接作用”到环境，而是经过执行层发布。

### 1.9 FDI/FTC 缺少来自环境的残差输入

FDI/FTC 需要测量响应、预测残差和执行器效率估计。当前环境反馈只回到 online 和 upper，没有明确回到 safety。这样会让人看不出 FDI residual monitor 的信息来源。建议增加：

`M5 Feedback logs -> M4 FDI residual monitor`

标签：

`y_i, \hat y_i, ε_i^pred, actuator response`

或简化为：

`prediction residuals, actuator response`

### 1.10 Certificate fail 的逻辑没有画出来

当前 safety block 写了 `Certificate Check`，但没有显示通过/失败后的执行关系。论文中关键逻辑是：

- certificate passes -> publish safe command
- certificate fails -> projection/tightening/fallback -> safe/fallback command

建议在 M4 内部加入一个小 diamond：

`Certificate passes?`

然后画：

- yes -> Safe command
- no -> Projection / tightening / fallback -> Safe/fallback command

注意：`feedback logs` 或 `Errors, forces, constraints, logs` 不应直接指向 `Certificate passes?` 的 no 出口。正确逻辑是反馈日志作为 certificate metrics 的输入，certificate check 根据这些量计算 \(m_k\)，再决定 yes/no。

### 1.11 C0-C3 模式没有体现

论文中 C0/C1/C2/C3 是方法逻辑的重要部分：

- C0 nominal tracking
- C1 high-curvature lateral priority
- C2 payload protection
- C3 conservative degraded fallback

当前图完全没有 mode scheduling。建议在 M3 或 M4 中加入：

`C-mode scheduler: C0/C1/C2/C3`

更合理的位置是 M3 内部，因为它决定 MPC 权重和约束；M4 可接收 certificate/FDI 触发后把 mode/fallback flag 回传给 M3。

### 1.12 当前画布高度太小，导出后文字可能过小

当前 draw.io 页面是：

- pageWidth = 1107
- pageHeight = 200
- fontSize = 7 到 10

这会导致双栏图导出后非常扁，内部标签难以阅读。建议把 Fig. 2 作为 `figure*` 跨双栏图，画布比例改成约：

- width: 1500-1650
- height: 420-520

用 5 个大模块横向排列，内部小模块纵向排布。这样既保留“长矩形整体感”，又不会因为太扁导致信息密度失控。

## 2. 推荐重画目标

Fig. 2 建议定位为：

**Module-level data flow of NR-KDCC over one sampling period.**

它应该回答三个问题：

1. NR-KDCC 有哪几个大模块？
2. 每个大模块内部的关键小模块是什么？
3. 数据、命令、反馈和安全触发信号如何流动？

不要把 Fig. 2 画成算法细节推导图，也不要画成过度抽象的 5 框流程图。它应该处于“方法章节总览图”和“在线信号流图”之间。

## 3. 推荐版式

### 3.1 整体画布

建议使用横向长矩形：

- canvas: 1600 × 500 draw.io units
- outer margin: 30
- module gap: 20-24
- main module height: 300-340
- feedback bus at bottom: y ≈ 390

推荐大模块从左到右排列：

1. M1 Offline learning layer
2. M2 Reference and communication layer
3. M3 Online prediction and consensus MPC
4. M4 Safety, FDI/FTC, and certificate
5. M5 Vehicle-payload environment and feedback

M1 可以略矮或放在左上，但建议仍在同一长矩形中，不要单独飘在外面。若空间不够，M1 可作为上方横条，并用虚线向 M3 加载模型。

### 3.2 推荐模块尺寸

可按以下比例重画：

| Module | Suggested position | Suggested size |
|---|---:|---:|
| M1 Offline learning layer | x=30, y=40 | w=250, h=250 |
| M2 Reference and communication | x=305, y=40 | w=270, h=300 |
| M3 Online prediction and consensus MPC | x=600, y=40 | w=390, h=300 |
| M4 Safety, FDI/FTC, and certificate | x=1015, y=40 | w=310, h=300 |
| M5 Vehicle-payload environment and feedback | x=1350, y=40 | w=220, h=300 |

底部反馈 bus：

`x=1470 -> x=330, y=390`

用 dashed gray line，分别向 M2、M3、M4 垂直分支。

## 4. 推荐大模块与小模块命名

### M1: Offline learning layer

大模块标题：

`M1 Offline learning layer`

内部小模块：

1. `Offline data generation`
2. `Bilinear Koopman fitting`
3. `IRSP projection and residual audit`
4. `Model package`

`Model package` 下方可以小字标注：

`\(\Phi_\theta,A,B,N_\ell,\bar w,\mathcal U_s\)`

如果 draw.io 不启用 LaTeX，就用：

`Phi_theta, A, B, N_l, w bounds, U_s`

### M2: Reference and communication layer

大模块标题：

`M2 Reference and communication layer`

内部小模块：

1. `Reference path and payload progress`
2. `Equivalent 4WS local-path publication`
3. `Link-quality monitor`
4. `Communication processing`

对应信号：

- reference path: `s_k, κ_r, ψ_r`
- local path packet: `P_i,k^tmp`
- network degradation: `τ, ℓ, β, ε`
- link quality: `q_ij,k, q_k^net`
- corrupted/processed signals: `d_hat, e_y,L_hat, P_hat_i,k^tmp`

### M3: Online prediction and consensus MPC

大模块标题：

`M3 Online prediction and consensus MPC`

内部小模块：

1. `Observation fusion and lifting`
2. `Delay-compensated neighbor prediction`
3. `Bilinear Koopman rollout`
4. `C-mode scheduler C0/C1/C2/C3`
5. `Consensus-MPC cost and constraints`
6. `Candidate control sequence`

建议不要把 `Koopman Predictor` 和 `MPC` 只合成一个框。至少拆出 `lifting/rollout` 和 `MPC cost + constraints`，否则看不出 Koopman 与 MPC 的接口。

关键公式/信号可简写为：

- `χ_k, z_k`
- `A_eff(u)`
- `x_hat_j,k^net`
- `e_L, e_c, e_d`
- `u_0:H-1^mpc`

### M4: Safety, FDI/FTC, and certificate

大模块标题：

`M4 Safety, FDI/FTC, and certificate`

内部小模块：

1. `FDI residual monitor`
2. `FTC reallocation / command projection`
3. `Certificate metrics`
4. `Certificate passes?`
5. `Projection / tightening / fallback`
6. `Safe command`

推荐内部逻辑：

`FDI residual monitor -> FTC projection`

`Certificate metrics -> Certificate passes?`

`Certificate passes? yes -> Safe command`

`Certificate passes? no -> Projection/tightening/fallback -> Safe command`

从 M4 回到 M3 的红色虚线：

`m_k, eta_hat, μ_k, tightened bounds`

这个回传表示下一步调度和约束收紧，不应画成环境日志直接进入 no 分支。

### M5: Vehicle-payload environment and feedback

大模块标题：

`M5 Vehicle-payload environment and feedback`

内部小模块：

1. `Command publication / communication`
2. `Vehicle-payload system`
3. `Feedback logs`

M5 的输出分三路：

- to M2: payload progress and reference feedback
- to M3: measured states, tracking errors, connection errors
- to M4: prediction residuals, actuator response, force/constraint logs

## 5. 推荐箭头与标签

### 5.1 主前向流

1. M1 -> M3  
   线型：blue dashed  
   标签：`model package: Phi_theta, A, B, N_l, bounds`

2. M2 -> M3  
   线型：teal solid  
   标签：`P_hat_i,k^tmp, d_hat_ij,k, e_hat_y,L,k, q, τ, ℓ`

3. M3 -> M4  
   线型：blue solid  
   标签：`u_0:H-1^mpc, predicted traj., margins`

4. M4 -> M5  
   线型：black solid  
   标签：`u_i,k^safe, mode μ_k`

5. M5 internal downward flow  
   `Command publication -> Vehicle-payload system -> Feedback logs`

### 5.2 反馈流

1. M5 -> M2  
   线型：gray dashed  
   标签：`s_k, e_y,L,k, payload progress`

2. M5 -> M3  
   线型：gray dashed  
   标签：`x_i,k, e_L,k, e_c,k, F_c,k`

3. M5 -> M4  
   线型：gray dashed  
   标签：`residuals, actuator response, force/constraint logs`

4. M4 -> M3  
   线型：red dashed  
   标签：`m_k, eta_hat, fallback/tightening flags`

### 5.3 不建议出现的箭头

不要画：

`Feedback logs -> Certificate passes? no`

正确逻辑应是：

`Feedback logs -> Certificate metrics -> Certificate passes? -> yes/no`

不要画：

`Network cloud -> MPC` 作为唯一通信退化输入

正确逻辑应是：

`Communication processing -> Online prediction/MPC`

并明确信号为 \(\hat d_{ij,k}\)、\(\hat e_{y,L,k}\)、\(\hat{\mathcal P}_{i,k}^{tmp}\)、\(q\)、\(\tau\)、\(\ell\)。

## 6. 视觉样式建议

### 6.1 模块颜色

可以保留当前色系，但要固定含义：

- M1 blue: offline learned model
- M2 teal/green: reference and communication
- M3 steel blue: online prediction and MPC
- M4 red/rose: safety and certificate
- M5 purple/gray: plant and feedback

不要让颜色同时表示模块类别和信号类别，否则会混乱。信号类别主要靠线型表达。

### 6.2 线型

建议统一：

- solid arrow: forward data/command flow in current sampling period
- dashed gray arrow: measured feedback/logs
- dashed blue arrow: offline model loading
- dashed red arrow: certificate/fallback/tightening signal

不要使用过多颜色表达不同变量。

### 6.3 标签

所有箭头标签都应：

- 无背景色
- 不加边框
- 不覆盖线条
- 使用 8.5-9 pt 等效字号
- 尽量放在线的上方或旁边
- 使用 HTML sub/sup 或普通文字，不使用未渲染的 LaTeX 下划线

### 6.4 线条布置

必须横平竖直：

- 所有 forward arrows 从左到右
- bottom feedback bus 从右到左
- tap arrows 垂直向上进入对应模块
- red certificate feedback 走 M4 和 M3 之间的短回路，不要穿越整个图
- 避免 diagonal arrows
- 避免箭头穿过模块标题

## 7. 建议重画后的图注

推荐图注：

`Fig. 2. Module-level data flow of NR-KDCC over one sampling period. The offline layer provides the stability-projected bilinear Koopman model package to the online prediction module. The reference and communication layer publishes 4WS-based local path packets and link-quality/degradation variables. The online layer fuses observations, compensates delay, performs Koopman rollout, schedules C0-C3 MPC weights/constraints, and outputs a candidate control sequence. The safety layer performs FDI/FTC, certificate checking, projection/tightening, and fallback before safe command publication. Feedback logs from the vehicle-payload system update reference progress, prediction states, residuals, force/constraint terms, and certificate quantities for the next sampling period.`

如果论文版面较紧，可以压缩为：

`Fig. 2. Module-level data flow of NR-KDCC. Solid arrows denote current-step data and command flow, gray dashed arrows denote closed-loop feedback logs, blue dashed arrows denote offline model loading, and red dashed arrows denote certificate-triggered tightening/fallback signals.`

## 8. 可直接照着改的最终版本

最终 Fig. 2 建议画成如下结构：

```text
┌────────────────────┐   ┌────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────┐
│ M1 Offline learning │   │ M2 Reference + comm.    │   │ M3 Prediction + consensus MPC │   │ M4 Safety + certificate  │   │ M5 Plant + feedback   │
│                    │   │                        │   │                              │   │                          │   │                      │
│ Data generation    │   │ Reference path          │   │ Observation fusion/lifting    │   │ FDI residual monitor     │   │ Command publication  │
│ Koopman fitting    │   │ 4WS local path packet   │   │ Delay compensation            │   │ FTC projection           │   │ Vehicle-payload sys. │
│ IRSP + residual    │   │ Link-quality monitor    │   │ Koopman rollout               │   │ Certificate metrics      │   │ Feedback logs        │
│ Model package      │   │ Communication process   │   │ C0-C3 scheduler               │   │ Certificate passes?      │   │                      │
│                    │   │                        │   │ MPC cost + constraints        │   │ Projection/tightening    │   │                      │
└─────────┬──────────┘   └───────────┬────────────┘   └──────────────┬───────────────┘   └────────────┬─────────────┘   └──────────┬───────────┘
          │ model package             │ degraded refs + q, τ, ℓ       │ candidate command sequence       │ safe command                 │
          └──────────────────────────►│──────────────────────────────►│─────────────────────────────────►│─────────────────────────────►│

feedback bus: M5 -> M2, M3, M4
certificate/tightening feedback: M4 -> M3
```

重画时保留这个逻辑即可。不要再把所有机制压成 5 个大框，也不要恢复到过度复杂、箭头交叉的旧版。目标是：大模块清楚，小模块足够支撑论文方法，箭头只保留关键数据流。

## 9. 当前版本可以保留的优点

当前版本不是完全不可用，以下优点可以保留：

- 横向主流程方向正确：offline/reference/network/MPC/safety/plant。
- 色彩已经大致按模块区分，没有过度花哨。
- 文字比旧版少，阅读负担较低。
- safe command 和 feedback 的大方向是对的。

重画时建议保留“横向主流程 + 底部反馈 bus”的基本思想，但必须补足内部小模块和精确数据标签。

