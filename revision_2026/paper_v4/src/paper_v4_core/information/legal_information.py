"""EXP-R2 R5 legal same-tick sensor packets and joint estimate assembly.

The plant truth is accepted only by ``sample_packets`` (the measurement
injector).  The controller-facing ``assemble_joint_estimate`` accepts packets,
rejects truth-like fields and future timestamps, and returns a detached 34-D
state estimate.  R5 has no network impairment; delayed-packet replay belongs
to the later E03/E05 network stages.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Mapping

import numpy as np

from ..controllers.physical_tracking_pilot import PilotConfig, solve


@dataclass(frozen=True)
class SensorNoise:
    position_std_m: float = 0.0
    heading_std_rad: float = 0.0
    velocity_std_mps: float = 0.0
    yaw_rate_std_radps: float = 0.0
    steering_std_rad: float = 0.0

    @classmethod
    def none(cls) -> "SensorNoise":
        return cls()

    @classmethod
    def basic(cls) -> "SensorNoise":
        return cls(
            position_std_m=0.01,
            heading_std_rad=float(np.deg2rad(0.2)),
            velocity_std_mps=0.02,
            yaw_rate_std_radps=0.005,
            steering_std_rad=0.0,
        )

    def metadata(self) -> dict:
        return asdict(self)


STATE_FIELDS = ("x_m", "y_m", "heading_rad", "vx_mps", "vy_mps", "yaw_rate_radps")
FORBIDDEN_KEYS = {"plant_state", "truth", "future_state", "network_truth", "fault_truth"}


def tick_rng(seed: int, tick: int, node: str, field: str) -> np.random.Generator:
    """Noise generator indexed by absolute tick, node and field.

    Task-book section 5 requires the noise to be indexed by absolute tick so that a
    method terminating early cannot shift the random stream for later ticks.  A single
    sequential stream (the previous implementation) drifts as soon as any run stops
    early or a node changes its number of draws, which makes two runs incomparable.
    Every draw is now a pure function of (seed, tick, node, field).
    """
    entropy = [int(seed), int(tick)] + [ord(character) for character in f"{node}|{field}"]
    return np.random.default_rng(np.random.SeedSequence(entropy))


def _noise_std(noise: SensorNoise) -> np.ndarray:
    return np.asarray(
        [
            noise.position_std_m,
            noise.position_std_m,
            noise.heading_std_rad,
            noise.velocity_std_mps,
            noise.velocity_std_mps,
            noise.yaw_rate_std_radps,
        ],
        dtype=float,
    )


def _measure_six(values: np.ndarray, noise: SensorNoise, seed: int, tick: int, node: str) -> dict[str, float]:
    std = _noise_std(noise)
    measured = np.asarray(values, dtype=float).copy()
    # A zero standard deviation contributes exactly 0.0, so the draw is skipped and the
    # channel stays bitwise equal to the plant value.
    for position, field in enumerate(STATE_FIELDS):
        if std[position] != 0.0:
            measured[position] = measured[position] + float(tick_rng(seed, tick, node, field).normal(0.0, std[position]))
    # The legal heading channel is causally unwrapped from local history.  Do
    # not map +pi to -pi here: that representation jump would silently change
    # the otherwise identical no-noise physical-MPC initial state.
    return {name: float(value) for name, value in zip(STATE_FIELDS, measured, strict=True)}


def sample_packets(
    plant_state: np.ndarray,
    actuator_state: np.ndarray,
    tick: int,
    noise: SensorNoise,
    seed: int,
) -> dict:
    """Create same-tick packets at the sensor boundary.

    The returned mapping contains measurements only.  It intentionally does
    not retain the input arrays or include evaluation truth.
    """
    state = np.asarray(plant_state, dtype=float)
    steering = np.asarray(actuator_state, dtype=float)
    if state.shape != (30,) or steering.shape != (4,):
        raise ValueError("plant/actuator state shapes must be (30,) and (4,)")
    vehicles = state[:24].reshape(4, 6)
    payload = state[24:30]
    packets: dict[str, dict] = {}
    for index in range(4):
        values = _measure_six(vehicles[index], noise, int(seed), int(tick), f"vehicle_{index}")
        steering_value = float(steering[index])
        if noise.steering_std_rad != 0.0:
            steering_value += float(tick_rng(int(seed), int(tick), f"vehicle_{index}", "actual_steering_rad").normal(0.0, noise.steering_std_rad))
        values["actual_steering_rad"] = steering_value
        packets[f"vehicle_{index}"] = {
            "node": f"vehicle_{index}",
            "sample_tick": int(tick),
            "arrival_tick": int(tick),
            "source": "vehicle_local_sensor_packet",
            "values": values,
        }
    packets["payload"] = {
        "node": "payload",
        "sample_tick": int(tick),
        "arrival_tick": int(tick),
        "source": "payload_coordinator_sensor_packet",
        "values": _measure_six(payload, noise, int(seed), int(tick), "payload"),
    }
    # The derived entropy is hashed so the exact noise realisation of this tick can be
    # identified without storing every draw.
    entropy = [[int(seed), int(tick), node, field] for node in sorted(packets) for field in sorted(packets[node]["values"])]
    entropy_hash = hashlib.sha256(json.dumps(entropy, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema": "EXP-R2-R5-legal-information-v2-absolute-tick-noise",
        "architecture": "centralized same-tick fusion of four local vehicle packets and one payload-coordinator packet",
        "noise": noise.metadata(),
        "noise_seed": int(seed),
        "noise_indexing": "per absolute tick, node and field via SeedSequence(seed, tick, ord(node|field))",
        "noise_entropy_sha256": entropy_hash,
        "packets": packets,
    }


def assemble_joint_estimate(information: Mapping, now_tick: int) -> tuple[np.ndarray, dict]:
    """Validate causal packets and assemble the physical MPC estimate."""
    if isinstance(information, np.ndarray) or not isinstance(information, Mapping):
        raise TypeError("controller requires a legal information mapping, not raw plant state")
    forbidden = FORBIDDEN_KEYS.intersection(information)
    if forbidden:
        raise ValueError(f"forbidden truth fields: {sorted(forbidden)}")
    packets = information.get("packets")
    if not isinstance(packets, Mapping):
        raise ValueError("packets mapping is required")
    expected = {"payload", *(f"vehicle_{i}" for i in range(4))}
    if set(packets) != expected:
        raise ValueError(f"packet nodes must be exactly {sorted(expected)}")

    state = np.empty(30, dtype=float)
    actuator = np.empty(4, dtype=float)
    audit_packets = []
    for index in range(4):
        name = f"vehicle_{index}"
        packet = packets[name]
        _validate_packet(packet, name, now_tick)
        values = packet["values"]
        state[index * 6 : (index + 1) * 6] = [values[field] for field in STATE_FIELDS]
        actuator[index] = values["actual_steering_rad"]
        audit_packets.append(_audit_packet(packet))
    packet = packets["payload"]
    _validate_packet(packet, "payload", now_tick)
    state[24:30] = [packet["values"][field] for field in STATE_FIELDS]
    audit_packets.append(_audit_packet(packet))
    estimate = np.r_[state, actuator]
    if not np.all(np.isfinite(estimate)):
        raise ValueError("non-finite legal estimate")
    return estimate.copy(), {
        "now_tick": int(now_tick),
        "packet_count": 5,
        "sources": audit_packets,
        "maximum_age_ticks": max(int(now_tick) - item["sample_tick"] for item in audit_packets),
        "truth_field_count": 0,
    }


def _validate_packet(packet: Mapping, expected_node: str, now_tick: int) -> None:
    if not isinstance(packet, Mapping) or packet.get("node") != expected_node:
        raise ValueError(f"invalid packet identity for {expected_node}")
    sample = int(packet.get("sample_tick", -1))
    arrival = int(packet.get("arrival_tick", -1))
    if sample > arrival or arrival > int(now_tick):
        raise ValueError(f"future or time-inconsistent packet for {expected_node}")
    values = packet.get("values")
    required = set(STATE_FIELDS) | ({"actual_steering_rad"} if expected_node.startswith("vehicle_") else set())
    if not isinstance(values, Mapping) or set(values) != required:
        raise ValueError(f"measurement fields mismatch for {expected_node}")
    if FORBIDDEN_KEYS.intersection(values):
        raise ValueError(f"truth field nested in {expected_node}")


def _audit_packet(packet: Mapping) -> dict:
    return {
        "node": packet["node"],
        "sample_tick": int(packet["sample_tick"]),
        "arrival_tick": int(packet["arrival_tick"]),
        "source": str(packet["source"]),
        "fields": sorted(packet["values"]),
    }


def solve_from_information(information, now_tick, u_nom, refs, model, config=PilotConfig()):
    """Controller boundary used by R5; raw plant arrays are rejected."""
    estimate, audit = assemble_joint_estimate(information, now_tick)
    result = solve(estimate, u_nom, refs, model, config)
    result["information_audit"] = audit
    result["initial_estimate"] = estimate
    return result
