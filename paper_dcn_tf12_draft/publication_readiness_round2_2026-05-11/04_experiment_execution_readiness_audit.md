# Worker D: Experiment Execution and Figure Readiness Audit

审计范围：只读检查 `00_round2_task_tree.md`、`04_experiment_figure_ablation_plan.md`、现有图/数据目录、README、manifest 和 runner 参数；未修改代码，未移动图，未运行昂贵实验。结论按投稿前 P0 门槛给出，不把 smoke、cached 或历史 TF13 证据当作主文最终统计。

## 1. 总体结论

当前状态是“图形资产较完整，但最终投稿证据未闭合”。`tf14_paper_figures_20260510/figures` 已有一套可排版的 PNG/PDF/SVG 图，`tf14_remaining_experiments_20260509` 和 `tf14_final_gap_closure_20260509` 也能生成 E0/E2/E3/E7 机制图；但投稿主结论仍被以下 P0 项阻断：

| P0 阻断项 | 当前证据 | 投稿影响 |
|---|---|---|
| T1 baseline 未完全冻结到实验 runner | 当前 runner 有 `baseline`/`AKE-baseline` 名称，但未能确认其对应 `AKE-R/AKE-A/AKE-M` 之一 | 主文不能写“优于 uploaded AKE baseline” |
| 强制非 Koopman 网络控制 baseline 缺失 | 未发现 `Physical-model DMPC`、`physical MPC + ZOH consensus` 或 `ZOH consensus MPC` 的现成 final runner | 主闭环比较方法集不合格 |
| 主闭环 final seeds 未完成 | `tf14_remaining_manifest.json` 显示 `minimum_group_n=1`、`final_statistics_ready=false` | R0/R2/R3/R7 当前不能作为正文最终统计 |
| E1 Koopman fresh 多训练种子缺失 | gap closure README 明确 E1 使用 cached offline screening data | Koopman 学习优势只能作机制示意或补充，不能支撑主结论 |
| 通信 dose-response 和 topology recovery 未发现 final runner | 仅有历史 `N07_comm_noise_dose_response.png` 或计划项 | DCN 网络韧性主张缺最关键边界图 |
| Safety diagnostics 需要 final 无 NaN 导出 | 当前 E7 smoke 的 safety 字段无 NaN，但全表非 E7 行缺 force/corner/connection 字段，且 n=1 | 安全图需 E7/E3 final seeds 后才能入正文 |
| 6-8 张正文主图缺统一 provenance ledger | manifest 有源文件，但未统一记录 seed list、scenario、method set、CI、NaN 检查 | 主图编号前必须先冻结 ledger |

## 2. 当前已有图/数据目录清单与可用性判断

| 目录 | 只读观察 | 可用性判断 |
|---|---|---|
| `tf14_paper_figures_20260510/figures` | 72 个文件，24 个图各有 PNG/PDF/SVG；含 `fig00` 到 `fig14` 和 `figSxx` | 可作为排版候选层；其中性能类图仍需 final provenance、T1/非 Koopman 方法集和 n>=20/CI 通过后才能进入正文主结论 |
| `tf14_paper_figures_20260508/source` | 48 个 CSV/JSON/NPZ 等源文件；manifest 记录 Stage5/Stage6/Stage2/Stage4/TF13 数据源 | 关键 provenance 层；manifest 已注明限制：Stage2 为 n=6、F3 是 cached/lightweight screening、F13 不是完整模块消融、S19 缺 per-step p95/p99 |
| `tf14_remaining_experiments_20260509/data` | `tf14_remaining_runs.csv`、`summary.csv`、`manifest.json`；42 runs；seed 仅 `2026`；E0/E2/E3/E7 present | runner 和字段最接近 P0 final；当前仅 smoke/partial，不能作为正文 final statistics |
| `tf14_remaining_experiments_20260509/figures` | R0/R2/R3/R7 图和 contact sheet；README 明确 `Final n>=20 ready: False` | 机制证据/开发审查可用；正文需 full-final rerun 替换 |
| `tf14_remaining_experiments_20260509/logs` | 按 E0/E2/E3/E7 和 seed 保存日志 | 可作失败追踪输入；最终需保留 crash、solver skip、fallback、constraint violation、NaN safety field 和 missing log |
| `tf14_final_gap_closure_20260509/figures` | 6 个 gap figures：E1、E2 heatmaps、E3 certificate、E7 force/corner timelines | 补洞图层；E1 是 cached，E2/E3/E7 来自 n=1 remaining 数据，不是 final statistical replacement |
| `tf14_final_gap_closure_20260509/source` | gap closure CSV/manifest；`extra_saved_figure_files.csv` 记录复制文件 | 可作 provenance 辅助；不能替代 final run ledger |
| `tf14_final_gap_closure_20260509/extra_saved_figures` | 复制 paper/remaining/gap/QA 图共 125 个 | 归档层；`*_qa` 和 contact sheet 只能 QA，不进论文编号 |
| `tf14_stage2_statistics_20260507` | n=6 seeds 2026-2031，场景 nominal/single fault/comm medium/mixed，方法 `baseline` 与 `tf14_main` | 历史统计参考；方法集和 n 均不满足 Round 2 主文门槛 |
| `tf14_stage5_phase_role_scenarios_20260507` | 12 个代表性场景/方法结果，baseline、tf14_main、tf14_phase_role | 代表性轨迹和源数据可用；不是 paired n>=20 final statistics |
| `tf14_stage6_tf13_error_match_20260508` | 4 个 error-match runs；README 说明目标是把 TF14 DLC 误差调到 TF13 同量级 | 开发/调参记录；不能作为主创新证据 |
| `tf14_stage4_fdi_fast_response_20260507` | FDI/FTC 参数调优、candidate rank 和 summary 图 | 调参证据或补充；最终 FDI/FTC claim 仍需 paired final seeds |
| `paper_dcn_tf12_draft/figures_reasonable_comm_ablation_2026-05-07` | TF13 retuned communication ablation，含 `N07_comm_noise_dose_response.png` 和 N08 heatmap | 只能作历史模板或 supplement；不能证明 TF14 主方法的 DCN dose-response |
| `paper_dcn_tf12_draft/hairpin_stress_suite_2026-05-06_030045` | 396 文件，含 data/figures/composite/safe supplement pack | 历史 stress/safe supplement；仅可补充或开发记录 |
| `paper_dcn_tf12_draft/hairpin_stress_suite_2026-04-30_221215` | 230 文件，早期 stress suite | 旧版开发记录；不建议进入正文主图 |
| `saved_data/payload_team/offline_dataset_a1_rigid_payload_2t.npz` | 被 `run_tf14_paper_figures.py` 用作 Fig. 2/S1 离线数据源 | 可作为数据覆盖图源；E1 预测优势仍需 fresh multi-seed training runner |

轻量 NaN 检查：`tf14_remaining_runs.csv` 全 42 行中，E7 safety 关键字段 `force_norm_peak`、`force_norm_rate_peak`、`corner_load_spread_peak`、`connection_max_utilization`、`connection_violation_count` 均无 NaN；但这些字段在非 E7 行有 16 个缺失/NaN，说明 safety 图必须以 E7 final export 为准，不能把全表直接当 T5。Round2 后的 Safety NaN gate 必须把每个 NaN 明确分类为 `failure`、`not_applicable` 或 `missing`；所有比较方法必须导出同名 safety/certificate 字段，否则该方法在对应安全图、T5 或 E3 证书图中判为不可用，不能以空值静默跳过。

### 2.1 Round2 seed list 与 trace 复用建议

| 实验组 | 建议 seed list | 复用规则 | 审计门槛 |
|---|---|---|---|
| 主闭环 E0/E2/E3/E7/T2/T3/T5 | `2026-2045`，共 20 个 paired seeds；若算力允许扩展 `2046-2055` 做 sensitivity | 同一 `scenario_seed` 同时生成初始状态、参考扰动索引、通信 trace id、故障 trace id；Proposed、Frozen_AKE、NonKoopman、NoDelay、NoCommAware、NoFTC 等方法必须读取同一 trace 文件，不能各自重采样 | 每个 method-scenario 至少 `n>=20` paired rows；任一方法缺某 seed 时，该 scenario 的 paired delta 和 CI 暂停 |
| fresh E1 Koopman training | 最低 `3101-3105`，推荐 `3101-3110`；记录为 `train_seed`，不要复用 controller `scenario_seed` | `train_seed` 只控制网络初始化、shuffle、mini-batch、early-stop tie-break；离线 train/val/test split seed 固定或单独记录为 `split_seed`，Frozen_AKE/EDMD/DMDc/Proposed 使用同一 split | 主文最低 `n_train>=5`，目标 `n_train>=10`；cached screening seed 不得混入 final E1 summary |
| 通信 dose-response | 默认沿用主闭环 `2026-2045` | 对每个 seed 预生成 `comm_trace_id = scenario + seed + delay_ms + dropout_pct + jitter + burst_length`；同一 grid cell 内所有方法共享 packet age/dropout/jitter/burst 序列 | 只允许通信变量随 grid 改变；方法间 trace 不一致时整格重跑 |
| fault/safety/topology | 默认沿用主闭环 `2026-2045` | `fault_trace_id` 和 `topology_trace_id` 必须由 seed 与 schedule 生成，并在 E3/E7/Topology 中复用；故障时刻、持续时间、恢复时刻不随方法改变 | 安全或拓扑图必须能从 ledger 追溯到同一 fault/topology schedule |

### 2.2 必需 CSV schema

| 表/ledger | 最低必需列 | 说明 |
|---|---|---|
| T1 baseline table `T1_baseline_fairness.csv` | `method_id`、`display_label`、`baseline_class`、`ake_variant`、`config_path`、`config_hash`、`train_budget`、`data_budget`、`horizon`、`dt`、`solver`、`constraint_set`、`comm_assumption`、`fault_assumption`、`tuning_budget`、`allowed_information`、`seed_policy`、`frozen_by`、`frozen_at` | `ake_variant` 只能为 `AKE-R`、`AKE-A`、`AKE-M` 或 `N/A`；NonKoopman 必须声明未使用 Koopman predictor |
| Main metrics `T2_main_closed_loop.csv` | `experiment_id`、`scenario`、`method_id`、`seed`、`comm_trace_id`、`fault_trace_id`、`topology_trace_id`、`success`、`failure_type`、`path_complete`、`rmse_y`、`rmse_s`、`max_error`、`final_error`、`solve_time_p50`、`solve_time_p95`、`solve_time_p99`、`step_time_p95`、`step_time_p99`、`solver_skip_count`、`fallback_count`、`constraint_violation_count`、`log_path` | 主统计从该表出发；失败行保留并参与 failure rate，不因 metric NaN 被删除 |
| Ablation metrics `T3_ablation_metrics.csv` | `scenario`、`method_id`、`ablation_factor`、`removed_module`、`seed`、`paired_full_method_id`、`paired_delta_rmse_y`、`paired_delta_rmse_s`、`paired_delta_success`、`ci_low`、`ci_high`、`failure_type`、`comm_trace_id`、`fault_trace_id` | 每个 ablation 必须能对回同 seed 的 full TF14；没有 paired full row 时该 delta 不可用 |
| Safety T5 `T5_safety_diagnostics.csv` | `scenario`、`method_id`、`seed`、`force_norm_peak`、`force_norm_rms`、`force_norm_rate_peak`、`corner_load_spread_peak`、`connection_max_utilization`、`connection_violation_count`、`min_obstacle_margin`、`min_inter_robot_distance`、`constraint_activity_count`、`fallback_count`、`intervention_count`、`nan_class`、`failure_type`、`log_path` | `nan_class` 必填，取 `none/failure/not_applicable/missing`；任何比较方法缺同字段时该方法该 safety 图不可用 |
| Certificate E3 `E3_certificate_terms.csv` | `scenario`、`method_id`、`seed`、`time_index`、`V`、`delta_V`、`decay_rhs`、`disturbance_term`、`switching_mode`、`dwell_time`、`certificate_margin`、`certificate_ok`、`min_margin_run`、`nan_class`、`formula_version` | 字段名必须与 Worker C 证明公式一致；公式版本变化需重导出旧图 |
| Figure provenance ledger `figure_provenance_ledger.csv` | `figure_slug`、`paper_slot`、`main_or_supplement`、`source_csv`、`source_manifest`、`runner_command`、`script_path`、`script_hash`、`generated_at`、`seed_list`、`scenario_list`、`method_set`、`metric_columns`、`ci_formula`、`failure_accounting_rule`、`nan_gate_result`、`trace_policy`、`stress_or_main_grid`、`decision`、`blocker` | 正文 6-8 张图必须全部有 ledger row；缺 ledger 的图只能作开发记录或 supplement |

### 2.3 通信 grid、topology schedule 与失败计入规则

通信主网格必须限制在 bounded degradation：delay `{0,50,100,200}` ms 与 dropout `{0,5,10,20}`% 的交叉组合；每格记录 `jitter_ms` 和 `burst_length`，推荐先固定 `jitter_ms in {0,10}`、`burst_length in {1,3,5}` 中的最终取值，再用同一 trace policy 重跑所有方法。`400` ms delay、`40`% dropout、leader-lost、长时断连只允许标为 stress-test，不得混入主 CI、T2/T4 bounded claim 或正文主结论。

Topology schedule 建议主文只放可恢复退化：`complete`、`ring`、`path`、`single_edge_loss_recoverable`、`intermittent_edge_recoverable`。每个 schedule 需固定 `topology_trace_id`、切换时间、恢复时间、最小连通窗口和 dwell-time；`leader_lost`、不可恢复 disconnect、长时分区只能进入 stress-test 图或 supplement，成功样本不得外推为可恢复拓扑理论保证。

失败计入规则必须在所有 final CSV 中一致：`crash`、`path_incomplete`、`solver_infeasible`、`constraint_violation`、`nan_safety_field`、`missing_log` 全部计入 `success=false` 和 failure rate；`not_applicable` 仅允许用于结构上无定义的字段，并需在 `nan_class` 中显式标注；`missing` 视为导出失败，不能作为安全通过。若日志缺失但 summary 有数值，该 run 仍按 `missing_log` 失败计数，除非有可复核的 replacement log 和 hash。

## 3. P0 实验运行顺序

必须按以下顺序执行。原因是后续统计若没有 T1 和非 Koopman 方法集，会导致所有 final seeds 需要重跑。

| 顺序 | P0 项 | 可立即执行性 | 关键理由 |
|---:|---|---|---|
| 1 | T1 baseline fairness freeze | 待 Worker A/主 agent 冻结；本审计不写 T1 文件 | 所有主图和表必须统一 `AKE-R/AKE-A/AKE-M` 标签、训练预算、通信假设和调参规则 |
| 2 | 非 Koopman baseline | 未发现现成 final runner；需实现或启用 | 至少需要 `Physical-model DMPC`、`physical MPC + ZOH consensus` 或 `ZOH consensus MPC`，否则主比较不合格 |
| 3 | n>=20 主闭环 | runner 存在，但 method set 当前不完整 | E0 full-final seeds 是主闭环骨架；必须先纳入 Frozen AKE、NonKoopman、NoDelay、NoCommAware，并固定 `2026-2045` paired seed/trace 复用后再跑 |
| 4 | fresh Koopman seeds | 未发现现成 E1 DNN runner | cached/offline screening 不能证明 Koopman 学习贡献；需 `n_train>=5` 最低、`n_train>=10` 目标的 fresh training seeds |
| 5 | 安全诊断 | E3/E7 runner 存在；需 full-final 与三分类 NaN gate | 安全、certificate、fallback/intervention 是正文安全图和 T5 的硬门槛；所有比较方法必须导出同名字段 |
| 6 | 通信 dose-response | 未发现 TF14 final runner；只有历史模板 | DCN 主题需要 delay `{0,50,100,200}` ms、dropout `{0,5,10,20}`%、jitter/burst 的 bounded grid，并与 400 ms/40% stress-test 分离 |
| 7 | topology recovery | 未发现 final runner | 需要 complete/ring/path/single-edge/recoverable topology sweep；leader-lost 和不可恢复断连仅 stress-test |

## 4. 每项 P0 实验的输入、输出、指标、验收标准、失败处理

| P0 项 | 输入 | 输出文件 | 指标 | 验收标准 | 失败处理 |
|---|---|---|---|---|---|
| T1 baseline fairness | uploaded AKE baseline PDF；Worker A baseline contract；当前 `baseline` runner/config；Proposed TF14 config | `T1_baseline_fairness.csv/md` 或等价 ledger；每个 method 的 frozen config hash/path；run command ledger | AKE label、data budget、train/val split、horizon、dt、solver、constraints、communication trace、tuning budget、seed list | `Frozen_AKE` 明确为 `AKE-R/AKE-A/AKE-M`；主文 wording 与标签一致；同一 seed/trace/constraint/horizon | 若无法 strict reproduce，则降级 `AKE-A` 或 `AKE-M`；若只能 `AKE-M`，主文不得声称优于原 AKE |
| 非 Koopman baseline | 物理模型或 ZOH consensus controller；同一 scenario/seed/trace；T1 method schema | final runs 写入 `tf14_remaining_runs.csv`/新 final CSV；NonKoopman diagnostics/logs；T1/T2/T4 方法表 | RMSE_y、RMSE_s、success/failure、constraint violation、runtime、comm sensitivity、fallback/intervention | 至少一个非 Koopman 网络控制 baseline 与 Proposed/Frozen_AKE 同场景、同 seed、同通信/故障 trace；不能使用 Koopman predictor | 若 Physical-model DMPC 不可用，最低用 `ZOH consensus MPC` 并标注限制；若仍缺失，所有主闭环 superiority claim 暂停 |
| n>=20 主闭环 | `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`；scenarios `sine_nominal_clean`、`sine_comm_noise_high`、`sine_single_fault_v2`、`sine_mixed_fault_noise`；seeds `2026-2045`；冻结 method set；同 seed 复用通信/故障/topology trace | `tf14_remaining_experiments_20260509/data/tf14_remaining_runs.csv`、`tf14_remaining_summary.csv`、`tf14_remaining_manifest.json`；`figures/R0_*`；logs/core/diagnostics per run | RMSE_y/RMSE_s、max error、full path、success/failure、step p95/p99、solve p95/p99、solver skip、fallback/intervention、95% CI、paired delta、failure_type | 每个 method-scenario `n>=20` paired seeds；failures 不剔除；95% CI 和 failure count 同时报；method set 包含 Proposed、Frozen_AKE、NonKoopman、NoDelay、NoCommAware | `crash`/`solver_infeasible`/`path_incomplete`/`constraint_violation`/`nan_safety_field`/`missing_log` 都计入失败；若 method 缺失或 trace 不一致，整组重跑 |
| fresh Koopman seeds | offline dataset；Proposed bilinear Koopman、linear EDMD/DMDc、Frozen AKE model；统一 split/normalization/epochs/early stop；train seeds `3101-3105` 最低、`3101-3110` 目标 | 新 E1 runner 输出 `E1_koopman_fresh_runs.csv`、`E1_koopman_fresh_summary.csv`、model seed logs、Fig. 2/3/G1 final replacement | one-step RMSE、multi-step rollout RMSE、spectral radius、stable projection margin、train/val loss、95% CI、training failure count | 最低 `n_train>=5`，目标 `n_train>=10`；fresh training seeds；同 split；不使用 cached screening 作为主结论 | 若训练失败，保留失败 seed、错误和模型目录 hash；若只剩 cached data，Koopman 图降级 supplement/机制示意 |
| 安全诊断 | E3/E7 full-final runs；Worker C proof field definitions；same disturbance traces；T1/NonKoopman/NoCommAware/NoFTC/Proposed | diagnostics `certificate.csv`、`comm.csv`、`connection.csv`、`fault.csv`、`switch.csv`、`control_spread.csv`、`payload_force.csv`、`summary.json`；`R3_*`、`R7_*`、G4/G5/G6 final；`T5_safety_diagnostics.csv` | certificate ok ratio/min margin/max V、force peak/RMS/rate、connection utilization/violation、corner load spread、constraint activity、fallback/intervention、solver skip、`nan_class` | T5 safety fields 不能有未分类 NaN；`nan_class` 只能为 `none/failure/not_applicable/missing`；所有方法同名字段齐全；violation/fallback/constraint activity 可复核；certificate 字段与理论公式一致 | `failure` 或 `missing` NaN 计入失败；字段缺失时该方法该图不可用；fallback 不完整则只可写“diagnostic pending”；证书与公式不一致则回退为 empirical safety |
| 通信 dose-response | 新/扩展 runner；delay `{0,50,100,200}` ms；dropout `{0,5,10,20}`%；记录 jitter/burst length；同一 trace 复用；stress 400 ms/40% 分开 | `F_comm_dose_response`/`N1`、`N3`、`T4_comm_envelope.csv`、trace ledger；`comm_trace_id` grid table | RMSE_y/RMSE_s、success、max error、certificate margin、connection utilization、stale packet age、jitter_ms、burst_length、solver skip/failure | bounded main grid 每点 `n>=20` paired seeds；只改变通信变量；stress-test 不混入主 CI；方法集含 Proposed/Frozen_AKE/NonKoopman/NoDelay/NoCommAware | 若仅有 TF13 `N07`，只能作模板/supplement；若 bounded grid 不完整，主文只写已覆盖子区间；400 ms/40% 结果只写 stress-test |
| topology recovery | 新/扩展 topology runner；complete/ring/path/single-edge loss/recoverable intermittent edge；leader-lost stress；fixed switching schedule | `F_topology_recovery`/`N2`、`T4_topology_recovery.csv`、topology schedule/trace logs；`topology_trace_id` ledger | consensus error、role switch count、RMSE、recovery time、force peak、connection violation、certificate min margin、fallback count、dwell-time | 可恢复 topology `n>=20` paired seeds；同一 schedule/initial state；leader-lost/long disconnect 单独标为 stress-test；recoverable schedule 必须含恢复时刻 | 若 topology runner 未就绪，网络拓扑韧性 claim 暂缓；leader-lost 成功样本不得外推为理论保证 |

## 5. 6-8 张正文主图 readiness gate

每张正文主图编号前必须通过同一 ledger：`figure_slug`、source data path、source manifest、runner command、script path/hash/timestamp、seed list、scenario、method set、metric columns、CI formula、NaN check、failure accounting、trace policy、main/stress grid 标记、main/supplement decision。

| 主图候选 | 当前图源 | Provenance | Seed | Scenario | Method set | CI | 无 NaN | Gate 结论 |
|---|---|---|---|---|---|---|---|---|
| Fig. 1 framework/model | `fig00_graphical_abstract`、`fig01_system_modeling` | 部分通过，source CSV 有记录 | N/A | N/A | N/A | N/A | N/A | 可入正文，但只能作结构图，不承载性能 claim |
| Fig. 2 Koopman learning/prediction | `fig02`、`fig03`、`E1_koopman_prediction_validation` | 部分通过，E1 来源明确但 cached | 不通过，缺 fresh training seeds | 离线/rollout 待冻结 | 缺 Frozen_AKE fresh 对照 | 不通过 | 需检查 | P0 blocked；fresh E1 完成前只作 supplement/机制示意 |
| Fig. 3 main closed-loop trajectory/timeline | `fig05_main_trajectory_compare`、`R0_error_timeseries` | 部分通过 | 不通过，当前代表性/seed_2026 | high comm/mixed 有，nominal/single fault需 final | 不通过，缺 NonKoopman 和冻结 T1 | 不适用或缺 | 待 final | P0 blocked；可保留代表性图，统计结论看 Fig. 4/T2 |
| Fig. 4 aggregate tracking/reliability | `fig06_tracking_error_statistics`、`R0_main_comparison_summary`、`R0_reliability_runtime` | 部分通过 | 不通过，当前 R0 n=1 或 Stage2 n=6 | 四主场景可由 E0 覆盖 | 不通过 | 不通过，需 95% CI/paired delta | 待 final | P0 blocked；E0 full-final 完成后替换 |
| Fig. 5 communication dose-response | 新 `F_comm_dose_response`/`N1`/`N3` | 缺失 | 缺失 | 缺 bounded grid | 缺失 | 缺失 | 缺失 | P0 missing；DCN 主题强建议正文必须有 |
| Fig. 6 module ablation | `R2_*`、`E2_positive_worse_*`、`fig13` | 部分通过 | 不通过，current n=1 | high comm/mixed 有 | 部分通过，仍缺 NonKoopman/T1 linkage | 不通过 | 待 final | P0 blocked；E2 full-final 后可入正文或正文+补充 |
| Fig. 7 safety/certificate | `fig10`、`R7_*`、`R3_*`、`G4/G5/G6` | 部分通过 | 不通过，E3/E7 current n=1 | high comm/mixed 有；single/nominal需 E3 | 部分通过，E7 含 baseline/no_comm/no_ftc/tf14 | 不通过 | E7 smoke 通过，final 待查 | P0 blocked；E7/E3 final + Worker C 字段一致后入正文 |
| Fig. 8 runtime/deployment overhead | `fig14_realtime_pareto`、`R0_reliability_runtime` | 部分通过 | 不通过 | 主场景需 paired | 不通过 | 不通过 | 待 final | P1/P0 边界；若主文强调实时部署，则需固定硬件、message size、p95/p99、overrun |

推荐正文最终收敛为 7 张：framework/model、fresh Koopman、main trajectory、aggregate performance、communication dose-response、safety/certificate、runtime/ablation 二选一或合并。若版面允许 8 张，再单独保留 topology recovery；否则 topology 放 supplement，但 T4 必须正文可引用。

## 6. 只能作 supplement 或开发记录的现有图

| 图/目录 | 归类 | 原因 |
|---|---|---|
| `tf14_remaining_experiments_20260509/figures/R0_*`、`R2_*`、`R3_*`、`R7_*` 当前版本 | Supplement/开发记录 | README 和 manifest 显示 `minimum_group_n=1`、`final_statistics_ready=false` |
| `tf14_final_gap_closure_20260509/figures/E1_*` 当前版本 | Supplement/机制示意 | 使用 cached offline screening data，不是 fresh DNN multi-seed |
| `tf14_final_gap_closure_20260509/figures/E2_*`、`E3_*`、`E7_*` 当前版本 | Supplement/开发记录 | 来自 remaining smoke/evidence 数据，不是 n>=20 final |
| `tf14_final_gap_closure_20260509/*contact_sheet*`、`extra_saved_figures/*_qa` | QA only | contact sheet 仅用于视觉检查，不应编号引用 |
| `tf14_paper_figures_20260510/figures/figS*` | Supplement by design | `S` 图可作补充；其中 `figS19_tf13_error_match_runtime` 是历史实现 sanity check |
| `tf14_paper_figures_20260510/figures/fig13_module_ablation_available_variants` 当前版本 | Supplement/需替换 | manifest 指出它只是 available-variant ablation，不是完整 bilinear/stable/comm/FDI/FTC 消融 |
| `tf14_paper_figures_20260510/figures/fig14_realtime_pareto` 当前版本 | Supplement/需刷新 | manifest 指出 raw per-step p95/p99/overrun 仍需 dedicated rerun/log export |
| `tf14_stage2_statistics_20260507/figures` | Supplement/历史统计 | n=6、方法集只有 baseline/tf14_main，缺 T1/NonKoopman/NoDelay/NoComm |
| `tf14_stage4_fdi_fast_response_20260507/figures` | 开发记录或 supplement | FDI/FTC 调参图，不是最终 paired performance |
| `tf14_stage5_phase_role_scenarios_20260507/figures` | Supplement/代表性记录 | 单 seed/代表性场景，非 final statistics |
| `tf14_stage6_tf13_error_match_20260508` 图表/CSV | 开发记录 | 目标是误差调参和 TF13 error-match，不是主创新证据 |
| `paper_dcn_tf12_draft/figures_reasonable_comm_ablation_2026-05-07` | Supplement/模板 | TF13 retuned 通信消融，可作图形结构参考，不能证明 TF14 主方法 |
| `paper_dcn_tf12_draft/hairpin_stress_suite_*` | Supplement/开发记录 | 旧 stress suite，适合失败边界、safe supplement 或历史诊断，不作为 TF14 主结论 |
| `figures_selected_*`、`data_selected_*`、`figures_tf13`、`data_tf13` | 开发记录/历史材料 | 非 Round 2 final provenance；若引用必须明确历史版本或补充用途 |

## 7. 已发现候选命令

以下命令来自 README、`FULL_FINAL_COMMANDS.md` 或 runner 参数检查。带“待确认”的命令只说明 runner 存在或可生成当前图层，不代表满足 P0 final 方法集。

```powershell
# E0 主闭环 n>=20 候选。待确认：必须先把 Frozen_AKE/NonKoopman/NoDelay/NoCommAware 纳入同一 method set。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise

# E2 模块消融 n>=20 候选。当前支持 full_tf14/no_bilinear/no_comm_aware/no_delay/no_fdi/no_ftc/no_online/no_phase/no_guard/no_scheduler/no_stable 等。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E2 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise

# E3 certificate n>=20 候选。待确认：需与 Worker C 的公式字段对齐。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E3 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise

# E7 safety diagnostics n>=20 候选。待确认：final 后需重新做无 NaN、fallback/intervention、constraint activity 检查。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E7 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise

# gap closure 图层重生成。注意：不是 n>=20 final replacement；会从已有 paper/remaining 数据生成 gap/copy 层。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_final_gap_closure_20260509\run_tf14_final_gap_closure.py

# paper figure draft regeneration。待确认：来自 runner 参数，建议只在不跑 detailed cases 时使用；不是 final statistics。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_paper_figures_20260508\run_tf14_paper_figures.py --skip-detail-run

# Stage4 FDI/FTC tuning。仅开发/调参用途，不替代 final paired seeds。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_stage4_fdi_fast_response_20260507\run_tf14_stage4_fdi_tuning.py

# Stage6 TF13 error-match。仅开发/调参用途，不作为主创新证据。
E:\anaconda\envs\pytorch_new\python.exe .\tf14_stage6_tf13_error_match_20260508\run_tf14_stage6_tf13_error_match.py
```

未发现可直接执行的 P0 命令：

| 缺失 runner | 当前处理 |
|---|---|
| T1 baseline freeze runner | 由 Worker A/主 agent 冻结合同；D 侧只要求实验 ledger 必须引用它 |
| NonKoopman final baseline runner | 待实现或确认隐藏入口；不能编造命令 |
| E1 fresh Koopman multi-training-seed runner | 待实现；现有 E1 cached 图不能替代 |
| TF14 bounded communication dose-response runner | 待实现；历史 `N07` 仅模板 |
| topology degradation/recovery runner | 待实现；leader-lost 仅 stress-test |

## 8. 执行优先级与交付 gate

| 优先级 | 执行动作 | 交付 gate |
|---|---|---|
| P0-1 | 冻结 T1 baseline 和 NonKoopman method schema，更新 runner 前不要跑 final seeds | 每个 method 有 frozen config、label、same seed/trace/constraint 说明 |
| P0-2 | dry-run 或单 seed 验证新增 NonKoopman 与 Frozen_AKE 接入 E0/E2/E7 | 只验证输出字段，不作为论文结果 |
| P0-3 | 跑 E0 `--full-final-seeds`，生成 T2/R0 final | 每个 method-scenario n>=20，`2026-2045` paired seeds、trace 复用、95% CI、paired delta、failure count 完整 |
| P0-4 | 跑 E1 fresh Koopman/AKE/DMDc/EDMD multi-training seeds | `n_train>=5` 通过，目标 `n_train>=10`；train seeds 与 split/hash 记录完整；替换 cached Fig. 2/3/G1 |
| P0-5 | 跑 E3/E7 full-final，生成 certificate/safety T5 | T5 无未分类 NaN；`failure/missing/not_applicable` 分类完整；所有比较方法同字段导出 |
| P0-6 | 跑 E2 full-final，生成 ablation T3/R2 | NoDelay/NoComm/NoBilinear/NoFTC/NoGuard 等 paired delta、trace 复用和失败计数齐全 |
| P0-7 | 新增通信 dose-response 和 topology recovery | T4 明确 bounded main vs stress-test；delay/dropout/jitter/burst grid 和 recoverable topology schedule 有 CI 与 failure mode |
| P0-8 | 冻结 6-8 张正文主图 ledger | 每张图 provenance、seed、scenario、method set、CI、NaN gate、failure accounting、trace policy 全部通过 |

最终投稿前允许的 claim 边界：只有在 T1、NonKoopman、paired `n>=20`、fresh E1、T5 无未分类 NaN、dose-response/topology 和主图 ledger 全部通过后，才能写“在 bounded communication degradation 和可恢复拓扑退化下，Proposed BK-DCCMPC 相对冻结 AKE baseline 与非 Koopman 网络控制 baseline 有统计支持的 tracking/safety/runtime 改善”。在此之前，主文只能写“当前图层展示机制与代表性趋势，最终统计仍待 P0 run 完成”。

## 9. One-page final gate checklist

| Final gate | 必须满足的通过条件 | 当前审计状态 |
|---|---|---|
| T1 frozen | `T1_baseline_fairness.csv/md` 已冻结；`Frozen_AKE` 明确为 `AKE-R/AKE-A/AKE-M`；method label、训练预算、通信假设、约束、调参预算和 config hash 可追溯 | 未通过，待 Worker A/主 agent freeze |
| NonKoopman present | 至少一个非 Koopman 网络控制 baseline 与 Proposed/Frozen_AKE 同 scenario、同 seed、同通信 trace、同故障 trace；T1 标明未使用 Koopman predictor | 未通过，未发现 final runner |
| Paired `n>=20` | 主闭环 E0/E2/E3/E7/T2/T3/T5 使用 `2026-2045` paired seeds；缺 seed、缺方法或 trace 不一致则该组不合格 | 未通过，当前主要是 n=1 或历史 n=6 |
| Fresh E1 | E1 使用 fresh training seeds，最低 `n_train>=5`、目标 `n_train>=10`；Proposed/Frozen_AKE/EDMD/DMDc 同 split、同预算；cached screening 不进主结论 | 未通过，当前 E1 为 cached |
| T5 no-NaN | Safety T5 所有比较方法导出同名字段；NaN 只能显式分类为 `failure/not_applicable/missing`，其中 `failure/missing` 计入失败；字段缺失则该方法该图不可用 | 未通过，需 final E7/E3 后复查 |
| Dose grid | 主通信网格覆盖 delay `{0,50,100,200}` ms、dropout `{0,5,10,20}`%、jitter、burst length；`400` ms/`40`% 只作 stress-test | 未通过，仅有历史模板或计划项 |
| Topology grid | 主拓扑只声明可恢复退化：complete/ring/path/single-edge loss/recoverable intermittent edge；leader-lost、不可恢复断连只作 stress-test | 未通过，未发现 final runner |
| Figure ledger | 6-8 张正文主图均有 `figure_provenance_ledger.csv` row：source、command、script hash、seed list、scenario、method set、CI、NaN gate、failure accounting、trace policy、main/stress 标记 | 未通过，需 final 数据替换后冻结 |
