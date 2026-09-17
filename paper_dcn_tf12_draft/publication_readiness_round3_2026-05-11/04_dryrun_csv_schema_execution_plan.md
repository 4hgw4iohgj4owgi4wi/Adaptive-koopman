# Round 3 Worker D: Dry-Run and CSV Schema Execution Plan

生成日期：2026-05-11

工作范围：只读检查 Round2 experiment audit、runner files、README，并形成安全 dry-run/help 命令、one-seed/smoke 候选、final `n>=20` 命令清单、CSV schema validation 计划、no-NaN/safety log 检查计划和进入 final runs 的 gate。本文件不执行任何实验，不修改 runner，不移动或删除已有数据。

## 0. 关键结论

| 项 | 结论 | 对执行计划的影响 |
|---|---|---|
| `run_tf14_remaining_experiments.py` | 有 `argparse` CLI，支持 `--help`、`--experiments`、`--seeds`、`--full-final-seeds`、`--scenarios`、`--quick`、`--force`、`--reuse-env` | 可做 `--help` 安全确认；one-seed/smoke 会真实写入固定 data/log/figures，不能当纯 dry-run |
| `run_tf14_final_gap_closure.py` | 没有 `argparse` 或 `--help`；直接运行会生成图、复制图并写 source/README/FULL_FINAL_COMMANDS | 不允许用它跑 help；只能静态读源码或在 final 数据通过后再运行 |
| 真正 `--dry-run` | 当前 runner 不存在 `--dry-run`、`--list-plan`、`--output-root` 或 `--validate-only` | Worker D 只能给“dry-run 等价的静态检查”和“受控 smoke 候选”，不能声称有无写入 dry-run |
| 当前数据状态 | `tf14_remaining_manifest.json` 显示 `minimum_group_n=1`、`final_statistics_ready=false`；README 明确 current rows are smoke/partial | 当前 CSV 只能用于 schema/字段审计，不能用于正文 final statistics |
| Round2 P0 gate | T1 baseline freeze、NonKoopman、paired `n>=20`、fresh E1、T5 no-NaN、dose/topology、figure ledger 未闭合 | final 命令只能列出，必须等 gate 全部满足后再执行 |

## 1. 安全 help/static 命令

这些命令用于确认 CLI、路径和现有 manifest。它们不启动实验；其中 `run_tf14_remaining_experiments.py --help` 会导入脚本并经过顶层目录检查，但不会进入 `_run_suite`。

| ID | 命令 | 预估耗时 | 安全边界 | 期望输出 |
|---|---|---:|---|---|
| H0 | `Test-Path .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py` | `<1 s` | 只读路径检查 | `True` |
| H1 | `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --help` | `3-10 s` | 不运行实验；不要加其他参数 | 显示 `--experiments`、`--seeds`、`--full-final-seeds`、`--scenarios`、`--quick`、`--force`、`--reuse-env` |
| H2 | `Select-String -Path .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py -Pattern 'parser.add_argument|P0_SEEDS|E0_SCENARIOS|E2_SCENARIOS|E3_SCENARIOS|E7_SCENARIOS|method_order'` | `<5 s` | 静态源码检查 | 确认 final seeds、scenario list、method order |
| H3 | `Select-String -Path .\tf14_final_gap_closure_20260509\run_tf14_final_gap_closure.py -Pattern 'def main|argparse|FULL_FINAL_COMMANDS|_write_commands_file'` | `<5 s` | 静态源码检查；不要运行 gap runner | 确认 gap runner 无 help，且会写图/manifest/README |
| H4 | `Get-Content .\tf14_remaining_experiments_20260509\data\tf14_remaining_manifest.json` | `<2 s` | 只读 manifest | 确认 `minimum_group_n`、`final_statistics_ready`、outputs |

禁止命令：

```powershell
# 不安全：gap runner 没有 --help，任何调用都会执行生成逻辑
E:\anaconda\envs\pytorch_new\python.exe .\tf14_final_gap_closure_20260509\run_tf14_final_gap_closure.py --help
```

## 2. One-Seed / Smoke 候选命令

以下命令是“受控 smoke run 候选”，不是纯 dry-run。当前 runner 写入固定目录：

- `tf14_remaining_experiments_20260509/data/tf14_remaining_runs.csv`
- `tf14_remaining_experiments_20260509/data/tf14_remaining_summary.csv`
- `tf14_remaining_experiments_20260509/data/tf14_remaining_manifest.json`
- `tf14_remaining_experiments_20260509/logs/...`
- `tf14_remaining_experiments_20260509/figures/...`

执行前必须由 main agent 明确批准，并先冻结/备份现有 `data`、`logs`、`figures`。默认不要用 `--force`，因为 `--force` 会覆盖已有 run IDs。

| ID | 候选命令 | 覆盖内容 | 预估耗时 | 用途 | 通过条件 |
|---|---|---|---:|---|---|
| O1 | `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E3 --seeds 2026 --scenarios sine_nominal_clean` | 1 seed x 1 scenario x 1 method | `1-3 min` | 最小 certificate/export smoke | 生成/保留 E3 row，certificate diagnostics 存在，schema 通过 |
| O2 | `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --seeds 2026 --scenarios sine_comm_noise_high` | 1 seed x 1 scenario x 4 methods | `3-6 min` | 主闭环 method-set/output smoke | E0 四方法 rows 完整，logs/core/summary 更新一致 |
| O3 | `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E7 --seeds 2026 --scenarios sine_comm_noise_high` | 1 seed x 1 scenario x 5 methods | `4-8 min` | safety diagnostics smoke | E7 safety columns finite 或显式分类，payload/connection logs 存在 |
| O4 | `E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --quick --seeds 2026` | quick overrides to mixed scenario and E0/E2/E3/E7; 约 21 run IDs | `15-25 min` | 综合 smoke | 所有实验类型能完成，manifest/summary/schema/no-NaN gate 通过 |

耗时依据：现有 `high_comm_smoke_stdout.log` 显示 21 个 run IDs 约从 2026-05-09 12:58:51 到 13:13:33，约 14 分 42 秒；`e7_corner_refresh_stdout.log` 显示 10 个 run IDs 约 6 分 13 秒。实际耗时依 GPU、已有 run skip、是否复用环境而变。

不建议在 smoke 中使用 `--reuse-env` 作为 gate 依据。`--reuse-env` 可加速调试，但 README 已提示默认 isolated run 更适合 final provenance。

## 3. Final `n>=20` 命令清单

以下命令只列出，不执行。它们来自 runner 源码、README 和 `FULL_FINAL_COMMANDS.md`。当前仍被 T1/NonKoopman/fresh E1/dose/topology/ledger gate 阻断；即使命令可运行，也不能直接视为投稿 final evidence。

```powershell
# E0 main closed-loop final candidate: 20 seeds x 4 scenarios x 4 methods = 320 run IDs, 估计 3.5-5.0 h
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E0 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise

# E2 module ablation final candidate: 20 seeds x 2 scenarios x 11 methods = 440 run IDs, 估计 5.0-7.0 h
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E2 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise

# E3 certificate final candidate: 20 seeds x 4 scenarios x 1 method = 80 run IDs, 估计 1.0-1.5 h
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E3 --full-final-seeds --scenarios sine_nominal_clean sine_comm_noise_high sine_single_fault_v2 sine_mixed_fault_noise

# E7 payload/connection safety final candidate: 20 seeds x 2 scenarios x 5 methods = 200 run IDs, 估计 2.5-4.0 h
E:\anaconda\envs\pytorch_new\python.exe .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py --experiments E7 --full-final-seeds --scenarios sine_comm_noise_high sine_mixed_fault_noise

# Gap-closure figure regeneration after final CSV gate only; not a simulation, but writes figures/source/README
E:\anaconda\envs\pytorch_new\python.exe .\tf14_final_gap_closure_20260509\run_tf14_final_gap_closure.py
```

Final 命令仍缺的 P0 项：

- E1 fresh Koopman multi-training-seed runner 未发现，cached E1 不可进入主结论。
- NonKoopman final baseline 未在当前 method order 中出现。
- Bounded communication dose-response runner 未发现。
- Topology recovery runner 未发现。
- T1 `Frozen_AKE` 标签、预算、配置 hash 和 method ledger 需要先冻结。

## 4. 预期输出与 provenance 粒度

| 输出 | 路径 | 角色 | Gate 要求 |
|---|---|---|---|
| run-level CSV | `tf14_remaining_experiments_20260509/data/tf14_remaining_runs.csv` | 每个 experiment/seed/scenario/method 一行 | 所有 run IDs 保留，失败不能删除 |
| summary CSV | `tf14_remaining_experiments_20260509/data/tf14_remaining_summary.csv` | group mean/std/n | 每个 method-scenario `num_runs>=20` |
| manifest | `tf14_remaining_experiments_20260509/data/tf14_remaining_manifest.json` | run batch metadata | `final_statistics_ready=true`、`minimum_group_n>=20`、`seeds=2026-2045` |
| logs | `tf14_remaining_experiments_20260509/logs/<experiment>/seed_<seed>/<scenario>_<method>.log` | run-level failure/safety trace | 每行 `log_path` 存在且非空 |
| diagnostics | `tf14_remaining_experiments_20260509/data/diagnostics/<experiment>/seed_<seed>/<scenario>_<method>/*.csv` | certificate/comm/connection/fault/switch/control/payload evidence | E3/E7 必须字段完整 |
| core arrays | `tf14_remaining_experiments_20260509/data/core/<experiment>/seed_<seed>/*_core.npz` | timeline figure provenance | 若正文使用 timeline，则 npz 存在且数组 finite |
| gap source | `tf14_final_gap_closure_20260509/source/*.csv` | final figure source layer | 只能在 final CSV 通过后重建；manifest limitations 不得含 cached final claim |

## 5. CSV Schema Validation 计划

### 5.1 `tf14_remaining_runs.csv` 当前 runner 必需列

最低必须存在：

```text
experiment, seed, scenario, path_mode, method, display_name,
full_path_reached, progress_ratio, sim_steps,
rmse_lat_mean, rmse_long_mean, max_lat_global, max_long_global,
step_time_mean, step_time_p50, step_time_p95, step_time_p99,
mpc_solve_time_mean, solve_time_p95, solve_time_p99,
solver_success_count, solver_skip_count, fail_total,
certificate_ok_ratio, certificate_min_margin, certificate_max_V,
force_norm_peak, force_norm_rms, force_norm_rate_peak,
corner_load_spread_peak, connection_max_utilization, connection_violation_count,
log_path, core_npz, diagnostics_dir
```

字段类型与范围：

- `experiment` 必须属于 `E0/E2/E3/E7`。
- `seed` 必须为整数；final batch 必须覆盖 `2026-2045`。
- `scenario` 必须属于 runner scenario list：`sine_nominal_clean`、`sine_comm_noise_high`、`sine_single_fault_v2`、`sine_mixed_fault_noise`。若旧数据出现 `dlc_*`，必须在 ledger 中标明旧 smoke/source，不得混入 final scenario gate。
- `method` 必须匹配当前 experiment 的 method order；final gate 还要求额外补齐/映射 `Frozen_AKE` 和 `NonKoopman`。
- `full_path_reached` 必须可解析为 bool；`progress_ratio` 在 `[0,1.05]` 内。
- runtime/solver/count/force/connection 字段必须非负；`step_time_p99 >= step_time_p95 >= 0`，`solve_time_p99 >= solve_time_p95 >= 0`。
- E7 safety 字段必须 finite；非 E7 若结构性空值，需在派生 T5 中标为 `not_applicable`，不能静默当作通过。

### 5.2 Round2 投稿 schema 缺口

当前 runner CSV 不能完全等价于 Round2 投稿表。final 前必须补一个派生 ledger 或修改 runner 使下列字段可追溯：

| Round2 schema 字段 | 当前状态 | 处理要求 |
|---|---|---|
| `experiment_id` | 当前为 `experiment` | 可 alias，但 ledger 要固定 |
| `method_id` | 当前为 `method` | 可 alias；必须补 `display_label/baseline_class/ake_variant` |
| `success`、`failure_type`、`path_complete` | 当前有 `full_path_reached`、`fail_total`，但 failure semantics 不足 | 需派生且保留 `crash/path_incomplete/solver_infeasible/constraint_violation/nan_safety_field/missing_log` |
| `comm_trace_id`、`fault_trace_id`、`topology_trace_id` | 当前未导出 | final paired-seed gate 阻断，除非补 trace ledger |
| `constraint_violation_count`、`fallback_count`、`intervention_count` | 当前仅有部分 solver/fail/safety proxy | T5/T2 gate 要求明确导出或派生 |
| `nan_class` | 当前未导出 | T5/E3 gate 必须补 `none/failure/not_applicable/missing` |
| `formula_version`、`decay_rhs`、`delta_V` | certificate diagnostics 当前为 `V/predicted_upper/contraction_margin/...` | 需与 Worker C proof 字段映射或重新导出 |

### 5.3 `tf14_remaining_summary.csv` 检查

必须存在：

```text
experiment, scenario, method, num_runs,
rmse_lat_mean_mean, rmse_lat_mean_std,
rmse_long_mean_mean, rmse_long_mean_std,
full_path_reached_mean, full_path_reached_std,
step_time_p95_mean, step_time_p99_mean,
solve_time_p95_mean, solve_time_p99_mean,
connection_max_utilization_mean, connection_violation_count_mean,
force_norm_peak_mean, force_norm_rms_mean, force_norm_rate_peak_mean,
corner_load_spread_peak_mean,
certificate_ok_ratio_mean, certificate_min_margin_mean,
fail_total_mean, solver_skip_count_mean
```

Gate：

- 每个 final group `num_runs>=20`。
- 同一 experiment/scenario/method 的 run-level row count 必须等于 summary `num_runs`。
- final summary 必须同时报告 mean/std；CI 可由 paired bootstrap 或 t interval 在 figure ledger 中记录。
- 不能因为 failed rows 的 metrics 为 NaN 就删除 failed rows；failure rate 必须单独计入。

### 5.4 Manifest 检查

`tf14_remaining_manifest.json` final gate：

- `stage == "tf14_remaining_experiments"`。
- `quick == false`。
- `minimum_group_n >= 20`。
- `final_statistics_ready == true`。
- `seeds` 精确为 `[2026, ..., 2045]`，除非另有扩展 sensitivity ledger。
- `outputs.runs_csv`、`outputs.summary_csv`、`outputs.manifest_json`、`outputs.figures` 全部存在。
- `experiments_present` 至少含本批请求 experiment；跨批整合时不得用旧 smoke 的 manifest 覆盖 final manifest。

### 5.5 Diagnostics CSV 检查

| 文件 | 当前观察到的关键列 | Final 检查 |
|---|---|---|
| `certificate.csv` | `step,mode,V,predicted_upper,contraction_margin,disturbance_level,identification_error,certificate_ok` | E3/E7 对应 run 必须存在；`V/predicted_upper/contraction_margin` finite；`certificate_ok` 可布尔化；字段需映射 Worker C 公式 |
| `comm.csv` | `step,quality_global,mean_delay_steps,loss_ratio,consensus_blend_mean,tighten_frac,degrade_mix,quality_in_mean` | high-comm/mixed 必须存在；delay/loss finite；trace policy 必须另有 ledger |
| `connection.csv` | `enabled,max_abs_ds,max_abs_dey,max_abs_dpsi,rms_rel` | E7 必须存在；不得缺字段；连接约束超限需计入 violation |
| `fault.csv` | `step,active,vehicle_index,mode,deficit_delta,deficit_ax,deficit_norm,source,redistribution_enabled,diagnosed_mode,diagnosed_confidence` | fault scenarios 必须存在；非 fault 可 empty 但要 `not_applicable` |
| `switch.csv` | `step,global_mode,target_mode,mode_hold_counter,comm_quality_global,redistributed_total_delta,redistributed_total_ax` | FTC/switch claim 使用时必须存在 |
| `control_spread.csv` | `delta_spread,ax_spread,...,comm_quality_global,...,fault_active,...` | runtime/safety supplement 使用时必须存在 |
| `payload_force.csv` | `ax_body,ay_body,fx_payload,fy_payload,mz_payload,corner_load_min,corner_load_max,corner_load_spread,...` | E7 force/corner/load 图必须存在且 finite |

### 5.6 只读 validation command 候选

该命令只读取 CSV/JSON/log/core paths 并打印错误；不运行实验，不写文件。

```powershell
@'
from pathlib import Path
import csv, json, math, sys

root = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
data = root / "tf14_remaining_experiments_20260509" / "data"
runs_path = data / "tf14_remaining_runs.csv"
summary_path = data / "tf14_remaining_summary.csv"
manifest_path = data / "tf14_remaining_manifest.json"

required_run = {
    "experiment","seed","scenario","method","display_name","full_path_reached",
    "progress_ratio","sim_steps","rmse_lat_mean","rmse_long_mean",
    "step_time_p95","step_time_p99","solve_time_p95","solve_time_p99",
    "solver_success_count","solver_skip_count","fail_total",
    "certificate_ok_ratio","certificate_min_margin","certificate_max_V",
    "force_norm_peak","force_norm_rms","force_norm_rate_peak",
    "corner_load_spread_peak","connection_max_utilization","connection_violation_count",
    "log_path","core_npz","diagnostics_dir",
}
required_summary = {"experiment","scenario","method","num_runs","rmse_lat_mean_mean","rmse_long_mean_mean","full_path_reached_mean"}
safety_cols = ["force_norm_peak","force_norm_rms","force_norm_rate_peak","corner_load_spread_peak","connection_max_utilization","connection_violation_count"]
errors = []

def is_finite(v):
    try:
        x = float(v)
        return math.isfinite(x)
    except Exception:
        return False

with runs_path.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
if not rows:
    errors.append("runs csv is empty")
missing = required_run.difference(rows[0].keys())
if missing:
    errors.append(f"runs missing columns: {sorted(missing)}")

for i, row in enumerate(rows, start=2):
    for pcol in ["log_path","core_npz","diagnostics_dir"]:
        value = row.get(pcol, "")
        if value and not Path(value).exists():
            errors.append(f"line {i}: missing path {pcol}={value}")
    if row.get("experiment") == "E7":
        for col in safety_cols:
            if not is_finite(row.get(col, "")):
                errors.append(f"line {i}: E7 non-finite safety col {col}")
    for lo, hi in [("step_time_p95","step_time_p99"), ("solve_time_p95","solve_time_p99")]:
        if is_finite(row.get(lo, "")) and is_finite(row.get(hi, "")) and float(row[hi]) < float(row[lo]):
            errors.append(f"line {i}: {hi} < {lo}")

with summary_path.open("r", encoding="utf-8-sig", newline="") as f:
    summary = list(csv.DictReader(f))
if summary:
    missing = required_summary.difference(summary[0].keys())
    if missing:
        errors.append(f"summary missing columns: {sorted(missing)}")

with manifest_path.open("r", encoding="utf-8") as f:
    manifest = json.load(f)
if manifest.get("final_statistics_ready") and int(manifest.get("minimum_group_n", 0)) < 20:
    errors.append("manifest final_statistics_ready true but minimum_group_n < 20")

if errors:
    print("SCHEMA_CHECK_FAIL")
    print("\n".join(errors[:200]))
    sys.exit(1)
print("SCHEMA_CHECK_PASS")
'@ | E:\anaconda\envs\pytorch_new\python.exe -
```

## 6. No-NaN / Safety Log 检查计划

### 6.1 NaN 分类规则

所有 final 表都必须把 NaN 分类为以下之一：

| `nan_class` | 含义 | 是否通过 |
|---|---|---|
| `none` | 字段存在且 finite | 通过 |
| `not_applicable` | 结构性无定义，例如非 fault scenario 的 fault delay | 可通过，但必须解释 |
| `failure` | run 失败导致 metric 不可用 | 不通过，计入 failure rate |
| `missing` | runner/log/diagnostic 缺字段或缺文件 | 不通过，视为导出失败 |

禁止把 `missing` 或 `failure` NaN 当作 0、均值插补或删除行。

### 6.2 E7 safety gate

对每个 E7 `scenario/method/seed`：

- `force_norm_peak`、`force_norm_rms`、`force_norm_rate_peak` 必须 finite 且非负。
- `corner_load_spread_peak` 必须 finite；若 payload/corner 无定义，必须显式 `not_applicable`，但 E7 正文 safety 图不可用。
- `connection_max_utilization` 必须 finite；`connection_violation_count` 必须为整数且 `>=0`。
- `payload_force.csv` 和 `connection.csv` 必须存在，行数非零。
- 任何 `connection_max_utilization > 1` 或 `connection_violation_count > 0` 必须保留并进入 safety/failure accounting，不得剔除。

### 6.3 E3 certificate gate

对每个 E3 `scenario/method/seed`：

- `certificate.csv` 必须存在，且 `V`、`predicted_upper`、`contraction_margin` finite。
- `certificate_ok` 必须可解析为 bool/0/1。
- `certificate_min_margin`、`certificate_ok_ratio` 与 run-level summary 对得上。
- Worker C 证明字段若要求 `delta_V/decay_rhs/disturbance_term/formula_version`，当前 diagnostics 需要映射或重新导出；否则证书图只能写 empirical certificate diagnostic。

### 6.4 Log safety gate

对 `tf14_remaining_runs.csv` 每一行：

- `log_path` 必须存在且非空。
- log 必须含 run start marker，如 `[remaining] <timestamp> <experiment> seed=... scenario/method`。
- fatal patterns 直接失败：`Traceback`、`RuntimeError`、`ValueError`、`CUDA out of memory`、`nan_safety_field`、`missing_log`、`solver_infeasible`。
- `WARN` 不自动失败，但必须统计；例如 accepted solver warnings 可列为 warning count，并在 figure ledger 中说明。
- 如果 summary 有数值但 log 缺失，该 run 仍按 `missing_log` 失败，除非有 replacement log 和 hash。

### 6.5 Core/figure provenance gate

若正文图使用 timeline 或 trajectory：

- `core_npz` 必须存在。
- 使用到的数组必须 finite，维度与 scenario/method/seed 一致。
- figure ledger 必须记录 `source_csv/source_npz/source_manifest/runner_command/script_hash/generated_at/seed_list/scenario_list/method_set/ci_formula/failure_accounting_rule/nan_gate_result/trace_policy/main_or_stress`。

## 7. Dry-Run 通过后进入 final runs 的 gate

只有全部满足时，main agent 才可进入 final `n>=20` 执行：

| Gate | 通过条件 | 未通过处理 |
|---|---|---|
| G1 static/help | H0-H4 通过；确认 remaining runner CLI；确认 gap runner 不能 help | 不进入 smoke/final |
| G2 T1 baseline | Worker A/B 或主 agent 冻结 `Frozen_AKE` 为 `AKE-R/AKE-A/AKE-M` 之一，含 config hash、budget、seed policy | 暂停所有 final statistics |
| G3 NonKoopman | 至少一个非 Koopman 网络控制 baseline 接入同 scenario/seed/trace/method schema | 主闭环 superiority claim 暂停；E0 final 不应先跑 |
| G4 one-seed/smoke | O1/O2/O3 或 O4 在批准后完成；schema/no-NaN/log gate 通过；无未解释 CSV 字段缺口 | 修 runner/schema，再重做 smoke |
| G5 trace policy | `comm_trace_id/fault_trace_id/topology_trace_id` 或等价 ledger 已冻结，paired seeds 同 trace | 不允许跑 paired final |
| G6 failure accounting | `success/failure_type/path_complete/nan_class` 可从 runner 或派生 ledger 生成 | 不允许生成 final tables |
| G7 resource/snapshot | final 前备份当前 `data/logs/figures`；记录 GPU/环境/Python path；禁止无意 `--force` | 先做 snapshot 和 run ledger |
| G8 figure ledger | 6-8 张正文主图的 ledger 模板已建好，能接收 final outputs | 图可生成但不得编号入正文 |

建议 final 执行顺序：

1. 冻结 T1 + NonKoopman + trace/failure schema。
2. 跑最小 O1/O3 safety/certificate smoke，并完成 schema/no-NaN/log validation。
3. 跑 E0 final，先建立主闭环 T2 骨架。
4. 跑 E3/E7 final，尽早暴露 safety/certificate NaN 和 log 问题。
5. 跑 E2 final ablation。
6. 仅在 final CSV/schema/no-NaN 通过后运行 gap-closure figure regeneration。

## 8. 当前不可作为 final 的内容

- `tf14_final_gap_closure_20260509/source/E1_koopman_prediction_validation.csv` 来自 cached offline screening；不能替代 fresh E1 multi-training-seed final。
- `tf14_remaining_experiments_20260509` 当前 manifest `minimum_group_n=1`；只可作为 smoke/schema evidence。
- 旧 `dlc_*` scenario rows 不得混入新 final `sine_*` scenario gate，除非 ledger 明确版本映射和复跑策略。
- gap closure runner 会写图和复制文件；它不是 validation-only 工具，不能用于 dry-run。

## 9. Worker D 交付状态

本轮未运行任何实验，未执行 help/smoke/final 命令。本文仅给出安全命令候选、schema validation 计划和 gate。下一步应由 main agent 在 G1-G8 条件满足后，按批准范围执行 H/O/final 命令。
