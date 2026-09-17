from __future__ import annotations

import csv
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "plant"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_physics_focus import audit_f3
from contracts import write_json
from data_manifest import array_sha256, file_sha256, params_sha256
from generate_data import resolved_params, save_raw, simulate_trajectory
from scenarios import ScenarioSpec


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _simulate_job(job: tuple) -> dict:
    plant_root, spec, law, seed, params, protocol, load_enabled = job
    for path in (str(plant_root), str(ROOT / "src"), str(ROOT / "scripts")):
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        summary, arrays = simulate_trajectory(
            spec,
            law,
            seed,
            params,
            protocol,
            actuator_mode="dynamic",
            load_transfer_enabled=bool(load_enabled),
        )
        replay_summary, replay_arrays = simulate_trajectory(
            spec,
            law,
            seed,
            params,
            protocol,
            actuator_mode="dynamic",
            load_transfer_enabled=bool(load_enabled),
        )
        return {
            "ok": True,
            "summary": summary,
            "arrays": arrays,
            "replay_summary": replay_summary,
            "replay_array_sha256": array_sha256(replay_arrays),
        }
    except Exception:
        return {"ok": False, "traceback": traceback.format_exc()}


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "f3"
    output.mkdir(parents=True, exist_ok=False)
    data_root = project / "revision_2026" / "koopman_focus_data" / "f3" / run_dir.name
    data_root.mkdir(parents=True, exist_ok=False)
    config = protocol["f3"]
    plant_root = ROOT / "plant"
    jobs = []
    trajectory_id = 0
    pair_id = 0
    for base in config["base_families"]:
        seed = int(base["seed"])
        params = resolved_params(seed, protocol)
        for direction in config["directions"]:
            spec = ScenarioSpec("D2", direction, None, 100.0, True)
            for plant in config["plants"]:
                for load in config["load_modes"]:
                    identity = {
                        "trajectory_id": trajectory_id,
                        "pair_id": pair_id,
                        "base_family_id": f"F3_{base['split']}_D2_{seed}",
                        "split": base["split"],
                        "seed": seed,
                        "scenario": "D2",
                        "direction": direction,
                        "plant": plant["name"],
                        "law": plant["law"],
                        "actuator_mode": "dynamic",
                        "load_mode": load["name"],
                        "load_transfer_enabled": bool(load["enabled"]),
                    }
                    jobs.append(
                        (
                            identity,
                            params,
                            (
                                plant_root,
                                spec,
                                plant["law"],
                                seed,
                                params,
                                protocol,
                                bool(load["enabled"]),
                            ),
                        )
                    )
                    trajectory_id += 1
                pair_id += 1
    workers = int(protocol["resource_limits"]["parallel_workers"])
    if not 1 <= workers <= 4:
        raise ValueError("parallel_workers must be in [1,4]")
    manifest_rows = []
    trajectories = []
    failures = []
    print(f"F3 submitted {len(jobs)} first/replay jobs to {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_simulate_job, (job[2] for job in jobs), chunksize=1)
        for count, (job, result) in enumerate(zip(jobs, results), start=1):
            identity, params, _ = job
            if not result["ok"]:
                failure = {"identity": identity, "traceback": result["traceback"]}
                failures.append(failure)
                failure_dir = output / "failure"
                failure_dir.mkdir(parents=True, exist_ok=True)
                write_json(failure_dir / f"trajectory_{identity['trajectory_id']:04d}.json", failure)
                print(f"F3 failed {count}/{len(jobs)}: {identity}", flush=True)
                continue
            summary = result["summary"]
            arrays = result["arrays"]
            replay_summary = result["replay_summary"]
            replay_equal = bool(
                summary["trajectory_array_sha256"]
                == replay_summary["trajectory_array_sha256"]
                == result["replay_array_sha256"]
            )
            identity = {**identity, "replay_hash_match": replay_equal}
            stem = (
                f"trajectory_{identity['trajectory_id']:04d}_D2_{identity['direction']}_"
                f"{identity['plant']}_{identity['load_mode']}"
            )
            raw_path = data_root / "raw" / f"{stem}.npz"
            save_raw(raw_path, arrays, summary, params)
            manifest_rows.append(
                {
                    **identity,
                    "params_sha256": params_sha256(params),
                    "trajectory_array_sha256": summary["trajectory_array_sha256"],
                    "raw_file_sha256": file_sha256(raw_path),
                    "raw_path": str(raw_path),
                    "sample_count": summary["sample_count"],
                    "duration_s": summary["duration_s"],
                    "distance_m": summary["distance_m"],
                    "status": summary["status"],
                    "tire_raw_utilization_max": summary["tire_raw_utilization_max"],
                    "minimum_support_load_n": summary["minimum_support_load_n"],
                    "connector_force_peak_n": summary["force_peak_n"],
                }
            )
            trajectories.append((identity, arrays, summary))
            print(
                f"F3 completed {count}/{len(jobs)}: seed={identity['seed']} "
                f"{identity['direction']} {identity['plant']} {identity['load_mode']}",
                flush=True,
            )
    if manifest_rows:
        write_csv(output / "data_manifest.csv", manifest_rows)
        write_csv(data_root / "data_manifest.csv", manifest_rows)
    if failures:
        complete = {
            "stage": "F3",
            "passed": False,
            "repair_code": "F3_TRAJECTORY_EXCEPTION",
            "failed_trajectory_count": len(failures),
            "completed_trajectory_count": len(trajectories),
            "data_root": str(data_root),
            "runtime_s": time.perf_counter() - started,
            "next_action": "Inspect the first saved trajectory exception; F4 and all learning stages remain NOT_RUN.",
        }
        write_json(output / "complete.json", complete)
        return complete

    audit = audit_f3(trajectories, protocol, output)
    from plot_focus import plot_f3

    figures = plot_f3(trajectories, output)
    runtime_s = time.perf_counter() - started
    time_budget_passed = runtime_s <= 3600.0 * float(
        protocol["resource_limits"]["maximum_f3_hours"]
    )
    complete = {
        **audit,
        "passed": bool(audit["passed"] and time_budget_passed),
        "data_root": str(data_root),
        "runtime_s": runtime_s,
        "time_budget_passed": time_budget_passed,
        "manifest_path": str(output / "data_manifest.csv"),
        "manifest_sha256": file_sha256(output / "data_manifest.csv"),
        "replay_mismatch_count": sum(not bool(row["replay_hash_match"]) for row in manifest_rows),
        "figures": figures,
    }
    if not complete["passed"]:
        complete.update(
            {
                "repair_code": "F3_" + "_".join(name.upper() for name in audit["failed_gates"])
                if audit["failed_gates"]
                else "F3_TIME_BUDGET_EXCEEDED",
                "next_action": "Stop at F3, inspect the first failed hard gate, and keep F4/K0-K7/C0 NOT_RUN.",
            }
        )
        write_json(
            output / "failure" / "diagnosis.json",
            {
                "failed_gates": audit["failed_gates"],
                "tradeoff_review_required": audit["tradeoff_review_required"],
                "repair_code": complete["repair_code"],
            },
        )
    else:
        complete["next_action"] = (
            "F3 PASS with TRADEOFF_REVIEW; stop for human review before separately authorizing F4."
            if audit["tradeoff_review_required"]
            else "F3 PASS; stop for human review before separately authorizing F4."
        )
    write_json(output / "complete.json", complete)
    return complete
