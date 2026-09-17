"""Non-dynamic contract tests for the EXP-R2 R5 legal-information boundary."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from .cli import save, sha
from .e01_100m import params
from .information.legal_information import SensorNoise, assemble_joint_estimate, sample_packets
from .plant.four_vehicle_common import initialize_state


def _record(tests, name, passed, **details):
    tests.append({"name": name, "pass": bool(passed), **details})


def run(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    state = initialize_state(params("P0"), 2.0)
    actuator = np.asarray([0.01, -0.02, 0.03, -0.04])
    tests = []

    packet = sample_packets(state, actuator, 7, SensorNoise.none(), 1)
    estimate, audit = assemble_joint_estimate(packet, 7)
    _record(
        tests,
        "noiseless_round_trip",
        np.array_equal(estimate[:30], state) and np.array_equal(estimate[30:], actuator),
        maximum_absolute_error=float(np.max(np.abs(estimate - np.r_[state, actuator]))),
    )
    _record(
        tests,
        "five_declared_same_tick_sources",
        audit["packet_count"] == 5 and audit["maximum_age_ticks"] == 0 and audit["truth_field_count"] == 0,
    )

    unwrapped = state.copy()
    unwrapped[[2, 8, 14, 20, 26]] = np.asarray([3.2, 3.3, 3.4, 3.5, 3.6])
    unwrapped_packet = sample_packets(unwrapped, actuator, 7, SensorNoise.none(), 1)
    unwrapped_estimate, _ = assemble_joint_estimate(unwrapped_packet, 7)
    _record(tests, "causal_unwrapped_heading_preserved", np.array_equal(unwrapped_estimate[:30], unwrapped))

    try:
        assemble_joint_estimate(state, 7)
        rejected_raw = False
    except TypeError:
        rejected_raw = True
    _record(tests, "raw_plant_state_rejected", rejected_raw)

    future = sample_packets(state, actuator, 8, SensorNoise.none(), 1)
    try:
        assemble_joint_estimate(future, 7)
        rejected_future = False
    except ValueError:
        rejected_future = True
    _record(tests, "future_packet_rejected", rejected_future)

    truth = sample_packets(state, actuator, 7, SensorNoise.none(), 1)
    truth["plant_state"] = state.tolist()
    try:
        assemble_joint_estimate(truth, 7)
        rejected_truth = False
    except ValueError:
        rejected_truth = True
    _record(tests, "truth_side_channel_rejected", rejected_truth)

    missing = sample_packets(state, actuator, 7, SensorNoise.none(), 1)
    del missing["packets"]["vehicle_3"]
    try:
        assemble_joint_estimate(missing, 7)
        rejected_missing = False
    except ValueError:
        rejected_missing = True
    _record(tests, "missing_node_rejected", rejected_missing)

    noisy = sample_packets(state, actuator, 7, SensorNoise.basic(), 5105)
    noisy_estimate, _ = assemble_joint_estimate(noisy, 7)
    changed = noisy_estimate[:30] - state
    _record(
        tests,
        "basic_noise_changes_measured_channels_only",
        np.any(changed != 0.0) and np.array_equal(noisy_estimate[30:], actuator),
        maximum_state_perturbation=float(np.max(np.abs(changed))),
        maximum_steering_perturbation=float(np.max(np.abs(noisy_estimate[30:] - actuator))),
    )


    # --- 2026-09-16 additions required by section 5 -----------------------------
    from .information.legal_information import tick_rng

    first = tick_rng(5105, 11, "vehicle_2", "x_m").normal(0.0, 1.0)
    again = tick_rng(5105, 11, "vehicle_2", "x_m").normal(0.0, 1.0)
    other_tick = tick_rng(5105, 12, "vehicle_2", "x_m").normal(0.0, 1.0)
    other_node = tick_rng(5105, 11, "vehicle_3", "x_m").normal(0.0, 1.0)
    _record(
        tests,
        "absolute_tick_noise_is_a_pure_function_of_seed_tick_node_field",
        first == again and first != other_tick and first != other_node,
        same_input_repeat=first == again,
        different_tick_differs=first != other_tick,
        different_node_differs=first != other_node,
    )

    # Early termination must not shift the stream: a tick drawn after an aborted run is
    # identical to the same tick drawn without the abort.
    uninterrupted = [tick_rng(5105, tick, "payload", "y_m").normal(0.0, 1.0) for tick in range(20)]
    aborted = [tick_rng(5105, tick, "payload", "y_m").normal(0.0, 1.0) for tick in range(3)]
    resumed = [tick_rng(5105, tick, "payload", "y_m").normal(0.0, 1.0) for tick in range(3, 20)]
    _record(
        tests,
        "early_termination_does_not_shift_the_noise_stream",
        aborted + resumed == uninterrupted,
        ticks=len(uninterrupted),
    )

    bundle = sample_packets(state, actuator, 7, SensorNoise.basic(), 5105)
    _record(
        tests,
        "information_bundle_registers_seed_indexing_and_entropy_hash",
        bundle.get("noise_seed") == 5105
        and "absolute tick" in bundle.get("noise_indexing", "")
        and isinstance(bundle.get("noise_entropy_sha256"), str)
        and len(bundle["noise_entropy_sha256"]) == 64,
        schema=bundle.get("schema"),
        entropy_sha256=bundle.get("noise_entropy_sha256"),
    )

    # A stale packet is not silently equal to a same-tick packet: it must be accepted
    # only with its age surfaced in the audit.
    stale = sample_packets(state, actuator, 6, SensorNoise.none(), 5105)
    stale_estimate, stale_audit = assemble_joint_estimate(stale, 7)
    _record(
        tests,
        "stale_packet_age_is_audited",
        stale_audit["maximum_age_ticks"] == 1,
        maximum_age_ticks=stale_audit["maximum_age_ticks"],
    )

    # Noisy heading pushed across the +/-pi representation boundary must stay finite and
    # must not trigger a representation jump in the assembled estimate.
    crossing = state.copy()
    crossing[[2, 8, 14, 20, 26]] = np.pi - 1e-3
    crossing_packet = sample_packets(crossing, actuator, 9, SensorNoise.basic(), 5105)
    crossing_estimate, _ = assemble_joint_estimate(crossing_packet, 9)
    heading_channels = crossing_estimate[[2, 8, 14, 20, 26]]
    _record(
        tests,
        "noisy_heading_across_pi_stays_finite_and_causal",
        np.all(np.isfinite(crossing_estimate))
        and np.all(np.abs(heading_channels - np.pi) < 0.05),
        headings=heading_channels.tolist(),
    )

    report = {
        "status": "PASS" if all(item["pass"] for item in tests) else "FAIL",
        "tests": tests,
        "basic_noise": SensorNoise.basic().metadata(),
        "scope": "information contract only; no plant dynamics and no performance evidence",
        "scope_note": "extended 2026-09-16 with absolute-tick noise indexing, early-termination invariance, entropy-hash registration, stale-packet auditing and a noisy cross-pi heading case, per section 5 and gpu_platform_decision_20260916.md",
        "source_sha256": sha(__file__),
    }
    save(out, "r5_information_tests.json", report)
    if report["status"] != "PASS":
        raise SystemExit(20)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
