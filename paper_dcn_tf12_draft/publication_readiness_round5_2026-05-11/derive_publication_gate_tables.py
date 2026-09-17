from __future__ import annotations

import csv
import hashlib
import json
import math
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round5_2026-05-11"
DEFAULT_STAGE_ROOT = ROOT / "tf14_remaining_experiments_20260509"


PUBLICATION_METHOD_MAP = {
    "baseline": {
        "method_id": "AKE_M_surrogate",
        "baseline_class": "AKE-M",
        "publication_role": "mechanism_surrogate",
    },
    "zoh_consensus_surrogate": {
        "method_id": "ZOH-CONSENSUS-SUR",
        "baseline_class": "nonkoopman_low_order_surrogate",
        "publication_role": "auxiliary_floor_baseline",
    },
    "tf14_main": {
        "method_id": "Proposed_TF14_main",
        "baseline_class": "proposed",
        "publication_role": "proposed_variant",
    },
    "tf14_phase_role": {
        "method_id": "Proposed_TF14_phase_role",
        "baseline_class": "proposed",
        "publication_role": "proposed_full_candidate",
    },
    "tf14_error_match": {
        "method_id": "Proposed_TF14_error_match",
        "baseline_class": "development",
        "publication_role": "development_variant",
    },
    "full_tf14": {
        "method_id": "Proposed_TF14_full",
        "baseline_class": "proposed",
        "publication_role": "proposed_full_candidate",
    },
    "no_bilinear": {
        "method_id": "Ablation_no_bilinear",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_stable_projection": {
        "method_id": "Ablation_no_stable_projection",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_online_adapt": {
        "method_id": "Ablation_no_online_adapt",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_comm_aware": {
        "method_id": "Ablation_no_comm_aware",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_delay_compensation": {
        "method_id": "Ablation_no_delay_compensation",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_fdi": {
        "method_id": "Ablation_no_fdi",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_ftc_switching": {
        "method_id": "Ablation_no_ftc_switching",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_phase_role": {
        "method_id": "Ablation_no_phase_role",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_realtime_scheduler": {
        "method_id": "Ablation_no_realtime_scheduler",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
    "no_ppc_progress_guard": {
        "method_id": "Ablation_no_ppc_progress_guard",
        "baseline_class": "ablation",
        "publication_role": "ablation",
    },
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_nan_like(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    try:
        return math.isnan(float(text))
    except ValueError:
        return text.lower() in {"nan", "none", "null"}


def classify_nan(row: dict[str, str], cols: list[str]) -> str:
    missing_cols = [c for c in cols if c not in row]
    if missing_cols:
        return "missing"
    if any(is_nan_like(row.get(c)) for c in cols):
        return "failure"
    return "none"


def derive_success(row: dict[str, str]) -> tuple[int, str]:
    full_path = as_float(row.get("full_path_reached"), 0.0)
    fail_total = as_float(row.get("fail_total"), 0.0)
    cert_ok = as_float(row.get("certificate_ok_ratio"), math.nan)
    if full_path < 0.5:
        return 0, "path_incomplete"
    if fail_total > 0:
        return 0, "fail_count_nonzero"
    if not math.isnan(cert_ok) and cert_ok < 0.5:
        return 0, "certificate_low"
    return 1, "none"


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive publication-gate tables from a TF14 remaining experiment stage.")
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    out_dir = args.out_dir
    data_dir = args.stage_root / "data"
    runs_csv = data_dir / "tf14_remaining_runs.csv"
    summary_csv = data_dir / "tf14_remaining_summary.csv"
    manifest_json = data_dir / "tf14_remaining_manifest.json"

    out_dir.mkdir(parents=True, exist_ok=True)
    run_rows, run_cols = read_csv(runs_csv)
    summary_rows, summary_cols = read_csv(summary_csv)
    manifest = json.loads(manifest_json.read_text(encoding="utf-8")) if manifest_json.exists() else {}

    safety_cols = [
        "force_norm_peak",
        "force_norm_rate_rms",
        "connection_max_utilization",
        "connection_violation_count",
        "corner_load_spread_peak",
    ]

    normalized: list[dict[str, Any]] = []
    for row in run_rows:
        method = row.get("method", "")
        info = PUBLICATION_METHOD_MAP.get(
            method,
            {
                "method_id": method or "unknown",
                "baseline_class": "unknown",
                "publication_role": "unknown",
            },
        )
        info = {
            "method_id": row.get("method_id") or info["method_id"],
            "baseline_class": row.get("baseline_class") or info["baseline_class"],
            "publication_role": row.get("publication_role") or info["publication_role"],
        }
        derived_success, derived_failure_type = derive_success(row)
        success_raw = as_float(row.get("success"), math.nan)
        success = int(success_raw) if math.isfinite(success_raw) else derived_success
        failure_type = row.get("failure_type") or derived_failure_type
        nan_class = row.get("nan_class") or classify_nan(row, safety_cols)
        if nan_class != "none" and row.get("experiment") == "E7":
            success = 0
            failure_type = f"safety_nan_{nan_class}"
        normalized.append(
            {
                "experiment_id": row.get("experiment", ""),
                "scenario": row.get("scenario", ""),
                "method": method,
                **info,
                "seed": row.get("seed", ""),
                "comm_trace_id": row.get("comm_trace_id") or f"PENDING_COMM_TRACE_{row.get('scenario','')}_{row.get('seed','')}",
                "fault_trace_id": row.get("fault_trace_id") or f"PENDING_FAULT_TRACE_{row.get('scenario','')}_{row.get('seed','')}",
                "topology_trace_id": row.get("topology_trace_id") or f"PENDING_TOPOLOGY_TRACE_{row.get('scenario','')}_{row.get('seed','')}",
                "trace_id_status": row.get("trace_id_status", "pending"),
                "success": success,
                "failure_type": failure_type,
                "nan_class": nan_class,
                "rmse_y": row.get("rmse_lat_mean", row.get("RMSE_y", "")),
                "rmse_s": row.get("rmse_s_mean", row.get("rmse_long_mean", row.get("RMSE_s", ""))),
                "full_path_reached": row.get("full_path_reached", ""),
                "constraint_violation_count": row.get("constraint_violation_count", row.get("connection_violation_count", "")),
                "fallback_count": row.get("fallback_count", "MISSING"),
                "intervention_count": row.get("intervention_count", "MISSING"),
                "certificate_ok_ratio": row.get("certificate_ok_ratio", ""),
                "certificate_min_margin": row.get("certificate_min_margin", ""),
                "force_norm_peak": row.get("force_norm_peak", ""),
                "force_norm_rate_rms": row.get("force_norm_rate_rms", ""),
                "connection_util_max": row.get("connection_util_max", row.get("connection_max_utilization", "")),
                "connection_violation_count": row.get("connection_violation_count", ""),
                "corner_load_spread_peak": row.get("corner_load_spread_peak", ""),
                "core_npz": row.get("core_npz", ""),
                "diagnostics_dir": row.get("diagnostics_dir", ""),
                "source_row_status": "runner_exported_with_provenance" if row.get("method_id") else "derived_from_existing_smoke_or_partial",
            }
        )

    write_csv(out_dir / "T2_T3_T5_normalized_existing_runs.csv", normalized)

    group_counts: Counter[tuple[str, str, str]] = Counter()
    group_success: Counter[tuple[str, str, str]] = Counter()
    group_runtime_exceptions: Counter[tuple[str, str, str]] = Counter()
    for row in normalized:
        key = (str(row["experiment_id"]), str(row["scenario"]), str(row["method_id"]))
        group_counts[key] += 1
        if int(row.get("success", 0) or 0) == 1:
            group_success[key] += 1
        if str(row.get("failure_type", "")) == "runtime_exception":
            group_runtime_exceptions[key] += 1

    group_rows: list[dict[str, Any]] = []
    for (experiment, scenario, method_id), n in sorted(group_counts.items()):
        num_success = group_success[(experiment, scenario, method_id)]
        num_runtime_exception = group_runtime_exceptions[(experiment, scenario, method_id)]
        group_rows.append(
            {
                "experiment_id": experiment,
                "scenario": scenario,
                "method_id": method_id,
                "num_runs": n,
                "num_success": num_success,
                "success_rate": num_success / n if n else 0.0,
                "num_runtime_exception": num_runtime_exception,
                "n20_ready": int(n >= 20),
            }
        )
    write_csv(out_dir / "group_count_gate_existing_runs.csv", group_rows)

    methods = sorted({r["method_id"] for r in normalized})
    has_ake_a = any(str(r["method_id"]).upper() in {"AKE-A", "AKE_A", "ORIGINAL_AKE_A"} or str(r["baseline_class"]).upper() == "AKE-A" for r in normalized)
    has_ake_m = any("AKE" in str(r["method_id"]).upper() or "AKE" in str(r["baseline_class"]).upper() for r in normalized)
    has_nonkoopman_validated = any(str(r["baseline_class"]).lower() in {"physical_dmpc", "zoh_consensus_mpc", "nonkoopman_physical_mpc"} for r in normalized)
    has_nonkoopman_surrogate = any(str(r["baseline_class"]).lower() == "nonkoopman_low_order_surrogate" for r in normalized)
    trace_values = [
        str(r.get(key, ""))
        for r in normalized
        for key in ("comm_trace_id", "fault_trace_id", "topology_trace_id")
    ]
    has_pending_trace = any((not value) or value.startswith("PENDING_") for value in trace_values)
    deterministic_trace_only = any(str(r.get("trace_id_status", "")).startswith("deterministic_") for r in normalized)
    required_success_rows = [
        r
        for r in normalized
        if str(r.get("publication_role", "")) not in {"auxiliary_floor_baseline", "ablation"}
    ]
    failed_required_rows = [r for r in required_success_rows if int(r.get("success", 0) or 0) != 1]
    t1_rows = [
        {
            "gate": "AKE_status",
            "status": "PASS" if has_ake_a else ("PARTIAL" if has_ake_m else "FAIL"),
            "detail": "已包含可信 AKE-A 行" if has_ake_a else ("已有 AKE 家族 surrogate，但仍缺原文 AKE-A" if has_ake_m else "没有 AKE 家族 baseline 行"),
        },
        {
            "gate": "NonKoopman_baseline",
            "status": "PASS" if has_nonkoopman_validated else ("PARTIAL" if has_nonkoopman_surrogate else "FAIL"),
            "detail": "已包含可信非 Koopman 物理/ZOH MPC 行" if has_nonkoopman_validated else ("只有低阶 ZOH surrogate，仍不能替代可发表的物理 DMPC baseline" if has_nonkoopman_surrogate else "当前 CSV 中没有物理模型 DMPC 或 ZOH consensus MPC 方法行"),
        },
        {
            "gate": "paired_n20",
            "status": "PASS" if group_counts and min(group_counts.values()) >= 20 else "FAIL",
            "detail": f"min_group_n={min(group_counts.values()) if group_counts else 0}",
        },
        {
            "gate": "required_method_success",
            "status": "PASS" if not failed_required_rows else "FAIL",
            "detail": "所有非辅助底线方法均成功" if not failed_required_rows else f"{len(failed_required_rows)} 个非辅助方法行失败或崩溃",
        },
        {
            "gate": "trace_ids",
            "status": "FAIL" if has_pending_trace else ("PARTIAL" if deterministic_trace_only else "PASS"),
            "detail": "仍存在 PENDING 占位 trace id" if has_pending_trace else ("runner 已输出确定性工况/seed trace id，但仍未链接外部原始 trace 文件" if deterministic_trace_only else "runner 原生 trace id 已存在"),
        },
        {
            "gate": "method_set_seen",
            "status": "INFO",
            "detail": "; ".join(methods),
        },
    ]
    write_csv(out_dir / "T1_gate_status_existing_runs.csv", t1_rows)

    experiments_seen = {str(r.get("experiment_id", "")) for r in normalized}
    final_statistics_ready = bool(manifest.get("final_statistics_ready")) and bool(group_counts) and min(group_counts.values()) >= 20

    def figure_status(required_experiment: str) -> tuple[str, str]:
        if required_experiment not in experiments_seen:
            return "not_present_in_this_stage", f"run {required_experiment} stage first"
        if final_statistics_ready:
            return "paired_n20_ready", "T1 baseline fidelity + trace provenance + metric direction"
        return "representative_or_partial_only", "n>=20 + T1 + method provenance"

    figure_rows = [
        {
            "figure_slug": "R0_main_comparison_summary",
            "paper_slot": "pending_main_candidate",
            "main_or_supplement": "pending",
            "source_data_path": str(summary_csv),
            "source_hash": file_hash(summary_csv),
            "evidence_status": figure_status("E0")[0],
            "blocking_gate": figure_status("E0")[1],
        },
        {
            "figure_slug": "R2_module_ablation_heatmap",
            "paper_slot": "pending_main_candidate",
            "main_or_supplement": "pending",
            "source_data_path": str(summary_csv),
            "source_hash": file_hash(summary_csv),
            "evidence_status": figure_status("E2")[0],
            "blocking_gate": figure_status("E2")[1],
        },
        {
            "figure_slug": "R3_certificate_statistics",
            "paper_slot": "pending_certificate_candidate",
            "main_or_supplement": "pending",
            "source_data_path": str(summary_csv),
            "source_hash": file_hash(summary_csv),
            "evidence_status": figure_status("E3")[0],
            "blocking_gate": figure_status("E3")[1],
        },
        {
            "figure_slug": "R7_payload_connection_safety",
            "paper_slot": "pending_safety_candidate",
            "main_or_supplement": "pending",
            "source_data_path": str(runs_csv),
            "source_hash": file_hash(runs_csv),
            "evidence_status": figure_status("E7")[0],
            "blocking_gate": figure_status("E7")[1],
        },
    ]
    write_csv(out_dir / "figure_provenance_ledger_existing_runs.csv", figure_rows)

    report = [
        "# 发表 Gate 派生表记录",
        "",
        f"- 生成时间：`{datetime.now().isoformat(timespec='seconds')}`",
        f"- run 明细来源：`{runs_csv}`",
        f"- summary 来源：`{summary_csv}`",
        f"- manifest 中 final_statistics_ready：`{manifest.get('final_statistics_ready')}`",
        f"- manifest 中 minimum_group_n：`{manifest.get('minimum_group_n')}`",
        "",
        "## 输出文件",
        "- `T2_T3_T5_normalized_existing_runs.csv`",
        "- `group_count_gate_existing_runs.csv`",
        "- `T1_gate_status_existing_runs.csv`",
        "- `figure_provenance_ledger_existing_runs.csv`",
        "",
        "## Gate 摘要",
    ]
    for row in t1_rows:
        report.append(f"- {row['gate']}: {row['status']} ({row['detail']})")
    report.append("")
    report.append("## 使用限制")
    if final_statistics_ready:
        report.append("当前表已满足 paired n>=20 的基本统计门槛；仍需结合 T1 baseline fidelity、trace provenance 和具体指标方向判断能否写入主文。")
    else:
        report.append("这些表由当前已有的 smoke 或部分数据派生，主要用于检查 schema、证据链和 gate 状态；在 n=20 正式批次完成前，不能作为论文最终证据。")
    (out_dir / "round5_derived_gate_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(out_dir / "round5_derived_gate_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
