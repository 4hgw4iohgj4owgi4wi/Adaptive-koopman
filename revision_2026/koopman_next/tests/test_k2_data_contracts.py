from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from audit_coverage import classify_windows
from data_manifest import (
    array_sha256,
    canonical_json,
    canonical_params,
    params_sha256,
    validate_manifest,
)
from generate_data import run_complete_control_interval, save_raw
from run_k2 import _simulate_pair
from scenarios import ScenarioSpec
from scenarios import command_for


def test_hundred_meter_complete_grid() -> None:
    calls: list[int] = []
    crossing_substep = None

    def stepper(index: int) -> float:
        nonlocal crossing_substep
        calls.append(index)
        if index == 2:
            crossing_substep = index + 1
        return 0.002 * (index + 1)

    values = run_complete_control_interval(stepper)
    assert calls == list(range(10))
    assert crossing_substep == 3
    assert values[-1] == 0.020
    time_s = np.arange(1, 9, dtype=float) * 0.020
    assert np.max(np.abs(np.diff(time_s) - 0.020)) <= 1.0e-15


def test_parameter_hash() -> None:
    from four_vehicle_common import ModelParams

    base = ModelParams()
    same = replace(base)
    changed = replace(base, payload=replace(base.payload, mass_kg=base.payload.mass_kg * 1.01))
    assert params_sha256(base) == params_sha256(same)
    assert params_sha256(base) != params_sha256(changed)
    payload = canonical_params(base)
    assert payload["schema"] == "ModelParams.resolved.v1"
    assert payload["units"]["payload.mass_kg"] == "kg"
    assert canonical_json(payload) == canonical_json(canonical_params(base))


def _manifest_row(trajectory_id: int, base: str, split: str, direction: str, plant: str) -> dict:
    return {
        "trajectory_id": trajectory_id,
        "base_family_id": base,
        "split": split,
        "direction": direction,
        "plant": plant,
        "params_json": "{}",
        "params_sha256": "ABC",
    }


def test_base_family_split() -> None:
    rows = [
        _manifest_row(0, "family-a", "train", "left", "V1-ES"),
        _manifest_row(1, "family-a", "train", "right", "V1-ES"),
        _manifest_row(2, "family-a", "train", "left", "R3-ES"),
        _manifest_row(3, "family-a", "train", "right", "R3-ES"),
        _manifest_row(4, "family-b", "validation", "none", "V1-ES"),
        _manifest_row(5, "family-b", "validation", "none", "R3-ES"),
    ]
    valid = validate_manifest(rows)
    assert valid["cross_split_base_family_count"] == 0
    assert valid["duplicate_trajectory_id_count"] == 0
    leaked = [dict(row) for row in rows]
    leaked[1]["split"] = "validation"
    assert validate_manifest(leaked)["cross_split_base_family_count"] == 1


def _coverage_arrays(kind: str) -> dict[str, np.ndarray]:
    count = 40
    event_counts = np.zeros((count, 16), dtype=int)
    smoothing = np.zeros((count, 4), dtype=float)
    control = np.zeros((count, 4, 2), dtype=float)
    state = np.zeros((count, 30), dtype=float)
    if kind == "maneuver":
        control[:, :, 1] = np.deg2rad(1.0)
    elif kind == "event":
        event_counts[7, 0] = 1
    elif kind != "steady":
        raise ValueError(kind)
    return {
        "time_s": np.arange(count, dtype=float) * 0.020,
        "event_counts16": event_counts,
        "smoothing_fraction": smoothing,
        "control4x2": control,
        "state30": state,
    }


def test_event_coverage() -> None:
    assert [row["class"] for row in classify_windows(_coverage_arrays("steady"), 20)] == [
        "steady",
        "steady",
    ]
    assert [row["class"] for row in classify_windows(_coverage_arrays("maneuver"), 20)] == [
        "maneuver",
        "maneuver",
    ]
    assert [row["class"] for row in classify_windows(_coverage_arrays("event"), 20)] == [
        "event",
        "steady",
    ]


def test_d2_retains_two_five_second_steps_with_repaired_amplitude() -> None:
    spec = ScenarioSpec("D2", "left", None, 100.0, True)
    acceleration = command_for(spec, 0.0, 0.0, None, None)
    primary = command_for(spec, 10.0, 31.0, 9.5, None)
    reverse = command_for(spec, 15.0, 55.0, 9.5, None)
    assert acceleration.acceleration_mps2 == 0.25
    assert (primary.virtual_front_deg, primary.virtual_rear_deg) == (3.5, -1.75)
    assert (reverse.virtual_front_deg, reverse.virtual_rear_deg) == (-3.5, 1.75)


def test_replay_hash() -> None:
    arrays = {"x": np.arange(12, dtype=np.float64).reshape(3, 4)}
    assert array_sha256(arrays) == array_sha256({"x": arrays["x"].copy()})
    changed = {"x": arrays["x"].copy()}
    changed["x"][0, 0] += 1.0
    assert array_sha256(arrays) != array_sha256(changed)


def test_save_raw_accepts_multiple_files_but_refuses_overwrite(tmp_path) -> None:
    from four_vehicle_common import ModelParams

    arrays = {"x": np.arange(3, dtype=float)}
    summary = {"status": "PASS"}
    first = tmp_path / "raw" / "first.npz"
    second = tmp_path / "raw" / "second.npz"
    save_raw(first, arrays, summary, ModelParams())
    save_raw(second, arrays, summary, ModelParams())
    assert first.exists() and second.exists()
    try:
        save_raw(first, arrays, summary, ModelParams())
    except FileExistsError as error:
        assert "refuse to overwrite" in str(error)
    else:
        raise AssertionError("save_raw overwrote an existing trajectory")


def test_parallel_pair_executor_smoke() -> None:
    from four_vehicle_common import ModelParams

    source_root = Path(__file__).resolve().parents[1]
    project_root = Path(os.environ["KOOPMAN_PROJECT_ROOT"])
    connector_src = project_root / "revision_2026" / "connector_r3_4" / "src"
    protocol = json.loads((source_root / "config" / "protocol.json").read_text(encoding="utf-8"))
    spec = ScenarioSpec("D0", "none", 0.04, None, False)
    job = (connector_src, spec, "V1", 910000, ModelParams(), protocol)
    with ProcessPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_simulate_pair, (job, job), chunksize=1))
    assert len(results) == 2
    for summary, arrays, replay_summary, replay_hash in results:
        assert summary["sample_count"] == 2
        assert summary["trajectory_array_sha256"] == replay_summary["trajectory_array_sha256"]
        assert replay_summary["trajectory_array_sha256"] == replay_hash
        assert np.allclose(arrays["time_s"], [0.02, 0.04], rtol=0.0, atol=1.0e-15)
