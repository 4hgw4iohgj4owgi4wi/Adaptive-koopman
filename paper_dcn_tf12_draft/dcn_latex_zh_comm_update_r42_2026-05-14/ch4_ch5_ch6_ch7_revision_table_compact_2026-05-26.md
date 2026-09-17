# Ch4--Ch7 Compact Proposed Revision Table

Target source: `manuscript_en_ch4_reviewfix_2026_05_26.tex`

Review source: `ch4_ch5_ch6_ch7_review_2026-05-26.md`

Status: proposal only. No `.tex` manuscript text has been changed.

## Compression Rule

This version merges the previous 32 detailed rows into 14 edit packages. Each package keeps only the exact phrase to remove, the core replacement wording, and the reason for adoption.

## Compact Table

| ID | Priority | Scope | Remove / Replace | Compact Proposed Wording | Adopt? |
|---|---:|---|---|---|---|
| R01 | P1 | Ch4 proof closure | Replace `\alpha_c:=\alpha-c_w...` | `Let $\alpha_{\mathrm{cert}}>0$ denote the nominal certificate decrease rate before residual absorption, and assume $\alpha_c:=\alpha_{\mathrm{cert}}-c_w\bar w_\chi^2L_\chi^2>0$.` | Yes |
| R02 | P1 | Ch4 mode switching | Add after mode-comparability sentence | `The failure-growth constants $\rho_f$ and $c_f$ include the worst-case jump induced by $\rho_P$ and $c_P$.` | Yes |
| R03 | P1 | Ch4 IRSP boundary | Add after norm-certificate sentence | `Without the norm certificate, the boundedness claim is restricted to the sampled control envelope $\mathcal U_s$ used by the controller audit.` | Yes |
| R04 | P0 | Ch5 opening | Replace current lines 692--699 | `\section{Experimental Results and Analysis}` plus two short paragraphs: define \ZOHcons{}, PPC, noComm/noDelay/noIRSP/noPPC; then state paired statistics versus mechanism-oriented single-seed diagnostics. | Yes |
| R05 | P0 | Ch5 style cleanup | Replace repeated `客观结果是` | Use `Figure~... shows that ...` or `Table~... shows that ...`. | Yes |
| R06 | P0 | Ch5 style cleanup | Replace repeated `造成上述结果的原因是` | Use `This behavior is consistent with ...` or `These results indicate that ...`; avoid strong causality unless the mechanism is directly defined. | Yes |
| R07 | P0 | Ch5 internal words | Delete `最新`, `调参`, `回填`, `主证据`, `原实验`, `内部审稿材料`, `地板基线` | Use `diagnostic`, `reported separately`, `not merged into paired statistics`, `mechanism-oriented evidence`, `low-order ZOH consistency baseline`. | Yes |
| R08 | P1 | Training/Koopman evidence | Replace `该图用于证明...` | `The figure checks convergence and excludes obvious divergence; it does not serve as a formal closed-loop proof.` For IRSP: `IRSP is an amplification-risk audit, not a prediction-accuracy enhancement module.` | Yes |
| R09 | P1 | K1/K2/K3 ablation | Replace any “K3 全面最优” implication | `K3 should be interpreted as the most conservative and certifiable predictor, not as the predictor with the lowest mean RMSE in every scenario.` | Yes |
| R10 | P0 | FDI/FTC paragraph | Replace `全局控制模式进入 reconfigured FTC MPC` and `该图证明...` | `The FTC reallocation flag becomes active, producing nonzero steering/acceleration redistribution. The figure indicates that FDI/FTC and certificate monitoring are integrated into the closed loop, but it remains a single-run mechanism diagnostic.` | Yes |
| R11 | P1 | Certificate experiment | Replace `分模式证书与 ISS/UUB 保护逻辑一致` | `The mode-wise statistics are consistent with the certificate-verified practical ISS/UUB conditions in Section 4, rather than proving global stability.` | Yes |
| R12 | P1 | Main comparison and force | Add force boundary after main comparison | `The main comparison supports tracking and connection-utilization improvements. Force-related quantities are reported as trade-off audits and are not the primary superiority claim against \AKE{}.` | Yes |
| R13 | P1 | Speed and single-seed diagnostics | Replace high-speed positive framing | `The paired 15 m/s protocol remains a failure case. The same-initial-condition run is a failure-mode diagnostic. At 15 m/s, the improvement is marginal and should not be treated as robust performance evidence.` | Yes |
| R14 | P0 | Ch6--Ch7 structure | Merge `讨论` and `结论` | Use `\section{Discussion and Conclusion}`. Keep three short paragraphs: main evidence; limitations/trade-offs; conclusion/future work. | Yes |

## Short Replacement Blocks

### R04: Compressed Ch5 Opening

```latex
\section{Experimental Results and Analysis}

This section reports eleven experiments and diagnostics corresponding to the method modules in Sections 3 and 4. \ZOHcons{} denotes a low-order zero-order-hold (ZOH) consistency baseline used to expose degradation without learned prediction or network-aware protection. The ablation suffixes noComm, noDelay, noIRSP, and noPPC denote removal of communication-quality awareness, delay compensation, input-aware robust spectral projection, and the PPC guard, respectively.

Experiments 6, 10, and 11 use paired multi-seed statistics, and Experiment 7 uses paired speed-stress statistics. Experiments 2--5, 8, and 9 are mechanism-oriented or same-initial-condition diagnostics; they inspect process-level behavior and are not merged into the paired statistical comparisons.
```

### R14: Compressed Discussion and Conclusion

```latex
\section{Discussion and Conclusion}

\Method{} mainly improves lateral tracking and connection-constraint utilization under mixed fault/noise and high communication noise. The paired comparison and ablation results indicate that communication-aware consensus MPC is the dominant contributor, because link quality directly changes consensus weights, neighbor trust, and constraint tightening.

The results also delimit the claim. Force peaks are not uniformly lower than \AKE{} and are therefore treated as trade-off audits. High-speed tests expose longitudinal phase error, and same-initial-condition single-seed diagnostics are mechanism checks rather than replacements for paired statistics. The stability result is certificate-verified practical boundedness, not global asymptotic stability.

Overall, \Method{} supports network-aware cooperative transport with better tracking and connection control under degradation. Future work should rerun the updated diagnostic settings with multi-seed statistics, improve high-speed longitudinal phase control, and validate the payload-force proxy with richer load measurements or physical experiments.
```

## Recommended Minimal Selection

Apply: `R01--R04`, `R07`, `R10--R14`.

Reason: this removes the main proof ambiguity, internal-process wording, FTC mode inconsistency, over-strong stability wording, force overclaim risk, single-seed overclaim risk, and the weak Ch6/Ch7 structure.

## If Full English Ch5 Is Required

Apply all `R01--R14`, then run a second pass to translate table headers, row labels, and all figure/table captions into English.
