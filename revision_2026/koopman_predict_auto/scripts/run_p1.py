from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from actuator_rollout import rollout_actuator_interval
from causal_schema import build_schema_v4
from contracts import write_json
from data_adapter import INPUT_KEYS_V4, LABEL_KEYS_V4
from steering_actuator import SteeringActuatorConfig, step_actuator


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "p1"
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment["KOOPMAN_PROJECT_ROOT"] = str(project)
    pytest_result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT / "tests"), "-q"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (output / "pytest_stdout.txt").write_text(pytest_result.stdout, encoding="utf-8")
    (output / "pytest_stderr.txt").write_text(pytest_result.stderr, encoding="utf-8")

    values = protocol["actuator"]
    config = SteeringActuatorConfig(
        tau_delta_s=float(values["tau_delta_s"]),
        rate_max_radps=float(values["rate_max_radps"]),
        angle_max_rad=float(np.deg2rad(values["angle_max_deg"])),
    )
    request = np.asarray([0.30, 0.28, -0.26, -0.24])
    initial = np.asarray([0.01, 0.02, -0.01, -0.02])
    rollout = rollout_actuator_interval(
        initial,
        request,
        plant_step_s=float(values["plant_step_s"]),
        substeps=int(values["substeps_per_request"]),
        config=config,
    )
    mirror = rollout_actuator_interval(
        -initial,
        -request,
        plant_step_s=float(values["plant_step_s"]),
        substeps=int(values["substeps_per_request"]),
        config=config,
    )
    replay = rollout_actuator_interval(
        initial.copy(),
        request.copy(),
        plant_step_s=float(values["plant_step_s"]),
        substeps=int(values["substeps_per_request"]),
        config=config,
    )
    small_request = np.full(4, 0.01)
    one_step = step_actuator(
        small_request, np.zeros(4), float(values["plant_step_s"]), config
    )
    manual = small_request * (
        1.0 - np.exp(-float(values["plant_step_s"]) / config.tau_delta_s)
    )
    schema = build_schema_v4()
    angle_violation = max(
        float(np.max(np.abs(rollout["delta_act_substeps_rad"]))) - config.angle_max_rad,
        0.0,
    )
    rate_violation = max(
        float(np.max(np.abs(rollout["delta_rate_substeps_radps"])))
        - config.rate_max_radps,
        0.0,
    )
    mirror_error = float(
        np.max(
            np.abs(
                mirror["delta_act_substeps_rad"]
                + rollout["delta_act_substeps_rad"]
            )
        )
    )
    manual_error = float(
        np.max(np.abs(one_step["delta_act_next_rad"] - manual))
    )
    replay_equal = all(
        np.array_equal(rollout[key], replay[key]) for key in rollout
    )
    schema_passed = bool(
        schema["hybrid_dimension"] == 51
        and {item["name"] for item in schema["inputs"]} == set(INPUT_KEYS_V4)
        and {item["name"] for item in schema["labels"]} == set(LABEL_KEYS_V4)
    )
    tolerance = protocol["p2"]
    passed = bool(
        pytest_result.returncode == 0
        and angle_violation <= float(tolerance["angle_atol_rad"])
        and rate_violation <= float(tolerance["rate_atol_radps"])
        and mirror_error <= 1.0e-12
        and manual_error <= 1.0e-15
        and replay_equal
        and schema_passed
    )
    summary = {
        "stage": "P1",
        "passed": passed,
        "pytest_returncode": pytest_result.returncode,
        "pytest_stdout_path": str(output / "pytest_stdout.txt"),
        "pytest_stderr_path": str(output / "pytest_stderr.txt"),
        "angle_violation_rad": angle_violation,
        "rate_violation_radps": rate_violation,
        "mirror_error_rad": mirror_error,
        "manual_two_ms_error_rad": manual_error,
        "deterministic_replay_equal": replay_equal,
        "schema_v4_passed": schema_passed,
        "hybrid_dimension": schema["hybrid_dimension"],
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        summary.update(
            {
                "repair_code": "P1_ACTUATOR_OR_CAUSAL_CONTRACT_FAILED",
                "next_action": "Inspect P1 pytest and contract summary; do not run P2.",
            }
        )
    write_json(output / "contract_summary.json", summary)
    return summary
