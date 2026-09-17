"""Float64 batched Torch port of the predictor physics used by rollout_step."""
from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class TorchModel:
    vehicle_mass: float
    vehicle_inertia: float
    lf: float
    lr: float
    cf: float
    cr: float
    mu: float
    vehicle_gravity: float
    payload_mass: float
    payload_inertia: float
    payload_cog_height: float
    payload_gravity: float
    connector_stiffness: float
    connector_damping: float
    connector_free_play: float
    connector_smoothing_width: float
    payload_anchors: torch.Tensor
    vehicle_anchors: torch.Tensor
    support_matrix: torch.Tensor
    support_gram: torch.Tensor
    static_support: torch.Tensor
    support_target_static: torch.Tensor

    @classmethod
    def from_model(cls, model, *, device: torch.device, dtype: torch.dtype = torch.float64):
        payload_anchors = torch.as_tensor(model.payload_anchor_body_m, dtype=dtype, device=device)
        vehicle_anchors = torch.as_tensor(model.vehicle_anchor_body_m, dtype=dtype, device=device)
        support_matrix = torch.cat(
            [torch.ones((1, 4), dtype=dtype, device=device), payload_anchors.T], dim=0
        )
        support_gram = support_matrix @ support_matrix.T
        total = float(model.payload.mass_kg * model.payload.gravity_mps2)
        static_support = torch.full((4,), total / 4.0, dtype=dtype, device=device)
        support_target_static = support_matrix @ static_support
        return cls(
            vehicle_mass=float(model.vehicle.mass_kg),
            vehicle_inertia=float(model.vehicle.yaw_inertia_kgm2),
            lf=float(model.vehicle.lf_m),
            lr=float(model.vehicle.lr_m),
            cf=float(model.vehicle.cf_nprad),
            cr=float(model.vehicle.cr_nprad),
            mu=float(model.vehicle.mu),
            vehicle_gravity=float(model.vehicle.gravity_mps2),
            payload_mass=float(model.payload.mass_kg),
            payload_inertia=float(model.payload.yaw_inertia_kgm2),
            payload_cog_height=float(model.payload.cog_height_m),
            payload_gravity=float(model.payload.gravity_mps2),
            connector_stiffness=float(model.connector.stiffness_npm),
            connector_damping=float(model.connector.damping_nspm),
            connector_free_play=float(model.connector.free_play_m),
            connector_smoothing_width=float(model.connector.smoothing_width_m),
            payload_anchors=payload_anchors,
            vehicle_anchors=vehicle_anchors,
            support_matrix=support_matrix,
            support_gram=support_gram,
            static_support=static_support,
            support_target_static=support_target_static,
        )

    @classmethod
    def from_mapping(cls, value: dict, *, device: torch.device, dtype: torch.dtype = torch.float64):
        payload_anchors = torch.as_tensor(value["payload_anchors"], dtype=dtype, device=device)
        vehicle_anchors = torch.as_tensor(value["vehicle_anchors"], dtype=dtype, device=device)
        support_matrix = torch.cat([torch.ones((1, 4), dtype=dtype, device=device), payload_anchors.T], dim=0)
        support_gram = support_matrix @ support_matrix.T
        total = float(value["payload_mass"] * value["payload_gravity"])
        static_support = torch.full((4,), total / 4.0, dtype=dtype, device=device)
        return cls(
            **{key: value[key] for key in (
                "vehicle_mass", "vehicle_inertia", "lf", "lr", "cf", "cr", "mu", "vehicle_gravity",
                "payload_mass", "payload_inertia", "payload_cog_height", "payload_gravity",
                "connector_stiffness", "connector_damping", "connector_free_play", "connector_smoothing_width",
            )},
            payload_anchors=payload_anchors,
            vehicle_anchors=vehicle_anchors,
            support_matrix=support_matrix,
            support_gram=support_gram,
            static_support=static_support,
            support_target_static=support_matrix @ static_support,
        )


def rotate(vector: torch.Tensor, yaw: torch.Tensor) -> torch.Tensor:
    c, s = torch.cos(yaw), torch.sin(yaw)
    x, y = vector[..., 0], vector[..., 1]
    return torch.stack((c * x - s * y, s * x + c * y), dim=-1)


def inverse_rotate(vector: torch.Tensor, yaw: torch.Tensor) -> torch.Tensor:
    c, s = torch.cos(yaw), torch.sin(yaw)
    x, y = vector[..., 0], vector[..., 1]
    return torch.stack((c * x + s * y, -s * x + c * y), dim=-1)


def cross2(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def connector_terms(state: torch.Tensor, model: TorchModel) -> dict[str, torch.Tensor]:
    vehicles = state[..., :24].reshape(*state.shape[:-1], 4, 6)
    payload = state[..., 24:30]
    payload_yaw = payload[..., 2]
    payload_arm = rotate(model.payload_anchors, payload_yaw[..., None])
    payload_anchor = payload[..., None, :2] + payload_arm
    payload_cog_velocity = rotate(payload[..., 3:5], payload_yaw)
    payload_cross = payload[..., None, 5:6] * torch.stack((-payload_arm[..., 1], payload_arm[..., 0]), dim=-1)
    payload_anchor_velocity = payload_cog_velocity[..., None, :] + payload_cross

    vehicle_yaw = vehicles[..., :, 2]
    vehicle_arm = rotate(model.vehicle_anchors, vehicle_yaw)
    vehicle_anchor = vehicles[..., :, :2] + vehicle_arm
    vehicle_velocity = rotate(vehicles[..., :, 3:5], vehicle_yaw)
    vehicle_cross = vehicles[..., :, 5:6] * torch.stack((-vehicle_arm[..., 1], vehicle_arm[..., 0]), dim=-1)
    vehicle_anchor_velocity = vehicle_velocity + vehicle_cross

    displacement = vehicle_anchor - payload_anchor
    relative_velocity = vehicle_anchor_velocity - payload_anchor_velocity
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    normal = displacement / torch.clamp_min(distance[..., None], 1.0e-12)
    penetration = torch.clamp_min(distance - model.connector_free_play, 0.0)
    normal_speed = torch.sum(relative_velocity * normal, dim=-1)
    ratio = torch.clamp(penetration / model.connector_smoothing_width, 0.0, 1.0)
    smooth = 3.0 * ratio.square() - 2.0 * ratio.pow(3)
    weight = torch.where(
        penetration <= 0.0,
        torch.zeros_like(penetration),
        torch.where(penetration >= model.connector_smoothing_width, torch.ones_like(penetration), smooth),
    )
    force_norm = model.connector_stiffness * penetration + model.connector_damping * weight * torch.clamp_min(normal_speed, 0.0)
    payload_force_world = force_norm[..., None] * normal
    vehicle_force_world = -payload_force_world
    payload_force_body = inverse_rotate(payload_force_world, payload_yaw[..., None])
    vehicle_force_body = inverse_rotate(vehicle_force_world, vehicle_yaw)
    payload_moment = cross2(payload_arm, payload_force_world)
    vehicle_moment = cross2(vehicle_arm, vehicle_force_world)
    return {
        "payload_force_world": payload_force_world,
        "vehicle_force_world": vehicle_force_world,
        "payload_force_body": payload_force_body,
        "vehicle_force_body": vehicle_force_body,
        "payload_moment": payload_moment,
        "vehicle_moment": vehicle_moment,
        "force_norm": force_norm,
        "penetration": penetration,
        "weight": weight,
    }


def support_loads(payload_accel_body: torch.Tensor, model: TorchModel, *, strict: bool = False) -> torch.Tensor:
    total = model.payload_mass * model.payload_gravity
    target = torch.stack(
        (
            torch.full_like(payload_accel_body[..., 0], total),
            -model.payload_mass * model.payload_cog_height * payload_accel_body[..., 0],
            -model.payload_mass * model.payload_cog_height * payload_accel_body[..., 1],
        ),
        dim=-1,
    )
    rhs = target - model.support_target_static
    correction = torch.linalg.solve(model.support_gram, rhs.unsqueeze(-1)).squeeze(-1)
    loads = model.static_support + correction @ model.support_matrix
    if strict and bool(torch.any(loads < -1.0e-9).item()):
        raise RuntimeError("SUPPORT_LIFT_OUTSIDE_ENVELOPE")
    return torch.clamp_min(loads, 0.0)


def system_derivative_batch(
    state: torch.Tensor,
    controls: torch.Tensor,
    model: TorchModel,
    *,
    strict: bool = False,
) -> torch.Tensor:
    if state.ndim != 2 or state.shape[1] != 30 or controls.shape != (state.shape[0], 4, 2):
        raise ValueError("state must be [B,30] and controls [B,4,2]")
    vehicles = state[:, :24].reshape(-1, 4, 6)
    payload = state[:, 24:30]
    connector = connector_terms(state, model)
    payload_force_world = torch.sum(connector["payload_force_world"], dim=1)
    payload_accel_body = inverse_rotate(payload_force_world / model.payload_mass, payload[:, 2])
    support = support_loads(payload_accel_body, model, strict=strict)

    vx, vy, yaw_rate = vehicles[..., 3], vehicles[..., 4], vehicles[..., 5]
    speed = torch.maximum(torch.abs(vx), torch.full_like(vx, 0.5))
    alpha_front = controls[..., 1] - torch.atan2(vy + model.lf * yaw_rate, speed)
    alpha_rear = -torch.atan2(vy - model.lr * yaw_rate, speed)
    fy_front = model.cf * alpha_front
    fy_rear = model.cr * alpha_rear
    fx = (model.vehicle_mass + support / model.vehicle_gravity) * controls[..., 0]
    fy = fy_front + fy_rear
    yaw_moment = model.lf * fy_front - model.lr * fy_rear
    cap = model.mu * (model.vehicle_mass * model.vehicle_gravity + torch.clamp_min(support, 0.0))
    utilization = torch.sqrt(fx.square() + fy.square()) / torch.clamp_min(cap, 1.0e-12)
    scale = torch.minimum(torch.ones_like(utilization), 1.0 / torch.clamp_min(utilization, 1.0e-12))
    tire_force = torch.stack((fx * scale, fy * scale), dim=-1)
    tire_moment = yaw_moment * scale

    velocity_world = rotate(vehicles[..., 3:5], vehicles[..., 2])
    vehicle_derivative = torch.empty_like(vehicles)
    vehicle_derivative[..., 0:2] = velocity_world
    vehicle_derivative[..., 2] = yaw_rate
    vehicle_derivative[..., 3] = (tire_force[..., 0] + connector["vehicle_force_body"][..., 0]) / model.vehicle_mass + yaw_rate * vy
    vehicle_derivative[..., 4] = (tire_force[..., 1] + connector["vehicle_force_body"][..., 1]) / model.vehicle_mass - yaw_rate * vx
    vehicle_derivative[..., 5] = (tire_moment + connector["vehicle_moment"]) / model.vehicle_inertia

    payload_velocity_world = rotate(payload[..., 3:5], payload[..., 2])
    payload_derivative = torch.empty_like(payload)
    payload_derivative[..., 0:2] = payload_velocity_world
    payload_derivative[..., 2] = payload[..., 5]
    payload_derivative[..., 3] = payload_accel_body[..., 0] + payload[..., 5] * payload[..., 4]
    payload_derivative[..., 4] = payload_accel_body[..., 1] - payload[..., 5] * payload[..., 3]
    payload_derivative[..., 5] = torch.sum(connector["payload_moment"], dim=1) / model.payload_inertia
    output = torch.cat((vehicle_derivative.reshape(-1, 24), payload_derivative), dim=1)
    if strict and not bool(torch.isfinite(output).all().item()):
        raise FloatingPointError("nonfinite torch derivative")
    return output


def rk4_step_batch(
    state: torch.Tensor,
    controls: torch.Tensor,
    dt: float,
    model: TorchModel,
    *,
    strict: bool = False,
) -> torch.Tensor:
    k1 = system_derivative_batch(state, controls, model, strict=strict)
    k2 = system_derivative_batch(state + 0.5 * dt * k1, controls, model, strict=strict)
    k3 = system_derivative_batch(state + 0.5 * dt * k2, controls, model, strict=strict)
    k4 = system_derivative_batch(state + dt * k3, controls, model, strict=strict)
    output = state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if strict and not bool(torch.isfinite(output).all().item()):
        raise FloatingPointError("nonfinite torch RK4 state")
    return output
