# NR-KDCC 一步控制流程图 draw.io 审核稿

生成日期：2026-06-02  
用途：先作为 draw.io 绘图前的详细图纸规格，供逐部分审核；审核通过后再生成正式 `.drawio` 图。

## 0. 依据与图的定位

主要依据：

- `manuscript_main_content_methods_logic_en_latex_20260530.md`
- `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev5_p12to11_20260528.pdf`
- 当前英文 TeX 中的 `fig:nrkdcc_flowchart` 位置与说明
- 既有 Fig. 2 审查稿：`fig2_nrkdcc_mpc_redraw_review_revision_20260530.md`

这次不再画“泛化模块数据流图”，而是画 **one sampling period control flow**，也就是一个采样周期内从参考路径进入、经过通信/预测/MPC/安全执行、再反馈到下一步的控制闭环。

目标图名建议：

`One-step control flow of NR-KDCC within one sampling period`

论文图注建议：

`One-step control flow of NR-KDCC within one sampling period. The upper offline band provides the projected bilinear Koopman model and certified input/residual bounds. The online path proceeds from the environment-derived reference path to 4WS local path publication, communication-quality processing, observation fusion, delay-compensated Koopman prediction, C-mode scheduled consensus MPC, FDI/FTC protection, certificate-based switching, safe command publication, and vehicle-payload feedback.`

审核点：

- 是否同意把这张图定位为“一步控制流程图”，而不是替代总框架图。
- 是否同意图内英文标签用于论文，中文仅保留在本审核稿中。

## 1. 总体版式

要求满足用户指定：

- 步骤从左到右。
- 左边开始是从环境得到的参考路径。
- 离线部分放在上方。
- 使用控制系统符号表达相加、对比、切换、限制、延迟和反馈。

推荐 draw.io 画布：

- `width = 1800`
- `height = 680`
- 横向 `figure*` 双栏图使用。
- 主流程放在中下部，离线模块放在上方横条。
- 底部放反馈总线，从车辆-载荷系统回到左侧误差计算、通信处理、FDI/FTC 和证书模块。

文本版排布草图：

```text
----------------------------------------------------------------------------------+
| OFFLINE BAND                                                                     |
| Scenario data -> Lifting + bilinear regression -> IRSP projection -> Model pkg   |
|                                       |                         |                |
+---------------------------------------+-------------------------+----------------+
                                        v                         v

[Environment reference path]
          |
          v
   (Σ reference - feedback)
          |
          v
[Upper 4WS local path publisher]
          |
          v
[Communication quality / delay / loss processor] -- packet loss switch / z^-tau
          |
          v
[Observation fusion + Koopman rollout]
          |
          v
[C-mode scheduler + consensus MPC]
          |
          v
[FDI/FTC + command projection] -> <certificate passes?> -- yes --> [Safe command publication]
                                      | no                          |
                                      v                             v
                         [tightening / fallback switch] -------> [Vehicle-payload plant]
                                                                      |
                                                                      v
                         <---------------- feedback bus ---------------+
```

审核点：

- 主流程是否保持你要求的“左到右”。
- 离线上方是否接受做成横向 band，而不是左侧一个独立大块。
- 底部反馈总线是否接受，避免反馈线穿过主流程。

## 2. 主流程模块定义

### M0 Environment-derived reference path

英文图内标签：

`Environment-derived reference path`

小字变量：

`p_L^ref(s), psi_L^ref(s), kappa_r(s), v_ref`

图形：

- 起始输入块，可用圆角矩形或路径图标式小块。
- 放在最左侧。
- 表示参考路径来自环境/道路/任务规划，而不是从控制器内部凭空生成。

输出：

- 参考载荷中心路径 `p_L^ref(s)`
- 参考航向 `psi_L^ref(s)`
- 曲率 `kappa_r(s)`
- 速度或进度参考 `v_ref, s_k`

进入下一模块：

- 到 `Σ` 误差计算节点。
- 同时进入上层 4WS 路径发布器，用于生成局部路径包。

审核点：

- 左起点名称是否用 `Environment-derived reference path`。
- 是否需要把 `road/map/task planner` 写在同一框内。

### S1 Summing junction: reference-feedback error

英文图内标签：

`Σ`

旁边小字：

`e_L, e_y, e_psi`

图形：

- 控制系统求和圆圈。
- 参考路径从左侧以 `+` 进入。
- 车辆-载荷反馈从底部反馈总线以 `-` 进入。

计算含义：

- 载荷中心误差：
  `e_L = [X_L-X_L^ref, Y_L-Y_L^ref, psi_L-psi_L^ref]^T`
- 车辆路径坐标误差：
  `e_y, e_psi`
- 连接误差后续由车辆/载荷几何反馈产生：
  `e_c = col(e_c,1,...,e_c,N)`

输出：

- `e_L, e_y, e_psi, e_c`

进入下一模块：

- `Upper 4WS local path publisher`
- `Observation fusion`
- `Consensus MPC`

审核点：

- 是否把相加/相减明确画成圆形求和节点，而不是普通方框。
- 是否接受反馈误差在这里统一计算，而不是分散在每个模块内。

### M1 Upper 4WS local path publisher

英文图内标签：

`Upper 4WS local path publisher`

小字变量：

`kappa_r -> beta^4ws, kappa^4ws -> P_i,k^tmp`

图形：

- 控制/规划处理块。
- 放在 `Σ` 之后。

内部小模块建议：

1. `Curvature and payload progress`
   - 输入 `s_k, kappa_r(s_k), psi_L^ref`
2. `Equivalent 4WS geometry`
   - 计算 `beta^4ws, kappa^4ws`
3. `Vehicle-specific local packets`
   - 输出 `P_i,k^tmp`

核心含义：

- 上层用等效 4WS 几何作为参考发布机制。
- 它不是替代下层车辆动力学，只负责在高曲率/局部预瞄中给每台车发布临时路径包。

输出：

- `P_i,k^tmp`
- `r_ref`
- `kappa_r`
- 高曲率标志或曲率强度 `|kappa_r|`

进入下一模块：

- 进入通信处理模块，路径包可能被延迟、丢包、污染。
- 曲率信号也进入 C-mode 调度器。

审核点：

- 是否保留 4WS 细节在主图中。
- 是否把 4WS 定位为“reference publication”，而不是单独控制器。

### M2 Communication processing and link-quality monitor

英文图内标签：

`Communication processing and link-quality monitor`

小字变量：

`q_ij,k, q_k^net, tau, loss, bias/noise`

图形：

- 主处理块。
- 内部放延迟块、开关块和质量监视块。

内部控制系统符号：

1. 延迟块：
   - 标签：`z^{-tau_ij,k}`
   - 表示邻居状态、距离、路径包的延迟。
2. 丢包/保持开关：
   - 标签：`loss?`
   - yes 分支：`hold / fallback estimate`
   - no 分支：`Koopman extrapolation`
3. 对比器：
   - 标签：`q compare`
   - 对 `q_ij,k` 和阈值比较，输出可靠/退化状态。

输入：

- `P_i,k^tmp`
- 邻车状态或距离 `x_j, d_ij`
- 载荷中心横向误差或反馈 `e_y,L`
- 通信日志 `tau, loss, beta, epsilon`

输出：

- 延迟/退化路径包 `hat P_i,k^tmp`
- 网络邻车估计 `hat x_j,k^net`
- 平滑链路质量 `bar q_ij,k`
- 全局网络质量 `q_k^net`
- 丢包和延迟统计 `ell_ij,k, tau_ij,k`

进入下一模块：

- `Observation fusion + Koopman rollout`
- `C-mode scheduler + consensus MPC`
- `Certificate metrics`

审核点：

- 是否同意把 network cloud 改为通信处理模块，而不是孤立云朵。
- 是否保留 `z^{-tau}` 延迟符号和 `loss?` 开关。

### M3 Observation fusion and Koopman rollout

英文图内标签：

`Observation fusion and Koopman rollout`

小字变量：

`chi_k -> Phi_theta -> z_k -> z_k+1|k`

图形：

- 处理块，内部含多路输入汇合符号。
- 可在左侧放一个 MUX/汇合节点。

内部小模块建议：

1. `MUX / observation fusion`
   - 汇合本车状态、载荷反馈、连接误差、通信质量、执行器效率和路径上下文。
2. `Lifting`
   - `z_k = Phi_theta(chi_k)`
3. `Projected bilinear rollout`
   - `z_{k+1} = A z_k + B u_k + sum u_l N_l z_k`

输入：

- 来自 `M2` 的 `hat x_j,k^net, q_k^net, tau, loss`
- 来自 `S1` 的 `e_L, e_y, e_psi, e_c`
- 来自离线 band 的 `Phi_theta, A, B, N_l, C, w bounds`
- 候选控制序列或上一控制 `u_k`

输出：

- 预测轨迹 `hat x_{k:k+H|k}`
- 预测邻居状态 `hat x_j,k+h|k`
- 残差上界 `bar w`
- 给 MPC 的预测模型和状态。

审核点：

- 是否将 `Observation fusion` 与 `Koopman rollout` 合在一个主块。
- 是否在图里显示 `chi_k -> z_k` 这个提升过程。

### M4 C-mode scheduler and consensus MPC

英文图内标签：

`C-mode scheduler and consensus MPC`

小字变量：

`C0/C1/C2/C3, J, constraints`

图形：

- 主控制器方框。
- 内部放一个模式切换器和一个 MPC 优化器。

内部控制系统符号：

1. 对比器：
   - 标签：`compare |kappa|, q, ||e_c||, force risk`
   - 对曲率、通信质量、连接误差、力风险做阈值判断。
2. 模式切换器：
   - 标签：`C-mode switch`
   - 输出 `C0/C1/C2/C3`
3. 限幅/饱和块：
   - 标签：`sat[0,1]`
   - 表示 payload-protection switch `sigma_k`
4. MPC 优化器：
   - 标签：`min J subject to tightened constraints`

C-mode 含义：

- `C0`: normal tracking and connection preservation
- `C1`: high-curvature lateral priority
- `C2`: payload protection
- `C3`: conservative degraded fallback

输入：

- 参考/误差：`e_L, e_y, e_psi, e_c`
- 预测轨迹：`hat x_{k:k+H|k}`
- 通信质量：`bar q_ij,k, q_k^net`
- 曲率：`kappa_r`
- 力风险：`hat F_L^xy`
- 证书或保护标志：`m_k, fallback flag`

输出：

- 候选控制序列 `u_{0:H-1}^{mpc}`
- 第一拍候选命令 `u_k^{mpc}`
- 约束裕度 `constraint margins`
- 模式 `mu_k`

进入下一模块：

- `FDI/FTC and command projection`

审核点：

- 是否在主图中保留 `C0/C1/C2/C3`。
- 是否把 `sigma_k` 画成饱和/切换符号。
- 是否接受 MPC 块只写核心目标和约束，不展开完整代价函数。

### M5 FDI/FTC and command projection

英文图内标签：

`FDI/FTC and command projection`

小字变量：

`residual -> eta_hat -> Pi_U`

图形：

- 安全执行层的第一块。
- 用红/粉色边框或淡红背景表示安全保护，但普通流向仍用深灰或蓝色箭头。

内部小模块：

1. `FDI residual monitor`
   - 输入测量响应和预测响应。
   - 输出故障标志和效率估计 `hat eta_i,k`。
2. `FTC reallocation`
   - 根据 `hat eta` 和 `q_k^net` 调整可行控制集合。
3. `Command projection`
   - 标签：`Pi_U(u_k^mpc)`
   - 输出修正命令 `tilde u_k`。

输入：

- `u_k^{mpc}`
- 预测/实测残差 `epsilon_i^pred`
- 执行器响应 `actuator response`
- `hat eta_i,k`
- `q_k^net`

输出：

- 修正命令 `tilde u_k`
- 故障标志 `FDI flag`
- 重分配标志 `FTC flag`
- 保护/回退请求 `fallback request`

进入下一模块：

- `Certificate check`

审核点：

- 是否把 FDI 和 FTC 分开画成两个小块。
- 是否从车辆反馈总线给 FDI 增加测量响应输入，避免看不出故障检测来源。

### D1 Certificate decision switch

英文图内标签：

`Certificate passes?`

小字变量：

`m_k >= -epsilon_m`

图形：

- 菱形判定节点。
- 这是主要“对比/切换”符号之一。

输入：

- 修正命令 `tilde u_k`
- 预测残差上界 `bar w`
- 通信质量 `q_k^net`
- 延迟 `tau`
- 力风险 `hat F_L^xy`
- 模式 `mu_k`
- 当前/预测证书值 `V, Vbar, m_k`

分支：

- yes：进入安全命令发布。
- no：进入 `Projection / tightening / fallback`，再回到证书检查或直接输出保守安全命令。

输出：

- `pass`
- `fail`
- `certificate margin m_k`

审核点：

- 是否接受证书作为单独菱形节点。
- 失败分支是否需要画“回到证书再检查”，还是直接输出 fallback command。

### M6 Projection / tightening / fallback switch

英文图内标签：

`Projection / tightening / fallback`

小字变量：

`C3, tightened U, contracted ref`

图形：

- 保护分支块，连接在证书 no 分支之后。
- 箭头用红色，仅表示失败/保护路径。

动作：

- 约束收紧 `tightened constraints`
- 命令投影 `command projection`
- 参考收缩 `reference contraction`
- 模式切换到 `C3`
- 保守 fallback command

输出：

- `u_k^{fallback}` 或重新修正后的 `u_k^{safe}`
- `fallback flag`

审核点：

- 是否需要在图中明确写 `C3`。
- 是否需要把 `PPC guard` 也写入此块的小字中。

### M7 Safe command publication

英文图内标签：

`Safe command publication`

小字变量：

`u_i,k^safe = [a_x,i, delta_i]`

图形：

- 命令发布块。
- 放在证书 yes/fallback 汇合之后。

控制系统符号：

- 在它前面放一个汇合点，表示 `certificate yes` 与 `fallback` 两条分支汇合。

输出：

- 安全命令 `u_i,k^safe`
- 经过执行通信/接收后进入车辆-载荷系统。

审核点：

- 是否需要保留“command publication / communication”这个独立步骤。
- 是否在图中显示命令是 `[a_x, delta]`。

### P1 Vehicle-payload plant and environment feedback

英文图内标签：

`Vehicle-payload plant and environment feedback`

小字变量：

`x_{k+1}, e_c, force proxy, logs`

图形：

- 标准 plant 方框，放在最右侧。
- 右侧可以加一个小输出端口 `sensors/logs`。

输入：

- `u_i,k^safe`

输出：

- 下一步车辆状态 `x_{i,k+1}`
- 载荷中心反馈 `xi_L,k+1`
- 路径误差 `e_y, e_psi`
- 连接误差 `e_c`
- 力代理 `F_c, hat F_L^xy`
- 约束日志 `g(x,u)`
- 通信日志 `q, tau, loss`
- 证书日志 `V, m_k`
- 执行器响应和残差

反馈去向：

- 到 `Σ`：计算 reference-feedback error。
- 到 `M2`：更新通信质量、延迟、丢包和污染测量。
- 到 `M5`：FDI residual monitor。
- 到 `D1`：certificate metrics。
- 到下一采样周期的日志输入。

审核点：

- 是否把 plant 命名为 `Vehicle-payload plant`，还是用 `Vehicle-payload system`。
- 是否保留 `environment feedback`，强调闭环来自环境实际响应。

## 3. 上方离线 band 细节

### O1 Offline scenario data generation

英文图内标签：

`Offline scenario data`

小字变量：

`nominal / noisy / fault / mixed`

输入：

- 车辆-载荷-通信仿真器。
- 名义、高通信噪声、单执行器故障、混合故障/噪声场景。

输出：

- `x, u, xi_L, e_c, q, tau, loss, eta_hat, certificate logs`

审核点：

- 是否把四类场景写在图中。
- 是否需要把 `curvature variation` 也写入小字。

### O2 Lifting and bilinear regression

英文图内标签：

`Lifting + bilinear regression`

小字变量：

`chi -> Phi_theta -> z, A, B, N_l`

动作：

- 构造增强观测 `chi_k`。
- 学习提升映射 `Phi_theta`。
- 用 ridge regression 拟合双线性 Koopman 动力学。

输出：

- `Phi_theta`
- `A, B, N_l`
- 可选 `C`

审核点：

- 是否需要把 `ridge` 写在框内。
- 是否 `N_l` 采用这个符号，不写成泛化 `N`。

### O3 Input-aware robust spectral projection

英文图内标签：

`IRSP stability projection`

小字变量：

`rho(A_eff(u)) <= r_u`

动作：

- 投影 `A`。
- 缩放 `N_l`。
- 检查输入相关有效矩阵 `A_eff(u)` 的谱半径。
- 生成输入包络和残差界。

输出：

- `A^+, N_l^+`
- `U_s`
- `w bounds`
- `IRSP / certificate bounds`

审核点：

- 是否把 `IRSP` 展开为 `Input-aware robust spectral projection`。
- 是否需要保留谱半径公式小字。

### O4 Model and certificate package

英文图内标签：

`Model and certificate package`

小字变量：

`Phi_theta, A, B, N_l, U_s, w bounds`

连线：

- 虚线向下连接 `M3 Observation fusion and Koopman rollout`。
- 虚线向下连接 `M4 Consensus MPC`。
- 虚线向下连接 `D1 Certificate decision switch`。

审核点：

- 是否接受离线输出不是只给 Koopman，而是也给 MPC 和 certificate。
- 是否需要把 `P_mu` 或证书矩阵放进小字。

## 4. 箭头与信号标签

主流程箭头建议：

| 编号 | 起点 | 终点 | 标签 | 线型 |
|---|---|---|---|---|
| A0 | M0 | S1 | `r_ref(s)` | solid |
| A1 | S1 | M1 | `tracking errors + path context` | solid |
| A2 | M1 | M2 | `P_i,k^tmp, kappa_r` | solid |
| A3 | M2 | M3 | `hat P_i,k^tmp, hat x_j,k^net, q, tau, loss` | solid |
| A4 | O4 | M3 | `Phi_theta, A, B, N_l` | dashed |
| A5 | M3 | M4 | `predicted states, residual bounds` | solid |
| A6 | M2 | M4 | `q_k^net, bar q_ij,k, tightened margins` | solid |
| A7 | M4 | M5 | `u_k^mpc, margins, mu_k` | solid |
| A8 | M5 | D1 | `tilde u_k, eta_hat, residuals` | solid |
| A9 | D1 yes | M7 | `pass` | solid |
| A10 | D1 no | M6 | `fail` | red solid |
| A11 | M6 | D1 或 M7 | `fallback / tightened command` | red solid |
| A12 | M7 | P1 | `u_i,k^safe` | solid |
| F1 | P1 | S1 | `x_{k+1}, xi_L,k+1` | dashed feedback bus |
| F2 | P1 | M2 | `communication logs` | dashed feedback bus |
| F3 | P1 | M5 | `actuator response, residuals` | dashed feedback bus |
| F4 | P1 | D1 | `V, m_k, force proxy, constraints` | dashed feedback bus |

标签规范：

- 论文图内尽量用英文和规范下标。
- draw.io 若不启用 LaTeX，使用 HTML 上下标：
  - `q<sub>ij,k</sub>`
  - `q<sub>k</sub><sup>net</sup>`
  - `u<sub>i,k</sub><sup>safe</sup>`
  - `P<sub>i,k</sub><sup>tmp</sup>`
- 信号标签不要使用白底贴片；使用透明文字，必要时调整线避开文字。

审核点：

- 主箭头 A0-A12 是否完整。
- 是否需要减少图中变量标签，保留更多解释在 caption。

## 5. 控制系统符号清单

正式 draw.io 中建议使用以下符号：

| 符号 | 放置位置 | 表达含义 |
|---|---|---|
| 求和圆圈 `Σ` | M0 后、S1 | 参考路径和反馈状态做差，生成误差 |
| MUX/汇合节点 | M3 左侧 | 多源观测融合为 `chi_k` |
| 延迟块 `z^{-tau}` | M2 内部 | 通信延迟 |
| 二值开关 `loss?` | M2 内部 | 丢包时 hold/fallback，否则 Koopman extrapolation |
| 对比器 `q compare` | M2/M4 内部 | 链路质量阈值判断 |
| 对比器 `risk compare` | M4 内部 | 曲率、连接误差、力风险判断 |
| 饱和块 `sat[0,1]` | M4 内部 | payload-protection switch `sigma_k` |
| 模式切换器 `C0/C1/C2/C3` | M4 内部 | 权重和约束调度 |
| 投影块 `Pi_U` | M5 内部 | 安全命令投影 |
| 菱形判定 `Certificate passes?` | D1 | `m_k >= -epsilon_m` |
| 底部反馈总线 | P1 到 S1/M2/M5/D1 | 下一采样周期闭环反馈 |

审核点：

- 这些控制系统符号是否够用。
- 是否需要加入比较器符号 `>` `<`，还是用菱形 decision 即可。

## 6. 颜色和样式建议

颜色保持克制，不用大面积强对比：

- Offline band：浅蓝 `#EAF3FF`，边框蓝 `#2F6FBB`
- Reference/communication：浅绿 `#E8FAF5`，边框青绿 `#15847D`
- Prediction/MPC：浅灰蓝 `#EEF4FA`，边框蓝灰 `#4B77A8`
- Safety/certificate：浅红 `#FFF1F2`，边框红 `#D64545`
- Plant/feedback：浅紫灰 `#F3EFFB`，边框紫灰 `#7E68A4`
- 正常箭头：深灰 `#374151`
- 离线加载和反馈：灰色虚线 `#6B7280`
- 失败/fallback 分支：红色 `#D64545`

字体：

- 大模块标题：10-11 pt，加粗。
- 小模块：8.5-9 pt。
- 信号标签：7.5-8 pt。
- 避免小于 7 pt。

版式规则：

- 所有主箭头用 orthogonal connector，并绑定 source/target。
- 不用自由手绘线和未绑定 targetPoint。
- 不用白底标签贴片。
- 不让反馈线穿过证书 no 分支，避免误读。
- 红色只用于失败/fallback，普通 safety 内部流向仍用深灰。

审核点：

- 是否同意这套颜色。
- 是否需要按照已有论文 Fig.2 的配色完全继承。

## 7. 信息密度控制

这张图应当保留的核心信息：

1. 左边从环境参考路径开始。
2. 参考与反馈先做差。
3. 上层 4WS 只发布局部路径包。
4. 通信退化不只是网络云，而是延迟、丢包、质量和污染测量的处理。
5. Koopman 预测来自上方离线模型包。
6. MPC 是单一主优化器，C0/C1/C2/C3 是调度模式，不是多个并行控制器。
7. FDI/FTC 依赖环境反馈残差。
8. certificate 通过/失败决定安全发布或 fallback。
9. plant 输出状态、误差、力代理、约束和日志，进入下一采样周期。

这张图不建议塞入的内容：

- 完整 MPC 代价函数。
- 完整 ISS/UUB 证明式。
- 所有实验指标。
- 每条通信变量的完整定义。
- 每台车四个重复支路。

审核点：

- 是否认可“机制完整但不展开所有公式”的取舍。
- 是否需要把某个模块再细分，或者反过来压缩。

## 8. 建议的最终 draw.io 文件和导出文件

审核通过后建议生成：

- `figures/fig2_nrkdcc_one_step_control_flow_20260602.drawio`
- `figures/fig2_nrkdcc_one_step_control_flow_20260602.pdf`
- `figures/fig2_nrkdcc_one_step_control_flow_20260602.png`

如果替换论文现有图：

- TeX 中 `fig:nrkdcc_flowchart` 可以保留 label。
- `\includegraphics` 可替换为新 PDF。
- caption 需同步改为 one-step control flow。

审核点：

- 文件名是否接受。
- 后续是否直接替换现有 `fig:nrkdcc_flowchart`。

## 9. 总审核清单

请重点确认以下 10 项：

1. 主流程是否严格从左到右。
2. 左起点是否就是 `Environment-derived reference path`。
3. 求和节点 `Σ` 是否放在参考路径之后。
4. 离线 band 是否放在上方，并输出到 Koopman/MPC/certificate。
5. 是否保留 4WS local path publisher。
6. 通信模块是否用 `z^{-tau}`、`loss?` 和 `q compare` 表示延迟、丢包和质量评估。
7. Koopman 模块是否显示 `chi_k -> Phi_theta -> z_k -> rollout`。
8. MPC 模块是否显示 `C0/C1/C2/C3` 模式切换。
9. 安全模块是否显示 FDI/FTC、命令投影、证书判定和 fallback。
10. plant 反馈是否同时回到误差计算、通信、FDI/FTC 和证书指标。

我的建议默认方案：

- 保留全部 10 项。
- 图中标签用英文。
- 审核稿保留中文解释。
- 正式 draw.io 做横向 `figure*`。
- 红色只表示证书失败和 fallback。

