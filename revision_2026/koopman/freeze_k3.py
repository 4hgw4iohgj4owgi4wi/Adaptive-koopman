"""Create or audit the immutable K3 evidence-isolation package (G30)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


BASE_SCENARIOS = (
    "staged_100m",
    "single_lane_change",
    "hairpin",
    "connector_directional",
    "network_excitation",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite preregistered file: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": relative.replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}


def make_internal() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(BASE_SCENARIOS):
        for index in range(20):
            seed = 82000 + scenario_index * 1000 + index
            rng = np.random.default_rng(seed)
            scales = {
                "payload_mass_scale": float(rng.uniform(0.97, 1.03)),
                "vehicle_yaw_inertia_scale": 1.0,
                "connector_stiffness_scale": float(rng.uniform(0.92, 1.08)),
                "connector_damping_scale": float(rng.uniform(0.92, 1.08)),
                "connector_free_play_scale": float(rng.uniform(0.92, 1.08)),
                "vehicle_mu_scale": float(rng.uniform(0.96, 1.04)),
                "curvature_scale": 1.0,
            }
            rows.append(
                {
                    "confirm_id": f"internal_{scenario}_{index:03d}",
                    "set": "confirm_internal",
                    "scenario": scenario,
                    "seed": seed,
                    "trajectory_index": index,
                    "parameter_scales": scales,
                }
            )
    return rows


def make_external() -> list[dict[str, Any]]:
    # Eight signed, mixed-factor corners per scenario.  Factors are deliberately
    # outside K2 train intervals; signs are mixed so no single "all harsh"
    # direction substitutes for a factorial robustness check.
    low_high = {
        "payload_mass_scale": (0.80, 1.22),
        "vehicle_yaw_inertia_scale": (0.78, 1.25),
        "connector_stiffness_scale": (0.65, 1.35),
        "connector_damping_scale": (0.60, 1.45),
        "connector_free_play_scale": (0.50, 1.80),
        "vehicle_mu_scale": (0.70, 1.15),
        "curvature_scale": (0.85, 1.20),
    }
    patterns = (
        (0, 0, 0, 0, 0, 0, 0),
        (1, 1, 1, 1, 1, 1, 1),
        (0, 1, 0, 1, 0, 1, 0),
        (1, 0, 1, 0, 1, 0, 1),
        (0, 0, 1, 1, 0, 0, 1),
        (1, 1, 0, 0, 1, 1, 0),
        (0, 1, 1, 0, 1, 0, 0),
        (1, 0, 0, 1, 0, 1, 1),
    )
    keys = tuple(low_high)
    rows: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(BASE_SCENARIOS):
        for index, pattern in enumerate(patterns):
            scales = {key: low_high[key][pattern[position]] for position, key in enumerate(keys)}
            rows.append(
                {
                    "confirm_id": f"external_{scenario}_{index:03d}",
                    "set": "confirm_external",
                    "scenario": scenario,
                    "seed": 92000 + scenario_index * 1000 + index,
                    "trajectory_index": index,
                    "parameter_scales": scales,
                }
            )
    return rows


def configuration() -> dict[str, Any]:
    return {
        "protocol_version": "K3-frozen-2026-08-19",
        "model": {
            "contracts": ["S4-force-in", "S5-force-out"],
            "dynamics": ["A-global", "B-global-plus-transition-residual"],
            "physical_input": "U1-four",
            "total_lift_dim": 96,
            "encoder_hidden_dim": 64,
            "encoder_depth": 2,
            "activation": "SiLU",
            "physical_state_passthrough": True,
            "common_output_heads": ["s2_four", "force_output", "payload_force_moment"],
            "parameter_count_relative_tolerance": 0.02,
        },
        "training": {
            "model_seeds": [73101, 73102, 73103, 73104, 73105],
            "horizon": 20,
            "teacher_free": True,
            "epochs": 60,
            "batch_size": 256,
            "optimizer": "AdamW",
            "learning_rate_grid": [0.001, 0.0003],
            "weight_decay": 1e-6,
            "gradient_clip_norm": 5.0,
            "early_stopping": "validation only; patience 10; restore best checkpoint",
            "search_budget_per_contract": 4,
            "loss_grid": [
                {"lambda_rec": 0.20, "lambda_1": 1.0, "lambda_H": 0.50, "lambda_F": 0.50, "lambda_Q": 0.50, "lambda_P": 0.10, "lambda_R": 1e-5},
                {"lambda_rec": 0.20, "lambda_1": 1.0, "lambda_H": 1.00, "lambda_F": 0.50, "lambda_Q": 0.50, "lambda_P": 0.10, "lambda_R": 1e-5},
            ],
            "selection_metric": "validation mean of h10-20 state, connector and opening NRMSE",
            "normalization": "K2 train trajectories only",
        },
        "transition_residual": {
            "spectral_norm_fraction_grid": [0.01, 0.02, 0.05, 0.10],
            "q_lowpass_cutoff_hz_grid": [1.0, 2.0, 4.0],
            "sigmoid_temperature_grid": [0.15, 0.25, 0.50],
            "gate_smoothing_grid": [0.0, 0.5, 0.8],
            "selection": "validation only",
            "hard_upper_bound": 0.10,
        },
        "development_roles": {
            "train": "train",
            "validation": "validation",
            "test": "dev_test_old",
            "external": "dev_external_old",
        },
        "confirm": {
            "internal_count": 100,
            "internal_per_scenario": 20,
            "external_count": 40,
            "generation_timing": "only after G34 candidate/config freeze",
            "single_use": True,
        },
        "gates": {
            "G31": "finite rollout; conservation construction audit; parameter count within 2%; no S5 force-input path",
            "G32_S5": "not worse than S4 by >5% on primary metrics and more compact or better external",
            "G32_S4": "at least one primary metric >=10% better with trajectory CI excluding zero; other metrics <=5% worse; sensor stress pass",
            "G33": "transition primary >=10% with CI; E-L/E-C <=5% worse; no triple external degradation; residual norm <=10%",
            "G35": "two strata improve; third <=5% worse; force/opening CI excludes zero; no triple external degradation; seed-consistent",
        },
    }


def create(root: Path) -> dict[str, Any]:
    k3_dir = root / "revision_2026" / "koopman" / "k3"
    k3_dir.mkdir(parents=True, exist_ok=True)
    for child in ("models", "development", "confirm", "closed_loop"):
        (k3_dir / child).mkdir(exist_ok=True)

    k2_manifest_path = root / "revision_2026" / "koopman" / "k2" / "data_full" / "manifest.json"
    k2_manifest = json.loads(k2_manifest_path.read_text(encoding="utf-8"))
    verified = 0
    mismatches: list[str] = []
    for row in k2_manifest["trajectories"]:
        path = k2_manifest_path.parent / row["file"]
        if path.is_file() and sha256(path) == row["sha256"]:
            verified += 1
        else:
            mismatches.append(str(path))
    if mismatches:
        raise RuntimeError(f"K2 data hash mismatch: {mismatches[:3]}")

    frozen_files = [
        "revision_2026/koopman.md",
        "revision_2026/koopman/k3.md",
        "revision_2026/koopman/generate_k2.py",
        "revision_2026/koopman/linear.py",
        "revision_2026/koopman/experts.py",
        "revision_2026/koopman/freeze_k3.py",
        "revision_2026/koopman/k2/solutions.md",
        "revision_2026/koopman/k2/data_full/manifest.json",
        "revision_2026/koopman/k2/data_full/split.json",
        "revision_2026/koopman/k2/linear/results.json",
        "revision_2026/koopman/k2/experts/results.json",
        "revision_2026/koopman/k2/experts/stop.md",
    ]
    freeze = {
        "stage": "K3.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": [file_record(root, relative) for relative in frozen_files],
        "k2_trajectory_hashes_verified": verified,
        "k2_trajectory_hash_mismatches": mismatches,
        "old_split_status": "test and external are development-only after their K2 results were viewed",
    }
    config = configuration()
    development = {
        "source_manifest_sha256": sha256(k2_manifest_path),
        "mapping": config["development_roles"],
        "counts": {
            "train": sum(row["split"] == "train" for row in k2_manifest["trajectories"]),
            "validation": sum(row["split"] == "validation" for row in k2_manifest["trajectories"]),
            "dev_test_old": sum(row["split"] == "test" for row in k2_manifest["trajectories"]),
            "dev_external_old": sum(row["split"] == "external" for row in k2_manifest["trajectories"]),
        },
        "trajectories": [
            {
                "file": row["file"],
                "scenario": row["scenario"],
                "trajectory_id": row["traj_id"],
                "original_split": row["split"],
                "k3_role": config["development_roles"][row["split"]],
                "sha256": row["sha256"],
            }
            for row in k2_manifest["trajectories"]
        ],
    }
    confirm_rows = make_internal() + make_external()
    confirm = {
        "stage": "K3.0.3_preregistered_before_training",
        "generated": False,
        "read_only_after_creation": True,
        "notes": [
            "confirm is generated only after G34; these exact rows may not be changed after development results",
            "payload inertia remains mass/geometry derived in the current plant; independent inertia mismatch is vehicle yaw inertia",
            "curvature_scale changes the frozen scenario steering profile and is external only",
        ],
        "rows": confirm_rows,
    }
    freeze["config_canonical_sha256"] = canonical_hash(config)
    freeze["development_canonical_sha256"] = canonical_hash(development)
    freeze["confirm_canonical_sha256"] = canonical_hash(confirm)

    write_new(k3_dir / "config.json", config)
    write_new(k3_dir / "development_split.json", development)
    write_new(k3_dir / "confirm_preregistered.json", confirm)
    write_new(k3_dir / "freeze.json", freeze)
    g30 = {
        "gate": "G30",
        "passed": bool(
            verified == 120
            and development["counts"] == {"train": 70, "validation": 15, "dev_test_old": 15, "dev_external_old": 20}
            and len(confirm_rows) == 140
            and sum(row["set"] == "confirm_internal" for row in confirm_rows) == 100
            and sum(row["set"] == "confirm_external" for row in confirm_rows) == 40
        ),
        "checks": {
            "k2_hashes_verified": verified,
            "development_counts": development["counts"],
            "confirm_internal": sum(row["set"] == "confirm_internal" for row in confirm_rows),
            "confirm_external": sum(row["set"] == "confirm_external" for row in confirm_rows),
            "confirm_manifest_frozen_before_training": True,
        },
    }
    write_new(k3_dir / "g30.json", g30)
    for path in (
        k3_dir / "config.json",
        k3_dir / "development_split.json",
        k3_dir / "confirm_preregistered.json",
        k3_dir / "freeze.json",
        k3_dir / "g30.json",
    ):
        os.chmod(path, stat.S_IREAD)
    return g30


def audit(root: Path) -> dict[str, Any]:
    k3_dir = root / "revision_2026" / "koopman" / "k3"
    freeze = json.loads((k3_dir / "freeze.json").read_text(encoding="utf-8"))
    mismatches = []
    for row in freeze["files"]:
        path = root / row["path"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            mismatches.append(row["path"])
    config = json.loads((k3_dir / "config.json").read_text(encoding="utf-8"))
    development = json.loads((k3_dir / "development_split.json").read_text(encoding="utf-8"))
    confirm = json.loads((k3_dir / "confirm_preregistered.json").read_text(encoding="utf-8"))
    hashes_match = {
        "config": canonical_hash(config) == freeze["config_canonical_sha256"],
        "development": canonical_hash(development) == freeze["development_canonical_sha256"],
        "confirm": canonical_hash(confirm) == freeze["confirm_canonical_sha256"],
    }
    return {
        "gate": "G30_audit",
        "passed": not mismatches and all(hashes_match.values()),
        "frozen_file_mismatches": mismatches,
        "preregistered_hashes_match": hashes_match,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    result = audit(args.root.resolve()) if args.audit else create(args.root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
