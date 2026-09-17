from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "plant")]

from data_adapter import build_sample_variant, causal_input_digest_variant
from data_manifest import file_sha256
from dataset import prediction_cache_from_raw
from generate_data import resolved_params, save_raw, simulate_trajectory
from physics_audit import audit_trajectory, window_ledger
from scenarios import ScenarioSpec


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _spec(identity: dict) -> ScenarioSpec:
    return ScenarioSpec(
        scenario=str(identity["scenario"]),
        direction=str(identity["direction"]),
        duration_s=(
            None if identity.get("duration_s") is None else float(identity["duration_s"])
        ),
        distance_target_m=(
            None
            if identity.get("distance_target_m") is None
            else float(identity["distance_target_m"])
        ),
        natural_event_source=bool(identity.get("natural_event_source", True)),
        member=str(identity.get("member", "none")),
    )


def _causality_audit(
    arrays: dict[str, np.ndarray], params: object, protocol: dict
) -> dict:
    index = 1
    changed = {key: np.asarray(value).copy() for key, value in arrays.items()}
    stop = min(index + 21, len(changed["actual_steering_rad"]))
    changed["actual_steering_rad"][index + 1 : stop] += 0.75
    changed["actual_steering_rate_radps"][index + 1 : stop] -= 4.0
    variants = {}
    for variant in ("S0", "S1", "S2"):
        original = build_sample_variant(
            arrays,
            index,
            params,
            variant=variant,
            expected_step_s=float(protocol["k2"]["model_step_s"]),
            plant_step_s=float(protocol["k2"]["plant_step_s"]),
        )
        tampered = build_sample_variant(
            changed,
            index,
            params,
            variant=variant,
            expected_step_s=float(protocol["k2"]["model_step_s"]),
            plant_step_s=float(protocol["k2"]["plant_step_s"]),
        )
        variants[variant] = (
            causal_input_digest_variant(original, variant)
            == causal_input_digest_variant(tampered, variant)
        )
    return {"passed": all(variants.values()), "variants": variants}


def simulate_job(job: dict) -> dict:
    """Process-safe trajectory generator with optional replay and N5 cache."""

    started = time.perf_counter()
    identity = dict(job["identity"])
    protocol = job["protocol"]
    raw_path = Path(job["raw_path"])
    cache_path = Path(job["cache_path"]) if job.get("cache_path") else None
    try:
        params = resolved_params(int(identity["seed"]), protocol)
        meta_path = raw_path.with_suffix(".meta.json")
        if raw_path.exists() != meta_path.exists():
            raise FileExistsError(f"ambiguous partial raw exists without its peer: {raw_path}")
        recovered_raw = raw_path.exists()
        if recovered_raw:
            arrays = load_npz(raw_path)
            summary = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        else:
            summary, arrays = simulate_trajectory(
                _spec(identity),
                str(identity["law"]),
                int(identity["seed"]),
                params,
                protocol,
                actuator_mode="A3",
                load_transfer_enabled=True,
            )
        replay_match = True
        replay_runtime_s = 0.0
        if bool(job.get("replay", False)):
            replay_started = time.perf_counter()
            replay_summary, _ = simulate_trajectory(
                _spec(identity),
                str(identity["law"]),
                int(identity["seed"]),
                params,
                protocol,
                actuator_mode="A3",
                load_transfer_enabled=True,
            )
            replay_runtime_s = time.perf_counter() - replay_started
            replay_match = bool(
                summary["trajectory_array_sha256"]
                == replay_summary["trajectory_array_sha256"]
            )
        if not recovered_raw:
            save_raw(raw_path, arrays, summary, params)
        audit = audit_trajectory(
            identity,
            arrays,
            summary,
            protocol,
            replay_hash_match=replay_match,
        )
        windows = window_ledger(identity, arrays, protocol)
        causality = {"passed": True, "variants": {}}
        analytic_error = None
        if cache_path is not None:
            cache = prediction_cache_from_raw(arrays, params, protocol)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if cache_path.exists():
                existing_cache = load_npz(cache_path)
                def identical(key: str) -> bool:
                    left = np.asarray(existing_cache[key])
                    right = np.asarray(cache[key])
                    if left.dtype.kind in {"O", "U", "S"}:
                        return bool(np.array_equal(left, right))
                    return bool(np.array_equal(left, right, equal_nan=True))

                if set(existing_cache) != set(cache) or any(
                    not identical(key) for key in cache
                ):
                    raise ValueError(f"existing cache identity mismatch: {cache_path}")
            else:
                np.savez_compressed(cache_path, **cache)
            causality = _causality_audit(arrays, params, protocol)
            analytic_error = float(
                np.max(
                    np.abs(
                        cache["analytic_actual_next4"]
                        - cache["actual_steering4"][1:]
                    )
                )
            )
        row = {
            **identity,
            "raw_path": str(raw_path),
            "raw_file_sha256": file_sha256(raw_path),
            "raw_meta_sha256": file_sha256(raw_path.with_suffix(".meta.json")),
            "trajectory_array_sha256": summary["trajectory_array_sha256"],
            "params_sha256": summary["params_sha256"],
            "params_json": summary["params_json"],
            "sample_count": int(summary["sample_count"]),
            "duration_s_actual": float(summary["duration_s"]),
            "distance_m": float(summary["distance_m"]),
            "status": summary["status"],
            "first_runtime_s": float(summary["runtime_s"]),
            "replay_runtime_s": replay_runtime_s,
            "replay_hash_match": replay_match,
            "audit_passed": bool(audit["passed"]),
            "failed_gates": json.dumps(audit["failed_gates"]),
            "cache_path": None if cache_path is None else str(cache_path),
            "cache_sha256": None if cache_path is None else file_sha256(cache_path),
            "causality_passed": bool(causality["passed"]),
            "analytic_actuator_max_abs_rad": analytic_error,
            "worker_wall_s": time.perf_counter() - started,
            "recovered_raw": recovered_raw,
        }
        return {
            "ok": True,
            "row": row,
            "audit": audit,
            "windows": windows,
            "causality": causality,
        }
    except Exception as error:
        return {
            "ok": False,
            "identity": identity,
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "worker_wall_s": time.perf_counter() - started,
        }


def simulate_hash_only(job: dict) -> dict:
    """Run without persistent outputs for worker-count identity scaling."""

    identity = dict(job["identity"])
    protocol = job["protocol"]
    started = time.perf_counter()
    try:
        params = resolved_params(int(identity["seed"]), protocol)
        summary, _ = simulate_trajectory(
            _spec(identity),
            str(identity["law"]),
            int(identity["seed"]),
            params,
            protocol,
            actuator_mode="A3",
            load_transfer_enabled=True,
        )
        return {
            "ok": True,
            "trajectory_id": int(identity["trajectory_id"]),
            "trajectory_array_sha256": summary["trajectory_array_sha256"],
            "runtime_s": time.perf_counter() - started,
        }
    except Exception as error:
        return {
            "ok": False,
            "trajectory_id": int(identity["trajectory_id"]),
            "error": repr(error),
            "traceback": traceback.format_exc(),
        }
