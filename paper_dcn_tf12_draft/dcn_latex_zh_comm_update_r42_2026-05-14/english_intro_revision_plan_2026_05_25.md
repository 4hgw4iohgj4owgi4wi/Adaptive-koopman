# English Introduction Revision Plan, 2026-05-25

## 0. Scope

Target source, if approved:

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\dcn_latex_zh_comm_update_r42_2026-05-14\manuscript_en_intro_litupdate_keeprefs_nocover_3contrib_abs_nolabel_2026_05_22.tex`

This plan does not modify the manuscript. It only specifies the edits I will make after approval.

Planned output after approval:

`manuscript_en_intro_revised_2026_05_25.tex`

The Chinese source and Chinese PDF will not be touched. In the English source, this pass will modify only the English article shell, abstract, keywords, and Introduction block. I will not translate Section 2 onward in this pass, because the user asked to revise the Introduction first.

## 1. Revision Principles

1. Make the English file look like an English submission at first inspection.
2. Reduce the abstract from a module list into a problem-method-evidence paragraph.
3. Keep all claims bounded by the existing evidence in the manuscript.
4. State the baseline fairly: Singh et al.'s adaptive Koopman embedding is not a four-vehicle network-degraded cooperative-transport method, so the paper uses a task-aligned AKE-M baseline rather than claiming a direct reproduction of all original AKE experiments.
5. Make contributions active and method-level: use "This paper proposes/develops/establishes", not "is used to".
6. Narrow Contribution 2 so it is a unified MPC mechanism, not a loose collection of 4WS, FDI/FTC, payload protection, fallback, and communication handling.
7. Expand abbreviations at first use in the English front matter and Introduction.
8. Replace Chinese-influenced terms with standard control-paper wording.

## 2. English-Shell Cleanup Before the Introduction

These edits are needed because the English PDF currently still presents Chinese metadata and labels before the Introduction.

### 2.1 Running Author and Header

Current:

```tex
\runauth{作者姓名}
\fancyhead[ER]{\em \footnotesize 作者姓名}
```

Planned:

```tex
\runauth{Author Name}
\fancyhead[ER]{\em \footnotesize Author Name}
```

Reason: keep placeholders, but make them English. I will not invent real author names or affiliations.

### 2.2 Figure, Table, Reference, Abstract, Keyword, and Theorem Labels

Current:

```tex
\captionsetup[figure]{labelfont={scriptsize,bf},name={图},labelsep=period,font={scriptsize},skip=2pt}
\captionsetup[table]{labelfont={scriptsize,bf},name={表},labelsep=newline,singlelinecheck=false,font={scriptsize},skip=2pt}
\renewcommand{\refname}{参考文献}
\noindent\unskip\textbf{摘要}
\noindent\textit{关键词：}
\newtheorem{assumption}{假设}
\newtheorem{theorem}{定理}
\newtheorem{remark}{注}
```

Planned:

```tex
\captionsetup[figure]{labelfont={scriptsize,bf},name={Fig.},labelsep=period,font={scriptsize},skip=2pt}
\captionsetup[table]{labelfont={scriptsize,bf},name={Table},labelsep=newline,singlelinecheck=false,font={scriptsize},skip=2pt}
\renewcommand{\refname}{References}
\noindent\unskip\textbf{Abstract}
\noindent\textit{Keywords:}
\newtheorem{assumption}{Assumption}
\newtheorem{theorem}{Theorem}
\newtheorem{remark}{Remark}
```

Reason: the English PDF should not display Chinese article-shell labels. This is not a content rewrite; it is submission-format cleanup.

### 2.3 Method Chinese Name Macro

Current:

```tex
\newcommand{\MethodCN}{网络韧性 Koopman-时延一致性协同运输控制}
```

Planned:

```tex
\newcommand{\MethodCN}{Network-resilient Koopman delay-compensated consensus cooperative transport control}
```

Reason: the English source should not carry a Chinese expansion if the macro is later printed. The method abbreviation `\Method{}` remains unchanged as `NR-KDCC`.

### 2.4 Title

Current:

```tex
{\LARGE 基于双线性 Koopman 学习与时延补偿一致性模型预测控制的网络韧性协同运输控制}
```

Planned:

```tex
{\LARGE Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC}
```

Reason: use the established English working title, keep `MPC` because it is a standard title-level abbreviation, and avoid a literal Chinese-style "based on..." title.

### 2.5 Author and Affiliation Placeholders

Current:

```tex
\author[]{\leftline{作者姓名$^{a,*}$}}
\address{\leftline{$^a$单位名称，城市，邮编，国家}}
```

Planned:

```tex
\author[]{\leftline{Author Name$^{a,*}$}}
\address{\leftline{$^a$Affiliation, City, Postal Code, Country}}
```

Reason: keep placeholders instead of fabricating personal information, but remove Chinese from the English version.

### 2.6 Keywords

Current:

```tex
协同运输 \sep Koopman 算子 \sep 双线性系统 \sep 模型预测控制 \sep 网络时延 \sep 丢包 \sep 容错控制 \sep Lyapunov 稳定性
```

Planned:

```tex
Cooperative transport \sep Koopman operator \sep bilinear prediction model \sep model predictive control \sep networked control \sep communication delay and packet loss \sep fault-tolerant control \sep Lyapunov stability certificate
```

Reason: make the keywords English and aligned with the revised Introduction. I will use "bilinear prediction model" rather than "bilinear system" because the paper's bilinear component is the learned lifted predictor.

### 2.7 Bibliography Titles

Observed from `core_references_round10.bib`: a CJK scan found no Chinese bibliographic titles in that file. The visible Chinese bibliography issue in this source is the heading `参考文献`, not the BibTeX titles.

Plan:

1. Change `\refname` to `References`.
2. After compilation, inspect the generated PDF/bbl for Chinese reference titles.
3. If Chinese titles are found in generated bibliography entries, translate only those BibTeX `title` fields and preserve the citation keys.

## 3. Abstract Rewrite Plan

The current abstract is one dense paragraph. I will keep it as one LaTeX abstract paragraph unless the template allows multi-sentence line breaks without visual issues. The new abstract will have five controlled sentences.

### Abstract Sentence 1: Problem Definition

Current:

```text
Four-vehicle rigid-payload cooperative transport is prone to coupled conflicts among team-center tracking, adjacent-distance preservation, and payload safety when high-curvature paths, communication delay/dropout, and actuator degradation occur simultaneously.
```

Planned:

```text
Four-vehicle rigid-payload cooperative transport couples centroid tracking, inter-vehicle distance regulation, and payload-force safety, and these objectives become difficult to reconcile when high-curvature references, communication delay/dropout, and actuator degradation occur simultaneously.
```

Reason: replace "team-center tracking" with "centroid tracking" and "adjacent-distance preservation" with "inter-vehicle distance regulation"; make the conflict read as a control objective conflict, not a vague "coupled conflict".

### Abstract Sentence 2: Method, With Fewer Modules

Current:

```text
To address predictive control under network degradation, this paper develops a network-resilient Koopman delay-compensated consensus control framework (\Method{}) that integrates an input-aware stability-projected bilinear Koopman predictor, communication-quality-aware consensus MPC, upper-layer equivalent four-wheel-steering local-path generation, FDI/FTC, and certificate-triggered degraded fallback.
```

Planned:

```text
This paper proposes a network-resilient Koopman delay-compensated consensus control framework (\Method{}) in which a stability-projected bilinear Koopman predictor is embedded in a communication-quality-aware model predictive control (MPC) loop with delay compensation, constraint tightening, and certificate-triggered fallback.
```

Reason: remove the "all modules in one sentence" problem. First use of MPC is expanded. 4WS and FDI/FTC will move to the Introduction/method explanation rather than the abstract core sentence.

### Abstract Sentence 3: Main Paired Comparison

Current:

```text
In paired $n=20$ tests, compared with a task-aligned baseline derived from the adaptive Koopman embedding method of Singh et al.\cite{singh2025adaptiveKoopman}, \Method{} reduces the lateral RMSE from 0.0453 to 0.0408 and the maximum connection utilization from 0.2999 to 0.0513 in the mixed fault/noise scenario; it also reduces the lateral RMSE from 0.0519 to 0.0424 and the maximum connection utilization from 0.3757 to 0.0452 in the high-communication-noise scenario.
```

Planned:

```text
Against a task-aligned adaptive Koopman embedding baseline derived from Singh et al.~\cite{singh2025adaptiveKoopman}, paired $n=20$ tests show that \Method{} reduces lateral root-mean-square error (RMSE) from 0.0453 to 0.0408 and maximum connection utilization from 0.2999 to 0.0513 under mixed fault/noise, and from 0.0519 to 0.0424 and 0.3757 to 0.0452, respectively, under high communication noise.
```

Reason: keep the data, expand RMSE at first use, and make clear that this is a task-aligned AKE baseline. I will not overclaim that Singh et al.'s original paper directly solved this task.

### Abstract Sentence 4: Hairpin Result Without Baseline Misreading

Current:

```text
In the 5 m/s high-delay hairpin test, the high-curvature disturbance-rejection branch reduces the team-center lateral RMSE from 0.2989 to 0.0851, while the payload-protection branch reduces the peak resultant force from 15487.33 N to 8874.04 N.
```

Planned:

```text
In the 5 m/s high-delay hairpin test, the high-curvature branch reduces centroid lateral RMSE from 0.2989 to 0.0851 relative to the degraded AKE-M baseline, whereas enabling the payload-protection branch reduces the peak resultant payload force from 15487.33 N for \MethodHC{} to 8874.04 N for the full \Method{} controller.
```

Reason: remove the ambiguity that payload force is better than the AKE-degraded baseline. The table shows `\AKEdeg{}` has 5544.45 N, `\MethodHC{}` has 15487.33 N, and full `\Method{}` has 8874.04 N. The abstract must present payload protection as an internal branch improvement from `\MethodHC{}` to full `\Method{}`.

### Abstract Sentence 5: Mechanism and Trade-Off

Current:

```text
These results show that the benefit of bilinear Koopman prediction becomes effective for network-degraded cooperative transport only when link quality, connection geometry, and payload-force risk are embedded into the MPC loop; activating payload protection trades a bounded increase in lateral error for a lower payload-force peak, revealing an objective trade-off between tracking accuracy and payload loading in the Koopman-MPC closed loop.
```

Planned:

```text
The results indicate that bilinear Koopman prediction translates into closed-loop benefits only when link quality, connection geometry, and payload-force risk are included in the MPC optimization; they also expose a safety-performance trade-off in which payload protection lowers force peaks at the cost of a bounded increase in lateral tracking error.
```

Reason: replace "becomes effective" and "payload loading" with more natural control-paper wording.

## 4. Introduction Paragraph-by-Paragraph Rewrite Plan

### Paragraph 1: General Path Tracking and Problem Opening

Current:

```text
Path tracking is a fundamental task in autonomous vehicles and mobile robots. Classical controllers, such as pure pursuit, Stanley control, linear quadratic regulation (LQR), and preview-based control, are attractive because of their simple structure and low computational cost. However, their performance usually relies on kinematic approximations, local linearization, or fixed-gain tuning. In four-vehicle rigid-payload transport, high-curvature paths amplify lateral-longitudinal coupling, actuator constraints, and connection errors. High-speed operation further increases control sensitivity, but it is treated in this paper as a stress-test condition rather than the main claimed advantage.
```

Planned:

```text
Path tracking is a fundamental task in autonomous vehicles and mobile robots. Classical controllers, including pure pursuit, Stanley control, linear quadratic regulation (LQR), and preview-based control, remain attractive because of their simple structure and low computational cost. Their performance, however, usually depends on kinematic approximations, local linearization, or fixed-gain tuning. In rigid-payload transport by four unmanned vehicles, path curvature couples centroid tracking, vehicle-level steering and acceleration limits, inter-vehicle connection errors, and payload-force constraints. This coupling makes the problem different from single-vehicle path tracking or ordinary platoon spacing control.
```

Reason: remove the first high-speed disclaimer here. The high-speed boundary will appear only once later. Replace "four-vehicle rigid-payload transport" with a more natural phrase.

### Paragraph 2: Communication-Degraded MPC Gap

Current:

```text
Model predictive control (MPC) provides a systematic way to handle tracking errors, input constraints, and safety bounds over a finite prediction horizon. Distributed MPC, consensus control, and leader-follower strategies have been widely used to maintain relative formations and inter-vehicle distances. Nevertheless, many cooperative tracking methods assume reliable communication or treat delay, packet loss, and biased information as external bounded disturbances. This assumption is restrictive for cooperative payload transport, because communication degradation directly affects relative-distance estimation, team-center error feedback, upper-layer reference delivery, lower-layer command reception, and payload-force distribution. Therefore, communication quality should enter the consensus weights, neighbor-state extrapolation, constraint tightening, and safety fallback logic, instead of being used only as an external simulation disturbance.
```

Planned:

```text
Model predictive control (MPC) provides a systematic way to handle tracking errors, input constraints, and safety bounds over a finite prediction horizon. Distributed MPC (DMPC), consensus control, and leader-follower strategies have been widely used to maintain relative formations and inter-vehicle distances. Many cooperative tracking methods, however, still assume reliable communication or model delay, packet loss, and biased information only as bounded external disturbances. This treatment is restrictive for cooperative payload transport, where communication degradation changes neighbor-state extrapolation, centroid-error feedback, upper-layer reference delivery, lower-layer command reception, and payload-force distribution. Hence, link quality should be treated as a scheduling variable in consensus weights, constraint tightening, and fallback decisions rather than as a disturbance added only during simulation.
```

Reason: expand DMPC at first use and sharpen the gap: communication quality must enter the controller, not only the scenario generator.

### Paragraph 3: Koopman Literature and Baseline Fairness

Current:

```text
When accurate first-principle models are difficult to obtain, data-driven modeling provides an alternative route for vehicle control. Neural networks and reinforcement-learning-based black-box models can approximate complex nonlinear dynamics, but they are often difficult to embed into constrained optimization, stability analysis, and safety certification. Koopman learning lifts nonlinear dynamics into a high-dimensional observable space, where the lifted dynamics can be approximated by a linear predictor, thus providing a control-friendly bridge between data-driven modeling and MPC\cite{brunton2016koopmanControl,korda2018koopmanMpc,xiao2022deepKoopmanVehicle,joglekar2023koopmanExperimental}. Recent Koopman vehicle-control studies have developed EDMD, deep Koopman models, stochastic MPC, safety command governors, physics-informed adaptive updates, robust path tracking, and approximation-error bounds\cite{kim2025ksmpc,chen2024koopmanSafetyGovernor,wang2026deepKoopmanRobustTracking,zhang2025physicsInformedAdaptiveKoopman,chen2024esoDeepKoopman,philipp2023koopmanErrorBounds,cibulka2021koopmanVehicleMpc}. The adaptive Koopman embedding (AKE) method of Singh et al. further improves robustness by correcting lifted-state prediction errors online\cite{singh2025adaptiveKoopman}. However, a purely linear lifted model has limited ability to represent input-state coupling caused by steering, longitudinal acceleration, communication quality, and connection states. For this reason, this paper adopts a bilinear Koopman structure, which preserves the MPC-compatible prediction form while explicitly retaining the multiplicative coupling between control inputs and lifted states.
```

Planned:

```text
When accurate first-principle models are difficult to obtain, data-driven modeling provides an alternative route for vehicle control. Neural networks and reinforcement-learning models can approximate complex nonlinear dynamics, but black-box predictors are difficult to embed in constrained optimization, stability analysis, and safety certification. Koopman learning lifts nonlinear dynamics into an observable space in which the lifted dynamics can be approximated by a predictor suitable for MPC\cite{brunton2016koopmanControl,korda2018koopmanMpc,xiao2022deepKoopmanVehicle,joglekar2023koopmanExperimental}. Recent studies have extended this idea through extended dynamic mode decomposition (EDMD), deep Koopman models, stochastic MPC, safety command governors, physics-informed adaptive updates, robust path tracking, and approximation-error bounds\cite{kim2025ksmpc,chen2024koopmanSafetyGovernor,wang2026deepKoopmanRobustTracking,zhang2025physicsInformedAdaptiveKoopman,chen2024esoDeepKoopman,philipp2023koopmanErrorBounds,cibulka2021koopmanVehicleMpc}. The adaptive Koopman embedding (AKE) method of Singh et al. corrects lifted-state prediction errors online and provides the mechanism from which the task-aligned AKE-M baseline in this paper is constructed\cite{singh2025adaptiveKoopman}. Because the original AKE formulation does not directly address four-vehicle network-degraded payload transport, this paper compares against a task-aligned AKE-M controller rather than claiming a one-to-one reproduction of the original experiments. The remaining modeling gap is that a purely linear lifted predictor cannot explicitly represent input-state couplings induced by steering, longitudinal acceleration, link quality, and connection geometry. We therefore use a bilinear Koopman predictor that preserves the MPC-compatible lifted form while retaining multiplicative coupling between control inputs and lifted states.
```

Reason: explicitly protects baseline fairness, expands EDMD, and turns the paragraph into a direct bridge from Koopman literature to this paper's bilinear predictor.

### Paragraph 4: Stability Projection

Current:

```text
Finite-dimensional Koopman models inevitably contain approximation errors. Under high-curvature maneuvers or degraded communication, such errors may be amplified by predictive feedback, constraint tightening, and reference replanning. Therefore, the proposed method does not rely on the learned predictor as an unconditional black-box model. A stability projection module is introduced to audit and rescale the effective Koopman operator $A_{\mathrm{eff}}(u)$ that is actually used by the controller. Its purpose is not to claim perfect long-horizon rollout accuracy, but to keep the closed-loop prediction model within a numerically stable and certifiable region, so that the subsequent MPC, safety filter, and fallback logic have a bounded model basis.
```

Planned:

```text
Finite-dimensional Koopman models inevitably contain approximation errors. Under high-curvature maneuvers or degraded communication, these errors may be amplified by predictive feedback, constraint tightening, and reference replanning. The proposed controller therefore does not treat the learned predictor as an unconditional black box. Instead, an input-aware stability projection audits and rescales the effective lifted operator $A_{\mathrm{eff}}(u)$ passed to the MPC optimizer. The purpose is not to guarantee perfect long-horizon rollout accuracy, but to keep the controller-side prediction model in a numerically stable and certifiable region for subsequent MPC, safety filtering, and fallback decisions.
```

Reason: replace "controller-used" with "passed to the MPC optimizer" and avoid overstating stability.

### Paragraph 5: Literature Review Restructuring

Current:

```text
Cooperative transport studies have covered formation control, distributed optimization, nonholonomic constraints, connector mechanisms, and learning-based task decisions. Recent works have addressed multi-robot communication for cooperative transport, differential-drive cooperative transport, six-degree-of-freedom connector systems, heterogeneous multi-formation planning, embedded formation transport, and multi-objective reinforcement-learning-based transport\cite{an2023multiRobotCommTransport,cooperativeTransport2024ras,gong2023sixDofTransport,zhang2024heterogeneousTransport,embeddedFormationTransport2024cep,multiObjectiveTransport2024mechatronics,intelligentCollaborativeTransport2024}. In parallel, networked control and vehicular-network studies have investigated vehicular ad hoc networks, vehicular edge computing, quality-of-service constraints, Markov packet loss, denial-of-service attacks, communication interruption, stochastic delay, and latency mitigation\cite{tan2022mlVehicularDcn,zhao2025blockchainVanetDcn,wu2025drlVecDcn,bian2025markovPacketLossDMPC,dosDMPC2024isa,robustCommunicationLoss2025trb,bai2023robustLongitudinalDMPC,bao2024robustUkfMpc,networkLatencyCav2024sensors,dai2024networkedPredictiveControl}. Most existing work, however, focuses on spacing regulation, string stability, or single-vehicle trajectory tracking. It does not jointly incorporate team-center error, vehicle-level short-horizon paths, connection utilization, payload force, communication quality, and actuator faults into an auditable predictive-control loop for a four-vehicle rigid-payload system.
```

Planned:

```text
A second line of related work concerns cooperative object transport. Existing studies cover formation control, distributed optimization, nonholonomic constraints, connector mechanisms, heterogeneous planning, embedded formation transport, and learning-based task decisions\cite{an2023multiRobotCommTransport,cooperativeTransport2024ras,gong2023sixDofTransport,zhang2024heterogeneousTransport,embeddedFormationTransport2024cep,multiObjectiveTransport2024mechatronics,intelligentCollaborativeTransport2024}. These methods clarify how multiple robots share object-motion tasks, but they usually do not combine learned prediction, communication-delay compensation, actuator-degradation handling, and payload-force monitoring in one MPC loop. A third related line is networked and vehicular control, where vehicular ad hoc networks (VANETs), quality-of-service (QoS) constraints, Markov packet loss, denial-of-service (DoS) attacks, stochastic delay, and latency mitigation have been studied\cite{tan2022mlVehicularDcn,zhao2025blockchainVanetDcn,wu2025drlVecDcn,bian2025markovPacketLossDMPC,dosDMPC2024isa,robustCommunicationLoss2025trb,bai2023robustLongitudinalDMPC,bao2024robustUkfMpc,networkLatencyCav2024sensors,dai2024networkedPredictiveControl}. However, these studies mainly address spacing regulation, string stability, resource allocation, or single-vehicle trajectory tracking. The gap targeted here is an auditable predictive-control loop that simultaneously accounts for centroid error, vehicle-level short-horizon references, inter-vehicle connection utilization, payload force, link quality, and actuator faults in a four-vehicle rigid-payload system.
```

Reason: reduce "reference pile" feeling by assigning literature to two lines and ending with a clear gap. Expand VANET, QoS, and DoS at first use.

### Paragraph 6: Robust MPC, Fault Handling, and Final Problem Statement

Current:

```text
Robust MPC, tube/convex robust DMPC, learning-supported MPC, and actuator FDI/FTC provide useful foundations for uncertainty handling, constraint tightening, and fault redistribution\cite{mayne2000constrainedMpc,mayne2005robustMpc,convexRobustDMPC2025ejc,gasparino2023nnMpcUncertainty,liu2024adaptiveFtcSbw,xu2024fdFtcSteering}. This paper uses these ideas for feasibility preservation, degraded protection, and fault-tolerant correction, but the target is not single-vehicle stabilization or platoon string stability. Instead, it focuses on cooperative payload safety under the coupled effects of high curvature and communication disturbance. This paper proposes a network-resilient Koopman delay-compensated consensus control framework, termed \Method{}; high-speed simulations are included only as sensitivity and stress tests, not as the main performance claim.
```

Planned:

```text
Robust MPC, tube and convex robust DMPC, learning-supported MPC, and fault detection and isolation/fault-tolerant control (FDI/FTC) provide foundations for uncertainty handling, constraint tightening, and actuator-fault redistribution\cite{mayne2000constrainedMpc,mayne2005robustMpc,convexRobustDMPC2025ejc,gasparino2023nnMpcUncertainty,liu2024adaptiveFtcSbw,xu2024fdFtcSteering}. This paper uses these foundations for feasibility preservation, degraded protection, and fault-tolerant correction, but its target is neither single-vehicle stabilization nor platoon string stability. It focuses on cooperative payload safety under the coupled effects of high curvature, network degradation, and actuator degradation. High-speed simulations are retained as sensitivity and stress tests rather than as the main performance claim.
```

Reason: expand FDI/FTC at first use and keep the high-speed disclaimer only once, after the problem scope has been defined.

## 5. Contribution Rewrite Plan

Current lead-in:

```text
The main contributions are summarized as follows.
```

Planned lead-in:

```text
The main contributions of this paper are as follows.
```

Reason: standard active paper phrasing.

### Contribution 1

Current:

```text
\item \textbf{An input-aware stability-projected bilinear Koopman learner is used to improve prediction for network-degraded cooperative transport.} Vehicle states, team-center errors, connection geometry, and communication/fault indicators are included in the lifted observation, while the bilinear terms explicitly represent the multiplicative coupling between steering, longitudinal acceleration, and lifted states. The stability projection further constrains the controller-used $A_{\mathrm{eff}}(u)$, thereby reducing prediction-drift risk under high curvature and degraded communication.
```

Planned:

```text
\item \textbf{This paper proposes an input-aware stability-projected bilinear Koopman learner for network-degraded cooperative transport.} The lifted observation includes vehicle states, centroid errors, connection geometry, and communication/fault indicators, while bilinear terms encode the multiplicative coupling between steering, longitudinal acceleration, and lifted states. The input-aware stability projection constrains the effective operator $A_{\mathrm{eff}}(u)$ passed to MPC, reducing prediction-drift risk under high curvature and degraded communication.
```

Reason: active contribution statement; "centroid errors" and "passed to MPC" are more natural than "team-center errors" and "controller-used".

### Contribution 2

Current:

```text
\item \textbf{A risk-aware mode-reconfigurable Koopman-MPC scheme is used to resolve the priority conflict among communication disturbance rejection, high-curvature tracking, and payload protection.} Under one bilinear prediction model, the controller reconfigures weights, constraints, consensus compensation, and fallback candidates according to communication quality, path curvature, connection utilization, payload-force risk, and certificate margins. Upper-layer equivalent four-wheel-steering local-path generation, adjacent-distance regulation, and FDI/FTC are integrated so that nominal tracking, network resilience, high-curvature payload protection, and safety fallback are handled within a unified loop.
```

Planned:

```text
\item \textbf{This paper develops a risk-aware Koopman-MPC loop that schedules communication compensation, connection constraints, and payload-force protection within one controller.} The controller reconfigures weights, constraint tightening, neighbor-state extrapolation, and fallback candidates according to link quality, path curvature, connection utilization, payload-force risk, and certificate margins. Four-wheel-steering (4WS) local-path publication and FDI/FTC-based execution-layer correction are treated as supporting mechanisms, so the contribution remains a unified communication- and risk-aware MPC framework rather than a collection of independent modules.
```

Reason: avoid "all-in-one module pile". This keeps 4WS and FDI/FTC in the contribution but demotes them to supporting mechanisms.

### Contribution 3

Current:

```text
\item \textbf{A Lyapunov/ISS certificate and task-aligned experiments are used to verify closed-loop safety bounds and identify the performance source.} The analysis incorporates Koopman residuals, communication disturbances, actuator degradation, stability projection, constraint tightening, and safety fallback into a unified boundedness argument, leading to practical input-to-state boundedness/uniform ultimate boundedness (UUB). The experiments, including training loss, short-window prediction, dimension ablation, communication/delay diagnostics, FDI/FTC timelines, baseline comparison, speed sensitivity, and 5 m/s high-curvature hairpin tests, support the operating boundaries of the learning, network-resilience, and payload-protection modules.
```

Planned:

```text
\item \textbf{This paper establishes a Lyapunov/input-to-state stability (ISS) certificate and a task-aligned experimental protocol for identifying the source of closed-loop performance.} The analysis accounts for Koopman residuals, communication disturbances, actuator degradation, stability projection, constraint tightening, and fallback actions, leading to practical input-to-state boundedness and uniform ultimate boundedness (UUB) under the stated operating conditions. The experiments combine training loss, short-window prediction, dimension ablation, communication/delay diagnostics, FDI/FTC timelines, baseline comparison, speed sensitivity, and 5 m/s high-curvature hairpin tests to delimit the learning, network-resilience, and payload-protection modules.
```

Reason: expand ISS at first use, avoid implying global stability, and state that experiments delimit module boundaries rather than simply "verify everything".

## 6. Terminology Replacement Map

I will apply these replacements inside the abstract and Introduction only:

| Current wording | Planned wording | Reason |
|---|---|---|
| team-center tracking | centroid tracking | Standard multi-robot/control wording |
| team-center errors | centroid errors | Same |
| adjacent-distance preservation | inter-vehicle distance regulation | More natural and precise |
| adjacent-distance regulation | inter-vehicle distance regulation | Same |
| controller-used $A_{\mathrm{eff}}(u)$ | effective operator $A_{\mathrm{eff}}(u)$ passed to MPC | Avoid Chinese-style compound |
| becomes effective for network-degraded cooperative transport | translates into closed-loop benefits under network degradation | More idiomatic |
| payload loading | payload-force safety / payload-force peak | Avoid ambiguity |
| high-speed operation ... stress-test | keep once as "High-speed simulations are retained as sensitivity and stress tests" | Avoid repeated defensive wording |

## 7. Abbreviation First-Use Checklist

I will check and enforce these first-use forms in the English front matter and Introduction:

| Abbreviation | Planned first-use form |
|---|---|
| LQR | linear quadratic regulation (LQR) |
| MPC | model predictive control (MPC) |
| DMPC | distributed MPC (DMPC) |
| EDMD | extended dynamic mode decomposition (EDMD) |
| AKE | adaptive Koopman embedding (AKE) |
| RMSE | root-mean-square error (RMSE) |
| VANET | vehicular ad hoc network (VANET) |
| QoS | quality of service (QoS) |
| DoS | denial of service (DoS) |
| FDI/FTC | fault detection and isolation/fault-tolerant control (FDI/FTC) |
| 4WS | four-wheel-steering (4WS) |
| ISS | input-to-state stability (ISS) |
| UUB | uniform ultimate boundedness (UUB) |

## 8. Claim Boundaries I Will Preserve

1. The paper will not claim that the full method always lowers payload force relative to `\AKEdeg{}`. The hairpin force claim will be stated as `\MethodHC{}` to full `\Method{}` improvement.
2. The paper will not claim global asymptotic stability. It will use practical input-to-state boundedness/UUB under stated operating conditions.
3. The paper will not present high-speed performance as the primary novelty.
4. The paper will not claim a direct apples-to-apples reproduction of Singh et al.'s original task. It will state that AKE-M is task-aligned because the original AKE does not directly solve four-vehicle network-degraded cooperative payload transport.
5. The literature review will support exactly three method lines: bilinear/stability-projected Koopman learning, communication-aware Koopman-MPC, and payload/fault/safety certification.

## 9. Implementation Plan After Approval

1. Copy the English source to `manuscript_en_intro_revised_2026_05_25.tex`.
2. Apply the English-shell cleanup in Section 2.
3. Replace the abstract using the five-sentence plan in Section 3.
4. Replace Introduction paragraphs 1-6 and the contribution list using Sections 4-5.
5. Run a CJK scan on the revised English source.
   - Expected remaining Chinese after this pass: Section 2 onward, because this pass does not translate the body.
   - Unexpected Chinese before `\section{Introduction}` and inside lines corresponding to the revised Introduction should be zero, except for protected file paths/comments if any.
6. Run an abbreviation-first-use scan for the checklist in Section 7.
7. Compile a new PDF with XeLaTeX using a fresh job name to avoid overwriting the current PDF.
8. Check the LaTeX log for hard errors, undefined references, and undefined citations.
9. Report the revised `.tex`, compiled `.pdf`, and any residual issues.

## 10. Approval Questions

Please approve or reject these three decisions before I edit:

1. Should I apply the English-shell cleanup in Section 2 together with the Introduction revision? My recommendation is yes, because the English PDF currently fails an immediate language-completeness check before the Introduction.
2. Should the title be exactly `Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC`? My recommendation is yes, because it matches the established manuscript direction and is concise.
3. Should I leave Section 2 onward untranslated in this pass? My recommendation is yes, because the current request is to revise the Introduction first and keep the Chinese version untouched.
