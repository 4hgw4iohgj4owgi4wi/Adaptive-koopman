# Fig. 2 新版模块化数据流图审查意见

审核对象：

`figures/fig2_nrkdcc_module_dataflow_pub_20260528.vsdx`

辅助导出预览：

`figures/fig2_nrkdcc_module_dataflow_pub_20260528.exported.png`

## 总体评价

新版 Fig. 2 的方向是对的：已经从原来的单链路流程图，改成了 `M1-M5` 五个大模块，并且开始标注跨模块数据。这比上一版更符合 Fig. 1 的框架逻辑。

但这版还不建议直接放入论文主文。主要问题是：图面过宽、文字过小、箭头标签过密，部分箭头逻辑仍容易误读。尤其是作为双栏论文的 `figure*` 插入后，很多标签会不可读。

当前图里约有 96 个对象，信息量偏大。主文 Fig. 2 应该控制在“模块关系清楚、关键接口清楚”，不要试图把所有内部变量都塞进一张图。

## 必须修改的问题

### 1. 版式太宽，缩放后不可读

当前页面比例约为 `19:8`，横向过长。插入论文后，如果宽度设为 `0.92\textwidth` 或 `\textwidth`，高度会被压缩，所有箭头标签都会变得很小。

建议改为两行或三行结构，而不是五个模块几乎一字排开：

```text
M1 Offline learning layer
        |
        v
M2 Reference/communication -> M3 Prediction/MPC -> M4 Safety/certificate -> M5 Environment
        ^                         ^                     ^                     |
        +-------------------------+---------------------+---------------------+
```

更推荐：

```text
top row:    M1 Offline learning layer
middle row: M2 Reference/communication -> M3 Prediction/MPC -> M4 Safety/certificate
right/bot:  M5 Vehicle-payload environment and feedback
```

这样能减少长距离斜箭头，也能把字体放大。

### 2. 模块标题不够醒目

`M1 Offline learning`、`M2 Reference and communication` 等标题现在太小，且与浅色模块背景融合，审稿人第一眼不一定能看到五个大模块。

建议每个大模块使用独立标题条：

- 标题条放在模块顶部，深色字、加粗。
- 标题字号至少比小模块文字大 1.5-2 pt。
- 标题建议写完整：
  - `M1 Offline learning layer`
  - `M2 Upper-layer reference and communication`
  - `M3 Online prediction and consensus-MPC`
  - `M4 Safety, FDI/FTC, and certificate`
  - `M5 Vehicle-payload environment and feedback`

### 3. 箭头标签太多、太小

现在几乎每条内部箭头都带小白框标签，例如 `samples`、`bounds`、`z,A,B,N,C`、`q,tau,loss`、`xhat_i,k:k+H` 等。单独看 Visio 能读，但放到论文里会很吃力。

建议原则：

- **跨大模块箭头必须标数据名。**
- **模块内部箭头只保留最关键的 1-2 个标签。**
- 小模块内部细节放 caption 或正文，不必全部放在图中。

保留的跨模块标签建议为：

| 起点 | 终点 | 建议标签 |
|---|---|---|
| M1 -> M3 | model package | `Phi_theta, A, B, N_l, C, IRSP bounds` |
| M2 -> M3 | reference packet | `P_{i,k-d}^{tmp}, r_ref` |
| M2 -> M3 | communication state | `q_{ij,k}, tau_{ij,k}, loss` |
| M3 -> M4 | candidate command | `u_i^*, predicted trajectory, constraint margins` |
| M4 -> M5 | safe command | `u_i^{safe}` |
| M5 -> M3 | state feedback | `x_{i,k+1}, e_y, e_s` |
| M5 -> M4 | certificate metrics | `V, margin, force proxy, g(x,u)` |

其余内部标签可以删减。

### 4. `Errors/logs` 到 certificate 的反馈仍可能误读

你上一轮指出的问题已经比旧版好：现在不再是红色箭头直接接 `no` 出口，而是灰色虚线反馈。

但当前灰色虚线从 `Feedback logs` 斜向进入 `Certificate passes?` 菱形下侧，视觉上仍然靠近 `no` 分支，容易被误解为日志触发了失败分支。

建议加一个小中间节点，避免直接连到菱形：

```text
Feedback logs
   |
   | V, margin, force proxy, g(x,u)
   v
Certificate metrics
   |
   v
Certificate passes?
```

或者让反馈箭头进入 `Certificate passes?` 的左侧/上侧，并明确写：

`feedback metrics, not branch decision`

但论文图里不建议写这么解释性的文字，更推荐加 `Certificate metrics` 小节点。

### 5. 缺少 FDI/FTC 的测量反馈输入

当前 `FDI/FTC repair` 主要接收来自 M3 的 `u_i^*, margins`，然后输出 `r_i, eta_i, u_tilde` 到 certificate。这个逻辑不完整。

FDI residual monitoring 至少需要实际测量/预测残差信息，应该从 M5 或 M3 反馈进来：

```text
M5 Feedback logs / sensor response -> FDI residual monitoring
label: measured response y_i, predicted response hat{y}_i, residual r_i
```

如果不加这条，读者会问：`r_i` 从哪里来？`FDI` 怎么检测故障？

建议把 M4 内部拆成两个小模块：

1. `FDI residual monitor`
2. `FTC reallocation`

数据流：

```text
measured/predicted response -> FDI residual monitor -> fault flag, eta_i -> FTC reallocation
candidate u_i^* -> FTC reallocation -> repaired command tilde u_i -> certificate check
```

### 6. M1 离线学习模块少了 bilinear regression 的明确环节

当前 M1 是：

`Offline data -> Koopman learning -> IRSP projection -> Model package`

这过于简化。文章方法里强调的是 bilinear Koopman predictor，因此图中最好明确出现：

```text
Offline data generation
    -> Lifting network Phi_theta
    -> Bilinear Koopman regression
    -> IRSP stability projection
    -> Model package
```

如果空间不足，可以把中间两个合并成：

`Lifting + bilinear regression`

当前箭头标签 `z,A,B,N,C` 也建议改为：

`z_k, A, B, N_l, C`

不要写 `N`，应与正文的 bilinear operator 记号一致。

### 7. M1 到 M3 的模型包输入目标不够准确

当前 `Model package` 的虚线大致接到 `Observation + lifting`。但模型包不只供 lifting 用，也供 Koopman prediction、MPC/certificate bounds 使用。

建议在 M3 顶部加一个小接口节点：

```text
Model interface
Phi_theta, A, B, N_l, C, bounds
```

然后从这个接口分别连到：

- `Observation + lifting`：`Phi_theta`
- `Koopman prediction`：`A, B, N_l, C`
- `MPC/certificate`：`IRSP bounds, UUB/certificate bounds`

这样更符合方法结构。

## 建议修改的问题

### 8. M4 中红色箭头使用过多

当前 M4 内部几乎所有箭头都是红色。这样会导致读者误以为整个 safety/certificate 模块都是异常分支。

建议：

- 正常安全检查链路用深灰或深蓝：
  - `FDI residual monitor -> FTC reallocation -> certificate check`
  - `certificate yes -> safe command`
- 只有证书失败和 fallback 链路用红色：
  - `certificate no -> projection/tightening`
  - `projection/tightening -> fallback`
  - `fallback -> certificate recheck`

这样红色才表示“保护/失败路径”，不会泛化成普通数据流颜色。

### 9. `Projection / / tightening` 有排版错误

当前小模块文字显示为：

`Projection / / tightening`

建议改为：

`Projection and tightening`

或：

`Projection / tightening`

同类问题还有：

`Feedback logs / errors / forces / / constraints`

建议改为：

`Feedback logs`

小字补充：

`errors, forces, constraints`

### 10. M5 名称建议更准确

当前标题是：

`M5 Environment feedback`

建议改为：

`M5 Vehicle-payload environment and feedback`

或短一点：

`M5 Environment and feedback`

因为这个模块不仅反馈，也包含 command channel、vehicle-payload system 和执行过程。

### 11. Command channel 需要和 command publication 区分

当前 M5 里只有 `Command channel`，M4 里有 `Safe command`。如果图面空间允许，建议 M5 内部写成：

```text
Command publication / communication
        |
        | u_{i,k}^{recv}
        v
Vehicle-payload system
```

如果保留一个框，建议标题改为：

`Command publication and communication`

这样与正文中 command publication、communication channel 的说法更一致。

### 12. M2 的 reference communication 应强调 delayed packet

当前 M2 到 M3 的箭头标签是 `P_i,k-d^tmp`，方向是对的，但建议写得更清楚：

`delayed local path packet P_{i,k-d}^{tmp}`

M2 内部 `path,kappa,v; 4WS` 建议改为：

`r_ref, kappa_ref, v_ref -> 4WS local path`

这样读者更容易理解 4WS 的作用。

### 13. M3 内部命名需要更贴近正文

建议改名：

- `Observation + lifting` -> `Observation fusion and lifting`
- `Delay / remote prediction` -> `Delay-compensated remote-state prediction`
- `Quality-aware consensus` 保留
- `MPC optimizer cost + constraints` -> `Consensus-MPC cost and constraints`
- `Candidate control` -> `Candidate control sequence`

### 14. 大量斜箭头影响阅读

当前有多条长斜箭头，例如 M2 到 M3、M3 到 M4、M5 到 M4。建议改成正交折线，尽量让箭头遵循：

- 左到右：主前向数据流
- 上到下：模块内部处理
- 右到左/下方虚线：反馈流

这样读者不用追踪斜线穿过模块。

### 15. 底部 legend 太小

底部说明：

`Solid: forward data/command; dashed: model loading or feedback; red: certificate-triggered protection.`

现在太小，放论文里基本看不到。建议：

- 要么删掉，放进 caption；
- 要么做成可视化 legend：三条短线 + 文字，字号和图中文字一致。

更推荐放进 caption：

`Solid arrows denote forward data/command flow; dashed arrows denote model loading or feedback; red arrows denote certificate-triggered protection and fallback.`

## 推荐重画结构

建议将图压缩成下面的结构，减少斜线和标签数量：

```text
                  M1 Offline learning layer
        Offline data -> Lifting + bilinear regression -> IRSP
                         |
                         | model package: Phi_theta, A, B, N_l, C, bounds
                         v

M2 Reference/communication  ->  M3 Online prediction/MPC  ->  M4 Safety/certificate  ->  M5 Environment
Reference path + 4WS             Observation + lifting          FDI monitor               Command channel
Local path packet                Delay compensation             FTC reallocation           Vehicle-payload system
Link-quality monitor             Quality-aware consensus         Certificate check          Feedback logs
Reference communication          MPC optimizer                   Projection/fallback

M5 feedback logs -- measured state, e_y, e_s ------------------> M3 Observation
M5 feedback logs -- V, margin, force proxy, g(x,u) ------------> M4 Certificate metrics
M5 feedback logs -- measured/predicted response, r_i ----------> M4 FDI monitor
M4 projection -- tightened bounds, contracted reference --------> M3 MPC optimizer
```

## 可以保留的优点

- 五个大模块的拆分方向正确。
- M2、M3、M4、M5 的主流程已经基本成型。
- 现在明确出现了 `P_i,k^tmp`、`q/tau/loss`、`u_i^*`、`u_i^safe`、`V/margin/F/g`，比旧版只有功能块更有信息量。
- `Errors/forces/constraints/logs` 不再用红色箭头连到 `no` 分支，这是正确方向。

## 结论

这版 Fig. 2 是一个好的结构草稿，但还不是投稿版。下一轮应优先做三件事：

1. 缩短横向比例并放大文字。
2. 减少内部箭头标签，只保留跨模块关键数据名。
3. 补上 `Feedback logs -> FDI residual monitor`，并把 `Feedback logs -> Certificate` 改成经由 `Certificate metrics` 的反馈输入。

完成这些后，这张图才会真正起到“框架图 + 信息流图”的作用，而不是变成一个难读的全变量流程表。
