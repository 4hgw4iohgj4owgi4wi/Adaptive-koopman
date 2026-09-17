"""POST-R3 C0 migration, negative contracts, and fixed-QP regression."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expanded(model) -> dict:
    value = asdict(model)
    value["payload"]["yaw_inertia_kgm2"] = model.payload.yaw_inertia_kgm2
    value["payload_anchor_body_m"] = model.payload_anchor_body_m.tolist()
    return value


def validate_data(data: dict, paper: Path, *, output_exists: bool = False, active_run: bool = False) -> None:
    if data.get("schema_version") != "POST-R3-C0-v1":
        raise ValueError("SCHEMA_MISMATCH")
    if output_exists:
        raise ValueError("REFUSING_EXISTING_OUTPUT")
    if active_run:
        raise ValueError("ACTIVE_RUN_PRESENT")
    parent = paper / data["parent_r3"]["path"]
    parent_json = json.loads(parent.read_text(encoding="utf-8"))
    if sha(parent) != data["parent_r3"]["sha256"] or parent_json.get("status") != "PASS":
        raise ValueError("PARENT_R3_NOT_PASS")
    parent_figure = paper / data["parent_r3"]["figure_manifest"]
    figure_json = json.loads(parent_figure.read_text(encoding="utf-8"))
    if sha(parent_figure) != data["parent_r3"]["figure_manifest_sha256"] or figure_json.get("figure_status") != "PASS":
        raise ValueError("PARENT_FIGURE_NOT_PASS")
    if data.get("candidate_id") != "EXP-R3-unfrozen-v1":
        raise ValueError("CANDIDATE_MISMATCH")
    identity = data.get("candidate_identity", {})
    if identity.get("frozen_dynamics_jacobian") is not False or identity.get("finite_difference_scale") != 1.0 or identity.get("workers") != 8:
        raise ValueError("ALGORITHM_IDENTITY_MISMATCH")
    for item in data["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("SOURCE_IDENTITY_MISMATCH:" + item["path"])
    rows = data["run_manifest"]
    expected = [(parameter, step) for parameter in ("P1", "P2") for step in (2.0, 1.0, 0.5)]
    actual = [(row.get("parameter_id"), row.get("plant_max_step_ms")) for row in rows]
    if actual != expected or len({row.get("run_id") for row in rows}) != 6 or len({row.get("output") for row in rows}) != 6:
        raise ValueError("RUN_MANIFEST_MATRIX_MISMATCH")
    if any(row.get("candidate_id") != data["candidate_id"] or row.get("expected_figures") != data["expected_figures"] for row in rows):
        raise ValueError("RUN_MANIFEST_IDENTITY_MISMATCH")


def negative_tests(data: dict, paper: Path) -> dict:
    import copy

    cases = {}
    mutations = {
        "old_frozen_candidate": lambda value: value["candidate_identity"].update(frozen_dynamics_jacobian=True),
        "wrong_parent_r3": lambda value: value["parent_r3"].update(sha256="0" * 64),
        "missing_candidate_field": lambda value: value.pop("candidate_id"),
        "wrong_parameter": lambda value: value["run_manifest"][0].update(parameter_id="P0"),
        "wrong_step": lambda value: value["run_manifest"][0].update(plant_max_step_ms=3.0),
        "wrong_protocol_source_sha": lambda value: value["identity_files"][0].update(sha256="1" * 64),
        "missing_figure_gate": lambda value: value["parent_r3"].update(figure_manifest_sha256="2" * 64),
        "duplicate_output": lambda value: value["run_manifest"][1].update(output=value["run_manifest"][0]["output"]),
    }
    for name, mutate in mutations.items():
        value = copy.deepcopy(data)
        mutate(value)
        try:
            validate_data(value, paper)
        except Exception as error:
            cases[name] = {"rejected": True, "reason": f"{type(error).__name__}:{error}"}
        else:
            cases[name] = {"rejected": False, "reason": "NOT_REJECTED"}
    for name, kwargs in (("existing_output", {"output_exists": True}), ("active_run", {"active_run": True})):
        try:
            validate_data(copy.deepcopy(data), paper, **kwargs)
        except Exception as error:
            cases[name] = {"rejected": True, "reason": f"{type(error).__name__}:{error}"}
        else:
            cases[name] = {"rejected": False, "reason": "NOT_REJECTED"}
    return cases


def qp_regression(paper: Path) -> dict:
    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.controllers import physical_tracking_pilot as controller
    from paper_v4_core.controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
    from paper_v4_core.controllers.physical_tracking_pilot import PilotConfig
    from paper_v4_core.e01_100m import params
    from paper_v4_core.pilot_runner import SPEED, make_preview
    from paper_v4_core.plant.four_vehicle_common import connector_diagnostics, initialize_state

    result = {}
    config = PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False, finite_difference_scale=1.0)
    with ParallelFiniteDifferenceBackend(8) as backend:
        warm_state = initialize_state(params("P1"), SPEED)
        warm_u, _, _ = make_preview(0.0, np.zeros(4), params("P1"), np.zeros(8), 20)
        warmup = backend.warm(np.r_[warm_state, np.zeros(4)], warm_u[0], params("P1"))
        for parameter in ("P1", "P2"):
            model = params(parameter)
            parameter_rows = {}
            for checkpoint, offset in (("initial", 0.0), ("force_bearing", 0.03)):
                state = initialize_state(model, SPEED)
                state[0] += offset
                delta = np.zeros(4)
                u_nom, refs, _ = make_preview(0.0, np.zeros(4), model, np.zeros(8), 20)
                started = time.perf_counter()
                serial = controller.solve(np.r_[state, delta], u_nom, refs, model, config)
                serial_wall = time.perf_counter() - started
                started = time.perf_counter()
                with install_parallel_linearization(backend):
                    parallel = controller.solve(np.r_[state, delta], u_nom, refs, model, config)
                parallel_wall = time.perf_counter() - started
                matrices = {}
                for name in ("P", "q", "A", "l", "u", "u_nom"):
                    a = np.asarray(serial["problem"][name])
                    b = np.asarray(parallel["problem"][name])
                    matrices[name] = bool(np.array_equal(a, b, equal_nan=True))
                force = connector_diagnostics(state, model, "R3")["force_norm_n"]
                checks = {
                    "serial_pass": serial["status"] == "PASS" and serial["validation"]["status"] == "PASS",
                    "parallel_pass": parallel["status"] == "PASS" and parallel["validation"]["status"] == "PASS",
                    "all_qp_arrays_exact": all(matrices.values()),
                    "first_control_exact": bool(np.array_equal(serial["control"][0], parallel["control"][0])),
                    "control_shape_20x8": np.asarray(serial["control"]).shape == (20, 8),
                    "request_bounds": bool(np.max(np.abs(np.asarray(serial["control"])[:, 0::2])) <= 2.0 + 1e-10 and np.max(np.abs(np.asarray(serial["control"])[:, 1::2])) <= np.deg2rad(15.0) + 1e-10),
                    "force_stage_identity": bool(np.max(force) > 50.0) if checkpoint == "force_bearing" else bool(np.max(force) < 1e-12),
                }
                parameter_rows[checkpoint] = {
                    "state_construction": "same-parameter initialized state" if checkpoint == "initial" else "same-parameter initialized state with vehicle-1 world-x offset +0.03 m",
                    "point_force_n": np.asarray(force).tolist(),
                    "checks": {name: bool(value) for name, value in checks.items()},
                    "matrix_exact": matrices,
                    "serial_wall_s": serial_wall,
                    "parallel_wall_s": parallel_wall,
                }
            result[parameter] = parameter_rows
    return {"parallel_pool_warmup_s": warmup, "parameters": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    data = json.loads(protocol_path.read_text(encoding="utf-8"))
    if args.out.exists():
        raise ValueError("REFUSING_EXISTING_OUTPUT")
    validate_data(data, paper)
    negatives = negative_tests(data, paper)
    qp = qp_regression(paper)
    checks = {
        "positive_contract": True,
        "all_negative_cases_rejected": all(row["rejected"] for row in negatives.values()),
        "all_fixed_qp_checks_pass": all(
            all(point["checks"].values())
            for parameter in qp["parameters"].values()
            for point in parameter.values()
        ),
        "run_manifest_six_unique_rows": len(data["run_manifest"]) == 6,
        "absolute_parameter_tables_registered": set(data["absolute_parameters"]) == {"P1", "P2"},
    }
    status = "PASS_C0_R4_READY" if all(checks.values()) else "FAIL_C0_BLOCK_R4"
    args.out.mkdir(parents=True)
    report = {"status": status, "protocol": str(protocol_path), "protocol_sha256": sha(protocol_path), "checks": checks, "negative_tests": negatives, "fixed_qp_regression": qp, "absolute_parameters": data["absolute_parameters"], "run_manifest": data["run_manifest"], "source_sha256": sha(Path(__file__).resolve())}
    (args.out / "c0_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out / "r4_run_manifest.json").write_text(json.dumps({"schema_version": "POST-R3-C1-run-manifest-v1", "rows": data["run_manifest"]}, indent=2), encoding="utf-8")
    (args.out / "absolute_parameters.json").write_text(json.dumps(data["absolute_parameters"], indent=2), encoding="utf-8")
    labels = list(checks) + list(negatives)
    values = [checks[name] for name in checks] + [negatives[name]["rejected"] for name in negatives]
    fig, axis = plt.subplots(figsize=(11.5, 7.5), constrained_layout=True)
    y = np.arange(len(labels))
    axis.barh(y, np.ones(len(labels)), color=["#2ca02c" if value else "#d62728" for value in values])
    axis.set_yticks(y, labels)
    axis.set_xlim(0.0, 1.05)
    axis.set_xticks([0.0, 1.0], ["FAIL", "PASS/rejected"])
    axis.set_title(f"POST-R3 C0 migration and negative-contract coverage: {status}")
    axis.grid(axis="x", alpha=0.2)
    fig.savefig(args.out / "c0_contract_coverage.png", dpi=240)
    fig.savefig(args.out / "c0_contract_coverage.svg")
    plt.close(fig)
    manifest = {"stage": "POST-R3/C0", "source_files": [{"path": str(protocol_path), "sha256": sha(protocol_path)}, {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}], "figures": ["c0_contract_coverage.png", "c0_contract_coverage.svg"], "science_status": status, "figure_status": "PENDING_VISUAL_QA"}
    (args.out / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.out / "README.md").write_text("# POST-R3 C0接口资格\n\n包含候选身份迁移、十项拒绝用例、P1/P2绝对参数、六行运行清单及每参数两个固定QP检查点。图表QA前不释放R4。\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks": checks, "negative_count": len(negatives)}))
    if status != "PASS_C0_R4_READY":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
