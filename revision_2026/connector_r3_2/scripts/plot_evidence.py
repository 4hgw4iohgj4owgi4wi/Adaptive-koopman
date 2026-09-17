from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    results = args.project_root.resolve() / "revision_2026" / "connector_r3_2_results"
    figures = results / "figures"
    data = results / "figure_data"
    figures.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    n1 = read_csv(results / "n1" / "analytic_cases.csv")
    n2 = read_csv(results / "n2" / "single_connector_factorial.csv")

    q99 = [row for row in n1 if row["case"].startswith("q99_load_+x")]
    speed = float(q99[0]["speed_mps"])
    contact = min(float(row["expected_time_s"]) for row in q99)
    smoothing = max(float(row["expected_time_s"]) for row in q99)
    t = np.linspace(0.0, smoothing + 0.0005, 600)
    q = -speed * contact + speed * t
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.plot(t * 1e3, q * 1e3, color="#1769aa", lw=2, label="analytic q(t), Q99 load")
    ax.axhline(0.0, color="#333333", ls="--", label="contact surface q=0")
    ax.axhline(0.0001776170305060031 * 1e3, color="#c62828", ls="--", label="smoothing surface q=delta_s")
    ax.scatter([contact * 1e3, smoothing * 1e3], [0.0, 0.0001776170305060031 * 1e3], color=["#333333", "#c62828"], zorder=3)
    ax.set(xlabel="time (ms)", ylabel="signed penetration q (mm)", title="N1 event-surface timeline")
    ax.legend(frameon=False)
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(figures / "01_event_surface_timeline.png", dpi=180)
    plt.close(fig)
    with (data / "01_event_surface_timeline.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream); writer.writerow(["time_s", "penetration_m"]); writer.writerows(zip(t, q))

    r3es = [row for row in n2 if row["factor"] == "R3-ES"]
    labels = ["q05", "q50", "q95", "q99", "stress_0p25", "stress_1p0"]
    med_nodes = [np.median([float(row["smoothing_zone_accepted_steps"]) for row in r3es if row["speed_label"] == label]) for label in labels]
    min_dt = [min(float(row["min_accepted_dt_s"]) for row in r3es if row["speed_label"] == label) * 1e6 for label in labels]
    fig, ax1 = plt.subplots(figsize=(8.8, 4.8))
    x = np.arange(len(labels))
    ax1.bar(x - .18, med_nodes, width=.36, color="#2e7d32", label="median accepted zone steps")
    ax1.axhline(8, color="#2e7d32", ls="--", lw=1)
    ax1.set_ylabel("accepted steps intersecting smoothing zone")
    ax2 = ax1.twinx()
    ax2.bar(x + .18, min_dt, width=.36, color="#ef6c00", label="minimum accepted dt")
    ax2.set_ylabel("minimum accepted dt (us)")
    ax1.set_xticks(x, labels, rotation=20)
    ax1.set_title("R3-ES smoothing-zone resolution")
    ax1.grid(axis="y", alpha=.2)
    handles = ax1.containers[:1] + ax2.containers[:1]
    ax1.legend(handles, ["zone steps", "minimum dt"], frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(figures / "02_substep_count_and_dt.png", dpi=180)
    plt.close(fig)
    with (data / "02_substep_count_and_dt.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream); writer.writerow(["speed_label", "median_zone_steps", "min_dt_us"]); writer.writerows(zip(labels, med_nodes, min_dt))

    factors = ["V1-F2", "V1-ES", "R3-F2", "R3-ES"]
    styles = {"V1-F2": ("#9e9e9e", "--"), "V1-ES": ("#1565c0", "-"), "R3-F2": ("#ef6c00", "--"), "R3-ES": ("#2e7d32", "-")}
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for factor in factors:
        values = [max(float(row["impulse_relative_error"]) for row in n2 if row["factor"] == factor and row["speed_label"] == label) * 100 for label in labels]
        ax.plot(x, values, marker="o", color=styles[factor][0], ls=styles[factor][1], label=factor)
    ax.axhline(2.0, color="#c62828", ls=":", label="2% ES gate")
    ax.set_xticks(x, labels, rotation=20)
    ax.set(ylabel="worst phase impulse error (%)", title="Single-connector impulse convergence vs 2 us reference")
    ax.set_yscale("symlog", linthresh=.01)
    ax.grid(alpha=.25)
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(figures / "03_single_connector_impulse_convergence.png", dpi=180)
    plt.close(fig)
    with (data / "03_single_connector_impulse_convergence.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream); writer.writerow(["factor", "speed_label", "worst_impulse_error_fraction"])
        for factor in factors:
            for label in labels:
                writer.writerow([factor, label, max(float(row["impulse_relative_error"]) for row in n2 if row["factor"] == factor and row["speed_label"] == label)])

    metrics = ["peak_force_relative_error", "impulse_relative_error", "terminal_state_scaled_error"]
    means = np.asarray([[np.mean([float(row[metric]) for row in n2 if row["factor"] == factor]) * 100 for metric in metrics] for factor in factors])
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    width = .19
    for index, factor in enumerate(factors):
        ax.bar(np.arange(3) + (index - 1.5) * width, means[index], width=width, color=styles[factor][0], label=factor)
    ax.set_xticks(np.arange(3), ["peak force", "impulse", "terminal state"])
    ax.set(ylabel="mean relative error (%)", title="V1/R3 × fixed/event-aware factorial")
    ax.set_yscale("symlog", linthresh=.01)
    ax.grid(axis="y", alpha=.25)
    ax.legend(frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(figures / "04_v1_r3_fixed_event_factorial.png", dpi=180)
    plt.close(fig)
    with (data / "04_v1_r3_fixed_event_factorial.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream); writer.writerow(["factor", *metrics]); writer.writerows([[factor, *means[index] / 100] for index, factor in enumerate(factors)])

    print(json.dumps({"figures": 4, "output": str(figures)}, indent=2))


if __name__ == "__main__":
    main()

