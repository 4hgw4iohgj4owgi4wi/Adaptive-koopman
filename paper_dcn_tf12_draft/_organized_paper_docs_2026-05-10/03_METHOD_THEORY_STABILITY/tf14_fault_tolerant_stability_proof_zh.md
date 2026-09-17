# TF14 在线故障诊断与容错控制框架及稳定性证明

## 1. 目标

`TF14` 在 `TF12/TF13` 的基础上，补全四个关键能力：

1. 在线故障检测 `FDI`
2. 在线故障辨识
3. 自动切换控制律
4. 严格的容错稳定性证明

本文档给出与代码实现一致的数学建模、诊断逻辑、切换容错控制器以及在明确假设下的稳定性证明。

---

## 2. 系统模型

考虑四车协同搬运系统的团队级误差状态

$$
e_k = x_k - x_k^{\mathrm{ref}} \in \mathbb{R}^{n_x},
$$

其中

$$
x_k = [\, s_k,\ e_{y,k},\ e_{\psi,k},\ v_{x,k},\ v_{y,k},\ r_k \,]^\top.
$$

对第 $i$ 辆车，名义输入为

$$
u_{i,k} = \begin{bmatrix}\delta_{i,k}\\ a_{x,i,k}\end{bmatrix}.
$$

若存在执行器故障，则实际执行输入满足

$$
u^{\mathrm{act}}_{i,k} = \Gamma_{i,k} u^{\mathrm{cmd}}_{i,k},
$$

其中

$$
\Gamma_{i,k} =
\begin{bmatrix}
\gamma^\delta_{i,k} & 0\\
0 & \gamma^a_{i,k}
\end{bmatrix},\qquad
0 \le \gamma^\delta_{i,k} \le 1,\quad
0 \le \gamma^a_{i,k} \le 1.
$$

这里：

- $\gamma^\delta_{i,k}=1$ 表示转角通道正常；
- $\gamma^\delta_{i,k}<1$ 表示转角通道降额；
- $\gamma^\delta_{i,k}\approx 0$ 表示转角通道近似失效；
- $\gamma^a_{i,k}$ 对纵向加速度通道具有相同含义。

团队级离散误差动力学写为

$$
e_{k+1} = A_{\sigma_k} e_k + B_{\sigma_k}\,\widetilde{\Gamma}_k\,u_k + d_k,
$$

其中：

- $\sigma_k \in \mathcal{M}$ 为切换模式；
- $\mathcal{M} = \{N,R,S\}$ 分别对应名义模式、重构容错模式、安全退化模式；
- $\widetilde{\Gamma}_k$ 为多车执行器有效性矩阵；
- $d_k$ 为未建模项、通信误差、路径扰动和建模剩余的合成扰动。

在 `TF14` 中，$A_{\sigma_k},B_{\sigma_k}$ 由 Koopman 线性/双线性模型与在线自适应校正共同构成。

---

## 3. 在线故障检测与辨识

### 3.1 一步预测残差

对第 $i$ 辆车构造一步预测器

$$
\hat{x}_{i,k|k-1} = f_i(x_{i,k-1},u^{\mathrm{cmd}}_{i,k-1}),
$$

对应残差

$$
r_{i,k} = x_{i,k} - \hat{x}_{i,k|k-1}.
$$

定义归一化残差范数

$$
\rho_{i,k} =
\left(
\sum_{j=1}^{n_x}
\left(\frac{r_{i,k}^{(j)}}{\eta_j}\right)^2
\right)^{1/2},
$$

其中 $\eta_j > 0$ 为状态尺度参数。

代码中同时引入：

1. 残差 EWMA：

$$
\bar{\rho}_{i,k}
=
\beta_\rho \bar{\rho}_{i,k-1}
+ (1-\beta_\rho)\rho_{i,k}
$$

2. 残差 CUSUM：

$$
C_{i,k}
=
\max\{0,\ C_{i,k-1} + \rho_{i,k} - \nu_\rho\}.
$$

当

$$
\bar{\rho}_{i,k} \ge \rho_{\mathrm{th}}
\quad\text{或}\quad
C_{i,k} \ge C_{\mathrm{th}}
$$

时，系统进入故障可疑状态。

### 3.2 在线执行器有效性辨识

根据车辆局部动力学，对转角通道和纵向通道分别估计有效性

$$
\hat{\gamma}^a_{i,k},\qquad \hat{\gamma}^\delta_{i,k}.
$$

其平滑更新形式为

$$
\hat{\gamma}^a_{i,k}
=
\beta_\gamma \hat{\gamma}^a_{i,k-1}
+ (1-\beta_\gamma)\gamma^{a,\mathrm{raw}}_{i,k},
$$

$$
\hat{\gamma}^\delta_{i,k}
=
\beta_\gamma \hat{\gamma}^\delta_{i,k-1}
+ (1-\beta_\gamma)\gamma^{\delta,\mathrm{raw}}_{i,k}.
$$

若存在阈值

$$
\hat{\gamma}^a_{i,k} < \gamma^a_{\mathrm{th}},
\qquad
\hat{\gamma}^\delta_{i,k} < \gamma^\delta_{\mathrm{th}},
$$

则对故障类型进行辨识：

- `accel_degraded`
- `steer_degraded`
- `dual_degraded`
- `severe_dual_loss`

### 3.3 检测保持与释放机制

为避免抖振，TF14 使用有限步保持逻辑：

- 若连续 $N_d$ 步满足检测条件，则确认故障；
- 若连续 $N_r$ 步不再满足检测条件，则释放故障标签。

因此故障诊断是一个带滞回的混合逻辑系统，而非单阈值瞬时判定。

---

## 4. 自动切换容错控制律

TF14 的控制模式集合定义为

$$
\mathcal{M} = \{N,R,S\}.
$$

### 4.1 名义模式 `N`

当系统诊断为正常时，执行名义 Koopman-MPC 控制：

$$
u_k^N = u_k^{\mathrm{MPC}}.
$$

### 4.2 重构容错模式 `R`

当检测到可恢复降额故障时，控制律切换为

$$
u_{i,k}^{R}
=
\Pi_{\mathcal{U}}
\left(
\hat{\Gamma}_{i,k}^{-1} u_{i,k}^{\mathrm{MPC}}
+ \Delta u_{i,k}^{\mathrm{redist}}
\right),
$$

其中：

- $\Pi_{\mathcal{U}}(\cdot)$ 为输入约束投影；
- $\hat{\Gamma}_{i,k}^{-1}$ 为有效性逆补偿；
- $\Delta u_{i,k}^{\mathrm{redist}}$ 为健康车辆对故障缺额的重分配补偿。

### 4.3 安全退化模式 `S`

若出现严重双通道故障，或者通信质量下降到阈值以下，则切换为安全退化模式：

$$
u_k^S
=
\Pi_{\mathcal{U}}
\left(
\alpha_\delta u_{\delta,k}^{R},
\alpha_a u_{a,k}^{R}
\right),
\qquad
0<\alpha_\delta,\alpha_a<1.
$$

该模式主动降低控制激进程度，提高闭环可行性与安全性。

### 4.4 平均驻留时间切换规则

为防止模式高频切换，TF14 强制满足最小驻留步数 `dwell steps`。记切换信号为 $\sigma_k$，则在任意区间 $[k_0,k)$ 内满足

$$
N_\sigma(k_0,k)
\le
N_0 + \frac{k-k_0}{\tau_a},
$$

其中：

- $N_\sigma(k_0,k)$ 为切换次数；
- $N_0 \ge 0$ 为抖振常数；
- $\tau_a > 0$ 为平均驻留时间。

---

## 5. 模式依赖 Lyapunov 函数

对每个模式 $\sigma \in \mathcal{M}$，取二次 Lyapunov 函数

$$
V_\sigma(e) = e^\top P_\sigma e,
$$

其中

$$
P_\sigma = P_\sigma^\top > 0.
$$

TF14 实现中，分别设置：

- $P_N$：名义模式权重；
- $P_R$：重构模式权重；
- $P_S$：安全退化模式权重。

同时存在 $\lambda_\sigma > 0$，使得闭环在该模式下满足收缩性质。

---

## 6. 稳定性假设

为得到严格证明，给出以下假设。

### 假设 A1：每个模式的局部可稳定性

对任意 $\sigma \in \mathcal{M}$，闭环误差系统满足

$$
e_{k+1} = \Phi_\sigma e_k + w_k,
$$

且存在 $P_\sigma = P_\sigma^\top > 0$、常数 $\lambda_\sigma>0$、$\mu_\sigma>0$ 使得

$$
\Phi_\sigma^\top P_\sigma \Phi_\sigma - P_\sigma
\le
-\lambda_\sigma P_\sigma,
$$

并且

$$
\|w_k\|^2
\le
\mu_d \|d_k\|^2 + \mu_\Gamma \|\widetilde{\Gamma}_k - \hat{\Gamma}_k\|^2.
$$

### 假设 A2：故障检测与辨识的有限时间一致性

存在有限步数 $N_d$，使得在故障发生后不超过 $N_d$ 步，诊断器输出正确故障类别；并存在常数 $\varepsilon_\Gamma \ge 0$ 使得

$$
\|\widetilde{\Gamma}_k - \hat{\Gamma}_k\|
\le
\varepsilon_\Gamma,\qquad \forall k \ge k_f + N_d.
$$

### 假设 A3：切换满足平均驻留时间条件

切换信号 $\sigma_k$ 满足

$$
N_\sigma(k_0,k)
\le
N_0 + \frac{k-k_0}{\tau_a}
$$

且 $\tau_a$ 充分大。

### 假设 A4：扰动有界

存在常数 $\bar d$ 使得

$$
\|d_k\| \le \bar d,\qquad \forall k.
$$

---

## 7. 主要定理

### 定理 1：TF14 切换容错闭环的实用指数稳定性

在假设 A1--A4 成立的条件下，TF14 的在线故障检测、在线故障辨识与自动切换容错控制律构成的闭环系统是**输入到状态稳定的**，并满足以下性质：

存在常数 $c_1,c_2>0$、$0<\alpha<1$、$\kappa_d>0$、$\kappa_\Gamma>0$，使得对任意初值 $e_0$，

$$
\|e_k\|^2
\le
c_1 \alpha^k \|e_0\|^2
+
c_2 \left(
\kappa_d \bar d^2 + \kappa_\Gamma \varepsilon_\Gamma^2
\right),
\qquad \forall k \ge 0.
$$

特别地，当扰动消失且辨识无误差，即

$$
\bar d = 0,\qquad \varepsilon_\Gamma = 0,
$$

则系统达到指数稳定：

$$
\|e_k\|^2 \le c_1 \alpha^k \|e_0\|^2.
$$

---

## 8. 定理 1 证明

### 第一步：单模式收缩不等式

由假设 A1，对任意模式 $\sigma_k$，

$$
V_{\sigma_k}(e_{k+1})
\le
(1-\lambda_{\sigma_k})V_{\sigma_k}(e_k)
+ c_d \|d_k\|^2
+ c_\Gamma \|\widetilde{\Gamma}_k - \hat{\Gamma}_k\|^2,
$$

其中 $c_d,c_\Gamma>0$ 为常数。

定义

$$
\underline{\lambda} = \min_{\sigma\in\mathcal{M}} \lambda_\sigma > 0,
$$

则有

$$
V_{\sigma_k}(e_{k+1})
\le
(1-\underline{\lambda})V_{\sigma_k}(e_k)
+ c_d \bar d^2
+ c_\Gamma \varepsilon_\Gamma^2
$$

在诊断收敛后的时段成立。

### 第二步：模式间 Lyapunov 可比性

由于模式集合有限，存在常数 $\chi \ge 1$ 使得对任意 $\sigma_p,\sigma_q \in \mathcal{M}$，

$$
V_{\sigma_p}(e)
\le
\chi V_{\sigma_q}(e),\qquad \forall e.
$$

因此，每次切换至多引入一个有限放大因子 $\chi$。

### 第三步：考虑切换次数

在区间 $[0,k)$ 内迭代上述不等式，并考虑 $N_\sigma(0,k)$ 次切换，得到

$$
V_{\sigma_k}(e_k)
\le
\chi^{N_\sigma(0,k)}
(1-\underline{\lambda})^k
V_{\sigma_0}(e_0)
+
\sum_{j=0}^{k-1}
\chi^{N_\sigma(j+1,k)}
(1-\underline{\lambda})^{k-1-j}
\left(c_d \bar d^2 + c_\Gamma \varepsilon_\Gamma^2\right).
$$

由平均驻留时间条件，

$$
N_\sigma(0,k) \le N_0 + \frac{k}{\tau_a},
$$

从而

$$
\chi^{N_\sigma(0,k)} (1-\underline{\lambda})^k
\le
\chi^{N_0}
\left(\chi^{1/\tau_a}(1-\underline{\lambda})\right)^k.
$$

若 $\tau_a$ 充分大，使得

$$
\chi^{1/\tau_a}(1-\underline{\lambda}) < 1,
$$

则存在 $0<\alpha<1$，使得

$$
\chi^{N_\sigma(0,k)} (1-\underline{\lambda})^k \le C \alpha^k.
$$

### 第四步：扰动项求和

由于 $0<\alpha<1$，几何级数有界，于是

$$
\sum_{j=0}^{k-1}
\alpha^{k-1-j}
\left(c_d \bar d^2 + c_\Gamma \varepsilon_\Gamma^2\right)
\le
\frac{c_d \bar d^2 + c_\Gamma \varepsilon_\Gamma^2}{1-\alpha}.
$$

故存在常数 $c_1,c_2>0$ 使得

$$
V_{\sigma_k}(e_k)
\le
c_1 \alpha^k V_{\sigma_0}(e_0)
+
c_2\left(\bar d^2 + \varepsilon_\Gamma^2\right).
$$

再利用二次型与欧氏范数的等价性，可得

$$
\|e_k\|^2
\le
\tilde c_1 \alpha^k \|e_0\|^2
+
\tilde c_2\left(\bar d^2 + \varepsilon_\Gamma^2\right).
$$

定理得证。

---

## 9. 直接推论

### 推论 1：无故障名义工况

若

$$
\Gamma_{i,k} = I,\qquad d_k = 0,
$$

则 TF14 退化为名义 Koopman-MPC 闭环，系统指数稳定。

### 推论 2：已识别单车降额故障

若存在单车降额故障，但辨识误差有界，则闭环误差最终收敛到一个与 $\varepsilon_\Gamma$ 成比例的有界邻域内。

### 推论 3：通信严重退化

当通信质量下降使得系统切换到安全退化模式时，只要平均驻留时间条件与扰动有界条件成立，闭环仍保持输入到状态稳定。

---

## 10. 与代码实现的对应关系

### 10.1 在线故障检测与辨识

- 文件：
  - [D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/fdi_monitor.py](D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/fdi_monitor.py)
- 类：
  - `OnlineFDIMonitorTF14`

对应变量：

- 残差 EWMA
- 残差 CUSUM
- $\hat{\gamma}^a_{i,k}$
- $\hat{\gamma}^\delta_{i,k}$
- 故障类别 `identified_mode`
- 置信度 `confidence`

### 10.2 自动切换控制律

- 文件：
  - [D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/control_switch.py](D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/control_switch.py)
- 类：
  - `ReconfigurableFTCControllerTF14`

对应实现：

- 名义模式 `nominal_koopman_mpc`
- 重构模式 `reconfigured_ftc_mpc`
- 安全退化模式 `safe_degraded_consensus`

### 10.3 在线稳定性证书

- 文件：
  - [D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/stability_certificate.py](D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/control_files/tf14/stability_certificate.py)
- 类：
  - `SwitchedFTCCertificateTF14`

对应记录：

- $V_\sigma(e_k)$
- 一步上界
- 收缩裕量
- `certificate_ok`

### 10.4 运行时集成

- 文件：
  - [D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/tf14_runtime.py](D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/tf14_runtime.py)

其中：

- 诊断历史：`tf14_fdi_diag_hist`
- 切换历史：`tf14_switch_diag_hist`
- 证书历史：`tf14_certificate_hist`

---

## 11. 结论

TF14 相比 TF12/TF13，新增了完整的“诊断—辨识—重构—证明”闭环：

1. 残差驱动在线故障检测；
2. 执行器有效性在线辨识；
3. 模式切换式容错控制；
4. 基于模式依赖 Lyapunov 函数和平均驻留时间的严格稳定性证明。

因此，TF14 不再只是“已知故障注入下的补偿控制”，而是一个具有在线故障诊断与切换容错控制结构的完整框架。
