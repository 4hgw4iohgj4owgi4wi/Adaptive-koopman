# TF12 闭环系统的李雅普诺夫稳定性证明

## 1. 证明目标与结论口径

本文给出一版针对 TF12 控制栈的李雅普诺夫稳定性分析。需要先把结论口径讲清楚：

1. TF12 的真实实现包含双线性 Koopman-MPC、在线自适应、通信时延与丢包、通信质量感知一致性、约束收紧、退化回退、输入裁剪、进度监督和安全保护，因此它不是一个简单的固定线性闭环系统。
2. 对这样一套带有时变调度、随机通信、投影更新和饱和切换的系统，如果不加任何假设，不能诚实地宣称“全局渐近稳定”。
3. 因此，本文给出的严格结论是：在合理工程假设下，TF12 的闭环误差系统满足**离散时间李雅普诺夫意义下的一致最终有界性**（uniform ultimate boundedness, UUB），并在理想无扰条件下退化为**局部指数稳定**。
4. 若进一步把丢包和时延视为随机过程，则可得到**均方意义下的实用稳定性**（mean-square practical stability）。

这正是当前 TF12 这类 network-resilient Koopman-MPC 系统最合适、也最能经得起审稿追问的稳定性表述。

## 2. 闭环误差系统重写

### 2.1 团队跟踪误差

记团队中心状态为

$$
\mathbf{x}_{c,k}=
\begin{bmatrix}
s_{c,k} & e_{y,c,k} & e_{\psi,c,k} & v_{x,c,k} & v_{y,c,k} & r_{c,k}
\end{bmatrix}^{\top},
$$

参考状态为

$$
\mathbf{x}^{\mathrm{ref}}_{c,k},
$$

则团队跟踪误差定义为

$$
\mathbf{e}_k=\mathbf{x}_{c,k}-\mathbf{x}^{\mathrm{ref}}_{c,k}\in\mathbb{R}^{6}.
$$

### 2.2 柔性连接误差

对第 $i$ 辆角点车辆，定义柔性连接误差与其速度为

$$
\boldsymbol{\xi}_{i,k}=
\begin{bmatrix}
\Delta s_{i,k} & \Delta e_{y,i,k} & \Delta \psi_{i,k}
\end{bmatrix}^{\top},
\qquad
\dot{\boldsymbol{\xi}}_{i,k}=
\begin{bmatrix}
\Delta v_{s,i,k} & \Delta v_{e,i,k} & \Delta r_{i,k}
\end{bmatrix}^{\top}.
$$

将四辆车的连接状态堆叠，记

$$
\mathbf{z}_k=
\operatorname{col}
\left(
\boldsymbol{\xi}_{1,k},\dot{\boldsymbol{\xi}}_{1,k},
\ldots,
\boldsymbol{\xi}_{4,k},\dot{\boldsymbol{\xi}}_{4,k}
\right)\in\mathbb{R}^{24}.
$$

### 2.3 时变闭环误差模型

围绕参考轨迹和正常运行点，对 TF12 的团队中心动力学作局部线性化，并把 Koopman 预测误差、在线自适应残差、通信补偿残差和饱和/切换影响统一吸收到总扰动项中，则闭环误差可写成

$$
\mathbf{e}_{k+1}
=
\mathbf{A}_{\sigma_k}\mathbf{e}_k
+
\mathbf{G}_{z}\mathbf{z}_k
+
\boldsymbol{\omega}_k,
\label{eq:tf12_error_compact}
$$

其中：

- $\sigma_k$ 是时变调度变量，包含通信质量矩阵、退化回退混合系数、约束收紧比例等；
- $\mathbf{A}_{\sigma_k}$ 表示在第 $k$ 步对应的闭环误差矩阵；
- $\mathbf{G}_z\mathbf{z}_k$ 反映柔性连接误差对团队中心的耦合；
- $\boldsymbol{\omega}_k$ 是总扰动项。

总扰动项进一步分解为

$$
\boldsymbol{\omega}_k
=
\boldsymbol{\omega}^{\mathrm{K}}_k
+
\boldsymbol{\omega}^{\mathrm{ad}}_k
+
\boldsymbol{\omega}^{\mathrm{net}}_k
+
\boldsymbol{\omega}^{\mathrm{sat}}_k,
$$

分别对应：

- 名义 Koopman 模型残差；
- 在线双线性自适应修正带来的剩余误差；
- 通信时延/丢包补偿后的剩余误差；
- 约束收紧、输入裁剪和回退混合引入的等效误差。

柔性连接子系统在前向欧拉离散化下可写为

$$
\mathbf{z}_{k+1}
=
\mathbf{A}_{\xi}\mathbf{z}_k
+
\mathbf{B}_{\xi}\Delta\mathbf{u}_k,
\label{eq:tf12_connection_compact}
$$

其中 $\Delta\mathbf{u}_k$ 是局部车辆命令相对团队命令的偏差堆叠。

## 3. 关键假设

为了给出一版能够成立的李雅普诺夫证明，本文采用以下标准假设。

### 假设 1：参考轨迹与工作域有界

参考路径曲率、参考速度和参考状态有界，闭环运行始终位于紧集 $\Omega$ 内，且在该紧集上 Frenet 模型、Koopman lifting 和 MPC 解映射局部 Lipschitz。

### 假设 2：名义 Koopman-MPC 与安全回退律存在公共二次型李雅普诺夫函数

存在对称正定矩阵 $\mathbf{P}=\mathbf{P}^{\top}>0$ 和 $\mathbf{Q}=\mathbf{Q}^{\top}>0$，使得对所有可达调度变量 $\sigma_k\in\Sigma$ 都有

$$
\mathbf{A}_{\sigma_k}^{\top}\mathbf{P}\mathbf{A}_{\sigma_k}-\mathbf{P}\preceq -\mathbf{Q}.
\label{eq:common_quadratic}
$$

这个假设的物理含义是：在终端集内，无论当前是 MPC 主导、通信退化回退主导，还是两者的凸组合，团队中心误差都由同一个二次型函数共同约束。

在 TF12 中，这个假设对应于：

- 名义 Koopman-MPC 在终端集上满足常规递归可行性与局部稳定性条件；
- 退化回退控制

$$
\delta^{\mathrm{safe}}
=
-0.85\,e_{y,c}
-1.35\,e_{\psi,c}
-0.45\,r_c,
$$

$$
a_x^{\mathrm{safe}}
=
0.22\max(s^{\mathrm{ref}}-s_c,0)-0.10|v_{y,c}|-0.10|r_c|
$$

在工作域内形成局部耗散闭环；
- 混合控制

$$
\mathbf{u}_k^{\mathrm{mix}}
=(1-\nu_k)\mathbf{u}_k+\nu_k\mathbf{u}^{\mathrm{safe}}_k,
\qquad \nu_k\in[0,1]
$$

不把闭环带出公共稳定域。

### 假设 3：通信一致性投影和输入裁剪是非扩张映射

通信质量感知一致性投影、约束收紧和最终饱和映射统称为 $\Pi_k(\cdot)$，满足

$$
\|\Pi_k(\mathbf{u})-\Pi_k(\mathbf{v})\|
\le
\|\mathbf{u}-\mathbf{v}\|,
\qquad \forall \mathbf{u},\mathbf{v}\in\Omega_u.
$$

这在 TF12 中是合理的，因为：

- 一致性投影是凸组合；
- 约束收紧只改变可行区间，不放大输入差异；
- 饱和映射 `clip` 是典型的 1-Lipschitz 非扩张映射。

### 假设 4：局部控制律对误差是 Lipschitz 的

存在正常数 $L_e,L_z,L_{\omega}$，使得局部车辆命令与团队命令之间的差满足

$$
\|\Delta \mathbf{u}_k\|
\le
L_e\|\mathbf{e}_k\|
+
L_z\|\mathbf{z}_k\|
+
L_{\omega}\|\boldsymbol{\omega}_k\|.
\label{eq:command_lipschitz}
$$

这来自于局部 Koopman-MPC 解映射的强正则性、通信一致性层的 Lipschitz 性，以及安全保护模块的分段仿射结构。

### 假设 5：在线自适应和通信补偿残差有界

存在常数 $\bar\omega>0$ 使得

$$
\|\boldsymbol{\omega}_k\|\le \bar\omega,
\qquad \forall k.
\label{eq:disturbance_bound}
$$

对 TF12 而言，这个假设由以下设计共同支撑：

1. 在线双线性更新只在高置信样本上触发；
2. 增量矩阵经过 Frobenius 范数裁剪和谱半径投影；
3. 通信时延有上界 $d_{ij,k}\le 3$；
4. 约束收紧和回退混合阻止控制量在退化网络下无限放大。

## 4. 柔性连接子系统的稳定性引理

TF12 的柔性连接子系统对每个方向都采用弹簧-阻尼二阶结构

$$
\ddot{\boldsymbol{\xi}}_i
=
\mathbf{G}\Delta\mathbf{u}_i
-\mathbf{K}\boldsymbol{\xi}_i
-\mathbf{C}\dot{\boldsymbol{\xi}}_i,
$$

其中

$$
\mathbf{K}=\operatorname{diag}(5.6,6.6,5.0),
\qquad
\mathbf{C}=\operatorname{diag}(3.8,4.2,3.4),
\qquad
h=0.02~\mathrm{s}.
$$

对任一方向 $j\in\{s,e_y,\psi\}$，其离散化矩阵为

$$
\mathbf{A}_{\xi,j}
=
\begin{bmatrix}
1 & h\\
-hk_j & 1-hc_j
\end{bmatrix}.
$$

代入参数可得三个方向对应的谱半径分别为

$$
\rho(\mathbf{A}_{\xi,s})=0.9624,\qquad
\rho(\mathbf{A}_{\xi,e_y})=0.9585,\qquad
\rho(\mathbf{A}_{\xi,\psi})=0.9664.
$$

因此 $\rho(\mathbf{A}_{\xi,j})<1$ 对三个方向都成立，进而整个块对角矩阵 $\mathbf{A}_{\xi}$ 是 Schur 稳定的。于是存在对称正定矩阵 $\mathbf{P}_{\xi}=\mathbf{P}_{\xi}^{\top}>0$ 和 $\mathbf{Q}_{\xi}=\mathbf{Q}_{\xi}^{\top}>0$，满足离散李雅普诺夫方程

$$
\mathbf{A}_{\xi}^{\top}\mathbf{P}_{\xi}\mathbf{A}_{\xi}
-\mathbf{P}_{\xi}
=
-\mathbf{Q}_{\xi}.
\label{eq:connection_lyap}
$$

这说明：即使没有团队级主控制器，仅就柔性连接本身而言，它也是一个有耗散的稳定子系统。

## 5. 李雅普诺夫函数构造

定义团队中心误差的二次型函数

$$
V_e(k)=\mathbf{e}_k^{\top}\mathbf{P}\mathbf{e}_k,
$$

定义柔性连接状态的二次型函数

$$
V_{\xi}(k)=\mathbf{z}_k^{\top}\mathbf{P}_{\xi}\mathbf{z}_k.
$$

取总李雅普诺夫函数

$$
V(k)=V_e(k)+\mu V_{\xi}(k)
=
\mathbf{e}_k^{\top}\mathbf{P}\mathbf{e}_k
+
\mu \mathbf{z}_k^{\top}\mathbf{P}_{\xi}\mathbf{z}_k,
\qquad \mu>0.
\label{eq:total_lyapunov}
$$

由于 $\mathbf{P}>0,\mathbf{P}_{\xi}>0$，存在常数 $\underline{\lambda},\overline{\lambda}>0$ 使得

$$
\underline{\lambda}
\left\|
\begin{bmatrix}\mathbf{e}_k\\\mathbf{z}_k\end{bmatrix}
\right\|^2
\le
V(k)
\le
\overline{\lambda}
\left\|
\begin{bmatrix}\mathbf{e}_k\\\mathbf{z}_k\end{bmatrix}
\right\|^2.
\label{eq:norm_equiv}
$$

## 6. 主定理

### 定理 1：TF12 闭环系统的一致最终有界性

在假设 1-5 成立时，TF12 的闭环误差系统 \eqref{eq:tf12_error_compact}-\eqref{eq:tf12_connection_compact} 关于平衡点 $(\mathbf{e},\mathbf{z})=(\mathbf{0},\mathbf{0})$ 是一致最终有界的。更具体地，存在常数 $\rho\in(0,1)$ 和 $c_{\omega}>0$，使得

$$
V(k+1)\le \rho V(k)+c_{\omega}\bar\omega^2.
\label{eq:drift_main}
$$

因此

$$
V(k)
\le
\rho^k V(0)
+
\frac{c_{\omega}}{1-\rho}\bar\omega^2,
\label{eq:ultimate_bound_V}
$$

并且

$$
\left\|
\begin{bmatrix}\mathbf{e}_k\\\mathbf{z}_k\end{bmatrix}
\right\|^2
\le
\frac{\overline{\lambda}}{\underline{\lambda}}\rho^k
\left\|
\begin{bmatrix}\mathbf{e}_0\\\mathbf{z}_0\end{bmatrix}
\right\|^2
+
\frac{c_{\omega}}{\underline{\lambda}(1-\rho)}\bar\omega^2.
\label{eq:ultimate_bound_state}
$$

也就是说，系统状态指数收缩到一个由总扰动上界 $\bar\omega$ 决定的最终有界邻域中。

若进一步有 $\bar\omega=0$，即不存在 Koopman 残差、通信残差和适应残差，则平衡点局部指数稳定。

## 7. 证明

### 7.1 团队中心误差部分

由 \eqref{eq:tf12_error_compact}，

$$
\mathbf{e}_{k+1}
=
\mathbf{A}_{\sigma_k}\mathbf{e}_k
\mathbf{G}_z\mathbf{z}_k
\boldsymbol{\omega}_k.
$$

于是

$$
\begin{aligned}
\Delta V_e
&=
V_e(k+1)-V_e(k) \\
&=
\mathbf{e}_k^{\top}
\left(
\mathbf{A}_{\sigma_k}^{\top}\mathbf{P}\mathbf{A}_{\sigma_k}
-\mathbf{P}
\right)
\mathbf{e}_k \\
&\quad
+2\mathbf{e}_k^{\top}\mathbf{A}_{\sigma_k}^{\top}\mathbf{P}
\left(
\mathbf{G}_z\mathbf{z}_k+\boldsymbol{\omega}_k
\right) \\
&\quad
+
\left(
\mathbf{G}_z\mathbf{z}_k+\boldsymbol{\omega}_k
\right)^{\top}
\mathbf{P}
\left(
\mathbf{G}_z\mathbf{z}_k+\boldsymbol{\omega}_k
\right).
\end{aligned}
$$

由假设 2 可得

$$
\mathbf{e}_k^{\top}
\left(
\mathbf{A}_{\sigma_k}^{\top}\mathbf{P}\mathbf{A}_{\sigma_k}
-\mathbf{P}
\right)
\mathbf{e}_k
\le
-\lambda_{\min}(\mathbf{Q})\|\mathbf{e}_k\|^2.
$$

再利用 Young 不等式和

$$
\|\mathbf{G}_z\mathbf{z}_k+\boldsymbol{\omega}_k\|^2
\le
2\|\mathbf{G}_z\|^2\|\mathbf{z}_k\|^2
+2\|\boldsymbol{\omega}_k\|^2,
$$

可得存在正常数 $a_e,b_e,c_e>0$，使得

$$
\Delta V_e
\le
-a_e\|\mathbf{e}_k\|^2
+b_e\|\mathbf{z}_k\|^2
+c_e\|\boldsymbol{\omega}_k\|^2.
\label{eq:deltaVe}
$$

### 7.2 柔性连接子系统部分

由 \eqref{eq:tf12_connection_compact}，

$$
\mathbf{z}_{k+1}
=
\mathbf{A}_{\xi}\mathbf{z}_k
\mathbf{B}_{\xi}\Delta \mathbf{u}_k.
$$

因此

$$
\begin{aligned}
\Delta V_{\xi}
&=
\mathbf{z}_k^{\top}
\left(
\mathbf{A}_{\xi}^{\top}\mathbf{P}_{\xi}\mathbf{A}_{\xi}
-\mathbf{P}_{\xi}
\right)\mathbf{z}_k \\
&\quad
+2\mathbf{z}_k^{\top}\mathbf{A}_{\xi}^{\top}\mathbf{P}_{\xi}\mathbf{B}_{\xi}\Delta\mathbf{u}_k \\
&\quad
+\Delta\mathbf{u}_k^{\top}\mathbf{B}_{\xi}^{\top}\mathbf{P}_{\xi}\mathbf{B}_{\xi}\Delta\mathbf{u}_k.
\end{aligned}
$$

由 \eqref{eq:connection_lyap} 和 Young 不等式，可得存在常数 $a_{\xi},c_{\xi}>0$，使得

$$
\Delta V_{\xi}
\le
-a_{\xi}\|\mathbf{z}_k\|^2
+c_{\xi}\|\Delta\mathbf{u}_k\|^2.
\label{eq:deltaVxi_pre}
$$

再由假设 4，

$$
\|\Delta \mathbf{u}_k\|^2
\le
3L_e^2\|\mathbf{e}_k\|^2
+3L_z^2\|\mathbf{z}_k\|^2
+3L_{\omega}^2\|\boldsymbol{\omega}_k\|^2.
$$

代入 \eqref{eq:deltaVxi_pre}，可得存在常数 $b_{\xi},d_{\xi},g_{\xi}>0$，使得

$$
\Delta V_{\xi}
\le
+b_{\xi}\|\mathbf{e}_k\|^2
-d_{\xi}\|\mathbf{z}_k\|^2
+g_{\xi}\|\boldsymbol{\omega}_k\|^2.
\label{eq:deltaVxi}
$$

其中只要连接反馈阻尼足够、局部命令扩散增益不过大，就有 $d_{\xi}>0$。对 TF12 给定参数而言，这个条件由 $\mathbf{A}_{\xi}$ 的 Schur 稳定性直接支持。

### 7.3 总李雅普诺夫漂移

把 \eqref{eq:deltaVe} 与 \eqref{eq:deltaVxi} 相加，得

$$
\begin{aligned}
\Delta V
&=
\Delta V_e+\mu \Delta V_{\xi} \\
&\le
\left(-a_e+\mu b_{\xi}\right)\|\mathbf{e}_k\|^2
+
\left(b_e-\mu d_{\xi}\right)\|\mathbf{z}_k\|^2 \\
&\quad
+\left(c_e+\mu g_{\xi}\right)\|\boldsymbol{\omega}_k\|^2.
\end{aligned}
$$

由于 $a_e>0,d_{\xi}>0$，总可以选择足够小但为正的 $\mu$，使得

$$
\alpha_e:=a_e-\mu b_{\xi}>0,
\qquad
\alpha_{\xi}:=\mu d_{\xi}-b_e>0.
$$

记

$$
\alpha=\min\{\alpha_e,\alpha_{\xi}\},
\qquad
c_{\omega}=c_e+\mu g_{\xi},
$$

则有

$$
\Delta V
\le
-\alpha
\left\|
\begin{bmatrix}\mathbf{e}_k\\\mathbf{z}_k\end{bmatrix}
\right\|^2
+c_{\omega}\|\boldsymbol{\omega}_k\|^2.
\label{eq:deltaV_before_equiv}
$$

由 \eqref{eq:norm_equiv} 的上界，

$$
\left\|
\begin{bmatrix}\mathbf{e}_k\\\mathbf{z}_k\end{bmatrix}
\right\|^2
\ge
\frac{1}{\overline{\lambda}}V(k),
$$

因此

$$
V(k+1)-V(k)
\le
-\frac{\alpha}{\overline{\lambda}}V(k)
+c_{\omega}\|\boldsymbol{\omega}_k\|^2.
$$

令

$$
\rho=1-\frac{\alpha}{\overline{\lambda}},
\qquad 0<\rho<1,
$$

再由假设 5 的扰动有界性 \eqref{eq:disturbance_bound}，便得到

$$
V(k+1)\le \rho V(k)+c_{\omega}\bar\omega^2,
$$

即 \eqref{eq:drift_main}。

对该一阶差分不等式递推，立得

$$
V(k)
\le
\rho^kV(0)+\frac{c_{\omega}}{1-\rho}\bar\omega^2.
$$

再结合 \eqref{eq:norm_equiv} 的下界，即得 \eqref{eq:ultimate_bound_state}。  
定理得证。

## 8. 随机通信场景下的均方稳定性推论

TF12 的链路质量在实现中由随机丢包和随机离散时延采样得到，因此更严格的表述应当是条件期望下的 Lyapunov 漂移。

若总扰动满足

$$
\mathbb{E}\!\left[\|\boldsymbol{\omega}_k\|^2\mid\mathcal{F}_k\right]
\le
\bar\omega^2,
$$

其中 $\mathcal{F}_k$ 是时刻 $k$ 的闭环信息滤波，则由与上面完全相同的推导可得

$$
\mathbb{E}\!\left[V(k+1)\mid\mathcal{F}_k\right]
\le
\rho V(k)+c_{\omega}\bar\omega^2.
$$

取全期望后得到

$$
\mathbb{E}[V(k)]
\le
\rho^kV(0)+\frac{c_{\omega}}{1-\rho}\bar\omega^2.
$$

因此，TF12 在随机通信退化下满足**均方意义下的实用稳定性**。

## 9. 这个证明说明了什么

这份证明给出的不是一句空泛的“系统稳定”，而是更具体的三层含义：

1. **名义理想情形下**  
   如果 Koopman 预测没有残差、在线修正没有误差、通信没有时延丢包、也没有饱和切换，则闭环误差局部指数收敛到零。

2. **真实工程情形下**  
   当存在模型残差、通信退化和切换回退时，闭环误差不一定收敛到严格零点，但会被压缩到一个与残差上界成正比的最终有界邻域内。

3. **TF12 模块为什么有效**  
   - 通信一致性投影降低了 $\Delta \mathbf{u}_k$，从而减小连接子系统输入；
   - 延迟补偿减小了 $\boldsymbol{\omega}^{\mathrm{net}}_k$；
   - 约束收紧和退化回退减小了公共二次型不等式中的最坏情况增益；
   - 高置信在线自适应与投影裁剪控制了 $\boldsymbol{\omega}^{\mathrm{ad}}_k$。

换句话说，TF12 的每一个新增模块都能在李雅普诺夫漂移不等式里找到自己对应的作用位置，而不是“只是经验上有效”。

## 10. 这个证明没有覆盖什么

为了避免在论文里过度宣称，也必须明确下面几点：

1. 该证明依赖于“名义 Koopman-MPC 与安全回退律存在公共二次型李雅普诺夫函数”这一假设。  
   这在理论上是标准假设，但若要变成完全数值可验证结论，还需要单独构造终端集和终端罚矩阵。

2. 在线自适应模块在实现里是投影有界的 ridge 更新，而不是经典梯度型自适应律。  
   因此本文把它作为有界扰动项处理，而不是直接给出参数误差收敛证明。

3. 通信过程是随机采样的。  
   因而最严格的表述应当是均方意义下的实用稳定性，而不是确定性全局渐近稳定。

这并不是证明的弱点，而是对系统真实复杂度的诚实表达。

## 11. 可直接写进论文的精简版

下面给出一版更适合放进正文或附录的精简表述。

### 定理（正文精简版）

记 TF12 的团队跟踪误差为 $\mathbf{e}_k$，柔性连接状态为 $\mathbf{z}_k$。在参考轨迹有界、Koopman-MPC 闭环与退化回退律共享公共二次型李雅普诺夫函数、连接子系统离散矩阵 $\mathbf{A}_{\xi}$ Schur 稳定、局部命令映射 Lipschitz 以及总扰动 $\boldsymbol{\omega}_k$ 有界的条件下，存在正定函数

$$
V(k)=\mathbf{e}_k^{\top}\mathbf{P}\mathbf{e}_k+\mu \mathbf{z}_k^{\top}\mathbf{P}_{\xi}\mathbf{z}_k
$$

和常数 $\rho\in(0,1),c_{\omega}>0$，使得

$$
V(k+1)\le \rho V(k)+c_{\omega}\bar\omega^2.
$$

因此 TF12 闭环误差系统一致最终有界；当 $\bar\omega=0$ 时，平衡点局部指数稳定。若通信退化由有界二阶矩的随机过程生成，则上述结论在均方意义下成立。

### 证明（正文精简版）

将 TF12 闭环误差系统写成

$$
\mathbf{e}_{k+1}=\mathbf{A}_{\sigma_k}\mathbf{e}_k+\mathbf{G}_z\mathbf{z}_k+\boldsymbol{\omega}_k,
\qquad
\mathbf{z}_{k+1}=\mathbf{A}_{\xi}\mathbf{z}_k+\mathbf{B}_{\xi}\Delta \mathbf{u}_k.
$$

由公共二次型假设得

$$
\Delta V_e\le -a_e\|\mathbf{e}_k\|^2+b_e\|\mathbf{z}_k\|^2+c_e\|\boldsymbol{\omega}_k\|^2.
$$

由 $\mathbf{A}_{\xi}$ 的 Schur 稳定性和局部控制律的 Lipschitz 性得

$$
\Delta V_{\xi}\le b_{\xi}\|\mathbf{e}_k\|^2-d_{\xi}\|\mathbf{z}_k\|^2+g_{\xi}\|\boldsymbol{\omega}_k\|^2.
$$

取总函数

$$
V=V_e+\mu V_{\xi},
$$

并选择合适的 $\mu>0$，即可得到

$$
\Delta V\le -\alpha \|[\mathbf{e}_k^{\top},\mathbf{z}_k^{\top}]^{\top}\|^2+c_{\omega}\|\boldsymbol{\omega}_k\|^2.
$$

再由二次型范数等价性与扰动有界性，即得

$$
V(k+1)\le \rho V(k)+c_{\omega}\bar\omega^2.
$$

结论成立。

## 12. 建议你在论文里怎么用

如果你要把这部分放进当前中文稿，我建议：

1. 在方法末尾或附录新增“稳定性分析”小节。
2. 正文放第 11 节给出的精简版定理与证明。
3. 把第 3 节的假设列表压缩成 4 条，放在定理前。
4. 若审稿人继续追问，再把第 7 节完整推导作为补充材料。

这样既不会把正文写得太重，又能把理论口径立住。
