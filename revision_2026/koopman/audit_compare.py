"""Read-only T1 audit for the frozen 120-trajectory Koopman dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
DATA = ROOT / "revision_2026" / "koopman" / "k2" / "data_full"
MODEL = ROOT / "revision_2026" / "koopman" / "k2" / "linear" / "models" / "S3-U1-lifted.npz"
OUT = ROOT / "revision_2026" / "koopman" / "compare" / "t1"
RANK_TOL = 1.0e-8


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def basis(x_norm: np.ndarray) -> np.ndarray:
    clipped = np.clip(x_norm, -8.0, 8.0)
    return np.concatenate([np.ones((x_norm.shape[0], 1)), x_norm, clipped * clipped], axis=1)


def physical_modes(u: np.ndarray) -> np.ndarray:
    accel = u[:, 0::2]
    steer = u[:, 1::2]
    return np.column_stack(
        [
            np.mean(accel, axis=1),
            0.5 * (accel[:, 0] + accel[:, 1] - accel[:, 2] - accel[:, 3]),
            0.5 * (accel[:, 0] + accel[:, 2] - accel[:, 1] - accel[:, 3]),
            0.5 * (accel[:, 0] + accel[:, 3] - accel[:, 1] - accel[:, 2]),
            0.25 * (steer[:, 0] + steer[:, 1] - steer[:, 2] - steer[:, 3]),
        ]
    )


def spectrum(matrix: np.ndarray) -> dict:
    singular = np.linalg.svd(matrix, compute_uv=False)
    ratio = singular / max(float(singular[0]), 1.0e-300)
    effective = int(np.count_nonzero(ratio >= RANK_TOL))
    smallest_effective = float(singular[effective - 1]) if effective else 0.0
    condition_effective = float(singular[0] / max(smallest_effective, 1.0e-300))
    condition_full = float(singular[0] / max(float(singular[-1]), 1.0e-300))
    return {
        "singular_values": singular,
        "relative_singular_values": ratio,
        "effective_rank": effective,
        "columns": int(matrix.shape[1]),
        "effective_rank_ratio": effective / matrix.shape[1],
        "condition_number_effective": condition_effective,
        "condition_number_full": condition_full,
    }


def feature_spectrum(phi: np.ndarray) -> dict:
    mean = phi.mean(axis=0)
    std = phi.std(axis=0)
    nonconstant = std >= 1.0e-10
    standardized = (phi[:, nonconstant] - mean[nonconstant]) / std[nonconstant]
    gram = standardized.T @ standardized / standardized.shape[0]
    eig = np.linalg.eigvalsh(gram)[::-1]
    eig = np.maximum(eig, 0.0)
    singular = np.sqrt(eig)
    ratio = singular / max(float(singular[0]), 1.0e-300)
    effective_nonconstant = int(np.count_nonzero(ratio >= RANK_TOL))
    # The explicit intercept is analytically independent of centered columns.
    effective = effective_nonconstant + int(np.count_nonzero(~nonconstant))
    columns = int(phi.shape[1])
    smallest = float(singular[effective_nonconstant - 1]) if effective_nonconstant else 0.0
    return {
        "columns": columns,
        "constant_columns": int(np.count_nonzero(~nonconstant)),
        "effective_rank": effective,
        "effective_rank_ratio": effective / columns,
        "condition_number_effective": float(singular[0] / max(smallest, 1.0e-300)),
        "relative_singular_values_nonconstant": ratio,
        "normalization": "train-column mean/std; explicit intercept audited analytically",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    with np.load(MODEL, allow_pickle=False) as model:
        x_mean = np.asarray(model["x_mean"], dtype=float)
        x_std = np.asarray(model["x_std"], dtype=float)
        u_mean = np.asarray(model["u_mean"], dtype=float)
        u_std = np.asarray(model["u_std"], dtype=float)

    train_x, train_u = [], []
    scenario_rows: dict[str, int] = {}
    scenario_windows: dict[str, int] = {}
    contact = {"free": 0, "contact": 0, "strong": 0}
    force_abs = []
    modal_by_scenario: dict[str, list[np.ndarray]] = {}
    for meta in manifest["trajectories"]:
        path = DATA / meta["file"]
        if sha256(path).lower() != str(meta["sha256"]).lower():
            raise RuntimeError(f"hash mismatch: {path}")
        if meta["split"] != "train":
            continue
        with np.load(path, allow_pickle=False) as source:
            x = np.asarray(source["s3_deform"][:-1], dtype=float)
            u = np.asarray(source["u1_four"], dtype=float)
            displacement = np.asarray(source["displacement_body"][:-1], dtype=float)
            force = np.asarray(source["force_body"][:-1], dtype=float)
        train_x.append(x)
        train_u.append(u)
        scenario = str(meta["scenario"])
        scenario_rows[scenario] = scenario_rows.get(scenario, 0) + u.shape[0]
        scenario_windows[scenario] = scenario_windows.get(scenario, 0) + max(u.shape[0] - 19, 0)
        modal_by_scenario.setdefault(scenario, []).append(physical_modes(u))
        displacement_norm = np.linalg.norm(displacement, axis=2)
        force_norm = np.linalg.norm(force, axis=2)
        free = np.all(force_norm < 1.0, axis=1)
        strong = np.any(force_norm >= 0.5 * float(meta["params"]["connector"]["rated_force_n"]), axis=1)
        contact["free"] += int(np.count_nonzero(free))
        contact["strong"] += int(np.count_nonzero(strong))
        contact["contact"] += int(u.shape[0] - np.count_nonzero(free) - np.count_nonzero(strong))
        force_abs.append(force_norm.reshape(-1))

    x = np.concatenate(train_x)
    u = np.concatenate(train_u)
    xn = (x - x_mean) / x_std
    un = (u - u_mean) / u_std
    z = basis(xn)
    z_dynamic = z[:, 1:]
    modes = physical_modes(u)
    mode_mean = modes.mean(axis=0)
    mode_std = np.where(modes.std(axis=0) < 1.0e-10, 1.0, modes.std(axis=0))
    mode_norm = (modes - mode_mean) / mode_std

    # Correct full-bilinear contract: z[0]=1 must not be repeated in u_j*z.
    full_phi = np.concatenate(
        [z, un, np.einsum("ni,nj->nij", un, z_dynamic).reshape(z.shape[0], -1)],
        axis=1,
    )
    structured_phi = np.concatenate(
        [z, un, np.einsum("ni,nj->nij", mode_norm, z_dynamic).reshape(z.shape[0], -1)],
        axis=1,
    )
    u_corr = np.corrcoef(u, rowvar=False)
    mode_corr = np.corrcoef(modes, rowvar=False)
    u_spec = spectrum((u - u.mean(axis=0)) / np.where(u.std(axis=0) < 1.0e-10, 1.0, u.std(axis=0)))
    mode_spec = spectrum((modes - mode_mean) / mode_std)
    full_spec = feature_spectrum(full_phi)
    structured_spec = feature_spectrum(structured_phi)

    coverage = {}
    for scenario, pieces in modal_by_scenario.items():
        value = np.concatenate(pieces)
        coverage[scenario] = {
            "rows": int(value.shape[0]),
            "mode_min": value.min(axis=0),
            "mode_q05": np.quantile(value, 0.05, axis=0),
            "mode_q50": np.quantile(value, 0.50, axis=0),
            "mode_q95": np.quantile(value, 0.95, axis=0),
            "mode_max": value.max(axis=0),
        }
    force_values = np.concatenate(force_abs)
    total_contact = sum(contact.values())
    report = {
        "stage": "T1_read_only_pretraining_audit",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manifest_sha256": sha256(DATA / "manifest.json"),
        "model_sha256": sha256(MODEL),
        "train_rows": int(u.shape[0]),
        "train_20step_windows_stride1": int(sum(scenario_windows.values())),
        "scenario_rows": scenario_rows,
        "scenario_20step_windows_stride1": scenario_windows,
        "u1_order": ["a_FL", "delta_FL", "a_FR", "delta_FR", "a_RL", "delta_RL", "a_RR", "delta_RR"],
        "physical_mode_order": ["common_accel", "front_rear_accel", "left_right_accel", "diagonal_accel", "common_curvature_steer"],
        "u1_correlation": u_corr,
        "u1_spectrum": u_spec,
        "physical_mode_correlation": mode_corr,
        "physical_mode_spectrum": mode_spec,
        "full_bilinear": full_spec,
        "structured_bilinear_unfactored": structured_spec,
        "coverage": coverage,
        "contact_phase": {
            **contact,
            "free_fraction": contact["free"] / total_contact,
            "contact_fraction": contact["contact"] / total_contact,
            "strong_fraction": contact["strong"] / total_contact,
            "strong_definition": "any connector >= 0.5 * trajectory rated force",
            "force_norm_q50_q90_q99_max_n": np.quantile(force_values, [0.5, 0.9, 0.99, 1.0]),
        },
        "g1": {
            "condition_over_1e8": bool(full_spec["condition_number_effective"] > 1.0e8),
            "effective_rank_ratio_below_0p90": bool(full_spec["effective_rank_ratio"] < 0.90),
        },
    }
    report["g1"]["k2_reliably_identifiable"] = not any(report["g1"].values())

    def default(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        raise TypeError(type(value).__name__)

    (OUT / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=default) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        OUT / "spectra.npz",
        u1_correlation=u_corr,
        u1_relative_singular=np.asarray(u_spec["relative_singular_values"]),
        modes_correlation=mode_corr,
        modes_relative_singular=np.asarray(mode_spec["relative_singular_values"]),
        full_relative_singular=np.asarray(full_spec["relative_singular_values_nonconstant"]),
        structured_relative_singular=np.asarray(structured_spec["relative_singular_values_nonconstant"]),
    )
    csv_lines = ["matrix,index,relative_singular_value"]
    for name, values in (
        ("U1", u_spec["relative_singular_values"]),
        ("physical_modes", mode_spec["relative_singular_values"]),
        ("full_bilinear", full_spec["relative_singular_values_nonconstant"]),
        ("structured_bilinear", structured_spec["relative_singular_values_nonconstant"]),
    ):
        csv_lines.extend(f"{name},{index},{float(value):.12e}" for index, value in enumerate(values))
    (OUT / "input_rank_condition.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    axes[0].semilogy(u_spec["relative_singular_values"], "o-", label="U1 (8)")
    axes[0].semilogy(mode_spec["relative_singular_values"], "s-", label="physical modes (5)")
    axes[0].axhline(RANK_TOL, color="tab:red", ls="--", label="rank tolerance")
    axes[0].set(xlabel="singular index", ylabel="relative singular value", title="Input rank")
    axes[0].legend()
    axes[1].semilogy(full_spec["relative_singular_values_nonconstant"], label="full bilinear")
    axes[1].semilogy(structured_spec["relative_singular_values_nonconstant"], label="structured bilinear")
    axes[1].axhline(RANK_TOL, color="tab:red", ls="--", label="rank tolerance")
    axes[1].set(xlabel="singular index", ylabel="relative singular value", title="Normalized regressor rank")
    axes[1].legend()
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.suptitle(
        f"T1 identifiability: full cond={full_spec['condition_number_effective']:.2e}, "
        f"rank={full_spec['effective_rank']}/{full_spec['columns']}"
    )
    fig.tight_layout()
    fig.savefig(OUT / "input_rank_condition.png", dpi=220)
    plt.close(fig)
    print(
        json.dumps(
            {
                "train_rows": report["train_rows"],
                "u1": {k: u_spec[k] for k in ("effective_rank", "effective_rank_ratio", "condition_number_effective")},
                "full": {k: full_spec[k] for k in ("columns", "effective_rank", "effective_rank_ratio", "condition_number_effective")},
                "structured": {k: structured_spec[k] for k in ("columns", "effective_rank", "effective_rank_ratio", "condition_number_effective")},
                "contact_phase": report["contact_phase"],
                "g1": report["g1"],
            },
            indent=2,
            default=default,
        )
    )


if __name__ == "__main__":
    main()
