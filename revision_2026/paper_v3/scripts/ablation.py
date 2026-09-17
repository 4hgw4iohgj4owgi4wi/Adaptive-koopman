"""Executable ABL-R1 runner.

The runner is intentionally self-contained: it expands the registered cases,
generates one immutable network trace per case, replays that trace for every
method, and keeps failed trials in the long table.  It never writes to the
historical model or Koopman result trees.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

import numpy as np

V3 = Path(__file__).resolve().parents[1]
if str(V3) not in sys.path:
    sys.path.insert(0, str(V3))

from src import PROTOCOL_VERSION
from src import plant
from src.cases import Case, expand_cases
from src.controllers import AgentController, variants
from src.identity import sha256, snapshot, tree_identity, write_json
from src.network import Replay, generate_trace, trace_sha256
from src.reference import build_reference, event_ticks, write_reference
from src.statistics import write_statistics


EXTERNAL = ("TUBE", "AOF", "NET", "AKE")


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def csv_write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def validate(project: Path, protocol: Path, config_path: Path, batch: str) -> int:
    config = load_config(config_path)
    errors: list[str] = []
    required = ("protocol_id", "dt_s", "substep_dt_s", "horizon", "scenarios", "profiles", "methods", "seed_roots", "families", "network", "gates", "batches")
    errors.extend([f"missing:{key}" for key in required if key not in config])
    if set(("P0", "P1", "K0", "K0N", "K1", "K1N")) - set(config.get("methods", {})):
        errors.append("six-cell method registry incomplete")
    if int(config.get("families", 0)) != 30:
        errors.append("formal family count is not 30")
    if float(config.get("substep_dt_s", 0.0)) != 0.002:
        errors.append("substep dt is not 2 ms")
    source_checks = {}
    for name, rel in config.get("source_paths", {}).items():
        p = project / rel if not Path(rel).is_absolute() else Path(rel)
        source_checks[name] = {"path": str(p), "exists": p.is_file(), "sha256": sha256(p) if p.is_file() else None}
        if not p.is_file(): errors.append(f"missing source:{name}:{p}")
    if "TODO" in config_path.read_text(encoding="utf-8") or "null" in config_path.read_text(encoding="utf-8").lower():
        errors.append("config contains TODO/null")
    # Contract tests: physical initialization, network determinism, and topology edge counts.
    try:
        params = plant.ModelParams(); state = plant.initialize(2.0, params)
        if state.shape != (30,) or not np.all(np.isfinite(state)): errors.append("AB01 plant init failed")
        from src.network import topology_edges
        if [len(topology_edges(i)) for i in range(3)] != [3, 8, 12]: errors.append("AB09 topology edge counts failed")
        trace_a = generate_trace("BURST10", 998877, 120, 20, 2)
        trace_b = generate_trace("BURST10", 998877, 120, 20, 2)
        if trace_sha256(trace_a) != trace_sha256(trace_b): errors.append("AB13 trace determinism failed")
    except Exception as exc:
        errors.append(f"contract exception:{type(exc).__name__}:{exc}")
    expected = {"ABL-DEV": 162, "ABL-CORE": 4860, "ABL-DELAY": 900, "ABL-COMMON": 360}.get(batch)
    if expected is not None:
        b = config["batches"][batch]
        actual = len(config["scenarios"]) * len(b["profiles"]) * int(b["families"]) * len(b["methods"])
        if actual != expected: errors.append(f"{batch} count mismatch:{actual}!={expected}")
    result = {"status": "PASS" if not errors else "FAIL", "batch": batch, "protocol": str(protocol),
              "protocol_sha256": sha256(protocol), "config_sha256": sha256(config_path),
              "sources": source_checks, "errors": errors, "host": snapshot(project, config)}
    write_json(V3 / "last_validate.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 22


def _make_case_root(run_dir: Path, config: dict, profiles: list[str], families: int, ticks: int) -> tuple[list[Case], Path]:
    case_root = run_dir / "case_plan"
    case_root.mkdir(parents=True, exist_ok=True)
    cases = expand_cases(config, case_root, profiles, families, ticks)
    trace_root = run_dir / "network_trace"
    trace_root.mkdir(parents=True, exist_ok=True)
    reference_rows: list[dict] = []
    event_rows: list[dict] = []
    for case in cases:
        reference = build_reference(case.scenario, case.ticks, float(config["dt_s"]))
        reference_rows.extend({"scenario": case.scenario, **row} for row in reference)
        ev = generate_trace(case.profile, case.network_seed, case.ticks, case.k_s, case.topology_slot)
        event_rows.extend({"scenario": case.scenario, "case_id": case.case_id, **asdict(e)} for e in ev)
        arr = np.asarray([[e.sender, e.receiver, e.sent_tick, e.arrival_tick, int(e.dropped), e.transport_delay] for e in ev], dtype=np.int32)
        np.savez_compressed(trace_root / f"{case.case_id}.npz", events=arr, trace_sha256=case.trace_sha256)
    csv_write(case_root / "reference.csv", reference_rows)
    csv_write(case_root / "events.csv", event_rows)
    return cases, case_root


def _simulate(task: tuple[dict, str, dict, str]) -> tuple[dict, dict]:
    case_dict, method_name, config, raw_dir = task
    case = Case(**case_dict)
    started = time.perf_counter()
    params = plant.ModelParams()
    rng = np.random.default_rng(np.random.SeedSequence([case.physical_seed, 71]))
    state = plant.initialize(2.5, params)
    # Family-specific initial perturbation is shared by all methods for pairing.
    state[1:24:6] += rng.normal(0.0, 0.008, size=4)
    state[25] += float(rng.normal(0.0, 0.008))
    reference = build_reference(case.scenario, case.ticks, float(config["dt_s"]))
    events = generate_trace(case.profile, case.network_seed, case.ticks, case.k_s, case.topology_slot)
    replay = Replay(events, state)
    method = variants(config)[method_name]
    stepper = plant.direct_step if config.get("_integrator") == "direct_equivalent" else plant.step
    agents = [AgentController(method, i, float(config["dt_s"]), params) for i in range(4)]
    states = [state.copy()]; controls_log = []; force_log = []; q_log = []; ages_log = []; est_log = []; mode_log = []
    failures: list[str] = []
    for tick in range(case.ticks):
        replay.deliver(tick)
        ref = dict(reference[min(tick, len(reference) - 1)])
        controls = np.zeros((4, 2), dtype=float)
        diagnostics = []
        for agent in range(4):
            controls[agent], diag = agents[agent].command(state, replay.view(agent), ref)
            diagnostics.append(diag)
        try:
            state = stepper(state, controls, float(config["dt_s"]), params)
        except Exception as exc:
            failures.append(f"{type(exc).__name__}:{exc}")
            break
        if not np.all(np.isfinite(state)):
            failures.append("PHYSICS_NONFINITE"); break
        conn = plant.connector_diagnostics(state, params)
        f = np.asarray(conn["force_payload_world_n"], dtype=float)
        q_front = 0.5 * ((conn["force_payload_body_n"][0, 0] + conn["force_payload_body_n"][1, 0]) - (conn["force_payload_body_n"][2, 0] + conn["force_payload_body_n"][3, 0]))
        q_left = 0.5 * ((conn["force_payload_body_n"][0, 1] + conn["force_payload_body_n"][2, 1]) - (conn["force_payload_body_n"][1, 1] + conn["force_payload_body_n"][3, 1]))
        states.append(state.copy()); controls_log.append(controls.copy()); force_log.append(f.copy())
        q_log.append([q_front, q_left]); ages_log.append(max(d["age_max_ticks"] for d in diagnostics)); est_log.append(np.mean([d["estimate_rmse"] for d in diagnostics])); mode_log.append("|".join(sorted(set(d["mode"] for d in diagnostics))))
        replay.send(tick, state)
    states_a = np.asarray(states); controls_a = np.asarray(controls_log); forces_a = np.asarray(force_log)
    refs = reference[:len(controls_a)]
    if len(refs):
        lateral = []
        for row, ref in zip(states_a[:-1], refs):
            payload = row[24:30]; tangent = np.array([np.cos(ref["yaw_rad"]), np.sin(ref["yaw_rad"])]); normal = np.array([-tangent[1], tangent[0]])
            lateral.append(float((payload[:2] - np.array([ref["x_m"], ref["y_m"]])) @ normal))
        lateral = np.asarray(lateral, dtype=float)
    else: lateral = np.zeros(1)
    final = states_a[-1, 24:30] if len(states_a) else np.full(6, np.nan)
    final_ref = reference[min(len(states_a) - 1, len(reference) - 1)]
    endpoint_error = float(np.linalg.norm(final[:2] - np.array([final_ref["x_m"], final_ref["y_m"]]))) if np.all(np.isfinite(final)) else float("inf")
    completed = bool(np.all(np.isfinite(states_a)) and endpoint_error <= 0.5 and abs(float(final[2]) - float(final_ref["yaw_rad"])) <= np.deg2rad(5.0))
    mode_counts = {m: mode_log.count(m) for m in sorted(set(mode_log))}
    row = {"case_id": case.case_id, "scenario": case.scenario, "profile": case.profile, "family": case.family,
           "topology_slot": case.topology_slot, "method": method_name, "method_label": config["methods"].get(method_name, {}).get("label", method_name),
           "predictor": method.model, "protection": method.protection, "align_stale_mean": method.align, "bound_mode": method.bound_mode,
           "completed": completed, "failure_type": "" if completed else (";".join(failures) if failures else "PATH_INCOMPLETE"),
           "ticks": int(len(controls_a)), "endpoint_error_m": endpoint_error,
           "lateral_rmse_m": float(np.sqrt(np.mean(lateral**2))) if len(lateral) else float("nan"),
           "lateral_p95_m": float(np.percentile(np.abs(lateral), 95)) if len(lateral) else float("nan"),
           "connector_peak_n": float(np.max(np.linalg.norm(forces_a, axis=2))) if forces_a.size else float("nan"),
           "connector_p99_n": float(np.percentile(np.linalg.norm(forces_a, axis=2), 99)) if forces_a.size else float("nan"),
           "q_peak_n": float(np.max(np.abs(q_log))) if q_log else float("nan"),
           "max_aoi_ticks": int(max(ages_log, default=0)), "mean_estimate_rmse": float(np.mean(est_log)) if est_log else float("nan"),
           "degraded_ticks": int(sum("DEGRADED" in m for m in mode_log)), "fallback_ticks": int(sum("FALLBACK" in m for m in mode_log)),
           "received_packets": int(replay.received), "trace_sha256": trace_sha256(events), "wall_time_s": time.perf_counter() - started,
           "solver_mode": "registered_local_physical_rollout_surrogate", "integrator_mode": config.get("_integrator", "substep_2ms"), "shadow_used_for_bound": bool(any(a.shadow_used for a in agents))}
    arrays = {"states": states_a, "controls": controls_a, "forces": forces_a, "q": np.asarray(q_log), "aoi": np.asarray(ages_log), "estimate_rmse": np.asarray(est_log), "mode": np.asarray(mode_log, dtype="U32")}
    return row, arrays


def _worker(task):
    return _simulate(task)


def _write_trial_raw(raw_dir: Path, row: dict, arrays: dict) -> None:
    target = raw_dir / row["case_id"]
    target.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target / f"{row['method']}.npz", **arrays)
    sub = raw_dir.parent / "raw_substeps" / row["case_id"]
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"{row['method']}.json").write_text(json.dumps({"integrator": row.get("integrator_mode", "substep_2ms"), "raw_tick_file": str(target / f"{row['method']}.npz"), "available": True}, indent=2), encoding="utf-8")


def _write_run_artifacts(run_dir: Path, project: Path, config: dict, rows: list[dict], case_root: Path, batch: str, errors: list[str] | None = None) -> None:
    errors = errors or []
    write_json(run_dir / "identity.json", {"protocol": config["protocol_id"], "batch": batch, "host": snapshot(project, config), "sources": tree_identity([project / "ablation.md", V3 / "scripts" / "ablation.py", V3 / "src" / "plant.py"]), "predictor_source_read_only": str(project / config["source_paths"]["predictor_source"])})
    write_json(run_dir / "model_freeze.json", {"P0": "physical_snapshot", "S0": "read-only historical Koopman identity", "K0": "baseline_koopman adapter", "K1": "improved_koopman fixed_guard adapter", "new_training": False, "note": "This run does not refit or change Koopman models."})
    shutil.copy2(project / "ablation.md", run_dir / "protocol_snapshot.md")
    shutil.copy2(V3 / "config" / "ablation.json", run_dir / "config_snapshot.json")
    params = []
    for k, v in config["ages"].items(): params.append({"name": k, "value": v, "unit": "tick" if "tick" in k else "", "source": "ablation.md section 7", "selection": "pre-registered"})
    params.extend([{"name": "dt", "value": config["dt_s"], "unit": "s", "source": "ablation.md", "selection": "frozen"}, {"name": "prediction_horizon", "value": config["horizon"], "unit": "step", "source": "ablation.md", "selection": "frozen"}])
    csv_write(run_dir / "parameters.csv", params)
    csv_write(run_dir / "state_availability.csv", [{"field": "vehicle_state", "source": "local_virtual_sensor", "controller_access": "local_only"}, {"field": "remote_vehicle_state", "source": "delivered_packet", "controller_access": "packet_view_only"}, {"field": "plant_truth", "source": "offline_evaluator", "controller_access": "forbidden"}])
    csv_write(run_dir / "metrics.csv", rows)
    csv_write(run_dir / "runtime.csv", [{k: r.get(k) for k in ("case_id", "method", "wall_time_s", "solver_mode", "ticks")} for r in rows])
    csv_write(run_dir / "failures.csv", [r for r in rows if not r.get("completed")])
    stats = write_statistics(run_dir / "statistics.csv", rows, [("K1N", "P1", "connector_p99_n"), ("K1N", "K0N", "connector_p99_n"), ("K1N", "K1", "connector_p99_n"), ("K1N", "ND", "mean_estimate_rmse"), ("K1N", "ND", "lateral_rmse_m")]) if rows else []
    gate = {"engineering": "PASS" if not errors else "FAIL", "scientific": "PASS" if rows and any(r.get("completed") for r in rows) else "FAIL", "errors": errors, "trial_count": len(rows), "completed_count": int(sum(bool(r.get("completed")) for r in rows)), "statistics_count": len(stats), "external_baselines": "NOT_RUN"}
    write_json(run_dir / "gates.json", gate)
    csv_write(run_dir / "sources.csv", [{"slot": "plant", "source": str(project / config["source_paths"]["plant"]), "status": "frozen_snapshot"}, {"slot": "K0/K1", "source": str(project / config["source_paths"]["predictor_source"]), "status": "read_only_identity"}, {"slot": "TUBE/AOF/NET/AKE", "source": "not implemented in ABL-R1 execution", "status": "PENDING"}])
    (run_dir / "baseline_adaptation.md").write_text("# External baseline adaptation record\n\nTUBE, AOF, NET, and AKE were not executed in ABL-R1. Their source qualification, state/interface mapping, and independent adaptation are still open. No internal heuristic was substituted for an external baseline.\n", encoding="utf-8")
    csv_write(run_dir / "reviewer_matrix.csv", [{"claim": "Koopman vs physical model", "evidence": "K0/K1 vs P0/P1 paired metrics", "status": "OPEN"}, {"claim": "communication protection", "evidence": "P1/K0N/K1N vs M0 rows", "status": "RECORDED"}, {"claim": "delay compensation", "evidence": "K1N vs ND plus DC/NC", "status": "PENDING"}, {"claim": "external competition", "evidence": "TUBE/AOF/NET/AKE", "status": "OPEN"}])
    csv_write(run_dir / "figure_manifest.csv", [{"figure": f"fig_{i}", "status": "PENDING_RENDER", "source": "metrics.csv/raw_ticks"} for i in range(1, 7)])
    integrators = sorted({str(r.get("integrator_mode", "unknown")) for r in rows})
    report = [f"# ABL-R1 {batch} report", "", f"Protocol: `{config['protocol_id']}`", f"Trial count: {len(rows)}", f"Completed: {sum(bool(r.get('completed')) for r in rows)}", f"Integrator modes: {', '.join(integrators)}", "", "## Scientific status", "The runner preserved failed trials and did not convert failures to zero metrics.", "The six-cell factor is executed with a read-only physical plant snapshot and fixed network traces.", "K0/K1 are registered read-only predictor adapters; no new Koopman training was started.", "The current controller execution mode is recorded as `registered_local_physical_rollout_surrogate`; it must not be described as a real-time MPC result.", "", "## External baselines", "TUBE, AOF, NET and AKE were not silently replaced by heuristics; they remain PENDING/OPEN.", "", "## Limitations", "The present run is an offline functional experiment. It does not establish hardware safety, material-tear limits, deterministic stability, or 20 ms real-time performance."]
    if errors: report.extend(["", "## Errors", *[f"- {e}" for e in errors]])
    (run_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (run_dir / "solutions.md").write_text("# Open items\n\n- External strong baselines require source qualification and independent implementation.\n- A real multi-step SQP-MPC implementation remains a separate engineering gate; this run records the surrogate mode explicitly.\n", encoding="utf-8")
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "logs" / "work_log.md").write_text(f"# Work log\n\n- {datetime.now().isoformat()} host={config['host_role']} batch={batch} trials={len(rows)}\n- Protocol SHA: {sha256(project / 'ablation.md')}\n", encoding="utf-8")


def run_batch(project: Path, config_path: Path, batch: str, workers: int, max_trials: int | None = None) -> int:
    config = load_config(config_path)
    if batch == "ABL-READY":
        return smoke(project, config_path)
    if batch not in config["batches"]:
        print(f"unknown batch {batch}", file=sys.stderr); return 22
    spec = config["batches"][batch]
    config["_integrator"] = config["formal_integrator"] if batch in {"ABL-CORE", "ABL-DELAY", "ABL-COMMON"} else config["dev_integrator"]
    ticks = int(config["dev_ticks"] if batch == "ABL-DEV" else config["formal_ticks"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = project / "revision_2026" / "paper_v3_results" / f"{stamp}_{batch}"
    run_dir.mkdir(parents=True, exist_ok=False)
    cases, case_root = _make_case_root(run_dir, config, list(spec["profiles"]), int(spec["families"]), ticks)
    tasks = [(asdict(case), method, config, str(run_dir / "raw_ticks")) for case in cases for method in spec["methods"]]
    if max_trials is not None: tasks = tasks[:int(max_trials)]
    rows: list[dict] = []; errors: list[str] = []
    if workers < 1 or workers > 6: raise ValueError("workers must be 1..6")
    try:
        if workers == 1:
            result_stream = (_worker(task) for task in tasks)
            for row, arrays in result_stream:
                rows.append(row); _write_trial_raw(run_dir / "raw_ticks", row, arrays)
                if len(rows) % 5 == 0: atomic_json(run_dir / "progress.json", {"completed": len(rows), "total": len(tasks), "run_dir": str(run_dir)})
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for row, arrays in pool.map(_worker, tasks, chunksize=1):
                    rows.append(row); _write_trial_raw(run_dir / "raw_ticks", row, arrays)
                    if len(rows) % 5 == 0: atomic_json(run_dir / "progress.json", {"completed": len(rows), "total": len(tasks), "run_dir": str(run_dir)})
    except Exception as exc:
        errors.append(f"runner_exception:{type(exc).__name__}:{exc}")
        (run_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    _write_run_artifacts(run_dir, project, config, rows, case_root, batch, errors)
    atomic_json(run_dir / "progress.json", {"completed": len(rows), "total": len(tasks), "run_dir": str(run_dir), "status": "COMPLETE" if not errors else "FAILED"})
    print(json.dumps({"run_dir": str(run_dir), "trials": len(rows), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 24


def plan(project: Path, config_path: Path, batch: str) -> int:
    config = load_config(config_path)
    if batch == "ABL-READY":
        plan_dir = project / "revision_2026" / "paper_v3" / "plan_ready"; plan_dir.mkdir(parents=True, exist_ok=True)
        cases = []
        for scenario in config["scenarios"]:
            cases.append({"scenario": scenario, "profiles": config["profiles"], "families": 30})
        write_json(plan_dir / "plan.json", {"batch": batch, "cases": cases, "methods": list(config["methods"])})
        print(json.dumps({"plan": str(plan_dir / 'plan.json'), "status": "PASS"}, ensure_ascii=False)); return 0
    spec = config["batches"].get(batch)
    if not spec: return 22
    count = len(config["scenarios"]) * len(spec["profiles"]) * int(spec["families"]) * len(spec["methods"])
    print(json.dumps({"batch": batch, "count": count, "methods": spec["methods"], "profiles": spec["profiles"], "families": spec["families"]}, ensure_ascii=False)); return 0


def smoke(project: Path, config_path: Path) -> int:
    config = load_config(config_path)
    root = project / "revision_2026" / "paper_v3_results"
    root.mkdir(parents=True, exist_ok=True)
    # One common normal case per registered method; external slots stay explicit PENDING.
    run_dir = root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_ABL-READY_SMOKE"
    run_dir.mkdir(parents=True, exist_ok=False)
    cases, case_root = _make_case_root(run_dir, config, ["CLEAN"], 1, int(config["formal_ticks"]))
    names = list(config["methods"]) + list(EXTERNAL)
    tasks = [(asdict(cases[0]), n, config, str(run_dir / "raw_ticks")) for n in config["methods"]]
    rows = []; errors = []
    try:
        for task in tasks:
            row, arrays = _worker(task); rows.append(row); _write_trial_raw(run_dir / "raw_ticks", row, arrays)
        rows.extend({"case_id": cases[0].case_id, "scenario": cases[0].scenario, "profile": "CLEAN", "family": 0, "method": n, "completed": False, "failure_type": "SOURCE_OR_ADAPTATION_BLOCKED"} for n in EXTERNAL)
    except Exception as exc:
        errors.append(f"smoke_exception:{type(exc).__name__}:{exc}")
    _write_run_artifacts(run_dir, project, config, rows, case_root, "ABL-READY", errors)
    atomic_json(run_dir / "smoke_gate.json", {"status": "PASS" if not errors else "FAIL", "rows": len(rows), "methods": names, "external": "PENDING"})
    print(json.dumps({"run_dir": str(run_dir), "rows": len(rows), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 24


def status(project: Path) -> int:
    root = project / "revision_2026" / "paper_v3_results"
    rows = []
    for p in sorted(root.glob("*/gates.json")):
        try:
            value = json.loads(p.read_text(encoding="utf-8")); value["run_dir"] = str(p.parent); rows.append(value)
        except Exception as exc: rows.append({"run_dir": str(p.parent), "error": str(exc)})
    print(json.dumps(rows, indent=2, ensure_ascii=False)); return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "plan", "smoke", "run", "status"])
    parser.add_argument("--project", type=Path, default=V3.parents[1].parents[0])
    parser.add_argument("--protocol", type=Path, default=V3 / "config" / "ablation.json")
    parser.add_argument("--batch", default="ABL-READY")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-trials", type=int, default=None)
    args = parser.parse_args()
    project = args.project.resolve(); protocol = project / "ablation.md"; config_path = args.protocol.resolve()
    if args.command == "validate": code = validate(project, protocol, config_path, args.batch)
    elif args.command == "plan": code = plan(project, config_path, args.batch)
    elif args.command == "smoke": code = smoke(project, config_path)
    elif args.command == "run": code = run_batch(project, config_path, args.batch, args.workers, args.max_trials)
    else: code = status(project)
    raise SystemExit(code)


if __name__ == "__main__": main()
