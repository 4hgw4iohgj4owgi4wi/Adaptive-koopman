# Fig. 2 reviewfix 版重画要求与审查意见

审核对象：

`figures/fig2_nrkdcc_module_dataflow_reviewfix_20260528.png`

目标：把 Fig. 2 改成一张可投稿的模块级数据流图。核心标准是：线条横平竖直、所有大模块整体形成一个长矩形、信号标签为无背景文字、模块命名与正文一致、各大模块尺寸紧凑且不空。

## 总体判断

这一版比前一版明显进步：大模块已经按 `M1-M5` 分层，主要模块也基本对应正文。但是当前图还不是最终稿，主要问题是版式和图形规范：

1. 大模块没有形成统一的长矩形轮廓。M1 横跨上方，M2-M5 位于下方，整体外形仍像错层拼图。
2. 仍有斜线和交叉线，尤其是 M1 到 M3、M2 内部、M3 到 M4、M4 到 M5 的若干连接。
3. 信号标签带灰色背景框，破坏图面一致性，且在缩放后像小补丁。
4. 部分变量标识不规范，例如 `Phi_theta,A,B,N_l,C,bounds`、`q_i,j,k, tau, loss`、`y_i,yhat_i,r_i`。
5. M2、M4、M5 内部留白仍偏大，模块尺寸没有完全随内容收紧。
6. M4 内部逻辑还可以更清楚：`Certificate metrics`、`Certificate passes?`、`Projection and tightening`、`Fallback command` 之间的方向需要严格区分正常链路和失败保护链路。

建议下一版不要继续“微调线条”，而是按下面的结构整体重排一次。

## 一、整体版式要求

### 1. 所有大模块应组成一个长矩形

建议采用“上方 M1 条带 + 下方 M2-M5 四列”的布局，让整体外边界近似一个长矩形：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ M1 Offline learning layer                                                    │
│ Offline data -> Lifting + bilinear regression -> IRSP -> Model package       │
├───────────────┬──────────────────────────┬──────────────────────┬───────────┤
│ M2 Reference  │ M3 Online prediction/MPC │ M4 Safety/certificate│ M5 Env.   │
│ communication │                          │                      │ feedback  │
└───────────────┴──────────────────────────┴──────────────────────┴───────────┘
```

具体比例建议：

| 区域 | 建议尺寸 |
|---|---:|
| 整图宽高比 | 约 2.1:1 到 2.4:1 |
| M1 高度 | 全图高度的 22%-26% |
| 下方 M2-M5 高度 | 全图高度的 74%-78% |
| M2 宽度 | 全图宽度的 20%-22% |
| M3 宽度 | 全图宽度的 30%-33% |
| M4 宽度 | 全图宽度的 27%-30% |
| M5 宽度 | 全图宽度的 18%-20% |
| 大模块间距 | 6-10 px，不要出现大空白沟槽 |

当前 M1 占据上方很宽但没有覆盖 M4/M5，上下两层错开，建议改成 M1 横跨全图宽度，或者至少与 M2-M5 的总宽度对齐。

### 2. 大模块内部不要显得空

当前 M2 和 M5 内部留白较多。建议按内容重新排布：

- M2 用 `2 x 2` 或紧凑上下结构。
- M3 用 `Model interface` 顶部居中，核心模块围绕它展开。
- M4 用左侧 FDI/FTC、中部 certificate、下方 protection/fallback、右侧 safe command。
- M5 用竖向三段：command communication -> vehicle-payload system -> feedback logs。

每个大模块内部的空白面积不要超过 35%-40%。标题区下面不应留大片空白。

## 二、线条要求

### 1. 所有连线尽量横平竖直

下一版不要使用斜线。全部用 Visio 的 orthogonal connector 或 elbow connector。

允许的线型：

```text
横线：A ───> B
竖线：A
      │
      v
折线：A ───┐
           v
           B
```

不建议出现：

```text
A  ╲
    ╲
     B
```

当前需要重点改掉的斜线：

1. M1 `Model package` 到 M3 `Model interface` 的斜线。
2. M2 `Reference path + 4WS model` 到 `Local path packet` 的斜线。
3. M3 `Model interface` 到 `Observation fusion and lifting`、`Koopman prediction` 的斜线。
4. M3 `Candidate control sequence` 到 M4 的转接线。
5. M4 `Safe command` 到 M5 `Command publication / communication` 的斜线。
6. M5 `Feedback logs` 到 M3/M4 的斜向反馈线。

### 2. 建议使用三条固定“信息通道”

为了减少线条乱穿，可以设置三类固定通道：

| 通道 | 位置 | 线型 |
|---|---|---|
| Offline model channel | M1 下边缘到 M3 上边缘 | 蓝色虚线，竖直下接 |
| Main forward channel | M2 -> M3 -> M4 -> M5 的中部水平线 | 深蓝/黑色实线 |
| Feedback channel | M5 底部沿底边回到 M3/M4 | 灰色虚线，横平竖直 |

这样图面会更像系统框架，而不是变量网络。

### 3. 信号标签不要有背景色

当前信号标签是灰底小框，例如 `Phi_theta,A,B,N_l,C,bounds`、`u_i^* traj., margins`。下一版应改成无背景文字：

- 无填充色。
- 无边框。
- 字号比模块文字小 1-1.5 pt。
- 颜色用深灰或对应箭头颜色的深色版。
- 放在箭头上方或旁边，不要压在线条上。

例如：

```text
Phi_theta, A, B, N_l, C, bounds
```

改成：

```text
Φθ, A, B, Nℓ, C, bounds
```

或保守写法：

```text
Phi_theta, A, B, N_l, C, bounds
```

但不要用灰底框。

## 三、小模块命名建议

下面是建议保留的小模块名称，并标注其正文依据。下一版尽量使用这些名称，不要再随意新增正文没有出现的名称。

### M1 Offline learning layer

| 当前名称 | 建议名称 | 是否有正文依据 | 修改理由 |
|---|---|---|---|
| Offline data generation | Offline data generation | 有 | 正文明确写 offline data generation。 |
| Lifting + bilinear regression | Koopman lifting and bilinear regression | 有 | 正文有 Bilinear Koopman Lifting 和 bilinear regression。 |
| IRSP stability projection | IRSP stability projection | 有 | 正文和 Fig. 3 均使用 IRSP。 |
| Model package Phi_theta,A,B,N_l,C,bounds | Model package | 有，但变量需规范 | 框内写 `Phi_theta, A, B, N_l, C, bounds` 或 `Phi_theta, A, B, N_l, C, IRSP bounds`。 |

M1 推荐内部顺序：

```text
Offline data generation -> Koopman lifting and bilinear regression -> IRSP stability projection -> Model package
```

### M2 Upper-layer reference and communication

| 当前名称 | 建议名称 | 是否有正文依据 | 修改理由 |
|---|---|---|---|
| Reference path + 4WS model | 4WS local-path publication | 有 | 正文强调 upper-layer 4WS local path publication，不只是 4WS model。 |
| Local path packet | Temporary path packet | 有 | 正文符号为 `P_{i,k}^{tmp}`，建议用 temporary path packet。 |
| Link-quality monitor | Link-quality monitor | 有 | 正文多次出现 link quality。 |
| Reference communication | Reference communication | 有 | 可保留。 |

M2 推荐内部布局：

```text
4WS local-path publication ──> Temporary path packet
                                      │
                                      v
Link-quality monitor ─────────> Reference communication
```

这里不要再用斜线。

### M3 Online prediction and consensus-MPC

| 当前名称 | 建议名称 | 是否有正文依据 | 修改理由 |
|---|---|---|---|
| Model interface | Koopman model interface | 可接受 | 作为图中接口节点可以保留，但建议加 Koopman，避免泛泛而谈。 |
| Observation fusion and lifting | Observation fusion and lifting | 有 | Fig. 2 caption 和 Section 3 均支持。 |
| Koopman prediction | Koopman prediction | 有 | 可保留。 |
| Delay-compensated remote prediction | Delay-compensated remote-state prediction | 有 | 正文/旧 Fig. 2 用 remote-state prediction。 |
| Quality-aware consensus | Communication-quality-aware consensus | 有 | 正文是 communication-quality-aware consensus MPC。 |
| Consensus-MPC cost + constraints | Communication-quality-aware Koopman-MPC | 有 | 正文主说法是 communication-quality-aware Koopman-MPC loop。若要突出约束，可写 `MPC cost and constraints`。 |
| Candidate control sequence | Candidate control sequence | 有 | Fig. 2 caption 已出现。 |

M3 推荐内部布局：

```text
                 Koopman model interface
                  │             │
                  v             v
Observation fusion and lifting -> Koopman prediction
        ^                         │
        │                         v
Delay-compensated remote-state -> Communication-quality-aware Koopman-MPC
prediction                         ^
        ^                          │
        │                          │
Communication-quality-aware consensus
                  │
                  v
          Candidate control sequence
```

实际画图时可以简化，不必每条内部线都标数据名。

### M4 Safety, FDI/FTC, and certificate

| 当前名称 | 建议名称 | 是否有正文依据 | 修改理由 |
|---|---|---|---|
| FDI residual monitor | FDI residual monitoring | 有 | 与正文和 Fig. 5 caption 对齐。 |
| FTC reallocation | FTC command reallocation | 有 | Fig. 5 caption 中提到 FTC reallocation commands。 |
| Certificate metrics | Certificate metrics | 可接受 | 正文有 certificate function 和 margin logs。 |
| Certificate passes? | Certificate check | 有 | 菱形内可写 `Certificate passes?`，模块名可叫 certificate check。 |
| Projection and tightening | Projection and tightening | 有 | 正文有 projection 和 constraint tightening。 |
| Fallback command | Degraded fallback | 有 | 正文用 degraded fallback。 |
| Safe command | Safe command output | 有 | 正文公式有 `u_k^{safe}`，图中可保留。 |

M4 推荐内部布局：

```text
FDI residual monitoring -> FTC command reallocation -> Certificate check -> Safe command output
                                      │                    │
                                      │                    no
                                      │                    v
                         Projection and tightening <- Degraded fallback
```

更严谨的数据逻辑：

```text
candidate control + measured/predicted response -> FDI residual monitoring
FDI residual monitoring -> FTC command reallocation
FTC command reallocation -> Certificate metrics
Certificate metrics -> Certificate check
Certificate check yes -> Safe command output
Certificate check no -> Projection and tightening -> Degraded fallback -> Certificate metrics/check
```

### M5 Vehicle-payload environment and feedback

| 当前名称 | 建议名称 | 是否有正文依据 | 修改理由 |
|---|---|---|---|
| Command publication / communication | Command publication and communication | 有 | 正文写 command publication, communication channels。 |
| Vehicle-payload system | Vehicle-payload system | 有 | 旧 Fig. 2 TikZ 已使用；正文有 coupled vehicle--payload model。 |
| Feedback logs errors, forces, constraints | Feedback logs | 有 | 框名简化；框内小字写 `errors, forces, constraints`。 |

M5 推荐内部布局：

```text
Command publication and communication
                │
                v
Vehicle-payload system
                │
                v
Feedback logs
errors, forces, constraints
```

## 四、信号标签规范

下一版跨模块箭头建议只保留以下标签。内部箭头不必全部标。

| 信号位置 | 当前写法 | 建议写法 |
|---|---|---|
| M1 -> M3 | `Phi_theta,A,B,N_l,C,bounds` | `Phi_theta, A, B, N_l, C, bounds` 或 `Φθ, A, B, Nℓ, C, bounds` |
| M2 -> M3 path | `P_i,k-d^tmp, r_ref` | `P_{i,k-d}^{tmp}, r_ref` 或 `delayed path packet, r_ref` |
| M2 -> M3 quality | `q_i,j,k, tau, loss` | `q_{ij,k}, tau_{ij,k}, ell_{ij,k}` |
| M3 -> M4 | `u_i^*, traj., margins` | `u_i^*, predicted trajectory, margins` |
| M5 -> M4 FDI | `y_i,yhat_i,r_i` | `y_i, yhat_i, r_i` 或 `measured/predicted response, residual` |
| M5 -> M4 certificate | `V,margin,F,g` | `V_k, m_k, force proxy, g(x,u)` |
| M5 -> M3 | `x_i,k+1, e_y, e_s` | `x_{i,k+1}, e_y, e_s` |
| M4 -> M5 | `u_i^safe` | `u_k^safe` 或 `safe command u_k^safe` |
| M4 -> M3 fallback | `tightened bounds` | `tightened bounds, contracted reference` |

注意：

- 如果 Visio 中公式不好看，就用短英文标签，不要强行写复杂下标。
- 不要用灰底框。
- 标签应贴近箭头中段，但不要和模块边框重叠。

## 五、当前图中需要具体修改的位置

### 1. M1 顶部模块

问题：

- M1 过宽但内部只有一行小模块，底部空白较多。
- 到 M3 的模型输入是斜向虚线。
- 信号标签有灰底框。

修改：

- M1 改为全图宽度的横向条带，或高度压缩到全图 22%-26%。
- `Model package -> Koopman model interface` 用竖直虚线下接，再水平折线进入 M3。
- 标签改为无背景文字：`Phi_theta, A, B, N_l, C, bounds`。

### 2. M2 模块

问题：

- `Reference path + 4WS model -> Local path packet` 是斜线。
- M2 左上和中部空白较明显。
- `Reference communication` 与 M3 的输出箭头贴着边界，标签挤在模块边缘。

修改：

- M2 内部改成 `2 x 2` 布局。
- `Reference communication` 放在右下，作为统一出口。
- 输出到 M3 的两条线从 M2 右侧同一出口组引出，分别进入 M3 的 delay prediction 和 quality-aware consensus。

### 3. M3 模块

问题：

- `Model interface` 到两个子模块的线是斜线。
- `Candidate control sequence -> M4` 的蓝色线绕行不够清楚。
- M3 右侧和底部仍有较多空白。

修改：

- `Model interface` 放在 M3 顶部居中，下接两条竖线/折线到 `Observation fusion and lifting` 与 `Koopman prediction`。
- `Candidate control sequence` 放在 M3 右下或底中，直接水平输出到 M4 左边。
- M3 到 M4 的主箭头只保留一条：`candidate command + predicted margins`。

### 4. M4 模块

问题：

- `Safe command` 到 M5 是斜线。
- `Certificate metrics`、`Certificate passes?` 和 `Safe command` 之间线条过密。
- `yes` 和 `no` 标签仍有灰底。
- `Fallback command` 回到 certificate 的虚线为红色竖线，含义可以，但需要更规整。

修改：

- `Safe command output` 移到 M4 最右侧，与 M5 `Command publication and communication` 横向对齐。
- `Certificate passes?` 菱形放在 M4 中心偏右。
- `yes` 出口水平向右到 `Safe command output`。
- `no` 出口垂直向下到 `Projection and tightening`。
- `Projection and tightening -> Degraded fallback -> Certificate metrics/check` 用红色折线，不要斜线。
- `Certificate metrics` 可以放在菱形上方，接收来自 M5 的灰色反馈。

### 5. M5 模块

问题：

- M5 内部纵向留白偏大。
- `Command publication / communication` 和 `Vehicle-payload system` 的距离较大。
- Feedback logs 的三条输出线都在右下角汇集，局部拥挤。

修改：

- M5 宽度可以略减，高度与下方模块保持一致。
- 三个小模块等距竖排。
- Feedback logs 输出分成三条正交反馈线：
  - 到 M3 observation：`x_{i,k+1}, e_y, e_s`
  - 到 M4 FDI：`y_i, yhat_i, r_i`
  - 到 M4 certificate metrics：`V_k, m_k, force proxy, g(x,u)`
- 三条反馈线可以共用一条底部灰色虚线主干，然后分叉上接，避免多条斜线。

## 六、颜色与线型建议

### 大模块颜色

当前颜色可以保留，但建议降低饱和度，让线条和文字更突出：

| 模块 | 建议底色 | 边框 |
|---|---|---|
| M1 Offline learning | very light blue | medium blue |
| M2 Reference/communication | very light teal | teal |
| M3 Online prediction/MPC | very light steel blue | steel blue |
| M4 Safety/certificate | very light red | red |
| M5 Environment/feedback | very light purple | purple |

### 箭头颜色

| 箭头类型 | 颜色 | 线型 |
|---|---|---|
| 主前向数据/命令流 | 深蓝或黑灰 | 实线 |
| 参考/通信状态输入 | teal | 实线 |
| 离线模型加载 | 蓝色 | 虚线 |
| 反馈日志/测量回流 | 灰色 | 虚线 |
| 证书失败/保护/fallback | red | 实线或虚线，但只用于失败路径 |

不要让红色箭头表示普通安全模块内部所有数据流。红色应只表示 certificate fail、projection、fallback 这类保护路径。

## 七、建议的最终结构草图

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ M1 Offline learning layer                                                                │
│  Offline data -> Koopman lifting + bilinear regression -> IRSP -> Model package          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Phi_theta, A, B, N_l, C, bounds
                                  v
┌──────────────────────┬──────────────────────────────┬────────────────────────┬──────────┐
│ M2 Reference/comm.   │ M3 Online prediction/MPC      │ M4 Safety/certificate  │ M5 Env.  │
│                      │                              │                        │ feedback │
│ 4WS local-path pub.  │ Koopman model interface       │ FDI residual monitor   │ Command  │
│      -> tmp packet   │ Observation fusion + lifting  │ FTC command realloc.   │ pub/comm │
│ Link-quality monitor │ Delay-compensated prediction  │ Certificate metrics    │    │     │
│      -> ref comm.    │ Quality-aware consensus       │ Certificate passes?    │ Vehicle  │
│                      │ Communication-quality MPC     │ Projection/tightening  │ payload  │
│                      │ Candidate control sequence    │ Degraded fallback      │    │     │
│                      │                              │ Safe command output    │ Logs     │
└──────────────────────┴──────────────────────────────┴────────────────────────┴──────────┘
```

主流程：

```text
M2 -> M3: delayed path packet, r_ref; q_ij,k, tau_ij,k, ell_ij,k
M3 -> M4: u_i^*, predicted trajectory, margins
M4 -> M5: u_k^safe
```

反馈流：

```text
M5 -> M3: x_{i,k+1}, e_y, e_s
M5 -> M4 FDI: y_i, yhat_i, r_i
M5 -> M4 certificate: V_k, m_k, force proxy, g(x,u)
M4 -> M3: tightened bounds, contracted reference
```

## 八、是否需要调整 caption

建议 Fig. 2 caption 同步改成与图一致：

```text
Module-level data flow of NR-KDCC. Solid arrows denote forward reference,
prediction, control, and command flow within one sampling period. Dashed
arrows denote offline model loading and closed-loop feedback. Red arrows
indicate certificate-triggered projection, tightening, and degraded fallback.
```

中文理解：这张图不是单纯流程图，而是模块级数据接口图。caption 要告诉审稿人颜色和线型是什么意思。

## 九、最终检查清单

下一版画完后按下面检查：

- [ ] 所有大模块整体外边界是否形成一个规整长矩形。
- [ ] 所有连接线是否横平竖直，没有斜线。
- [ ] 信号标签是否全部无背景、无边框。
- [ ] 标签是否不压住箭头、不压住模块边框。
- [ ] M2、M3、M4、M5 底边是否对齐。
- [ ] 大模块内部是否没有明显大片空白。
- [ ] 小模块名称是否都能在正文中找到对应概念。
- [ ] `N_l`、`q_ij`、`tau`、`ell`、`u^safe` 等符号是否统一。
- [ ] 红色是否只用于 certificate fail / projection / fallback。
- [ ] `Feedback logs` 是否没有连到 `no` 出口，而是连到 FDI、certificate metrics 和 observation。

## 结论

当前 reviewfix 版可以作为结构草稿，但需要按投稿图标准重画。最关键的修改不是再增加内容，而是删掉视觉噪声、规范线条、收紧模块尺寸、统一命名。建议下一版直接按“顶部 M1 条带 + 下方 M2-M5 四列”的长矩形结构重做，并把所有信号标签改为无背景文字。
