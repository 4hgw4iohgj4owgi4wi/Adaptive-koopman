"""Pre-N1 no-op gate for the R5 strict chain.

The strict N0 protocol names its same-backend full-state baseline and the exact raw
columns that must remain unchanged.  This tool compares those persisted trajectories,
checks the two single-run audits and figure manifests, and emits its own JSON and
PNG/SVG evidence.  N1 must not be frozen until this gate and its visual QA pass.
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_raw(path: Path) -> tuple[np.ndarray, dict[str, int]]:
    with np.load(path, allow_pickle=False) as data:
        values = data["values"].copy()
        columns = [str(value) for value in data["columns"]]
    return values, {name: index for index, name in enumerate(columns)}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = Path(args.protocol).resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = read_json(protocol_path)
    if protocol.get("scope") != "R5_LEGAL_INFORMATION" or protocol.get("run", {}).get("noise") != "none":
        raise ValueError("N0_PROTOCOL_REQUIRED")

    out = (paper / args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    baseline_rel = protocol["noiseless_no_op_gate"]["baseline"]
    n0_rel = protocol["run"]["output"]
    baseline = paper / baseline_rel
    n0 = paper / n0_rel
    required = []
    for run in (baseline, n0):
        required.extend([
            run / "raw.npz",
            run / "metrics.json",
            run / "single_run_audit.json",
            run / "figures/figure_manifest.json",
        ])
    missing = [str(path.relative_to(paper)).replace("\\", "/") for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("PREREQUISITE_NOT_READY:" + ",".join(missing))

    baseline_raw, baseline_index = load_raw(baseline / "raw.npz")
    n0_raw, n0_index = load_raw(n0 / "raw.npz")
    baseline_metrics = read_json(baseline / "metrics.json")
    n0_metrics = read_json(n0 / "metrics.json")
    baseline_audit = read_json(baseline / "single_run_audit.json")
    n0_audit = read_json(n0 / "single_run_audit.json")
    baseline_figure = read_json(baseline / "figures/figure_manifest.json")
    n0_figure = read_json(n0 / "figures/figure_manifest.json")

    gate = protocol["noiseless_no_op_gate"]
    whitelist = list(gate["whitelist"])
    threshold = float(gate["threshold_absolute"])
    absent = [name for name in whitelist if name not in baseline_index or name not in n0_index]
    same_rows = baseline_raw.shape[0] == n0_raw.shape[0]
    if absent or not same_rows:
        column_differences = {name: None for name in whitelist}
        per_tick = np.asarray([], dtype=float)
        maximum = float("inf")
    else:
        difference = np.abs(
            baseline_raw[:, [baseline_index[name] for name in whitelist]]
            - n0_raw[:, [n0_index[name] for name in whitelist]]
        )
        maxima = difference.max(axis=0)
        column_differences = {name: float(value) for name, value in zip(whitelist, maxima)}
        per_tick = difference.max(axis=1)
        maximum = float(maxima.max())

    time_difference = float("inf")
    if same_rows and "time_s" in baseline_index and "time_s" in n0_index:
        time_difference = float(np.abs(
            baseline_raw[:, baseline_index["time_s"]] - n0_raw[:, n0_index["time_s"]]
        ).max())

    checks = [
        {"check": "baseline_completed", "pass": baseline_metrics.get("status") == "COMPLETED"},
        {"check": "n0_completed", "pass": n0_metrics.get("status") == "COMPLETED"},
        {"check": "baseline_single_run_audit_pass", "pass": baseline_audit.get("status") == "PASS_SINGLE_RUN_AUDIT"},
        {"check": "n0_single_run_audit_pass", "pass": n0_audit.get("status") == "PASS_SINGLE_RUN_AUDIT"},
        {"check": "baseline_figure_qa_pass", "pass": baseline_figure.get("figure_status") == "PASS_VISUAL_QA"},
        {"check": "n0_figure_qa_pass", "pass": n0_figure.get("figure_status") == "PASS_VISUAL_QA"},
        {"check": "row_counts_match", "pass": same_rows},
        {"check": "all_whitelist_columns_present", "pass": not absent},
        {"check": "solver_settings_identical", "pass": baseline_metrics.get("solver_settings") == n0_metrics.get("solver_settings")},
        {"check": "acceptance_tolerances_identical", "pass": baseline_metrics.get("acceptance_tolerances") == n0_metrics.get("acceptance_tolerances")},
        {"check": "time_is_bitwise_identical", "pass": time_difference == 0.0},
        {"check": "n0_no_op_within_absolute_threshold", "pass": maximum <= threshold},
    ]
    status = "PASS_R5_STRICT_N0_NO_OP" if all(item["pass"] for item in checks) else "FAIL_R5_STRICT_N0_NO_OP"

    out.mkdir(parents=True)
    figures = out / "figures"
    figures.mkdir()
    report = {
        "status": status,
        "protocol": str(protocol_path.relative_to(paper)).replace("\\", "/"),
        "protocol_sha256": args.protocol_sha.lower(),
        "baseline": baseline_rel,
        "n0": n0_rel,
        "threshold_absolute": threshold,
        "maximum_absolute_difference": maximum,
        "time_maximum_absolute_difference": time_difference,
        "columns_compared": len(whitelist),
        "columns_exactly_identical": sum(value == 0.0 for value in column_differences.values()),
        "missing_columns": absent,
        "column_maximum_absolute_differences": column_differences,
        "checks": checks,
        "claim_boundary": ("Same-backend, same-controller deterministic no-op comparison between the strict full-state "
                           "baseline and strict legal-information N0. It does not evaluate measurement noise."),
    }
    (out / "no_op.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    plot_values = np.asarray([
        value if value is not None and np.isfinite(value) else np.nan
        for value in column_differences.values()
    ], dtype=float)
    floor = min(threshold, 1e-18) if threshold > 0 else 1e-18
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), constrained_layout=True)
    axes[0].plot(np.arange(len(whitelist)), np.maximum(plot_values, floor), "o", markersize=4)
    axes[0].axhline(threshold, color="red", linestyle="--", label=f"gate {threshold:.1e}")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("column max abs difference")
    axes[0].set_xlabel("whitelist column index")
    axes[0].grid(True, which="both", alpha=0.25)
    axes[0].legend()
    if per_tick.size:
        axes[1].plot(np.arange(per_tick.size), np.maximum(per_tick, floor), linewidth=1.0)
    axes[1].axhline(threshold, color="red", linestyle="--", label=f"gate {threshold:.1e}")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("per-tick max abs difference")
    axes[1].set_xlabel("tick")
    axes[1].grid(True, which="both", alpha=0.25)
    axes[1].legend()
    fig.suptitle(f"R5 strict N0 no-op gate — {status}\n{len(whitelist)} columns, max={maximum:.3e}")
    fig.savefig(figures / "r5_strict_n0_no_op.png", dpi=220)
    fig.savefig(figures / "r5_strict_n0_no_op.svg")
    plt.close(fig)

    manifest = {
        "science_status": status,
        "figure_status": "PENDING_VISUAL_QA",
        "figures": ["figures/r5_strict_n0_no_op.png", "figures/r5_strict_n0_no_op.svg"],
        "generating_script": "tools/r5_strict_no_op_gate.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [
            {"path": f"{baseline_rel}/raw.npz", "sha256": sha(baseline / "raw.npz")},
            {"path": f"{n0_rel}/raw.npz", "sha256": sha(n0 / "raw.npz")},
        ],
        "caption": (f"Strict same-backend N0 no-op comparison across {len(whitelist)} registered columns; "
                    f"maximum absolute difference {maximum:.3e} against {threshold:.1e}."),
    }
    (out / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figures / "README.md").write_text(
        "# R5 strict N0 no-op gate\n\n"
        f"Science status: **{status}**. Figure status: **PENDING_VISUAL_QA**.\n\n"
        "The upper panel reports the maximum difference of each registered column; the lower panel reports the "
        "maximum registered difference at each tick. Values plotted at the numerical floor are exact zeros.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "output": args.out, "maximum_absolute_difference": maximum}, ensure_ascii=False))
    if status != "PASS_R5_STRICT_N0_NO_OP":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
