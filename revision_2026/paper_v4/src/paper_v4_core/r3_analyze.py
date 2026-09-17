"""EXP-R2 R3 numerical pairing for the selected full-route physical-MPC candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .r2c_analyze import audit, load


STEPS = ("2ms", "1ms", "0.5ms")
EXPECTED_MAX_STEP_S = {"2ms": 0.002, "1ms": 0.001, "0.5ms": 0.0005}


def convergence_quantities(folder: Path):
    raw, c, sub, s, metrics, _ = load(folder)
    peaks = np.asarray(
        [
            max(
                np.max(raw[:, c[f"point_force_norm{i}"]]),
                np.max(sub[:, s[f"force_peak{i}"]]),
            )
            for i in range(4)
        ],
        float,
    )
    impulses = np.c_[
        [np.sum(sub[:, s[f"force_impulse_x{i}"]]) for i in range(4)],
        [np.sum(sub[:, s[f"force_impulse_y{i}"]]) for i in range(4)],
    ]
    terminal_position = raw[-1, [c["x24"], c["x25"]]]
    terminal_heading = float(raw[-1, c["x26"]])
    return {
        "peaks_n": peaks,
        "impulses_ns": impulses,
        "terminal_position_m": terminal_position,
        "terminal_heading_rad": terminal_heading,
        "metrics": metrics,
    }


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--lambda-internal", type=float, choices=(1.0, 2.0), required=True)
    parser.add_argument("--candidate-id")
    parser.add_argument("--run", action="append", nargs=2, metavar=("STEP", "FOLDER"), required=True)
    args = parser.parse_args()
    supplied = {step: Path(folder) for step, folder in args.run}
    if set(supplied) != set(STEPS) or len(args.run) != len(STEPS):
        raise SystemExit("Exactly one 2ms, 1ms, and 0.5ms run is required")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    audits = {}
    values = {}
    for step in STEPS:
        row, _ = audit(step, supplied[step])
        expected_step = EXPECTED_MAX_STEP_S[step]
        _, _, _, _, metrics, _ = load(supplied[step])
        row["checks"]["maximum_plant_step_identity"] = bool(
            np.isclose(metrics["maximum_plant_step_s"], expected_step, rtol=0.0, atol=1e-15)
        )
        row["checks"]["selected_lambda_identity"] = bool(
            np.isclose(metrics["lambda_internal"], args.lambda_internal, rtol=0.0, atol=0.0)
        )
        if args.candidate_id is not None:
            row["checks"]["candidate_identity"] = metrics.get("candidate_id") == args.candidate_id
        row["status"] = "PASS" if all(row["checks"].values()) else "FAIL"
        audits[step] = row
        values[step] = convergence_quantities(supplied[step])
    pairs = []
    for coarse, fine in zip(STEPS[:-1], STEPS[1:]):
        a = values[coarse]
        b = values[fine]
        peak_relative = float(
            np.max(np.abs(a["peaks_n"] - b["peaks_n"]) / np.maximum(np.abs(b["peaks_n"]), 1.0))
        )
        impulse_relative = float(
            np.max(
                np.linalg.norm(a["impulses_ns"] - b["impulses_ns"], axis=1)
                / np.maximum(np.linalg.norm(b["impulses_ns"], axis=1), 1.0)
            )
        )
        terminal_position = float(np.linalg.norm(a["terminal_position_m"] - b["terminal_position_m"]))
        terminal_heading = float(
            np.rad2deg(abs((a["terminal_heading_rad"] - b["terminal_heading_rad"] + np.pi) % (2.0 * np.pi) - np.pi))
        )
        gate_applies = fine == "0.5ms"
        gate_pass = bool(
            peak_relative <= 0.02
            and impulse_relative <= 0.02
            and terminal_position <= 0.001
            and terminal_heading <= 0.01
        ) if gate_applies else None
        pairs.append(
            {
                "pair": f"{coarse}_to_{fine}",
                "peak_max_relative": peak_relative,
                "impulse_vector_max_relative": impulse_relative,
                "terminal_payload_position_m": terminal_position,
                "terminal_payload_heading_deg": terminal_heading,
                "registered_gate_applies": gate_applies,
                "registered_gate_pass": gate_pass,
            }
        )
    evidence_pass = all(row["status"] == "PASS" for row in audits.values())
    registered_pair_pass = next(row["registered_gate_pass"] for row in pairs if row["registered_gate_applies"])
    report = {
        "status": "PASS" if evidence_pass and registered_pair_pass else "FAIL",
        "scope": "selected R2c full-route controller candidate; R3 numerical pairing only",
        "candidate_id": args.candidate_id,
        "lambda_internal": args.lambda_internal,
        "thresholds": {
            "peak_relative": 0.02,
            "impulse_vector_relative": 0.02,
            "terminal_position_m": 0.001,
            "terminal_heading_deg": 0.01,
        },
        "gate_application": "Original gate retained: 1ms_to_0.5ms is decisive; 2ms_to_1ms is reported as a diagnostic comparison.",
        "near_zero_policy": "Connector impulse vector norm uses a 1 N*s denominator floor.",
        "evidence_audits": audits,
        "pairs": pairs,
        "source_sha256": sha(__file__),
    }
    save(out, "r3_convergence.json", report)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    names = [row["pair"] for row in pairs]
    series = (
        (100.0 * np.asarray([row["peak_max_relative"] for row in pairs]), "peak difference (%)", 2.0),
        (100.0 * np.asarray([row["impulse_vector_max_relative"] for row in pairs]), "impulse-vector difference (%)", 2.0),
        (1000.0 * np.asarray([row["terminal_payload_position_m"] for row in pairs]), "terminal position difference (mm)", 1.0),
        (np.asarray([row["terminal_payload_heading_deg"] for row in pairs]), "terminal heading difference (deg)", 0.01),
    )
    for axis, (y, ylabel, limit) in zip(axes.ravel(), series):
        axis.plot(names, y, marker="o")
        axis.axhline(limit, color="r", ls="--", label="registered limit")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle(f"EXP-R2 R3 numerical pairing, lambda_internal={args.lambda_internal:g}")
    fig.savefig(out / "r3_convergence.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"status": report["status"], "pairs": pairs}))
    if report["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
