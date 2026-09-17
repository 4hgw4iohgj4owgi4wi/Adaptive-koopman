import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def _sanitize_name(s: str, fallback: str = "unknown") -> str:
    txt = str(s or "").strip()
    if not txt:
        txt = fallback
    txt = re.sub(r"[^A-Za-z0-9._-]+", "_", txt)
    txt = txt.strip("._-")
    return txt or fallback


def _safe_float(v: Any, default: float = np.nan) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return _safe_float(v)
    if isinstance(v, (np.integer, int)):
        return _safe_int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return v


def _extract_series(result: Dict[str, Any]) -> Dict[str, np.ndarray]:
    team = np.asarray(result.get("team_state_hist", []), dtype=float)
    team_ref = np.asarray(result.get("ref_team_hist", []), dtype=float)
    sim_steps = _safe_int(result.get("sim_steps", -1), -1)
    n = min(
        max(0, sim_steps + 1),
        team.shape[0] if team.ndim == 2 else 0,
        team_ref.shape[0] if team_ref.ndim == 2 else 0,
    )

    if n <= 0:
        return {
            "t": np.array([], dtype=float),
            "e_s_system": np.array([], dtype=float),
            "e_y_system": np.array([], dtype=float),
            "e_pos_system": np.array([], dtype=float),
            "step_runtime_hist": np.asarray(result.get("step_runtime_hist", []), dtype=float),
        }

    e_s = team[:n, 0] - team_ref[:n, 0]
    e_y = team[:n, 1] - team_ref[:n, 1]
    e_pos = np.hypot(e_s, e_y)
    dt = _safe_float(result.get("case", {}).get("dt", np.nan), np.nan)
    if not np.isfinite(dt) or dt <= 0:
        dt = _safe_float(result.get("dt", 0.02), 0.02)
    t = np.arange(n, dtype=float) * float(dt)

    return {
        "t": t,
        "e_s_system": np.asarray(e_s, dtype=float),
        "e_y_system": np.asarray(e_y, dtype=float),
        "e_pos_system": np.asarray(e_pos, dtype=float),
        "step_runtime_hist": np.asarray(result.get("step_runtime_hist", []), dtype=float),
    }


def save_tf12_history_record(
    *,
    result: Dict[str, Any],
    method_cfg: Dict[str, Any],
    case_name: str = "tf12_main",
    scenario_mode: str = "unknown",
    root_dir: str = "results/history/tf12",
) -> Dict[str, str]:
    """Save compact history snapshot with timestamped clear path.

    Returns:
        {"npz_path": "...", "json_path": "..."}
    """
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    day = now.strftime("%Y-%m-%d")

    method_name = _sanitize_name(method_cfg.get("name", "method"))
    case_tag = _sanitize_name(case_name, "tf12_main")
    mode_tag = _sanitize_name(scenario_mode, "unknown")

    base_dir = Path(root_dir) / day
    base_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{stamp}_{case_tag}_{mode_tag}_{method_name}"
    npz_path = base_dir / f"{stem}.npz"
    json_path = base_dir / f"{stem}.json"

    series = _extract_series(result)
    vehicle_metrics = result.get("vehicle_metrics", [])
    max_abs_ey = []
    max_abs_es = []
    for m in vehicle_metrics:
        max_abs_ey.append(_safe_float(m.get("max_lat", np.nan), np.nan))
        max_abs_es.append(_safe_float(m.get("max_long", np.nan), np.nan))

    metadata = {
        "timestamp_local": now.isoformat(timespec="seconds"),
        "history_version": "tf12_v1",
        "case_name": case_tag,
        "scenario_mode": mode_tag,
        "method_name": method_name,
        "full_path_reached": bool(result.get("full_path_reached", False)),
        "sim_steps": _safe_int(result.get("sim_steps", -1), -1),
        "step_time_mean": _safe_float(result.get("step_time_mean", np.nan), np.nan),
        "step_time_max": _safe_float(result.get("step_time_max", np.nan), np.nan),
        "rmse_lat_mean": _safe_float(result.get("rmse_lat_mean", np.nan), np.nan),
        "rmse_long_mean": _safe_float(result.get("rmse_long_mean", np.nan), np.nan),
        "max_lat_global": _safe_float(result.get("max_lat_global", np.nan), np.nan),
        "max_long_global": _safe_float(result.get("max_long_global", np.nan), np.nan),
        "progress_ratio": _safe_float(result.get("progress_ratio", np.nan), np.nan),
        "final_s_team": _safe_float(
            result.get("final_s_team", result.get("final_s", np.nan)),
            np.nan,
        ),
        "target_s_team": _safe_float(result.get("target_s_team", np.nan), np.nan),
        "fleet_vehicle_max_abs_ey": max_abs_ey,
        "fleet_vehicle_max_abs_es": max_abs_es,
        "tf14_fdi_summary": _jsonable(result.get("tf14_fdi_summary")),
        "tf14_switch_summary": _jsonable(result.get("tf14_switch_summary")),
        "tf14_certificate_summary": _jsonable(result.get("tf14_certificate_summary")),
        "tf14_interaction_summary": _jsonable(result.get("tf14_interaction_summary")),
        "npz_path": str(npz_path),
        "json_path": str(json_path),
    }

    np.savez_compressed(
        npz_path,
        metadata_json=np.array(json.dumps(metadata, ensure_ascii=False), dtype=object),
        t=series["t"],
        e_s_system=series["e_s_system"],
        e_y_system=series["e_y_system"],
        e_pos_system=series["e_pos_system"],
        step_runtime_hist=series["step_runtime_hist"],
    )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {"npz_path": str(npz_path), "json_path": str(json_path)}


def load_tf12_history_records(
    *,
    root_dir: str = "results/history/tf12",
    limit: int = 60,
    load_series: bool = True,
) -> List[Dict[str, Any]]:
    base = Path(root_dir)
    if not base.exists():
        return []

    files = sorted(base.rglob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit > 0:
        files = files[: int(limit)]

    out: List[Dict[str, Any]] = []
    for fp in files:
        try:
            pack = np.load(fp, allow_pickle=True)
            md = json.loads(str(pack["metadata_json"].item()))
            item: Dict[str, Any] = {"metadata": md}
            if load_series:
                item["series"] = {
                    "t": np.asarray(pack["t"], dtype=float),
                    "e_s_system": np.asarray(pack["e_s_system"], dtype=float),
                    "e_y_system": np.asarray(pack["e_y_system"], dtype=float),
                    "e_pos_system": np.asarray(pack["e_pos_system"], dtype=float),
                    "step_runtime_hist": np.asarray(pack["step_runtime_hist"], dtype=float),
                }
            out.append(item)
        except Exception:
            continue
    return out
