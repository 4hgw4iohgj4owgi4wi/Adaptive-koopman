# English Text Draft with Embedded LaTeX Equations

Source manuscript: `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev6_fig2dataflow_20260528.tex`

This Markdown draft keeps the main text readable while embedding the core equations in LaTeX display form. It is intended for Markdown editors that support MathJax or KaTeX. The emphasis is on explaining the method logic: how modeling, Koopman learning, communication compensation, MPC scheduling, FDI/FTC, certificate checking, and feedback interact in one closed-loop pipeline.

## Title

Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC

## Abstract

Four autonomous vehicles transporting a rigid payload must coordinate centroid tracking, distance regulation, connection safety, payload-force risk, and actuator commands under high path curvature, communication delay/dropout, and actuator degradation. This paper proposes **NR-KDCC**, a network-resilient Koopman delay-compensated consensus control framework. The method combines a stability-projected bilinear Koopman predictor with a link-quality-aware consensus MPC loop. The predictor learns short-horizon vehicle-payload evolution from offline data and is projected through an input-aware spectral audit so that input-dependent lifted dynamics do not amplify prediction errors inside the MPC horizon. The MPC layer then uses link quality, connection geometry, curvature, fault indicators, and certificate margins to schedule consensus weights, constraint tightening, delay compensation, fallback decisions, and payload-protection terms.

The proposed framework is evaluated against task-aligned adaptive Koopman embedding baselines and low-order consistency baselines. In paired tests under mixed fault/noise and high communication noise, NR-KDCC reduces lateral tracking error and connection-constraint utilization relative to AKE-M while maintaining full-path completion. High-curvature hairpin diagnostics further show that lateral-priority control improves tracking but can increase short-window payload-force peaks, whereas the payload-protection branch reduces connection utilization and force level at the cost of longitudinal lag and local lateral-error excursions. The results indicate that Koopman prediction benefits network-degraded cooperative transport only when link quality, connection geometry, and payload-force risk enter the control loop together.

## 1. Introduction

Path tracking is a basic function of autonomous vehicles and mobile robots, but four-vehicle rigid-payload transport is more demanding than ordinary single-vehicle tracking. The team must track the payload-center reference, regulate vehicle-to-payload connection errors, coordinate adjacent vehicles, respect steering and acceleration limits, and avoid excessive payload-force excitation. These objectives become strongly coupled under high curvature, communication delay/dropout, and actuator degradation.

Classical tracking controllers such as pure pursuit, Stanley control, LQR, and preview control are computationally efficient, but they are not designed to handle the simultaneous interaction among payload geometry, multi-vehicle consensus, link quality, force-risk auditing, and degraded execution. MPC and distributed MPC are better suited to constrained control, yet many networked-control formulations either assume reliable communication or treat delay and packet loss as bounded external disturbances. In cooperative payload transport, communication degradation changes neighbor prediction, reference delivery, centroid feedback, command reception, and force distribution. It should therefore be used inside the controller as a scheduling variable, not only as an additive uncertainty.

Koopman learning offers a useful way to build data-driven predictors that remain compatible with MPC. By lifting nonlinear dynamics to a higher-dimensional observable space, Koopman models can provide short-horizon predictions for constrained optimization. However, finite-dimensional Koopman models still contain residual errors, and these errors can be amplified by high curvature, aggressive steering, communication degradation, and replanning. This paper therefore does not use Koopman learning as an isolated prediction module. Instead, it embeds a bilinear Koopman predictor into a network-aware MPC loop and audits the input-dependent lifted dynamics through input-aware robust spectral projection.

The contribution is the integration of learning, communication compensation, safety scheduling, and certificate-driven execution in one coherent transport-control framework. The offline layer learns a bilinear Koopman model from scenarios that include curvature variation, communication degradation, and actuator-efficiency loss. The online layer uses the learned model to compensate delay, predict neighboring states, and evaluate candidate control sequences. The MPC layer schedules weights and constraints according to link quality, connection geometry, curvature, and safety margins. The execution layer then checks actuator faults, projects unsafe commands, activates fallback when needed, and logs a Lyapunov/ISS certificate.

## 2. System Modeling and Problem Definition

### 2.1 Vehicle Dynamics

The system contains four vehicles indexed by \(i\in\{1,\ldots,N\}\), with \(N=4\). The global-frame position and heading of vehicle \(i\) are

$$
p_i=[X_i,Y_i]^\top,\qquad \psi_i .
$$

The body-frame longitudinal velocity, lateral velocity, and yaw rate are \(v_{x,i}\), \(v_{y,i}\), and \(r_i\). The control input is written consistently as

$$
u_{i,k}^{\mathrm{ctrl}}=[a_{x,i,k},\delta_{i,k}]^\top ,
$$

where \(a_{x,i,k}\) is the longitudinal acceleration command and \(\delta_{i,k}\) is the front steering angle.

The global kinematics are

$$
\begin{aligned}
\dot X_i &= v_{x,i}\cos\psi_i-v_{y,i}\sin\psi_i,\\
\dot Y_i &= v_{x,i}\sin\psi_i+v_{y,i}\cos\psi_i,\\
\dot \psi_i &= r_i .
\end{aligned}
$$

With a linear tire model, the lateral and yaw dynamics are

$$
\begin{aligned}
\dot v_{y,i}
&=-\frac{2C_f+2C_r}{m v_{x,i}}v_{y,i}
+\left(-v_{x,i}-\frac{2C_f l_f^{\mathrm{veh}}-2C_r l_r^{\mathrm{veh}}}{m v_{x,i}}\right)r_i
+\frac{2C_f}{m}\delta_i+d_{y,i},\\
\dot r_i
&=-\frac{2C_f l_f^{\mathrm{veh}}-2C_r l_r^{\mathrm{veh}}}{I_z v_{x,i}}v_{y,i}
-\frac{2C_f (l_f^{\mathrm{veh}})^2+2C_r (l_r^{\mathrm{veh}})^2}{I_z v_{x,i}}r_i
+\frac{2C_f l_f^{\mathrm{veh}}}{I_z}\delta_i+d_{r,i},\\
\dot v_{x,i}
&=a_{x,i}+r_i v_{y,i}+d_{x,i}.
\end{aligned}
$$

Here \(m\), \(I_z\), \(l_f^{\mathrm{veh}}\), \(l_r^{\mathrm{veh}}\), \(C_f\), and \(C_r\) denote vehicle mass, yaw inertia, front and rear axle distances, and front and rear cornering stiffness. The disturbance terms \(d_{x,i}\), \(d_{y,i}\), and \(d_{r,i}\) collect modeling errors, payload-induced coupling, and external disturbances.

The vehicle model gives the local dynamics used by the simulator and the controller. It is not enough by itself, because cooperative payload transport also requires path-coordinate errors, connection geometry, communication degradation, and safety constraints.

### 2.2 Path-Coordinate Errors

Let the reference-path arc length, curvature, and tangent heading be \(s\), \(\kappa_r(s)\), and \(\psi_r(s)\). After projection of vehicle \(i\) onto the path coordinate, the lateral error is \(e_{y,i}\), and the heading error is

$$
e_{\psi,i}=\psi_i-\psi_r(s_i).
$$

Within the operating region \(|\kappa_r(s_i)e_{y,i}|<1\), the Frenet error dynamics are

$$
\dot s_i=
\frac{v_{x,i}\cos e_{\psi,i}-v_{y,i}\sin e_{\psi,i}}
{1-\kappa_r(s_i)e_{y,i}},
$$

and

$$
\dot e_{y,i}=v_{x,i}\sin e_{\psi,i}+v_{y,i}\cos e_{\psi,i},\qquad
\dot e_{\psi,i}=r_i-\kappa_r(s_i)\dot s_i .
$$

The global-frame model is used for payload geometry and simulation, while the Frenet errors are used in the MPC cost and tracking evaluation.

### 2.3 Rigid Payload and Connection Errors

The payload-center pose is

$$
\xi_L=[X_L,Y_L,\psi_L]^\top,\qquad p_L=[X_L,Y_L]^\top .
$$

The payload center is used as the representative team center. Let \(b_i\) be the fixed vector from the payload center to the \(i\)-th connection point in the payload frame. The global connection-point position is

$$
p_{L,i}=p_L+R(\psi_L)b_i,
\qquad
R(\psi)=
\begin{bmatrix}
\cos\psi&-\sin\psi\\
\sin\psi&\cos\psi
\end{bmatrix}.
$$

The vehicle-payload connection error is

$$
e_{c,i}=p_i-p_{L,i},
\qquad
e_c=\mathrm{col}(e_{c,1},\ldots,e_{c,N})\in\mathbb R^{2N}.
$$

If an equivalent spring-damper connection is used, the connection-force proxy is

$$
F_{c,i}=K_c e_{c,i}+D_c\dot e_{c,i},
$$

where \(K_c,D_c\succeq0\). This proxy is used for cost shaping and safety auditing. It is not claimed to be an exact force-sensor measurement. In the experiments, force-related quantities are therefore interpreted as risk and trade-off metrics rather than as direct physical-force guarantees.

### 2.4 Communication Graph and Degraded Measurements

Communication is represented by a five-node graph

$$
\mathcal G_k=(\mathcal V\cup\{0\},\mathcal E_k),
$$

where node \(0\) is the upper reference planner and \(\mathcal V=\{1,2,3,4\}\) is the set of executing vehicles. Vehicle-layer communication uses ring neighbors,

$$
\mathcal N_i=\{i-1,i+1\},
$$

with indices wrapped modulo \(N\).

Communication degradation affects three classes of variables: adjacent distance, payload-center lateral error, and upper-layer temporary path packet:

$$
\begin{aligned}
\hat d_{ij,k}&=d_{ij,k-\tau^d_{ij,k}}+\beta^d_{ij,k}+\epsilon^d_{ij,k},\\
\hat e_{y,L,k}&=e_{y,L,k-\tau^y_k}+\beta^y_k+\epsilon^y_k,\\
\hat{\mathcal P}_{i,k}^{\mathrm{tmp}}
&=\mathcal P_{i,k-\tau^p_{i,k}}^{\mathrm{tmp}}+\beta^p_{i,k}+\epsilon^p_{i,k}.
\end{aligned}
$$

Here \(\tau\), \(\beta\), and \(\epsilon\) denote delay, bias, and noise. The link quality of edge \((j,i)\) is \(q_{ij,k}\in[0,1]\), and the aggregate network quality is \(q_k^{\mathrm{net}}\). Packet loss is represented by \(\ell_{ij,k}\in\{0,1\}\), where \(\ell_{ij,k}=1\) denotes loss.

When the neighbor state is available, the delayed state is extrapolated through the lifted predictor; when packet loss occurs, a held or fallback estimate is used:

$$
\hat x_{j,k}^{\mathrm{net}}=
\begin{cases}
\Pi_x \hat z_{j,k|k-\tau^x_{ij,k}}, & \ell_{ij,k}=0,\\
\hat x_{j,k-1}^{\mathrm{net}}, & \ell_{ij,k}=1 .
\end{cases}
$$

The adjacent-distance regulation error is

$$
e^{d}_{ij,k}=\hat d_{ij,k}-d^{\mathrm{ref}}_{ij}(s_k),\qquad (j,i)\in\mathcal E_k .
$$

The communication model is central to NR-KDCC because link quality is later used to schedule consensus weights, constraint tightening, neighbor prediction, and fallback.

## 3. Proposed NR-KDCC Method

### 3.1 Overall Logic

NR-KDCC is a closed-loop pipeline with five layers.

The **offline learning layer** generates vehicle-payload-communication data under nominal, noisy, faulty, and mixed degraded scenarios. These data are used to fit a bilinear Koopman predictor and to determine the input envelope used by the stability projection.

The **upper reference and communication layer** generates payload-center references and vehicle-specific local path packets. It also records the quality of the upper-to-lower path-delivery channel.

The **online prediction and consensus-MPC layer** fuses local observations, delayed neighbor information, upper-layer path packets, and Koopman predictions. It solves one MPC problem whose weights and constraints are scheduled by communication quality, curvature, connection risk, and protection mode.

The **safety, FDI/FTC, and certificate layer** receives candidate MPC commands, diagnoses actuator degradation, projects unsafe commands, checks certificate margins, and activates fallback if needed.

The **vehicle-payload environment and feedback layer** executes the published command and returns measured states, errors, force proxies, constraint logs, communication logs, and certificate quantities for the next sampling period.

The logic is sequential: Koopman learning supplies prediction, communication quality supplies trust and margins, MPC supplies constrained optimization, FDI/FTC supplies degraded execution protection, the certificate supplies boundedness auditing, and feedback closes the loop.

### 3.2 Upper-Layer Equivalent 4WS Local Path Publication

The upper layer uses an equivalent four-wheel-steering representation of the payload-centered team. This is only a geometric reference-publication device. It does not replace the lower single-vehicle dynamics.

Let \(l_f^{\mathrm{4ws}}\) and \(l_r^{\mathrm{4ws}}\) be the equivalent front and rear axle distances, and

$$
L^{\mathrm{4ws}}=l_f^{\mathrm{4ws}}+l_r^{\mathrm{4ws}}.
$$

The equivalent sideslip angle and curvature are

$$
\begin{aligned}
\beta^{\mathrm{4ws}} &=
\arctan
\frac{
l_r^{\mathrm{4ws}}\tan\delta_f^{\mathrm{up}}
+l_f^{\mathrm{4ws}}\tan\delta_r^{\mathrm{up}}
}{L^{\mathrm{4ws}}},\\
\kappa^{\mathrm{4ws}} &=
\frac{\cos\beta^{\mathrm{4ws}}}{L^{\mathrm{4ws}}}
\left(\tan\delta_f^{\mathrm{up}}-\tan\delta_r^{\mathrm{up}}\right).
\end{aligned}
$$

The upper solver tracks the reference curvature and penalizes sideslip, front/rear steering relation, and steering magnitude:

$$
\begin{aligned}
\min_{\delta_f^{\mathrm{up}},\delta_r^{\mathrm{up}}}\quad
&w_\kappa\left(\kappa^{\mathrm{4ws}}-\kappa_r(s)\right)^2
+w_\beta\left(\beta^{\mathrm{4ws}}\right)^2\\
&+w_\rho\left(\tan\delta_r^{\mathrm{up}}+\rho_r\tan\delta_f^{\mathrm{up}}\right)^2
+w_\delta\left[\left(\delta_f^{\mathrm{up}}\right)^2+\left(\delta_r^{\mathrm{up}}\right)^2\right]\\
\mathrm{s.t.}\quad
&|\delta_f^{\mathrm{up}}|\le \bar\delta_f,\qquad
|\delta_r^{\mathrm{up}}|\le \bar\delta_r .
\end{aligned}
$$

For vehicle \(i\), the equivalent rigid-body velocity direction is

$$
\psi_{i,k}^{\mathrm{up}}=
\psi_{L,k}^{\mathrm{ref}}+
\operatorname{atan2}\!\left(
\sin\beta^{\mathrm{4ws}}+\kappa^{\mathrm{4ws}} b_{x,i},
\cos\beta^{\mathrm{4ws}}-\kappa^{\mathrm{4ws}} b_{y,i}
\right).
$$

The temporary local path packet is then

$$
\mathcal P_{i,k}^{\mathrm{tmp}}(\varsigma)=
p_{L}^{\mathrm{ref}}(s_k+\varsigma)+
R\!\left(\psi_L^{\mathrm{ref}}(s_k+\varsigma)\right)b_i+
\alpha_p \varsigma
\begin{bmatrix}
\cos \psi_{i,k}^{\mathrm{up}}\\
\sin \psi_{i,k}^{\mathrm{up}}
\end{bmatrix},
\quad 0\le\varsigma\le\ell_p .
$$

The data flow is direct: reference curvature and payload-center progress generate equivalent 4WS geometry; the geometry generates vehicle-specific local path packets; the path packets enter the communication graph; the lower MPC receives delayed or degraded packets and handles them as part of the networked control problem.

### 3.3 Offline Data Generation

Offline data are generated from the vehicle-payload-communication simulator. The scenarios include nominal operation, high communication noise, single actuator fault, and mixed fault/noise. The raw vehicle state dimension is \(6\), and the control input dimension is \(n_u=2\). Each trajectory records states, payload-center quantities, connection errors, control inputs, link quality, delay/loss variables, actuator-efficiency estimates, and certificate-related quantities.

This stage is needed for two reasons. First, the Koopman predictor must see the same types of coupling that appear online: curvature, communication degradation, connection error, and actuator-efficiency loss. Second, the stability projection needs a realistic input envelope and representative input samples.

### 3.4 Bilinear Koopman Lifting

Let \(x_{i,k}\in\mathbb R^6\) be the raw physical state of vehicle \(i\). NR-KDCC uses an enhanced observation vector

$$
\chi_k\in\mathbb R^{n_\chi},
$$

which contains vehicle states, payload-center errors, connection geometry, aggregate network quality \(q_k^{\mathrm{net}}\), actuator-efficiency estimates, and path-context variables. The reported implementation uses \(n_\chi=24\) and lifted dimension \(n_z=31\).

The Koopman lifting is

$$
z_k=\Phi_\theta(\chi_k)=
\begin{bmatrix}
\chi_k\\
\phi_\theta(\chi_k)
\end{bmatrix}
\in\mathbb R^{n_z},
$$

where \(\phi_\theta\) is a learned nonlinear feature map.

The lifted dynamics are bilinear in the control input:

$$
z_{k+1}
=A z_k+B u_k^{\mathrm{ctrl}}
+\sum_{\ell=1}^{n_u}u_{k,\ell}^{\mathrm{ctrl}}N_\ell z_k+w_k .
$$

Here \(A,N_\ell\in\mathbb R^{n_z\times n_z}\), \(B\in\mathbb R^{n_z\times n_u}\), and \(w_k\) is the residual. The bilinear term is important because steering and acceleration interact with lateral motion, yaw motion, connection geometry, and payload-center progress. A purely linear lifted predictor cannot represent these input-state couplings as directly.

For a dataset

$$
\mathcal D=\{z_k,u_k^{\mathrm{ctrl}},z_{k+1}\}_{k=1}^{M-1},
$$

define the regressor

$$
\Xi_k=
\begin{bmatrix}
z_k^\top&
(u_k^{\mathrm{ctrl}})^\top&
(u_{k,1}^{\mathrm{ctrl}}z_k)^\top&
\cdots&
(u_{k,n_u}^{\mathrm{ctrl}}z_k)^\top
\end{bmatrix}^\top .
$$

Let

$$
Z_+=[z_2,\ldots,z_M],
\qquad
\Xi=[\Xi_1,\ldots,\Xi_{M-1}].
$$

The parameter matrix

$$
\Theta=[A\;B\;N_1\;\cdots\;N_{n_u}]
$$

is fitted by ridge regression:

$$
\Theta^\star=Z_+\Xi^\top(\Xi\Xi^\top+\lambda I)^{-1}.
$$

Ridge regularization suppresses parameter amplification caused by limited samples, correlated regressors, and noise. Online residual updates are allowed only within the projection and constraint boundaries, so adaptation cannot freely push the predictor outside the audited operating region.

### 3.5 Input-Aware Robust Spectral Projection

The effective lifted matrix depends on the control input:

$$
A_{\mathrm{eff}}(u_k^{\mathrm{ctrl}})
=A+\sum_{\ell=1}^{n_u}u_{k,\ell}^{\mathrm{ctrl}}N_\ell .
$$

Therefore, projecting only \(A\) is not enough. NR-KDCC applies input-aware robust spectral projection. First, the main matrix is projected:

$$
A^+=\Pi_{r_A}(A),
$$

and the bilinear matrices are scaled:

$$
N_\ell^+=\gamma N_\ell,\qquad 0\le\gamma\le1 .
$$

The sampled robust bound chooses the largest \(\gamma\) satisfying

$$
\gamma_s=\max_{\gamma\in[0,1]}\gamma
\quad\mathrm{s.t.}\quad
\max_{u\in\mathcal U_s}
\rho\!\left(A^++\gamma\sum_{\ell=1}^{n_u}u_\ell N_\ell\right)
\le r_u .
$$

Here \(\mathcal U_s\) contains training-input quantiles, boundary points, and corner points. A conservative norm certificate can also be computed:

$$
\begin{aligned}
\gamma_c
&=\max\left\{0,\min\left(1,\,
\frac{r_u-\|A^+\|_2}
{\sum_{\ell=1}^{n_u}u_{\ell,\max}^{\mathrm{abs}}\|N_\ell\|_2+\varepsilon}
\right)\right\},\\
u_{\ell,\max}^{\mathrm{abs}}
&=\max(|u_\ell^{\min}|,|u_\ell^{\max}|).
\end{aligned}
$$

The default experiments use the sampled bound to avoid overly weakening the bilinear terms and record the norm certificate as an audit metric.

The one-step residual is bounded as

$$
\|w_k\|
\le
\bar w_0+\bar w_\chi\|\chi_k-\chi_k^{\mathrm{ref}}\|
+\bar w_q(1-q_k^{\mathrm{net}}),
$$

which later enters the stability certificate through the network-quality term.

The projection should be interpreted as a controller-side amplification-risk audit. It does not prove global stability of the true nonlinear system, and it does not guarantee lower open-loop rollout error. Its role is to keep the learned predictor numerically suitable for the MPC operating region.

### 3.6 Communication-Quality-Aware Consensus MPC

At every sampling time, the lower layer solves one MPC problem over horizon \(H\). Define the vehicle tracking error vector

$$
\xi_{v,i,k}=[e_{y,i,k},e_{\psi,i,k}]^\top .
$$

The base MPC cost is

$$
\begin{aligned}
J
&=\sum_{h=0}^{H-1}
\Big[
\|e_{L,k+h}\|_{Q_L}^2
+\sum_i\|\xi_{v,i,k+h}\|_{Q_v}^2\\
&\quad
+\sum_{(j,i)\in\mathcal E_k}
\omega_{ij,k}
\|x_{i,k+h}-\hat x_{j,k+h|k}^{\mathrm{net}}\|_{Q_c}^2\\
&\quad
+\sum_{(j,i)\in\mathcal E_k}
\omega^d_{ij,k}w_d\|e^d_{ij,k+h}\|^2
+\|e_{c,k+h}\|_{Q_e}^2\\
&\quad
+\|u_{k+h}^{\mathrm{ctrl}}\|_{R_u}^2
+\|\Delta u_{k+h}^{\mathrm{ctrl}}\|_{R_\Delta}^2
\Big]
+\|e_{L,k+H}\|_{P_L}^2 .
\end{aligned}
$$

Here

$$
e_L=[X_L-X_L^{\mathrm{ref}},Y_L-Y_L^{\mathrm{ref}},\psi_L-\psi_L^{\mathrm{ref}}]^\top .
$$

The communication weight is

$$
\omega_{ij,k}=\omega_{\min}+(\omega_{\max}-\omega_{\min})\bar q_{ij,k},
$$

where \(\bar q_{ij,k}\) is the smoothed link quality. Reliable links therefore carry stronger consensus weight, while unreliable links are down-weighted.

The constraints include

$$
\begin{gathered}
v_{x,\min}\le v_{x,i,k+h}\le v_{x,\max},\qquad
|\delta_{i,k+h}|\le\delta_{\max},\qquad
|a_{x,i,k+h}|\le a_{\max},\\
\|e_{c,i,k+h}\|\le e_{c,\max}(q_k^{\mathrm{net}}),\qquad
\|F_{c,i,k+h}\|\le F_{c,\max},\\
|\Delta \delta_{i,k+h}|\le \Delta\delta_{\max},\qquad
|\Delta a_{x,i,k+h}|\le \Delta a_{\max}.
\end{gathered}
$$

When \(q_k^{\mathrm{net}}\) decreases, the connection and input constraints are tightened. If degradation is severe, the controller enters conservative fallback. Thus communication quality affects not only prediction but also trust, constraint margins, and execution mode.

### 3.7 C-Mode Scheduling and Protection Branches

The online mode is

$$
\mu_k\in\{\mathrm{C0},\mathrm{C1},\mathrm{C2},\mathrm{C3}\}.
$$

C0 is normal tracking and connection preservation. C1 is high-curvature lateral priority. C2 is payload protection. C3 is conservative degraded fallback. These modes are not separate controllers; they are weight and constraint schedules applied to the same Koopman-MPC optimizer.

In high curvature, lateral and heading error weights are increased while steering penalty is moderately reduced:

$$
\begin{gathered}
D_v=\mathrm{diag}(\sqrt{\eta_y},\sqrt{\eta_\psi}),\qquad
D_\delta=\mathrm{diag}(1,\sqrt{\eta_\delta}),\\
Q_v^{\mathrm{hc}}=D_v Q_v D_v,\qquad
R_u^{\mathrm{hc}}=D_\delta R_u D_\delta .
\end{gathered}
$$

Here \(\eta_y>1\), \(\eta_\psi>1\), and \(0<\eta_\delta<1\). The purpose is to make the optimizer more willing to use steering authority to suppress lateral and heading errors in high-curvature segments while still respecting connection and input constraints.

The payload-protection switch is

$$
\sigma_k=
\operatorname{sat}_{[0,1]}\!\left(
\frac{|\kappa_r(s_k)|-\kappa_{\mathrm{off}}}
{\kappa_{\mathrm{on}}-\kappa_{\mathrm{off}}+\varepsilon}
\right).
$$

When payload protection is active, the cost is augmented by

$$
J_k^{\mathrm{prot}}
=J_k+
\sigma_k\left(
\lambda_c\|e_{c,k}\|^2
+\lambda_u\sum_i\|u_{i,k}^{\mathrm{ctrl}}-\bar u_k^{\mathrm{ctrl}}\|^2
+\lambda_F\|\hat F_{L,k}^{xy}\|^2
\right),
$$

where

$$
\bar u_k^{\mathrm{ctrl}}=\frac{1}{N}\sum_i u_{i,k}^{\mathrm{ctrl}} .
$$

This branch shifts the objective from pure tracking toward a compromise among tracking, connection preservation, input-dispersion reduction, and force-risk mitigation.

### 3.8 FDI/FTC Execution-Layer Protection

The actual actuator input is approximated as

$$
u_{i,k}^{\mathrm{act}}
=\eta_{i,k}\odot u_{i,k}^{\mathrm{cmd}}+\nu_{i,k},
\qquad
\|\nu_{i,k}\|\le \bar\nu_i .
$$

The actuator efficiency \(\eta_{i,k}\) is estimated separately for acceleration and steering channels. The FDI statistic combines exponentially weighted moving average and cumulative sum:

$$
\bar\varepsilon_{i,k}
=(1-\alpha_\varepsilon)\bar\varepsilon_{i,k-1}
+\alpha_\varepsilon\|\varepsilon_{i,k}^{\mathrm{pred}}\|,
$$

$$
c_{i,k}=
\max\{0,c_{i,k-1}+\bar\varepsilon_{i,k}-\varepsilon_0\}.
$$

If degradation is detected, FTC projects the MPC command into a conservative feasible set:

$$
u_k^{\mathrm{safe}}
=
\arg\min_{u\in\mathcal U(\hat\eta_k,q_k^{\mathrm{net}})}
\|u-u_k^{\mathrm{mpc}}\|_{R_s}^2
+\alpha_e\|e_{c,k+1}(u)\|^2 .
$$

The execution layer therefore diagnoses degradation, projects unsafe commands, redistributes authority, and checks certificate margins before publishing commands. Role scheduling only adds a bounded trim and is not allowed to override the main constraint-consistent MPC decision.

### 3.9 Certificate Checking and Practical Boundedness

Define the physical error and combined lifted error as

$$
\begin{aligned}
e_k
&=\mathrm{col}\left(
e_{L,k},e_{c,k},e_{y,1,k},e_{\psi,1,k},\ldots,e_{y,N,k},e_{\psi,N,k}
\right),\\
\xi_k
&=\mathrm{col}(e_k,\tilde z_k),
\qquad
\tilde z_k=z_k-z_k^\star,\\
z_k^\star&=\Phi_\theta(\chi_k^{\mathrm{ref}}).
\end{aligned}
$$

For each mode \(\mu\in\{\mathrm{C0},\mathrm{C1},\mathrm{C2},\mathrm{C3}\}\), define

$$
V_{\mu,k}
=\xi_k^\top P_\mu\xi_k
+\sum_i\|\mathbf 1_2-\hat{\boldsymbol\eta}_{i,k}\|_{B_i}^2
+\gamma_q\sum_{(j,i)\in\mathcal E_k}(1-\bar q_{ij,k})^2 .
$$

The payload-protection certificate is

$$
\bar V_{\mu,k}
=V_{\mu,k}+\mu_F\sigma_k\|\hat F_{L,k}^{xy}\|^2 .
$$

The online certificate margin is

$$
m_k=
(1-\lambda_{\mu_k}\Delta t)\bar V_{\mu_k,k}
+\gamma_d\|d_k\|^2+\gamma_w\|w_k\|^2
-\bar V_{\mu_{k+1},k+1}.
$$

A step passes the certificate if

$$
m_k\ge-\epsilon_m .
$$

On passing steps, the implemented certificate verifies a practical ISS-type inequality:

$$
\bar V_{\mu_{k+1},k+1}-\bar V_{\mu_k,k}
\le
-\alpha_c\|\xi_k\|^2
+c_d\|d_k\|^2
+c_q(1-q_k^{\mathrm{net}})^2
+c_\tau\tau_k^2
+c_F|\Delta\sigma_k|
+c_0 .
$$

The state-dependent residual must satisfy the small-gain condition

$$
\alpha_c=
\alpha_{\mathrm{cert}}-c_w\bar w_\chi^2L_\chi^2>0 .
$$

On certificate-failing steps, bounded growth is required:

$$
\bar V_{\mu_{k+1},k+1}
\le
(1+\rho_f)\bar V_{\mu_k,k}+c_f .
$$

If the failing-step density is sufficiently low and the average contraction condition holds,

$$
(1-\bar\nu)\alpha_V>\bar\nu\rho_f,
\qquad
\alpha_V=\alpha_c/\bar c ,
$$

then the combined error is practically input-to-state stable. If the disturbance inputs are uniformly bounded, there exist \(C>0\), \(\lambda\in(0,1)\), and an ultimate bound \(\Omega\) such that

$$
\|\xi_k\|^2\le C\lambda^k\|\xi_0\|^2+\Omega ,
$$

with

$$
\Omega=
O\!\left(
c_0+\|d\|_\infty^2+\|1-q^{\mathrm{net}}\|_\infty^2
+\|\tau\|_\infty^2+\|\Delta\sigma\|_\infty+c_f
\right).
$$

This statement matches the implemented controller. It is a practical ISS/UUB claim under compact operating conditions, bounded residuals, finite-density certificate failures, and feasible fallback. It is not a global asymptotic stability claim.

### 3.10 Full Sampling-Period Logic

One sampling period proceeds as follows.

First, the system receives vehicle states, payload-center feedback, connection errors, communication logs, and actuator-response information from the previous step.

Second, the upper layer updates the payload-center reference and constructs local path packets. In high-curvature regions, the equivalent 4WS geometric prior shapes those packets.

Third, the communication module evaluates link quality, delay, packet loss, and corrupted measurements. Delayed neighbor states are extrapolated with the Koopman predictor or a fallback rule.

Fourth, the predictor constructs \(\chi_k\), lifts it to \(z_k\), and rolls out candidate states through the projected bilinear Koopman model.

Fifth, the MPC selects the active C-mode schedule and solves for a candidate command sequence. Link quality determines consensus trust and constraint margins. Curvature and force risk determine whether lateral priority or payload protection is active.

Sixth, the execution layer checks actuator-efficiency estimates, FDI/FTC flags, command feasibility, and certificate margins. If needed, it projects the command, redistributes vehicle roles, tightens constraints, or switches to fallback.

Seventh, the safe command is published to the vehicle-payload system. The resulting states, errors, force proxies, constraints, and certificate quantities are logged and fed into the next sampling period.

## 4. Experimental Results and Analysis

The experiments are organized to match the method modules.

The Koopman prediction audit shows that the bilinear predictor slightly improves one-step RMSE relative to a linear model, while IRSP keeps comparable short-horizon prediction accuracy. The more important result is the spectral audit: sampled effective spectral radii of \(A_{\mathrm{eff}}(u)\) are reduced from above one to below one after projection. This supports the interpretation of IRSP as prediction-amplification risk control rather than as a pure accuracy enhancer.

The closed-loop Koopman ablation shows that a raw six-dimensional linear Koopman model performs poorly because it cannot represent curvature, connection geometry, communication quality, or fault context. AKE-style linear and unprojected bilinear variants can have lower mean RMSE in some single-seed cases, but the projected bilinear model is more conservative and better aligned with certificate-audited MPC.

The communication diagnostic shows that the controller responds to delay, packet loss, and link-quality degradation through consensus blending, constraint tightening, command-dispersion suppression, and protective-mode activation. This confirms that network degradation enters the control loop structurally rather than as unmodeled noise.

The FDI/FTC diagnostic shows that fault activation produces controller-side fault flags, FTC reallocation, and changes in vehicle-level command decomposition. Certificate logging continues through this transition, showing that degradation is handled online before command publication.

The main paired comparison shows that NR-KDCC and AKE-M both complete the mixed fault/noise and high communication noise scenarios. The differentiating metrics are lateral RMSE and maximum connection utilization. Under mixed fault/noise, NR-KDCC reduces lateral RMSE from \(0.0453\) to \(0.0408\) and maximum connection utilization from \(0.2999\) to \(0.0513\). Under high communication noise, it reduces lateral RMSE from \(0.0519\) to \(0.0424\) and maximum connection utilization from \(0.3757\) to \(0.0452\). Force peaks are higher than AKE-M in these main scenarios, so force is treated as a trade-off audit rather than as a primary superiority claim.

The speed-sensitivity study shows that the method works well at \(2\) m/s and \(5\) m/s, while longitudinal phase error becomes dominant at \(10\) m/s and all methods fail at \(15\) m/s. The high-speed cases are therefore boundary diagnostics.

The hairpin diagnostic separates tracking and force-protection effects. NR-KDCC-HC greatly improves lateral tracking relative to degraded AKE-M, but increases short-window force peak. Full NR-KDCC activates payload protection and lowers maximum connection utilization and force peak, but introduces more longitudinal lag and a local lateral-error excursion. This supports the claimed tracking-force trade-off.

The core ablation shows that removing communication awareness causes the largest degradation in connection utilization. Removing PPC protection causes full-path failure under mixed fault/noise, and ZOH-cons fails under the communication-stress scenarios. These results identify link-quality-aware consensus MPC and constraint tightening as the dominant modules.

## 5. Discussion and Conclusion

NR-KDCC improves network-degraded cooperative payload transport mainly by connecting prediction, communication awareness, and constraint scheduling in one MPC loop. The Koopman predictor alone is not the central claim. Its value appears when it is used together with link-quality-aware neighbor prediction, consensus weighting, connection constraints, force-risk auditing, FDI/FTC execution protection, and certificate-triggered fallback.

The strongest evidence is the reduction in lateral tracking error and connection-constraint utilization under mixed fault/noise and high communication noise. These improvements show that link quality should be embedded directly in the optimizer. The ablation study confirms this point because removing communication awareness sharply increases connection utilization.

The method also has clear limits. Force-related quantities are trade-off metrics. In high curvature, lateral-priority control can improve path tracking while increasing force peaks. Payload protection can reduce force and connection excitation, but it may sacrifice longitudinal synchronization and local tracking. High-speed operation is also not fully solved; longitudinal phase error becomes dominant at higher speeds, and \(15\) m/s is treated as a failure-mode audit.

The main conclusion is that network-resilient cooperative transport cannot be achieved by adding Koopman prediction alone. The learned predictor must be connected to communication quality, connection geometry, actuator degradation, payload-force risk, and certificate-based execution. NR-KDCC provides one such integrated structure and demonstrates its benefits under communication and fault degradation.

## One-Paragraph Summary for Presentation

This paper proposes NR-KDCC for four-vehicle rigid-payload cooperative transport under communication delay/dropout, high communication noise, actuator degradation, and high-curvature paths. The method first learns a bilinear Koopman predictor,

$$
z_{k+1}
=A z_k+B u_k^{\mathrm{ctrl}}
+\sum_{\ell=1}^{n_u}u_{k,\ell}^{\mathrm{ctrl}}N_\ell z_k+w_k,
$$

then applies input-aware spectral projection to limit prediction-error amplification in the MPC horizon. Online, the predictor is embedded in a link-quality-aware consensus MPC that adjusts neighbor trust, constraint tightening, delay compensation, and protection modes according to communication quality, curvature, connection geometry, fault state, and certificate margins. The execution layer further applies FDI/FTC, bounded role scheduling, command projection, and fallback before publishing safe commands. Experiments show improved lateral tracking and lower connection-constraint utilization relative to task-aligned AKE-M baselines, while hairpin diagnostics clarify the trade-off between high-curvature tracking and payload-force protection.

