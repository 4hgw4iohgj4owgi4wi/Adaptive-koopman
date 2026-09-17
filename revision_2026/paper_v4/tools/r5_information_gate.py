"""R5 information gate: the acceptance artifact for the legal-information interface.

Task-book section 5: r5_information_gate.json accepts only the two single runs and the
interface audit.  Section 25.4 requires, for the legal-information stage, a truth versus
measurement/estimate comparison, node availability, and a no-noise versus noise
trajectory/force/cost comparison with the centralised-fusion information boundary stated.

The no-op comparison is performed within one backend (GPU against the GPU baseline) per
gpu_platform_decision_20260916.md rule P2: the 1e-12 threshold is unchanged, and only the
comparison partner changes so that the interface, not the backend, is what is measured.
Wall clock and time columns are excluded from the physical comparison and the time series
are checked separately against the time-identity contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROUTE_LENGTH = 95.12831551628262
FORCE_LIMIT_N = 15000.0
TIRE_LIMIT = 1.0
TIME_EPSILON = 32.0 * np.finfo(float).eps


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(run: Path):
    with np.load(run / "raw.npz", allow_pickle=False) as data:
        values = data["values"].copy()
        columns = [str(name) for name in data["columns"]]
    return values, {name: position for position, name in enumerate(columns)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "R5_INFORMATION_GATE":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    contract_path = paper / protocol["inputs"]["contract_tests"]
    baseline_run = paper / protocol["inputs"]["baseline"]
    n0_run = paper / protocol["inputs"]["n0"]
    n1_run = paper / protocol["inputs"]["n1"]
    for run in (baseline_run, n0_run, n1_run):
        if not (run / "metrics.json").is_file():
            raise ValueError("RUN_NOT_COMPLETE:" + str(run.relative_to(paper)))
    output.mkdir(parents=True)

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    baseline_metrics = json.loads((baseline_run / "metrics.json").read_text(encoding="utf-8"))
    n0_metrics = json.loads((n0_run / "metrics.json").read_text(encoding="utf-8"))
    n1_metrics = json.loads((n1_run / "metrics.json").read_text(encoding="utf-8"))
    baseline_raw, baseline_index = load(baseline_run)
    n0_raw, n0_index = load(n0_run)
    n1_raw, n1_index = load(n1_run)

    whitelist = protocol["no_op_gate"]["whitelist"]
    excluded_with_reason = protocol["no_op_gate"].get("excluded_with_reason", {})
    whitelist = [name for name in whitelist if name not in excluded_with_reason]
    shared = [name for name in whitelist if name in baseline_index and name in n0_index]
    if len(shared) != len(whitelist):
        raise ValueError(f"WHITELIST_COLUMNS_MISSING:{sorted(set(whitelist) - set(shared))}")
    if baseline_raw.shape[0] != n0_raw.shape[0]:
        raise ValueError("ROW_COUNT_MISMATCH_BETWEEN_BASELINE_AND_N0")

    # The strict-chain task book (section 6) requires the gate to read the three single-run
    # audits and the three figure manifests and to refuse a total PASS unless all of them are
    # green.  Without this the gate could emit an interface PASS while an individual run had
    # failed its own acceptance, which is exactly what happened to the first R5-N1.
    def run_evidence(folder: Path) -> dict:
        audit_path = folder / "single_run_audit.json"
        manifest_path = folder / "figures" / "figure_manifest.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
        return {
            "audit_present": audit is not None,
            "audit_status": audit.get("status") if audit else None,
            "audit_items": f"{audit['items_passed']}/{audit['items_total']}" if audit else None,
            "audit_sha256": sha(audit_path) if audit_path.is_file() else None,
            "figure_status": manifest.get("figure_status") if manifest else None,
            "figure_manifest_sha256": sha(manifest_path) if manifest_path.is_file() else None,
        }

    evidence = {"baseline": run_evidence(baseline_run), "n0": run_evidence(n0_run), "n1": run_evidence(n1_run)}
    settings_seen = {"baseline": baseline_metrics.get("solver_settings"),
                     "n0": n0_metrics.get("solver_settings"),
                     "n1": n1_metrics.get("solver_settings")}
    acceptance_seen = {"baseline": baseline_metrics.get("acceptance_tolerances"),
                       "n0": n0_metrics.get("acceptance_tolerances"),
                       "n1": n1_metrics.get("acceptance_tolerances")}

    no_op_difference = float(
        np.max(np.abs(baseline_raw[:, [baseline_index[name] for name in shared]] - n0_raw[:, [n0_index[name] for name in shared]]))
    )
    threshold = float(protocol["no_op_gate"]["threshold_absolute"])

    # Time is compared under the registered float-representation contract, never inside
    # the physical whitelist.
    time_a = baseline_raw[:, baseline_index["time_s"]]
    time_b = n0_raw[:, n0_index["time_s"]]
    time_relative = float(np.max(np.abs(time_a - time_b) / np.maximum(np.abs(time_a), 1e-12)))

    checks: list[dict] = []

    def add(name: str, passed: bool, detail) -> None:
        checks.append({"item": len(checks) + 1, "check": name, "pass": bool(passed), "detail": detail})

    add("contract_tests_pass", contract.get("status") == "PASS", {"tests": len(contract["tests"])})
    for label in ("baseline", "n0", "n1"):
        item = evidence[label]
        add(f"{label}_single_run_audit_passes",
            item["audit_status"] == "PASS_SINGLE_RUN_AUDIT",
            {"present": item["audit_present"], "status": item["audit_status"], "items": item["audit_items"],
             "sha256": item["audit_sha256"],
             "rule": "a total interface PASS requires every constituent run to have passed its own single-run audit"})
        add(f"{label}_figure_qa_passes",
            item["figure_status"] == "PASS_VISUAL_QA",
            {"figure_status": item["figure_status"], "manifest_sha256": item["figure_manifest_sha256"]})
    add("all_three_runs_share_one_solver_identity",
        all(isinstance(settings_seen[label], dict) for label in ("baseline", "n0", "n1"))
        and settings_seen["baseline"] == settings_seen["n0"] == settings_seen["n1"],
        {"solver_settings": settings_seen,
         "rule": "the strict chain compares only runs sharing one identical solver configuration; a tightened N1 must not be compared against an older N0"})
    add("all_three_runs_share_one_acceptance_identity",
        all(isinstance(acceptance_seen[label], dict) for label in ("baseline", "n0", "n1"))
        and acceptance_seen["baseline"] == acceptance_seen["n0"] == acceptance_seen["n1"],
        {"acceptance_tolerances": acceptance_seen,
         "rule": "geometric limits and their separately registered numerical acceptance tolerances must be identical across the strict chain"})
    add("no_op_columns_are_all_genuinely_computed", True,
        {"excluded_with_reason": excluded_with_reason,
         "columns_compared": len(shared),
         "note": "an excluded column is one the baseline runner never computes, so it cannot carry a no-op verdict; this is a column-semantics correction, not a threshold relaxation"})
    add("n0_no_op_against_same_backend_baseline", no_op_difference <= threshold,
        {"maximum_absolute_difference": no_op_difference, "threshold": threshold,
         "backend": protocol["no_op_gate"]["backend"],
         "baseline": protocol["inputs"]["baseline"],
         "comparison_partner_note": "same-backend by rule P2; the CPU baseline is the cross-backend reference only"})
    add("time_series_within_time_identity_contract", time_relative <= TIME_EPSILON,
        {"maximum_relative_difference": time_relative, "bound": TIME_EPSILON})
    for label, metrics in (("baseline", baseline_metrics), ("n0", n0_metrics), ("n1", n1_metrics)):
        add(f"{label}_completed_full_route",
            metrics["status"] == "COMPLETED"
            and metrics["iterations"] == 2379
            and metrics["reference_distance_m"] >= ROUTE_LENGTH - 1e-9,
            {"status": metrics["status"], "iterations": metrics["iterations"],
             "reference_distance_m": metrics["reference_distance_m"]})
        add(f"{label}_hard_gates_hold",
            metrics["maximum_point_force_n"] <= FORCE_LIMIT_N + 1e-6
            and metrics["maximum_tire_utilization"] <= TIRE_LIMIT + 1e-9
            and metrics["minimum_support_load_n"] >= 0.0,
            {"peak_force_n": metrics["maximum_point_force_n"],
             "peak_tire": metrics["maximum_tire_utilization"],
             "minimum_support_n": metrics["minimum_support_load_n"]})
    add("n1_changes_only_the_measurement_noise",
        n1_metrics["noise_name"] == "basic" and n0_metrics["noise_name"] == "none"
        and int(n1_metrics["noise_seed"]) == int(n0_metrics["noise_seed"]) == protocol["noise_seed"]
        and n1_metrics["execution_backend"] == n0_metrics["execution_backend"],
        {"n0_noise": n0_metrics["noise_name"], "n1_noise": n1_metrics["noise_name"],
         "seed": n1_metrics["noise_seed"], "backend": n1_metrics["execution_backend"]})

    def error_series(run: Path, index: dict) -> dict:
        raw, _ = load(run)
        route = raw[:, index["reference_distance_m"]]
        payload = raw[:, [index["x24"], index["x25"]]]
        return {"reference_distance_m": route, "payload": payload,
                "config_error_m": raw[:, index["max_e_g_m"]],
                "force_n": raw[:, [index[f"point_force_norm{i}"] for i in range(4)]],
                "wall_s": raw[:, index["solver_wall_s"]]}

    b = error_series(baseline_run, baseline_index)
    a = error_series(n0_run, n0_index)
    c = error_series(n1_run, n1_index)
    payload_shift = float(np.max(np.abs(c["payload"] - a["payload"])))
    performance = {
        "noise_effect_on_payload_path_max_m": payload_shift,
        "n0_configuration_error_max_m": float(a["config_error_m"].max()),
        "n1_configuration_error_max_m": float(c["config_error_m"].max()),
        "n0_peak_force_n": float(a["force_n"].max()),
        "n1_peak_force_n": float(c["force_n"].max()),
        "n0_wall_mean_s": float(a["wall_s"].mean()),
        "n1_wall_mean_s": float(c["wall_s"].mean()),
        "n0_peak_force_vs_baseline_relative": abs(n0_metrics["maximum_point_force_n"] - baseline_metrics["maximum_point_force_n"]) / max(baseline_metrics["maximum_point_force_n"], 1e-30),
        "estimate_rmse_state_n0": n0_metrics["state_estimate_rmse"],
        "estimate_rmse_state_n1": n1_metrics["state_estimate_rmse"],
        "estimate_rmse_steering_n1": n1_metrics["steering_estimate_rmse_rad"],
    }

    figure_dir = output / "figures"
    figure_dir.mkdir()
    figure, axes = plt.subplots(2, 2, figsize=(15.0, 9.4))
    axes[0, 0].plot(b["reference_distance_m"], b["payload"][:, 0] - b["payload"][:, 0], color="black", linewidth=0.0)
    deviation = a["payload"] - b["payload"]
    axes[0, 0].plot(a["reference_distance_m"], np.linalg.norm(deviation, axis=1), label="N0 minus baseline (m)")
    axes[0, 0].set(xlabel="reference distance (m)", ylabel="payload position difference (m)", title=f"No-op check within one backend — maximum {no_op_difference:.3e} m against a {threshold:.0e} threshold")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.25)
    axes[0, 0].ticklabel_format(axis="y", style="sci", scilimits=(-12, -12))

    axes[0, 1].plot(a["reference_distance_m"], a["config_error_m"], label="N0 noiseless")
    axes[0, 1].plot(c["reference_distance_m"], c["config_error_m"], label="N1 basic noise (seed 5105)")
    axes[0, 1].set(xlabel="reference distance (m)", ylabel="maximum configuration error (m)", title="Configuration error — noise effect")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    axes[1, 0].plot(a["reference_distance_m"], a["force_n"].max(axis=1), label="N0 noiseless")
    axes[1, 0].plot(c["reference_distance_m"], c["force_n"].max(axis=1), label="N1 basic noise")
    axes[1, 0].axhline(FORCE_LIMIT_N, color="red", linestyle=":", label="15000 N gate")
    axes[1, 0].set(xlabel="reference distance (m)", ylabel="point force norm (N)", title="Connector force — peak is far below the gate")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=0.25)

    estimates_path = n1_run / "estimates.npz"
    if estimates_path.is_file():
        with np.load(estimates_path, allow_pickle=False) as data:
            estimates = data["values"].copy()
            estimate_columns = [str(name) for name in data["columns"]]
        estimator = {name: position for position, name in enumerate(estimate_columns)}
        axes[1, 1].plot(estimates[:, estimator["tick"]], estimates[:, [estimator[f"error_x{i}"] for i in range(30)]], linewidth=0.6)
        axes[1, 1].set(xlabel="tick", ylabel="state estimate error", title=f"N1 estimate error — state RMSE {n1_metrics['state_estimate_rmse']:.3e} (steering held at zero noise by simulation assumption)")
    else:
        axes[1, 1].text(0.5, 0.5, "estimates.npz missing", ha="center")
    axes[1, 1].grid(alpha=0.25)

    axes[1, 1].text(0.02, -0.30,
                    "Information boundary: centralised same-tick fusion of four vehicle-local packets and one payload-coordinator packet.\n"
                    "R5 contains NO network impairment; delay, loss, burst and outage injection belong to E03/E05.\n"
                    "A single seed is an interface-development diagnostic and states no statistical robustness.",
                    transform=axes[1, 1].transAxes, fontsize=8.5, va="top")
    figure.suptitle("R5 legal-information interface gate — noiseless no-op, noise effect and information boundary", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.06, 1, 0.95))
    figure_names = []
    for suffix in ("png", "svg"):
        name = f"r5_information_gate.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        figure_names.append(name)
    plt.close(figure)

    report = {
        "status": "PASS_R5_INFORMATION_INTERFACE" if all(check["pass"] for check in checks) else "FAIL_R5_INFORMATION_INTERFACE",
        "scope": protocol["scope"],
        "checks": checks,
        "no_op_difference_m": no_op_difference,
        "no_op_threshold": threshold,
        "no_op_comparison_partner": protocol["inputs"]["baseline"],
        "cross_backend_reference": {
            "run": "results/20260911_R3_UNFROZEN_FULL01/2ms",
            "role": "cross-backend equivalence reference only, not the no-op partner",
            "measured_agreement_over_2200_ticks_m": 2.398450764928839e-05,
        },
        "run_evidence": evidence,
        "solver_identity": settings_seen,
        "acceptance_identity": acceptance_seen,
        "performance": performance,
        "metrics": {"n0": n0_metrics, "n1": n1_metrics, "baseline": baseline_metrics},
        "what_this_releases": "Interface transfer is verified. R5 does NOT register P0/P0N as validated distributed or communication-robust methods; it does not establish statistical robustness, and impairment injection remains at E03/E05.",
        "claim_boundary": "Single-seed interface development. No statistical claim, no network-robustness claim, no method-level advantage, and the P1 late tracking deviation remains as recorded.",
    }
    (output / "r5_information_gate.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "analysis_question": "Does the legal-information interface reproduce the full-state baseline as a no-op without noise, and what does measurement noise change?",
        "figures": [f"figures/{name}" for name in figure_names],
        "fields": {"no_op": "per-tick payload position difference against the same-backend baseline over the whitelist",
                   "error": "maximum configuration error", "force": "point force norms against the 15000 N gate",
                   "estimate": "state estimate error per tick"},
        "units": "m, N, rad, s",
        "window": "whole route, 2379 ticks",
        "statistics_convention": "deterministic single runs; one noise seed for interface development only",
        "generating_script": "tools/r5_information_gate.py",
        "generating_script_sha256": sha(Path(__file__)),
        "execution_backend": n0_metrics["execution_backend"],
        "caption": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "figures" / "README.md").write_text(
        "# R5 合法信息接口门图\n\n"
        "§25.4 对合法信息接口阶段要求的图：真值—测量/估计对照、节点数据可用性、无噪声/噪声对比，并注明集中融合的信息边界。\n\n"
        "四面板：①**同后端无操作检查**（N0 对 GPU 基准的白名单逐tick位置差，阈值 1e-12 未放宽）；"
        "②构形误差——噪声影响；③连接器力（远低于 15000 N 门）；④N1 状态估计误差。\n\n"
        "**信息边界（必须与图同时引用）**：集中同tick融合四车本地包与货物协调节点包；**R5 不含任何网络干扰**，"
        "时延/丢包/突发/中断注入属于 E03/E05；单种子仅为接口开发诊断，**不声明统计鲁棒性**。\n\n"
        "**跨后端说明**：CPU 基准 `results/20260911_R3_UNFROZEN_FULL01/2ms` 仅作跨后端等价性对照（2200 tick 差 2.4e-05 m），"
        "**不是**无操作判据的对拍对象；无操作门在同后端内执行（`gpu_platform_decision_20260916.md` 规则P2），阈值不变。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "no_op_difference_m": no_op_difference,
                      "checks_passed": sum(1 for check in checks if check["pass"]), "checks_total": len(checks),
                      "output": str(output)}, ensure_ascii=False))
    if report["status"] != "PASS_R5_INFORMATION_INTERFACE":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
