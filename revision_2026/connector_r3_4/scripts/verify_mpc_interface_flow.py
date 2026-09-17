from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def latest_passing(root: Path) -> Path:
    for candidate in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True):
        complete = candidate / "complete.json"
        if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed") is True:
            return candidate
    raise FileNotFoundError(f"no passing artifact below {root}")


def design(xn: np.ndarray, un: np.ndarray, model_type: str) -> np.ndarray:
    xn = np.atleast_2d(xn)
    un = np.atleast_2d(un)
    if model_type == "fixed_linear":
        return np.c_[xn, un, np.ones(len(xn))]
    interaction = (un[:, :, None] * xn[:, None, :]).reshape(len(xn), -1)
    return np.c_[xn, un, interaction, np.ones(len(xn))]


def predict(saved: np.lib.npyio.NpzFile, x: np.ndarray, u: np.ndarray) -> np.ndarray:
    xn = (np.atleast_2d(x) - saved["x_mean"]) / saved["x_scale"]
    un = (np.atleast_2d(u) - saved["u_mean"]) / saved["u_scale"]
    yn = design(xn, un, str(saved["model_type"])) @ saved["coefficient"]
    return yn * saved["x_scale"] + saved["x_mean"]


def finite_difference_linearization(saved: np.lib.npyio.NpzFile, x: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    base = predict(saved, x, u)[0]
    a = np.zeros((64, 64), dtype=float)
    b = np.zeros((64, 8), dtype=float)
    for index in range(64):
        step = max(1.0e-7, abs(float(x[index])) * 1.0e-7)
        perturbed = x.copy()
        perturbed[index] += step
        a[:, index] = (predict(saved, perturbed, u)[0] - base) / step
    for index in range(8):
        step = max(1.0e-7, abs(float(u[index])) * 1.0e-7)
        perturbed = u.copy()
        perturbed[index] += step
        b[:, index] = (predict(saved, x, perturbed)[0] - base) / step
    c = base - a @ x - b @ u
    delta_x = np.linspace(-1.0e-7, 1.0e-7, 64)
    delta_u = np.linspace(1.0e-7, -1.0e-7, 8)
    exact = predict(saved, x + delta_x, u + delta_u)[0]
    local = base + a @ delta_x + b @ delta_u
    residual = float(np.max(np.abs(exact - local)))
    return a, b, c, residual


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    model_dir = latest_passing(project / "revision_2026" / "connector_r3_4_models" / "smoke")
    data_dir = latest_passing(project / "revision_2026" / "connector_r3_4_data" / "full")
    checks = []
    for model_path in sorted(model_dir.glob("*.npz")):
        with np.load(model_path) as saved:
            plant = str(saved["plant"])
            model_type = str(saved["model_type"])
            with np.load(data_dir / f"dataset_{plant.lower()}_es.npz") as data:
                rows = np.flatnonzero(data["split"] == "test")
                x = np.asarray(data["s4_force_in"][rows[0]], dtype=float)
                u = np.asarray(data["u8"][rows[0]], dtype=float)
                side_channel_shapes = {
                    "internal_force8": list(data["internal_force8"].shape[1:]),
                    "tension_proxy2": list(data["tension_proxy2"].shape[1:]),
                    "contact_fraction4": list(data["contact_fraction4"].shape[1:]),
                    "force_active_mask4": list(data["force_active_mask4"].shape[1:]),
                    "event_counts16": list(data["event_counts16"].shape[1:]),
                }
            prediction = predict(saved, x, u)
            a, b, c, residual = finite_difference_linearization(saved, x, u)
            expected_feature_dimension = 73 if model_type == "fixed_linear" else 585
            passed = bool(
                saved["coefficient"].shape == (expected_feature_dimension, 64)
                and prediction.shape == (1, 64)
                and a.shape == (64, 64)
                and b.shape == (64, 8)
                and c.shape == (64,)
                and np.isfinite(prediction).all()
                and np.isfinite(a).all()
                and np.isfinite(b).all()
                and np.isfinite(c).all()
                and residual <= (1.0e-8 if model_type == "fixed_linear" else 1.0e-6)
                and side_channel_shapes == {
                    "internal_force8": [8],
                    "tension_proxy2": [2],
                    "contact_fraction4": [4],
                    "force_active_mask4": [4],
                    "event_counts16": [16],
                }
            )
            checks.append(
                {
                    "plant": plant,
                    "model": model_type,
                    "model_path": str(model_path),
                    "coefficient_shape": list(saved["coefficient"].shape),
                    "prediction_shape": list(prediction.shape),
                    "A_shape": list(a.shape),
                    "B_shape": list(b.shape),
                    "c_shape": list(c.shape),
                    "linearization_max_abs_residual": residual,
                    "side_channel_shapes": side_channel_shapes,
                    "passed": passed,
                }
            )
    historical_mpc = [
        project / "single_vehicle_koopman_adapt_MPC.ipynb",
    ]
    interface = {
        "status": "CANDIDATE_INTERFACE_VERIFIED_NOT_CLOSED_LOOP_VALIDATED",
        "sample_period_s": 0.02,
        "state": {"name": "S4_force_in", "dimension": 64, "physical_state30": [0, 30], "deformation16": [30, 46], "connector_force_body8": [46, 54], "legacy_q2": [54, 56], "force_rate8": [56, 64]},
        "control": {"name": "u8", "dimension": 8, "order": "[acceleration, steering] repeated for vehicles 1..4"},
        "prediction": {"dimension": 64, "linear_model": "global affine", "bilinear_model": "state/control-dependent local affine A(x,u), B(x,u), c(x,u)"},
        "constraint_side_channels": {"internal_force8": "N", "tension_proxy2": "N", "contact_fraction4": "1", "force_active_mask4": "bool", "event_counts16": "count"},
        "historical_mpc": [{"path": str(path), "exists": path.exists(), "status": "HISTORICAL_ONLY_NOT_COMPATIBLE_BY_ASSUMPTION"} for path in historical_mpc],
        "closed_loop_claim": False,
    }
    write_json(output / "mpc_interface.json", interface)
    write_json(output / "mpc_checks.json", checks)
    passed = len(checks) == 4 and all(row["passed"] for row in checks)
    complete = {
        "stage": "MPC_INTERFACE",
        "passed": passed,
        "model_dir": str(model_dir),
        "data_dir": str(data_dir),
        "model_check_count": len(checks),
        "interface_path": str(output / "mpc_interface.json"),
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete["repair_code"] = "MPC_INTERFACE_DIMENSION_OR_LINEARIZATION"
        complete["next_action"] = "Inspect the first failed model shape, non-finite prediction, side-channel dimension, or local-linearization residual."
    write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
