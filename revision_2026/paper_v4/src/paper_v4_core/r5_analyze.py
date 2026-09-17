"""Independent EXP-R2 R5 legal-information interface audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .r2c_analyze import audit, load


def _load_estimates(folder: Path):
    with np.load(folder / "estimates.npz", allow_pickle=False) as data:
        values = data["values"]
        columns = {str(name): index for index, name in enumerate(data["columns"])}
    information = [json.loads(line) for line in (folder / "information.jsonl").read_text(encoding="utf-8").splitlines()]
    return values, columns, information


def _r5_audit(label: str, folder: Path):
    row, loaded = audit(label, folder)
    _, _, _, _, metrics, solver = load(folder)
    expected_runner = sha(Path(__file__).with_name("r5_runner.py"))
    estimates, estimate_columns, information = _load_estimates(folder)
    row["checks"]["source_identity"] = metrics.get("source_sha256") == expected_runner
    row["checks"]["r5_role_identity"] = metrics.get("role") == "DEV" and "legal sensor packets" in metrics.get("identity", "")
    row["checks"]["p0_lambda2_2ms_identity"] = metrics.get("parameter_id") == "P0" and metrics.get("lambda_internal") == 2.0 and metrics.get("maximum_plant_step_s") == 0.002
    row["checks"]["estimate_count_and_finiteness"] = len(estimates) == len(solver) and np.all(np.isfinite(estimates))
    row["checks"]["information_count"] = len(information) == len(solver)
    row["checks"]["all_information_same_tick_and_truth_free"] = all(
        record["audit"]["packet_count"] == 5
        and record["audit"]["maximum_age_ticks"] == 0
        and record["audit"]["truth_field_count"] == 0
        and record["tick"] == record["audit"]["now_tick"]
        for record in information
    )
    row["checks"]["noise_metadata_identity"] = metrics.get("noise_name") in {"none", "basic"} and all(record["noise_name"] == metrics["noise_name"] and record["noise"] == metrics["noise"] for record in information)
    row["status"] = "PASS" if all(row["checks"].values()) else "FAIL"
    error_indices = [estimate_columns[f"error_x{i}"] for i in range(30)]
    steering_error_indices = [estimate_columns[f"error_delta{i}"] for i in range(4)]
    row["state_estimate_rmse"] = float(np.sqrt(np.mean(estimates[:, error_indices] ** 2)))
    row["steering_estimate_rmse_rad"] = float(np.sqrt(np.mean(estimates[:, steering_error_indices] ** 2)))
    return row, loaded, (estimates, estimate_columns, information)


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--baseline-r2c", required=True)
    parser.add_argument("--no-noise", required=True)
    parser.add_argument("--basic-noise", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    baseline_folder = Path(args.baseline_r2c)
    no_noise_folder = Path(args.no_noise)
    basic_folder = Path(args.basic_noise)

    baseline_row, baseline_loaded = audit("R2c_full_state_lambda2", baseline_folder)
    no_noise_row, no_noise_loaded, no_noise_info = _r5_audit("R5_no_noise", no_noise_folder)
    basic_row, basic_loaded, basic_info = _r5_audit("R5_basic_noise", basic_folder)
    baseline_raw, baseline_columns = baseline_loaded[0], baseline_loaded[1]
    no_noise_raw, no_noise_columns = no_noise_loaded[0], no_noise_loaded[1]
    shared_columns = [name for name in baseline_columns if name in no_noise_columns]
    baseline_matrix = baseline_raw[:, [baseline_columns[name] for name in shared_columns]]
    no_noise_matrix = no_noise_raw[:, [no_noise_columns[name] for name in shared_columns]]
    exact_difference = float(np.max(np.abs(baseline_matrix - no_noise_matrix))) if baseline_matrix.shape == no_noise_matrix.shape else float("inf")
    no_noise_row["checks"]["noiseless_wrapper_reproduces_full_state_baseline"] = exact_difference <= 1e-12
    no_noise_row["maximum_abs_difference_from_r2c_baseline"] = exact_difference
    no_noise_row["status"] = "PASS" if all(no_noise_row["checks"].values()) else "FAIL"

    report = {
        "status": "PASS" if baseline_row["status"] == "PASS" and no_noise_row["status"] == "PASS" and basic_row["status"] == "PASS" else "FAIL",
        "scope": "R5 causal same-tick legal-information transfer; no network impairment and no method ranking",
        "baseline": baseline_row,
        "no_noise": no_noise_row,
        "basic_noise": basic_row,
        "sensor_assumption": "Simulation-only independent Gaussian noise: position 0.01 m, heading 0.2 deg, velocity 0.02 m/s, yaw rate 0.005 rad/s; heading is causally unwrapped from local history, and steering measurement is kept exact because no calibrated steering-noise assumption is registered.",
        "causal_boundary": "Plant truth enters only the sensor injector and evaluator; physical MPC receives a detached estimate assembled from four vehicle-local packets plus one payload-coordinator packet.",
        "source_sha256": sha(__file__),
    }
    save(out, "r5_information_gate.json", report)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), constrained_layout=True)
    route_styles = (("no noise", no_noise_loaded, no_noise_info), ("basic noise", basic_loaded, basic_info))
    for label, loaded, info in route_styles:
        raw, columns = loaded[0], loaded[1]
        axes[0, 0].plot(raw[:, columns["x24"]], raw[:, columns["x25"]], label=label)
        axes[0, 1].plot(raw[:, columns["time_s"]], raw[:, columns["internal_force_norm_n"]], label=label)
        estimate_values, estimate_columns, _ = info
        pos_error = np.sqrt(np.sum(estimate_values[:, [estimate_columns["error_x24"], estimate_columns["error_x25"]]] ** 2, axis=1))
        axes[1, 0].plot(estimate_values[:, estimate_columns["time_s"]], pos_error, label=label)
        axes[1, 1].plot(raw[:, columns["time_s"]], np.max(raw[:, [columns[f"point_force_norm{i}"] for i in range(4)]], axis=1), label=label)
    axes[0, 0].set(xlabel="x (m)", ylabel="y (m)", title="Actual payload paths")
    axes[0, 0].axis("equal")
    axes[0, 1].set(xlabel="time (s)", ylabel="N", title="Internal-force norm")
    axes[1, 0].set(xlabel="time (s)", ylabel="m", title="Payload position measurement error")
    axes[1, 1].set(xlabel="time (s)", ylabel="N", title="Maximum connector resultant")
    for axis in axes.ravel():
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle("EXP-R2 R5 legal-information interface diagnostics")
    fig.savefig(out / "r5_information.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"status": report["status"], "no_noise": no_noise_row["status"], "basic_noise": basic_row["status"]}))
    if report["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
