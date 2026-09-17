"""Paired diagnostic of the current connector-state surrogate.

This does not add a new physical connector. It measures whether toggling the
existing compliance surrogate changes the closed-loop result and whether its
logged deformation proxy grows in higher-curvature portions of the route.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = PROJECT_ROOT / "tf14_remaining_experiments_20260509" / "run_tf14_remaining_experiments.py"
OUT_DIR = Path(__file__).resolve().parent / "connector_role_audit_seed3092"


def load_runner():
    spec = importlib.util.spec_from_file_location("connector_audit_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def scalar_summary(result):
    conn = result.get("connection_summary", {}) or {}
    force = result.get("payload_force_summary", {}) or {}
    metrics = result.get("team_metrics", {}) or {}
    # The canonical runner already computes reliable publication rows; retain
    # raw structures here and add curvature/deformation diagnostics below.
    force_hist = result.get("payload_force_hist", []) or []
    conn_hist = result.get("connection_diag_hist", []) or []
    n = min(len(force_hist), len(conn_hist))
    curvature = np.asarray([abs(float(force_hist[i].get("kappa", 0.0))) for i in range(n)])
    deform = np.asarray(
        [
            max(
                float(conn_hist[i].get("max_abs_ds", 0.0)),
                float(conn_hist[i].get("max_abs_dey", 0.0)),
                float(conn_hist[i].get("max_abs_dpsi", 0.0)),
            )
            for i in range(n)
        ]
    )
    if n and np.std(curvature) > 0 and np.std(deform) > 0:
        corr = float(np.corrcoef(curvature, deform)[0, 1])
    else:
        corr = None
    if n:
        q25, q75 = np.quantile(curvature, [0.25, 0.75])
        low = deform[curvature <= q25]
        high = deform[curvature >= q75]
        low_mean = float(np.mean(low)) if low.size else None
        high_mean = float(np.mean(high)) if high.size else None
    else:
        q25 = q75 = low_mean = high_mean = None
    return {
        "connection_summary": conn,
        "payload_force_summary": force,
        "team_metrics": metrics,
        "curvature_deformation": {
            "records": n,
            "abs_curvature_q25": None if q25 is None else float(q25),
            "abs_curvature_q75": None if q75 is None else float(q75),
            "low_curvature_deformation_mean": low_mean,
            "high_curvature_deformation_mean": high_mean,
            "pearson_abs_curvature_vs_max_deformation": corr,
        },
    }


def main():
    runner = load_runner()
    runner._configure_output_root(OUT_DIR)
    stage5 = runner._load_stage5_module()
    stage6 = runner._load_stage6_module()
    stage1 = stage5._load_stage1_module()
    stage2 = stage5._load_stage2_module()
    scenario = runner._scenario_plans(stage5, ["sine_mixed_fault_noise"])[0]

    output = {
        "purpose": "diagnose indirect closed-loop role of the existing connector-state surrogate",
        "seed": 3092,
        "scenario": scenario.key,
        "warning": "This is a one-seed diagnostic, not publication-level evidence.",
        "variants": {},
    }
    for key, enabled in (("connector_on", True), ("connector_off", False)):
        ns = stage5._bootstrap_env_for_path(stage1, scenario.path_mode)
        full = runner._final_method_plans(stage5, stage6, stage1, ns)["tf14_phase_role"]
        cfg = dict(full.updates)
        cfg["use_connection_compliance"] = enabled
        method = runner.MethodPlan(key, key, cfg)
        log_path = OUT_DIR / "logs" / f"{key}.log"
        result = runner._run_one(
            ns=ns,
            scenario=scenario,
            method=method,
            seed=3092,
            experiment="CONNECTOR_ROLE_AUDIT",
            log_path=log_path,
        )
        row = runner._summary_row(stage5, stage2, result, "CONNECTOR_ROLE_AUDIT", 3092, scenario, method, log_path)
        output["variants"][key] = {
            "publication_row": row,
            **scalar_summary(result),
        }

    on = output["variants"]["connector_on"]["publication_row"]
    off = output["variants"]["connector_off"]["publication_row"]
    fields = [
        "rmse_lat_mean",
        "rmse_long_mean",
        "connection_util_max",
        "force_norm_peak",
        "force_norm_rms",
        "full_path_reached",
    ]
    output["paired_difference_on_minus_off"] = {
        field: (
            float(on[field]) - float(off[field])
            if field in on and field in off and isinstance(on[field], (int, float)) and isinstance(off[field], (int, float))
            else None
        )
        for field in fields
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "connector_role_audit.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

