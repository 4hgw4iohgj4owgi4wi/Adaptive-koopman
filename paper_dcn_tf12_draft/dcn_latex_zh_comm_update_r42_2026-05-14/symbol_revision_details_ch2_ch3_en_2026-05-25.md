# Symbol Revision Details for Chapters 2 and 3

Source audit:

`symbol_audit_ch2_ch3_2026-05-25.md`

Target manuscript:

`manuscript_en_intro_revised_2026_05_25.tex`

Scope:

- Chapter 2: lines 182-294 in the current target manuscript.
- Chapter 3: lines 295-533 in the current target manuscript.
- This document is an English revision specification only. It does not modify the manuscript source.

## 1. Overall Editing Goal

The technical chain in Chapters 2 and 3 is usable: vehicle dynamics, Frenet errors, payload connection geometry, communication degradation, upper-layer 4WS local-path generation, bilinear Koopman lifting, input-aware robust spectral projection (IRSP), Koopman-MPC, payload protection, and FDI/FTC are all present.

The main issue is not missing theory, but notation hygiene. Several symbols are reused across unrelated meanings, which can make a reviewer question whether the MPC cost, Koopman state, constraints, and fault-protection layer are dimensionally consistent.

The revision should therefore do three things:

1. Separate vehicle velocity symbols from control-input symbols.
2. Separate payload-state symbols from network-quality symbols.
3. Make all matrix dimensions, input ordering, and auxiliary quantities explicit before they appear in equations.

## 2. Highest-Priority Symbol Conflicts

### 2.1 Replace vehicle longitudinal/lateral velocity notation

Current issue:

- `u_i` denotes body-frame longitudinal velocity in Chapter 2.
- `u_k`, `u_{k+h}`, `u_k^{mpc}`, `u_k^{safe}`, and `u_{i,k}^{act}` later denote control inputs.

Risk:

The same symbol family `u` is used for both velocity and control input. This is the largest notation risk in the current Chapters 2 and 3.

Revision:

- Replace vehicle longitudinal velocity:

```tex
u_i \quad \rightarrow \quad v_{x,i}
```

- Replace vehicle lateral velocity:

```tex
v_i \quad \rightarrow \quad v_{y,i}
```

- Keep yaw rate as:

```tex
r_i
```

Recommended rewritten definition:

```tex
The position and heading of vehicle $i$ are $p_i=[X_i,Y_i]^\top$ and $\psi_i$.
Its body-frame longitudinal velocity, lateral velocity, and yaw rate are
$v_{x,i}$, $v_{y,i}$, and $r_i$, respectively. The control input is
$u_{i,k}^{\mathrm{ctrl}}=[a_{x,i,k},\delta_{i,k}]^\top$.
```

Equations to update:

- World kinematics:

```tex
\dot X_i = v_{x,i}\cos\psi_i-v_{y,i}\sin\psi_i,
\qquad
\dot Y_i = v_{x,i}\sin\psi_i+v_{y,i}\cos\psi_i .
```

- Bicycle dynamics:

```tex
\dot v_{y,i} =
-\frac{2C_f+2C_r}{m v_{x,i}}v_{y,i}
\left(-v_{x,i}-\frac{2C_f l_f^{\mathrm{veh}}-2C_r l_r^{\mathrm{veh}}}{m v_{x,i}}\right)r_i
+\frac{2C_f}{m}\delta_i+d_{y,i},
```

```tex
\dot v_{x,i}=a_{x,i}+r_i v_{y,i}+d_{x,i}.
```

Constraint update:

```tex
v_{x,\min}\le v_{x,i,k+h}\le v_{x,\max}.
```

Do not use `u_{\min}` or `u_{\max}` for speed bounds after this change.

### 2.2 Define the control-input vector and preserve input ordering

Current issue:

The manuscript says the physical inputs are longitudinal acceleration and steering angle, but later uses

```tex
R_u^{\mathrm{hc}}=\mathrm{diag}(\eta_\delta,1)R_u
```

while claiming that this reduces the steering penalty. This only works if the input vector is ordered as `[delta,a_x]^\top`. If the input vector is `[a_x,delta]^\top`, the formula reduces the acceleration penalty instead.

Recommended choice:

Use the physically natural order:

```tex
u_{i,k}^{\mathrm{ctrl}}=[a_{x,i,k},\delta_{i,k}]^\top .
```

Then write the high-curvature input penalty as:

```tex
R_u^{\mathrm{hc}}=\mathrm{diag}(1,\eta_\delta)R_u,
\qquad 0<\eta_\delta<1.
```

If the code actually uses `[delta,a_x]^\top`, then explicitly define that ordering and keep the current diagonal order. The manuscript must not leave this implicit.

### 2.3 Rename temporary path references currently denoted by `r`

Current issue:

`r` currently denotes all of the following:

- yaw rate `r_i`;
- temporary upper-layer path/reference `r_{i,k}^{tmp}`;
- one-step prediction residual `r_{i,k}`;
- CUSUM threshold `r_0`.

Risk:

This confuses dynamics, reference generation, and FDI residuals.

Revision:

Keep yaw rate:

```tex
r_i
```

Rename temporary path/reference:

```tex
r_{i,k}^{\mathrm{tmp}} \quad \rightarrow \quad \mathcal P_{i,k}^{\mathrm{tmp}}
```

or, if a vector path parameter is desired:

```tex
\xi_{i,k}^{\mathrm{tmp}}
```

Recommended text:

```tex
The upper layer sends a temporary local path packet
$\mathcal P_{i,k}^{\mathrm{tmp}}$ to vehicle $i$.
```

Rename prediction residuals:

```tex
r_{i,k} \quad \rightarrow \quad \varepsilon_{i,k}^{\mathrm{pred}},
\qquad
\bar r_{i,k} \quad \rightarrow \quad \bar\varepsilon_{i,k}^{\mathrm{pred}}.
```

Rename CUSUM baseline:

```tex
r_0 \quad \rightarrow \quad \varepsilon_0
```

Rewritten FDI monitor:

```tex
\bar\varepsilon_{i,k}^{\mathrm{pred}}
=
(1-\alpha_\varepsilon)\bar\varepsilon_{i,k-1}^{\mathrm{pred}}
+\alpha_\varepsilon \varepsilon_{i,k}^{\mathrm{pred}},
```

```tex
c_{i,k}=\max\{0,c_{i,k-1}
+\bar\varepsilon_{i,k}^{\mathrm{pred}}-\varepsilon_0\}.
```

### 2.4 Separate payload pose from communication quality

Current issue:

- `q_L` is payload pose.
- `q_{ij,k}` is link quality.
- `q_k` is aggregate communication quality.
- `\mathcal U(\hat\eta,q)` uses `q` again for communication quality.

Risk:

The reader may interpret `q_L` and `q_k` as related state variables, although one is payload pose and the other is network quality.

Revision:

Rename payload pose:

```tex
q_L=[X_L,Y_L,\psi_L]^\top
\quad \rightarrow \quad
\xi_L=[X_L,Y_L,\psi_L]^\top .
```

Keep pairwise link quality:

```tex
q_{ij,k}\in[0,1].
```

Rename aggregate network quality:

```tex
q_k \quad \rightarrow \quad q_k^{\mathrm{net}}
```

Use it consistently in constraints and safety sets:

```tex
e_{c,\max}(q_k^{\mathrm{net}}),
\qquad
\mathcal U(\hat\eta_k,q_k^{\mathrm{net}}).
```

### 2.5 Separate vehicle wheelbase from upper-layer 4WS equivalent geometry

Current issue:

`l_f,l_r` are used both for the single-vehicle bicycle model and the equivalent four-wheel-steering (4WS) upper-layer platform.

Risk:

The reviewer may think the equivalent payload-level platform uses the same geometric parameters as a single vehicle.

Revision:

Use:

```tex
l_f^{\mathrm{veh}},\quad l_r^{\mathrm{veh}}
```

for the vehicle model, and:

```tex
l_f^{\mathrm{4ws}},\quad l_r^{\mathrm{4ws}},\quad
L^{\mathrm{4ws}}=l_f^{\mathrm{4ws}}+l_r^{\mathrm{4ws}}
```

for the upper-layer equivalent platform.

Update the 4WS equations:

```tex
\beta^{\mathrm{4ws}}=
\tan^{-1}\left(
\frac{l_r^{\mathrm{4ws}}\tan\delta_f^{\mathrm{up}}
+l_f^{\mathrm{4ws}}\tan\delta_r^{\mathrm{up}}}
{L^{\mathrm{4ws}}}
\right),
```

```tex
\kappa^{\mathrm{4ws}}=
\frac{\cos\beta^{\mathrm{4ws}}}{L^{\mathrm{4ws}}}
\left(\tan\delta_f^{\mathrm{up}}-\tan\delta_r^{\mathrm{up}}\right).
```

### 2.6 Fix the dimension of `Q_v`

Current issue:

The MPC cost uses:

```tex
\norm{e_{y,i,k+h},e_{\psi,i,k+h}}_{Q_v}^2
```

which suggests `Q_v` is a `2 x 2` matrix, but the high-curvature mode uses:

```tex
Q_v^{\mathrm{hc}}=
\mathrm{diag}(1,\eta_y,\eta_\psi,1,1,1)Q_v
```

which assumes `Q_v` is `6 x 6`.

Recommended minimal fix:

Use a 2D vehicle tracking-error vector:

```tex
\xi_{v,i,k}=[e_{y,i,k},e_{\psi,i,k}]^\top,
\qquad
Q_v\in\mathbb R^{2\times 2}.
```

Then write:

```tex
\norm{\xi_{v,i,k+h}}_{Q_v}^2
```

and:

```tex
Q_v^{\mathrm{hc}}
=
\mathrm{diag}(\eta_y,\eta_\psi)Q_v,
\qquad
\eta_y>1,\quad \eta_\psi>1.
```

Alternative larger fix:

If the actual controller uses a 6D vehicle error vector, define it explicitly before the cost:

```tex
\xi_{v,i,k}
=
[e_{s,i,k},e_{y,i,k},e_{\psi,i,k},
v_{x,i,k}-v_x^{\mathrm{ref}},
v_{y,i,k},r_{i,k}]^\top .
```

Then use:

```tex
\norm{\xi_{v,i,k+h}}_{Q_v}^2,
\qquad
Q_v\in\mathbb R^{6\times 6}.
```

Do not mix the 2D cost form with the 6D scaling form.

### 2.7 Align Koopman state dimension with the claimed observation content

Current issue:

The manuscript defines:

```tex
x_k\in\mathbb R^{n_x},\qquad n_x=6,
```

but the Introduction and overview say the lifted observation includes vehicle states, centroid errors, connection geometry, communication quality, and fault indicators.

Risk:

The reviewer may see a mismatch between the method claim and the Koopman formula.

Recommended fix if the actual model is team/context aware:

Define an enhanced observation:

```tex
\chi_k=
\mathrm{col}\big(
x_{1,k},\ldots,x_{N,k},
e_{L,k},e_{c,k},
q_k^{\mathrm{net}},
\hat\eta_k,
\zeta_k
\big),
```

where `\zeta_k` collects optional curvature, path, or mode indicators used by the implementation.

Then define:

```tex
z_k=\Phi_\theta(\chi_k)
=
[\chi_k^\top,\phi_\theta(\chi_k)^\top]^\top
\in\mathbb R^{n_z}.
```

Recommended text:

```tex
The symbol $\chi_k$ denotes the enhanced observation used for learning and control.
It includes the physical vehicle states and the task/network context variables that
are available to the controller. The raw per-vehicle dynamic state remains
$x_{i,k}\in\mathbb R^6$.
```

If the actual model is purely per-vehicle:

- Keep `x_{i,k}\in\mathbb R^6`.
- Remove or weaken claims that team-center errors, connection geometry, communication quality, and fault indicators are included in the lifted observation.

### 2.8 Correct the continuous IRSP certificate `gamma_c`

Current issue:

The formula currently uses `\bar u_\ell` both as an input upper bound and as the absolute input envelope being defined. It also allows `\gamma_c<0` if `r_u<\|A^+\|_2`.

Revision:

Define:

```tex
u_{\ell,\max}^{\mathrm{abs}}
=
\max\{|u_\ell^{\min}|,|u_\ell^{\max}|\}.
```

Then write:

```tex
\gamma_c=
\max\left\{
0,
\min\left(
1,
\frac{r_u-\|A^+\|_2}
{\sum_{\ell=1}^{n_u}
u_{\ell,\max}^{\mathrm{abs}}\|N_\ell\|_2+\epsilon}
\right)
\right\}.
```

Add:

```tex
If $r_u<\|A^+\|_2$, the conservative continuous-input certificate sets
$\gamma_c=0$.
```

This removes self-reference and enforces `0 <= gamma_c <= 1`.

## 3. Required Definition Additions

Add or revise the following definitions before the first use of each symbol.

### Chapter 2 definitions

1. Vehicle index:

```tex
i\in\{1,\ldots,N\},\qquad N=4.
```

2. Payload planar position:

```tex
p_L=[X_L,Y_L]^\top.
```

3. Connection-error stack dimension:

```tex
e_c=\mathrm{col}(e_{c,1},\ldots,e_{c,N})\in\mathbb R^{2N}.
```

4. Connection-force parameters:

```tex
K_c,D_c\in\mathbb R^{2\times 2}
```

or, if scalar:

```tex
K_c,D_c>0.
```

5. 2D cross product for payload torque:

```tex
a\times b=a_xb_y-a_yb_x,\qquad a,b\in\mathbb R^2.
```

6. Ring-neighbor convention:

```tex
The neighbor indices $i-1$ and $i+1$ are taken modulo $N$.
```

7. Dropout indicator convention:

```tex
\ell_{ij,k}=1
```

means packet dropout, and:

```tex
\ell_{ij,k}=0
```

means successful reception.

8. Team/payload path progress:

```tex
s_k
```

should be defined as the reference progress of the payload centroid or team centroid, whichever is used in the code.

9. Payload/centroid lateral error:

```tex
e_{y,L,k}
```

should be defined by projecting the payload centroid or team centroid onto the reference path.

### Chapter 3 definitions

1. Upper-layer reference heading:

```tex
\psi_{L,k}^{\mathrm{ref}}=\psi_r(s_k)
```

if the payload reference heading is the path tangent.

2. Upper-layer reference path:

```tex
p_L^{\mathrm{ref}}(s)
```

should be introduced before `eq:fourws_local_path`.

3. 4WS local-path interpolation parameter:

Avoid reusing `\sigma` because `\sigma_k` is used for payload protection. Use:

```tex
\varsigma\in[0,\ell_p].
```

4. Ridge-regression stacks:

```tex
Z_+=[z_2,\ldots,z_M],
\qquad
\Xi=[\Xi_1,\ldots,\Xi_{M-1}].
```

5. Koopman matrix dimensions:

```tex
A,N_\ell\in\mathbb R^{n_z\times n_z},
\qquad
B\in\mathbb R^{n_z\times n_u}.
```

6. Projection operator:

```tex
\Pi_{r_A}(\cdot)
```

should be described as a spectral projection that rescales unstable eigenvalues or singular modes to satisfy the selected radius bound.

7. Residual-bound constants:

```tex
\bar w_0,\bar w_x,\bar w_q\ge0.
```

State whether they are estimated from validation trajectories or selected as conservative design constants.

8. MPC horizon:

```tex
H\in\mathbb Z_{>0}.
```

9. Weight matrices:

```tex
Q_L,P_L,Q_v,Q_c,Q_e,R_u,R_\Delta,R_s\succeq0
```

or `\succ0` where strict positive definiteness is required.

10. Distance weight:

Replace:

```tex
q_d
```

with:

```tex
w_d
```

or:

```tex
Q_d
```

to avoid confusion with communication quality `q`.

11. Payload-protection weights:

```tex
\lambda_c,\lambda_u,\lambda_F\ge0.
```

12. Safe control set:

```tex
\mathcal U(\hat\eta_k,q_k^{\mathrm{net}})
```

should be defined as the set of admissible control inputs after actuator-efficiency degradation and network-quality tightening.

## 4. Formula-Level Revision Details

### 4.1 `eq:world_kinematics`

Change only velocity names. No structural change is needed.

### 4.2 `eq:bicycle_dynamics`

Update:

- `u_i` to `v_{x,i}`;
- `v_i` to `v_{y,i}`;
- `l_f,l_r` to `l_f^{veh},l_r^{veh}`;
- disturbance names to match velocity names, for example `d_{x,i},d_{y,i},d_{r,i}`.

Add a sentence:

```tex
The numerical implementation uses $v_{x,i}\leftarrow\max(v_{x,i},v_{x,\min})$
to avoid low-speed singularity.
```

### 4.3 `eq:comm_corrupted_measurements`

Rename:

```tex
r_{i,k}^{\mathrm{tmp}}
\rightarrow
\mathcal P_{i,k}^{\mathrm{tmp}}.
```

Use distinct bias notation:

```tex
\beta^d_{ij,k},\quad \beta^y_k,\quad \beta^p_{i,k}
```

instead of `b^d,b^y,b^r`, because `b_i` already denotes payload attachment geometry.

### 4.4 `eq:delay_prediction`

Current form:

```tex
\hat z_{j,k-\tau+\tau|k-\tau}
```

is algebraically equal to `k|k-\tau` but visually confusing.

Recommended form:

```tex
\hat x_{j,k}^{\mathrm{net}}=
\begin{cases}
\Pi_x\hat z_{j,k|k-\tau_{ij,k}^{x}}, & \ell_{ij,k}=0,\\
\hat x_{j,k-1}^{\mathrm{net}}, & \ell_{ij,k}=1.
\end{cases}
```

Then define:

```tex
\hat z_{j,k|k-\tau_{ij,k}^{x}}
```

as the Koopman/kinematic prediction from the delayed received state to the current time.

### 4.5 `eq:fourws_local_path`

Rename the local interpolation variable:

```tex
\sigma \rightarrow \varsigma
```

to avoid conflict with the payload-protection switch `\sigma_k`.

Use:

```tex
\varsigma\in[0,\ell_p].
```

### 4.6 `eq:koopman_lift`

Preferred revision:

```tex
\chi_k\in\mathbb R^{n_\chi}
```

for enhanced observation, then:

```tex
z_k=\Phi_\theta(\chi_k)
=[\chi_k^\top,\phi_\theta(\chi_k)^\top]^\top
\in\mathbb R^{n_z}.
```

Use `x_{i,k}` only for raw physical vehicle state.

### 4.7 `eq:norm_irsp_certificate`

Replace the formula with the corrected `gamma_c` expression in Section 2.8.

### 4.8 `eq:mpc_cost`

If using the minimal 2D vehicle-error representation:

```tex
\xi_{v,i,k+h}=[e_{y,i,k+h},e_{\psi,i,k+h}]^\top,
```

then write:

```tex
\sum_i \|\xi_{v,i,k+h}\|_{Q_v}^2.
```

Control input:

```tex
\|u_{k+h}^{\mathrm{ctrl}}\|_{R_u}^2
+\|\Delta u_{k+h}^{\mathrm{ctrl}}\|_{R_\Delta}^2.
```

Define:

```tex
\Delta u_{k+h}^{\mathrm{ctrl}}
=u_{k+h}^{\mathrm{ctrl}}-u_{k+h-1}^{\mathrm{ctrl}}.
```

### 4.9 `eq:constraints`

Rewrite the first constraint as a speed bound:

```tex
v_{x,\min}\le v_{x,i,k+h}\le v_{x,\max}.
```

Keep steering and acceleration bounds as input bounds:

```tex
|\delta_{i,k+h}|\le\delta_{\max},
\qquad
|a_{x,i,k+h}|\le a_{\max}.
```

Use:

```tex
e_{c,\max}(q_k^{\mathrm{net}})
```

instead of `e_{c,\max}(q_k)`.

### 4.10 `eq:high_curvature_lateral_priority`

If control input is `[a_x,\delta]^\top`, use:

```tex
R_u^{\mathrm{hc}}=\mathrm{diag}(1,\eta_\delta)R_u.
```

If `Q_v` is 2D, use:

```tex
Q_v^{\mathrm{hc}}=\mathrm{diag}(\eta_y,\eta_\psi)Q_v.
```

### 4.11 `eq:payload_protection_switch`

Current risk:

The text says the switch reacts to force or connection risk, but the formula only uses curvature.

Recommended minimal wording correction:

```tex
The curvature window activates the payload-protection branch in the high-risk
hairpin segment; within this branch, the cost terms below penalize connection
utilization, control dispersion, and predicted payload-force proxy.
```

Recommended stronger formula, if desired:

```tex
\sigma_k=
\max\{\sigma_k^\kappa,\sigma_k^F,\sigma_k^c\},
```

where `\sigma_k^\kappa`, `\sigma_k^F`, and `\sigma_k^c` are curvature, force-risk, and connection-risk activation factors.

### 4.12 `eq:payload_protection_cost`

Define:

```tex
\bar u_k^{\mathrm{ctrl}}
=
\frac{1}{N}\sum_{i=1}^N u_{i,k}^{\mathrm{ctrl}}.
```

Define the force proxy:

```tex
\hat F_{L,k}^{xy}
```

as either the predicted resultant payload force or a stated surrogate computed from connection errors and relative velocities.

### 4.13 `eq:actuator_efficiency`

Use control-specific notation:

```tex
u_{i,k}^{\mathrm{act}}
=
\eta_{i,k}\odot u_{i,k}^{\mathrm{cmd}}+\nu_{i,k}.
```

This can be kept if all vehicle speed symbols have already been renamed to `v_x,v_y`. Otherwise, rename the control vector to:

```tex
\upsilon_{i,k}^{\mathrm{act}},
\qquad
\upsilon_{i,k}^{\mathrm{cmd}}.
```

Define:

```tex
\nu_{i,k}
```

as bounded execution noise or actuator disturbance.

### 4.14 `eq:fdi_ewma_cusum`

Rename residual variables as in Section 2.3.

### 4.15 `eq:ftc_projection`

Use:

```tex
u_k^{\mathrm{safe}}
=
\arg\min_{u\in\mathcal U(\hat\eta_k,q_k^{\mathrm{net}})}
\|u-u_k^{\mathrm{mpc}}\|_{R_s}^2
+\alpha_e\|e_{c,k+1}(u)\|^2.
```

Then define:

- `R_s\succeq0` or `R_s\succ0`;
- `\alpha_e\ge0`;
- `e_{c,k+1}(u)` as the one-step predicted connection error under candidate input `u`.

## 5. Recommended Editing Order

### Step 1: Rename global conflicting symbols

Do these first because they affect many formulas:

1. `u_i -> v_{x,i}` for longitudinal speed.
2. `v_i -> v_{y,i}` for lateral speed.
3. `q_L -> \xi_L` for payload pose.
4. `q_k -> q_k^{net}` for aggregate network quality.
5. `r_{i,k}^{tmp} -> \mathcal P_{i,k}^{tmp}`.
6. FDI residual `r` variables -> `\varepsilon^{pred}` variables.
7. `l_f,l_r` in vehicle model -> `l_f^{veh},l_r^{veh}`.
8. `l_f,l_r,L` in 4WS model -> `l_f^{4ws},l_r^{4ws},L^{4ws}`.

### Step 2: Insert missing definitions before formulas

Insert compact definition sentences before the relevant equations. Do not create a long symbol table unless the journal format allows it.

### Step 3: Fix dimension-sensitive formulas

Prioritize:

1. `Q_v` and `Q_v^{hc}`;
2. `R_u^{hc}`;
3. Koopman enhanced observation `\chi_k`;
4. corrected `\gamma_c`;
5. MPC constraints and FTC projection.

### Step 4: Recompile and check

After edits:

1. Run XeLaTeX/BibTeX/XeLaTeX/XeLaTeX if references are affected.
2. Search the log for undefined references and hard errors.
3. Search the source for remaining ambiguous patterns:

```text
u_i
r_{i,k}^{tmp}
\bar r
r_0
q_L
q_k)
l_f,l_r
Q_v^{\mathrm{hc}}=\mathrm{diag}(1,\eta_y,\eta_\psi,1,1,1)
R_u^{\mathrm{hc}}=\mathrm{diag}(\eta_\delta,1)
```

## 6. Minimal Patch Checklist

If only one compact revision pass is allowed, complete these ten items:

1. Rename vehicle velocities to `v_{x,i}` and `v_{y,i}`.
2. Define `u_{i,k}^{ctrl}=[a_{x,i,k},\delta_{i,k}]^\top`.
3. Correct `R_u^{hc}` according to the input order.
4. Rename temporary path references from `r^{tmp}` to `\mathcal P^{tmp}`.
5. Rename FDI residual variables from `r` to `\varepsilon^{pred}`.
6. Rename payload pose to `\xi_L` and aggregate network quality to `q_k^{net}`.
7. Add `veh` and `4ws` superscripts to the two wheelbase families.
8. Make `Q_v` either consistently 2D or consistently 6D.
9. Replace the `\gamma_c` formula with the nonnegative, non-self-referential version.
10. Add definitions for `p_L`, `s_k`, `e_{y,L,k}`, `p_L^{ref}`, `\psi_L^{ref}`, `Z_+`, `\Xi`, `\Pi_x`, `K_c`, `D_c`, `\omega^d`, `Q_d/w_d`, `\lambda_c`, `\lambda_u`, `\lambda_F`, `R_s`, and `\alpha_e`.

## 7. Reviewer-Facing Rationale

These edits are not cosmetic. They reduce three specific reviewer risks:

1. Dimensional ambiguity: the reader can verify that MPC weights, Koopman states, and high-curvature scaling act on vectors of the correct dimension.
2. Semantic ambiguity: the reader can distinguish velocity, control input, path reference, residual, payload pose, and link quality without relying on context.
3. Baseline and mechanism traceability: the same symbols used in the model, controller, and experiments will refer to the same physical or algorithmic quantities.

After these notation fixes, Chapters 2 and 3 should read as a reproducible control formulation rather than an engineering description with locally overloaded symbols.
