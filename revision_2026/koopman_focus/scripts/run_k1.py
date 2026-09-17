from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from causal_schema import build_schema_v3
from contracts import write_json
from data_adapter import build_sample, causal_input_digest, parameter_vector, validate_force_interfaces
from relative_coordinates import (
    G0_SLICE,
    G1_SLICE,
    G2_SLICE,
    G3_SLICE,
    MIRROR_INDEX,
    decode_absolute,
    encode_relative,
    rotation,
)


def read_manifest(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rigid_transform(state30: np.ndarray, angle: float, translation: np.ndarray) -> np.ndarray:
    state = np.asarray(state30, dtype=float).copy()
    transform = rotation(angle)
    for offset in (0, 6, 12, 18, 24):
        state[offset : offset + 2] = transform @ state[offset : offset + 2] + translation
        state[offset + 2] += angle
    return state


def mirror_state(state30: np.ndarray) -> np.ndarray:
    state = np.asarray(state30, dtype=float)
    vehicles = state[:24].reshape(4, 6).copy()[MIRROR_INDEX]
    payload = state[24:].copy()
    for body in list(vehicles) + [payload]:
        body[1] *= -1.0
        body[2] *= -1.0
        body[4] *= -1.0
        body[5] *= -1.0
    return np.r_[vehicles.ravel(), payload]


def mirror_expected(relative47: np.ndarray) -> np.ndarray:
    source = np.asarray(relative47, dtype=float)
    result = source.copy()
    result[G0_SLICE] = source[G0_SLICE] * np.asarray([1.0, -1.0, -1.0])
    g1 = source[G1_SLICE].reshape(4, 4)[MIRROR_INDEX].copy()
    g1 *= np.asarray([1.0, -1.0, -1.0, 1.0])
    result[G1_SLICE] = g1.ravel()
    g2 = source[G2_SLICE].reshape(4, 3)[MIRROR_INDEX].copy()
    g2 *= np.asarray([1.0, -1.0, -1.0])
    result[G2_SLICE] = g2.ravel()
    g3 = source[G3_SLICE].reshape(4, 4)[MIRROR_INDEX].copy()
    g3 *= np.asarray([1.0, -1.0, 1.0, -1.0])
    result[G3_SLICE] = g3.ravel()
    return result


def future_perturbed(arrays: dict[str, np.ndarray], index: int) -> dict[str, np.ndarray]:
    result = {key: np.asarray(value).copy() for key, value in arrays.items()}
    future_fields = (
        "state30",
        "force_payload_body_n",
        "force_interval_mean_body_n",
        "force_interval_impulse_world_ns",
        "internal_force_interval_mean_n",
        "tension_proxy_interval_mean_n",
        "event_counts16",
        "contact_fraction",
        "smoothing_fraction",
    )
    for field_index, key in enumerate(future_fields, start=1):
        result[key][index + 1] = result[key][index + 1] + field_index * 0.123456789
    return result


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "k1"
    output.mkdir(parents=True, exist_ok=False)
    connector_src = project / "revision_2026" / "connector_r3_4" / "src"
    sys.path.insert(0, str(connector_src))
    from four_vehicle_common import ModelParams

    thresholds = protocol["k1"]
    expected_step_s = float(thresholds["expected_model_step_s"])
    step_atol_s = float(thresholds["model_step_atol_s"])
    schema = build_schema_v3()
    schema["model_step_contract"] = {
        "expected_step_s": expected_step_s,
        "absolute_tolerance_s": step_atol_s,
        "off_grid_policy": "reject_before_sample_construction",
    }
    write_json(output / "schema.json", schema)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["KOOPMAN_PROJECT_ROOT"] = str(project)
    tests = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            str(ROOT / "tests"),
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    (output / "pytest.stdout.txt").write_text(tests.stdout, encoding="utf-8")
    (output / "pytest.stderr.txt").write_text(tests.stderr, encoding="utf-8")

    data_dir = project / Path(protocol["connector_data"])
    manifest_path = data_dir / "trajectory_manifest.csv"
    manifest = read_manifest(manifest_path)
    audit_rows = []
    maxima = {
        "roundtrip_float64": 0.0,
        "roundtrip_float32": 0.0,
        "rigid_invariance": 0.0,
        "mirror_equivariance": 0.0,
        "geometry_g3": 0.0,
        "future_input_digest_mismatch": 0,
        "future_label_unchanged": 0,
        "action_reaction_n": 0.0,
        "payload_wrench": 0.0,
        "internal_force_n": 0.0,
        "internal_null": 0.0,
        "tension_n": 0.0,
        "q_manual": 0.0,
        "accepted_previous_interval_error_s": 0.0,
        "accepted_prediction_interval_error_s": 0.0,
    }
    params = ModelParams()
    first_compatible_arrays = None
    incompatible_trajectories = []
    compatible_trajectory_count = 0
    off_grid_sample_accepted = 0
    observed_step_s = set()
    for row in manifest:
        raw_path = Path(row["raw_path"])
        with np.load(raw_path) as source:
            arrays = {key: source[key].copy() for key in source.files if not key.endswith("_2ms")}
        count = len(arrays["time_s"])
        all_steps = np.diff(np.asarray(arrays["time_s"], dtype=float))
        observed_step_s.update(float(np.round(value, 12)) for value in all_steps)
        step_error = np.abs(all_steps - expected_step_s)
        trajectory_compatible = bool(
            np.all(np.isfinite(all_steps))
            and np.all(all_steps > 0.0)
            and np.max(step_error) <= step_atol_s
        )
        if trajectory_compatible:
            compatible_trajectory_count += 1
            if first_compatible_arrays is None:
                first_compatible_arrays = arrays
        else:
            incompatible_trajectories.append(
                {
                    "trajectory_id": int(row["trajectory_id"]),
                    "scenario": row["scenario"],
                    "plant": row["plant"],
                    "split": row["split"],
                    "samples": int(count),
                    "step_min_s": float(np.min(all_steps)),
                    "step_max_s": float(np.max(all_steps)),
                    "off_grid_interval_count": int(np.sum(step_error > step_atol_s)),
                    "first_off_grid_interval_indices": np.flatnonzero(step_error > step_atol_s)[:8].tolist(),
                    "target_step_s": expected_step_s,
                }
            )
        stride = max(1, (count - 2) // 32)
        indices = sorted(set(range(1, count - 1, stride)) | {count - 2})
        local = {key: 0.0 for key in maxima if key not in {"future_input_digest_mismatch", "future_label_unchanged"}}
        digest_mismatch = 0
        label_unchanged = 0
        for index in indices:
            state = np.asarray(arrays["state30"][index], dtype=float)
            encoded = encode_relative(state, params)
            decoded = decode_absolute(encoded["relative_state47"], encoded["payload_pose_context3"])
            error64 = float(np.max(np.abs(decoded - state)))
            decoded32 = decode_absolute(
                encoded["relative_state47"].astype(np.float32),
                encoded["payload_pose_context3"].astype(np.float32),
            ).astype(np.float32)
            error32 = float(np.max(np.abs(decoded32 - state.astype(np.float32))))
            transformed = rigid_transform(state, 0.37, np.asarray([13.0, -7.0]))
            transformed_relative = encode_relative(transformed, params)["relative_state47"]
            rigid_error = float(np.max(np.abs(transformed_relative - encoded["relative_state47"])))
            mirrored = encode_relative(mirror_state(state), params)["relative_state47"]
            mirror_error = float(np.max(np.abs(mirrored - mirror_expected(encoded["relative_state47"]))))
            reencoded = encode_relative(decoded, params)["relative_state47"]
            geometry_error = float(np.max(np.abs(reencoded[G3_SLICE] - encoded["relative_state47"][G3_SLICE])))
            sample = None
            if trajectory_compatible:
                sample = build_sample(
                    arrays,
                    index,
                    params,
                    expected_step_s=expected_step_s,
                    step_atol_s=step_atol_s,
                )
                if index in {indices[0], indices[-1]}:
                    perturbed_sample = build_sample(
                        future_perturbed(arrays, index),
                        index,
                        params,
                        expected_step_s=expected_step_s,
                        step_atol_s=step_atol_s,
                    )
                    digest_mismatch += int(causal_input_digest(sample) != causal_input_digest(perturbed_sample))
                    label_unchanged += int(
                        np.array_equal(sample["physical_state30_k1"], perturbed_sample["physical_state30_k1"])
                    )
            else:
                try:
                    build_sample(
                        arrays,
                        index,
                        params,
                        expected_step_s=expected_step_s,
                        step_atol_s=step_atol_s,
                    )
                except ValueError as error:
                    if "off-grid" not in str(error):
                        raise
                else:
                    off_grid_sample_accepted += 1
            force = validate_force_interfaces(arrays, index, params)
            force_body = np.asarray(arrays["force_payload_body_n"][index], dtype=float)
            q_manual = np.asarray(
                [
                    0.5 * ((force_body[0, 0] + force_body[1, 0]) - (force_body[2, 0] + force_body[3, 0])),
                    0.5 * ((force_body[0, 1] + force_body[2, 1]) - (force_body[1, 1] + force_body[3, 1])),
                ]
            )
            previous_interval_error = abs(
                float(arrays["time_s"][index] - arrays["time_s"][index - 1]) - expected_step_s
            )
            prediction_interval_error = abs(
                float(arrays["time_s"][index + 1] - arrays["time_s"][index]) - expected_step_s
            )
            values = {
                "roundtrip_float64": error64,
                "roundtrip_float32": error32,
                "rigid_invariance": rigid_error,
                "mirror_equivariance": mirror_error,
                "geometry_g3": geometry_error,
                "action_reaction_n": force["action_reaction_max_n"],
                "payload_wrench": force["payload_wrench_max_abs"],
                "internal_force_n": force["internal_force_max_abs_n"],
                "internal_null": force["internal_null_norm"],
                "tension_n": force["tension_max_abs_n"],
                "q_manual": float(np.max(np.abs(force["q"] - q_manual))),
                "accepted_previous_interval_error_s": (
                    previous_interval_error if trajectory_compatible else 0.0
                ),
                "accepted_prediction_interval_error_s": (
                    prediction_interval_error if trajectory_compatible else 0.0
                ),
            }
            for key, value in values.items():
                local[key] = max(local[key], value)
                maxima[key] = max(maxima[key], value)
        maxima["future_input_digest_mismatch"] += digest_mismatch
        maxima["future_label_unchanged"] += label_unchanged
        audit_rows.append(
            {
                "trajectory_id": int(row["trajectory_id"]),
                "scenario": row["scenario"],
                "plant": row["plant"],
                "split": row["split"],
                "seed": int(row["seed"]),
                "checked_samples": len(indices),
                "model_step_compatible": trajectory_compatible,
                "step_min_s": float(np.min(all_steps)),
                "step_max_s": float(np.max(all_steps)),
                **local,
                "future_input_digest_mismatch": digest_mismatch,
                "future_label_unchanged": label_unchanged,
            }
        )
    write_csv(output / "trajectory_contract_audit.csv", audit_rows)

    randomized = replace(
        params,
        vehicle=replace(params.vehicle, mass_kg=params.vehicle.mass_kg * 1.03, mu=0.81),
        payload=replace(params.payload, mass_kg=params.payload.mass_kg * 1.07, length_m=params.payload.length_m * 0.97),
        connector=replace(
            params.connector,
            stiffness_npm=params.connector.stiffness_npm * 1.05,
            damping_nspm=params.connector.damping_nspm * 0.93,
        ),
    )
    assert first_compatible_arrays is not None
    default_sample = build_sample(
        first_compatible_arrays, 1, params, expected_step_s=expected_step_s, step_atol_s=step_atol_s
    )
    randomized_sample = build_sample(
        first_compatible_arrays, 1, randomized, expected_step_s=expected_step_s, step_atol_s=step_atol_s
    )
    parameter_passthrough = {
        "default": parameter_vector(params).tolist(),
        "randomized": parameter_vector(randomized).tolist(),
        "parameter_vector_changed": not np.array_equal(
            default_sample["parameter_vector_k"], randomized_sample["parameter_vector_k"]
        ),
        "connector_geometry_changed": not np.array_equal(
            default_sample["relative_state47_k"], randomized_sample["relative_state47_k"]
        ),
    }
    write_json(output / "parameter_passthrough.json", parameter_passthrough)

    limitations = {
        "not_hard_failures": True,
        "items": [
            {
                "code": "F23_MIXED_MODEL_STEP",
                "fact": (
                    f"F23 contains {compatible_trajectory_count} trajectories on the registered "
                    f"{expected_step_s:.3f} s model step and {len(incompatible_trajectories)} off-grid "
                    f"trajectories: {incompatible_trajectories}."
                ),
                "cause": "The 100 m simulator normally aggregates ten 2 ms plant steps, but breaks the inner loop as soon as distance reaches 100 m and then records that partial terminal interval. In both plants the terminal interval is 6 ms while regular intervals are 20 ms.",
                "impact": "F23 cannot be used as one homogeneous one-step training set; identical model steps would represent different physical horizons. The repaired adapter now rejects the two off-grid trajectories.",
                "minimum_resolution": "K2/K3 must generate every model sample on one frozen 20 ms grid and record step_min/step_max in each trajectory manifest; do not repair F23 by relabeling 6 ms samples as 20 ms.",
            },
            {
                "code": "F23_PARAMETER_IDENTITY_IMPLICIT_DEFAULT",
                "fact": "The frozen F23 trajectory manifest has no per-trajectory mass/k/c/free-play/mu fields.",
                "cause": "F23 was an interface-smoke data set generated with ModelParams() defaults, before the K3 parameterized-data contract existed.",
                "impact": "K1 can verify explicit parameter pass-through synthetically, but cannot retroactively prove randomized-parameter replay from F23.",
                "minimum_resolution": "K2/K3 raw and sample manifests must store the resolved ModelParams vector and hash for every base family.",
            },
            {
                "code": "F23_SPLIT_TOO_NARROW_FOR_MODEL_SELECTION",
                "fact": "The frozen 26 trajectories contain only one validation and two test trajectories per plant, concentrated in directional connector excitations.",
                "cause": "F23 was intentionally expanded only enough to repair the smoke-test training coverage without moving its original validation/test trajectories.",
                "impact": "No K4-K12 model superiority, gate identifiability, scenario generalization or statistical claim can be repaired using F23 alone.",
                "minimum_resolution": "Generate K2 coverage pilot, then independent K3 train/validation/development base families; do not reuse F23 for selection.",
            },
            {
                "code": "F23_EVENT_COVERAGE_INSUFFICIENT_FOR_GATE",
                "fact": "Existing evidence reports about 4.80% event-containing control intervals and about 1.46% smoothing exposure for R3.",
                "cause": "Most F23 trajectories are natural low-load maneuvers; the data set was not designed to identify three event regimes.",
                "impact": "A three-expert gate or event residual cannot be made identifiable by K1 code changes or duplicated windows.",
                "minimum_resolution": "K2 must add genuine D10 and at least three natural maneuver families with events, then count non-overlapping 20-step windows.",
            },
        ],
    }
    write_json(output / "limitations.json", limitations)

    passed = bool(
        tests.returncode == 0
        and len(manifest) == int(thresholds["frozen_interface_trajectory_count"])
        and maxima["roundtrip_float64"] <= float(thresholds["roundtrip_float64_atol"])
        and maxima["roundtrip_float32"] <= float(thresholds["roundtrip_float32_atol"])
        and maxima["rigid_invariance"] <= float(thresholds["coordinate_contract_atol"])
        and maxima["mirror_equivariance"] <= float(thresholds["coordinate_contract_atol"])
        and maxima["geometry_g3"] <= float(thresholds["coordinate_contract_atol"])
        and maxima["future_input_digest_mismatch"] <= int(thresholds["future_leakage_byte_mismatch_max"])
        and maxima["future_label_unchanged"] == 0
        and maxima["action_reaction_n"] <= float(thresholds["force_contract_atol"])
        and maxima["payload_wrench"] <= float(thresholds["force_contract_atol"])
        and maxima["internal_force_n"] <= float(thresholds["force_contract_atol"])
        and maxima["internal_null"] <= float(thresholds["force_contract_atol"])
        and maxima["tension_n"] <= float(thresholds["force_contract_atol"])
        and maxima["q_manual"] <= float(thresholds["force_contract_atol"])
        and maxima["accepted_previous_interval_error_s"] <= step_atol_s
        and maxima["accepted_prediction_interval_error_s"] <= step_atol_s
        and off_grid_sample_accepted == 0
        and compatible_trajectory_count + len(incompatible_trajectories) == len(manifest)
        and compatible_trajectory_count > 0
        and parameter_passthrough["parameter_vector_changed"]
        and parameter_passthrough["connector_geometry_changed"]
    )
    metrics = {
        "passed": passed,
        "trajectory_count": len(manifest),
        "checked_sample_count": sum(row["checked_samples"] for row in audit_rows),
        "pytest_returncode": tests.returncode,
        "pytest_summary": tests.stdout.strip(),
        "maxima": maxima,
        "time_contract": {
            "target_model_step_s": expected_step_s,
            "tolerance_s": step_atol_s,
            "observed_step_s": sorted(observed_step_s),
            "compatible_trajectory_count": compatible_trajectory_count,
            "rejected_off_grid_trajectory_count": len(incompatible_trajectories),
            "off_grid_sample_accepted": off_grid_sample_accepted,
            "incompatible_trajectories": incompatible_trajectories,
        },
        "parameter_passthrough": parameter_passthrough,
        "limitations_path": str(output / "limitations.json"),
    }
    write_json(output / "metrics.json", metrics)
    complete = {
        "stage": "K1",
        "passed": passed,
        "schema_path": str(output / "schema.json"),
        "metrics_path": str(output / "metrics.json"),
        "trajectory_audit_path": str(output / "trajectory_contract_audit.csv"),
        "parameter_passthrough_path": str(output / "parameter_passthrough.json"),
        "limitations_path": str(output / "limitations.json"),
        "trajectory_count": len(manifest),
        "checked_sample_count": metrics["checked_sample_count"],
        "maxima": maxima,
        "time_contract": metrics["time_contract"],
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete.update(
            {
                "repair_code": "K1_CAUSAL_COORDINATE_OR_FORCE_CONTRACT_FAILED",
                "next_action": "Inspect pytest and trajectory_contract_audit; do not run K2 or training.",
            }
        )
    write_json(output / "complete.json", complete)
    return complete
