"""Full-route (R4) runner with a selectable CPU or CUDA linearisation backend.

Independent module: it does not modify any file pinned by the G3 protocol.  The
closed-loop tick semantics are taken verbatim from
``gpu_closed_loop_runner.execute`` so that the two cannot drift apart; only the
start condition, the tick count and the protocol identity differ.

Starting point is the frozen initial condition (``initialize_state(model, SPEED)``
with zero steering, zero previous control, zero reference distance and zero beta),
which is exactly where ``post_r3_r4_runner.execute`` starts, so a CPU run of this
module is directly comparable with the historical 2 ms reference.

Known limitation, declared rather than hidden: ``execute`` does not maintain the
per-tick configuration error, so after the run this module replaces that one
metric with ``null`` plus an explicit note; the comparator computes the true value
from the persisted state, reference distance and beta columns.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import numpy as np

from ..cli import save, sha
from ..e01_100m import DT, params
from ..pilot_runner import ROUTE_LENGTH, SPEED
from .gpu_closed_loop_runner import expanded_parameters, execute

SCHEMA = "R4-FULL-ROUTE-v1"
SCOPE = "R4_FULL_ROUTE"

REQUIRED_G3_VERDICTS = (
    "cpu_run_completed",
    "gpu_run_completed",
    "gpu_position_within_tolerance",
    "gpu_heading_within_tolerance",
    "gpu_force_peak_within_tolerance",
    "original_hard_gates_hold",
)
NOT_REQUIRED_G3_VERDICTS = ("restart_position_within_tolerance", "restart_heading_within_tolerance")


def validate_protocol(path: Path, expected_sha: str, paper: Path, parameter: str, backend: str) -> dict:
    if sha(path) != expected_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != SCHEMA:
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    if protocol.get("scope") != SCOPE:
        raise ValueError("PROTOCOL_SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        source = paper / item["path"]
        if not source.is_file() or sha(source) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    # Parent gates are enforced in code, not only asserted in prose.  The G3 report
    # deliberately keeps its restart_* verdicts FAILED, so the overall G3 status is
    # not PASS; what this runner requires is the set of verdicts the full route
    # actually depends on, and it re-checks both the required and the recorded-failed
    # sets against the live report so the protocol cannot quietly hide a change.
    g3 = paper / protocol["parent_g3"]["path"]
    g3_data = json.loads(g3.read_text(encoding="utf-8"))
    if sha(g3) != protocol["parent_g3"]["sha256"]:
        raise ValueError("PARENT_G3_IDENTITY_MISMATCH")
    live_required = {
        f"{window['window']}.{verdict}": bool(window["verdicts"].get(verdict))
        for window in g3_data["windows"]
        for verdict in REQUIRED_G3_VERDICTS
    }
    live_failed = {
        f"{window['window']}.{verdict}": bool(window["verdicts"].get(verdict))
        for window in g3_data["windows"]
        for verdict in NOT_REQUIRED_G3_VERDICTS
    }
    if live_required != protocol["parent_g3"]["required_verdicts"] or not all(live_required.values()):
        raise ValueError("PARENT_G3_REQUIRED_VERDICTS_NOT_MET")
    if live_failed != protocol["parent_g3"]["not_required_verdicts"]:
        raise ValueError("PARENT_G3_VERDICT_RECORD_MISMATCH")
    mechanism = paper / protocol["parent_g3b_mechanism"]["path"]
    mechanism_data = json.loads(mechanism.read_text(encoding="utf-8"))
    if sha(mechanism) != protocol["parent_g3b_mechanism"]["sha256"] or mechanism_data.get("status") != "PASS_READ_ONLY_MECHANISM_ANALYSIS":
        raise ValueError("PARENT_G3B_MECHANISM_NOT_PASS")
    qualification = paper / protocol["parent_qualification"]["path"]
    qualification_data = json.loads(qualification.read_text(encoding="utf-8"))
    if sha(qualification) != protocol["parent_qualification"]["sha256"] or qualification_data.get("status") != "PASS_G0_G2_GPU_QUALIFIED":
        raise ValueError("PARENT_QUALIFICATION_NOT_PASS")
    run = protocol["run"]
    if run["parameter_id"] != parameter or run["backend"] != backend:
        raise ValueError("RUN_IDENTITY_MISMATCH")
    if backend not in ("cpu", "gpu") or parameter not in ("P0", "P1", "P2"):
        raise ValueError("UNREGISTERED_RUN_CELL")
    model = params(parameter)
    if expanded_parameters(model) != protocol["absolute_parameters"]:
        raise ValueError("ABSOLUTE_PARAMETER_IDENTITY_MISMATCH")
    return protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--deadline-unix", type=float, required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[3]
    protocol_path = Path(args.protocol).resolve()
    declared = json.loads(protocol_path.read_text(encoding="utf-8"))["run"]["parameter_id"]
    protocol = validate_protocol(protocol_path, args.protocol_sha, paper, declared, args.backend)
    run = protocol["run"]
    parameter = run["parameter_id"]
    out = (paper / run["output"]).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    model = params(parameter)
    from ..plant.four_vehicle_common import initialize_state

    count = int(np.ceil((ROUTE_LENGTH / SPEED) / DT))
    if count != int(run["total_ticks"]):
        raise ValueError("TICK_COUNT_MISMATCH")
    out.mkdir(parents=True)
    checkpoint_state = {
        "state": initialize_state(model, SPEED),
        "delta": np.zeros(4),
        "previous_u": np.zeros(8),
        "distance": 0.0,
        "beta": np.zeros(4),
        "source_row": None,
        "source_time_s": 0.0,
        "replay_closure": None,
    }
    save(out, "checkpoint_source.json", {
        "start": "frozen_initial_condition",
        "note": "identical to post_r3_r4_runner.execute: initialize_state(model, SPEED) with zero steering, zero previous control, zero distance and zero beta",
        "total_ticks": count,
        "backend": args.backend,
        "state": checkpoint_state["state"].tolist(),
    })
    window = {"name": "full_route", "start_tick": 0, "ticks": count, "plant_max_step_ms": float(run["plant_max_step_ms"]), "source_run": None}
    max_step_s = float(run["plant_max_step_ms"]) / 1000.0

    if args.backend == "cpu":
        from ..controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization

        workers = int(run["workers"])
        with ParallelFiniteDifferenceBackend(workers) as backend:
            warmup = backend.warm(np.r_[checkpoint_state["state"], checkpoint_state["delta"]], np.zeros(8), model)
            save(out, "pool.json", {"workers": workers, "warmup_s": warmup})
            with install_parallel_linearization(backend):
                execute(out, model, parameter, "cpu", window, checkpoint_state, max_step_s, args.deadline_unix, args.protocol_sha.lower())
    else:
        from ..gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization

        with CudaIpcFiniteDifferenceBackend(model) as backend:
            environment = backend.environment()
            warmup = backend.warm(np.r_[checkpoint_state["state"], checkpoint_state["delta"]], np.zeros(8))
            save(out, "pool.json", {
                "backend": "cuda", "device": environment.get("device_name"),
                "warmup_s": warmup, "worker_module_audit": environment.get("worker_module_audit"),
            })
            with install_cuda_linearization(backend):
                execute(out, model, parameter, "gpu", window, checkpoint_state, max_step_s, args.deadline_unix, args.protocol_sha.lower())

    # Declare the one metric this implementation does not maintain, instead of
    # leaving a zero that could be misread as a measured value.
    metrics_path = out / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["maximum_configuration_error_m"] = None
    metrics["maximum_configuration_error_note"] = "not maintained by the windowed runner; compute from raw state/reference_distance_m/reference_beta* with tools/full_route_compare.py"
    save(out, "metrics.json", metrics)
    status_path = out / "status.json"
    if status_path.is_file():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["maximum_configuration_error_m"] = None
        status["maximum_configuration_error_note"] = metrics["maximum_configuration_error_note"]
        save(out, "status.json", status)
    print(json.dumps({"out": str(out), "status": metrics["status"], "ticks": metrics["iterations"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
