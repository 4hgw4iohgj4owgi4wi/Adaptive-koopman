"""Independent EXP-R2 section 18.7 actuator-discretization audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .actuator_discretization import SOURCE_RAW_SHA256, UPDATE_INTERVALS, WINDOWS
from .cli import save, sha


LABELS = {0.002: "2ms", 0.001: "1ms", 0.0005: "0.5ms"}


def _load(folder: Path):
    arrays = {}
    for stem in ("updates", "control_end", "substeps"):
        with np.load(folder / f"{stem}.npz", allow_pickle=False) as data:
            arrays[stem] = (data["values"], {str(name): index for index, name in enumerate(data["columns"])})
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    return arrays, metrics


def _audit(folder: Path, window: str, update_s: float):
    arrays, metrics = _load(folder)
    updates, update_columns = arrays["updates"]
    controls, control_columns = arrays["control_end"]
    substeps, sub_columns = arrays["substeps"]
    expected_controls = int(round(WINDOWS[window][1] / 0.02))
    expected_updates = int(round(WINDOWS[window][1] / update_s))
    point = float(max(np.max(updates[:, [update_columns[f"point_force{i}"] for i in range(4)]]), np.max(substeps[:, [sub_columns[f"force_peak{i}"] for i in range(4)]])))
    tire = float(max(np.max(updates[:, [update_columns[f"tire_utilization{i}"] for i in range(4)]]), np.max(substeps[:, [sub_columns[f"tire_utilization{i}"] for i in range(4)]])))
    support = float(min(np.min(updates[:, [update_columns[f"support_load{i}"] for i in range(4)]]), np.min(substeps[:, [sub_columns[f"support_load{i}"] for i in range(4)]])))
    source_diff = metrics.get("source_replay_max_abs_difference")
    checks = {
        "required_files": all((folder / name).is_file() for name in ("updates.npz", "control_end.npz", "substeps.npz", "metrics.json", "status.json")),
        "finite_arrays": all(np.all(np.isfinite(values)) for values, _ in arrays.values()),
        "identity": metrics.get("window") == window and metrics.get("actuator_update_s") == update_s and metrics.get("plant_max_step_s") == 0.0005 and metrics.get("source_raw_sha256") == SOURCE_RAW_SHA256,
        "complete": metrics.get("status") == "COMPLETED" and metrics.get("trajectory_completed") and len(controls) == expected_controls and len(updates) == expected_updates,
        "time_closure": abs(float(np.sum(substeps[:, sub_columns["dt_s"]])) - WINDOWS[window][1]) <= 1e-12,
        "actual_force_tire_support": point <= 15000.0 + 1e-6 and tire <= 1.0 + 1e-9 and support >= 0.0,
        "two_ms_reproduces_frozen_source": update_s != 0.002 or (source_diff is not None and source_diff <= 1e-12),
    }
    terminal = controls[-1, [control_columns["x24"], control_columns["x25"], control_columns["x26"]]]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "point_force_peak4_n": metrics["point_force_peak4_n"],
        "force_impulse4x2_ns": metrics["force_impulse4x2_ns"],
        "terminal_payload_position_m": terminal[:2].tolist(),
        "terminal_payload_heading_rad": float(terminal[2]),
        "maximum_tire_utilization": tire,
        "minimum_support_load_n": support,
        "source_replay_max_abs_difference": source_diff,
    }


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    audits, pairs = {}, []
    for window in WINDOWS:
        values = {}
        for update_s in UPDATE_INTERVALS:
            label = LABELS[update_s]
            row = _audit(root / f"{window}_{label}", window, update_s)
            audits[f"{window}_{label}"] = row
            values[label] = row
        for coarse, fine in (("2ms", "1ms"), ("1ms", "0.5ms")):
            a, b = values[coarse], values[fine]
            peak_a, peak_b = np.asarray(a["point_force_peak4_n"]), np.asarray(b["point_force_peak4_n"])
            impulse_a, impulse_b = np.asarray(a["force_impulse4x2_ns"]), np.asarray(b["force_impulse4x2_ns"])
            peak_relative = float(np.max(np.abs(peak_a - peak_b) / np.maximum(np.abs(peak_b), 1.0)))
            impulse_relative = float(np.max(np.linalg.norm(impulse_a - impulse_b, axis=1) / np.maximum(np.linalg.norm(impulse_b, axis=1), 1.0)))
            terminal_position = float(np.linalg.norm(np.asarray(a["terminal_payload_position_m"]) - np.asarray(b["terminal_payload_position_m"])))
            terminal_heading = float(np.rad2deg(abs((a["terminal_payload_heading_rad"] - b["terminal_payload_heading_rad"] + np.pi) % (2.0 * np.pi) - np.pi)))
            decisive = fine == "0.5ms"
            gate_pass = bool(peak_relative <= 0.02 and impulse_relative <= 0.02 and terminal_position <= 0.001 and terminal_heading <= 0.01) if decisive else None
            pairs.append({
                "window": window,
                "pair": f"{coarse}_to_{fine}",
                "peak_max_relative": peak_relative,
                "impulse_vector_max_relative": impulse_relative,
                "terminal_payload_position_m": terminal_position,
                "terminal_payload_heading_deg": terminal_heading,
                "registered_gate_applies": decisive,
                "registered_gate_pass": gate_pass,
            })
    evidence_pass = all(row["status"] == "PASS" for row in audits.values())
    convergence_pass = all(row["registered_gate_pass"] for row in pairs if row["registered_gate_applies"])
    report = {
        "status": "PASS" if evidence_pass and convergence_pass else "FAIL",
        "scope": "Frozen-command actuator update interval diagnostic with plant max step fixed at 0.5 ms; not a new formal plant identity.",
        "windows": {name: {"start_s": value[0], "duration_s": value[1]} for name, value in WINDOWS.items()},
        "thresholds": {"peak_relative": 0.02, "impulse_vector_relative": 0.02, "terminal_position_m": 0.001, "terminal_heading_deg": 0.01},
        "gate_application": "2ms_to_1ms is diagnostic; 1ms_to_0.5ms is decisive for each window.",
        "audits": audits,
        "pairs": pairs,
        "source_sha256": sha(__file__),
    }
    save(out, "actuator_discretization.json", report)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), constrained_layout=True)
    definitions = (("peak_max_relative", 100.0, "peak difference (%)", 2.0), ("impulse_vector_max_relative", 100.0, "impulse difference (%)", 2.0), ("terminal_payload_position_m", 1000.0, "terminal position (mm)", 1.0), ("terminal_payload_heading_deg", 1.0, "terminal heading (deg)", 0.01))
    for axis, (key, scale, ylabel, limit) in zip(axes.ravel(), definitions):
        for window in WINDOWS:
            rows = [row for row in pairs if row["window"] == window]
            axis.plot([row["pair"] for row in rows], [scale * row[key] for row in rows], marker="o", label=window)
        axis.axhline(limit, color="r", ls="--", label="registered limit")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.suptitle("EXP-R2 actuator-discretization diagnostic")
    fig.savefig(out / "actuator_discretization.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"status": report["status"], "pairs": pairs}))
    if report["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
