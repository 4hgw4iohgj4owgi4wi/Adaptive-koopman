from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np


PLANT_DT = 0.002
FORBIDDEN = ("validation", "development", "confirm")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def params_from_meta(v1, meta: dict):
    p = meta["params"]
    return v1.ModelParams(
        vehicle=v1.VehicleParams(**p["vehicle"]),
        payload=v1.PayloadParams(**p["payload"]),
        connector=v1.ConnectorParams(**p["connector"]),
    )


def replay_one(args: tuple[str, str, str]) -> dict:
    project_s, file_s, partial_s = args
    project, path, partial = Path(project_s), Path(file_s), Path(partial_s)
    sys.path.insert(0, str(project / "revision_2026" / "model"))
    import four_vehicle_coupled as v1

    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["metadata_json"].item()))
    if meta.get("split") != "train" or any(x in str(path).lower() for x in FORBIDDEN):
        raise RuntimeError(f"forbidden non-train input: {path}")
    if bool(meta.get("is_augmented")) or bool(meta.get("local_mirror")):
        raise RuntimeError(f"base replay received mirror/augmentation: {path}")
    controls = np.asarray(z["control64"], dtype=float)
    state = np.asarray(z["initial_state64"], dtype=float).copy()
    p = params_from_meta(v1, meta)
    substeps = int(meta["substeps"])
    if abs(float(meta["plant_dt_s"]) - PLANT_DT) > 1e-12 or substeps != 10:
        raise RuntimeError(f"unexpected replay timing in {path}")

    prev = v1.connector_diagnostics(state, p)["penetration_m"]
    active_chunks: list[np.ndarray] = []
    event_delta: list[float] = []
    event_vn: list[float] = []
    event_conn: list[int] = []
    event_step: list[int] = []
    step = 0
    for u in controls:
        u = np.asarray(u, dtype=float).reshape(4, 2)
        for _ in range(substeps):
            state = v1.rk4_step(state, u, PLANT_DT, p)
            diag = v1.connector_diagnostics(state, p)
            pen = diag["penetration_m"]
            vn = diag["normal_speed_mps"]
            on = np.flatnonzero((prev <= 0.0) & (pen > 0.0) & np.isfinite(pen) & np.isfinite(vn) & (vn > 0.0))
            for j in on:
                event_delta.append(float(pen[j]))
                event_vn.append(float(vn[j]))
                event_conn.append(int(j))
                event_step.append(step)
            ap = pen[(pen > 0.0) & np.isfinite(pen)]
            if len(ap):
                active_chunks.append(ap.astype(np.float32))
            prev = pen
            step += 1

    active = np.concatenate(active_chunks) if active_chunks else np.empty(0, np.float32)
    # Reproduction audit against the saved float32 terminal checkpoint.
    saved_terminal = np.asarray(z["state30"][-1], dtype=float)
    terminal_scaled = float(np.max(np.abs(state - saved_terminal) / np.maximum(np.abs(saved_terminal), 1.0)))
    np.savez_compressed(
        partial,
        active_penetration=active,
        event_delta=np.asarray(event_delta, dtype=np.float64),
        event_vn=np.asarray(event_vn, dtype=np.float64),
        event_connector=np.asarray(event_conn, dtype=np.int8),
        event_step=np.asarray(event_step, dtype=np.int64),
    )
    return {
        "path": str(path),
        "partial": str(partial),
        "scenario": meta["scenario"],
        "trajectory_id": int(meta["trajectory_id"]),
        "connector_damping_nspm": float(p.connector.damping_nspm),
        "events": len(event_delta),
        "active_samples": int(len(active)),
        "terminal_scaled_error_vs_saved_float32": terminal_scaled,
    }


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    train = Path(sys.argv[2]).resolve()
    out = Path(sys.argv[3]).resolve()
    protocol = Path(sys.argv[4]).resolve()
    low = str(train).lower()
    if train.name.lower() != "train" or any(x in low for x in FORBIDDEN):
        raise SystemExit(f"R0 refuses non-train path: {train}")
    out.mkdir(parents=True, exist_ok=True)
    partial_dir = out / "partials"
    partial_dir.mkdir(exist_ok=True)
    files = sorted(train.glob("base_*.npz"))
    if len(files) != 256:
        raise SystemExit(f"expected 256 independent train bases, found {len(files)}")

    tasks = [(str(project), str(p), str(partial_dir / f"{p.stem}.npz")) for p in files]
    results = []
    workers = min(12, max(1, (os.cpu_count() or 4) - 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(replay_one, task): task[1] for task in tasks}
        for i, future in enumerate(as_completed(future_map), 1):
            result = future.result()
            results.append(result)
            if i % 16 == 0:
                print(f"R0 replay {i}/256", flush=True)

    results.sort(key=lambda x: x["trajectory_id"])
    active_all: list[np.ndarray] = []
    event_rows: list[dict] = []
    for result in results:
        z = np.load(result["partial"])
        active_all.append(z["active_penetration"])
        for delta, vn, connector, step in zip(z["event_delta"], z["event_vn"], z["event_connector"], z["event_step"]):
            event_rows.append({
                "delta_on_m": float(delta),
                "vn_on_mps": float(vn),
                "old_damping_force_n": float(result["connector_damping_nspm"] * vn),
                "scenario": result["scenario"],
                "trajectory_id": result["trajectory_id"],
                "connector_id": int(connector),
                "plant_step": int(step),
            })
    active = np.concatenate(active_all).astype(np.float64)
    event_delta = np.asarray([x["delta_on_m"] for x in event_rows], dtype=float)
    if not len(event_delta) or not len(active):
        raise SystemExit("no valid train-only contact-onset evidence")
    delta_s = float(np.quantile(event_delta, 0.99))
    active_q50 = float(np.quantile(active, 0.50))
    condition = bool(0.0 < delta_s < 0.25 * active_q50)

    with (out / "delta_s_events.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(event_rows[0]))
        writer.writeheader()
        writer.writerows(event_rows)

    source_manifest = project / "revision_2026" / "koopman" / "innovation_efd_r13_results" / "u4_data" / "manifest.json"
    train_hashes = {p.name: sha256(p) for p in files}
    manifest = {
        "input_path": str(train),
        "input_split": "train",
        "base_files": len(files),
        "analytic_mirrors_read": False,
        "workers": workers,
        "plant_dt_s": PLANT_DT,
        "source_manifest_path": str(source_manifest),
        "source_manifest_sha256": sha256(source_manifest),
        "protocol_sha256": sha256(protocol),
        "v1_plant_sha256": sha256(project / "revision_2026" / "model" / "four_vehicle_coupled.py"),
        "train_file_sha256": train_hashes,
        "development_read": False,
        "confirm_read": False,
    }
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    freeze = {
        "passed": condition,
        "freeze_rule": "Q0.99(delta_on | vn_on > 0), independent train bases only",
        "smoothing_width_m": delta_s,
        "event_count": len(event_rows),
        "event_delta_quantiles_m": {str(q): float(np.quantile(event_delta, q)) for q in (0, .5, .9, .95, .99, 1)},
        "active_penetration_samples": int(len(active)),
        "active_penetration_q50_m": active_q50,
        "upper_bound_0p25_q50_m": 0.25 * active_q50,
        "freeze_condition": "0 < delta_s < 0.25*Q0.50(active penetration)",
        "freeze_condition_passed": condition,
        "max_terminal_scaled_error_vs_saved_float32": max(x["terminal_scaled_error_vs_saved_float32"] for x in results),
        "script_sha256": sha256(Path(__file__)),
        "input_manifest_sha256": sha256(out / "input_manifest.json"),
        "development_read": False,
        "confirm_read": False,
    }
    (out / "delta_s_freeze.json").write_text(json.dumps(freeze, indent=2), encoding="utf-8")
    print(json.dumps(freeze, indent=2))
    raise SystemExit(0 if condition else 2)


if __name__ == "__main__":
    main()
