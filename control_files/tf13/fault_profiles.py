"""Fault profile presets for TF13."""

from __future__ import annotations


def profile_ax_limited(vehicle_index=1):
    return {
        "enable_fault_tolerant_control": True,
        "fault_vehicle_index": int(vehicle_index),
        "fault_mode": "ax_limit",
        "fault_ax_scale": 0.45,
        "fault_delta_scale": 1.00,
        "fault_start_step": 80,
        "fault_start_s": 8.0,
        "fault_tolerant_redistribution": True,
    }


def profile_steer_limited(vehicle_index=1):
    return {
        "enable_fault_tolerant_control": True,
        "fault_vehicle_index": int(vehicle_index),
        "fault_mode": "delta_limit",
        "fault_ax_scale": 1.00,
        "fault_delta_scale": 0.55,
        "fault_start_step": 80,
        "fault_start_s": 8.0,
        "fault_tolerant_redistribution": True,
    }


def profile_both_limited(vehicle_index=1):
    return {
        "enable_fault_tolerant_control": True,
        "fault_vehicle_index": int(vehicle_index),
        "fault_mode": "both",
        "fault_ax_scale": 0.45,
        "fault_delta_scale": 0.55,
        "fault_start_step": 80,
        "fault_start_s": 8.0,
        "fault_tolerant_redistribution": True,
        "fault_comp_gain": 0.90,
        "fault_comp_delta_clip": 0.035,
        "fault_comp_ax_clip": 0.38,
    }

