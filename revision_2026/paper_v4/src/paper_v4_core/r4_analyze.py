"""Independent EXP-R2 R4 parameter/resolution audit for the selected controller."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .r2c_analyze import audit, load
from .r3_analyze import convergence_quantities


PARAMETERS = ("P1", "P2")
STEPS = ("2ms", "1ms", "0.5ms")
EXPECTED_MAX_STEP_S = {"2ms": 0.002, "1ms": 0.001, "0.5ms": 0.0005}


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--lambda-internal", type=float, choices=(1.0, 2.0), required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    audits = {}
    pairs = []
    for parameter in PARAMETERS:
        values = {}
        for step in STEPS:
            folder = root / f"{parameter}_{step}"
            row, _ = audit(f"{parameter}_{step}", folder)
            _, _, _, _, metrics, _ = load(folder)
            row["checks"]["parameter_identity"] = metrics.get("parameter_id") == parameter
            row["checks"]["maximum_plant_step_identity"] = bool(
                np.isclose(metrics.get("maximum_plant_step_s"), EXPECTED_MAX_STEP_S[step], rtol=0.0, atol=1e-15)
            )
            row["checks"]["selected_lambda_identity"] = bool(
                np.isclose(metrics.get("lambda_internal"), args.lambda_internal, rtol=0.0, atol=0.0)
            )
            row["status"] = "PASS" if all(row["checks"].values()) else "FAIL"
            audits[f"{parameter}_{step}"] = row
            values[step] = convergence_quantities(folder)
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
                    "parameter": parameter,
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
    convergence_pass = all(row["registered_gate_pass"] for row in pairs if row["registered_gate_applies"])
    report = {
        "status": "PASS" if evidence_pass and convergence_pass else "FAIL",
        "scope": "P1/P2 full-route parameter and numerical pairing for the R2c-selected controller",
        "lambda_internal": args.lambda_internal,
        "thresholds": {
            "peak_relative": 0.02,
            "impulse_vector_relative": 0.02,
            "terminal_position_m": 0.001,
            "terminal_heading_deg": 0.01,
        },
        "gate_application": "Original gate retained for each parameter: 1ms_to_0.5ms is decisive; 2ms_to_1ms is diagnostic.",
        "evidence_audits": audits,
        "pairs": pairs,
        "source_sha256": sha(__file__),
    }
    save(out, "r4_convergence.json", report)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    definitions = (
        ("peak_max_relative", 100.0, "peak difference (%)", 2.0),
        ("impulse_vector_max_relative", 100.0, "impulse-vector difference (%)", 2.0),
        ("terminal_payload_position_m", 1000.0, "terminal position difference (mm)", 1.0),
        ("terminal_payload_heading_deg", 1.0, "terminal heading difference (deg)", 0.01),
    )
    for axis, (key, scale, ylabel, limit) in zip(axes.ravel(), definitions):
        for parameter in PARAMETERS:
            rows = [row for row in pairs if row["parameter"] == parameter]
            axis.plot([row["pair"] for row in rows], [scale * row[key] for row in rows], marker="o", label=parameter)
        axis.axhline(limit, color="r", ls="--", label="registered limit")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle(f"EXP-R2 R4 parameter/resolution pairing, lambda_internal={args.lambda_internal:g}")
    fig.savefig(out / "r4_convergence.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"status": report["status"], "pairs": pairs}))
    if report["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
