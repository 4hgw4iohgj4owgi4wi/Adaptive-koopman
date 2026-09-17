"""TF13 runtime wrapper.

TF13 focuses on fault-tolerant cooperative transport:
- one vehicle can have actuator degradation (steer / accel / both)
- remaining vehicles compensate through cooperative redistribution

Implementation reuses TF12 runtime with TF13-oriented defaults.
"""

from __future__ import annotations

from typing import Any, Dict

import tf12_runtime


generate_a1_dataset = tf12_runtime.generate_a1_dataset
build_a1_initial_states = tf12_runtime.build_a1_initial_states
build_a1_reference_bundle = tf12_runtime.build_a1_reference_bundle
_retune_rigid_team_parameters_a1 = tf12_runtime._retune_rigid_team_parameters_a1


def _merge_tf13_defaults(method_cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(method_cfg)
    out.setdefault("name", "tf13_fault_tolerant_main")
    out.setdefault("enable_fault_tolerant_control", True)
    out.setdefault("fault_vehicle_index", 1)
    out.setdefault("fault_mode", "both")
    # Mild + late fault defaults: keep fault-tolerance visible while preserving
    # feasibility on high-curvature right-angle hairpin tracking.
    out.setdefault("fault_start_step", 160)
    out.setdefault("fault_start_s", 18.0)
    out.setdefault("fault_ax_scale", 0.88)
    out.setdefault("fault_delta_scale", 0.90)
    out.setdefault("fault_tolerant_redistribution", True)
    out.setdefault("fault_comp_gain", 1.35)
    out.setdefault("fault_comp_delta_clip", 0.070)
    out.setdefault("fault_comp_ax_clip", 0.80)

    # Keep TF12 function set enabled and bias to stability under degradation.
    out.setdefault("use_connection_compliance", True)
    out.setdefault("use_team_stability_guard", True)
    out.setdefault("use_progress_supervisor", True)
    out.setdefault("use_comm_quality_consensus", True)
    out.setdefault("use_delay_compensation", True)
    out.setdefault("use_comm_constraint_tightening", False)
    out.setdefault("use_comm_degraded_fallback", True)
    out.setdefault("use_ppc", True)
    out.setdefault("use_dynamic_ppc", True)
    out.setdefault("use_adaptive_weight", True)
    out.setdefault("use_online_model_adaptation", True)
    out.setdefault("online_adaptation_mode", "bilinear_ridge")
    out.setdefault("completion_tol_s", 1.0)
    out.setdefault("max_extra_steps", 900)
    return out


def run_tf13_main(ctx: Dict[str, Any], payload_module, payload_cfg, change_mask):
    ctx_local = dict(ctx)
    method_cfg = dict(ctx_local.get("METHOD_CFG", {}))
    ctx_local["METHOD_CFG"] = _merge_tf13_defaults(method_cfg)
    return tf12_runtime.run_tf12_main(ctx_local, payload_module, payload_cfg, change_mask)


def run_tf12_main(ctx: Dict[str, Any], payload_module, payload_cfg, change_mask):
    """Compatibility alias so TF12-style notebook cells can run on TF13 runtime."""
    return run_tf13_main(ctx, payload_module, payload_cfg, change_mask)
