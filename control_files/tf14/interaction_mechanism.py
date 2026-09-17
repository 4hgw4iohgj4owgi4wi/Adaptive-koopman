from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np


def _as_float(v: Any, default: float = np.nan) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _as_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _flatten_records(seq: Optional[Sequence[Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in seq or []:
        if isinstance(item, Mapping):
            out.append(dict(item))
        elif isinstance(item, (list, tuple)):
            for sub in item:
                if isinstance(sub, Mapping):
                    out.append(dict(sub))
    return out


def _corr(x: Sequence[float], y: Sequence[float]) -> float:
    xx = np.asarray(x, dtype=float).reshape(-1)
    yy = np.asarray(y, dtype=float).reshape(-1)
    n = min(xx.size, yy.size)
    if n < 3:
        return float("nan")
    xx = xx[:n]
    yy = yy[:n]
    valid = np.isfinite(xx) & np.isfinite(yy)
    if int(np.sum(valid)) < 3:
        return float("nan")
    xx = xx[valid]
    yy = yy[valid]
    if float(np.std(xx)) < 1e-12 or float(np.std(yy)) < 1e-12:
        return float("nan")
    return float(np.corrcoef(xx, yy)[0, 1])


def _first_step(records: Sequence[Mapping[str, Any]], predicate) -> Optional[int]:
    steps = []
    for item in records:
        try:
            if predicate(item):
                steps.append(_as_int(item.get("step", -1), -1))
        except Exception:
            continue
    steps = [s for s in steps if s >= 0]
    return int(min(steps)) if steps else None


def _step_series(
    records: Sequence[Mapping[str, Any]],
    key: str,
    *,
    reducer: str = "mean",
    default: float = np.nan,
) -> Tuple[np.ndarray, np.ndarray]:
    buckets: Dict[int, List[float]] = {}
    for item in records:
        step = _as_int(item.get("step", -1), -1)
        if step < 0:
            continue
        val = _as_float(item.get(key, default), default)
        if not np.isfinite(val):
            continue
        buckets.setdefault(step, []).append(val)
    if not buckets:
        return np.array([], dtype=int), np.array([], dtype=float)
    steps = np.array(sorted(buckets.keys()), dtype=int)
    vals = []
    for s in steps:
        arr = np.asarray(buckets[int(s)], dtype=float)
        if reducer == "max":
            vals.append(float(np.max(arr)))
        elif reducer == "min":
            vals.append(float(np.min(arr)))
        else:
            vals.append(float(np.mean(arr)))
    return steps, np.asarray(vals, dtype=float)


def _series_from_list(records: Sequence[Mapping[str, Any]], key: str, default: float = np.nan) -> np.ndarray:
    vals = [_as_float(item.get(key, default), default) for item in records]
    return np.asarray(vals, dtype=float)


def _mode_counts(switch_hist: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in switch_hist:
        mode = str(item.get("global_mode", item.get("mode", "unknown")))
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def _certificate_by_mode(cert_hist: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, Dict[str, List[float]]] = {}
    for item in cert_hist:
        mode = str(item.get("mode", "unknown"))
        grouped.setdefault(mode, {"V": [], "margin": [], "ok": []})
        grouped[mode]["V"].append(_as_float(item.get("V", np.nan), np.nan))
        grouped[mode]["margin"].append(_as_float(item.get("contraction_margin", np.nan), np.nan))
        grouped[mode]["ok"].append(1.0 if bool(item.get("certificate_ok", False)) else 0.0)
    out: Dict[str, Dict[str, float]] = {}
    for mode, vals in grouped.items():
        v = np.asarray(vals["V"], dtype=float)
        margin = np.asarray(vals["margin"], dtype=float)
        ok = np.asarray(vals["ok"], dtype=float)
        out[mode] = {
            "mean_V": float(np.nanmean(v)) if v.size else float("nan"),
            "max_V": float(np.nanmax(v)) if v.size else float("nan"),
            "mean_margin": float(np.nanmean(margin)) if margin.size else float("nan"),
            "ok_ratio": float(np.nanmean(ok)) if ok.size else float("nan"),
            "count": int(v.size),
        }
    return out


def summarize_tf14_interactions(
    *,
    fdi_hist: Optional[Sequence[Any]] = None,
    switch_hist: Optional[Sequence[Any]] = None,
    certificate_hist: Optional[Sequence[Any]] = None,
    comm_diag_hist: Optional[Sequence[Mapping[str, Any]]] = None,
    fault_diag_hist: Optional[Sequence[Mapping[str, Any]]] = None,
    control_spread_hist: Optional[Sequence[Mapping[str, Any]]] = None,
    payload_force_hist: Optional[Sequence[Mapping[str, Any]]] = None,
    dt: float = 0.02,
) -> Dict[str, Any]:
    """Build mechanism-level statistics for TF14.

    The returned fields are meant for paper figures/tables: they quantify the
    chain from communication/fault disturbances to diagnosis, switching,
    redistribution, payload internal force, and certificate response.
    """

    flat_fdi = _flatten_records(fdi_hist)
    flat_switch = _flatten_records(switch_hist)
    flat_cert = _flatten_records(certificate_hist)
    comm = [dict(x) for x in (comm_diag_hist or []) if isinstance(x, Mapping)]
    fault = [dict(x) for x in (fault_diag_hist or []) if isinstance(x, Mapping)]
    spread = [dict(x) for x in (control_spread_hist or []) if isinstance(x, Mapping)]
    payload = [dict(x) for x in (payload_force_hist or []) if isinstance(x, Mapping)]
    dt = float(max(dt, 1e-9))

    fault_first = _first_step(fault, lambda d: bool(d.get("active", False)))
    detected_first = _first_step(
        flat_fdi,
        lambda d: bool(d.get("detected", False))
        or str(d.get("identified_mode", "nominal")) not in {"nominal", ""},
    )
    switch_first = _first_step(
        flat_switch,
        lambda d: str(d.get("global_mode", "nominal_koopman_mpc")) != "nominal_koopman_mpc",
    )

    fault_to_detection_steps = None
    if fault_first is not None and detected_first is not None:
        fault_to_detection_steps = int(max(0, detected_first - fault_first))

    detection_to_switch_steps = None
    if detected_first is not None and switch_first is not None:
        detection_to_switch_steps = int(max(0, switch_first - detected_first))

    _, residual_step = _step_series(flat_fdi, "residual_ewma", reducer="mean")
    _, conf_step = _step_series(flat_fdi, "confidence", reducer="mean")
    q_global = _series_from_list(comm, "quality_global", 1.0)
    comm_degrade = 1.0 - q_global if q_global.size else np.array([], dtype=float)
    fault_deficit = _series_from_list(fault, "deficit_norm", 0.0)
    redistributed_delta = _series_from_list(spread, "redistributed_total_delta", np.nan)
    redistributed_ax = _series_from_list(spread, "redistributed_total_ax", np.nan)
    if redistributed_delta.size == 0 or not np.any(np.isfinite(redistributed_delta)):
        redistributed_delta = _series_from_list(flat_switch, "redistributed_total_delta", 0.0)
    if redistributed_ax.size == 0 or not np.any(np.isfinite(redistributed_ax)):
        redistributed_ax = _series_from_list(flat_switch, "redistributed_total_ax", 0.0)
    if redistributed_delta.size or redistributed_ax.size:
        n_red = max(redistributed_delta.size, redistributed_ax.size)
        rd = np.zeros(n_red, dtype=float)
        ra = np.zeros(n_red, dtype=float)
        rd[: redistributed_delta.size] = np.nan_to_num(redistributed_delta, nan=0.0)
        ra[: redistributed_ax.size] = np.nan_to_num(redistributed_ax, nan=0.0)
        redistributed_norm = np.hypot(rd, ra)
    else:
        redistributed_norm = np.array([], dtype=float)

    if payload:
        mz_payload = np.abs(_series_from_list(payload, "mz_payload", 0.0))
        corner_spread = []
        for item in payload:
            loads = np.asarray(item.get("corner_normal_loads", []), dtype=float).reshape(-1)
            corner_spread.append(float(np.ptp(loads)) if loads.size else np.nan)
        corner_spread_arr = np.asarray(corner_spread, dtype=float)
    else:
        mz_payload = np.array([], dtype=float)
        corner_spread_arr = np.array([], dtype=float)

    cert_v = _series_from_list(flat_cert, "V", np.nan)
    cert_margin = _series_from_list(flat_cert, "contraction_margin", np.nan)
    cert_ok = np.asarray([1.0 if bool(d.get("certificate_ok", False)) else 0.0 for d in flat_cert], dtype=float)

    edges = {
        "comm_degradation_to_residual": _corr(comm_degrade, residual_step),
        "comm_degradation_to_confidence": _corr(comm_degrade, conf_step),
        "fault_deficit_to_confidence": _corr(fault_deficit, conf_step),
        "fault_deficit_to_redistribution": _corr(fault_deficit, redistributed_norm),
        "redistribution_to_payload_moment": _corr(redistributed_norm, mz_payload),
        "redistribution_to_corner_load_spread": _corr(redistributed_norm, corner_spread_arr),
        "certificate_margin_to_V": _corr(cert_margin, cert_v),
    }

    active_modes = sorted(
        {
            str(d.get("identified_mode", "nominal"))
            for d in flat_fdi
            if str(d.get("identified_mode", "nominal")) != "nominal"
        }
    )

    return {
        "counts": {
            "fdi_records": int(len(flat_fdi)),
            "switch_records": int(len(flat_switch)),
            "certificate_records": int(len(flat_cert)),
            "comm_records": int(len(comm)),
            "fault_records": int(len(fault)),
            "payload_force_records": int(len(payload)),
        },
        "event_steps": {
            "fault_first": fault_first,
            "detected_first": detected_first,
            "switch_first": switch_first,
            "fault_to_detection_steps": fault_to_detection_steps,
            "detection_to_switch_steps": detection_to_switch_steps,
            "fault_to_detection_time": None
            if fault_to_detection_steps is None
            else float(fault_to_detection_steps * dt),
            "detection_to_switch_time": None
            if detection_to_switch_steps is None
            else float(detection_to_switch_steps * dt),
        },
        "mode_counts": _mode_counts(flat_switch),
        "identified_non_nominal_modes": active_modes,
        "interaction_edges": edges,
        "certificate_by_mode": _certificate_by_mode(flat_cert),
        "summary_scalars": {
            "mean_comm_quality": float(np.nanmean(q_global)) if q_global.size else float("nan"),
            "min_comm_quality": float(np.nanmin(q_global)) if q_global.size else float("nan"),
            "mean_fdi_confidence": float(np.nanmean(conf_step)) if conf_step.size else float("nan"),
            "max_fault_deficit": float(np.nanmax(fault_deficit)) if fault_deficit.size else 0.0,
            "max_redistribution_norm": float(np.nanmax(redistributed_norm)) if redistributed_norm.size else 0.0,
            "max_payload_moment_abs": float(np.nanmax(mz_payload)) if mz_payload.size else float("nan"),
            "certificate_ok_ratio": float(np.nanmean(cert_ok)) if cert_ok.size else float("nan"),
        },
    }


def summarize_tf14_interactions_from_result(result: Mapping[str, Any]) -> Dict[str, Any]:
    return summarize_tf14_interactions(
        fdi_hist=result.get("tf14_fdi_diag_hist", []),
        switch_hist=result.get("tf14_switch_diag_hist", []),
        certificate_hist=result.get("tf14_certificate_hist", []),
        comm_diag_hist=result.get("comm_diag_hist", []),
        fault_diag_hist=result.get("fault_diag_hist", []),
        control_spread_hist=result.get("control_spread_hist", []),
        payload_force_hist=result.get("payload_force_hist", []),
        dt=_as_float(result.get("dt", result.get("case", {}).get("dt", 0.02)), 0.02),
    )
