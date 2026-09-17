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

from audit_physics_v2 import audit_p2
from contracts import write_json
from data_manifest import array_sha256, file_sha256, params_sha256
from generate_data import resolved_params, save_raw, simulate_trajectory
from scenarios import ScenarioSpec


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _simulate_job(job: tuple) -> tuple[dict, dict[str, np.ndarray], dict, str]:
    connector_src, spec, law, seed, params, protocol, mode = job
    connector_path = str(connector_src)
    if connector_path not in sys.path:
        sys.path.insert(0, connector_path)
    summary, arrays = simulate_trajectory(
        spec, law, seed, params, protocol, actuator_mode=mode
    )
    replay_summary, replay_arrays = simulate_trajectory(
        spec, law, seed, params, protocol, actuator_mode=mode
    )
    return summary, arrays, replay_summary, array_sha256(replay_arrays)


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "p2"
    output.mkdir(parents=True, exist_ok=False)
    data_root = (
        project
        / "revision_2026"
        / "koopman_next_v2_data"
        / "p2"
        / run_dir.name
    )
    data_root.mkdir(parents=True, exist_ok=False)
    connector_src = project / "revision_2026" / "connector_r3_4" / "src"
    connector_path = str(connector_src)
    if connector_path not in sys.path:
        sys.path.insert(0, connector_path)
    config = protocol["p2"]
    jobs = []
    trajectory_id = 0
    pair_id = 0
    for base in config["base_families"]:
        seed = int(base["seed"])
        params = resolved_params(seed, protocol)
        for direction in config["directions"]:
            spec = ScenarioSpec("D2", direction, None, 100.0, True)
            for plant in config["plants"]:
                for mode in config["actuator_modes"]:
                    identity = {
                        "trajectory_id": trajectory_id,
                        "pair_id": pair_id,
                        "base_family_id": f"P2_{base['split']}_D2_{seed}",
                        "split": base["split"],
                        "seed": seed,
                        "scenario": "D2",
                        "direction": direction,
                        "plant": plant["name"],
                        "law": plant["law"],
                        "actuator_mode": mode,
                    }
                    jobs.append(
                        (
                            identity,
                            params,
                            (
                                connector_src,
                                spec,
                                plant["law"],
                                seed,
                                params,
                                protocol,
                                mode,
                            ),
                        )
                    )
                    trajectory_id += 1
                pair_id += 1

    workers = int(config["parallel_workers"])
    if not 1 <= workers <= 4:
        raise ValueError(f"P2 parallel workers must be in [1,4], found {workers}")
    manifest_rows = []
    trajectories = []
    print(f"P2 submitted {len(jobs)} first/replay jobs to {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_simulate_job, (job[2] for job in jobs), chunksize=1)
        for count, (job, result) in enumerate(zip(jobs, results), start=1):
            identity, params, _ = job
            summary, arrays, replay_summary, replay_hash = result
            first_hash = summary["trajectory_array_sha256"]
            replay_equal = bool(
                first_hash
                == replay_summary["trajectory_array_sha256"]
                == replay_hash
            )
            identity = {**identity, "replay_hash_match": replay_equal}
            stem = (
                f"trajectory_{identity['trajectory_id']:04d}_D2_{identity['direction']}_"
                f"{identity['plant']}_{identity['actuator_mode']}"
            )
            raw_path = data_root / "raw" / f"{stem}.npz"
            save_raw(raw_path, arrays, summary, params)
            manifest_rows.append(
                {
                    **identity,
                    "params_sha256": params_sha256(params),
                    "trajectory_array_sha256": first_hash,
                    "raw_file_sha256": file_sha256(raw_path),
                    "raw_path": str(raw_path),
                    "sample_count": summary["sample_count"],
                    "duration_s": summary["duration_s"],
                    "distance_m": summary["distance_m"],
                    "status": summary["status"],
                    "tire_raw_utilization_max": summary["tire_raw_utilization_max"],
                    "connector_force_peak_n": summary["force_peak_n"],
                }
            )
            trajectories.append((identity, arrays, summary))
            print(
                f"P2 completed {count}/{len(jobs)}: seed={identity['seed']} "
                f"{identity['direction']} {identity['plant']} {identity['actuator_mode']}",
                flush=True,
            )

    write_csv(output / "data_manifest.csv", manifest_rows)
    write_csv(data_root / "data_manifest.csv", manifest_rows)
    audit = audit_p2(trajectories, protocol, output)
    runtime_s = time.perf_counter() - started
    complete = {
        **audit,
        "data_root": str(data_root),
        "runtime_s": runtime_s,
        "manifest_path": str(output / "data_manifest.csv"),
        "manifest_sha256": file_sha256(output / "data_manifest.csv"),
        "replay_mismatch_count": sum(
            not bool(row["replay_hash_match"]) for row in manifest_rows
        ),
    }
    complete["artifacts"] = {
        **complete["artifacts"],
        "data_manifest": str(output / "data_manifest.csv"),
        "raw_data_root": str(data_root / "raw"),
    }
    if not complete["passed"]:
        failed = output / "failure"
        failed.mkdir(parents=True, exist_ok=False)
        with (output / "physics_audit_v2.csv").open(
            "r", newline="", encoding="utf-8-sig"
        ) as stream:
            audit_rows = list(csv.DictReader(stream))
        candidate_failures = [
            row
            for row in audit_rows
            if row["actuator_mode"] == "dynamic" and row["passed"].lower() != "true"
        ]
        diagnosis = {
            "repair_code": "P2_" + "_".join(
                name.upper() for name in complete["failed_gates"]
            ),
            "failed_gates": complete["failed_gates"],
            "candidate_failures": candidate_failures,
            "next_action": (
                "Stop P2. Decompose feedforward/heading feedback and perform offline fixed-support "
                "versus quasi-static support-capacity diagnostics. Do not change heading_gain, "
                "request amplitude, seeds, speed, or the 0.90 threshold under this protocol."
            ),
        }
        write_json(failed / "diagnosis.json", diagnosis)
        complete.update(diagnosis)
    else:
        complete["next_action"] = (
            "Stop after P2 and inspect raw evidence. P2S requires separate authorization."
        )
    write_json(output / "complete.json", complete)
    return complete
