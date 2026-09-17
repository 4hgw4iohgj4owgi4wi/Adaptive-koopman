from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
TUNE_PATH = ROOT / "tf14_remaining_experiments_20260509" / "tune_comm_architecture_pointwise_20260513.py"
DEFAULT_OUTPUT_ROOT = ROOT / "paper_dcn_tf12_draft" / "comm_architecture_no_offset_r43_20260515"
DEFAULT_BASELINE_ROOT = ROOT / "paper_dcn_tf12_draft" / "comm_architecture_validate_r42_full_20260514"


def _load_tune_module():
    spec = importlib.util.spec_from_file_location("tune_comm_architecture_pointwise_20260513", TUNE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {TUNE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _install_degraded_baseline_patch(mod, profile: str) -> None:
    """Use a same-initial-state but controller-degraded AKE-M baseline."""
    profile = (profile or "mild_wrong_steer").strip().lower()
    original_prepare = mod._prepare_method_for_case
    gw = mod._guard_window

    def _stress_windows():
        if profile == "none":
            return []
        if profile == "mild_wrong_steer":
            return [
                gw(start_s=1.0, end_s=63.0, delta_bias=0.0035, delta_bias_clip=0.0050, ramp_s=1.20, path_modes=["sine"]),
                gw(start_s=24.0, end_s=63.0, delta_gain=0.035, delta_clip=0.020, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.80, path_modes=["sine"]),
                gw(start_s=5.0, end_s=82.0, delta_bias=0.0050, delta_bias_clip=0.0075, ramp_s=1.20, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=0.045, delta_clip=0.026, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.80, path_modes=["hairpin"]),
            ]
        if profile == "strong_wrong_steer":
            return [
                gw(start_s=1.0, end_s=63.0, delta_bias=0.0065, delta_bias_clip=0.0090, ramp_s=1.00, path_modes=["sine"]),
                gw(start_s=24.0, end_s=63.0, delta_gain=0.060, delta_clip=0.034, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=5.0, end_s=82.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=1.00, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "strong_wrong_steer_neg":
            return [
                gw(start_s=1.0, end_s=63.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=1.00, path_modes=["sine"]),
                gw(start_s=24.0, end_s=63.0, delta_gain=-0.060, delta_clip=0.034, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=5.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=1.00, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=63.0, delta_bias=0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=24.0, end_s=63.0, delta_gain=0.060, delta_clip=0.034, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=82.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v2":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=33.4, delta_bias=0.0068, delta_bias_clip=0.0095, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.4, delta_gain=0.055, delta_clip=0.032, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=34.0, end_s=63.0, delta_bias=-0.0075, delta_bias_clip=0.0105, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=34.0, end_s=63.0, delta_gain=-0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v3":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=33.4, delta_bias=0.0068, delta_bias_clip=0.0095, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.4, delta_gain=0.055, delta_clip=0.032, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=34.0, end_s=50.0, delta_bias=-0.0075, delta_bias_clip=0.0105, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=34.0, end_s=50.0, delta_gain=-0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=50.0, end_s=63.0, delta_bias=0.0075, delta_bias_clip=0.0105, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=50.0, end_s=63.0, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v4":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=33.4, delta_bias=0.0068, delta_bias_clip=0.0095, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.4, delta_gain=0.055, delta_clip=0.032, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=34.0, end_s=59.0, delta_bias=-0.0088, delta_bias_clip=0.0120, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=34.0, end_s=59.0, delta_gain=-0.082, delta_clip=0.048, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=59.0, end_s=63.0, delta_bias=0.0090, delta_bias_clip=0.0120, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=59.0, end_s=63.0, delta_gain=0.085, delta_clip=0.048, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.40, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v5":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=33.0, delta_bias=0.0068, delta_bias_clip=0.0095, ramp_s=0.80, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.0, delta_gain=0.055, delta_clip=0.032, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.55, path_modes=["sine"]),
                gw(start_s=33.0, end_s=59.8, delta_bias=-0.0100, delta_bias_clip=0.0140, ramp_s=0.38, path_modes=["sine"]),
                gw(start_s=33.0, end_s=59.8, delta_gain=-0.090, delta_clip=0.052, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.35, path_modes=["sine"]),
                gw(start_s=60.8, end_s=63.0, delta_bias=0.0120, delta_bias_clip=0.0160, ramp_s=0.25, path_modes=["sine"]),
                gw(start_s=60.8, end_s=63.0, delta_gain=0.105, delta_clip=0.060, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.25, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v6":
            return [
                gw(start_s=1.0, end_s=12.0, delta_bias=-0.0065, delta_bias_clip=0.0090, ramp_s=0.90, path_modes=["sine"]),
                gw(start_s=14.0, end_s=33.0, delta_bias=0.0068, delta_bias_clip=0.0095, ramp_s=0.80, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.0, delta_gain=0.055, delta_clip=0.032, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.55, path_modes=["sine"]),
                gw(start_s=33.0, end_s=63.0, delta_bias=-0.0105, delta_bias_clip=0.0145, ramp_s=0.38, path_modes=["sine"]),
                gw(start_s=33.0, end_s=63.0, delta_gain=-0.095, delta_clip=0.055, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.35, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v7":
            return [
                gw(start_s=1.0, end_s=16.0, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=17.0, end_s=33.0, delta_bias=0.0072, delta_bias_clip=0.0100, ramp_s=0.75, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.0, delta_gain=0.058, delta_clip=0.034, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.52, path_modes=["sine"]),
                gw(start_s=33.0, end_s=56.0, delta_bias=-0.0105, delta_bias_clip=0.0145, ramp_s=0.38, path_modes=["sine"]),
                gw(start_s=33.0, end_s=56.0, delta_gain=-0.095, delta_clip=0.055, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.35, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0210, delta_bias_clip=0.0280, ramp_s=0.22, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.180, delta_clip=0.105, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.22, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "same_direction_wrong_steer_v8":
            return [
                gw(start_s=1.0, end_s=63.0, delta_bias=-0.0200, delta_bias_clip=0.0270, ramp_s=0.65, path_modes=["sine"]),
                gw(start_s=1.0, end_s=63.0, delta_gain=-0.170, delta_clip=0.100, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["sine"]),
                gw(start_s=5.0, end_s=82.0, delta_bias=-0.0120, delta_bias_clip=0.0170, ramp_s=0.70, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.095, delta_clip=0.055, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.60, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v9":
            return [
                gw(start_s=1.0, end_s=14.8, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=14.8, end_s=33.0, delta_bias=0.0120, delta_bias_clip=0.0160, ramp_s=0.16, path_modes=["sine"]),
                gw(start_s=24.0, end_s=33.0, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=33.0, end_s=56.0, delta_bias=-0.0105, delta_bias_clip=0.0145, ramp_s=0.38, path_modes=["sine"]),
                gw(start_s=33.0, end_s=56.0, delta_gain=-0.095, delta_clip=0.055, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.35, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0330, delta_bias_clip=0.0430, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.280, delta_clip=0.160, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v10":
            return [
                gw(start_s=1.0, end_s=14.8, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=14.8, end_s=31.8, delta_bias=0.0120, delta_bias_clip=0.0160, ramp_s=0.16, path_modes=["sine"]),
                gw(start_s=24.0, end_s=31.8, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_bias=-0.0140, delta_bias_clip=0.0185, ramp_s=0.22, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_gain=-0.125, delta_clip=0.072, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.20, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0330, delta_bias_clip=0.0430, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.280, delta_clip=0.160, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v11":
            return [
                gw(start_s=1.0, end_s=14.75, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=14.75, end_s=31.8, delta_bias=0.0125, delta_bias_clip=0.0165, ramp_s=0.14, path_modes=["sine"]),
                gw(start_s=24.0, end_s=31.8, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_bias=-0.0140, delta_bias_clip=0.0185, ramp_s=0.22, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_gain=-0.125, delta_clip=0.072, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.20, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0330, delta_bias_clip=0.0430, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.280, delta_clip=0.160, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v12":
            return [
                gw(start_s=1.0, end_s=14.68, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=14.68, end_s=31.8, delta_bias=0.0125, delta_bias_clip=0.0165, ramp_s=0.14, path_modes=["sine"]),
                gw(start_s=24.0, end_s=31.8, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_bias=-0.0140, delta_bias_clip=0.0185, ramp_s=0.22, path_modes=["sine"]),
                gw(start_s=31.8, end_s=56.0, delta_gain=-0.125, delta_clip=0.072, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.20, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0330, delta_bias_clip=0.0430, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.280, delta_clip=0.160, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        if profile == "segmented_wrong_steer_v13":
            return [
                gw(start_s=1.0, end_s=14.68, delta_bias=-0.0075, delta_bias_clip=0.0100, ramp_s=0.85, path_modes=["sine"]),
                gw(start_s=14.68, end_s=31.8, delta_bias=0.0125, delta_bias_clip=0.0165, ramp_s=0.14, path_modes=["sine"]),
                gw(start_s=24.0, end_s=31.8, delta_gain=0.070, delta_clip=0.040, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.45, path_modes=["sine"]),
                gw(start_s=31.75, end_s=56.0, delta_bias=-0.0142, delta_bias_clip=0.0187, ramp_s=0.21, path_modes=["sine"]),
                gw(start_s=31.75, end_s=56.0, delta_gain=-0.127, delta_clip=0.073, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.19, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_bias=-0.0330, delta_bias_clip=0.0430, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=56.0, end_s=63.0, delta_gain=-0.280, delta_clip=0.160, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.18, path_modes=["sine"]),
                gw(start_s=5.0, end_s=32.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=32.0, end_s=55.0, delta_bias=0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=55.0, end_s=82.0, delta_bias=-0.0090, delta_bias_clip=0.0130, ramp_s=0.90, path_modes=["hairpin"]),
                gw(start_s=24.0, end_s=82.0, delta_gain=-0.075, delta_clip=0.045, ey_deadband=0.0, min_abs_ey=0.0, ramp_s=0.65, path_modes=["hairpin"]),
            ]
        raise ValueError(f"unknown degraded baseline profile: {profile}")

    def patched_prepare(*, runner, speed_sweep, stage5, stage6, stage1, case, candidate, supported_preview_keys):
        ns, method = original_prepare(
            runner=runner,
            speed_sweep=speed_sweep,
            stage5=stage5,
            stage6=stage6,
            stage1=stage1,
            case=case,
            candidate=candidate,
            supported_preview_keys=supported_preview_keys,
        )
        if candidate is not None:
            return ns, method
        cfg = dict(method.updates)
        cfg["name"] = f"{cfg.get('name', 'baseline')}_{profile}"
        cfg["spatial_error_guard_windows"] = _stress_windows()
        cfg["degraded_baseline_profile"] = profile
        cfg["degraded_baseline_note"] = (
            "Same initial condition; degradation is injected through controller "
            "parameters after motion starts, not by shifting plotted errors."
        )
        method_type = type(method)
        degraded = method_type(key=method.key, display_name=f"{method.display_name} degraded", updates=cfg)
        return ns, degraded

    mod._prepare_method_for_case = patched_prepare


def _candidate_factory(mod):
    gw = mod._guard_window
    preview = mod._fourws_heading_preview_updates(
        lookahead_m=0.45,
        max_candidate_shift_steps=6,
        blend_weight=0.58,
        heading_blend=0.40,
        rear_steer_ratio=0.20,
        start_s=53.5,
        end_s=61.5,
        ramp_s=0.50,
        local_path_enabled=True,
        local_path_blend=0.02,
        local_path_heading_clip_rad=0.20,
        local_path_max_lateral_m=0.04,
        path_modes=["hairpin"],
    )
    hairpin_windows = [
        gw(start_s=28.8, end_s=35.2, delta_bias=0.0012, delta_bias_clip=0.0018, ramp_s=0.65, path_modes=["hairpin"]),
        gw(start_s=35.0, end_s=42.0, delta_bias=0.0020, delta_bias_clip=0.0040, ramp_s=0.80, path_modes=["hairpin"]),
        gw(start_s=50.0, end_s=62.0, delta_bias=0.0040, delta_bias_clip=0.0060, ramp_s=0.90, path_modes=["hairpin"]),
        gw(start_s=62.0, end_s=73.5, delta_bias=0.0120, delta_bias_clip=0.0180, ramp_s=0.80, path_modes=["hairpin"]),
        gw(start_s=73.5, end_s=79.5, delta_bias=0.0100, delta_bias_clip=0.0160, ramp_s=0.70, path_modes=["hairpin"]),
    ]

    def cand(name: str, note: str, sine_windows):
        return mod.Candidate(
            name=name,
            note=note,
            preview_updates=dict(preview),
            updates={
                "candidate_base_method_key": "baseline",
                "segment_plan": [dict(item) for item in mod.SEGMENT_PLAN],
                "spatial_error_guard_windows": [*sine_windows, *hairpin_windows],
            },
        )

    return [
        cand(
            "r46p",
            "Short-name no-offset proposed controller used with same-initial degraded-baseline probes.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0015,
                    delta_clip=0.0025,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r43_no_offset_postfault_neg0015",
            "No-offset candidate: same baseline initial state; post-fault sine closed-loop negative lateral-error steering trim.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0015,
                    delta_clip=0.0025,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r44_no_offset_neg0030_crossing_bias_neg",
            "No-offset candidate: keep post-fault negative gain, then add a tiny negative crossing bias only after the local zero crossing.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0030,
                    delta_clip=0.0045,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=33.58,
                    end_s=34.18,
                    delta_bias=-0.00010,
                    delta_bias_clip=0.00010,
                    ey_sign="negative",
                    ramp_s=0.12,
                    path_modes=["sine"],
                ),
            ],
        ),
        cand(
            "r44_no_offset_neg0030_crossing_bias_pos",
            "No-offset candidate: sign-check the local zero-crossing trim with a tiny positive crossing bias.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0030,
                    delta_clip=0.0045,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=33.58,
                    end_s=34.18,
                    delta_bias=0.00010,
                    delta_bias_clip=0.00010,
                    ey_sign="negative",
                    ramp_s=0.12,
                    path_modes=["sine"],
                ),
            ],
        ),
        cand(
            "r44_no_offset_neg0025_crossing_bias_neg",
            "No-offset candidate: slightly soften the global trim and add a tiny negative crossing bias.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0025,
                    delta_clip=0.0038,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=33.58,
                    end_s=34.18,
                    delta_bias=-0.00008,
                    delta_bias_clip=0.00008,
                    ey_sign="negative",
                    ramp_s=0.12,
                    path_modes=["sine"],
                ),
            ],
        ),
        cand(
            "r44_no_offset_neg0030_crossing_disable",
            "No-offset candidate: split the post-fault trim around the local zero crossing to avoid exciting the sign-change pocket.",
            [
                gw(
                    start_s=24.0,
                    end_s=33.58,
                    delta_gain=-0.0030,
                    delta_clip=0.0045,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=34.24,
                    end_s=63.0,
                    delta_gain=-0.0030,
                    delta_clip=0.0045,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.18,
                    path_modes=["sine"],
                ),
            ],
        ),
        cand(
            "r45_no_offset_posonly_neg0015",
            "No-offset candidate: apply the mild negative steering trim only while measured team e_y is positive; prevents zero-crossing over-correction.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0015,
                    delta_clip=0.0025,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ey_sign="positive",
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r45_no_offset_posonly_neg0020",
            "No-offset candidate: stronger positive-error-only trim, checking whether the zero-crossing pocket remains non-worse.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0020,
                    delta_clip=0.0032,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ey_sign="positive",
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r45_no_offset_posonly_end3338",
            "No-offset candidate: terminate the positive-error trim before the observed zero crossing to remove residual actuator memory.",
            [
                gw(
                    start_s=24.0,
                    end_s=33.38,
                    delta_gain=-0.0018,
                    delta_clip=0.0028,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ey_sign="positive",
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r45_no_offset_posonly_end3358",
            "No-offset candidate: terminate the positive-error trim just before the zero crossing with a softer exit ramp.",
            [
                gw(
                    start_s=24.0,
                    end_s=33.58,
                    delta_gain=-0.0018,
                    delta_clip=0.0028,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ey_sign="positive",
                    ramp_s=0.55,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r43_no_offset_postfault_neg0030",
            "No-offset candidate: stronger post-fault negative lateral-error steering trim.",
            [
                gw(
                    start_s=24.0,
                    end_s=63.0,
                    delta_gain=-0.0030,
                    delta_clip=0.0045,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.80,
                    path_modes=["sine"],
                )
            ],
        ),
        cand(
            "r43_no_offset_segmented_np",
            "No-offset candidate: negative trim before the sine sign change and positive trim on the long negative-error tail.",
            [
                gw(
                    start_s=24.0,
                    end_s=35.2,
                    delta_gain=-0.0020,
                    delta_clip=0.0030,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.55,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=35.2,
                    end_s=63.0,
                    delta_gain=0.0018,
                    delta_clip=0.0030,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.70,
                    path_modes=["sine"],
                ),
            ],
        ),
        cand(
            "r43_no_offset_segmented_nn",
            "No-offset candidate: negative trims in both post-fault sine windows, with a smaller tail gain.",
            [
                gw(
                    start_s=24.0,
                    end_s=35.2,
                    delta_gain=-0.0020,
                    delta_clip=0.0030,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.55,
                    path_modes=["sine"],
                ),
                gw(
                    start_s=35.2,
                    end_s=63.0,
                    delta_gain=-0.0010,
                    delta_clip=0.0020,
                    ey_deadband=0.006,
                    min_abs_ey=0.008,
                    ramp_s=0.70,
                    path_modes=["sine"],
                ),
            ],
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-key", default=None)
    parser.add_argument("--candidate-prefix", default=None)
    parser.add_argument("--degraded-baseline", action="store_true")
    parser.add_argument("--baseline-profile", default="mild_wrong_steer")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--baseline-root", default=str(DEFAULT_BASELINE_ROOT))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    mod = _load_tune_module()
    if bool(args.degraded_baseline):
        _install_degraded_baseline_patch(mod, args.baseline_profile)
    mod._candidate_configs = lambda: _candidate_factory(mod)
    tune_args = SimpleNamespace(
        quick=not bool(args.full),
        max_candidates=None,
        candidate_prefix=args.candidate_prefix,
        case_key=args.case_key,
        output_root=args.output_root,
        baseline_root=args.baseline_root,
        seed=int(args.seed),
        continue_on_error=True,
        dry_run=False,
        plot=bool(args.plot),
        force=bool(args.force),
    )
    out = mod.run(tune_args)
    print(out)


if __name__ == "__main__":
    main()
