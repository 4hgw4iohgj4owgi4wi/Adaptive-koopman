from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from four_vehicle_common import ModelParams, connector_kinematics, split_state
from internal_force import legacy_q_fr_q_lr
from run_maneuvers_flow import simulate
from schema_r3 import build_schema


PILOT_SCENARIOS = ("100m", "straight", "single_lane_change_left", "hairpin_left", "line_curve_transition_left")
FULL_EXTRA_SCENARIOS = ("connector_longitudinal", "connector_lateral", "connector_diagonal_1", "connector_diagonal_2")
PLANTS = (("V1-ES", "V1"), ("R3-ES", "R3"))
PILOT_RUN_ID = "20260828_145237_DATA_PILOT_F18"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def array_digest(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.ascontiguousarray(arrays[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def state_sets(state: np.ndarray, force_body: np.ndarray, force_rate: np.ndarray, params: ModelParams) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    vehicles, payload = split_state(state)
    yaw_mean = np.arctan2(np.mean(np.sin(vehicles[:, 2])), np.mean(np.cos(vehicles[:, 2])))
    s1 = np.r_[
        payload,
        np.mean(vehicles[:, 0]),
        np.mean(vehicles[:, 1]),
        yaw_mean,
        np.mean(vehicles[:, 3]),
        np.mean(vehicles[:, 4]),
        np.mean(vehicles[:, 5]),
    ]
    s2 = np.asarray(state, dtype=float).copy()
    kinematics = connector_kinematics(state, params)
    s3 = np.r_[s2, kinematics["displacement_world_m"].ravel(), kinematics["relative_velocity_world_mps"].ravel()]
    q = legacy_q_fr_q_lr(force_body)
    s4 = np.r_[s3, force_body.ravel(), q, force_rate.ravel()]
    return s1, s2, s3, s4


def build_sample(arrays: dict[str, np.ndarray], index: int, params: ModelParams) -> dict[str, np.ndarray | float | int]:
    dt = float(arrays["time_s"][index] - arrays["time_s"][index - 1])
    force_body = np.asarray(arrays["force_interval_mean_body_n"][index], dtype=float)
    prior_force_body = np.asarray(arrays["force_interval_mean_body_n"][index - 1], dtype=float)
    force_rate = (force_body - prior_force_body) / dt
    s1, s2, s3, s4 = state_sets(arrays["state30"][index], force_body, force_rate, params)
    return {
        "s1_team": s1,
        "s2_four": s2,
        "s3_deform": s3,
        "s4_force_in": s4,
        "u8": np.asarray(arrays["control4x2"][index + 1], dtype=float).ravel(),
        "y30": np.asarray(arrays["state30"][index + 1], dtype=float),
        "internal_force8": np.asarray(arrays["internal_force_interval_mean_n"][index], dtype=float),
        "tension_proxy2": np.asarray(arrays["tension_proxy_interval_mean_n"][index], dtype=float),
        "force_interval_mean8": np.asarray(arrays["force_interval_mean_world_n"][index], dtype=float).ravel(),
        "force_interval_impulse8": np.asarray(arrays["force_interval_impulse_world_ns"][index], dtype=float).ravel(),
        "contact_fraction4": np.asarray(arrays["contact_fraction"][index], dtype=float),
        "smoothing_fraction4": np.asarray(arrays["smoothing_fraction"][index], dtype=float),
        "smoothing_weight_mean4": np.asarray(arrays["smoothing_weight_mean"][index], dtype=float),
        "event_counts16": np.asarray(arrays["event_counts16"][index], dtype=float),
        "force_active_mask4": np.asarray(arrays["force_active_mask"][index], dtype=bool),
        "sample_time_s": float(arrays["time_s"][index]),
        "target_time_s": float(arrays["time_s"][index + 1]),
        "source_index": index,
    }


def build_trajectory(arrays: dict[str, np.ndarray], trajectory_id: int, split: str) -> dict[str, np.ndarray]:
    params = ModelParams()
    samples = [build_sample(arrays, index, params) for index in range(1, len(arrays["time_s"]) - 1)]
    keys = [key for key in samples[0] if key not in {"sample_time_s", "target_time_s", "source_index"}]
    result = {key: np.asarray([sample[key] for sample in samples]) for key in keys}
    result["sample_time_s"] = np.asarray([sample["sample_time_s"] for sample in samples], dtype=float)
    result["target_time_s"] = np.asarray([sample["target_time_s"] for sample in samples], dtype=float)
    result["source_index"] = np.asarray([sample["source_index"] for sample in samples], dtype=int)
    result["trajectory_id"] = np.full(len(samples), trajectory_id, dtype=int)
    result["split"] = np.full(len(samples), split)
    return result


def concatenate(items: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {key: np.concatenate([item[key] for item in items], axis=0) for key in items[0]}


def save_network_interfaces(data_dir: Path, trajectories: list[tuple[dict, dict]]) -> None:
    payload = {}
    for interface_index, (_, arrays) in enumerate(trajectories[:2]):
        count = max(0, len(arrays["time_s"]) - 2)
        mask = np.ones((count, 4), dtype=bool)
        aoi = np.zeros((count, 4), dtype=float)
        start = count // 3
        stop = min(count, start + max(1, count // 10))
        mask[start:stop, interface_index] = False
        for index in range(start, stop):
            aoi[index, interface_index] = (index - start + 1) * 0.02
        payload[f"interface_{interface_index}_network_mask"] = mask
        payload[f"interface_{interface_index}_network_aoi_s"] = aoi
        payload[f"interface_{interface_index}_trajectory_id"] = np.asarray([interface_index], dtype=int)
    np.savez_compressed(data_dir / "network_interface_only.npz", **payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    level = "pilot" if args.pilot else "full"
    data_dir = args.project_root.resolve() / "revision_2026" / "connector_r3_4_data" / level / output.name
    data_dir.mkdir(parents=True, exist_ok=False)
    base_scenarios = PILOT_SCENARIOS if args.pilot else PILOT_SCENARIOS + FULL_EXTRA_SCENARIOS
    scenario_specs = []
    for scenario_index, scenario in enumerate(base_scenarios):
        split = "train" if scenario_index < max(3, len(base_scenarios) - 3) else ("validation" if scenario_index == len(base_scenarios) - 2 else "test")
        scenario_specs.append((scenario, scenario, split, 0))
    if not args.pilot:
        scenario_specs.extend((scenario, f"{scenario}_dev_seed1", "train", 1) for scenario in FULL_EXTRA_SCENARIOS)
    pilot_data_dir = args.project_root.resolve() / "revision_2026" / "connector_r3_4_data" / "pilot" / PILOT_RUN_ID
    pilot_manifest = {}
    if not args.pilot:
        with (pilot_data_dir / "trajectory_manifest.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            pilot_manifest = {(row["scenario"], row["plant"].split("-")[0]): row for row in csv.DictReader(stream)}
    started = time.perf_counter()
    manifest = []
    plant_data: dict[str, list[dict[str, np.ndarray]]] = {law: [] for _, law in PLANTS}
    trajectory_payloads = []
    trajectory_id = 0
    for scenario, manifest_scenario, split, seed in scenario_specs:
        for label, law in PLANTS:
            raw_path = data_dir / "raw" / f"trajectory_{trajectory_id:03d}_{manifest_scenario}_{law}.npz"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            reused = not args.pilot and scenario in PILOT_SCENARIOS and seed == 0
            progress = {"trajectory_id": trajectory_id, "scenario": manifest_scenario, "plant": law, "seed": seed, "mode": "REUSE_PILOT_RAW" if reused else "SIMULATE", "phase": "STARTED", "elapsed_s": time.perf_counter() - started}
            write_json(output / "trajectory_progress.json", progress)
            if reused:
                source_row = pilot_manifest[(scenario, law)]
                shutil.copy2(Path(source_row["raw_path"]), raw_path)
                progress.update({"phase": "RAW_COPIED", "elapsed_s": time.perf_counter() - started})
                write_json(output / "trajectory_progress.json", progress)
                with np.load(Path(source_row["raw_path"])) as source:
                    arrays = {key: source[key].copy() for key in source.files}
                summary = {"status": source_row["status"], "tire_raw_utilization_max": [float(source_row["tire_raw_utilization_max"])] * 4, "scenario": scenario, "law": law}
            else:
                summary, arrays = simulate(scenario, label, law, "ES", seed=seed)
                np.savez_compressed(raw_path, **arrays)
            progress.update({"phase": "RAW_READY", "elapsed_s": time.perf_counter() - started})
            write_json(output / "trajectory_progress.json", progress)
            samples = build_trajectory(arrays, trajectory_id, split)
            progress.update({"phase": "SAMPLES_READY", "elapsed_s": time.perf_counter() - started})
            write_json(output / "trajectory_progress.json", progress)
            plant_data[law].append(samples)
            digest = array_digest(arrays)
            manifest.append(
                {
                    "trajectory_id": trajectory_id,
                    "scenario": manifest_scenario,
                    "plant": f"{law}-ES",
                    "split": split,
                    "seed": seed,
                    "role": "development_coverage" if seed != 0 else "primary",
                    "samples": len(samples["sample_time_s"]),
                    "raw_path": str(raw_path),
                    "array_sha256": digest,
                    "status": summary["status"],
                    "tire_raw_utilization_max": max(summary["tire_raw_utilization_max"]),
                }
            )
            trajectory_payloads.append((summary, arrays))
            trajectory_id += 1
            progress.update({"phase": "COMPLETE", "elapsed_s": time.perf_counter() - started})
            write_json(output / "trajectory_progress.json", progress)
    combined_paths = {}
    for law, items in plant_data.items():
        combined = concatenate(items)
        path = data_dir / f"dataset_{law.lower()}_es.npz"
        np.savez_compressed(path, **combined)
        combined_paths[law] = str(path)
    save_network_interfaces(data_dir, trajectory_payloads)
    replay_summary, replay_arrays = simulate("straight", "V1-ES", "V1", "ES", seed=0)
    reference = next(arrays for summary, arrays in trajectory_payloads if summary["scenario"] == "straight" and summary["law"] == "V1")
    replay_equal = array_digest(reference) == array_digest(replay_arrays)
    write_csv(data_dir / "trajectory_manifest.csv", manifest)
    schemas = {name: build_schema(name) for name in ("S1_team", "S2_four", "S3_deform", "S4_force_in")}
    write_json(data_dir / "schema.json", schemas)
    verification_path = output / "data_verification.json"
    verification = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "verify_data_flow.py"), "--data-dir", str(data_dir), "--output", str(verification_path)],
        capture_output=True,
        text=True,
    )
    verification_payload = json.loads(verification_path.read_text(encoding="utf-8")) if verification_path.exists() else {"passed": False}
    data_complete = {
        "stage": "DATA_PILOT" if args.pilot else "DATA_FULL",
        "passed": all(row["status"] == "PASS" and row["tire_raw_utilization_max"] <= 0.9 for row in manifest) and replay_equal and verification.returncode == 0 and verification_payload.get("passed") is True,
        "trajectory_count": len(manifest),
        "clean_trajectory_count": len(manifest),
        "network_interface_trajectory_count": 2,
        "combined_paths": combined_paths,
        "data_dir": str(data_dir),
        "replay_equal": replay_equal,
        "replay_status": replay_summary["status"],
        "verification": verification_payload,
        "runtime_s": time.perf_counter() - started,
        "limitations": [] if args.pilot else ["Full dataset contains 26 physical trajectories rather than the suggested 100; no duplicated windows were introduced.", "Eight seed-1 directional development trajectories were added only to the training split after the F22 out-of-coverage diagnosis; the original validation/test trajectories were not moved."],
    }
    if not data_complete["passed"]:
        data_complete["repair_code"] = "DATA_GENERATION_OR_REPLAY"
        data_complete["next_action"] = "Inspect the first invalid manifest row or the first differing replay array before rebuilding combined files."
    write_json(data_dir / "complete.json", data_complete)
    write_json(output / "complete.json", data_complete)
    print(json.dumps(data_complete, ensure_ascii=False))
    raise SystemExit(0 if data_complete["passed"] else 2)


if __name__ == "__main__":
    main()
