from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save(fig, outdir: Path, name: str) -> None:
    fig.tight_layout()
    fig.savefig(outdir / name, dpi=190, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    results = Path(sys.argv[1]).resolve()
    figures = results / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    support = json.loads((results / "r0b" / "contact_speed_support.json").read_text(encoding="utf-8"))
    rows = read_csv(results / "r0b" / "contact_speed_support.csv")
    speed = np.asarray([float(row["vn_on_mps"]) for row in rows])
    tau = np.asarray([float(row["tau_nominal_s"]) for row in rows])

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    ax.hist(speed, bins=np.geomspace(max(speed.min(), 1e-7), speed.max(), 70), color="#0072B2", alpha=.82)
    for key, value in support["support_test_speeds_mps"].items():
        ax.axvline(value, lw=1.0, label=f"{key.upper()}={value:.4g} m/s")
    ax.set_xscale("log"); ax.set_xlabel("Contact-onset normal speed (m/s)"); ax.set_ylabel("Events")
    ax.set_title("Train-only contact-speed support (5,771 events)"); ax.grid(alpha=.2); ax.legend(fontsize=8)
    save(fig, figures, "01_contact_speed_support.png")

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    ax.hist(tau * 1e3, bins=np.geomspace(max(tau.min() * 1e3, 1e-4), tau.max() * 1e3, 70), color="#009E73", alpha=.82)
    ax.axvline(2.0, color="#D55E00", ls="--", label="2 ms plant step")
    ax.axvline(20.0, color="#CC79A7", ls=":", label="20 ms learning sample")
    ax.set_xscale("log"); ax.set_xlabel("Nominal smoothing time delta_s/v (ms)"); ax.set_ylabel("Events")
    ax.set_title("Train-only nominal boundary-layer duration"); ax.grid(alpha=.2); ax.legend()
    save(fig, figures, "02_nominal_smoothing_time.png")

    phase = read_csv(results / "r2_1" / "phase_sweep.csv")
    fig, ax = plt.subplots(figsize=(9.2, 5.3))
    for label in ("q05", "q50", "q95", "q99"):
        subset = [row for row in phase if row["speed_label"] == label]
        ax.plot([float(row["phase_s"]) * 1e6 for row in subset],
                [100 * float(row["first_sample_reduction"]) for row in subset], marker="o", ms=2.5, label=label.upper())
    ax.axhline(50, color="black", ls="--", lw=1, label="50% hard gate")
    ax.set(xlabel="Contact phase within 20 us reference step (us)", ylabel="First-active-sample reduction (%)",
           title="Sampling-phase robustness inside train support")
    ax.grid(alpha=.2); ax.legend()
    save(fig, figures, "03_phase_sweep_onset_reduction.png")

    e1 = np.load(results / "r2_1" / "e1_damped.npz")
    fig, axes = plt.subplots(3, 1, figsize=(9.4, 8.0), sharex=True)
    axes[0].plot(e1["time_s"] * 1e3, e1["total_mechanical_energy_j"], label="Mechanical energy")
    axes[0].plot(e1["time_s"] * 1e3, e1["total_mechanical_energy_j"][0] - e1["cumulative_dissipation_j"], "--", label="E0 - integrated damping")
    axes[1].plot(e1["time_s"] * 1e3, e1["damping_power_w"], color="#D55E00")
    axes[2].plot(e1["time_s"] * 1e3, e1["energy_balance_residual_j"], color="#009E73")
    axes[0].set_ylabel("Energy (J)"); axes[1].set_ylabel("Damping power (W)"); axes[2].set_ylabel("Balance residual (J)"); axes[2].set_xlabel("Time (ms)")
    axes[0].set_title("E1: activated damping and discrete energy balance")
    for ax in axes: ax.grid(alpha=.2)
    axes[0].legend()
    save(fig, figures, "04_e1_energy_balance.png")

    e2 = read_csv(results / "r2_1" / "e2_prescribed_cycle.csv")
    t = np.asarray([float(row["time_s"]) for row in e2])
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 6.5), sharex=True)
    axes[0].plot(t * 1e3, [float(row["elastic_force_n"]) for row in e2], label="Elastic")
    axes[0].plot(t * 1e3, [float(row["damping_force_n"]) for row in e2], label="Damping")
    axes[1].plot(t * 1e3, [float(row["damping_power_w"]) for row in e2], color="#D55E00")
    axes[0].set_ylabel("Force (N)"); axes[1].set_ylabel("Damping power (W)"); axes[1].set_xlabel("Time (ms)")
    axes[0].set_title("E2: prescribed loading/unloading cycle"); axes[0].legend()
    for ax in axes: ax.grid(alpha=.2)
    save(fig, figures, "05_e2_prescribed_cycle.png")

    diag = read_csv(results / "r2_1" / "two_ms_diagnostics.csv")
    fig, ax = plt.subplots(figsize=(9.3, 5.2))
    labels = [row["case"] for row in diag]
    values = [100 * float(row["two_ms_endpoint_reduction"]) for row in diag]
    colors = ["#0072B2" if row["domain"] == "support" else "#D55E00" for row in diag]
    ax.bar(labels, values, color=colors); ax.axhline(50, color="black", ls="--", lw=1)
    ax.set_ylabel("2 ms endpoint force reduction (%)"); ax.set_title("2 ms endpoint: support versus stress diagnostics")
    ax.tick_params(axis="x", rotation=25); ax.grid(axis="y", alpha=.2)
    save(fig, figures, "06_two_ms_support_vs_stress.png")

    r3_path = results / "r3_dt" / "r3_dt_results.json"
    if r3_path.is_file():
        dt_rows = read_csv(results / "r3_dt" / "dt_comparison.csv")
        coarse = [row for row in dt_rows if abs(float(row["dt_s"]) - .002) < 1e-12]
        fig, ax = plt.subplots(figsize=(10.2, 5.5))
        x = np.arange(len(coarse)); width = .25
        ax.bar(x-width, [100*float(r["peak_force_relative_error"]) for r in coarse], width, label="Peak")
        ax.bar(x, [100*float(r["impulse_relative_error"]) for r in coarse], width, label="Impulse")
        ax.bar(x+width, [100*float(r["terminal_state_scaled_error"]) for r in coarse], width, label="Terminal scaled")
        ax.set_xticks(x, [r["case"] for r in coarse], rotation=30, ha="right")
        ax.set_ylabel("2 ms versus 0.1 ms error (%)"); ax.set_title("R3a single-connector time-step convergence")
        ax.grid(axis="y", alpha=.2); ax.legend()
        save(fig, figures, "07_dt_convergence.png")

        resolution = read_csv(results / "r3_dt" / "plant_step_resolution.csv")
        fig, ax = plt.subplots(figsize=(8.8, 5.2))
        labels = ("q50", "q95", "q99")
        data = [[int(row["strict_inside_zone_nodes"]) for row in resolution if row["speed_label"] == label] for label in labels]
        ax.boxplot(data, tick_labels=[label.upper() for label in labels], showmeans=True)
        ax.axhline(2, color="#D55E00", ls="--", label="minimum median node gate")
        ax.set_ylabel("Strictly inside-zone nodes at 2 ms"); ax.set_title("Plant-grid resolution across 32 contact phases")
        ax.grid(axis="y", alpha=.2); ax.legend()
        save(fig, figures, "08_plant_step_resolution.png")

    print(json.dumps({"figures": sorted(path.name for path in figures.glob("*.png"))}))


if __name__ == "__main__":
    main()
