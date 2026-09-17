from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--through-stage", default="N3")
    args = parser.parse_args(); results = args.project_root.resolve() / "revision_2026" / "connector_r3_3_results"
    figures = results / "figures"; data_dir = results / "figure_data"; figures.mkdir(parents=True, exist_ok=True); data_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario in ("g3_turn_reversal", "q99_contact"):
        metrics = read_csv(results / "n3" / scenario / "metrics.csv")
        by_run = {row["run"]: row for row in metrics}
        for law in ("V1", "R3"):
            reference = by_run[f"{law}-REF"]
            reference_peak = np.asarray([float(reference[f"peak_force_{index}_n"]) for index in range(4)])
            reference_impulse = np.asarray([[float(reference[f"impulse_{index}_x_ns"]), float(reference[f"impulse_{index}_y_ns"])] for index in range(4)])
            for label, h in ((f"{law}-ES", 0.002), (f"{law}-ES-H1", 0.001), (f"{law}-ES-H0p5", 0.0005)):
                value = by_run[label]
                peak = np.asarray([float(value[f"peak_force_{index}_n"]) for index in range(4)])
                impulse = np.asarray([[float(value[f"impulse_{index}_x_ns"]), float(value[f"impulse_{index}_y_ns"])] for index in range(4)])
                peak_error = float(np.max(np.abs(peak - reference_peak) / np.maximum(np.abs(reference_peak), 1e-12)))
                impulse_error = float(np.max(np.linalg.norm(impulse - reference_impulse, axis=1) / np.maximum(np.linalg.norm(reference_impulse, axis=1), 1e-12)))
                rows.append({"scenario": scenario, "law": law, "outer_h_s": h, "peak_force_error_fraction": peak_error, "impulse_error_fraction": impulse_error, "runtime_s": float(value["runtime_s"]), "reference": "0.1 ms + ES within 2 ms record blocks"})
    with (data_dir / "05_four_vehicle_dt_convergence.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharex=True)
    styles = {("g3_turn_reversal", "V1"): ("#1565c0", "o"), ("g3_turn_reversal", "R3"): ("#2e7d32", "s"), ("q99_contact", "V1"): ("#ef6c00", "^"), ("q99_contact", "R3"): ("#7b1fa2", "D")}
    for scenario in ("g3_turn_reversal", "q99_contact"):
        for law in ("V1", "R3"):
            subset = sorted([row for row in rows if row["scenario"] == scenario and row["law"] == law], key=lambda row: row["outer_h_s"])
            x = np.asarray([row["outer_h_s"] * 1e3 for row in subset]); color, marker = styles[(scenario, law)]; label = f"{scenario} / {law}"
            axes[0].plot(x, [row["peak_force_error_fraction"] * 100 for row in subset], color=color, marker=marker, label=label)
            axes[1].plot(x, [row["impulse_error_fraction"] * 100 for row in subset], color=color, marker=marker, label=label)
    axes[0].axhline(5.0, color="#c62828", ls="--", lw=1); axes[1].axhline(2.0, color="#c62828", ls="--", lw=1)
    axes[0].set(title="Four-point peak force convergence", ylabel="worst connector error (%)", xlabel="external interval H (ms)")
    axes[1].set(title="Four-point impulse convergence", ylabel="worst connector error (%)", xlabel="external interval H (ms)")
    for axis in axes: axis.set_yscale("symlog", linthresh=0.001); axis.grid(alpha=.25)
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("N3 four-vehicle convergence vs 0.1 ms + event-substep reference")
    fig.tight_layout(); fig.savefig(figures / "05_four_vehicle_dt_convergence.png", dpi=180); plt.close(fig)
    print(f"wrote {figures / '05_four_vehicle_dt_convergence.png'}")


if __name__ == "__main__": main()

