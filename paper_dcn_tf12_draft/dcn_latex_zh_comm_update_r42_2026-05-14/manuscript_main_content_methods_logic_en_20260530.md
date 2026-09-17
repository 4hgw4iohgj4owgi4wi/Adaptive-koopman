# English Text Draft with Expanded Method Logic

Source manuscript: `manuscript_en_ch4_ch7_balanced_full_2026_05_26_figrev6_fig2dataflow_20260528.tex`

This draft is a prose-oriented English version of the main manuscript content. It is not a line-by-line translation of the LaTeX source. The method section is intentionally expanded to make the logic among modeling, Koopman learning, communication compensation, MPC scheduling, fault protection, certificate checking, and experimental evidence explicit.

## Title

Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC

## Abstract Draft

Four autonomous vehicles transporting a rigid payload must coordinate centroid tracking, connection preservation, payload-force safety, and actuator commands under high path curvature, communication delay/dropout, and actuator degradation. This paper proposes NR-KDCC, a network-resilient Koopman delay-compensated consensus control framework. The method combines a stability-projected bilinear Koopman predictor with a link-quality-aware consensus MPC loop. The predictor learns short-horizon vehicle-payload evolution from offline data and is projected through an input-aware spectral audit so that input-dependent lifted dynamics do not amplify prediction errors inside the MPC horizon. The MPC layer then uses link quality, connection geometry, curvature, fault indicators, and certificate margins to schedule consensus weights, constraint tightening, delay compensation, fallback decisions, and payload-protection terms.

The proposed framework is evaluated against task-aligned adaptive Koopman embedding baselines and low-order consistency baselines. In paired tests under mixed fault/noise and high communication noise, NR-KDCC reduces lateral tracking error and connection-constraint utilization relative to AKE-M while maintaining full-path completion. High-curvature hairpin diagnostics further show that lateral-priority control improves tracking but can increase short-window payload-force peaks, whereas the payload-protection branch reduces connection utilization and force level at the cost of longitudinal lag and local lateral-error excursions. The results indicate that Koopman prediction benefits network-degraded cooperative transport only when link quality, connection geometry, and payload-force risk enter the control loop together.

## 1. Introduction Draft

Path tracking is a basic function of autonomous vehicles and mobile robots, but four-vehicle rigid-payload transport is more demanding than ordinary single-vehicle tracking. The team must track the payload-center reference, regulate vehicle-to-payload connection errors, coordinate adjacent vehicles, respect steering and acceleration limits, and avoid excessive payload-force excitation. These objectives become strongly coupled under high curvature, communication delay/dropout, and actuator degradation.

Classical tracking controllers such as pure pursuit, Stanley control, LQR, and preview control are computationally efficient, but they are not designed to handle the simultaneous interaction among payload geometry, multi-vehicle consensus, link quality, force-risk auditing, and degraded execution. MPC and distributed MPC are better suited to constrained control, yet many networked-control formulations either assume reliable communication or treat delay and packet loss as bounded external disturbances. In cooperative payload transport, communication degradation changes neighbor prediction, reference delivery, centroid feedback, command reception, and force distribution. It should therefore be used inside the controller as a scheduling variable, not only as an additive uncertainty.

Koopman learning offers a useful way to build data-driven predictors that remain compatible with MPC. By lifting nonlinear dynamics to a higher-dimensional observable space, Koopman models can provide short-horizon predictions for constrained optimization. However, finite-dimensional Koopman models still contain residual errors, and these errors can be amplified by high curvature, aggressive steering, communication degradation, and replanning. This paper therefore does not use Koopman learning as an isolated prediction module. Instead, it embeds a bilinear Koopman predictor into a network-aware MPC loop and audits the input-dependent lifted dynamics through input-aware robust spectral projection.

The main contribution is the integration of learning, communication compensation, safety scheduling, and certificate-driven execution in one coherent transport-control framework. The offline layer learns a bilinear Koopman model from scenarios that include curvature variation, communication degradation, and actuator-efficiency loss. The online layer uses the learned model to compensate delay, predict neighboring states, and evaluate candidate control sequences. The MPC layer schedules weights and constraints according to link quality, connection geometry, curvature, and safety margins. The execution layer then checks actuator faults, projects unsafe commands, activates fallback when needed, and logs a Lyapunov/ISS certificate. This structure is designed to make the learned predictor useful without relying on an unsupported claim of global prediction accuracy.

## 2. System Modeling and Problem Definition Draft

The system consists of four vehicles connected to a rigid payload. Each vehicle is described in the global frame by position, heading, longitudinal velocity, lateral velocity, and yaw rate. The control input contains longitudinal acceleration and front steering. The global kinematics are used for simulation and payload geometry, while Frenet-coordinate errors are used for tracking and MPC cost construction.

The payload center is treated as the representative team center. Each vehicle is associated with a fixed connection point on the payload. After transforming these connection points into the global frame, the difference between the vehicle position and the corresponding payload connection point defines the connection error. A spring-damper-style force proxy is constructed from the connection error and its rate. This proxy is used for cost shaping and safety auditing. It is not claimed to be a direct force-sensor measurement or a globally exact estimate of the true payload force.

Communication is modeled as a five-node graph. Node 0 is the upper cooperative reference planner, and nodes 1 to 4 are the executing vehicles. The vehicle layer uses ring-neighbor communication, while the upper node broadcasts short-horizon local path packets to the four vehicles. Communication degradation affects three major data types: adjacent-vehicle distances, payload-center lateral error, and upper-to-lower temporary path packets. Each degraded signal can contain delay, bias, noise, or packet loss. Link quality is represented explicitly and then used by the controller to adjust neighbor trust, consensus weights, constraint tightening, and fallback decisions.

The control problem is therefore not only to track a path. It is to maintain a feasible and safe cooperative transport process under imperfect prediction, unreliable communication, actuator degradation, connection constraints, and payload-force risk.

## 3. Proposed NR-KDCC Method

### 3.1 Overall Logic

NR-KDCC is organized as a closed-loop sequence with five logical layers.

The first layer is the offline learning layer. It generates vehicle-payload-communication data under nominal, noisy, faulty, and mixed degraded conditions. These data are used to fit a bilinear Koopman predictor. The same layer also performs input-aware stability projection so that the learned lifted dynamics remain suitable for MPC.

The second layer is the upper reference and communication layer. It generates payload-center references and vehicle-specific local path packets. This layer also processes link quality, delay, packet loss, and path-delivery uncertainty. It does not directly control the vehicles. Its role is to provide geometry-aware and communication-aware reference information to the lower optimizer.

The third layer is the online prediction and consensus-MPC layer. It fuses local observations, delayed neighbor information, upper-layer path packets, and Koopman predictions. It predicts the short-horizon evolution of vehicle states, payload-center errors, and connection errors. It then solves one MPC problem whose cost and constraints are scheduled by communication quality, curvature, connection risk, and protection mode.

The fourth layer is the safety, FDI/FTC, and certificate layer. It receives candidate MPC commands, checks actuator degradation, redistributes commands if a channel is degraded, evaluates certificate margins, and activates projection, tightening, or fallback if the candidate command is unsafe.

The fifth layer is the vehicle-payload environment and feedback layer. The vehicle-payload system executes the published command and returns measured states, tracking errors, connection errors, force proxies, constraint terms, communication logs, and certificate quantities. These feedback logs close the loop for the next sampling period.

The important point is that these layers are not independent controllers. They are ordered parts of one closed-loop pipeline. The offline Koopman model gives the prediction interface. The communication layer determines how reliable the received information is. The MPC layer uses that reliability to optimize a candidate input sequence. The execution layer decides whether that candidate can be safely applied. The environment feedback then updates the next prediction and certificate step.

### 3.2 Method Naming and Variant Roles

NR-KDCC denotes the full framework. It includes the bilinear Koopman predictor, input-aware robust spectral projection, link-quality-aware consensus MPC, upper-layer 4WS local path publication, FDI/FTC execution protection, role scheduling, certificate checking, and curvature-window payload protection.

NR-KDCC-base removes role scheduling while retaining the main network-aware Koopman-MPC structure. This variant is used to show whether the additional role-scheduling trim contributes beyond the main optimizer.

NR-KDCC-HC enables the high-curvature lateral-priority branch but does not enable payload protection. This variant is useful because it separates high-curvature tracking improvement from force-risk reduction. If NR-KDCC-HC improves lateral tracking but increases force peaks, while full NR-KDCC reduces those force peaks, then the roles of the two branches are clearly separated.

AKE-M and AKE-M-degraded are task-aligned baselines inspired by adaptive Koopman embedding. They adapt the idea of online Koopman prediction correction to the present four-vehicle rigid-payload transport task. They are not claimed to reproduce the original AKE experiments one-to-one.

ZOH-cons is a low-order zero-order-hold consistency baseline. It is used to expose what happens when learned prediction and network-aware protection are absent.

### 3.3 Upper-Layer Equivalent 4WS Local Path Publication

The upper layer uses an equivalent four-wheel-steering representation of the payload-centered team. This does not replace the lower vehicle model and does not claim to describe the true payload dynamics. It is a geometric path-publication device.

The motivation is that a rigid payload moving through high curvature cannot be handled well if each vehicle only corrects its own local lateral error. The vehicles must receive references that are consistent with the payload-center motion and with the relative positions of their connection points. The equivalent 4WS planner provides this geometric consistency. It computes front and rear equivalent steering quantities from the reference curvature and then converts them into vehicle-specific desired headings and local path packets.

The data flow is as follows. The reference path provides curvature, heading, and payload-center progress. The upper planner uses these quantities to compute an equivalent payload-centered turning direction. For each vehicle, the planner combines the payload reference pose with the vehicle's payload-frame connection offset. The output is a temporary local path packet for that vehicle. This packet is then sent through the upper-to-lower communication edge, where it can suffer delay, packet loss, bias, or noise just like other network signals.

Thus, the upper layer contributes two things to the lower MPC: a geometry-aware local path and an explicit communication-quality signal for the path-delivery channel. The lower layer remains responsible for vehicle dynamics, constraints, prediction, and control.

### 3.4 Offline Data Generation and Why It Is Needed

The Koopman predictor is trained offline because the controller needs a short-horizon prediction model before online control begins. The data generation process deliberately includes nominal operation, high communication noise, single actuator faults, and mixed fault/noise cases. This is necessary because the online controller will operate in exactly these degraded regimes. If the offline data only covered clean tracking, the learned predictor would not encode the coupling among curvature, communication degradation, actuator-efficiency loss, and connection errors.

Each trajectory records physical vehicle states, payload-center quantities, connection errors, control inputs, communication quality, delay/loss variables, actuator-efficiency estimates, and certificate-related quantities. Random steering excitation, acceleration perturbation, curvature variation, and communication-quality disturbances are included to avoid a dataset consisting only of steady or near-equilibrium motion.

The resulting dataset serves two purposes. First, it fits the Koopman lifting and bilinear lifted dynamics. Second, it gives realistic input and state envelopes for the input-aware stability projection. This means the stability audit is tied to the same operating region that the controller will later use.

### 3.5 Bilinear Koopman Lifting

The raw physical state alone is not enough for this task. A six-dimensional vehicle state can describe local vehicle motion, but it does not directly include payload-center error, connection geometry, path curvature, link quality, or actuator degradation. NR-KDCC therefore uses an enhanced observation vector. This observation contains vehicle-local states, payload-center tracking quantities, connection geometry, communication quality, fault context, and path-context variables.

The Koopman lifting maps this enhanced observation into a higher-dimensional lifted state. The reported implementation uses a 24-dimensional observation and a 31-dimensional lifted state. The lifted state contains the original observation plus learned nonlinear features.

The lifted dynamics are bilinear in the control input. This is important because steering and acceleration do not simply add independent corrections. Steering interacts with lateral velocity, yaw rate, path curvature, and connection geometry. Acceleration interacts with longitudinal phase, payload-center progress, and force distribution. A purely linear lifted model can miss these input-state couplings. The bilinear model includes terms where each control input multiplies the lifted state, allowing the effective prediction matrix to change with the applied command.

The parameters are estimated by ridge regression. Ridge regularization is used to reduce parameter amplification caused by limited data, correlated regressors, and noisy observations. Online residual updates may be used, but they are constrained by the stability projection and by the MPC operating bounds. The controller therefore does not allow online adaptation to freely change the predictor in a way that could destroy feasibility or certificate validity.

### 3.6 Input-Aware Robust Spectral Projection

A central issue is that the bilinear Koopman predictor has an input-dependent effective matrix. Even if the main lifted matrix appears stable, the effective matrix under a large steering or acceleration command may have a spectral radius greater than one. Such a predictor can amplify residuals during the MPC prediction horizon, especially in high curvature or degraded communication.

NR-KDCC therefore applies input-aware robust spectral projection. The main matrix is first projected to a smaller drift radius. The bilinear input matrices are then scaled so that the effective matrix remains within a sampled spectral bound over representative control inputs. The sampled set includes training-input quantiles, boundary values, and corner points. A conservative norm-based certificate can also be computed as an audit, but the default experiments use the sampled spectral projection to avoid weakening the bilinear terms too much.

This projection should be interpreted correctly. It is not a proof that the true nonlinear vehicle-payload system is globally stable. It is also not primarily an accuracy-improvement device. Its role is controller-side risk control: it limits input-dependent error amplification of the learned predictor inside the MPC operating region. The experiments confirm this interpretation. The bilinear and projected bilinear predictors have comparable short-horizon prediction errors, but the projection reduces sampled effective spectral radii from values above one to values below one.

### 3.7 Communication-Quality-Aware Consensus MPC

The lower-layer optimizer is one MPC problem. It is not a collection of separate controllers. The optimizer predicts future states with the Koopman model and minimizes a cost that includes payload-center tracking error, vehicle lateral and heading errors, neighbor-consensus errors, adjacent-distance errors, connection errors, control effort, and input-rate penalties.

Communication quality enters the MPC in several places.

First, it affects neighbor prediction. If a neighbor state arrives with delay, the lifted predictor extrapolates it to the current time. If a packet is lost, the controller uses a held or fallback estimate. Thus, delay compensation is directly connected to the Koopman prediction interface.

Second, link quality affects consensus weights. A reliable neighbor can be trusted more strongly in the consensus term. An unreliable neighbor receives a lower weight, preventing poor communication from forcing the optimizer to chase corrupted information.

Third, network quality affects constraint tightening. When communication deteriorates, the controller tightens connection-error and input bounds to preserve feasibility and reduce risk. This is why communication degradation is treated as a scheduling signal rather than only as a disturbance.

Fourth, severe network degradation can trigger the conservative C3 fallback mode. In that case, the controller prioritizes connection preservation and input feasibility, may reduce reference progress, and suppresses dependence on unreliable neighbor information.

The resulting logic is: communication quality determines how much the controller trusts received information, how much margin it reserves in constraints, and whether normal tracking should yield to conservative safety.

### 3.8 C-Mode Scheduling and Protection Branches

The online control mode is denoted by C0, C1, C2, or C3.

C0 is normal tracking and connection preservation. It is used when curvature, communication, and actuator conditions are within normal ranges.

C1 is the high-curvature lateral-priority mode. It increases the weights on lateral and heading errors and moderately reduces the steering penalty. This makes the optimizer more willing to use steering authority to suppress lateral deviation during curve entry and high-curvature segments. The connection constraints remain active, so the vehicle cannot improve its own lateral error by ignoring payload geometry.

C2 is the payload-protection mode. It is activated in a curvature window when connection excitation and force risk become more important. This mode strengthens penalties on connection error, input dispersion among vehicles, and the planar payload resultant-force proxy. Its goal is not to minimize lateral error at every instant. Its goal is to reduce force peaks and connection excitation while keeping tracking acceptable.

C3 is the conservative degraded mode. It is triggered by severe communication degradation, actuator-efficiency loss, or certificate concerns. It reduces trust in unreliable information, prioritizes connection and input constraints, and can contract reference progress to maintain a nonempty feasible set.

These modes are not different controllers. They are different weight and constraint schedules for the same Koopman-MPC optimizer. If several triggers occur simultaneously, safety feasibility has priority, followed by payload protection, high-curvature tracking robustness, and nominal tracking. This priority order explains why the controller may intentionally sacrifice longitudinal phase or local tracking smoothness when force or connection risk becomes dominant.

### 3.9 FDI/FTC Execution-Layer Protection

The MPC produces a candidate command sequence, but the execution layer decides whether the first command can be safely published. This separation is important because the optimizer may compute a command assuming nominal actuator response, while the actual actuator may be degraded.

The FDI module estimates actuator efficiency for both longitudinal acceleration and steering channels. It uses prediction residuals, exponentially weighted moving averages, cumulative sums, warm-up counters, consecutive-trigger logic, and release-hold logic. The purpose is to avoid classifying ordinary communication noise or transient prediction error as a persistent actuator fault.

When a channel is identified as degraded, the FTC module projects the MPC command into a conservative feasible input set. This projection keeps the command close to the MPC candidate while accounting for degraded actuator authority and connection-error growth. It does not guarantee monotonic reduction of connection error at every step. Instead, it guarantees a weaker and more realistic property: the additional connection-error degradation induced by safety projection remains bounded by actuator-degradation and link-quality terms.

Role scheduling is also applied at the execution layer. It adjusts each vehicle's contribution to lateral correction, longitudinal propulsion, and connection protection according to curvature, link quality, and fault state. However, only a small bounded trim is allowed after the main MPC feedback. This prevents role scheduling from overriding the constraint-consistent decision made by the optimizer.

The execution-layer logic is therefore: diagnose degradation, project unsafe commands, apply bounded redistribution, check certificate margin, and publish either the safe command or a fallback command.

### 3.10 Certificate Checking and Closed-Loop Feedback

The Lyapunov/ISS certificate is used as an online audit of whether the current step is consistent with practical boundedness. The certificate combines physical errors, lifted prediction error, actuator-efficiency degradation, link-quality degradation, and, when payload protection is active, a force-proxy term.

At each step, the controller evaluates a certificate margin. If the margin passes, the step is counted as certificate-consistent. If it fails, the execution layer does not simply continue normally. It can tighten constraints, project commands, contract reference progress, or enter C3 fallback. The theoretical result then uses two ingredients: passing steps provide a practical ISS-type decrease, and failing steps are allowed only if their growth is bounded and their density is low enough over long windows.

This logic is weaker than global asymptotic stability, but it matches the implemented controller. The paper therefore claims certificate-verified practical ISS and uniform ultimate boundedness in a compact operating region, not strict global stability.

### 3.11 Full Sampling-Period Logic

One sampling period can be described as follows.

First, the system receives vehicle states, payload-center feedback, connection errors, communication logs, and actuator-response information from the previous step.

Second, the upper layer updates the payload-center reference and constructs local path packets when needed. In high-curvature regions, the equivalent 4WS geometric prior shapes these local paths.

Third, the communication module evaluates link quality, delay, packet loss, and corrupted measurements. Delayed neighbor states are extrapolated with the Koopman predictor or a fallback rule.

Fourth, the online predictor constructs the enhanced observation, lifts it, and rolls out candidate future states through the stability-projected bilinear Koopman model.

Fifth, the MPC selects the active C-mode schedule and solves for a candidate control sequence. Link quality determines consensus trust and constraint margins. Curvature and force risk determine whether lateral priority or payload protection is active.

Sixth, the execution layer checks actuator-efficiency estimates, FDI/FTC flags, command feasibility, and certificate margins. If necessary, it projects the command, redistributes vehicle roles, tightens constraints, or switches to fallback.

Seventh, the safe command is published to the vehicle-payload system. The resulting states, errors, force proxies, constraints, and certificate quantities are logged and fed into the next sampling period.

This sequence explains the relationship among the modules. Koopman learning supplies prediction, communication quality supplies trust and margins, MPC supplies constrained optimization, FDI/FTC supplies degraded execution protection, the certificate supplies boundedness auditing, and feedback logs close the loop.

## 4. Stability Certificate and Practical Boundedness Draft

The stability analysis is framed as a practical boundedness result. It does not claim global asymptotic stability of the true nonlinear vehicle-payload system. Instead, it shows that, under compact operating conditions, bounded residuals, bounded communication disturbances, and feasible fallback commands, the combined physical and lifted errors remain practically input-to-state stable and uniformly ultimately bounded.

The proof follows the implemented certificate logic. On certificate-passing steps, the augmented certificate decreases up to terms caused by model disturbance, communication degradation, delay, residual error, and changes in the payload-protection switch. The state-dependent part of the Koopman residual is absorbed through a small-gain condition. The input-aware spectral projection prevents the lifted predictor from amplifying errors inside the audited input envelope.

On certificate-failing steps, monotone decrease is not assumed. Instead, a bounded-growth condition is required. This is essential because a finite number of failures alone would not prevent unbounded growth if each failure could arbitrarily increase the certificate. With bounded failure growth and sufficiently low failure density over long windows, the passing-step contraction dominates the failing-step growth on average.

The final result is an ultimate bound depending on constant residual terms, model disturbances, network-quality degradation, delay, payload-protection switching variation, and fallback-growth constants. This result is consistent with the experimental certificate statistics: some scenarios have short negative margin transients, but the controller remains within the practical boundedness regime when fallback and average contraction conditions hold.

## 5. Experimental Results and Analysis Draft

The experiments are organized to match the method modules.

The first group examines Koopman learning and projection. The bilinear predictor slightly improves one-step RMSE relative to a linear model, while the projected bilinear predictor keeps comparable prediction accuracy. The more important result is that input-aware spectral projection reduces the sampled effective spectral radius from above one to below one. This supports the interpretation of IRSP as an amplification-risk audit rather than a pure prediction-accuracy improvement.

The second group studies closed-loop Koopman variants. The raw six-dimensional linear Koopman model performs poorly because it does not represent curvature, connection geometry, communication quality, or fault context. AKE-style linear and unprojected bilinear variants can have lower mean RMSE in some single-seed cases, but the current projected bilinear model is more conservative and more suitable for certificate-audited MPC.

The communication diagnostic shows that the controller responds to delay, packet loss, and link-quality degradation through consensus blending, constraint tightening, command-dispersion suppression, and protective-mode activation. This demonstrates that network degradation enters the control loop structurally rather than as unmodeled noise.

The FDI/FTC diagnostic shows that fault activation produces controller-side fault flags, FTC reallocation, and changes in vehicle-level command decomposition. The certificate continues to be logged through this transition. This confirms that degradation signals are integrated into the execution layer rather than evaluated only after the experiment.

The main paired comparison shows that NR-KDCC and AKE-M both complete the mixed fault/noise and high communication noise scenarios. The differentiating metrics are lateral RMSE and maximum connection utilization. Under mixed fault/noise, NR-KDCC reduces lateral RMSE from 0.0453 to 0.0408 and maximum connection utilization from 0.2999 to 0.0513. Under high communication noise, it reduces lateral RMSE from 0.0519 to 0.0424 and maximum connection utilization from 0.3757 to 0.0452. The force peak is higher than AKE-M in these main scenarios, so force is treated as a trade-off audit rather than as a primary superiority claim.

The speed-sensitivity study shows that the method works well at 2 m/s and 5 m/s, but longitudinal phase error becomes dominant at 10 m/s and all methods fail at 15 m/s. The high-speed cases are therefore boundary diagnostics, not performance claims.

The hairpin diagnostic separates tracking and force-protection effects. NR-KDCC-HC greatly improves lateral tracking relative to degraded AKE-M, but increases short-window force peak. Full NR-KDCC activates payload protection and lowers maximum connection utilization and force peak, but introduces more longitudinal lag and a local lateral-error excursion. This supports the claimed tracking-force trade-off.

The core ablation shows that removing communication awareness causes the largest degradation in connection utilization. Removing PPC protection causes full-path failure under mixed fault/noise, and ZOH-cons fails under the communication-stress scenarios. These results identify link-quality-aware consensus MPC and constraint tightening as the dominant modules.

The certificate statistics show full-path completion across the reported 5 m/s sine scenarios, but certificate-ok ratios and minimum margins vary by scenario. This matches the theoretical framing: the controller is supported by practical ISS/UUB with finite-density failures and bounded fallback growth, not by a strict global stability claim.

## 6. Discussion and Conclusion Draft

NR-KDCC improves network-degraded cooperative payload transport mainly by combining prediction, communication awareness, and constraint scheduling in one MPC loop. The Koopman predictor alone is not the central claim. Its value appears when it is used together with link-quality-aware neighbor prediction, consensus weighting, connection constraints, force-risk auditing, FDI/FTC execution protection, and certificate-triggered fallback.

The strongest evidence is the reduction in lateral tracking error and connection-constraint utilization under mixed fault/noise and high communication noise. These improvements show that link quality should be embedded directly in the optimizer. The ablation study confirms this point, because removing communication awareness sharply increases connection utilization even when the task is still completed.

The method also has clear limits. Force-related quantities are trade-off metrics. In high curvature, lateral-priority control can improve path tracking while increasing force peaks. Payload protection can reduce force and connection excitation, but it may sacrifice longitudinal synchronization and local tracking. High-speed operation is also not fully solved; longitudinal phase error becomes dominant at higher speeds, and 15 m/s is treated as a failure-mode audit.

The main conclusion is that network-resilient cooperative transport cannot be achieved by adding Koopman prediction alone. The learned predictor must be connected to communication quality, connection geometry, actuator degradation, payload-force risk, and certificate-based execution. NR-KDCC provides one such integrated structure and demonstrates its benefits under communication and fault degradation.

## One-Paragraph Summary for Presentation

This paper proposes NR-KDCC for four-vehicle rigid-payload cooperative transport under communication delay/dropout, high communication noise, actuator degradation, and high-curvature paths. The method first learns a bilinear Koopman predictor from degraded transport data and then applies input-aware spectral projection to limit prediction-error amplification in the MPC horizon. Online, the predictor is embedded in a link-quality-aware consensus MPC that adjusts neighbor trust, constraint tightening, delay compensation, and protection modes according to communication quality, curvature, connection geometry, fault state, and certificate margins. The execution layer further applies FDI/FTC, bounded role scheduling, command projection, and fallback before publishing safe commands. Experiments show improved lateral tracking and lower connection-constraint utilization relative to task-aligned AKE-M baselines, while hairpin diagnostics clarify the trade-off between high-curvature tracking and payload-force protection.

