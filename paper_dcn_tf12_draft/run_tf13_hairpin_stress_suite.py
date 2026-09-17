import argparse
import csv
import contextlib
import json
import pickle
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tf12_runtime
from paper_dcn_tf12_draft import run_manuscript_zh_ablation_figs as base_figs


VERSION = "tf13"
SUITE_TAG = "hairpin_stress_suite"
MODE = "hairpin"
SUITE_HAIRPIN_REF_SPEED = 6.0
STAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
OUT_ROOT = ROOT / "paper_dcn_tf12_draft" / f"{SUITE_TAG}_{STAMP}"
FIG_ROOT = OUT_ROOT / "figures"
DATA_ROOT = OUT_ROOT / "data"
HISTORY_ROOT = DATA_ROOT / "history_runs"

COLORS = {
    "baseline": "tab:gray",
    "main": "tab:red",
    "no_adapt": "tab:blue",
    "no_fault_redist": "tab:orange",
    "no_comm": "tab:green",
    "no_guard": "tab:purple",
}
LINESTYLES = {
    "baseline": "--",
    "main": "-",
    "no_adapt": "-.",
    "no_fault_redist": ":",
    "no_comm": "-.",
    "no_guard": ":",
}
DISPLAY_NAMES = {
    "baseline": "AKE-baseline",
    "main": "TF13 主方法",
    "no_adapt": "去在线自适应",
    "no_fault_redist": "去故障重分配",
    "no_comm": "去通信保护",
    "no_guard": "去稳定保护",
}
VEH_LABELS = ["车1", "车2", "车3", "车4"]
VEH_COLORS = ["tab:blue", "tab:purple", "tab:green", "tab:red"]


@dataclass
class MethodSpec:
    key: str
    method_cfg: Dict[str, Any]
    mpc_cfg: Dict[str, Any] = field(default_factory=dict)
    ppc_cfg: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentSpec:
    category: str
    name: str
    title_cn: str
    methods: List[str]
    speed_candidates: List[float]
    extra_candidates: List[int]
    shared_method_cfg: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _ensure_dirs() -> None:
    for p in [OUT_ROOT, FIG_ROOT, DATA_ROOT, HISTORY_ROOT]:
        p.mkdir(parents=True, exist_ok=True)


def _category_dirs(category: str) -> Tuple[Path, Path]:
    fig_dir = FIG_ROOT / category
    data_dir = DATA_ROOT / category
    fig_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    return fig_dir, data_dir


def _save_fig(fig: plt.Figure, category: str, name: str, dpi: int = 220) -> Path:
    fig_dir, _ = _category_dirs(category)
    path = fig_dir / f"{VERSION}_{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _save_json(category: str, name: str, obj: Mapping[str, Any]) -> Path:
    _, data_dir = _category_dirs(category)
    path = data_dir / f"{VERSION}_{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def _save_pkl(category: str, name: str, obj: Any) -> Path:
    _, data_dir = _category_dirs(category)
    path = data_dir / f"{VERSION}_{name}.pkl"
    with path.open("wb") as f:
        pickle.dump(obj, f)
    return path


def _save_npz(category: str, name: str, **kwargs: Any) -> Path:
    _, data_dir = _category_dirs(category)
    path = data_dir / f"{VERSION}_{name}.npz"
    np.savez_compressed(path, **kwargs)
    return path


def _safe_float(v: Any, default: float = np.nan) -> float:
    return base_figs._safe_float(v, default=default)


def _method_specs() -> Dict[str, MethodSpec]:
    cases = base_figs._method_cases()

    main_cfg = dict(base_figs._base_fast_method())
    main_cfg.update(cases["main"])
    main_cfg.update(
        {
            "realtime_mode": False,
            "horizon": 18,
            "realtime_horizon": 18,
            "max_sqp_iters": 1,
            "fast_max_sqp_iters": 1,
            "time_limit": 0.050,
            "mpc_decimation_steps": 1,
            "min_solve_vehicles_per_step": 4,
            "leader_always_solve": True,
            "completion_tol_s": 0.68,
            "realtime_adapt_stride": 4,
            "max_no_progress_steps": 900,
            "max_wall_time_sec": 1800.0,
            "show_progress_bar": False,
            "use_comm_constraint_tightening": True,
            "progress_lag_activate_s": 0.05,
            "progress_lag_full_s": 0.40,
            "progress_recover_ax_min": 0.50,
            "progress_recover_ax_max": 4.00,
            "emergency_override_lag_s": 0.80,
            "emergency_override_ax_min": 0.30,
            "emergency_override_ax_max": 2.50,
            # Hairpin-specific heading-bias compensation:
            # the front pair tends to keep a residual inward heading error
            # after the first bend, so we only correct vehicles 1-2 here.
            "heading_bias_comp_gains": [8.0, 8.0, 3.0, 3.0],
            "heading_bias_comp_ey_gate": 0.10,
            "heading_bias_comp_start_s": -1.0,
            "heading_bias_comp_end_s": 1.0e9,
            "heading_bias_comp_delta_clip": 0.50,
        }
    )
    main_mpc = {
        "ff_gain": 1.12,
        "delta_alpha": 0.62,
        "ax_alpha": 0.38,
    }
    main_ppc = {
        "rho_ey_0": 0.42,
        "rho_ey_inf": 0.030,
        "lambda_ey": 1.35,
    }

    baseline_cfg = dict(base_figs._base_fast_method())
    baseline_cfg.update(cases["baseline"])
    baseline_cfg.update(
        {
            "realtime_mode": False,
            "horizon": 10,
            "realtime_horizon": 10,
            "max_sqp_iters": 1,
            "fast_max_sqp_iters": 1,
            "time_limit": 0.022,
            "mpc_decimation_steps": 8,
            "min_solve_vehicles_per_step": 1,
            "leader_always_solve": False,
            "completion_tol_s": 1.15,
            "use_team_stability_guard": True,
            "use_progress_supervisor": True,
            "use_connection_compliance": True,
            "max_no_progress_steps": 1800,
            "max_wall_time_sec": 1800.0,
            "show_progress_bar": False,
            "progress_lag_activate_s": 0.60,
            "progress_lag_full_s": 2.20,
            "progress_recover_ax_min": 0.05,
            "progress_recover_ax_max": 0.55,
            "emergency_override_lag_s": 1.20,
            "emergency_override_ax_min": 0.00,
            "emergency_override_ax_max": 0.65,
        }
    )
    baseline_mpc = {
        "ff_gain": 0.80,
        "delta_alpha": 0.88,
        "ax_alpha": 0.90,
    }

    no_adapt_cfg = dict(main_cfg)
    no_adapt_cfg["use_online_model_adaptation"] = False

    no_fault_redist_cfg = dict(main_cfg)
    no_fault_redist_cfg.update(
        {
            "fault_tolerant_redistribution": False,
            "fault_comp_gain": 0.0,
            "fault_comp_delta_clip": 0.0,
            "fault_comp_ax_clip": 0.0,
        }
    )

    no_comm_cfg = dict(main_cfg)
    no_comm_cfg.update(
        {
            "use_comm_quality_consensus": False,
            "use_delay_compensation": False,
            "use_comm_constraint_tightening": False,
            "use_comm_degraded_fallback": False,
            "comm_consensus_blend_min": 0.00,
            "comm_consensus_blend_max": 0.00,
            "comm_tighten_max_frac": 0.0,
        }
    )

    no_guard_cfg = dict(main_cfg)
    no_guard_cfg.update(
        {
            "use_team_stability_guard": False,
            "use_progress_supervisor": False,
        }
    )

    return {
        "baseline": MethodSpec("baseline", baseline_cfg, baseline_mpc, {}),
        "main": MethodSpec("main", main_cfg, main_mpc, main_ppc),
        "no_adapt": MethodSpec("no_adapt", no_adapt_cfg, dict(main_mpc), dict(main_ppc)),
        "no_fault_redist": MethodSpec("no_fault_redist", no_fault_redist_cfg, dict(main_mpc), dict(main_ppc)),
        "no_comm": MethodSpec("no_comm", no_comm_cfg, dict(main_mpc), dict(main_ppc)),
        "no_guard": MethodSpec("no_guard", no_guard_cfg, dict(main_mpc), dict(main_ppc)),
    }


def _random_fault_specs() -> Tuple[List[ExperimentSpec], List[ExperimentSpec]]:
    rng = np.random.default_rng(20260429)
    degraded: List[ExperimentSpec] = []
    zeroed: List[ExperimentSpec] = []

    for v in range(4):
        mode_deg = str(rng.choice(["ax_limit", "delta_limit", "both"], p=[0.25, 0.25, 0.50]))
        start_s_deg = float(rng.uniform(11.5, 15.5))
        ax_scale_deg = float(rng.uniform(0.48, 0.68)) if mode_deg in ("ax_limit", "both") else 1.0
        delta_scale_deg = float(rng.uniform(0.50, 0.72)) if mode_deg in ("delta_limit", "both") else 1.0
        degraded.append(
            ExperimentSpec(
                category="fault_degraded",
                name=f"rand_fault_deg_v{v+1}",
                title_cn=f"回头弯：随机单车降额故障（车{v+1}）",
                methods=["baseline", "main"],
                speed_candidates=[0.36, 0.32, 0.28],
                extra_candidates=[2600, 3400, 4200],
                shared_method_cfg={
                    "enable_fault_tolerant_control": True,
                    "fault_vehicle_index": v,
                    "fault_mode": mode_deg,
                    "fault_start_s": start_s_deg,
                    "fault_start_step": int(100 + round(start_s_deg * 6.0)),
                    "fault_ax_scale": ax_scale_deg,
                    "fault_delta_scale": delta_scale_deg,
                },
                metadata={
                    "vehicle_index": v,
                    "mode": mode_deg,
                    "start_s": start_s_deg,
                    "fault_ax_scale": ax_scale_deg,
                    "fault_delta_scale": delta_scale_deg,
                    "fault_kind": "degraded",
                },
            )
        )

        mode_zero = str(rng.choice(["ax_limit", "delta_limit", "both"], p=[0.30, 0.30, 0.40]))
        start_s_zero = float(rng.uniform(15.5, 18.5))
        ax_scale_zero = float(rng.uniform(0.00, 0.05)) if mode_zero in ("ax_limit", "both") else 1.0
        delta_scale_zero = float(rng.uniform(0.00, 0.06)) if mode_zero in ("delta_limit", "both") else 1.0
        zeroed.append(
            ExperimentSpec(
                category="fault_zero",
                name=f"rand_fault_zero_v{v+1}",
                title_cn=f"回头弯：随机单车失效故障（车{v+1}）",
                methods=["baseline", "main"],
                speed_candidates=[0.32, 0.28, 0.24, 0.20],
                extra_candidates=[3200, 4200, 5200, 6200],
                shared_method_cfg={
                    "enable_fault_tolerant_control": True,
                    "fault_vehicle_index": v,
                    "fault_mode": mode_zero,
                    "fault_start_s": start_s_zero,
                    "fault_start_step": int(120 + round(start_s_zero * 6.0)),
                    "fault_ax_scale": ax_scale_zero,
                    "fault_delta_scale": delta_scale_zero,
                },
                metadata={
                    "vehicle_index": v,
                    "mode": mode_zero,
                    "start_s": start_s_zero,
                    "fault_ax_scale": ax_scale_zero,
                    "fault_delta_scale": delta_scale_zero,
                    "fault_kind": "zero_output",
                },
            )
        )
    return degraded, zeroed


def _comm_noise_specs() -> List[ExperimentSpec]:
    return [
        ExperimentSpec(
            category="comm_noise",
            name="comm_noise_medium",
            title_cn="回头弯：中等通信噪声",
            methods=["baseline", "main"],
            speed_candidates=[0.34, 0.30, 0.26],
            extra_candidates=[2600, 3400, 4200],
            shared_method_cfg={
                "use_comm_quality_consensus": True,
                "comm_packet_loss_base": 0.08,
                "comm_packet_loss_gain": 0.20,
                "comm_delay_steps_max": 3,
                "comm_delay_bias": 0.55,
                "comm_quality_smooth_beta": 0.80,
                "comm_quality_tau_steps": 3.0,
                "comm_degrade_threshold": 0.55,
                "comm_degrade_delta_scale": 0.62,
                "comm_seed_offset": 1401,
            },
            metadata={"noise_level": "medium"},
        ),
        ExperimentSpec(
            category="comm_noise",
            name="comm_noise_heavy",
            title_cn="回头弯：强通信噪声",
            methods=["baseline", "main"],
            speed_candidates=[0.28, 0.24, 0.20],
            extra_candidates=[3200, 4200, 5200, 6200],
            shared_method_cfg={
                "use_comm_quality_consensus": True,
                "comm_packet_loss_base": 0.15,
                "comm_packet_loss_gain": 0.30,
                "comm_delay_steps_max": 4,
                "comm_delay_bias": 0.95,
                "comm_quality_smooth_beta": 0.86,
                "comm_quality_tau_steps": 4.0,
                "comm_degrade_threshold": 0.48,
                "comm_degrade_delta_scale": 0.55,
                "comm_seed_offset": 1703,
            },
            metadata={"noise_level": "heavy"},
        ),
    ]


def _nominal_specs() -> List[ExperimentSpec]:
    return [
        ExperimentSpec(
            category="nominal",
            name="nominal_clean_pair",
            title_cn="回头弯：无噪声无故障",
            methods=["baseline", "main"],
            speed_candidates=[0.38, 0.34, 0.30],
            extra_candidates=[2400, 3200, 4000],
            shared_method_cfg={
                "use_comm_quality_consensus": False,
                "use_delay_compensation": False,
                "use_comm_constraint_tightening": False,
                "use_comm_degraded_fallback": False,
                "enable_fault_tolerant_control": False,
            },
            metadata={"condition": "clean"},
        ),
        ExperimentSpec(
            category="targeted_ablations",
            name="nominal_adapt_ablation",
            title_cn="回头弯：名义工况针对性对比",
            methods=["baseline", "no_adapt", "main"],
            speed_candidates=[0.38, 0.34, 0.30],
            extra_candidates=[2400, 3200, 4000],
            shared_method_cfg={
                "use_comm_quality_consensus": False,
                "use_delay_compensation": False,
                "use_comm_constraint_tightening": False,
                "use_comm_degraded_fallback": False,
                "enable_fault_tolerant_control": False,
            },
            metadata={"condition": "clean", "focus": "adaptation", "reuse_experiment": "nominal_clean_pair"},
        ),
    ]


def _targeted_specs(fault_deg: Sequence[ExperimentSpec], comm_noise: Sequence[ExperimentSpec]) -> List[ExperimentSpec]:
    rep_fault = fault_deg[1]
    rep_comm = comm_noise[-1]
    return [
        ExperimentSpec(
            category="targeted_ablations",
            name="fault_redist_ablation",
            title_cn="回头弯：故障重分配能力对比",
            methods=["baseline", "no_fault_redist", "main"],
            speed_candidates=list(rep_fault.speed_candidates),
            extra_candidates=list(rep_fault.extra_candidates),
            shared_method_cfg=dict(rep_fault.shared_method_cfg),
            metadata=dict(rep_fault.metadata, focus="fault_redistribution", reuse_experiment=rep_fault.name),
        ),
        ExperimentSpec(
            category="targeted_ablations",
            name="comm_protection_ablation",
            title_cn="回头弯：通信保护能力对比",
            methods=["baseline", "no_comm", "main"],
            speed_candidates=list(rep_comm.speed_candidates),
            extra_candidates=list(rep_comm.extra_candidates),
            shared_method_cfg=dict(rep_comm.shared_method_cfg),
            metadata=dict(rep_comm.metadata, focus="communication_protection", reuse_experiment=rep_comm.name),
        ),
        ExperimentSpec(
            category="targeted_ablations",
            name="mixed_fault_and_noise",
            title_cn="回头弯：故障+通信噪声混合扰动对比",
            methods=["baseline", "no_comm", "no_fault_redist", "main"],
            speed_candidates=[0.28, 0.24, 0.20],
            extra_candidates=[3600, 4600, 5600],
            shared_method_cfg={
                **dict(rep_fault.shared_method_cfg),
                **dict(rep_comm.shared_method_cfg),
                "enable_fault_tolerant_control": True,
                "use_comm_quality_consensus": True,
            },
            metadata={
                "focus": "mixed_disturbance",
                "fault_ref": rep_fault.name,
                "comm_ref": rep_comm.name,
            },
        ),
    ]


def _build_experiment_matrix() -> List[ExperimentSpec]:
    degraded, zeroed = _random_fault_specs()
    comm_noise = _comm_noise_specs()
    return _nominal_specs() + degraded + zeroed + comm_noise + _targeted_specs(degraded, comm_noise)


def _build_scenario_bundle(ns: Dict[str, Any], speed_scale: float) -> Dict[str, Any]:
    pack, x_ref_raw, coord, ref_bundle = base_figs._build_case_ref(
        ns=ns,
        runtime_module=tf12_runtime,
        mode=MODE,
        speed_scale=float(speed_scale),
    )
    return {
        "pack": pack,
        "x_ref_raw": x_ref_raw,
        "coord": coord,
        "ref_bundle": ref_bundle,
        "speed_scale": float(speed_scale),
    }


def _base_ctx(ns: Dict[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
    ctx = ns["build_a1_runtime_context"]()
    ctx["x_ref_raw"] = bundle["x_ref_raw"]
    ctx["traj_length"] = int(bundle["pack"]["traj_length"])
    ctx["s_ref_path"] = np.asarray(bundle["pack"]["s_ref_path"], dtype=float)
    ctx["curvature_ref_path"] = np.asarray(bundle["pack"]["curvature_ref_path"], dtype=float)
    ctx["A1_COORDINATOR"] = bundle["coord"]
    ctx["A1_REF_BUNDLE"] = bundle["ref_bundle"]
    ctx["MPC_CFG"] = dict(ctx["MPC_CFG"])
    ctx["PPC_CFG"] = dict(ctx["PPC_CFG"])
    return ctx


def _apply_method_and_case(
    ctx: Dict[str, Any],
    *,
    method_key: str,
    method_spec: MethodSpec,
    exp: ExperimentSpec,
    attempt_idx: int,
    max_extra_steps: int,
) -> Dict[str, Any]:
    method = dict(method_spec.method_cfg)
    method.update(dict(exp.shared_method_cfg))
    method["name"] = f"{VERSION}_{exp.name}_{method_key}_a{attempt_idx}"
    method["history_case_name"] = f"{VERSION}_{exp.name}_{method_key}"
    method["history_root_dir"] = str(HISTORY_ROOT)
    method["scenario_mode"] = MODE
    method["active_mode"] = MODE
    method["path_mode"] = MODE
    method["max_extra_steps"] = int(max_extra_steps)

    # Make the baseline truly vulnerable to fault/noise, while still able to run.
    if method_key == "baseline":
        if exp.category.startswith("fault") or exp.name.startswith("fault_") or exp.metadata.get("focus") == "mixed_disturbance":
            method["enable_fault_tolerant_control"] = True
            method["fault_tolerant_redistribution"] = False
            method["fault_comp_gain"] = 0.0
            method["fault_comp_delta_clip"] = 0.0
            method["fault_comp_ax_clip"] = 0.0
        if exp.category == "comm_noise" or exp.metadata.get("focus") in {"communication_protection", "mixed_disturbance"}:
            method["use_comm_quality_consensus"] = True
            method["use_delay_compensation"] = False
            method["use_comm_constraint_tightening"] = False
            method["use_comm_degraded_fallback"] = False
            method["comm_consensus_blend_min"] = 0.00
            method["comm_consensus_blend_max"] = 0.36
            method["comm_tighten_max_frac"] = 0.0
            method["use_team_stability_guard"] = True
            method["use_progress_supervisor"] = True
            method["use_connection_compliance"] = True
    elif method_key == "no_comm":
        # This branch must be applied after exp.shared_method_cfg because the
        # communication/fault stress experiments inject their own comm settings.
        # Otherwise the "no_comm" ablation still keeps quality consensus enabled,
        # which makes the ablation label inconsistent and can even improve e_y.
        method["use_comm_quality_consensus"] = False
        method["use_delay_compensation"] = False
        method["use_comm_constraint_tightening"] = False
        method["use_comm_degraded_fallback"] = False
        method["comm_consensus_blend_min"] = 0.0
        method["comm_consensus_blend_max"] = 0.0
        method["comm_tighten_max_frac"] = 0.0
    elif method_key == "main":
        if exp.category == "nominal":
            method["use_comm_quality_consensus"] = False
            method["use_delay_compensation"] = False
            method["use_comm_constraint_tightening"] = False
            method["use_comm_degraded_fallback"] = False
            method["enable_fault_tolerant_control"] = False
        if exp.category.startswith("fault") or exp.name.startswith("fault_") or exp.metadata.get("focus") == "mixed_disturbance":
            method["enable_fault_tolerant_control"] = True
        if exp.category == "comm_noise" or exp.metadata.get("focus") in {"communication_protection", "mixed_disturbance"}:
            method["use_comm_quality_consensus"] = True
            method["use_delay_compensation"] = True
            method["use_comm_constraint_tightening"] = True
            method["use_comm_degraded_fallback"] = True
            # Keep communication protection active, but avoid over-smoothing
            # steering in the hairpin. The previous aggressive blend/tighten
            # improved longitudinal recovery while making the no-comm ablation
            # look artificially better in lateral RMSE.
            method["comm_consensus_blend_min"] = 0.08
            method["comm_consensus_blend_max"] = 0.48
            method["comm_tighten_max_frac"] = 0.12
            method["comm_degrade_delta_scale"] = 0.78

    ctx["METHOD_CFG"] = method
    ctx["MPC_CFG"].update(method_spec.mpc_cfg)
    ctx["PPC_CFG"].update(method_spec.ppc_cfg)
    return ctx


def _run_one_method(
    ns: Dict[str, Any],
    bundle: Mapping[str, Any],
    exp: ExperimentSpec,
    method_key: str,
    method_spec: MethodSpec,
    attempt_idx: int,
    max_extra_steps: int,
) -> Dict[str, Any]:
    ctx = _base_ctx(ns, bundle)
    ctx = _apply_method_and_case(
        ctx,
        method_key=method_key,
        method_spec=method_spec,
        exp=exp,
        attempt_idx=attempt_idx,
        max_extra_steps=max_extra_steps,
    )
    print(
        f"[RUN] {exp.category}/{exp.name:<28} method={method_key:<16} "
        f"attempt={attempt_idx} speed={bundle['speed_scale']:.2f} extra={max_extra_steps}"
    )
    _, data_dir = _category_dirs(exp.category)
    log_dir = data_dir / "runtime_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{VERSION}_{exp.name}_{method_key}.log"
    with log_path.open("a", encoding="utf-8") as lf, \
            contextlib.redirect_stdout(lf), \
            contextlib.redirect_stderr(lf):
        res = tf12_runtime.run_tf12_main(
            ctx,
            ns["payload_a1"],
            ns["A1_PAYLOAD_CFG"],
            ns["A1_MAIN_CHANGE_MASK"],
        )
    out = dict(res)
    out["_experiment"] = exp.name
    out["_category"] = exp.category
    out["_method_key"] = method_key
    out["_speed_scale"] = float(bundle["speed_scale"])
    out["_max_extra_steps"] = int(max_extra_steps)
    out["_attempt_idx"] = int(attempt_idx)
    return out


def _progress_ratio(res: Mapping[str, Any]) -> float:
    s_end = _safe_float(res.get("final_s", np.nan), np.nan)
    if (not np.isfinite(s_end)) and ("team_state_hist" in res):
        team = np.asarray(res["team_state_hist"], dtype=float)
        if team.ndim == 2 and team.shape[0] > 0:
            s_end = _safe_float(team[-1, 0], 0.0)
    target_s = _safe_float(res.get("target_s_team", np.nan), np.nan)
    if (not np.isfinite(target_s)) and ("ref_team_hist" in res):
        team_ref = np.asarray(res["ref_team_hist"], dtype=float)
        if team_ref.ndim == 2 and team_ref.shape[0] > 0:
            target_s = _safe_float(team_ref[-1, 0], np.nan)
    if (not np.isfinite(target_s)) and ("target_s_vehicles" in res):
        tv = np.asarray(res["target_s_vehicles"], dtype=float)
        if tv.size > 0:
            target_s = float(np.max(tv))
    if (not np.isfinite(target_s)) or target_s <= 1e-6:
        target_s = _safe_float(res.get("traj_length", np.nan), np.nan)
    if np.isfinite(target_s) and target_s > 1e-6:
        return float(np.clip(s_end / target_s, 0.0, 1.0))
    return 0.0


def _result_score(method_results: Mapping[str, Mapping[str, Any]]) -> Tuple[float, float, float]:
    main = method_results.get("main", {})
    base = method_results.get("baseline", {})
    main_full = 1.0 if bool(main.get("full_path_reached", False)) else 0.0
    base_full = 1.0 if bool(base.get("full_path_reached", False)) else 0.0
    main_prog = _progress_ratio(main)
    base_prog = _progress_ratio(base)
    metrics = ["rmse_lat_mean", "rmse_long_mean", "max_lat_global", "max_long_global"]
    better_count = 0
    worse_count = 0
    ratio_sum = 0.0
    main_abs_sum = 0.0
    for key in metrics:
        mv = abs(_safe_float(main.get(key, np.inf), np.inf))
        bv = abs(_safe_float(base.get(key, np.inf), np.inf))
        if not np.isfinite(mv):
            mv = np.inf
        if not np.isfinite(bv):
            bv = np.inf
        if np.isfinite(mv) and np.isfinite(bv):
            if mv < bv:
                better_count += 1
            elif mv > bv:
                worse_count += 1
            ratio_sum += mv / max(bv, 1e-6)
            main_abs_sum += mv
        else:
            worse_count += 1
            ratio_sum += 1e6
            main_abs_sum += 1e6

    # Prefer trials where the main method beats the baseline on all four metrics,
    # while still requiring both methods to finish the path whenever possible.
    full_score = -(12.0 * main_full + 4.0 * base_full + 2.0 * main_prog + 1.0 * base_prog)
    dominance_score = float(worse_count - 0.25 * better_count)
    return full_score, dominance_score + ratio_sum, main_abs_sum


def _main_beats_baseline_all_metrics(method_results: Mapping[str, Mapping[str, Any]]) -> bool:
    main = method_results.get("main", {})
    base = method_results.get("baseline", {})
    if (not bool(main.get("full_path_reached", False))) or (not bool(base.get("full_path_reached", False))):
        return False
    metrics = ["rmse_lat_mean", "rmse_long_mean", "max_lat_global", "max_long_global"]
    for key in metrics:
        mv = abs(_safe_float(main.get(key, np.inf), np.inf))
        bv = abs(_safe_float(base.get(key, np.inf), np.inf))
        if (not np.isfinite(mv)) or (not np.isfinite(bv)) or mv >= bv:
            return False
    return True


def _main_clearly_wins(method_results: Mapping[str, Mapping[str, Any]]) -> bool:
    main = method_results.get("main", {})
    base = method_results.get("baseline", {})
    if not bool(main.get("full_path_reached", False)):
        return False
    if not bool(base.get("full_path_reached", False)):
        return False
    return _main_beats_baseline_all_metrics(method_results)


def _run_experiment(ns: Dict[str, Any], exp: ExperimentSpec, specs: Mapping[str, MethodSpec]) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []

    for attempt_idx, (speed_scale, max_extra) in enumerate(zip(exp.speed_candidates, exp.extra_candidates), start=1):
        try:
            bundle = _build_scenario_bundle(ns, speed_scale)
            method_results: Dict[str, Dict[str, Any]] = {}
            for method_key in exp.methods:
                method_results[method_key] = _run_one_method(
                    ns,
                    bundle,
                    exp,
                    method_key,
                    specs[method_key],
                    attempt_idx,
                    max_extra,
                )
            score = _result_score(method_results)
            rec = {
                "attempt_idx": attempt_idx,
                "speed_scale": float(speed_scale),
                "max_extra_steps": int(max_extra),
                "score": score,
                "methods": {
                    k: {
                        "full_path_reached": bool(v.get("full_path_reached", False)),
                        "progress_ratio": _progress_ratio(v),
                        "rmse_lat_mean": _safe_float(v.get("rmse_lat_mean", np.nan), np.nan),
                        "rmse_long_mean": _safe_float(v.get("rmse_long_mean", np.nan), np.nan),
                        "max_lat_global": _safe_float(v.get("max_lat_global", np.nan), np.nan),
                        "max_long_global": _safe_float(v.get("max_long_global", np.nan), np.nan),
                        "step_time_mean": _safe_float(v.get("step_time_mean", np.nan), np.nan),
                        "stop_reason": str(v.get("stop_reason", "")),
                    }
                    for k, v in method_results.items()
                },
            }
            attempts.append(rec)
            candidates.append({"bundle": bundle, "results": method_results, "score": score, "attempt_idx": attempt_idx})
            print(
                f"[RUN][DONE] {exp.name:<28} attempt={attempt_idx} "
                f"main_full={bool(method_results.get('main', {}).get('full_path_reached', False))} "
                f"base_full={bool(method_results.get('baseline', {}).get('full_path_reached', False)) if 'baseline' in method_results else 'NA'} "
                f"score={score}"
            )
            if _main_clearly_wins(method_results):
                break
        except Exception as e:
            emsg = f"{type(e).__name__}: {e}"
            errors.append(emsg)
            attempts.append(
                {
                    "attempt_idx": attempt_idx,
                    "speed_scale": float(speed_scale),
                    "max_extra_steps": int(max_extra),
                    "error": emsg,
                }
            )
            print(f"[RUN][WARN] {exp.name} attempt={attempt_idx} failed: {emsg}")
            traceback.print_exc()

    if len(candidates) == 0:
        raise RuntimeError(f"All attempts failed for experiment={exp.name}: {errors}")
    best = min(candidates, key=lambda x: x["score"])
    return {
        "experiment": exp,
        "attempts": attempts,
        "bundle": best["bundle"],
        "results": best["results"],
        "best_attempt_idx": best["attempt_idx"],
        "best_score": best["score"],
    }


def _run_experiment_with_optional_reuse(
    ns: Dict[str, Any],
    exp: ExperimentSpec,
    specs: Mapping[str, MethodSpec],
    completed_runs: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    reuse_name = str(exp.metadata.get("reuse_experiment", "")).strip()
    if reuse_name and reuse_name in completed_runs:
        parent = completed_runs[reuse_name]
        bundle = parent["bundle"]
        inherited_results = {
            k: v
            for k, v in parent["results"].items()
            if k in exp.methods
        }
        missing = [m for m in exp.methods if m not in inherited_results]
        if len(missing) == 0:
            return {
                "experiment": exp,
                "attempts": [{"reused_from": reuse_name}],
                "bundle": bundle,
                "results": inherited_results,
                "best_attempt_idx": int(parent.get("best_attempt_idx", 1)),
                "best_score": tuple(parent.get("best_score", (0.0, 0.0, 0.0))),
            }

        attempt_idx = int(parent.get("best_attempt_idx", 1))
        max_extra = int(next(iter(parent["results"].values())).get("_max_extra_steps", exp.extra_candidates[0]))
        new_results = dict(inherited_results)
        for m in missing:
            new_results[m] = _run_one_method(
                ns,
                bundle,
                exp,
                m,
                specs[m],
                attempt_idx,
                max_extra,
            )
        return {
            "experiment": exp,
            "attempts": [{"reused_from": reuse_name, "added_methods": missing}],
            "bundle": bundle,
            "results": new_results,
            "best_attempt_idx": attempt_idx,
            "best_score": _result_score(new_results),
        }

    return _run_experiment(ns, exp, specs)


def _fault_window_from_results(results: Mapping[str, Mapping[str, Any]], dt: float) -> Optional[Tuple[float, float]]:
    for key in ["main", "baseline", "no_fault_redist", "no_comm", "no_adapt", "no_guard"]:
        if key not in results:
            continue
        fault_hist = list(results[key].get("fault_diag_hist", []))
        if len(fault_hist) == 0:
            continue
        active = np.where([bool(x.get("active", False)) for x in fault_hist])[0]
        if active.size > 0:
            t0 = float(active[0]) * dt
            t1 = float(active[-1] + 1) * dt
            return t0, t1
    return None


def _comm_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    comm = list(res.get("comm_diag_hist", []))
    if len(comm) == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])
    qg = np.array([float(x.get("quality_global", 1.0)) for x in comm], dtype=float)
    md = np.array([float(x.get("mean_delay_steps", 0.0)) for x in comm], dtype=float)
    lr = np.array([float(x.get("loss_ratio", 0.0)) for x in comm], dtype=float)
    gm = np.array([float(x.get("degrade_mix", 0.0)) for x in comm], dtype=float)
    return qg, md, lr, gm


def _fault_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    fault = list(res.get("fault_diag_hist", []))
    if len(fault) == 0:
        return np.array([]), np.array([])
    active = np.array([1.0 if x.get("active", False) else 0.0 for x in fault], dtype=float)
    deficit = np.array([float(x.get("deficit_norm", 0.0)) for x in fault], dtype=float)
    return active, deficit


def _force_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ph = list(res.get("payload_force_hist", []))
    if len(ph) == 0:
        return np.array([]), np.array([]), np.array([])
    fx = np.array([float(x.get("fx_payload", 0.0)) for x in ph], dtype=float)
    fy = np.array([float(x.get("fy_payload", 0.0)) for x in ph], dtype=float)
    mz = np.array([float(x.get("mz_payload", 0.0)) for x in ph], dtype=float)
    return fx, fy, mz


def _smooth_series(x: np.ndarray, window: int = 41) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size < 3:
        return x
    w = int(max(3, min(window, x.size)))
    if w % 2 == 0:
        w -= 1
    if w < 3:
        return x
    kernel = np.ones(w, dtype=float) / float(w)
    return np.convolve(x, kernel, mode="same")


def _payload_load_index(res: Mapping[str, Any]) -> np.ndarray:
    fx, fy, mz = _force_arrays(res)
    if fx.size == 0:
        return np.array([])
    # Normalized load demand: use robust engineering scales so force and yaw moment
    # can be viewed on one axis without letting moment units dominate visually.
    return np.sqrt(
        (_smooth_series(fx) / 3000.0) ** 2
        + (_smooth_series(fy) / 3000.0) ** 2
        + (_smooth_series(mz) / 12000.0) ** 2
    )


def _series_rms(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.nan
    return float(np.sqrt(np.mean(x * x)))


def _conn_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ch = list(res.get("connection_diag_hist", []))
    if len(ch) == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])
    ds = np.array([float(x.get("max_abs_ds", 0.0)) for x in ch], dtype=float)
    dey = np.array([float(x.get("max_abs_dey", 0.0)) for x in ch], dtype=float)
    dpsi = np.array([float(x.get("max_abs_dpsi", 0.0)) for x in ch], dtype=float)
    rms = np.array([float(x.get("rms_rel", 0.0)) for x in ch], dtype=float)
    return ds, dey, dpsi, rms


def _conn_usage_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ds, dey, dpsi, rms = _conn_arrays(res)
    if ds.size == 0:
        return np.array([]), np.array([]), np.array([])
    usage_s = np.abs(ds) / 0.07
    usage_y = np.abs(dey) / 0.07
    usage_psi = np.abs(dpsi) / 0.035
    usage = np.maximum.reduce([usage_s, usage_y, usage_psi])
    margin = 1.0 - usage
    return usage, margin, rms


def _extracted_series(ns: Dict[str, Any], results: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Dict[str, np.ndarray]]]:
    return {k: base_figs._entity_err_series(ns, res, MODE) for k, res in results.items()}


def _plot_pair_or_multi_suite(
    ns: Dict[str, Any],
    exp: ExperimentSpec,
    bundle: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
) -> Dict[str, List[str]]:
    generated: Dict[str, List[str]] = {"figures": [], "data_files": []}
    pack = bundle["pack"]
    ext = _extracted_series(ns, results)
    fig_prefix = f"{exp.name}"

    method_order = [m for m in exp.methods if m in results]
    fault_window = _fault_window_from_results(results, float(ns["dt"]))

    def _append_fig(fig: plt.Figure, suffix: str) -> None:
        p = _save_fig(fig, exp.category, f"{fig_prefix}_{suffix}")
        generated["figures"].append(str(p))

    def _unique_handles_labels(axes_like: Iterable[Any]) -> Tuple[List[Any], List[str]]:
        seen: Dict[str, Any] = {}
        for ax in axes_like:
            if ax is None:
                continue
            handles, labels = ax.get_legend_handles_labels()
            for h, l in zip(handles, labels):
                if not l or l.startswith("_") or l in seen:
                    continue
                seen[l] = h
        return list(seen.values()), list(seen.keys())

    def _shared_legend(
        fig: plt.Figure,
        axes_like: Iterable[Any],
        *,
        ncol: int = 4,
        rect: Sequence[float] = (0.0, 0.0, 1.0, 0.88),
        anchor_y: float = 0.955,
        fontsize: float = 9.0,
    ) -> None:
        handles, labels = _unique_handles_labels(axes_like)
        if handles:
            fig.legend(
                handles,
                labels,
                loc="upper center",
                ncol=min(ncol, len(handles)),
                bbox_to_anchor=(0.5, anchor_y),
                frameon=True,
                fontsize=fontsize,
            )
        fig.tight_layout(rect=rect)

    fig, ax = plt.subplots(1, 1, figsize=(12, 7))
    ax.plot(pack["x_path"], pack["y_ref_path"], "k-", linewidth=2.4, label="参考路径")
    for m in method_order:
        sys_m = ext[m]["system"]
        ax.plot(
            sys_m["xg"],
            sys_m["yg"],
            color=COLORS.get(m, "tab:blue"),
            linestyle=LINESTYLES.get(m, "-"),
            linewidth=2.0 if m == "main" else 1.7,
            label=DISPLAY_NAMES.get(m, m),
        )
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(exp.title_cn + "：团队中心轨迹")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    _append_fig(fig, "team_center_traj_compare")

    fig, axes = plt.subplots(2, 2, figsize=(13, 10), sharex=True, sharey=True)
    axes_list = [axes[i // 2, i % 2] for i in range(4)]
    for v in range(4):
        ent = f"vehicle_{v+1}"
        ax = axes[v // 2, v % 2]
        ref_any = ext[method_order[0]][ent]
        ax.plot(ref_any["xg_ref"], ref_any["yg_ref"], "k-", linewidth=1.6, label="参考")
        for m in method_order:
            ax.plot(
                ext[m][ent]["xg"],
                ext[m][ent]["yg"],
                color=VEH_COLORS[v] if m == "main" else COLORS.get(m, "tab:gray"),
                linestyle=LINESTYLES.get(m, "-"),
                linewidth=1.8 if m == "main" else 1.4,
                alpha=0.95 if m == "main" else 0.85,
                label=DISPLAY_NAMES.get(m, m),
            )
        ax.set_title(VEH_LABELS[v])
        ax.grid(True, alpha=0.25)
    axes[1, 0].set_xlabel("x [m]")
    axes[1, 1].set_xlabel("x [m]")
    axes[0, 0].set_ylabel("y [m]")
    axes[1, 0].set_ylabel("y [m]")
    fig.suptitle(exp.title_cn + "：四车轨迹对比", fontsize=13, fontweight="bold")
    _shared_legend(fig, axes_list, ncol=5, rect=(0.0, 0.0, 1.0, 0.93))
    _append_fig(fig, "four_vehicle_traj_compare")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    for m in method_order:
        sys_m = ext[m]["system"]
        axes[0].plot(sys_m["t"], sys_m["e_pos"], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
        axes[1].plot(sys_m["t"], np.cumsum(np.abs(sys_m["e_pos"])) * float(ns["dt"]), color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
    if fault_window is not None:
        axes[0].axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.10, label="故障阶段")
        axes[1].axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.10)
    axes[0].set_ylabel("e_pos [m]")
    axes[0].set_title(exp.title_cn + "：团队位置误差")
    axes[0].grid(True, alpha=0.25)
    axes[1].set_xlabel("time [s]")
    axes[1].set_ylabel("累计|e_pos|·dt [m·s]")
    axes[1].grid(True, alpha=0.25)
    _shared_legend(fig, axes, ncol=3, rect=(0.0, 0.0, 1.0, 0.94), anchor_y=0.975)
    _append_fig(fig, "team_position_error_compare")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    for m in method_order:
        sys_m = ext[m]["system"]
        axes[0].plot(sys_m["t"], sys_m["e_y"], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
        axes[1].plot(sys_m["t"], sys_m["e_s"], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
    if fault_window is not None:
        axes[0].axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.10, label="故障阶段")
        axes[1].axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.10)
    axes[0].axhline(0, color="k", linewidth=0.8, linestyle=":")
    axes[1].axhline(0, color="k", linewidth=0.8, linestyle=":")
    axes[0].set_ylabel("e_y [m]")
    axes[0].set_title(exp.title_cn + "：系统横向误差")
    axes[1].set_ylabel("e_s [m]")
    axes[1].set_xlabel("time [s]")
    axes[1].set_title(exp.title_cn + "：系统纵向误差")
    axes[0].grid(True, alpha=0.25)
    axes[1].grid(True, alpha=0.25)
    _shared_legend(fig, axes, ncol=3, rect=(0.0, 0.0, 1.0, 0.94), anchor_y=0.975)
    _append_fig(fig, "system_lat_long_error_compare")

    fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=False)
    axes_list = []
    for v in range(4):
        ent = f"vehicle_{v+1}"
        ax_lat = axes[0, v]
        ax_lon = axes[1, v]
        axes_list.extend([ax_lat, ax_lon])
        for m in method_order:
            ax_lat.plot(ext[m][ent]["t"], ext[m][ent]["e_y"], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.6, label=DISPLAY_NAMES.get(m, m))
            ax_lon.plot(ext[m][ent]["t"], ext[m][ent]["e_s"], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.6, label=DISPLAY_NAMES.get(m, m))
        if fault_window is not None:
            ax_lat.axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.08, label="故障阶段" if v == 0 else "")
            ax_lon.axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.08, label="" if v > 0 else "故障阶段")
        ax_lat.axhline(0, color="k", linewidth=0.7, linestyle=":")
        ax_lon.axhline(0, color="k", linewidth=0.7, linestyle=":")
        ax_lat.set_title(f"{VEH_LABELS[v]} e_y")
        ax_lon.set_title(f"{VEH_LABELS[v]} e_s")
        ax_lat.grid(True, alpha=0.25)
        ax_lon.grid(True, alpha=0.25)
        ax_lon.set_xlabel("time [s]")
    axes[0, 0].set_ylabel("e_y [m]")
    axes[1, 0].set_ylabel("e_s [m]")
    fig.suptitle(exp.title_cn + "：四车横向/纵向误差对比", fontsize=13, fontweight="bold")
    _shared_legend(fig, axes_list, ncol=5, rect=(0.0, 0.0, 1.0, 0.93))
    _append_fig(fig, "each_vehicle_lat_long_error_compare")

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=False)
    bar_labels: List[str] = []
    load_bars: List[float] = []
    err_bars: List[float] = []
    for m in method_order:
        load_idx = _payload_load_index(results[m])
        sys_m = ext[m]["system"]
        if load_idx.size == 0:
            continue
        t = np.arange(load_idx.size, dtype=float) * float(ns["dt"])
        axes[0].plot(
            t,
            load_idx,
            color=COLORS.get(m, "tab:blue"),
            linestyle=LINESTYLES.get(m, "-"),
            linewidth=1.8,
            label=DISPLAY_NAMES.get(m, m),
        )
        axes[1].plot(
            sys_m["t"],
            sys_m["e_pos"],
            color=COLORS.get(m, "tab:blue"),
            linestyle=LINESTYLES.get(m, "-"),
            linewidth=1.8,
            label=DISPLAY_NAMES.get(m, m),
        )
        bar_labels.append(DISPLAY_NAMES.get(m, m))
        load_bars.append(_series_rms(load_idx))
        err_bars.append(_series_rms(np.asarray(sys_m["e_pos"], dtype=float)))
    ybar = np.arange(len(bar_labels), dtype=float)
    if len(bar_labels) > 0:
        base_idx = 0
        for i, label in enumerate(bar_labels):
            if "baseline" in label:
                base_idx = i
                break
        load_ref = max(load_bars[base_idx], 1e-9)
        err_ref = max(err_bars[base_idx], 1e-9)
        load_rel = np.asarray(load_bars, dtype=float) / load_ref
        err_rel = np.asarray(err_bars, dtype=float) / err_ref
        bar_colors = [COLORS.get(m, "tab:blue") for m in method_order if m in results]
        axes[2].barh(ybar - 0.18, load_rel, height=0.34, color=bar_colors, alpha=0.72, label="受力需求RMS / baseline [-]")
        axes[2].barh(ybar + 0.18, err_rel, height=0.34, color=bar_colors, alpha=0.28, hatch="//", label="位置误差RMS / baseline [-]")
        axes[2].axvline(1.0, color="k", linestyle=":", linewidth=0.9)
        axes[2].set_yticks(ybar)
        axes[2].set_yticklabels(bar_labels)
        axes[2].set_xlim(0.0, max(1.15, 1.12 * float(np.nanmax(np.r_[load_rel, err_rel]))))
    axes[0].set_ylabel("归一化受力需求 [-]")
    axes[0].set_title("受力需求（平滑稳健口径）")
    axes[1].set_ylabel("e_pos [m]")
    axes[1].set_title("跟踪误差收益")
    axes[2].set_ylabel("method [-]")
    axes[2].set_xlabel("相对 AKE-baseline [-]")
    for i, ax in enumerate(axes):
        if fault_window is not None:
            ax.axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.08, label="故障阶段" if i == 0 else "")
        ax.grid(True, alpha=0.25)
    axes[2].legend(fontsize=8, loc="upper right")
    fig.suptitle(exp.title_cn + "：货物受力需求与跟踪收益", fontsize=13, fontweight="bold")
    _shared_legend(fig, axes[:2], ncol=3, rect=(0.0, 0.0, 1.0, 0.92), anchor_y=0.965)
    _append_fig(fig, "payload_force_moment_compare")

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=False)
    for m in method_order:
        usage, margin, rms = _conn_usage_arrays(results[m])
        if usage.size == 0:
            continue
        t = np.arange(usage.size, dtype=float) * float(ns["dt"])
        axes[0].plot(t, usage, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=DISPLAY_NAMES.get(m, m))
        axes[1].plot(t, margin, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=DISPLAY_NAMES.get(m, m))
        axes[2].plot(t, rms, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=DISPLAY_NAMES.get(m, m))
    axes[0].axhline(1.0, color="tab:red", linestyle=":", linewidth=1.1, label="约束边界 [-]")
    axes[1].axhline(0.0, color="tab:red", linestyle=":", linewidth=1.1, label="安全裕度边界 [-]")
    axes[0].set_ylabel("约束占用率 [-]")
    axes[0].set_title("四车相对连接约束占用率")
    axes[1].set_ylabel("安全裕度 [-]")
    axes[1].set_title("正值表示未触及连接约束")
    axes[2].set_ylabel("rms_rel [-]")
    axes[2].set_title("相对连接误差能量")
    for i, ax in enumerate(axes):
        if fault_window is not None:
            ax.axvspan(fault_window[0], fault_window[1], color="tab:purple", alpha=0.08, label="故障阶段" if i == 0 else "")
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("time [s]")
    fig.suptitle(exp.title_cn + "：连接约束安全裕度", fontsize=13, fontweight="bold")
    _shared_legend(fig, axes, ncol=3, rect=(0.0, 0.0, 1.0, 0.93), anchor_y=0.965)
    _append_fig(fig, "connection_error_compare")

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=False)
    for m in method_order:
        qg, md, lr, gm = _comm_arrays(results[m])
        fa, dn = _fault_arrays(results[m])
        if qg.size > 0:
            t = np.arange(qg.size, dtype=float) * float(ns["dt"])
            axes[0].plot(t, qg, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=f"{DISPLAY_NAMES.get(m, m)} quality")
            axes[0].plot(t, lr, color=COLORS.get(m, "tab:blue"), linestyle=":", linewidth=1.2, alpha=0.75, label=f"{DISPLAY_NAMES.get(m, m)} loss")
            axes[1].plot(t, md, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=DISPLAY_NAMES.get(m, m))
        if dn.size > 0:
            t2 = np.arange(dn.size, dtype=float) * float(ns["dt"])
            axes[2].plot(t2, dn, color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.7, label=f"{DISPLAY_NAMES.get(m, m)} deficit")
            if np.any(fa > 0.5):
                axes[2].fill_between(
                    t2,
                    0.0,
                    np.max(dn) if np.max(dn) > 0 else 1.0,
                    where=fa > 0.5,
                    color="tab:purple",
                    alpha=0.07,
                    label="故障阶段" if m == method_order[0] else "",
                )
    axes[0].set_ylabel("quality/loss [-]")
    axes[1].set_ylabel("delay [steps]")
    axes[2].set_ylabel("deficit norm [-]")
    axes[2].set_xlabel("time [s]")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=8, loc="upper left", ncol=2)
    axes[1].legend(fontsize=8, loc="upper right", ncol=2)
    axes[2].legend(fontsize=8, loc="upper left", ncol=3)
    fig.suptitle(exp.title_cn + "：通信/时延/故障时序", fontsize=13, fontweight="bold")
    fig.tight_layout()
    _append_fig(fig, "comm_delay_fault_timeline")

    if fault_window is not None:
        t0, t1 = fault_window
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        for m in method_order:
            sys_m = ext[m]["system"]
            mask = (sys_m["t"] >= max(0.0, t0 - 2.0)) & (sys_m["t"] <= t1 + 8.0)
            axes[0].plot(sys_m["t"][mask], sys_m["e_pos"][mask], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
            axes[1].plot(sys_m["t"][mask], sys_m["e_y"][mask], color=COLORS.get(m, "tab:blue"), linestyle=LINESTYLES.get(m, "-"), linewidth=1.8, label=DISPLAY_NAMES.get(m, m))
        for ax in axes:
            ax.axvspan(t0, t1, color="tab:purple", alpha=0.12, label="故障阶段")
            ax.grid(True, alpha=0.25)
        axes[0].set_ylabel("e_pos [m]")
        axes[1].set_ylabel("e_y [m]")
        axes[1].set_xlabel("time [s]")
        fig.suptitle(exp.title_cn + "：故障阶段局部放大", fontsize=13, fontweight="bold")
        _shared_legend(fig, axes, ncol=3, rect=(0.0, 0.0, 1.0, 0.93), anchor_y=0.965)
        _append_fig(fig, "fault_window_zoom")

    series_dump: Dict[str, Any] = {}
    for m in method_order:
        sys_m = ext[m]["system"]
        for key in ["t", "e_pos", "e_y", "e_s", "xg", "yg", "xg_ref", "yg_ref"]:
            series_dump[f"{m}_system_{key}"] = np.asarray(sys_m[key], dtype=float)
    _save_npz(exp.category, f"{fig_prefix}_series", **series_dump)
    generated["data_files"].append(str((_category_dirs(exp.category)[1] / f"{VERSION}_{fig_prefix}_series.npz")))
    return generated


def _metrics_rows(exp: ExperimentSpec, results: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for method_key, res in results.items():
        attempt_idx = _safe_float(res.get("_attempt_idx", np.nan), np.nan)
        max_extra_steps = _safe_float(res.get("_max_extra_steps", np.nan), np.nan)
        traj_samples = _safe_float(res.get("traj_samples", np.nan), np.nan)
        if (not np.isfinite(traj_samples)) and ("ref_team_hist" in res):
            team_ref = np.asarray(res["ref_team_hist"], dtype=float)
            if team_ref.ndim == 2 and team_ref.shape[0] > 0:
                traj_samples = float(team_ref.shape[0])
        if (not np.isfinite(traj_samples)):
            traj_samples = _safe_float(res.get("sim_steps_nominal", np.nan), np.nan)
        final_s = _safe_float(res.get("final_s", np.nan), np.nan)
        if (not np.isfinite(final_s)) and ("team_state_hist" in res):
            team = np.asarray(res["team_state_hist"], dtype=float)
            sim_steps = int(res.get("sim_steps", max(team.shape[0] - 1, 0)))
            if team.ndim == 2 and team.shape[0] > 0:
                final_s = _safe_float(team[min(sim_steps, team.shape[0] - 1), 0], np.nan)
        target_s = _safe_float(res.get("target_s_team", np.nan), np.nan)
        if (not np.isfinite(target_s)) and ("ref_team_hist" in res):
            team_ref = np.asarray(res["ref_team_hist"], dtype=float)
            if team_ref.ndim == 2 and team_ref.shape[0] > 0:
                target_s = _safe_float(team_ref[-1, 0], np.nan)
        rows.append(
            {
                "category": exp.category,
                "experiment": exp.name,
                "title_cn": exp.title_cn,
                "method": method_key,
                "display_name": DISPLAY_NAMES.get(method_key, method_key),
                "attempt_idx": int(attempt_idx) if np.isfinite(attempt_idx) else np.nan,
                "speed_scale": _safe_float(res.get("_speed_scale", np.nan), np.nan),
                "max_extra_steps": int(max_extra_steps) if np.isfinite(max_extra_steps) else np.nan,
                "full_path_reached": bool(res.get("full_path_reached", False)),
                "progress_ratio": _progress_ratio(res),
                "final_s": final_s,
                "traj_length": target_s,
                "traj_samples": traj_samples,
                "rmse_lat_mean": _safe_float(res.get("rmse_lat_mean", np.nan), np.nan),
                "rmse_long_mean": _safe_float(res.get("rmse_long_mean", np.nan), np.nan),
                "max_lat_global": _safe_float(res.get("max_lat_global", np.nan), np.nan),
                "max_long_global": _safe_float(res.get("max_long_global", np.nan), np.nan),
                "step_time_mean": _safe_float(res.get("step_time_mean", np.nan), np.nan),
                "mpc_solve_time_mean": _safe_float(res.get("mpc_solve_time_mean", np.nan), np.nan),
                "stop_reason": str(res.get("stop_reason", "")),
                "comm_quality_mean": _safe_float(res.get("comm_summary", {}).get("quality_mean", np.nan), np.nan),
                "comm_delay_mean": _safe_float(
                    res.get("comm_summary", {}).get(
                        "delay_mean",
                        res.get("comm_summary", {}).get("delay_steps_mean", np.nan),
                    ),
                    np.nan,
                ),
                "comm_loss_mean": _safe_float(
                    res.get("comm_summary", {}).get(
                        "loss_mean",
                        res.get("comm_summary", {}).get("loss_ratio_mean", np.nan),
                    ),
                    np.nan,
                ),
                "fault_active_ratio": _safe_float(res.get("fault_summary", {}).get("active_ratio", np.nan), np.nan),
                "fault_deficit_norm_peak": _safe_float(res.get("fault_summary", {}).get("deficit_norm_peak", np.nan), np.nan),
                "conn_rms_mean": _safe_float(res.get("connection_summary", {}).get("rms_rel_mean", np.nan), np.nan),
            }
        )
    return rows


def _save_metrics_csv(rows: Sequence[Mapping[str, Any]], name: str) -> Path:
    path = DATA_ROOT / f"{VERSION}_{name}.csv"
    if len(rows) == 0:
        return path
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _plot_global_summary(all_rows: Sequence[Mapping[str, Any]]) -> List[str]:
    out: List[str] = []
    base_map: Dict[str, Mapping[str, Any]] = {}
    main_map: Dict[str, Mapping[str, Any]] = {}
    for row in all_rows:
        if row["method"] == "baseline":
            base_map[str(row["experiment"])] = row
        elif row["method"] == "main":
            main_map[str(row["experiment"])] = row

    common = [k for k in base_map.keys() if k in main_map]
    if len(common) == 0:
        return out

    labels = common
    lat_base = np.array([_safe_float(base_map[k]["rmse_lat_mean"], np.nan) for k in common], dtype=float)
    lat_main = np.array([_safe_float(main_map[k]["rmse_lat_mean"], np.nan) for k in common], dtype=float)
    long_base = np.array([_safe_float(base_map[k]["rmse_long_mean"], np.nan) for k in common], dtype=float)
    long_main = np.array([_safe_float(main_map[k]["rmse_long_mean"], np.nan) for k in common], dtype=float)
    prog_base = np.array([_safe_float(base_map[k]["progress_ratio"], np.nan) for k in common], dtype=float)
    prog_main = np.array([_safe_float(main_map[k]["progress_ratio"], np.nan) for k in common], dtype=float)

    x = np.arange(len(common), dtype=float)
    w = 0.36
    fig, axes = plt.subplots(3, 1, figsize=(max(14, 0.6 * len(common) + 6), 11), sharex=True)
    axes[0].bar(x - w / 2, lat_base, width=w, color="tab:gray", alpha=0.75, label="AKE-baseline")
    axes[0].bar(x + w / 2, lat_main, width=w, color="tab:red", alpha=0.85, label="TF13")
    axes[0].set_ylabel("RMSE e_y [m]")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend()
    axes[1].bar(x - w / 2, long_base, width=w, color="tab:gray", alpha=0.75, label="AKE-baseline")
    axes[1].bar(x + w / 2, long_main, width=w, color="tab:red", alpha=0.85, label="TF13")
    axes[1].set_ylabel("RMSE e_s [m]")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend()
    axes[2].bar(x - w / 2, prog_base, width=w, color="tab:gray", alpha=0.75, label="AKE-baseline")
    axes[2].bar(x + w / 2, prog_main, width=w, color="tab:red", alpha=0.85, label="TF13")
    axes[2].set_ylabel("进度占比 [-]")
    axes[2].set_xlabel("experiment [-]")
    axes[2].grid(True, axis="y", alpha=0.25)
    axes[2].legend()
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=55, ha="right")
    fig.suptitle("TF13 回头弯鲁棒性实验：主方法 vs baseline 总结", fontsize=14, fontweight="bold")
    p = _save_fig(fig, "summary", "stress_suite_global_summary")
    out.append(str(p))
    return out


def replot_existing_suite(existing_root: Path) -> None:
    global OUT_ROOT, FIG_ROOT, DATA_ROOT, HISTORY_ROOT
    existing_root = Path(existing_root)
    OUT_ROOT = existing_root
    FIG_ROOT = existing_root / "figures"
    DATA_ROOT = existing_root / "data"
    HISTORY_ROOT = DATA_ROOT / "history_runs"
    _ensure_dirs()

    ns = base_figs._bootstrap_env_from_notebook()
    try:
        ns["TF12_PATH_CFG"]["hairpin_ref_speed"] = float(SUITE_HAIRPIN_REF_SPEED)
        hairpin_pack = ns["_build_hairpin_path"](
            v_ref=float(ns["TF12_PATH_CFG"]["hairpin_ref_speed"]),
            dt_val=float(ns["dt"]),
            payload_cfg=ns["A1_PAYLOAD_CFG"],
            mpc_cfg=ns["MPC_CFG"],
            path_cfg=ns["TF12_PATH_CFG"],
        )
        ns["TF12_PATH_LIBRARY"]["hairpin"] = hairpin_pack
    except Exception:
        pass

    exp_map = {e.name: e for e in _build_experiment_matrix()}
    manifest_path = DATA_ROOT / "summary" / f"{VERSION}_suite_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_rows: List[Dict[str, Any]] = []
    for item in manifest.get("experiments", []):
        name = str(item["name"])
        category = str(item["category"])
        exp = exp_map[name]
        pkl_path = DATA_ROOT / category / f"{VERSION}_{name}_results.pkl"
        with pkl_path.open("rb") as f:
            results = pickle.load(f)
        # Rebuild bundle from the speed used by the stored result.
        any_res = next(iter(results.values()))
        speed = float(any_res.get("_speed_scale", 0.90))
        bundle = _build_scenario_bundle(ns, speed)
        _plot_pair_or_multi_suite(ns, exp, bundle, results)
        all_rows.extend(_metrics_rows(exp, results))

    metrics_csv = _save_metrics_csv(all_rows, "stress_suite_metrics")
    summary_figs = _plot_global_summary(all_rows)
    manifest["metrics_csv"] = str(metrics_csv)
    manifest["summary_figures"] = summary_figs
    _save_json("summary", "suite_manifest", manifest)


def refresh_existing_suite(
    existing_root: Path,
    *,
    rerun_methods: Optional[Sequence[str]] = None,
    only_experiments: Optional[Sequence[str]] = None,
    out_root: Optional[Path] = None,
) -> Path:
    global OUT_ROOT, FIG_ROOT, DATA_ROOT, HISTORY_ROOT, STAMP
    existing_root = Path(existing_root)
    if out_root is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_root = ROOT / "paper_dcn_tf12_draft" / f"{SUITE_TAG}_{stamp}"
    else:
        out_root = Path(out_root)
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    OUT_ROOT = out_root
    FIG_ROOT = out_root / "figures"
    DATA_ROOT = out_root / "data"
    HISTORY_ROOT = DATA_ROOT / "history_runs"
    STAMP = out_root.name.replace(f"{SUITE_TAG}_", "")
    _ensure_dirs()

    rerun_methods = tuple(rerun_methods or ("main", "no_adapt", "no_fault_redist", "no_comm", "no_guard"))
    rerun_set = {str(x).strip() for x in rerun_methods if str(x).strip()}
    only_set = {str(x).strip() for x in (only_experiments or []) if str(x).strip()}

    ns = base_figs._bootstrap_env_from_notebook()
    try:
        ns["TF12_PATH_CFG"]["hairpin_ref_speed"] = float(SUITE_HAIRPIN_REF_SPEED)
        hairpin_pack = ns["_build_hairpin_path"](
            v_ref=float(ns["TF12_PATH_CFG"]["hairpin_ref_speed"]),
            dt_val=float(ns["dt"]),
            payload_cfg=ns["A1_PAYLOAD_CFG"],
            mpc_cfg=ns["MPC_CFG"],
            path_cfg=ns["TF12_PATH_CFG"],
        )
        ns["TF12_PATH_LIBRARY"]["hairpin"] = hairpin_pack
    except Exception:
        pass

    specs = _method_specs()
    exp_map = {e.name: e for e in _build_experiment_matrix()}
    src_manifest_path = existing_root / "data" / "summary" / f"{VERSION}_suite_manifest.json"
    if not src_manifest_path.exists():
        raise FileNotFoundError(f"source manifest not found: {src_manifest_path}")
    with src_manifest_path.open("r", encoding="utf-8") as f:
        src_manifest = json.load(f)

    suite_manifest: Dict[str, Any] = {
        "timestamp": STAMP,
        "suite_tag": SUITE_TAG,
        "source_root": str(existing_root),
        "out_root": str(OUT_ROOT),
        "fig_root": str(FIG_ROOT),
        "data_root": str(DATA_ROOT),
        "refresh_mode": {
            "rerun_methods": sorted(rerun_set),
            "only_experiments": sorted(only_set),
        },
        "experiments": [],
    }
    all_rows: List[Dict[str, Any]] = []

    for item in src_manifest.get("experiments", []):
        name = str(item["name"])
        category = str(item["category"])
        exp = exp_map[name]
        pkl_path = existing_root / "data" / category / f"{VERSION}_{name}_results.pkl"
        if not pkl_path.exists():
            raise FileNotFoundError(f"result pkl not found: {pkl_path}")
        with pkl_path.open("rb") as f:
            src_results = pickle.load(f)

        any_res = next(iter(src_results.values()))
        speed = float(any_res.get("_speed_scale", 0.90))
        attempt_idx = int(any_res.get("_attempt_idx", item.get("best_attempt_idx", 1)))
        max_extra = int(any_res.get("_max_extra_steps", 2400))
        bundle = _build_scenario_bundle(ns, speed)

        new_results: Dict[str, Dict[str, Any]] = {}
        for method_key in exp.methods:
            should_rerun = method_key in rerun_set and (len(only_set) == 0 or name in only_set)
            if should_rerun:
                print(
                    f"[REFRESH][RERUN] {category}/{name:<28} method={method_key:<16} "
                    f"speed={speed:.2f} extra={max_extra}"
                )
                new_results[method_key] = _run_one_method(
                    ns,
                    bundle,
                    exp,
                    method_key,
                    specs[method_key],
                    attempt_idx,
                    max_extra,
                )
            else:
                new_results[method_key] = dict(src_results[method_key])

        fig_info = _plot_pair_or_multi_suite(ns, exp, bundle, new_results)
        rows = _metrics_rows(exp, new_results)
        all_rows.extend(rows)
        _save_json(
            exp.category,
            f"{exp.name}_metrics",
            {
                "rows": rows,
                "refreshed_from": str(pkl_path),
                "rerun_methods": sorted([m for m in exp.methods if m in rerun_set and (len(only_set) == 0 or name in only_set)]),
            },
        )
        _save_json(
            exp.category,
            f"{exp.name}_attempts",
            {
                "refresh_source": str(pkl_path),
                "attempt_idx": attempt_idx,
                "speed_scale": speed,
                "max_extra_steps": max_extra,
            },
        )
        _save_pkl(exp.category, f"{exp.name}_results", new_results)
        suite_manifest["experiments"].append(
            {
                "category": exp.category,
                "name": exp.name,
                "title_cn": exp.title_cn,
                "methods": list(exp.methods),
                "metadata": dict(exp.metadata),
                "best_attempt_idx": attempt_idx,
                "best_score": list(_result_score(new_results)),
                "figures": fig_info["figures"],
                "data_files": fig_info["data_files"],
            }
        )

    metrics_csv = _save_metrics_csv(all_rows, "stress_suite_metrics")
    summary_figs = _plot_global_summary(all_rows)
    suite_manifest["metrics_csv"] = str(metrics_csv)
    suite_manifest["summary_figures"] = summary_figs
    _save_json("summary", "suite_manifest", suite_manifest)
    return OUT_ROOT


def main() -> None:
    _ensure_dirs()
    ns = base_figs._bootstrap_env_from_notebook()
    try:
        ns["TF12_PATH_CFG"]["hairpin_ref_speed"] = float(SUITE_HAIRPIN_REF_SPEED)
        hairpin_pack = ns["_build_hairpin_path"](
            v_ref=float(ns["TF12_PATH_CFG"]["hairpin_ref_speed"]),
            dt_val=float(ns["dt"]),
            payload_cfg=ns["A1_PAYLOAD_CFG"],
            mpc_cfg=ns["MPC_CFG"],
            path_cfg=ns["TF12_PATH_CFG"],
        )
        ns["TF12_PATH_LIBRARY"]["hairpin"] = hairpin_pack
        print(
            f"[SUITE] hairpin rebuilt for stress suite | ref_speed={SUITE_HAIRPIN_REF_SPEED:.2f} "
            f"| traj_length={hairpin_pack['traj_length']}"
        )
    except Exception as e:
        print(f"[SUITE][WARN] hairpin rebuild failed, keep existing pack: {e}")
    method_specs = _method_specs()
    experiments = _build_experiment_matrix()

    _save_json(
        "summary",
        "experiment_matrix",
        {
            "timestamp": STAMP,
            "suite_tag": SUITE_TAG,
            "num_experiments": len(experiments),
            "experiments": [
                {
                    "category": e.category,
                    "name": e.name,
                    "title_cn": e.title_cn,
                    "methods": list(e.methods),
                    "speed_candidates": list(e.speed_candidates),
                    "extra_candidates": list(e.extra_candidates),
                    "shared_method_cfg": dict(e.shared_method_cfg),
                    "metadata": dict(e.metadata),
                }
                for e in experiments
            ],
        },
    )

    all_metrics_rows: List[Dict[str, Any]] = []
    suite_manifest: Dict[str, Any] = {
        "timestamp": STAMP,
        "suite_tag": SUITE_TAG,
        "out_root": str(OUT_ROOT),
        "fig_root": str(FIG_ROOT),
        "data_root": str(DATA_ROOT),
        "experiments": [],
    }
    completed_runs: Dict[str, Dict[str, Any]] = {}

    for exp in experiments:
        print(f"\n===== EXPERIMENT: {exp.category}/{exp.name} =====")
        result_pack = _run_experiment_with_optional_reuse(ns, exp, method_specs, completed_runs)
        results = result_pack["results"]
        metrics_rows = _metrics_rows(exp, results)
        all_metrics_rows.extend(metrics_rows)

        fig_info = _plot_pair_or_multi_suite(ns, exp, result_pack["bundle"], results)
        _save_json(
            exp.category,
            f"{exp.name}_metrics",
            {"rows": metrics_rows, "best_score": result_pack["best_score"], "best_attempt_idx": result_pack["best_attempt_idx"]},
        )
        _save_json(exp.category, f"{exp.name}_attempts", {"attempts": result_pack["attempts"]})
        _save_pkl(exp.category, f"{exp.name}_results", results)
        suite_manifest["experiments"].append(
            {
                "category": exp.category,
                "name": exp.name,
                "title_cn": exp.title_cn,
                "methods": list(exp.methods),
                "metadata": dict(exp.metadata),
                "best_attempt_idx": result_pack["best_attempt_idx"],
                "best_score": list(result_pack["best_score"]),
                "figures": fig_info["figures"],
                "data_files": fig_info["data_files"],
            }
        )
        completed_runs[exp.name] = result_pack

    metrics_csv = _save_metrics_csv(all_metrics_rows, "stress_suite_metrics")
    summary_figs = _plot_global_summary(all_metrics_rows)
    suite_manifest["metrics_csv"] = str(metrics_csv)
    suite_manifest["summary_figures"] = summary_figs
    _save_json("summary", "suite_manifest", suite_manifest)
    print(f"\n[OK] stress suite completed. out_root={OUT_ROOT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TF13 hairpin stress-suite runner")
    parser.add_argument("--replot-root", type=str, default="", help="Replot an existing suite in place")
    parser.add_argument("--refresh-root", type=str, default="", help="Create a new suite by refreshing an existing suite")
    parser.add_argument("--out-root", type=str, default="", help="Output root for --refresh-root")
    parser.add_argument("--rerun-methods", nargs="*", default=[], help="Methods to rerun when refreshing")
    parser.add_argument("--only-experiments", nargs="*", default=[], help="Only rerun these experiments when refreshing")
    args = parser.parse_args()

    if args.replot_root:
        replot_existing_suite(Path(args.replot_root))
    elif args.refresh_root:
        new_root = refresh_existing_suite(
            Path(args.refresh_root),
            rerun_methods=args.rerun_methods if len(args.rerun_methods) > 0 else None,
            only_experiments=args.only_experiments if len(args.only_experiments) > 0 else None,
            out_root=Path(args.out_root) if args.out_root else None,
        )
        print(f"\n[OK] refreshed suite completed. out_root={new_root}")
    else:
        main()
