from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np


HORIZONS = (1, 5, 10, 20)
MODEL_SPECS = {"fixed_linear": 1.0e-6, "bilinear": None}
BILINEAR_RIDGE_CANDIDATES = (0.01, 0.1, 1.0, 10.0, 100.0)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def latest_complete_data(project: Path) -> Path:
    root = project / "revision_2026" / "connector_r3_4_data" / "full"
    for candidate in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True):
        complete = candidate / "complete.json"
        if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed") is True:
            return candidate
    raise FileNotFoundError("no passing DATA_FULL directory")


def load_dataset(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as source:
        return {key: source[key].copy() for key in source.files}


def consecutive_pair_mask(data: dict[str, np.ndarray], split: str) -> np.ndarray:
    same_trajectory = data["trajectory_id"][:-1] == data["trajectory_id"][1:]
    consecutive_source = data["source_index"][1:] == data["source_index"][:-1] + 1
    in_split = (data["split"][:-1] == split) & (data["split"][1:] == split)
    return same_trajectory & consecutive_source & in_split


def design_matrix(xn: np.ndarray, un: np.ndarray, model_type: str) -> np.ndarray:
    if model_type == "fixed_linear":
        return np.c_[xn, un, np.ones(len(xn))]
    interactions = (un[:, :, None] * xn[:, None, :]).reshape(len(xn), -1)
    return np.c_[xn, un, interactions, np.ones(len(xn))]


def predict_normalized(xn: np.ndarray, un: np.ndarray, coefficient: np.ndarray, model_type: str) -> np.ndarray:
    return design_matrix(np.atleast_2d(xn), np.atleast_2d(un), model_type) @ coefficient


def fit_model(data: dict[str, np.ndarray], model_type: str, ridge: float) -> dict[str, np.ndarray | float | str]:
    x_all = np.asarray(data["s4_force_in"], dtype=float)
    u_all = np.asarray(data["u8"], dtype=float)
    train_rows = data["split"] == "train"
    x_mean = np.mean(x_all[train_rows], axis=0)
    x_std_raw = np.std(x_all[train_rows], axis=0)
    x_active = x_std_raw > 1.0e-10
    x_scale = np.where(x_active, x_std_raw, 1.0)
    u_mean = np.mean(u_all[train_rows], axis=0)
    u_std_raw = np.std(u_all[train_rows], axis=0)
    u_active = u_std_raw > 1.0e-10
    u_scale = np.where(u_active, u_std_raw, 1.0)
    pair_mask = consecutive_pair_mask(data, "train")
    row = np.flatnonzero(pair_mask)
    xn = (x_all[row] - x_mean) / x_scale
    un = (u_all[row] - u_mean) / u_scale
    yn = (x_all[row + 1] - x_mean) / x_scale
    phi = design_matrix(xn, un, model_type)
    regularizer = np.eye(phi.shape[1]) * ridge
    regularizer[-1, -1] = 0.0
    coefficient = np.linalg.solve(phi.T @ phi + regularizer, phi.T @ yn)
    condition_number = float(np.linalg.cond(phi.T @ phi + regularizer))
    return {
        "model_type": model_type,
        "ridge": ridge,
        "coefficient": coefficient,
        "x_mean": x_mean,
        "x_scale": x_scale,
        "x_active": x_active,
        "u_mean": u_mean,
        "u_scale": u_scale,
        "u_active": u_active,
        "condition_number": condition_number,
        "train_pair_count": len(row),
    }


def save_model(path: Path, model: dict[str, np.ndarray | float | str], plant: str) -> None:
    np.savez_compressed(
        path,
        model_type=np.asarray(model["model_type"]),
        plant=np.asarray(plant),
        state_set=np.asarray("S4_force_in"),
        coefficient=model["coefficient"],
        x_mean=model["x_mean"],
        x_scale=model["x_scale"],
        x_active=model["x_active"],
        u_mean=model["u_mean"],
        u_scale=model["u_scale"],
        u_active=model["u_active"],
        ridge=np.asarray(model["ridge"]),
        sample_period_s=np.asarray(0.02),
    )


def reload_difference(path: Path, model: dict[str, np.ndarray | float | str], data: dict[str, np.ndarray]) -> float:
    with np.load(path) as saved:
        rows = np.flatnonzero(data["split"] == "validation")[:8]
        if not len(rows):
            rows = np.arange(min(8, len(data["s4_force_in"])))
        x = data["s4_force_in"][rows]
        u = data["u8"][rows]
        xn_a = (x - model["x_mean"]) / model["x_scale"]
        un_a = (u - model["u_mean"]) / model["u_scale"]
        prediction_a = predict_normalized(xn_a, un_a, model["coefficient"], str(model["model_type"]))
        xn_b = (x - saved["x_mean"]) / saved["x_scale"]
        un_b = (u - saved["u_mean"]) / saved["u_scale"]
        prediction_b = predict_normalized(xn_b, un_b, saved["coefficient"], str(saved["model_type"]))
    return float(np.max(np.abs(prediction_a - prediction_b)))


def trajectory_segments(data: dict[str, np.ndarray], split: str) -> list[np.ndarray]:
    segments = []
    for trajectory_id in np.unique(data["trajectory_id"][data["split"] == split]):
        rows = np.flatnonzero((data["trajectory_id"] == trajectory_id) & (data["split"] == split))
        if len(rows) and np.all(np.diff(data["source_index"][rows]) == 1):
            segments.append(rows)
    return segments


def rollout_metrics(data: dict[str, np.ndarray], model: dict[str, np.ndarray | float | str], split: str) -> list[dict]:
    x_all = np.asarray(data["s4_force_in"], dtype=float)
    u_all = np.asarray(data["u8"], dtype=float)
    scale = np.asarray(model["x_scale"], dtype=float)
    active = np.asarray(model["x_active"], dtype=bool)
    results = []
    for horizon in HORIZONS:
        model_error = []
        persistence_error = []
        state_error = []
        force_error = []
        maximum_normalized_prediction = 0.0
        sample_count = 0
        for rows in trajectory_segments(data, split):
            if len(rows) <= horizon:
                continue
            starts = np.arange(len(rows) - horizon)
            prediction = x_all[rows[starts]].copy()
            persistence = prediction.copy()
            for step in range(horizon):
                control = u_all[rows[starts + step]]
                xn = (prediction - model["x_mean"]) / scale
                un = (control - model["u_mean"]) / model["u_scale"]
                prediction_n = predict_normalized(xn, un, model["coefficient"], str(model["model_type"]))
                maximum_normalized_prediction = max(maximum_normalized_prediction, float(np.max(np.abs(prediction_n))))
                prediction = prediction_n * scale + model["x_mean"]
            truth = x_all[rows[starts + horizon]]
            model_error.append(((prediction[:, active] - truth[:, active]) / scale[active]).ravel())
            persistence_error.append(((persistence[:, active] - truth[:, active]) / scale[active]).ravel())
            state_error.append(((prediction[:, :30] - truth[:, :30]) / scale[:30]).ravel())
            force_error.append(((prediction[:, 46:54] - truth[:, 46:54]) / scale[46:54]).ravel())
            sample_count += len(starts)
        model_vector = np.concatenate(model_error)
        persistence_vector = np.concatenate(persistence_error)
        results.append(
            {
                "split": split,
                "horizon": horizon,
                "sample_count": sample_count,
                "nrmse": float(np.sqrt(np.mean(model_vector**2))),
                "persistence_nrmse": float(np.sqrt(np.mean(persistence_vector**2))),
                "state30_nrmse": float(np.sqrt(np.mean(np.concatenate(state_error) ** 2))),
                "connector_force8_nrmse": float(np.sqrt(np.mean(np.concatenate(force_error) ** 2))),
                "maximum_abs_normalized_prediction": maximum_normalized_prediction,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    data_dir = latest_complete_data(project)
    model_dir = project / "revision_2026" / "connector_r3_4_models" / "smoke" / output.name
    model_dir.mkdir(parents=True, exist_ok=False)
    all_metrics = []
    model_records = []
    ridge_search = []
    gates = []
    for plant in ("V1", "R3"):
        data = load_dataset(data_dir / f"dataset_{plant.lower()}_es.npz")
        for model_type, ridge in MODEL_SPECS.items():
            if model_type == "bilinear":
                candidates = []
                for candidate_ridge in BILINEAR_RIDGE_CANDIDATES:
                    candidate_model = fit_model(data, model_type, candidate_ridge)
                    candidate_metrics = rollout_metrics(data, candidate_model, "validation")
                    one = next(row for row in candidate_metrics if row["horizon"] == 1)
                    twenty = next(row for row in candidate_metrics if row["horizon"] == 20)
                    eligible = one["nrmse"] <= one["persistence_nrmse"] and twenty["maximum_abs_normalized_prediction"] < 1.0e6
                    candidates.append((candidate_ridge, candidate_model, twenty["nrmse"], eligible))
                    ridge_search.append(
                        {
                            "plant": plant,
                            "ridge": candidate_ridge,
                            "validation_one_step_nrmse": one["nrmse"],
                            "validation_one_step_persistence_nrmse": one["persistence_nrmse"],
                            "validation_twenty_step_nrmse": twenty["nrmse"],
                            "validation_twenty_step_max_abs_normalized_prediction": twenty["maximum_abs_normalized_prediction"],
                            "eligible": eligible,
                        }
                    )
                eligible_candidates = [item for item in candidates if item[3]]
                ridge, model, _, _ = min(eligible_candidates, key=lambda item: item[2]) if eligible_candidates else candidates[-1]
            else:
                model = fit_model(data, model_type, float(ridge))
            model_path = model_dir / f"{plant.lower()}_{model_type}.npz"
            save_model(model_path, model, plant)
            difference = reload_difference(model_path, model, data)
            metrics = []
            for split in ("validation", "test"):
                metrics.extend(rollout_metrics(data, model, split))
            for row in metrics:
                row.update({"plant": plant, "model": model_type})
            all_metrics.extend(metrics)
            numeric_metric_keys = (
                "sample_count",
                "nrmse",
                "persistence_nrmse",
                "state30_nrmse",
                "connector_force8_nrmse",
                "maximum_abs_normalized_prediction",
            )
            finite = bool(
                np.isfinite(model["coefficient"]).all()
                and all(all(np.isfinite(row[key]) for key in numeric_metric_keys) for row in metrics)
            )
            one_step = [row for row in metrics if row["horizon"] == 1]
            one_step_beats_persistence = all(row["nrmse"] <= row["persistence_nrmse"] for row in one_step)
            twenty_step = [row for row in metrics if row["horizon"] == 20]
            bounded_twenty_step = all(row["maximum_abs_normalized_prediction"] < 1.0e6 for row in twenty_step)
            gate = finite and difference <= 1.0e-12 and one_step_beats_persistence and bounded_twenty_step
            gates.append(gate)
            model_records.append(
                {
                    "plant": plant,
                    "model": model_type,
                    "path": str(model_path),
                    "state_dimension": 64,
                    "control_dimension": 8,
                    "feature_dimension": int(model["coefficient"].shape[0]),
                    "constant_state_indices": np.flatnonzero(~model["x_active"]).tolist(),
                    "constant_control_indices": np.flatnonzero(~model["u_active"]).tolist(),
                    "ridge": float(ridge),
                    "regularized_condition_number": model["condition_number"],
                    "train_pair_count": model["train_pair_count"],
                    "reload_max_abs_difference": difference,
                    "one_step_beats_persistence": one_step_beats_persistence,
                    "twenty_step_finite_and_bounded": bounded_twenty_step,
                    "passed": gate,
                }
            )
    write_json(output / "training_metrics.json", all_metrics)
    write_json(output / "model_records.json", model_records)
    write_json(output / "ridge_search.json", ridge_search)
    complete = {
        "stage": "TRAIN_SMOKE",
        "passed": all(gates),
        "data_dir": str(data_dir),
        "model_dir": str(model_dir),
        "models": model_records,
        "metrics_path": str(output / "training_metrics.json"),
        "interpretation": "S4 causal state smoke test only; this is not a claim of a final Koopman architecture or controller performance.",
        "runtime_s": time.perf_counter() - started,
    }
    if not complete["passed"]:
        complete["repair_code"] = "TRAIN_ALIGNMENT_SCALE_OR_ROLLOUT"
        complete["next_action"] = "Inspect the first model whose one-step error exceeds persistence, reload differs, or normalized 20-step rollout is unbounded."
    write_json(model_dir / "complete.json", complete)
    write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if complete["passed"] else 2)


if __name__ == "__main__":
    main()
