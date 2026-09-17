"""Preregistered universal Koopman enhancement experiment.

The first executable bottleneck is G1: the accepted plant/data contract must
demonstrate safe 50--80% rated-force coverage before any new module is fitted.
This entry point therefore implements T0 and the preregistered T1 feasibility
scan first.  Downstream stages are never allowed to cross a failed G1.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
from pathlib import Path
import sys
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
REV = HERE.parent
PROJECT = REV.parent
OUT = HERE / "universal"
COMPARE = HERE / "compare"
MODEL_DIR = REV / "model"
for item in (HERE, MODEL_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import generate_k2 as base  # noqa: E402
import generate_compare as compare_gen  # noqa: E402
from four_vehicle_coupled import system_derivative  # noqa: E402


DT = base.CONTROL_DT
PLANT_DT = base.PLANT_DT
SUBSTEPS = base.SUBSTEPS
PROTOCOL = OUT / "protocol.md"
SCENES = ("E0", "E1", "E2", "E3", "E4", "E5", "E6", "E9")
EXPECTED_MACRO = {
    "K0": 0.12513541290453,
    "K1": 0.13283731952714747,
    "K2": 0.4023273784857165,
    "K3": 0.44346566324356557,
    "K3-r2": 0.44346566324356557,
    "K4": 0.40143743177289654,
    "K5-linear": 0.16730901051004596,
    "K5-bilinear": 3928981162.612287,
}


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def append_log(identifier: str, title: str, lines: list[str]) -> None:
    block = "\n\n## " + identifier + " — " + title + "\n\n" + "\n".join(f"- {line}" for line in lines) + "\n"
    for path in (OUT / "work_log.md", REV / "work_log.md"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(block)


def planned_seeds() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, scene in enumerate(SCENES):
        for split, offsets in (("train", range(30)), ("validation", range(100, 108)), ("development-test", range(200, 208))):
            for offset in offsets:
                rows.append({"stage": "D1", "split": split, "scene": scene, "seed": 910000 + 1000 * index + offset})
    for task in range(38):
        split = "train" if task < 20 else "validation" if task < 25 else "development-test" if task < 30 else "future-confirm"
        for traj, scene in enumerate(("E1", "E2", "E3")):
            rows.append({"stage": "parameter", "split": split, "scene": scene, "task": task, "seed": 930000 + 10 * task + traj})
    for profile_index, profile in enumerate(("iid", "burst", "delay", "dos", "reorder")):
        for trace in range(40):
            rows.append({"stage": "network", "split": "planned", "profile": profile, "trace": trace, "seed": 940000 + 100 * profile_index + trace})
    for index, scene in enumerate(SCENES):
        for offset in range(20):
            rows.append({"stage": "D2-internal", "split": "future-confirm", "scene": scene, "seed": 960000 + 1000 * index + offset})
    for task in range(8):
        for traj, scene in enumerate(("E1", "E2", "E3")):
            rows.append({"stage": "D2-external", "split": "future-confirm", "scene": scene, "task": task + 30, "seed": 970000 + 10 * task + traj})
    for profile_index, profile in enumerate(("iid", "burst", "delay", "dos")):
        for trace in range(10):
            rows.append({"stage": "D2-network", "split": "future-confirm", "profile": profile, "trace": trace, "seed": 980000 + 100 * profile_index + trace})
    return rows


def historical_macro() -> dict[str, float]:
    path = COMPARE / "t4" / "confirm_results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, float] = {}
    for model, block in data.items():
        values = [float(row["J_pred"]) for label, row in block["macro_by_label"].items() if label in {f"E{i}" for i in range(9)}]
        result[model] = float(np.mean(values))
    return result


def run_t0() -> bool:
    stage = OUT / "t0"
    complete = stage / "complete.json"
    had_failed = (stage / "failed.json").exists()
    if complete.exists():
        data = json.loads(complete.read_text(encoding="utf-8"))
        if data.get("protocol_sha256") == sha256(PROTOCOL):
            print("T0 already complete and protocol hash matches", flush=True)
            return bool(data.get("accepted"))

    required = {
        "protocol": PROTOCOL,
        "compare_t0_freeze": COMPARE / "t0" / "freeze.json",
        "compare_t2_complete": COMPARE / "t2" / "complete.json",
        "compare_t3_complete": COMPARE / "t3" / "complete.json",
        "compare_t4_results": COMPARE / "t4" / "confirm_results.json",
        "compare_t4_gates": COMPARE / "t4" / "final_gates.json",
        "compare_confirm_manifest": COMPARE / "confirm" / "manifest.json",
        "K2": COMPARE / "models" / "K2.npz",
        "K3": COMPARE / "models" / "K3.npz",
        "K3-r2": COMPARE / "models" / "K3-r2.npz",
        "K4": COMPARE / "models" / "K4.npz",
        "K5-linear": COMPARE / "models" / "K5-linear.npz",
        "K5-bilinear": COMPARE / "models" / "K5-bilinear.npz",
        "normalizers": HERE / "k01" / "matrices.npz",
        "generator": HERE / "generate_compare.py",
        "compare_pipeline": HERE / "compare_pipeline.py",
        "universal_pipeline": Path(__file__).resolve(),
    }
    missing = [name for name, path in required.items() if not path.exists()]
    hashes = {name: {"path": str(path), "sha256": sha256(path)} for name, path in required.items() if path.exists()}
    t0_freeze = json.loads((COMPARE / "t0" / "freeze.json").read_text(encoding="utf-8"))
    t2 = json.loads((COMPARE / "t2" / "complete.json").read_text(encoding="utf-8"))
    t3 = json.loads((COMPARE / "t3" / "complete.json").read_text(encoding="utf-8"))
    expected_hashes = {
        "K2": t2["models"]["K2"]["sha256"], "K3": t2["models"]["K3"]["sha256"], "K3-r2": t2["models"]["K3-r2"]["sha256"],
        "K4": t3["selected"]["K4"]["sha256"], "K5-linear": t3["selected"]["K5-linear"]["sha256"], "K5-bilinear": t3["selected"]["K5-bilinear"]["sha256"],
    }
    artifact_match = {name: hashes.get(name, {}).get("sha256") == value for name, value in expected_hashes.items()}
    confirm_manifest = json.loads((COMPARE / "confirm" / "manifest.json").read_text(encoding="utf-8"))
    trajectories = confirm_manifest.get("completed", confirm_manifest.get("trajectories", []))
    confirm_files_ok = len(trajectories) == 140 and all((COMPARE / "confirm" / row["file"]).exists() for row in trajectories)
    macro = historical_macro()
    macro_match = {name: abs(macro.get(name, math.inf) - expected) <= 1e-10 for name, expected in EXPECTED_MACRO.items()}
    accepted = not missing and all(artifact_match.values()) and confirm_files_ok and all(macro_match.values())

    seed_rows = planned_seeds()
    seed_fields = sorted({key for row in seed_rows for key in row})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "seed_table.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=seed_fields)
        writer.writeheader(); writer.writerows(seed_rows)
    backbone_rows = []
    for name in EXPECTED_MACRO:
        artifact = name if name in hashes else "historical K0/K1 in k01 matrices"
        backbone_rows.append({"backbone": name, "artifact": artifact, "artifact_sha256": hashes.get(name, {}).get("sha256", t0_freeze.get(f"{name}_sha256", "")), "confirm_macro_J_pred": macro.get(name), "G0_macro_match": macro_match.get(name, False)})
    with (OUT / "backbone_audit.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(backbone_rows[0])); writer.writeheader(); writer.writerows(backbone_rows)
    manifest = {
        "stage": "T0", "protocol_sha256": sha256(PROTOCOL), "files": hashes,
        "historical_K0_sha256": t0_freeze.get("K0_sha256"), "historical_K1_sha256": t0_freeze.get("K1_sha256"),
        "expected_artifact_hashes": expected_hashes, "artifact_hash_match": artifact_match,
        "confirm_trajectory_count": len(trajectories), "confirm_files_ok": confirm_files_ok,
        "macro_reaudit": macro, "macro_match_to_frozen_exact_values": macro_match,
        "python": sys.version, "platform": platform.platform(),
    }
    write_json(OUT / "manifest.json", manifest)
    write_json(OUT / "protocol.json", {
        "protocol_sha256": sha256(PROTOCOL), "control_dt_s": DT, "plant_dt_s": PLANT_DT, "substeps": SUBSTEPS,
        "scenes": list(SCENES), "load_bins": [[0, .1], [.1, .3], [.3, .5], [.5, .8]],
        "coarse_scan": {"speeds": [1.0, 2.5, 4.0], "front_deg": [10.0, 15.0], "rear_ratios": [-.5, -1.0], "modes": ["none", "front-rear", "left-right", "diagonal"], "profiles": ["hold", "reversal"]},
    })
    if accepted and had_failed:
        archived = stage / "failed_initial_precision.json"
        if not archived.exists():
            (stage / "failed.json").replace(archived)
    write_json(complete if accepted else stage / "failed.json", {"stage": "T0", "accepted": accepted, "protocol_sha256": sha256(PROTOCOL), "missing": missing, "artifact_match": artifact_match, "confirm_files_ok": confirm_files_ok, "macro_match": macro_match})
    retry_note = "首次G0因K5-bilinear十位数量级均值的手工常数少保留约4.77e-7而失败；已用冻结JSON经Python计算的精确float修复并保留初始失败文件，未改模型/数据/协议。" if had_failed else "无实现重试。"
    append_log("W0053R" if had_failed else "W0053", "普适性实验T0冻结与历史复现门", [
        f"协议hash={sha256(PROTOCOL)}；执行脚本hash={sha256(Path(__file__).resolve())}。",
        f"B0–B5B artifact匹配={artifact_match}；历史140条confirm文件完整={confirm_files_ok}。",
        f"冻结结果只读macro复核={macro}；G0={'PASS' if accepted else 'FAIL'}。",
        retry_note,
        "本阶段未生成D1/D2、未训练F/H/T/C/A、未启动闭环。",
    ])
    print(f"T0 {'PASS' if accepted else 'FAIL'}", flush=True)
    return accepted


def smooth01(x: float) -> float:
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)


def excitation_signal(t: float, profile: str) -> float:
    if t < 2.0 or t >= 14.0:
        return 0.0
    if t < 4.0:
        return smooth01((t - 2.0) / 2.0)
    if profile == "hold":
        return 1.0 if t < 12.0 else 1.0 - smooth01((t - 12.0) / 2.0)
    if t < 7.0:
        return 1.0
    if t < 9.0:
        return 1.0 - 2.0 * smooth01((t - 7.0) / 2.0)
    if t < 12.0:
        return -1.0
    return -1.0 + smooth01((t - 12.0) / 2.0)


MODES = {
    "none": np.zeros(4),
    "front-rear": np.array([1.0, 1.0, -1.0, -1.0]),
    "left-right": np.array([1.0, -1.0, 1.0, -1.0]),
    "diagonal": np.array([1.0, -1.0, -1.0, 1.0]),
}


def classify_windows(force_norm: np.ndarray, force_body: np.ndarray, penetration: np.ndarray, rated: float, steering: np.ndarray | None = None) -> dict[str, int]:
    counts = {key: 0 for key in ("L0", "L1", "L2", "L3", "L4-high", "R0", "R1", "R2", "R3", "R4", "R5")}
    contact = penetration > 0.0
    q_fr = .5 * ((force_body[:, 0, 0] + force_body[:, 1, 0]) - (force_body[:, 2, 0] + force_body[:, 3, 0]))
    q_lr = .5 * ((force_body[:, 0, 1] + force_body[:, 2, 1]) - (force_body[:, 1, 1] + force_body[:, 3, 1]))
    onset = np.any((~contact[:-1]) & contact[1:], axis=1)
    release = np.any(contact[:-1] & (~contact[1:]), axis=1)
    floor = .01 * rated
    for start in range(0, len(force_norm) - 19, 20):
        stop = start + 20
        ratio = float(np.max(force_norm[start:stop]) / rated)
        if ratio < .1: counts["L0"] += 1
        elif ratio < .3: counts["L1"] += 1
        elif ratio < .5: counts["L2"] += 1
        elif ratio <= .8: counts["L3"] += 1
        else: counts["L4-high"] += 1
        lo, hi = max(0, start - 10), min(len(onset), stop + 10)
        is_onset, is_release = bool(np.any(onset[lo:hi])), bool(np.any(release[lo:hi]))
        if not np.any(contact[start:stop]): counts["R0"] += 1
        if is_onset: counts["R1"] += 1
        if is_release: counts["R3"] += 1
        if np.any(contact[start:stop]) and not is_onset and not is_release: counts["R2"] += 1
        fb = force_body[start:stop]
        reversal = False
        for point in range(4):
            for axis in range(2):
                series = fb[:, point, axis]
                if np.any(series >= floor) and np.any(series <= -floor): reversal = True
        counts["R4"] += int(reversal)
        counts["R5"] += int(max(float(np.max(np.abs(q_fr[start:stop]))), float(np.max(np.abs(q_lr[start:stop])))) >= .1 * rated)
    return counts


def coverage_candidates(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    bins = {"L1": (.1, .3), "L2": (.3, .5), "L3": (.5, .8)}
    selected: dict[str, list[dict[str, Any]]] = {}
    for tier, (low, high) in bins.items():
        pool = [row for row in rows if row["accepted"] and low <= float(row["max_force_ratio"]) < high and int(row[f"windows_{tier}"]) > 0]
        chosen = []
        for profile in ("hold", "reversal"):
            subset = sorted((row for row in pool if row["profile"] == profile), key=lambda row: (int(row[f"windows_{tier}"]), -float(row["max_connector_force_n"])), reverse=True)
            chosen.extend(subset[:3])
        if not chosen:
            raise RuntimeError(f"no safe feasibility configuration for {tier}")
        selected[tier] = chosen
    return selected


def d1_jobs() -> list[dict[str, Any]]:
    jobs = []
    for index, scene in enumerate(SCENES):
        for split, offsets in (("train", range(30)), ("validation", range(100, 108)), ("development-test", range(200, 208))):
            for offset in offsets:
                jobs.append({"scenario": scene, "physical_scene": scene, "scene_index": index, "split": split, "offset": offset, "seed": 910000 + 1000 * index + offset, "traj_id": offset, "external": False, "parameter_external": False, "network_profile": "clean", "network_trace_id": "clean"})
    assert len(jobs) == 368
    return jobs


def simulate_d1(job: dict[str, Any], scales: dict[str, Any], config: dict[str, Any] | None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    original_physical = compare_gen.physical_command
    original_e9 = compare_gen.e9_excitation
    original_allocate = base.allocate_controls
    current = {"signal": 0.0, "sign": 1.0}

    def physical_wrapper(scene: str, t: float, speed: float, phase: float, sign: float) -> tuple[float, float, float]:
        if config is None or t >= 14.0:
            current["signal"] = 0.0
            return original_physical(scene, t, speed, phase, sign)
        signal = excitation_signal(t, str(config["profile"]))
        current["signal"] = signal; current["sign"] = sign
        return base.target_speed_accel(speed, float(config["speed"])), sign * float(config["front_deg"]) * signal, sign * float(config["rear_ratio"]) * float(config["front_deg"]) * signal

    def e9_wrapper(t: float, phase: float, local_scales: dict[str, np.ndarray]) -> tuple[float, float, float, np.ndarray]:
        if config is None or t >= 14.0:
            current["signal"] = 0.0
            return original_e9(t, phase, local_scales)
        signal = excitation_signal(t, str(config["profile"]))
        sign = 1.0 if math.sin(phase) >= 0.0 else -1.0
        current["signal"] = signal; current["sign"] = sign
        accel_correction = base.target_speed_accel(0.0, float(config["speed"])) - base.target_speed_accel(0.0, 2.2)
        return accel_correction, sign * float(config["front_deg"]) * signal, sign * float(config["rear_ratio"]) * float(config["front_deg"]) * signal, np.zeros(4)

    def allocation_wrapper(state: np.ndarray, accel: float, front: float, rear: float, params: Any, cfg: Any) -> tuple[np.ndarray, dict[str, Any]]:
        controls, allocation = original_allocate(state, accel, front, rear, params, cfg)
        if config is not None:
            amplitude = 0.0 if config["mode"] == "none" else 1.2
            controls[:, 0] = np.clip(controls[:, 0] + amplitude * current["signal"] * current["sign"] * MODES[str(config["mode"])], -1.4, 1.2)
        return controls, allocation

    compare_gen.physical_command = physical_wrapper
    compare_gen.e9_excitation = e9_wrapper
    base.allocate_controls = allocation_wrapper
    try:
        arrays, metadata = compare_gen.simulate(job, scales)
    finally:
        compare_gen.physical_command = original_physical
        compare_gen.e9_excitation = original_e9
        base.allocate_controls = original_allocate
    metadata["coverage_tier"] = "nominal" if config is None else str(job["coverage_tier"])
    metadata["coverage_config_id"] = None if config is None else int(config["config_id"])
    return arrays, metadata


def load_scan_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("config_id", "seed", "completed_steps", "windows_L0", "windows_L1", "windows_L2", "windows_L3", "windows_L4-high", "windows_R0", "windows_R1", "windows_R2", "windows_R3", "windows_R4", "windows_R5"):
            if key in row: row[key] = int(row[key])
        for key in ("speed", "front_deg", "rear_ratio", "max_connector_force_n", "max_force_ratio"):
            if key in row: row[key] = float(row[key])
        row["accepted"] = str(row["accepted"]).lower() == "true"
    return rows


def generate_parameter_tasks() -> None:
    path = OUT / "parameter_tasks.csv"
    if path.exists(): return
    rng = np.random.default_rng(906001)
    ranges = np.array([[.85, 1.15], [.75, 1.25], [.70, 1.30], [.70, 1.40], [.80, 1.10]])
    best, best_min = None, -math.inf
    for _ in range(100):
        unit = np.column_stack([(rng.permutation(38) + rng.random(38)) / 38.0 for _ in range(5)])
        distance = np.linalg.norm(unit[:, None, :] - unit[None, :, :], axis=2); distance += np.eye(38) * 1e9
        score = float(np.min(distance))
        if score > best_min: best, best_min = unit, score
    values = ranges[:, 0] + np.asarray(best) * (ranges[:, 1] - ranges[:, 0])
    fields = ("task_id", "split", "payload_mass_scale", "connector_stiffness_scale", "connector_damping_scale", "connector_free_play_scale", "vehicle_mu_scale")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for task, value in enumerate(values):
            split = "train" if task < 20 else "validation" if task < 25 else "development-test" if task < 30 else "future-confirm"
            writer.writerow(dict(zip(fields, [task, split, *value.tolist()])))


def generate_network_traces() -> None:
    path = OUT / "network_traces.npz"
    if path.exists(): return
    profiles = ("iid", "burst", "delay", "dos", "reorder")
    arrays = {}
    steps = 2200
    for profile_index, profile in enumerate(profiles):
        for trace in range(40):
            rng = np.random.default_rng(940000 + 100 * profile_index + trace)
            drop = np.zeros(steps, dtype=np.int8); delay = np.zeros(steps, dtype=np.int16)
            if profile == "iid": drop = (rng.random(steps) < .25).astype(np.int8)
            elif profile == "burst":
                drop = (rng.random(steps) < .08).astype(np.int8)
                for begin in (300, 800, 1500): drop[begin:begin + 75] = 1
            elif profile == "delay": delay = rng.integers(3, 9, size=steps, dtype=np.int16)
            elif profile == "dos": drop[350:550] = 1; drop[1100:1300] = 1
            elif profile == "reorder": delay = rng.integers(0, 7, size=steps, dtype=np.int16); delay[600:700] = np.arange(100, dtype=np.int16) % 9
            aoi = np.zeros(steps, dtype=np.int16)
            for k in range(steps): aoi[k] = (aoi[k-1] + 1 if k and drop[k] else delay[k])
            arrays[f"{profile}_{trace:02d}"] = np.column_stack([drop, delay, aoi]).astype(np.int16)
    np.savez_compressed(path, **arrays)


def complete_d1() -> bool:
    stage = OUT / "t1"
    data_root = OUT / "d1"
    traj_dir = data_root / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    scan_rows = load_scan_rows(stage / "force_coverage_scan.csv")
    candidates = coverage_candidates(scan_rows)
    config_freeze = OUT / "d1_config.json"
    frozen = {tier: [{key: row[key] for key in ("config_id", "speed", "front_deg", "rear_ratio", "mode", "profile", "max_force_ratio", f"windows_{tier}")} for row in values] for tier, values in candidates.items()}
    if config_freeze.exists():
        if json.loads(config_freeze.read_text(encoding="utf-8"))["selected"] != clean(frozen): raise RuntimeError("D1 coverage configuration changed")
    else:
        write_json(config_freeze, {"selection_rule": "top 3 target-bin windows within each hold/reversal profile; E0/E1 nominal; E2-E6/E9 balanced L1/L2/L3 by frozen offset", "selected": frozen, "scan_csv_sha256": sha256(stage / "force_coverage_scan.csv")})
    scales = compare_gen.train_scales(HERE / "k2" / "data_full")
    manifest_rows = []
    failures = []
    jobs = d1_jobs()
    tier_scenes = set(("E2", "E3", "E4", "E5", "E6", "E9"))
    for index, job in enumerate(jobs):
        tier = None if job["scenario"] not in tier_scenes else ("L1", "L2", "L3")[(int(job["offset"]) + int(job["scene_index"])) % 3]
        config = None if tier is None else candidates[tier][(int(job["offset"]) + int(job["scene_index"])) % len(candidates[tier])]
        job["coverage_tier"] = "nominal" if tier is None else tier
        name = f"{job['split']}_{job['scenario']}_{job['seed']}.npz"
        path = traj_dir / name
        try:
            if path.exists():
                with np.load(path, allow_pickle=False) as source: metadata = json.loads(str(source["metadata_json"].item()))
                if int(metadata["seed"]) != int(job["seed"]): raise RuntimeError("resume seed mismatch")
            else:
                arrays, metadata = simulate_d1(job, scales, config)
                np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
            with np.load(path, allow_pickle=False) as source:
                force_body = np.asarray(source["force_body"], dtype=float)[:-1]
                displacement = np.asarray(source["displacement_body"], dtype=float)[:-1]
                u3 = np.asarray(source["u3_alloc"], dtype=float)
            rated = float(metadata["params"]["connector"]["rated_force_n"]); free = float(metadata["params"]["connector"]["free_play_m"])
            force_norm = np.linalg.norm(force_body, axis=2); penetration = np.maximum(np.linalg.norm(displacement, axis=2) - free, 0.0)
            counts = classify_windows(force_norm, force_body, penetration, rated, u3[:, 8] if u3.ndim == 2 and u3.shape[1] > 8 else None)
            row = {**metadata, "file": str(path.relative_to(data_root)), "sha256": sha256(path), **{f"windows_{key}": value for key, value in counts.items()}}
            manifest_rows.append(row)
            print(f"D1 [{index+1:03d}/368] {name} tier={job['coverage_tier']} force={metadata['max_connector_force_n']:.1f}N L3={counts['L3']}", flush=True)
        except Exception as exc:
            failures.append({"job": job, "error": repr(exc), "file": str(path)})
            print(f"D1 FAILED {name}: {exc!r}", flush=True); break
    totals = {}
    for split in ("train", "validation", "development-test"):
        subset = [row for row in manifest_rows if row["split"] == split]
        totals[split] = {key: int(sum(int(row.get(f"windows_{key}", 0)) for row in subset)) for key in ("L0", "L1", "L2", "L3", "L4-high", "R0", "R1", "R2", "R3", "R4", "R5")}
        totals[split]["trajectories"] = len(subset)
    thresholds = {"train": 1000, "validation": 200, "development-test": 200}
    coverage_pass = not failures and len(manifest_rows) == 368 and all(totals[split][key] >= thresholds[split] for split in thresholds for key in ("L0", "L1", "L2", "L3", "R1", "R3", "R4"))
    write_json(data_root / "manifest.json", {"accepted": not failures and len(manifest_rows) == 368, "planned": 368, "completed": len(manifest_rows), "failures": failures, "coverage": totals, "trajectories": manifest_rows})
    fields = ["split", "threshold", *totals["train"].keys()]
    with (OUT / "coverage_counts.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for split, values in totals.items(): writer.writerow({"split": split, "threshold": thresholds[split], **values})
    if coverage_pass:
        generate_parameter_tasks(); generate_network_traces()
        write_json(stage / "complete.json", {"stage": "T1", "accepted": True, "status": "full_G1_pass", "coverage": totals, "d1_manifest_sha256": sha256(data_root / "manifest.json"), "parameter_tasks_sha256": sha256(OUT / "parameter_tasks.csv"), "network_traces_sha256": sha256(OUT / "network_traces.npz")})
        append_log("W0055", "普适性实验D1数据与完整G1覆盖门", [f"D1 368条全部生成并按整轨迹划分；覆盖={totals}。", "G1完整覆盖门=PASS；参数任务表和200条冻结网络trace已生成。", f"D1 manifest hash={sha256(data_root/'manifest.json')}。"])
        return True
    write_json(stage / "complete.json", {"stage": "T1", "accepted": False, "status": "failed_full_D1_coverage", "coverage": totals, "failures": failures, "downstream": {f"T{i}": "not_applicable_upstream_G1_failed" for i in range(2, 10)}})
    summary = json.loads((stage / "coverage_summary.json").read_text(encoding="utf-8")); write_solutions(summary)
    with (OUT / "solutions.md").open("a", encoding="utf-8") as handle: handle.write("\n## D1完整计数\n\n```json\n" + json.dumps(totals, ensure_ascii=False, indent=2) + "\n```\n\n可行性扫描能到达L3，但D1的预注册分层计数未全部满足；不得据此训练后续模块。\n")
    write_json(OUT / "stage_status.json", {"T0": "passed", "T1": "failed_full_D1_coverage", **{f"T{i}": "not_applicable_upstream_G1_failed" for i in range(2, 10)}})
    append_log("W0055", "普适性实验D1数据与完整G1覆盖门", [f"D1完成={len(manifest_rows)}/368，失败={failures}；覆盖={totals}。", "G1完整覆盖门=FAIL；按协议停止T2–T9。", f"D1 manifest hash={sha256(data_root/'manifest.json')}；solutions hash={sha256(OUT/'solutions.md')}。"])
    return False


def finalize_g1_stop() -> None:
    stage = OUT / "t1"
    completed = json.loads((stage / "complete.json").read_text(encoding="utf-8"))
    if completed.get("status") != "failed_full_D1_coverage": return
    manifest = json.loads((OUT / "d1" / "manifest.json").read_text(encoding="utf-8"))
    totals = completed["coverage"]
    direction = {split: {axis: {"positive": 0, "negative": 0, "zero": 0} for axis in ("Q_FR", "Q_LR", "steering")} for split in ("train", "validation", "development-test")}
    max_force = max_icr = max_tire = 0.0
    ultimate_steps = 0
    for row in manifest["trajectories"]:
        split = row["split"]
        max_force = max(max_force, float(row["max_connector_force_n"])); max_icr = max(max_icr, float(row["icr_residual_peak_mps"])); max_tire = max(max_tire, float(row["max_tire_utilization"])); ultimate_steps += int(row["ultimate_exceeded_steps"])
        path = OUT / "d1" / row["file"]
        with np.load(path, allow_pickle=False) as source:
            fb = np.asarray(source["force_body"], dtype=float)[:-1]
            u3 = np.asarray(source["u3_alloc"], dtype=float)
        qfr = .5 * ((fb[:, 0, 0] + fb[:, 1, 0]) - (fb[:, 2, 0] + fb[:, 3, 0]))
        qlr = .5 * ((fb[:, 0, 1] + fb[:, 2, 1]) - (fb[:, 1, 1] + fb[:, 3, 1]))
        steering = u3[:, 8] if u3.shape[1] > 8 else np.zeros(len(u3))
        for start in range(0, len(fb) - 19, 20):
            for axis, series in (("Q_FR", qfr), ("Q_LR", qlr), ("steering", steering)):
                window = series[start:start+20]; value = float(window[np.argmax(np.abs(window))])
                label = "positive" if value > 1e-12 else "negative" if value < -1e-12 else "zero"
                direction[split][axis][label] += 1
    direction_pass = {}
    for split, axes in direction.items():
        direction_pass[split] = {}
        for axis, counts in axes.items():
            nonzero = counts["positive"] + counts["negative"]
            counts["positive_fraction_nonzero"] = counts["positive"] / max(nonzero, 1)
            counts["negative_fraction_nonzero"] = counts["negative"] / max(nonzero, 1)
            direction_pass[split][axis] = bool(min(counts["positive_fraction_nonzero"], counts["negative_fraction_nonzero"]) >= .2)
    write_json(OUT / "direction_balance.json", {"definition": "sign of maximum-absolute Q_FR, Q_LR and virtual-front-steering value in every non-overlapping 20-step window", "counts": direction, "pass_min_20pct_each_sign": direction_pass})

    keys = ("L0", "L1", "L2", "L3", "R1", "R3", "R4")
    splits = ("train", "validation", "development-test")
    threshold = {"train": 1000, "validation": 200, "development-test": 200}
    x = np.arange(len(keys)); width = .25
    fig, ax = plt.subplots(figsize=(11, 5.6), constrained_layout=True)
    for index, split in enumerate(splits):
        ratio = [totals[split][key] / threshold[split] for key in keys]
        bars = ax.bar(x + (index-1)*width, ratio, width, label=split)
        for bar, value in zip(bars, [totals[split][key] for key in keys]): ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+.025, str(value), ha="center", va="bottom", fontsize=8, rotation=90)
    ax.axhline(1.0, color="#b33b3b", ls="--", label="preregistered minimum")
    ax.set_xticks(x, keys); ax.set_ylabel("count / split-specific minimum"); ax.set_ylim(0, max(4.2, ax.get_ylim()[1])); ax.grid(axis="y", alpha=.25); ax.legend(ncol=4)
    ax.set_title("D1 non-overlapping 20-step coverage gates")
    fig.savefig(OUT / "d1_coverage.png", dpi=180); plt.close(fig)

    shortfall = 1000 - int(totals["train"]["L3"])
    solutions = f"""# 普适性实验G1停止与解决方案

## 已核实事实

- 预注册96配置扫描全部成功，24个配置进入L3；前5名五seed重复全部5/5复现。扫描证明当前plant和控制合同可以安全到达L3，但不等于D1覆盖自动充足。
- D1按冻结seed生成368/368条，train/validation/development-test分别为240/64/64条；没有删除失败轨迹，也没有发生非有限、ultimate或共同ICR失败。
- train覆盖：L0/L1/L2/L3=`{totals['train']['L0']}/{totals['train']['L1']}/{totals['train']['L2']}/{totals['train']['L3']}`，L3要求1000，实际短缺`{shortfall}`窗（7.3%）。
- validation L3=`{totals['validation']['L3']}/200`，development-test L3=`{totals['development-test']['L3']}/200`，均通过。
- train R1/R3/R4=`{totals['train']['R1']}/{totals['train']['R3']}/{totals['train']['R4']}`；R4只比1000多19窗，说明反转覆盖也处在边缘。
- D1最大连接力`{max_force:.2f} N`，最大共同ICR残差`{max_icr:.3e} m/s`，ultimate超限步数`{ultimate_steps}`。

## 停止原因

G1是联合门，train L3的`927<1000`已经足以判失败。看到这个结果后再把L2轨迹改成L3、追加未冻结seed、重分split或把门槛改成927，都会把覆盖集变成结果驱动设计。按协议，T2–T9均为`not_applicable_upstream_G1_failed`；本轮没有训练F/H/RLS/T/C/A，也没有生成D2或启动闭环。

## 最可能原因与替代解释

1. 目标L3轨迹受内部质量、刚度、阻尼、free-play和附着扰动影响，单条实际L3窗只有约4–23个；按轨迹数量均衡不等于按最终窗口数量均衡。
2. 为保留E0/E1的直线语义，这两个场景没有强行叠加15°转向；因此L3主要由E2–E6/E9承担。
3. 这不是“模型训练失败”，因为任何新增模型尚未训练；它是样本量/覆盖合同失败。

## 可验证方案、成本和风险

1. 新建而不是回改本协议：把本轮D1作为独立pilot，用其L3均值和最差轨迹预先计算新训练集规模。按当前短缺，数学最低约需6条典型L3轨迹；考虑20%覆盖余量，建议预注册增加9–12条train轨迹并同步增加validation/development，不能只补train到刚好1000。
2. 新协议采用“先冻结每个split的候选seed池，再全部生成并按安全/覆盖规则整体接受或整体失败”，避免逐条挑seed。成本约1–2小时生成和约数百MB存储；风险是新参数扰动仍使L3波动。
3. 若改成按运行分布分位数定义载荷档，研究问题会从“额定力覆盖”变成“常用载荷域覆盖”，必须重新生成盲confirm并修改论文主张，不能用来挽救本轮G1。
4. 不建议降低1000门、重复使用相邻滑窗凑数、提高刚度/降低额定力或放宽ultimate；这些做法分别造成统计伪重复或改变物理系统。

## 当前结论边界

本轮只证明强受力轨迹在现有plant中可安全生成，但预注册D1训练覆盖尚未达标。因而不能评价F/H组合的跨骨干普适性，也不能把T2–T9的未执行写成方法负结果。上一轮K0/K1普通载荷域结论保持不变。
"""
    (OUT / "solutions.md").write_text(solutions, encoding="utf-8")
    report = f"""# Koopman组合普适性实验停止报告

## 结论

本轮在G1停止。96配置安全可行性扫描通过，D1的368条轨迹也全部成功生成，但train的50–80%额定力L3覆盖为`927/1000`，少73个互不重叠20步窗。因此没有合法证据进入骨干审计和F/H等模块训练。

这不是“组合方法无效”的证据；它只说明本轮预注册训练数据覆盖不足。T2–T9均按协议记为不适用，未生成新盲确认集、未运行MPC/闭环。

## G1计数

| split | L0 | L1 | L2 | L3 | R1 | R3 | R4 | 门槛 | 判定 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| train | {totals['train']['L0']} | {totals['train']['L1']} | {totals['train']['L2']} | **{totals['train']['L3']}** | {totals['train']['R1']} | {totals['train']['R3']} | {totals['train']['R4']} | 1000 | FAIL |
| validation | {totals['validation']['L0']} | {totals['validation']['L1']} | {totals['validation']['L2']} | {totals['validation']['L3']} | {totals['validation']['R1']} | {totals['validation']['R3']} | {totals['validation']['R4']} | 200 | PASS |
| development-test | {totals['development-test']['L0']} | {totals['development-test']['L1']} | {totals['development-test']['L2']} | {totals['development-test']['L3']} | {totals['development-test']['R1']} | {totals['development-test']['R3']} | {totals['development-test']['R4']} | 200 | PASS |

## 物理与执行事实

- 368/368条D1轨迹完成，最大连接力`{max_force:.2f} N`，15 kN ultimate超限步数为`{ultimate_steps}`。
- 最大共同ICR残差`{max_icr:.3e} m/s`；轮胎模型保持原饱和合同。
- 初次扫描的`KeyError('tire')`已作为实现错误归档并整批重跑；T0的K5-bilinear精度常数错误也已归档。两次修复均未改模型、数据seed、协议或门槛。
- 方向平衡只读审计见`direction_balance.json`；即使方向门通过，也不能抵消train L3失败。

## 文件

- `t1/force_coverage_scan.csv/png`：96配置可行性证据；
- `d1/manifest.json`：368条轨迹hash、参数和逐轨迹覆盖；
- `coverage_counts.csv`、`d1_coverage.png`：完整G1计数；
- `direction_balance.json`：方向符号平衡；
- `solutions.md`：可执行解决方案与论文边界；
- `stage_status.json`：T0–T9最终状态。
"""
    (OUT / "final_report.md").write_text(report, encoding="utf-8")
    write_json(OUT / "stop_manifest.json", {"status": "stopped_at_G1", "protocol_sha256": sha256(PROTOCOL), "pipeline_sha256": sha256(Path(__file__).resolve()), "d1_manifest_sha256": sha256(OUT/"d1"/"manifest.json"), "coverage_csv_sha256": sha256(OUT/"coverage_counts.csv"), "coverage_png_sha256": sha256(OUT/"d1_coverage.png"), "direction_balance_sha256": sha256(OUT/"direction_balance.json"), "solutions_sha256": sha256(OUT/"solutions.md"), "final_report_sha256": sha256(OUT/"final_report.md")})
    append_log("W0056", "普适性实验G1停止报告固化", [f"纠正早期solutions沿用“扫描无L3”模板的错误；真实结论为扫描通过但D1 train L3={totals['train']['L3']}/1000。", f"方向平衡只读审计={direction_pass}；D1最大力={max_force:.2f} N，最大ICR残差={max_icr:.3e} m/s，ultimate步数={ultimate_steps}。", f"最终报告hash={sha256(OUT/'final_report.md')}；solutions hash={sha256(OUT/'solutions.md')}；停止manifest hash={sha256(OUT/'stop_manifest.json')}。", "未改协议、seed、D1文件或门槛；未训练F/H/RLS/T/C/A，未生成D2，未启动闭环。"])


def simulate_scan(config: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    params = base.ModelParams()
    state = base.initialize_state(params, speed_mps=float(config["speed"]))
    vehicles, _ = base.split_state(state)
    vehicles[:, 3] += rng.normal(0.0, 0.015, size=4)
    vehicles[:, 4] += rng.normal(0.0, 0.004, size=4)
    state[:24] = vehicles.reshape(-1)
    alloc_cfg = base.AllocationConfig(max_steering_deg=15.0)
    force_rows, force_body_rows, penetration_rows = [], [], []
    max_icr = max_raw_tire = max_force = 0.0
    saturated_steps = 0
    ultimate = False
    finite = True
    error = ""
    steps = int(round(16.0 / DT))
    pattern = MODES[str(config["mode"])]
    amplitude = 0.0 if config["mode"] == "none" else 1.2
    try:
        for k in range(steps):
            t = k * DT
            signal = excitation_signal(t, str(config["profile"]))
            _, payload = base.split_state(state)
            speed = float(np.linalg.norm(payload[3:5]))
            accel = base.target_speed_accel(speed, float(config["speed"]))
            front = float(config["front_deg"]) * signal
            rear = float(config["rear_ratio"]) * front
            controls, allocation = base.allocate_controls(state, accel, front, rear, params, alloc_cfg)
            controls[:, 0] = np.clip(controls[:, 0] + amplitude * signal * pattern, -1.4, 1.2)
            controls[:, 1] = np.clip(controls[:, 1], -math.radians(15.0), math.radians(15.0))
            _, aux = system_derivative(state, controls, params)
            conn = aux["connectors"]
            fn = np.asarray(conn["force_norm_n"], dtype=float)
            fb = np.asarray(conn["force_payload_body_n"], dtype=float)
            pen = np.asarray(conn["penetration_m"], dtype=float)
            raw_tire = max(float(row["raw_utilization"]) for row in aux["tire"])
            max_raw_tire = max(max_raw_tire, raw_tire)
            saturated_steps += int(raw_tire > 1.0 + 1e-12)
            max_force = max(max_force, float(np.max(fn)))
            max_icr = max(max_icr, float(np.max(np.abs(allocation["normal_velocity_residual_mps"]))))
            force_rows.append(fn); force_body_rows.append(fb); penetration_rows.append(pen)
            if np.any(fn >= params.connector.ultimate_force_n):
                ultimate = True
                break
            for _ in range(SUBSTEPS):
                state = base.rk4_step(state, controls, PLANT_DT, params)
            if not np.all(np.isfinite(state)):
                finite = False
                break
    except Exception as exc:
        finite = False; error = repr(exc)
    force_arr = np.asarray(force_rows, dtype=float)
    body_arr = np.asarray(force_body_rows, dtype=float)
    pen_arr = np.asarray(penetration_rows, dtype=float)
    accepted = bool(finite and not ultimate and max_icr <= 1e-8 and len(force_arr) == steps)
    counts = classify_windows(force_arr, body_arr, pen_arr, params.connector.rated_force_n) if accepted else {key: 0 for key in ("L0", "L1", "L2", "L3", "L4-high", "R0", "R1", "R2", "R3", "R4", "R5")}
    return {
        **config, "seed": seed, "accepted": accepted, "finite": finite, "ultimate_exceeded": ultimate, "error": error,
        "completed_steps": len(force_arr), "max_connector_force_n": max_force, "max_force_ratio": max_force / params.connector.rated_force_n,
        "max_icr_residual_mps": max_icr, "max_raw_tire_utilization": max_raw_tire, "tire_saturation_fraction": saturated_steps / max(len(force_arr), 1),
        **{f"windows_{key}": value for key, value in counts.items()},
    }


def scan_configs() -> list[dict[str, Any]]:
    configs = []
    for config_id, values in enumerate(itertools.product((1.0, 2.5, 4.0), (10.0, 15.0), (-.5, -1.0), tuple(MODES), ("hold", "reversal"))):
        speed, front, rear, mode, profile = values
        configs.append({"config_id": config_id, "speed": speed, "front_deg": front, "rear_ratio": rear, "mode": mode, "profile": profile})
    assert len(configs) == 96
    return configs


def write_scan_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def plot_scan(rows: list[dict[str, Any]], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: row["max_connector_force_n"])
    x = np.arange(len(ordered)); y = np.array([row["max_connector_force_n"] / 1000.0 for row in ordered])
    colors = ["#2f6f9f" if row["accepted"] else "#b33b3b" for row in ordered]
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), constrained_layout=True)
    axes[0].bar(x, y, color=colors, width=.9)
    for level, label, color in ((6.0, "50% rated / L3 lower", "#d48600"), (9.6, "80% rated", "#7a3b9a"), (15.0, "ultimate", "#b33b3b")):
        axes[0].axhline(level, ls="--", color=color, label=label)
    axes[0].set_ylabel("Peak connector force (kN)"); axes[0].set_xlabel("96 preregistered configurations, sorted")
    axes[0].legend(ncol=3); axes[0].grid(axis="y", alpha=.25)
    axes[1].scatter([row["max_raw_tire_utilization"] for row in rows], [row["max_force_ratio"] for row in rows], c=[row["windows_L3"] for row in rows], cmap="viridis", s=35)
    axes[1].axhspan(.5, .8, color="#d48600", alpha=.12, label="required L3")
    axes[1].set_xlabel("Peak raw tire utilization"); axes[1].set_ylabel("Peak force / rated force")
    axes[1].grid(alpha=.25); axes[1].legend()
    fig.suptitle("G1 safe force-coverage feasibility scan")
    fig.savefig(path, dpi=180); plt.close(fig)


def write_solutions(summary: dict[str, Any]) -> None:
    peak = summary["peak_configuration"]
    text = f"""# 普适性实验G1停止与解决方案

## 已核实事实

- 预注册96配置受约束扫描已经全部运行，合法配置`{summary['accepted_configurations']}/96`。
- 合法配置峰值连接力为`{summary['max_accepted_force_n']:.2f} N`，即额定12 kN的`{100*summary['max_accepted_force_ratio']:.2f}%`。
- L3（50–80%额定力）互不重叠20步窗总数为`{summary['total_L3_windows']}`；进入L3的配置数为`{summary['configs_with_L3']}`。
- 峰值配置：速度`{peak['speed']} m/s`、前轮`{peak['front_deg']}°`、后/前比`{peak['rear_ratio']}`、差动`{peak['mode']}`、时序`{peak['profile']}`、seed `{peak['seed']}`。
- 扫描保持每车加速度`[-1.4,1.2] m/s²`、转角`±15°`、共同ICR分配、轮胎饱和和15 kN ultimate合同。没有通过增大刚度、降低额定力、删除失败轨迹或输出裁剪制造覆盖。

## 停止原因

G1要求train至少1000个L3窗、validation和development-test各至少200个L3窗；本次可行性扫描没有形成可复现L3入口，因此直接生成368条D1轨迹不能合理预期满足覆盖门。按冻结协议，T2–T9均记为`not_applicable_upstream_G1_failed`。这不证明所有控制序列在数学上都不可能进入L3，只证明当前已验收控制/plant合同和预注册扫描没有提供所需证据。

## 最可能原因与替代解释

1. 纵向控制幅值由`[-1.4,1.2] m/s²`限制，四车差动能建立的稳态连接力远低于6 kN。
2. 共同ICR分配和轮胎饱和限制弯道中的相对运动；高转角增加轮胎饱和，不必然增加连接器差动力。
3. 当前连接器是30 kN/m、2 mm free-play的单向拉伸/阻尼模型；历史最大载荷本来就只有约1.155 kN。
4. 可能存在未被96配置网格覆盖的瞬态最优控制序列，但在没有优化器和独立安全约束证明前，不能假设它存在并据此训练。

## 可验证方案、成本和风险

1. 单独建立“受约束最优激励设计”任务：以L3窗数为目标，显式约束ultimate、轮胎、速度、横摆、车辆/货物位置和控制变化率；先做小规模direct-collocation或CMA-ES。成本约1–3 GPU/CPU天，风险是得到高度非自然、论文不可解释的控制序列。
2. 若论文目标是正常操纵域普适性，将载荷覆盖合同改为基于当前运行分布的分位档，而不是额定力百分比；这会改变研究问题，必须新建协议和新盲确认，不能回改本轮G1。
3. 若确实要研究高载荷，应先核实连接器额定力、刚度、阻尼和车辆执行器是否来自实物/设计数据。改变这些plant参数会形成新物理系统，需要重新验收四车动力学、共同ICR和安全合同。
4. 增加车辆侧独立连接力日志/传感合同，再验证作用—反作用和单车受力；当前payload-side 18D输出仍不足以独立识别该残差。

## 当前论文结论边界

在补齐合法L3覆盖前，不能执行或声称F物理头的“50–80%额定载荷普适性”，也不能把后续H/T/C/A的缺失解释为方法失败。可继续保留上一轮K0/K1在普通接触载荷域的结论。
"""
    (OUT / "solutions.md").write_text(text, encoding="utf-8")


def run_t1() -> bool:
    if not run_t0():
        write_json(OUT / "t1" / "complete.json", {"stage": "T1", "status": "not_applicable_upstream_G0_failed"})
        return False
    stage = OUT / "t1"
    complete = stage / "complete.json"
    if complete.exists():
        data = json.loads(complete.read_text(encoding="utf-8"))
        scan_path = stage / "force_coverage_scan.csv"
        invalid_keyerror = False
        if scan_path.exists():
            with scan_path.open("r", encoding="utf-8-sig", newline="") as handle:
                old_rows = list(csv.DictReader(handle))
            invalid_keyerror = bool(old_rows) and all(row.get("error") == "KeyError('tire')" and int(row.get("completed_steps", 0)) == 0 for row in old_rows)
        if invalid_keyerror:
            archive = OUT / "t1_invalid_keyerror"
            if archive.exists():
                raise RuntimeError(f"cannot preserve invalid T1 because archive already exists: {archive}")
            stage.replace(archive)
            for name in ("solutions.md", "stage_status.json"):
                source = OUT / name
                if source.exists():
                    source.replace(OUT / (source.stem + "_invalid_keyerror" + source.suffix))
            print("Archived invalid KeyError('tire') T1 and restarting all 96 configurations", flush=True)
        elif data.get("accepted") and data.get("status") == "feasibility_pass_D1_generation_required":
            print("T1 feasibility already passed; continuing with frozen D1 generation", flush=True)
            return complete_d1()
        else:
            print(f"T1 already complete: {data.get('status')}", flush=True)
            if data.get("status") == "failed_full_D1_coverage": finalize_g1_stop()
            return bool(data.get("accepted"))
    stage.mkdir(parents=True, exist_ok=True)
    rows = []
    for config in scan_configs():
        result = simulate_scan(config, 900000 + int(config["config_id"]))
        rows.append(result)
        print(f"[{len(rows):02d}/96] cfg={config['config_id']:02d} force={result['max_connector_force_n']:.1f}N L3={result['windows_L3']} ok={result['accepted']}", flush=True)
    write_scan_csv(stage / "force_coverage_scan.csv", rows)
    plot_scan(rows, stage / "force_coverage_scan.png")
    accepted_rows = [row for row in rows if row["accepted"]]
    peak = max(accepted_rows, key=lambda row: row["max_connector_force_n"]) if accepted_rows else max(rows, key=lambda row: row["max_connector_force_n"])
    l3_rows = [row for row in accepted_rows if row["windows_L3"] > 0]
    repetitions: list[dict[str, Any]] = []
    repeat_pass = False
    if l3_rows:
        for rank, candidate in enumerate(sorted(l3_rows, key=lambda row: row["windows_L3"], reverse=True)[:5]):
            config = {key: candidate[key] for key in ("config_id", "speed", "front_deg", "rear_ratio", "mode", "profile")}
            for rep in range(5):
                item = simulate_scan(config, 901000 + 10 * rank + rep); item["repeat_rank"] = rank; item["repeat"] = rep
                repetitions.append(item)
                print(f"repeat rank={rank} rep={rep} force={item['max_connector_force_n']:.1f}N L3={item['windows_L3']} ok={item['accepted']}", flush=True)
        write_scan_csv(stage / "force_coverage_repeats.csv", repetitions)
        for rank in range(min(5, len(l3_rows))):
            group = [row for row in repetitions if row["repeat_rank"] == rank]
            if sum(row["accepted"] and row["windows_L3"] > 0 for row in group) >= 4:
                repeat_pass = True
    summary = {
        "stage": "T1_G1_feasibility", "protocol_sha256": sha256(PROTOCOL), "planned_configurations": 96,
        "accepted_configurations": len(accepted_rows), "failed_configurations": 96 - len(accepted_rows),
        "max_accepted_force_n": float(peak["max_connector_force_n"]), "max_accepted_force_ratio": float(peak["max_force_ratio"]),
        "peak_configuration": peak, "configs_with_L3": len(l3_rows), "total_L3_windows": int(sum(row["windows_L3"] for row in accepted_rows)),
        "repeat_required": bool(l3_rows), "repeat_pass": repeat_pass,
        "G1_feasibility_pass": repeat_pass,
    }
    write_json(stage / "coverage_summary.json", summary)
    if not repeat_pass:
        status = "failed_no_L3_in_coarse_scan" if not l3_rows else "failed_L3_not_reproducible_4_of_5"
        write_json(complete, {"stage": "T1", "accepted": False, "status": status, "summary_sha256": sha256(stage / "coverage_summary.json"), "downstream": {f"T{i}": "not_applicable_upstream_G1_failed" for i in range(2, 10)}})
        write_solutions(summary)
        write_json(OUT / "stage_status.json", {"T0": "passed", "T1": status, **{f"T{i}": "not_applicable_upstream_G1_failed" for i in range(2, 10)}})
        append_log("W0054R" if (OUT / "t1_invalid_keyerror").exists() else "W0054", "普适性实验T1强受力覆盖门", [
            f"预注册96配置全部运行；合法配置={len(accepted_rows)}/96，失败配置={96-len(accepted_rows)}。",
            f"合法峰值连接力={peak['max_connector_force_n']:.2f} N（额定力{100*peak['max_force_ratio']:.2f}%）；L3配置={len(l3_rows)}，L3互不重叠20步窗={summary['total_L3_windows']}。",
            f"G1=FAIL（{status}）；按冻结协议T2–T9均不适用，未训练F/H/T/C/A、未生成D1/D2、未启动闭环。",
            "首次96配置因读取不存在的`tire`键而在step 0统一失败；已归档`t1_invalid_keyerror`，改为从同一plant的`system_derivative`读取原始轮胎利用率并整批重跑。模型、协议、控制和安全门未改。" if (OUT / "t1_invalid_keyerror").exists() else "无实现重试。",
            f"扫描CSV hash={sha256(stage/'force_coverage_scan.csv')}；图片hash={sha256(stage/'force_coverage_scan.png')}；solutions hash={sha256(OUT/'solutions.md')}。",
        ])
        print(f"T1/G1 FAIL: {status}", flush=True)
        return False
    write_json(complete, {"stage": "T1", "accepted": True, "status": "feasibility_pass_D1_generation_required", "summary_sha256": sha256(stage / "coverage_summary.json")})
    append_log("W0054", "普适性实验T1强受力可行性扫描", [f"96配置和五seed重复通过；允许继续生成D1。峰值={peak['max_connector_force_n']:.2f} N。"])
    print("T1 feasibility PASS; continue with full D1 generation", flush=True)
    return complete_d1()


def upstream_not_applicable(stage_name: str) -> None:
    t1 = OUT / "t1" / "complete.json"
    if t1.exists() and not json.loads(t1.read_text(encoding="utf-8")).get("accepted"):
        print(f"{stage_name.upper()} not applicable: G1 failed", flush=True)
        return
    raise RuntimeError(f"{stage_name} implementation is gated behind successful G1 and has not been reached")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "all"), required=True)
    args = parser.parse_args()
    if args.stage == "t0": run_t0(); return
    if args.stage == "t1": run_t1(); return
    if args.stage == "all":
        if not run_t0(): return
        if not run_t1(): return
        for index in range(2, 10): upstream_not_applicable(f"t{index}")
        return
    upstream_not_applicable(args.stage)


if __name__ == "__main__":
    main()
