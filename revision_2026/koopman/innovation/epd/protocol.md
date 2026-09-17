# EPD-Koopman实验执行书

> 状态：新协议，尚未修改5080代码、尚未训练、尚未读取EFD-R1.3锁定development。  
> 目标工程：D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main  
> 新代码目录：revision_2026/koopman/innovation/epd/  
> 新结果目录：revision_2026/koopman/innovation_epd_results/  
> 历史冻结依据：D:\PDxc\Review\koopman_freeze.md  
> 本地工作记录：D:\PDxc\Review\epd_log.md  

## 1. 路线决定

本协议采用 EPD-Koopman（Equivariant Physics-Decoded Koopman，等变物理解码Koopman）路线：

1. 冻结当前最强的 fixed-lift linear Koopman 核心，不继续调 full bilinear、structured bilinear、IRSP、P1—P4 physical lift或多专家门控；
2. Koopman算子继续接收当前完整46维测量状态作为初始状态，但后续只信任其30维车辆—货物核心状态输出；
3. 四个连接点的相对位移和相对速度由30维核心状态、锚点几何和已知参数精确重构；
4. 四点货物侧连接力由与plant一致的自由间隙轴向弹簧—阻尼本构解码；
5. 若纯物理解码仍有系统误差，只学习“物理解码残差”，不再从头学习绝对连接几何；
6. 残差模型采用共享多时域head、硬镜像等变投影、交叉拟合收缩、有界输出和域外回退，目标是消除EFD-R1.3中两个bootstrap的灾难性退化；
7. 离线预测通过前不进入通信干扰、DoS、闭环MPC或控制优势实验。

### 1.1 当前已知事实

- EFD-R1.3已冻结为负结果，U8—U10未执行；
- 当前最强核心为 V-FL92-U8，validation family-macro J=0.1019893581；
- full/structured bilinear相对V-FL92-U8分别恶化约59.5%和46.0%；
- IRSP只通过采样控制集谱半径审计，连续域三角上界1.3261大于0.998；
- R1.3 G2在代表种子上改善连接速度、力和受拉内力代理，但几何仅改善13.81%，五个bootstrap只有三个为正；
- G2与M在旧实现中没有完整拆开，不能把旧G2/M写成论文正贡献。

### 1.2 本协议不允许偷换的前提

1. “Koopman只预测30维”是输出使用策略，不代表冻结的V-FL92-U8初始lift只读取30维。实际合同是：

   \[
   z_0=\psi(x_0),\qquad x_0\in\mathbb R^{46},
   \]

   其中46维包含30维核心状态、8维连接位移和8维连接速度。EPD只使用后续解码出的前30维核心预测。

2. 当前连接力是二维平面货物体坐标系中的纵向、横向分量 \(F_x,F_y\)，不是三维模型中的“水平力、竖直力”。support\_fz只是准静态辅助量，不是第三个连接器力分量。

3. 当前力真值来自同一仿真plant，车辆侧力在数据中由货物侧力取负生成；因此作用—反作用只能声明为模型结构恒等式，不能称为两侧独立测量验证。

4. 当前模型没有材料损伤、连接点强度和疲劳演化，不能根据 \(Q_{\rm front-rear}\) 或 \(Q_{\rm left-right}\) 判断真实货物撕裂。

5. 现有阻尼项只在连接器活动时启用：

   \[
   c[v_n]_+\mathbf 1_{\ell>\ell_0}.
   \]

   当 \(\ell\) 刚越过自由间隙且 \(v_n>0\) 时，力可能发生跳变。因此不得宣称本构在活动切换边界全局连续或全局Lipschitz。

## 2. 研究目标与文章主线

### 2.1 主问题

在已知未来20步四车控制输入的条件下，能否在不改变当前最强Koopman核心预测的前提下，通过精确连接几何、plant一致本构和硬等变有界残差，提高：

- 10—20步连接位移预测；
- 10—20步连接相对速度预测；
- 四点 \(F_x,F_y\) 预测；
- 前后、左右受拉内力代理预测；
- 力方向、活动状态和方向反转预测；
- 未见镜像、全局旋转和参数边界上的泛化；
- 跨family、跨fold和一次性盲confirm的稳定性。

### 2.2 预期文章逻辑

文章中的Koopman部分必须按以下证据顺序写：

1. 公平比较表明，复杂bilinear结构在当前场景中没有胜过fixed-lift linear；
2. 误差分解表明，核心状态预测与连接几何/本构输出不应由同一个固定输出通道承担；
3. 提出EPD：稳定Koopman核心＋精确几何解码＋活动本构＋硬等变有界残差；
4. 用K0—K4逐项消融证明每个组件何时生效；
5. 用有限时域误差分解和活动状态误判项给出可核查理论边界；
6. 用family级统计、锁定development和一次性confirm证明收益可复现；
7. EPD离线证据成立后，再另立任务书验证通信保护和闭环控制。

### 2.3 本轮明确不回答

- 连续输入域IRSP收缩证书；
- 完整闭环ISS/UUB；
- delay compensation和DoS保护；
- 高速10—15 m/s闭环可用性；
- 真实材料撕裂、疲劳和断裂；
- HIL或实车测量。

这些项目不得通过EPD离线预测结果间接宣称已经解决。

## 3. 状态、坐标和参数合同

### 3.1 核心状态

第 \(i\) 辆车，\(i\in\{\mathrm{FL,FR,RL,RR}\}\)，采用

\[
x_i=
\begin{bmatrix}
p_{i,x}^{w}&p_{i,y}^{w}&\psi_i&
v_{i,x}^{b}&v_{i,y}^{b}&r_i
\end{bmatrix}^{\!\top}.
\]

货物状态采用

\[
x_L=
\begin{bmatrix}
p_{L,x}^{w}&p_{L,y}^{w}&\psi_L&
v_{L,x}^{b}&v_{L,y}^{b}&r_L
\end{bmatrix}^{\!\top}.
\]

核心状态为

\[
x^c=\operatorname{col}(x_{\rm FL},x_{\rm FR},x_{\rm RL},x_{\rm RR},x_L)
\in\mathbb R^{30}.
\]

完整测量状态为

\[
x=\operatorname{col}(x^c,d_1^L,\ldots,d_4^L,
v_{1,\mathrm{rel}}^L,\ldots,v_{4,\mathrm{rel}}^L)
\in\mathbb R^{46}.
\]

控制输入顺序固定为

\[
u=\operatorname{col}(a_{\rm FL},\delta_{\rm FL},
a_{\rm FR},\delta_{\rm FR},
a_{\rm RL},\delta_{\rm RL},
a_{\rm RR},\delta_{\rm RR})\in\mathbb R^8.
\]

### 3.2 旋转矩阵

全文数学公式采用列向量。定义从车体坐标系到世界坐标系的旋转：

\[
R(\psi)=
\begin{bmatrix}
\cos\psi&-\sin\psi\\
\sin\psi&\cos\psi
\end{bmatrix},
\qquad
J=
\begin{bmatrix}
0&-1\\
1&0
\end{bmatrix}.
\]

代码使用行向量存储时，列向量公式 \(R^\top q^w\) 对应代码中的 \(q^w@R\)。任务书、论文与代码注释必须明确这一差别。

### 3.3 锚点参数

- \(\rho_i^v\)：第 \(i\) 辆车质心到车辆连接锚点的车体系向量；
- \(\rho_i^L\)：货物质心到第 \(i\) 个货物锚点的货物体系向量；
- \(k\)：连接刚度；
- \(c\)：连接阻尼；
- \(\ell_0\)：自由间隙；
- \(m_L,\mu\)：货物质量和轮胎附着参数。

静态参数输入：

\[
p=\operatorname{col}(m_L,\mu,k,c,\ell_0).
\]

## 4. EPD方法

### 4.1 冻结Koopman核心

主核心沿用冻结的V-FL92-U8：

\[
z_{k+1}=Az_k+Bu_k,\qquad z_0=\psi(x_0),
\]

\[
\hat x_{k+h}^{c}=C_c z_{k+h},\qquad h=1,\ldots,20.
\]

要求：

- A、B、lift、normalizer和checkpoint逐文件hash冻结；
- EPD的 \(\hat x^c\) 必须与V-FL92-U8前30维输出逐元素一致；
- EPD不得借修改核心算子获取收益；
- 已知未来控制使用实际施加的四车8维控制，不使用货物真值或未来状态。

### 4.2 精确连接几何重构

车辆锚点和货物锚点的世界坐标为

\[
a_i^w=p_i^w+R(\psi_i)\rho_i^v,
\]

\[
b_i^w=p_L^w+R(\psi_L)\rho_i^L.
\]

从货物锚点指向车辆锚点的连接位移：

\[
d_i^w=a_i^w-b_i^w,
\qquad
d_i^L=R(\psi_L)^\top d_i^w.
\]

车辆锚点与货物锚点的世界速度：

\[
\dot a_i^w=
R(\psi_i)v_i^b+r_iJ R(\psi_i)\rho_i^v,
\]

\[
\dot b_i^w=
R(\psi_L)v_L^b+r_LJ R(\psi_L)\rho_i^L.
\]

连接相对速度：

\[
v_{i,\mathrm{rel}}^w=\dot a_i^w-\dot b_i^w,
\qquad
v_{i,\mathrm{rel}}^L=R(\psi_L)^\top v_{i,\mathrm{rel}}^w.
\]

记

\[
\tilde g_h=
G_{\rm kin}(\hat x_{k+h}^c,p)
=\operatorname{col}(\tilde d_{1:4,h}^L,\tilde v_{1:4,h}^L)
\in\mathbb R^{16}.
\]

这里的“精确”指公式与plant几何完全一致，不代表使用预测核心状态后没有误差。

### 4.3 plant一致轴向本构

对每个连接点：

\[
\ell_i=\|d_i^L\|_2,\qquad
n_i=\frac{d_i^L}{\max(\ell_i,\varepsilon_d)},
\]

\[
\Delta_i=[\ell_i-\ell_0]_+,\qquad
\bar v_{n,i}=n_i^\top v_{i,\mathrm{rel}}^L,
\]

\[
a_i=\mathbf 1_{\Delta_i>0},
\]

\[
f_i=a_i\left(k\Delta_i+c[\bar v_{n,i}]_+\right),
\]

\[
F_{L,i}^{L}=f_i n_i.
\]

需要区分两个量：

\[
\bar v_{n,i}=n_i^\top v_{i,\mathrm{rel}}^L
\]

是所有状态下都可计算的几何法向相对速度；当前plant的 connector\_diagnostics 在非活动状态保留零值，其日志字段等价于

\[
v_{n,i}^{\rm plant}=a_i\bar v_{n,i}.
\]

本构中的阻尼使用活动状态内的 \([\bar v_{n,i}]_+\)。训练特征使用连续可计算的 \(\bar v_{n,i}\)，与plant日志比对时必须使用 \(v_{n,i}^{\rm plant}\)，禁止把两者混为同一监督量。

车辆侧世界力按结构定义：

\[
F_{v,i}^{w}=-R(\psi_L)F_{L,i}^{L}.
\]

车辆体系力为

\[
F_{v,i}^{b}=R(\psi_i)^\top F_{v,i}^{w}.
\]

必须同时输出：

- \(\Delta_i\)；
- 几何法向速度 \(\bar v_{n,i}\) 和plant日志法向速度 \(v_{n,i}^{\rm plant}\)；
- 活动状态 \(a_i\)；
- 力幅值 \(f_i\)；
- 货物侧 \(F_{L,i}^L\)；
- 车辆侧结构力 \(F_{v,i}^{w},F_{v,i}^{b}\)；
- 方向有效标记 \(\ell_i\ge\varepsilon_d\)。

### 4.4 受拉内力代理

角点顺序固定为FL、FR、RL、RR。定义

\[
Q_{\rm front-rear}
=\frac12\left[
(F_{\rm FL,x}+F_{\rm FR,x})
-(F_{\rm RL,x}+F_{\rm RR,x})
\right],
\]

\[
Q_{\rm left-right}
=\frac12\left[
(F_{\rm FL,y}+F_{\rm RL,y})
-(F_{\rm FR,y}+F_{\rm RR,y})
\right].
\]

二者只能称为前后、左右受拉内力代理，不能称为材料撕裂应力。

### 4.5 物理解码残差

真值连接几何记为 \(g_h^\star\)。学习目标不是 \(g_h^\star\)，而是

\[
r_h^\star=g_h^\star-\tilde g_h.
\]

共享残差模型为

\[
\bar r_h=W\phi_h+b.
\]

所有20个horizon共享同一个W，通过 \(\tau_h=h/20\) 和 \(\tau_h^2\) 表示时域位置，禁止再训练20个彼此独立的高维绝对输出head。

特征固定为

\[
\phi_h=\operatorname{col}
\left(
\xi(x_0^c),\xi(\hat x_{k+h}^c),
\tilde g_h,
s_h(u_{0:h-1}),
p,
\tilde\Delta_h,\tilde{\bar v}_{n,h},
\tau_h,\tau_h^2
\right).
\]

特征中不再放常数列；仿射截距由单独的 \(b\) 表示且不参与ridge惩罚。这样避免“常数特征＋独立截距”造成确定性秩亏，也避免重现R1.3中把输出首维误当输入常数项钳位的错误。

其中 \(\xi(x^c)\) 包含：

- 四车质心相对货物质心的货物体系坐标；
- 四车相对货物航向的 \(\cos(\psi_i-\psi_L)\)、\(\sin(\psi_i-\psi_L)\)；
- 四车车体系 \(v_x,v_y,r\)；
- 货物体系 \(v_{L,x},v_{L,y},r_L\)。

控制前缀摘要为

\[
s_h=
\operatorname{col}
\left(
u_{h-1},
\Delta t\sum_{j=0}^{h-1}u_j,
u_{h-1}-u_0
\right)\in\mathbb R^{24}.
\]

不得重新使用8h维完整控制前缀，以降低随horizon增长的病态性。

### 4.6 加权SVD ridge

每个family权重相同。设family \(f\) 含 \(N_f\) 个window，每个window含20个horizon样本，则单样本权重为

\[
w_{fwh}=\frac{1}{N_{\rm family}N_f\,20}.
\]

加权目标：

\[
\min_W
\sum_{f,w,h}w_{fwh}
\left\|r_{fwh}^\star-W\phi_{fwh}-b\right\|_2^2
+\lambda\|W\|_F^2.
\]

实现必须先按family权重对特征和目标做加权中心化：

\[
\tilde\phi=\phi-\mu_\phi,\qquad
\tilde r=r^\star-\mu_r,
\qquad
b=\mu_r-W\mu_\phi.
\]

令 \(\Omega=\operatorname{diag}(\sqrt{w_n})\)，则实际送入SVD的矩阵为

\[
\Phi_w=\Omega(\Phi-\mathbf1\mu_\phi^\top),
\qquad
R_w=\Omega(R-\mathbf1\mu_r^\top).
\]

实现必须使用SVD，不直接求解未经诊断的正规方程。若加权中心化后的设计矩阵

\[
\Phi_w=U\Sigma V^\top,
\]

则

\[
W^\top=
V\operatorname{diag}
\left(\frac{\sigma_j}{\sigma_j^2+\lambda}\right)
U^\top R_w.
\]

这里权重通过平方根进入最小二乘，不能直接乘 \(w_n\) 后再次平方。截距 \(b\) 不被正则化，输出均值和标准差必须独立处理，不能调用含“首维常数钳位”的输入normalizer。

必须报告每折：

- 最大、最小非零奇异值；
- 数值秩；
- 条件数；
- ridge路径；
- 每个特征组的尺度；
- 是否存在零方差或近零方差列。

ridge候选固定为

\[
\lambda\in\{10^{-8},10^{-6},10^{-4},10^{-2},1,10^2\}.
\]

使用train内部五折和one-standard-error规则选择满足近最优误差的最大 \(\lambda\)，不使用R1.3 validation或锁定development选参数。

### 4.7 硬镜像等变

定义货物左右镜像矩阵

\[
M_y=\operatorname{diag}(1,-1)
\]

和角点置换

\[
\pi=(\mathrm{FL}\ \mathrm{FR})(\mathrm{RL}\ \mathrm{RR}).
\]

镜像后：

\[
d_i^{L\prime}=M_y d_{\pi(i)}^L,\qquad
v_i^{L\prime}=M_y v_{\pi(i)}^L,
\]

\[
F_i^{L\prime}=M_yF_{\pi(i)}^L.
\]

加速度只置换，转角同时置换并变号。\(Q_{\rm front-rear}\) 与 \(Q_{\rm left-right}\) 在当前定义下均为镜像不变量。

令 \(T_\phi,T_r\) 分别为特征和残差的带符号置换矩阵。列向量约定下等变条件为

\[
WT_\phi=T_rW.
\]

仿射截距还必须满足

\[
b=T_rb.
\]

由于镜像变换为对合 \(T^{-1}=T\)，Reynolds投影为

\[
W_{\rm eq}
=\frac12\left(W+T_rWT_\phi\right).
\]

截距投影为

\[
b_{\rm eq}=\frac12(b+T_rb).
\]

必须验证

\[
\|W_{\rm eq}T_\phi-T_rW_{\rm eq}\|_{\max}\le10^{-10}.
\]

并验证

\[
\|b_{\rm eq}-T_rb_{\rm eq}\|_{\max}\le10^{-10}.
\]

代码若使用行回归 \(R=\Phi W_{\rm row}\)，对应投影为

\[
W_{\rm row,eq}
=\frac12
\left(
W_{\rm row}
+T_\phi^\top W_{\rm row}T_r^\top
\right).
\]

不得混用两种矩阵约定。

### 4.8 交叉拟合收缩

对五折out-of-fold残差预测 \(\bar r_h\)，按位移组、速度组和四个horizon带

\[
\mathcal H_1=1\!:\!5,\quad
\mathcal H_2=6\!:\!10,\quad
\mathcal H_3=11\!:\!15,\quad
\mathcal H_4=16\!:\!20
\]

计算

\[
\beta_{q,b}
=\operatorname{clip}_{[0,1]}
\frac{\sum (r^\star)^\top\bar r}
{\sum\|\bar r\|_2^2+\epsilon}.
\]

若某组没有out-of-fold正收益，\(\beta_{q,b}=0\)，自动退化为纯物理解码。不得在validation上回调 \(\beta\)。

对horizon \(h\) 所属的区间 \(b(h)\)，定义

\[
B_h=\operatorname{diag}
\left(
\beta_{d,b(h)}I_8,\,
\beta_{v,b(h)}I_8
\right).
\]

### 4.9 等变有界器和域外回退

对每个镜像轨道共享正界 \(\rho_j\)，由train中 \(|r_j^\star|\) 的99.5%分位数冻结。定义奇函数有界器

\[
\mathcal B_\rho(q)_j=\rho_j\tanh(q_j/\rho_j).
\]

镜像轨道共享 \(\rho_j\) 时，

\[
\mathcal B_\rho(T_rq)=T_r\mathcal B_\rho(q),
\]

因此不破坏等变性。

用对称标准化特征定义域外距离

\[
q(\phi)=\sqrt{\frac1{d_\phi}
\left\|\frac{\phi-\mu_\phi}{\sigma_\phi}\right\|_2^2}.
\]

其中 \(\mu_\phi\) 必须满足 \(T_\phi\mu_\phi=\mu_\phi\)，标准差在同一镜像轨道内共享。由此 \(q\) 在带符号置换下不变。train冻结

\[
q_{\rm in}=Q_{0.99}(q),\qquad
q_{\rm out}=\max\{Q_{0.999}(q),q_{\rm in}+0.5\}.
\]

信任系数：

\[
\alpha(q)=
\begin{cases}
1,&q\le q_{\rm in},\\
\dfrac{q_{\rm out}-q}{q_{\rm out}-q_{\rm in}},
&q_{\rm in}<q<q_{\rm out},\\
0,&q\ge q_{\rm out}.
\end{cases}
\]

最终连接几何：

\[
\hat g_h=
\tilde g_h+
\alpha(\phi_h)
\mathcal B_\rho
\left(
B_h(W_{\rm eq}\phi_h+b_{\rm eq})
\right).
\]

最终力只允许由 \(\hat d_h,\hat v_h\) 通过第4.3节本构解码，不允许再单独训练一个与几何不一致的力head。

## 5. 可证明性质与边界

### 5.1 精确几何恒等式

若输入是真实核心状态且锚点参数一致，则

\[
G_{\rm kin}(x_{k+h}^{c,\star},p)
=g_{k+h}^\star
\]

应在float64下达到数值误差门。该结论只验证公式与plant一致，不是学习性能结果。

### 5.2 平移、全局旋转和镜像性质

由于 \(d_i^L,v_i^L\) 均在货物坐标系表达：

- 所有车辆和货物同时平移时，输出不变；
- 所有世界位置和航向同时旋转时，货物体系输出不变；
- 左右镜像时，输出满足角点置换和横向分量变号；
- 经Reynolds投影、有界器和不变信任系数后，残差路径仍满足镜像等变。

端到端必须分别验证公式层、残差层和本构层，不能只报告W的交换子。

### 5.3 有限时域核心误差分解

本协议不假设A收缩。对已知相同控制输入，有限时域lift误差写为

\[
e_{z,h}
=A^he_{z,0}
+\sum_{j=0}^{h-1}
A^{h-1-j}w_{k+j},
\]

其中 \(w_{k+j}\) 是模型残差。于是

\[
\|e_{z,h}\|_2
\le
\|A^h\|_2\|e_{z,0}\|_2
+\sum_{j=0}^{h-1}
\|A^{h-1-j}\|_2\|w_{k+j}\|_2.
\]

该式是有限20步误差分解，不是渐近稳定性或ISS/UUB证明。

### 5.4 几何误差界

利用

\[
\|R(\psi)-R(\hat\psi)\|_2
\le|\psi-\hat\psi|,
\]

其中航向误差均取 \((-\pi,\pi]\) 上的wrap差，

记核心预测误差为 \(e_{x^c}=\hat x^c-x^{c,\star}\)，并记纯运动学重构所需的真实修正为

\[
r_h^\star=g_h^\star-G_{\rm kin}(\hat x_h^c,p).
\]

单点位移残差目标满足

\[
\|r_{d_i}^\star\|_2
\le
\|e_{p_i}\|_2+\|e_{p_L}\|_2
+\|\rho_i^v\|_2|e_{\psi_i}|
+\|\rho_i^L\|_2|e_{\psi_L}|
\]

在速度和横摆率有界的紧集上，存在可从运行域上界计算的 \(L_{v,i}\)，使

\[
\|r_{v_i}^\star\|_2
\le L_{v,i}\|e_{x^c}\|_2.
\]

对最终EPD输出，若 \(\hat r_h\) 是经过收缩、有界和回退后的残差，则

\[
\hat g_h-g_h^\star=\hat r_h-r_h^\star.
\]

因此最终几何误差取决于残差逼近误差，而不是仅凭运动学公式自动消失。由 \(\|\hat r_h\|\le\|\rho\|\) 还可给出保守界

\[
\|\hat g_h-g_h^\star\|_2
\le \|\rho\|_2+L_G\|e_{x^c,h}\|_2.
\]

论文必须给出锚点长度、速度上界和横摆率上界对应的数值，不得只写“存在常数”；也不得把有界残差误写成“必然改善”。

### 5.5 活动模态内的力误差界

定义活动状态 \(a_i=\mathbf1_{\ell_i>\ell_0}\)。在预测与真值活动状态相同、且活动时

\[
\ell_i,\hat\ell_i\ge \ell_0+\eta,\qquad \eta>0,
\]

法向量满足

\[
\|\hat n_i-n_i\|_2
\le \frac{2}{\ell_0+\eta}\|\hat d_i-d_i\|_2.
\]

若相对速度和力幅值在声明运行域内分别由 \(V_{\max}\)、\(F_{\max}\) 有界，则同一活动模态内存在

\[
\|\hat F_i-F_i\|_2
\le L_{d,i}\|\hat d_i-d_i\|_2
+L_{v,i}^{F}\|\hat v_i-v_i\|_2.
\]

可取保守系数

\[
L_{v,i}^{F}=c,
\]

\[
L_{d,i}
=k+\frac{2cV_{\max}}{\ell_0+\eta}
+\frac{2F_{\max}}{\ell_0+\eta}.
\]

### 5.6 跨活动边界的误判项

由于当前plant的阻尼门在活动边界可能跳变，完整误差必须增加活动状态误判项：

\[
\|\hat F_i-F_i\|_2
\le
L_{d,i}\|e_{d_i}\|_2
+c\|e_{v_i}\|_2
+M_{F,i}\mathbf1_{\hat a_i\ne a_i}.
\]

\(M_{F,i}\) 必须取为声明紧集上的 \(F_{\max,i}+\hat F_{\max,i}\)。额定力或ultimate阈值只有在预测器明确饱和时才能作为该上界；当前解码器没有力饱和，不能直接拿12 kN或15 kN替代数学上界。实验必须报告：

- 活动状态准确率、precision、recall、F1；
- 活动状态误判率；
- 距离切换边界 \(|\ell-\ell_0|\) 的分箱误差；
- 误判样本对总力误差的贡献。

如果活动误判项主导，论文结论应是“切换识别仍是主要瓶颈”，不能用平均RMSE掩盖。

## 6. 方法注册表和消融

| ID | 核心 | 连接几何 | 力 | 等变/约束 | 作用 |
|---|---|---|---|---|---|
| EPD-K0-FL46 | 冻结V-FL92-U8 | FL原16维输出 | FL原解码 | 无新增 | 最强历史基线 |
| EPD-K1-KIN | 与K0逐元素一致 | 精确 \(G_{\rm kin}\) | plant轴向解码 | 无学习残差 | 零训练物理解码 |
| EPD-K2-RES | 同K0 | KIN＋普通共享残差 | 轴向解码 | 无硬投影、无界 | 判断残差本身收益与风险 |
| EPD-K3-EQ | 同K0 | KIN＋硬等变残差 | 轴向解码 | Reynolds投影 | 判断结构等变收益 |
| EPD-K4-EPD | 同K0 | KIN＋等变有界收缩残差 | 轴向解码 | 投影、收缩、有界、域外回退 | 唯一主候选 |

辅助审计，不参与主排序：

| ID | 含义 |
|---|---|
| EPD-O1-KIN | 真值30维核心输入 \(G_{\rm kin}\)，验证几何公式 |
| EPD-O2-AX | 真值d/v输入轴向本构，验证力公式 |
| EPD-B1-ARX | 冻结raw-state ARX强简单基线 |
| EPD-B2-H2 | 含已知p的direct multi-horizon基线 |
| EPD-B3-F5 | direct force可学习性上界 |
| EPD-A1-NOMINAL-P | K4使用标称p而非逐轨迹已知p，审计参数输入收益 |
| EPD-A2-NO-BOUND | K3，等价于去掉有界/回退机制 |
| EPD-A3-NO-EQ | K2，等价于去掉硬等变 |
| EPD-A4-BETA1 | 强制 \(\beta=1\)，审计交叉拟合收缩 |

旧bilinear和IRSP只在历史负结果表引用，不在本协议重新训练。

## 7. 数据与证据隔离

### 7.1 数据角色

| 数据 | 数量 | 本协议角色 | 是否允许选参数 |
|---|---:|---|---|
| R1.3 train | 256 base family | EPD训练＋五折交叉拟合 | 允许，仅限train内部 |
| R1.3 analytic mirror | 256 | 结构增强，不增加独立n | 随源family同折 |
| R1.3 validation | 96 | 已查看历史诊断集 | 不允许形成新主证据 |
| R1.3 development | 64 | 锁定的一次性EPD独立验证 | 冻结模型后只读一次 |
| EPD confirm-ID | 160 | 新seed一次性盲确认 | 禁止 |
| EPD stress-OOD | 80 | 声明域边界和失败模式 | 禁止，不与ID合并 |

R1.3 validation已经参与方法路线形成，任何新模型在该集合上的好结果都只能标记为 post-hoc diagnostic。

### 7.2 新seed块

依次审计候选：

\[
\mathrm{BASE}\in\{261000,271000,281000\}.
\]

首个与历史manifest、文件名、metadata seed均无碰撞的块被选中。建议分配：

| 用途 | seed |
|---|---|
| 五折与模型随机性 | BASE+5001—BASE+5005 |
| 统计 | BASE+5999 |
| confirm-ID | BASE+4001—BASE+4160 |
| stress-OOD | BASE+6001—BASE+6080 |

不得因为结果不好更换BASE。

### 7.3 数据覆盖审计

生成 coverage\_cube.json，至少按以下变量分箱：

- 货物速度：0.7—1.5、1.5—2.5、2.5—3.5、3.5—5.0 m/s；
- 加速度绝对值：0—0.2、0.2—0.7、0.7—1.4 m/s²；
- 曲率绝对值：直线、低曲率、中曲率、回头弯高曲率；
- 转向变化：稳态、进入弯道、反向切换、退出弯道；
- 活动连接点数：0、1—2、3—4；
- 四点力方向、活动反转和 \(Q\) 高载荷；
- 货物质量、刚度、阻尼、间隙、附着系数分位区间。

覆盖门只要求预注册“必需单元”非空，不要求不现实的完整笛卡尔积。必须另外报告空单元，禁止只报告每个变量的边缘最小值和最大值。

### 7.4 stress-OOD分组

每组20个独立base：

1. 4—5 m/s速度边界；
2. 低附着与标称载荷；
3. 重货物与连接参数边界组合；
4. 高曲率进入、反向和退出组合。

若plant出现非有限、连接力超过ultimate或100 m无法完成：

- 保留失败轨迹和触发条件；
- 该stress组判运行域失败；
- 不删除异常样本后重算；
- 不阻断已通过的ID预测主张，但必须收缩文章运行域。

镜像、30°、60°和120°全局旋转用于等变/不变测试，不计为新的独立family。

## 8. 指标

### 8.1 归一化

所有尺度只由R1.3 train冻结。对输出组 \(G\)：

\[
E_{G,f}
=
\sqrt{
\frac{1}{N_fH_Gd_G}
\sum_{w,h,j}
\left(
\frac{\hat y_{fwhj}-y_{fwhj}}
{s_{G,j}}
\right)^2
}.
\]

主口径为family-macro：

\[
E_G^{\rm macro}
=\frac1{N_{\rm family}}\sum_fE_{G,f}.
\]

解析镜像不增加family数量，长轨迹不能因window更多获得更大权重。

### 8.2 主指标

- \(E_{\rm core}\)：30维核心状态NRMSE；
- \(E_d\)：8维连接位移NRMSE；
- \(E_v\)：8维连接速度NRMSE；
- \(E_F\)：8维四点力NRMSE；
- \(E_Q\)：2维受拉内力代理NRMSE；
- 原有统一指标

  \[
  J_{\rm pred}
  =\frac13(E_{\rm core}+E_F+E_Q).
  \]

为了与历史结果可比，不重新给 \(J_{\rm pred}\) 加入d/v权重；d/v通过独立硬门约束。

主时域为10—20步，同时报告1、5、10、15、20步和1—5、6—10、11—15、16—20四个区间。

### 8.3 方向和切换指标

- 四点 \(F_x,F_y\) 分量符号准确率，活动floor为10 N；
- 四点力向量角度MAE和p95；
- \(Q_{\rm front-rear},Q_{\rm left-right}\) 符号准确率，活动floor为500 N；
- 力方向反转事件准确率和检测延迟；
- 活动状态precision、recall、F1和误判率；
- 距自由间隙边界的误差分箱；
- force-rate NRMSE；
- rated/ultimate阈值越界识别。

### 8.4 结构与运行时间

- 核心输出逐元素一致性；
- 几何oracle误差；
- 轴向本构oracle误差；
- 作用—反作用结构残差；
- \(F_i\) 与 \(d_i\) 共线残差及点积非负；
- Q重构残差；
- Reynolds交换子；
- 端到端镜像残差；
- 全局旋转不变残差；
- 非有限率、发散率、fallback率；
- 9个候选window的20步rollout p50/p95/p99/max；
- 参数量、内存和训练时间。

## 9. 统计方法和通过门

### 9.1 统计

- 统计单位：独立base family；
- 五折：按scenario、turn sign和load层化，镜像与源family同折；
- paired family bootstrap：10000次，固定BASE+5999；
- paired permutation：小样本可精确，否则固定10000次；
- 报告均值差、中位数差、95% CI、p值和配对效应量；
- 对K4相对K0、K1和最强合格简单基线的主比较做Holm校正；
- 不以“p大于0.05”证明等效，非劣必须使用预注册界。

### 9.2 O1/O2公式门

必须全部通过：

- 真值核心重构d/v的float64最大绝对误差不超过 \(10^{-9}\)；
- float32回放最大误差不超过 \(10^{-6}\)；
- 真值d/v解码货物侧力最大绝对误差不超过 \(2\times10^{-3}\) N；
- Q重构和作用—反作用结构残差不超过 \(10^{-10}\)；
- 旋转、镜像公式测试满足容差。

任一失败说明公式或接口不一致，立即停止训练。

### 9.3 train五折必要门

K4必须：

1. 五折至少4折的10—20步 \(J_{\rm pred}\) 相对K0为正；
2. 五折至少4折的 \(E_d,E_v,E_F,E_Q\) 不出现超过3%的恶化；
3. fold-macro改善达到：

   \[
   E_d\ge30\%,\quad E_v\ge10\%,\quad
   E_F\ge10\%,\quad E_Q\ge10\%;
   \]

4. \(J_{\rm pred}\) 相对K0改善至少8%；
5. 核心状态逐元素一致；
6. 非有限率为0；
7. K2灾难性fold被K4消除：K4最差fold相对K1恶化不超过3%；
8. K3相对K2在未见镜像/旋转至少一项改善5%，且ID误差非劣不超过1%；
9. K4相对K3的中位误差非劣不超过1%，最差fold改善至少10%或消除超3%退化；
10. 活动误判率不高于K0且不超过2%。

不通过则不得读取锁定development。

### 9.4 一次性development门

模型、normalizer、ridge、\(\beta\)、残差界、域外阈值、指标代码和图表代码全部hash冻结后，才允许一次读取64条development。

K4必须同时满足：

- \(E_d/E_v/E_F/E_Q\) 改善30%/10%/10%/10%；
- \(J_{\rm pred}\) 改善至少8%，paired CI下界大于0；
- 至少两个弯道/切换工况 \(J_{\rm pred}\) 改善至少10%；
- 直线/低激励工况不恶化超过3%；
- 方向、Q方向和反转准确率不低于K0减1个百分点，至少两项显著改善；
- 力角度p95不高于K0且不超过60°；
- 活动误判率不高于K0且不超过2%；
- 端到端镜像/旋转、结构残差和运行时间通过；
- 20步p99不超过2 ms，最大值小于20 ms。

失败则停止，不生成confirm，不根据development回调train。

### 9.5 confirm门

confirm-ID只生成一次并只评估一次。通过门与development相同，并增加：

- Holm校正后主比较CI下界仍大于0；
- 至少4/5训练fold、development和confirm方向一致；
- confirm中没有非有限和新增发散；
- K4相对所有合格简单基线的 \(J_{\rm pred}\) 改善至少8%；
- 文章主表、摘要和贡献只使用confirm-ID，不使用历史validation最好值。

stress-OOD单独报告，不与confirm-ID合并。stress失败时缩小运行域，不得用ID均值覆盖。

## 10. 任务树

EP0 冻结与身份审计  
├─ 核对R1.3 freeze manifest、代码树和结果树hash  
├─ 选择无碰撞BASE  
├─ 冻结EPD协议hash、方法注册表和数据角色  
└─ 失败：停止，不创建模型

EP1 公式和接口oracle  
├─ 真值core→d/v  
├─ 真值d/v→F/Q  
├─ 镜像、旋转、作用—反作用结构测试  
└─ 任一不通过：停止，写solutions.md

EP2 历史只读诊断  
├─ 分析R1.3两个失败bootstrap的奇异值、秩、ridge和尺度  
├─ K0→K1零训练物理解码  
├─ 只允许读取train和已看validation  
└─ 输出diagnostic，不作为论文主证据

EP3 train内部五折  
├─ K0/K1/K2/K3/K4完整消融  
├─ SVD ridge、one-SE、交叉拟合beta  
├─ 条件数、最差fold、活动边界分析  
└─ 不通过：硬停止，development保持未读

EP4 模型冻结  
├─ 冻结K4、normalizer、阈值、指标和图表代码  
├─ 写model_card.json、freeze_manifest.json  
└─ 冻结后任何代码改动必须重新开始EP3

EP5 一次性development  
├─ 只读64条锁定数据  
├─ 执行全门和统计  
└─ 不通过：停止，不生成confirm

EP6 confirm与stress生成  
├─ 160条confirm-ID  
├─ 80条stress-OOD  
├─ 覆盖审计和plant安全门  
└─ 任一生成错误：保留失败，不删样本

EP7 一次性盲confirm  
├─ K0/K1/K2/K3/K4和简单基线  
├─ family paired CI、Holm、方向、运行时间  
├─ stress单独报告  
└─ 不通过：交付负结果，不换seed

EP8 论文产物  
├─ 图、表、CSV、JSON一一对应  
├─ 理论命题和数值常数核对  
├─ 审稿意见逐条映射  
├─ 论文允许/禁止主张清单  
└─ delivery.zip和总hash

EP9 后续网络任务书  
└─ 只有EP7通过后，另立通信干扰、DoS、delay和闭环实验，不在EPD结果中提前执行

## 11. 5080代码修改清单

只能新建 revision_2026/koopman/innovation/epd/，不得修改R1.3冻结目录。

| 文件 | 新增职责 | 关键接口/shape |
|---|---|---|
| config.py | 路径、seed、门、阈值 | EPDConfig |
| registry.py | K0—K4和辅助审计身份 | method_registry.json |
| core_adapter.py | 加载冻结FL并滚动 | x0[N,46],u[N,20,8]→core[N,20,30] |
| kinematic_decoder.py | 第4.2节几何 | core[N,H,30],p→d/v[N,H,4,2] |
| axial_decoder.py | 冻结plant一致本构 | d/v,p→F,a,penetration,vn |
| relative_features.py | 固定维共享特征 | core0/coreh,u,p→phi[N,H,D] |
| symmetry.py | 镜像、旋转、T矩阵、Reynolds | project、commutator |
| residual_model.py | weighted SVD ridge、beta、有界器、回退 | fit/predict/model card |
| data_adapter.py | 读取冻结train/validation/development | family不泄漏 |
| coverage.py | coverage cube与空单元 | coverage_cube.json |
| metrics.py | family/scenario/horizon/方向/活动 | metrics.json |
| statistics.py | bootstrap、置换、Holm、效应量 | statistics.json |
| access_guard.py | train→development→confirm状态机 | 越权退出码2 |
| selftest.py | oracle、shape、矩阵约定、容差 | selftest.json |
| run.py | EP0—EP9幂等任务树 | --stage EPx |
| plots.py | 只读JSON/CSV出图 | PNG/PDF/CSV |
| paper_export.py | 表格、公式常数、审稿映射 | paper/ |
| audit.py | SHA256、环境、命令和留痕 | manifests |

### 11.1 必须新增的单元测试

- test\_kinematic\_decoder\_matches\_plant\_float64
- test\_row\_column\_rotation\_convention
- test\_anchor\_velocity\_includes\_yaw\_cross\_term
- test\_axial\_decoder\_matches\_plant
- test\_inactive\_force\_is\_zero
- test\_inactive\_plant\_normal\_speed\_logging\_convention
- test\_boundary\_damping\_discontinuity\_is\_reported
- test\_q\_definition\_and\_mirror\_invariance
- test\_reynolds\_column\_and\_row\_forms
- test\_affine\_intercept\_mirror\_invariance
- test\_bounded\_map\_preserves\_equivariance
- test\_ood\_trust\_is\_mirror\_invariant
- test\_family\_weights\_sum\_equally
- test\_mirror\_pair\_never\_crosses\_fold
- test\_development\_confirm\_access\_guard
- test\_core\_output\_bitwise\_identity

## 12. 分阶段执行细则

### EP0

产物：

- protocol\_sha256.txt；
- historical\_freeze\_audit.json；
- seed\_audit.json；
- method\_registry.json；
- environment.json；
- code\_map.md。

禁止：

- 修改旧checkpoint；
- 将旧V-M改名为EPD；
- 在seed碰撞后人工选择“结果更好”的候选块。

### EP1

先用手工构造状态验证：

- 零航向；
- 非零货物航向；
- 四车不同航向和横摆率；
- 零位移、自由间隙内、刚过间隙、加载、卸载；
- 左右镜像；
- 全局30°、60°、120°旋转。

再使用真实train轨迹真值core做批量oracle。任一公式门失败时，只修新EPD适配器；不得改plant迁就解码器。

### EP2

只读诊断内容：

- 旧G1/G2每个horizon、每个bootstrap的设计矩阵奇异谱；
- 236003/236004是否存在family重复集中、有效秩下降、尺度失配或ridge路径异常；
- 旧20个独立head与新共享head的参数量和条件数；
- K1相对K0的零训练误差；
- 活动边界样本占比。

EP2可以决定“是否具备继续EP3的必要信号”，但不得用旧validation选择EP3超参数。

继续EP3的必要条件：

- O1/O2通过；
- K1相对K0至少一个d/v/F/Q指标改善10%；
- K1任一关键指标不恶化超过20%；
- 共享特征矩阵经标准化后有效秩满足预注册门。

### EP3

每一折独立：

1. 用四折估计normalizer、残差界、q阈值；
2. 在四折内部选择ridge；
3. 在留出折生成out-of-fold残差；
4. 汇总五折out-of-fold结果计算beta；
5. 用冻结beta重新进行严格cross-fit评估；
6. 输出每折模型、预测、family指标和失败样本；
7. 若K2出现爆炸但K4回退成功，必须同时保留K2负结果。

不得先在全train拟合再对同一train宣称五折稳定。

### EP4

冻结后生成：

- final\_model.npz；
- model\_card.json；
- feature\_schema.json；
- normalizer.json；
- thresholds.json；
- training\_families.csv；
- source\_manifest.csv；
- verify\_freeze.ps1。

model card必须记录：

- 训练数据hash；
- core checkpoint hash；
- 特征维数和顺序；
- ridge、beta、残差界、q阈值；
- 运行域；
- 已知限制；
- 不允许的论文主张。

### EP5

执行前访问守卫确认：

- EP3 passed；
- EP4 freeze hash存在；
- development从未被EPD模型读取；
- 指标和图表代码已冻结。

读取后无论成功或失败，都写 development\_consumed.json。失败时不得删除该标记。

### EP6—EP7

confirm生成前冻结generator hash和参数范围。confirm预测文件应先密封保存，再运行指标，避免看见部分结果后中断或修改模型。

每个family保存：

- 输入与参数；
- K0—K4 20步预测；
- 真值；
- d/v/F/Q；
- 活动状态和方向；
- fallback；
- 每步运行时间；
- 所属覆盖单元。

### EP8

所有图必须由冻结CSV/JSON生成，图中均值、误差条和样本数可以反查。不得手工修改图片数值或选择性删除失败seed。

## 13. 失败和停止处理

| 问题 | 判断 | 允许处理 | 禁止处理 |
|---|---|---|---|
| core hash不一致 | 身份失败 | 修路径后重新EP0 | 使用近似模型 |
| 真值core无法重构d/v | 公式/接口失败 | 修EPD适配器 | 修改plant |
| 轴向oracle不一致 | 本构接口失败 | 核对坐标、参数、门函数 | 放宽到掩盖差异 |
| 共享特征病态 | 数值失败 | SVD、删确定性重复列、按协议重启EP3 | 查看development选特征 |
| K1无信号 | 路线必要条件失败 | 停止并写原因 | 堆神经网络掩盖 |
| K2爆炸、K4稳定 | 有界机制可能有效 | 保留完整消融 | 删除K2负结果 |
| K4五折不足4/5 | 科学门失败 | 停止 | 换seed或只报中位seed |
| development失败 | 独立证据失败 | 停止，不生成confirm | 回调train/validation |
| confirm失败 | 主张失败 | 交付负结果 | 新建confirm替换 |
| stress超ultimate | 运行域失败 | 收缩运行域 | 删除轨迹后报告泛化 |
| 活动误判主导 | 切换瓶颈 | 报告边界误差 | 只报平均RMSE |
| 运行时间超门 | 实时性失败 | 优化实现后另立重复协议 | 用不同硬件混报 |

确定性代码bug的处理：

1. 保存修复前结果为带 pre\_fix 后缀的只读文件；
2. 在work\_log记录触发输入、根因、前后hash；
3. 不改seed、数据、阈值和模型设计；
4. 使用相同输入重跑；
5. 若修复改变科学问题或超参数，必须重启当前证据层。

## 14. 论文产物

### 14.1 方法章节

建议结构：

1. Cooperative vehicle–payload core dynamics；
2. Fixed-lift Koopman core predictor；
3. Payload-frame connector kinematic decoder；
4. Active axial constitutive decoder；
5. Shared equivariant bounded residual；
6. Finite-horizon error decomposition with activity mismatch；
7. Training and inference algorithm。

### 14.2 理论命题

- 命题1：真实核心状态下的连接几何重构恒等式；
- 命题2：EPD对全局SE(2)平移/旋转不变及左右镜像等变；
- 命题3：Reynolds投影、有界器和域外信任系数保持镜像等变；
- 命题4：有限20步核心误差到d/v误差的传播界；
- 命题5：同一活动模态内的力误差界及跨模态活动误判项。

不得把命题4—5写成闭环稳定性定理。

### 14.3 主表

表1：方法身份、输入、lift、参数量和是否使用p。  
表2：K0—K4 confirm-ID主指标和95% CI。  
表3：K0—K4逐场景10—20步误差。  
表4：方向、活动、反转、结构残差和运行时间。  
表5：stress-OOD运行域与失败率。  
表6：审稿意见—新证据—论文位置映射。

### 14.4 主图

1. EPD结构图：Koopman core→KIN→residual→AX；
2. 数据覆盖cube与空单元；
3. h=1—20的d/v/F/Q误差和family CI；
4. 五折、development、confirm稳定性；
5. 转向反转事件的四点Fx/Fy方向、Q和活动状态；
6. 普通残差与有界等变残差的最差fold对比；
7. 镜像/旋转和stress-OOD；
8. 精度—参数量—运行时间Pareto。

### 14.5 审稿意见映射

| 审稿关注 | EPD能回答的证据 | 仍需后续 |
|---|---|---|
| bilinear未胜linear | 冻结负结果＋K0基线 | 删除bilinear主张 |
| Koopman创新不足 | EPD结构、命题和K0—K4消融 | 需confirm通过 |
| IRSP连续域不足 | 明确删除连续证书 | 不在EPD修复 |
| force结果被淡化 | d/v/F/Q、方向、活动边界全报告 | 真实测力/HIL仍缺 |
| 统计不足 | family五折、development、confirm、CI、Holm | 控制模块统计另做 |
| 工作范围有限 | ID＋stress单列并收缩声明域 | 10—15 m/s闭环仍缺 |
| delay/DoS证据不足 | 本轮不混入 | EP9另立网络实验 |
| 稳定性条件循环 | 不把预测误差界称稳定性 | 闭环证明仍需重写 |

### 14.6 允许和禁止的表述

只有EP7通过后允许：

- EPD在声明的低速二维仿真域内提高20步连接几何和力预测；
- 硬等变、有界残差和物理回退提高跨fold稳定性；
- 活动状态误判是力误差界的显式组成；
- 结果得到独立development和一次性confirm支持。

始终禁止：

- EPD证明完整闭环稳定；
- EPD验证真实货物不会撕裂；
- EPD的车辆侧力是独立测量；
- 采样谱半径等于连续域证书；
- stress失败样本被平均结果覆盖；
- 解析镜像增加独立样本量；
- 旧R1.3 validation结果被称为盲证据。

## 15. 运行命令

5080 PowerShell：

    $ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
    $Py = 'E:\anaconda\envs\pytorch_new\python.exe'
    $Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\epd\run.py'

    & $Py $Runner --stage EP0
    & $Py $Runner --stage EP1
    & $Py $Runner --stage EP2
    & $Py $Runner --stage EP3
    & $Py $Runner --stage EP4
    & $Py $Runner --stage EP5
    & $Py $Runner --stage EP6
    & $Py $Runner --stage EP7
    & $Py $Runner --stage EP8

run.py必须幂等。已完成stage若输入hash一致应直接复用；输入hash变化则拒绝覆盖并要求新结果目录。

## 16. 留痕和交付

每次代码、数据、模型或报告变化必须在5080结果目录work\_log.md和本地epd\_log.md追加：

- 时间和记录ID；
- 用户目标；
- 修改前后文件hash；
- 修改文件和函数；
- 执行命令；
- 输入数据、seed和stage；
- 结果和通过门；
- 事实、推测和下一动作；
- 是否读取development/confirm；
- 是否触发停止。

遇到无法跑出的支撑证据，立即停止后续阶段，并在solutions.md写：

1. 已核实事实；
2. 失败是工程错误还是科学门失败；
3. 可能原因，明确标记为假设；
4. 允许修复；
5. 论文影响；
6. 恢复条件和成本。

最终交付至少包括：

- protocol.md及hash；
- 全部源代码和source manifest；
- K0—K4模型及model card；
- train五折、development、confirm和stress原始预测；
- metrics/statistics JSON和CSV；
- 论文图表及生成脚本；
- work\_log.md、solutions.md；
- reviewer\_matrix.md；
- paper\_claims.md；
- delivery.zip和总SHA256。

## 17. 完成定义

只有同时满足以下条件，才能声明“EPD-Koopman取得可用于论文的改进”：

1. EP1公式和物理合同通过；
2. EP3五折通过且至少4/5稳定；
3. EP5一次性development通过；
4. EP7一次性confirm-ID通过；
5. K4相对K0及最强合格简单基线满足预注册误差、CI、方向、活动和运行时间门；
6. stress结果被完整报告并据此限定运行域；
7. 理论只陈述有限时域误差和活动边界，不冒充闭环稳定性；
8. 所有表图能追溯到冻结CSV/JSON；
9. 没有读取锁定数据后回调模型；
10. 网络和控制结论仍等待独立后续协议。

若任一主门失败，本协议的合格产物是可审计的负结果和原因定位，不是把阈值、seed或主张改到“通过”。
