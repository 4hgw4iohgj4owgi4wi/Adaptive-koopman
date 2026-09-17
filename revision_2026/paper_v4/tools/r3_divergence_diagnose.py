"""Read-only diagnosis of EXP-R2 R3 closed-loop resolution divergence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as archive:
        values = np.asarray(archive["values"], dtype=float)
        columns = [str(value) for value in archive["columns"].tolist()]
    return values, {name: index for index, name in enumerate(columns)}


def first_over(values: np.ndarray, threshold: float):
    indices = np.flatnonzero(values > threshold)
    return None if not len(indices) else int(indices[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse", required=True)
    parser.add_argument("--fine", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    coarse_path, fine_path = Path(args.coarse), Path(args.fine)
    coarse, cc = load(coarse_path)
    fine, fc = load(fine_path)
    if coarse.shape[0] != fine.shape[0]:
        raise SystemExit("Tick counts differ; direct same-tick diagnosis is invalid")
    time = coarse[:, cc["time_s"]]
    if not np.array_equal(time, fine[:, fc["time_s"]]):
        raise SystemExit("Time grids differ; direct same-tick diagnosis is invalid")

    pos = np.linalg.norm(coarse[:, [cc["x24"], cc["x25"]]] - fine[:, [fc["x24"], fc["x25"]]], axis=1)
    heading = np.abs((coarse[:, cc["x26"]] - fine[:, fc["x26"]] + np.pi) % (2 * np.pi) - np.pi)
    accel = np.column_stack([
        coarse[:, cc[f"request_accel{i}"]] - fine[:, fc[f"request_accel{i}"]] for i in range(4)
    ])
    steer = np.column_stack([
        coarse[:, cc[f"request_delta{i}"]] - fine[:, fc[f"request_delta{i}"]] for i in range(4)
    ])
    force = np.column_stack([
        coarse[:, cc[f"point_force_norm{i}"]] - fine[:, fc[f"point_force_norm{i}"]] for i in range(4)
    ])
    max_accel = np.max(np.abs(accel), axis=1)
    max_steer_deg = np.rad2deg(np.max(np.abs(steer), axis=1))
    max_force = np.max(np.abs(force), axis=1)

    report = {
        "status": "DIAGNOSTIC_ONLY",
        "scope": "same-tick read-only comparison; no new dynamics and no gate change",
        "coarse_sha256": sha256(coarse_path),
        "fine_sha256": sha256(fine_path),
        "samples": int(len(time)),
        "time_grid_identical": True,
        "initial_payload_position_difference_m": float(pos[0]),
        "initial_payload_heading_difference_deg": float(np.rad2deg(heading[0])),
        "terminal_payload_position_difference_m": float(pos[-1]),
        "terminal_payload_heading_difference_deg": float(np.rad2deg(heading[-1])),
        "maximum_payload_position_difference_m": float(np.max(pos)),
        "maximum_payload_heading_difference_deg": float(np.rad2deg(np.max(heading))),
        "maximum_same_tick_requested_acceleration_difference_mps2": float(np.max(max_accel)),
        "maximum_requested_acceleration_difference_time_s": float(time[int(np.argmax(max_accel))]),
        "maximum_same_tick_requested_steering_difference_deg": float(np.max(max_steer_deg)),
        "maximum_requested_steering_difference_time_s": float(time[int(np.argmax(max_steer_deg))]),
        "maximum_same_tick_point_force_difference_n": float(np.max(max_force)),
        "maximum_point_force_difference_time_s": float(time[int(np.argmax(max_force))]),
        "first_position_over_1mm": None,
        "first_heading_over_0_01deg": None,
        "first_control_difference_over_numeric_noise": None,
        "first_acceleration_difference_over_0_01_mps2": None,
        "first_steering_difference_over_0_01deg": None,
        "interpretation_boundary": "A nonzero same-tick command difference shows that the comparison is closed-loop numerical sensitivity, not a frozen-input integrator-only test. It does not by itself identify the root cause inside the optimizer or plant.",
    }
    for key, series, threshold in (
        ("first_position_over_1mm", pos, 0.001),
        ("first_heading_over_0_01deg", np.rad2deg(heading), 0.01),
        ("first_control_difference_over_numeric_noise", np.maximum(max_accel, max_steer_deg), 1e-10),
        ("first_acceleration_difference_over_0_01_mps2", max_accel, 0.01),
        ("first_steering_difference_over_0_01deg", max_steer_deg, 0.01),
    ):
        index = first_over(series, threshold)
        if index is not None:
            report[key] = {"tick_index": index, "time_s": float(time[index]), "value": float(series[index])}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "r3_divergence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    axes[0, 0].plot(time, 1000 * pos)
    axes[0, 0].axhline(1, color="r", ls="--", label="1 mm gate")
    axes[0, 0].set_ylabel("payload position difference (mm)")
    axes[0, 1].plot(time, np.rad2deg(heading))
    axes[0, 1].axhline(0.01, color="r", ls="--", label="0.01 deg gate")
    axes[0, 1].set_ylabel("payload heading difference (deg)")
    axes[1, 0].plot(time, max_accel)
    axes[1, 0].set_ylabel("max requested acceleration difference (m/s²)")
    axes[1, 1].plot(time, max_steer_deg, label="steering (deg)")
    axes[1, 1].plot(time, max_force / 1000, label="point force / 1000 (N/1000)")
    axes[1, 1].set_ylabel("same-tick difference")
    for axis in axes.ravel():
        axis.set_xlabel("time (s)")
        axis.grid(alpha=0.25)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend()
    fig.suptitle("EXP-R2 R3: 1 ms vs 0.5 ms closed-loop divergence")
    fig.savefig(out / "r3_divergence.png", dpi=180)
    plt.close(fig)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
