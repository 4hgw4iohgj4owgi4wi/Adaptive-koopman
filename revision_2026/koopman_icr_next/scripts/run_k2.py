from __future__ import annotations

import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_coverage import build_coverage
from contracts import write_json
from data_manifest import (
    array_sha256,
    canonical_json,
    canonical_params,
    file_sha256,
    params_sha256,
    validate_manifest,
)
from dataset import concatenate_trajectories, normalization_from_train, trajectory_samples
from generate_data import resolved_params, save_raw, simulate_trajectory
from scenarios import build_base_families, scenario_specs


PLANTS = (("V1-ES", "V1"), ("R3-ES", "R3"))
MIRROR_INDEX = np.asarray([1, 0, 3, 2], dtype=int)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _mirror_state_batch(states: np.ndarray) -> np.ndarray:
    states = np.asarray(states, dtype=float)
    vehicles = states[:, :24].reshape(-1, 4, 6)[:, MIRROR_INDEX].copy()
    payload = states[:, 24:].copy()
    vehicles[:, :, [1, 2, 4, 5]] *= -1.0
    payload[:, [1, 2, 4, 5]] *= -1.0
    return np.concatenate((vehicles.reshape(-1, 24), payload), axis=1)


def _mirror_control_batch(controls: np.ndarray) -> np.ndarray:
    result = np.asarray(controls, dtype=float)[:, MIRROR_INDEX].copy()
    result[:, :, 1] *= -1.0
    return result


def _mirror_point_force_batch(forces: np.ndarray) -> np.ndarray:
    result = np.asarray(forces, dtype=float)[:, MIRROR_INDEX].copy()
    result[:, :, 1] *= -1.0
    return result


def mirror_audit(
    trajectories: list[tuple[dict, dict[str, np.ndarray]]], atol: float
) -> dict:
    by_pair: dict[tuple[str, str], dict[str, tuple[dict, dict[str, np.ndarray]]]] = {}
    for identity, arrays in trajectories:
        if identity["direction"] not in {"left", "right"}:
            continue
        key = (str(identity["base_family_id"]), str(identity["plant"]))
        by_pair.setdefault(key, {})[str(identity["direction"])] = (identity, arrays)
    rows = []
    missing_pairs = 0
    maxima = {
        "state": 0.0,
        "control": 0.0,
        "force_absolute_n": 0.0,
        "force_relative": 0.0,
        "time": 0.0,
        "distance": 0.0,
    }
    for (base, plant), pair in sorted(by_pair.items()):
        if set(pair) != {"left", "right"}:
            missing_pairs += 1
            continue
        left_identity, left = pair["left"]
        _, right = pair["right"]
        if len(left["time_s"]) != len(right["time_s"]):
            rows.append(
                {
                    "base_family_id": base,
                    "plant": plant,
                    "scenario": left_identity["scenario"],
                    "same_length": False,
                    "state_max_abs": "",
                    "control_max_abs": "",
                    "force_max_abs_n": "",
                    "time_max_abs_s": "",
                    "distance_max_abs_m": "",
                    "passed": False,
                }
            )
            continue
        mirrored_force = _mirror_point_force_batch(left["force_payload_body_n"])
        force_absolute_error = np.abs(mirrored_force - right["force_payload_body_n"])
        force_scale_n = np.maximum(
            np.maximum(np.abs(mirrored_force), np.abs(right["force_payload_body_n"])), 1.0
        )
        errors = {
            "state": float(np.max(np.abs(_mirror_state_batch(left["state30"]) - right["state30"]))),
            "control": float(
                np.max(np.abs(_mirror_control_batch(left["control4x2"]) - right["control4x2"]))
            ),
            "force_absolute_n": float(np.max(force_absolute_error)),
            "force_relative": float(np.max(force_absolute_error / force_scale_n)),
            "time": float(np.max(np.abs(left["time_s"] - right["time_s"]))),
            "distance": float(np.max(np.abs(left["distance_m"] - right["distance_m"]))),
        }
        for name, value in errors.items():
            maxima[name] = max(maxima[name], value)
        passed = all(
            errors[name] <= atol
            for name in ("state", "control", "force_relative", "time", "distance")
        )
        rows.append(
            {
                "base_family_id": base,
                "plant": plant,
                "scenario": left_identity["scenario"],
                "same_length": True,
                "state_max_abs": errors["state"],
                "control_max_abs": errors["control"],
                "force_max_abs_n": errors["force_absolute_n"],
                "force_max_relative": errors["force_relative"],
                "time_max_abs_s": errors["time"],
                "distance_max_abs_m": errors["distance"],
                "passed": passed,
            }
        )
    failed = sum(not bool(row["passed"]) for row in rows)
    return {
        "passed": bool(rows and missing_pairs == 0 and failed == 0),
        "pair_count": len(rows),
        "missing_pair_count": missing_pairs,
        "failed_pair_count": failed,
        "absolute_tolerance": atol,
        "maxima": maxima,
        "rows": rows,
    }


def _expected_members(base: dict, directional: set[str]) -> set[tuple[str, str]]:
    directions = ("left", "right") if base["scenario"] in directional else ("none",)
    return {(direction, plant) for direction in directions for plant, _ in PLANTS}


def _save_combined(data_root: Path, combined: dict[str, np.ndarray], plant: str) -> tuple[Path, Path]:
    stem = plant.lower().replace("-", "_")
    combined_path = data_root / f"combined_{stem}.npz"
    normalization_path = data_root / f"normalization_train_{stem}.npz"
    np.savez_compressed(combined_path, **combined)
    np.savez_compressed(normalization_path, **normalization_from_train(combined))
    return combined_path, normalization_path


def _simulate_pair(job: tuple) -> tuple[dict, dict[str, np.ndarray], dict, str]:
    connector_src, spec, law, seed, params, protocol = job
    connector_path = str(connector_src)
    if connector_path not in sys.path:
        sys.path.insert(0, connector_path)
    summary, arrays = simulate_trajectory(spec, law, seed, params, protocol)
    replay_summary, replay_arrays = simulate_trajectory(spec, law, seed, params, protocol)
    return summary, arrays, replay_summary, array_sha256(replay_arrays)


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "k2"
    output.mkdir(parents=True, exist_ok=False)
    data_root = project / "revision_2026" / "koopman_next_data" / "pilot" / run_dir.name
    data_root.mkdir(parents=True, exist_ok=False)
    connector_src = project / "revision_2026" / "connector_r3_4" / "src"
    sys.path.insert(0, str(connector_src))

    config = protocol["k2"]
    specs = scenario_specs(config["scenarios"])
    specs_by_scenario: dict[str, list] = {}
    for spec in specs:
        specs_by_scenario.setdefault(spec.scenario, []).append(spec)
    base_families = build_base_families(protocol)
    registered_splits = {row["base_family_id"]: row["split"] for row in base_families}
    params_by_base = {
        row["base_family_id"]: resolved_params(int(row["seed"]), protocol) for row in base_families
    }

    manifest_rows: list[dict] = []
    time_rows: list[dict] = []
    parameter_rows: list[dict] = []
    replay_rows: list[dict] = []
    trajectories: list[tuple[dict, dict[str, np.ndarray]]] = []
    sample_entries_by_plant: dict[str, list[tuple[dict, dict[str, np.ndarray]]]] = {
        plant: [] for plant, _ in PLANTS
    }
    jobs: list[tuple[dict, object, object, tuple]] = []
    trajectory_id = 0
    for base in base_families:
        base_id = str(base["base_family_id"])
        params = params_by_base[base_id]
        for spec in specs_by_scenario[str(base["scenario"])]:
            for plant, law in PLANTS:
                identity = {
                    "trajectory_id": trajectory_id,
                    "base_family_id": base_id,
                    "split": registered_splits[base_id],
                    "scenario": spec.scenario,
                    "direction": spec.direction,
                    "plant": plant,
                    "law": law,
                    "seed": int(base["seed"]),
                }
                jobs.append(
                    (
                        identity,
                        spec,
                        params,
                        (connector_src, spec, law, int(base["seed"]), params, protocol),
                    )
                )
                trajectory_id += 1

    workers = int(config["parallel_workers"])
    if not 1 <= workers <= 4:
        raise ValueError(f"K2 parallel_workers must be in [1, 4], found {workers}")
    print(f"K2 submitted {len(jobs)} paired first/replay jobs to {workers} CPU workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_simulate_pair, (job[3] for job in jobs), chunksize=1)
        for completed_count, (job, result) in enumerate(zip(jobs, results), start=1):
            identity, spec, params, _ = job
            plant = str(identity["plant"])
            summary, arrays, replay_summary, replay_array_hash = result
            print(
                f"K2 completed {completed_count}/{len(jobs)}: "
                f"{identity['base_family_id']} {spec.direction} {plant}",
                flush=True,
            )
            expected_param_hash = params_sha256(params)
            expected_param_json = canonical_json(canonical_params(params))
            raw_path = data_root / "raw" / (
                f"trajectory_{identity['trajectory_id']:04d}_{spec.scenario}_{spec.direction}_{plant}.npz"
            )
            save_raw(raw_path, arrays, summary, params)
            replay_equal = bool(
                summary["trajectory_array_sha256"]
                == replay_summary["trajectory_array_sha256"]
                == replay_array_hash
            )
            steps = np.diff(np.asarray(arrays["time_s"], dtype=float))
            step_error = np.abs(steps - float(config["model_step_s"]))
            off_grid = int(
                np.sum(
                    ~np.isfinite(steps)
                    | (steps <= 0.0)
                    | (step_error > float(config["time_step_atol_s"]))
                )
            )
            with np.load(raw_path, allow_pickle=False) as raw:
                loaded_param_json = str(raw["params_json"].item())
                loaded_param_hash = str(raw["params_sha256"].item())
            recomputed_param_hash = expected_param_hash
            try:
                recomputed_param_hash = __import__("hashlib").sha256(
                    loaded_param_json.encode("utf-8")
                ).hexdigest().upper()
            except (TypeError, UnicodeError):
                recomputed_param_hash = "INVALID"
            params_match = bool(
                loaded_param_json == expected_param_json
                and loaded_param_hash == expected_param_hash
                and recomputed_param_hash == expected_param_hash
            )
            manifest_rows.append(
                {
                    **identity,
                    "params_sha256": expected_param_hash,
                    "params_json": expected_param_json,
                    "initial_state_sha256": summary["initial_state_sha256"],
                    "control_sha256": summary["control_sha256"],
                    "trajectory_array_sha256": summary["trajectory_array_sha256"],
                    "raw_file_sha256": file_sha256(raw_path),
                    "raw_path": str(raw_path),
                    "sample_count": summary["sample_count"],
                    "duration_s": summary["duration_s"],
                    "distance_m": summary["distance_m"],
                    "event_count": summary["event_count"],
                    "force_peak_n": summary["force_peak_n"],
                    "status": summary["status"],
                }
            )
            time_rows.append(
                {
                    **identity,
                    "interval_count": len(steps),
                    "step_min_s": float(np.min(steps)),
                    "step_max_s": float(np.max(steps)),
                    "max_abs_step_error_s": float(np.max(step_error)),
                    "off_grid_interval_count": off_grid,
                    "distance_target_m": summary["distance_target_m"],
                    "final_distance_m": summary["distance_m"],
                    "distance_overshoot_m": summary["distance_overshoot_m"],
                    "crossing_control_interval_index": (
                        summary["first_distance_crossing"]["control_interval_index"]
                        if summary["first_distance_crossing"] is not None
                        else ""
                    ),
                    "crossing_substep_in_interval": (
                        summary["first_distance_crossing"]["substep_in_interval"]
                        if summary["first_distance_crossing"] is not None
                        else ""
                    ),
                }
            )
            parameter_rows.append(
                {
                    **identity,
                    "manifest_params_sha256": expected_param_hash,
                    "raw_params_sha256": loaded_param_hash,
                    "recomputed_params_sha256": recomputed_param_hash,
                    "params_hash_match": params_match,
                    "replay_hash_match": replay_equal,
                }
            )
            replay_rows.append(
                {
                    **identity,
                    "first_array_sha256": summary["trajectory_array_sha256"],
                    "replay_array_sha256": replay_summary["trajectory_array_sha256"],
                    "control_sha256_match": summary["control_sha256"]
                    == replay_summary["control_sha256"],
                    "initial_state_sha256_match": summary["initial_state_sha256"]
                    == replay_summary["initial_state_sha256"],
                    "replay_hash_match": replay_equal,
                }
            )
            trajectories.append((identity, arrays))
            samples = trajectory_samples(
                arrays,
                params,
                expected_step_s=float(config["model_step_s"]),
                step_atol_s=float(config["time_step_atol_s"]),
            )
            sample_entries_by_plant[plant].append((identity, samples))

    write_csv(output / "data_manifest.csv", manifest_rows)
    write_csv(data_root / "data_manifest.csv", manifest_rows)
    write_csv(output / "time_grid_audit.csv", time_rows)
    write_csv(output / "parameter_identity_audit.csv", parameter_rows)
    write_csv(output / "replay_audit.csv", replay_rows)

    split_audit = validate_manifest(manifest_rows)
    directional = set(config["directional_scenarios"])
    member_failures = []
    for base in base_families:
        observed = {
            tuple(item)
            for item in split_audit["base_family_members"][str(base["base_family_id"])]
        }
        expected = _expected_members(base, directional)
        if observed != expected:
            member_failures.append(
                {
                    "base_family_id": base["base_family_id"],
                    "expected": sorted(map(list, expected)),
                    "observed": sorted(map(list, observed)),
                }
            )
    split_audit["member_failure_count"] = len(member_failures)
    split_audit["member_failures"] = member_failures
    write_json(output / "split_audit.json", split_audit)

    combined_by_plant = {
        plant: concatenate_trajectories(entries)
        for plant, entries in sample_entries_by_plant.items()
    }
    combined_artifacts = {}
    for plant, combined in combined_by_plant.items():
        combined_path, normalization_path = _save_combined(data_root, combined, plant)
        combined_artifacts[plant] = {
            "combined_path": str(combined_path),
            "combined_sha256": file_sha256(combined_path),
            "normalization_path": str(normalization_path),
            "normalization_sha256": file_sha256(normalization_path),
            "sample_count": int(len(combined["sample_time_s"])),
        }
    write_json(output / "combined_artifacts.json", combined_artifacts)

    coverage = build_coverage(trajectories, combined_by_plant, protocol)
    write_json(output / "coverage.json", coverage)
    mirror = mirror_audit(trajectories, float(config["mirror_atol"]))
    write_csv(output / "mirror_audit.csv", mirror["rows"])
    write_json(output / "mirror_audit.json", {key: value for key, value in mirror.items() if key != "rows"})

    time_gate = bool(
        all(int(row["off_grid_interval_count"]) == 0 for row in time_rows)
        and all(row["status"] == "PASS" for row in manifest_rows)
        and all(
            row["distance_target_m"] in {None, ""}
            or float(row["final_distance_m"]) >= float(row["distance_target_m"])
            for row in time_rows
        )
    )
    parameter_gate = all(bool(row["params_hash_match"]) for row in parameter_rows)
    replay_gate = all(bool(row["replay_hash_match"]) for row in replay_rows)
    split_gate = bool(
        split_audit["cross_split_base_family_count"] == 0
        and split_audit["duplicate_trajectory_id_count"] == 0
        and split_audit["missing_parameter_identity_count"] == 0
        and split_audit["member_failure_count"] == 0
    )
    physics_rows = []
    for row, (_, arrays) in zip(manifest_rows, trajectories):
        maximum_tire = float(np.max(arrays["tire_raw_utilization"]))
        meta = json.loads(Path(row["raw_path"]).with_suffix(".meta.json").read_text(encoding="utf-8"))
        relative_internal_null = float(meta["internal_null_max_n"]) / max(
            float(meta["internal_force_peak_n"]), 1.0
        )
        passed = bool(
            meta["finite"]
            and not meta["ultimate_force_exceeded"]
            and maximum_tire <= float(config["tire_raw_utilization_max"])
            and float(meta["icr_residual_max_mps"]) <= float(config["icr_residual_atol_mps"])
            and float(meta["action_reaction_max_n"]) <= float(config["action_reaction_atol_n"])
            and relative_internal_null <= float(config["internal_null_relative_atol"])
        )
        physics_rows.append(
            {
                "trajectory_id": row["trajectory_id"],
                "base_family_id": row["base_family_id"],
                "scenario": row["scenario"],
                "direction": row["direction"],
                "plant": row["plant"],
                "finite": meta["finite"],
                "ultimate_force_exceeded": meta["ultimate_force_exceeded"],
                "tire_raw_utilization_max": maximum_tire,
                "icr_residual_max_mps": meta["icr_residual_max_mps"],
                "action_reaction_max_n": meta["action_reaction_max_n"],
                "internal_null_relative": relative_internal_null,
                "passed": passed,
            }
        )
    write_csv(output / "physics_audit.csv", physics_rows)
    physics_gate = all(bool(row["passed"]) for row in physics_rows)

    actual_runtime_s = time.perf_counter() - started
    actual_bytes = directory_bytes(data_root)
    trajectory_count = len(manifest_rows)
    scale = float(config["projected_full_trajectory_count"]) / max(trajectory_count, 1)
    resource = {
        "pilot_trajectory_count": trajectory_count,
        "projected_full_trajectory_count": int(config["projected_full_trajectory_count"]),
        "pilot_data_bytes": actual_bytes,
        "pilot_data_gib": actual_bytes / 2**30,
        "pilot_runtime_s": actual_runtime_s,
        "seconds_per_trajectory_including_replay": actual_runtime_s / max(trajectory_count, 1),
        "projection_method": "linear scaling of this paired pilot, including replay and combined artifacts",
        "projected_full_data_gib": actual_bytes * scale / 2**30,
        "projected_full_runtime_hours": actual_runtime_s * scale / 3600.0,
        "maximum_full_data_gib": float(protocol["resource_limits"]["maximum_full_data_gib"]),
        "maximum_single_stage_hours": float(protocol["resource_limits"]["maximum_single_stage_hours"]),
    }
    resource["passed"] = bool(
        resource["projected_full_data_gib"] <= resource["maximum_full_data_gib"]
        and resource["projected_full_runtime_hours"] <= resource["maximum_single_stage_hours"]
    )
    write_json(output / "resource_projection.json", resource)

    gates = {
        "trajectory_count": trajectory_count == 60,
        "time_grid_and_completion": time_gate,
        "parameter_identity": parameter_gate,
        "replay_identity": replay_gate,
        "base_family_split": split_gate,
        "coverage": bool(coverage["hard_gate_passed"]),
        "mirror": bool(mirror["passed"]),
        "physics": physics_gate,
        "resource": bool(resource["passed"]),
    }
    passed = all(gates.values())
    failed_gates = [name for name, value in gates.items() if not value]
    complete = {
        "stage": "K2",
        "passed": passed,
        "data_root": str(data_root),
        "trajectory_count": trajectory_count,
        "base_family_count": int(split_audit["base_family_count"]),
        "coverage_counts": coverage["class_counts"],
        "off_grid_trajectory_count": sum(
            int(row["off_grid_interval_count"] > 0) for row in time_rows
        ),
        "replay_mismatch_count": sum(not bool(row["replay_hash_match"]) for row in replay_rows),
        "parameter_mismatch_count": sum(not bool(row["params_hash_match"]) for row in parameter_rows),
        "cross_split_base_family_count": int(split_audit["cross_split_base_family_count"]),
        "mirror_failed_pair_count": int(mirror["failed_pair_count"]),
        "physics_failed_trajectory_count": sum(not bool(row["passed"]) for row in physics_rows),
        "projected_full_data_gib": resource["projected_full_data_gib"],
        "projected_full_runtime_hours": resource["projected_full_runtime_hours"],
        "gates": gates,
        "failed_gates": failed_gates,
        "runtime_s": time.perf_counter() - started,
        "artifacts": {
            "data_manifest": str(output / "data_manifest.csv"),
            "time_grid_audit": str(output / "time_grid_audit.csv"),
            "parameter_identity_audit": str(output / "parameter_identity_audit.csv"),
            "split_audit": str(output / "split_audit.json"),
            "coverage": str(output / "coverage.json"),
            "replay_audit": str(output / "replay_audit.csv"),
            "resource_projection": str(output / "resource_projection.json"),
            "mirror_audit": str(output / "mirror_audit.csv"),
            "physics_audit": str(output / "physics_audit.csv"),
        },
    }
    if not passed:
        failure = run_dir / "failure"
        failure.mkdir(parents=True, exist_ok=True)
        failure_rows = [
            row
            for row in manifest_rows
            if row["status"] != "PASS"
            or any(
                int(physics["trajectory_id"]) == int(row["trajectory_id"])
                and not bool(physics["passed"])
                for physics in physics_rows
            )
        ]
        write_json(
            failure / "diagnosis.json",
            {
                "repair_code": "K2_" + "_".join(name.upper() for name in failed_gates),
                "failed_gates": failed_gates,
                "minimal_failed_trajectories": failure_rows[:12],
                "coverage_gates": coverage["gates"],
                "schema_by_plant": coverage["schema_by_plant"],
                "mirror": {key: value for key, value in mirror.items() if key != "rows"},
            },
        )
        complete.update(
            {
                "repair_code": "K2_" + "_".join(name.upper() for name in failed_gates),
                "next_action": (
                    "Inspect k2 audits and failure/diagnosis.json; preserve this run. "
                    "Apply only a minimum contract/scenario repair, then rerun K0/K1/K2 under a new identity. "
                    "K3 and all training remain forbidden."
                ),
            }
        )
    write_json(output / "complete.json", complete)
    return complete
