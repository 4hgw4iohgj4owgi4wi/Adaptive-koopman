"""Independent MPC baselines for the fixed three-vehicle transport task.

The proposed controller remains the learned Koopman-MPC with an RBF stability
margin cost.  This module supplies three physical-model baselines used only for
comparison:

``NMPC``
    Nominal nonlinear direct-shooting MPC.
``Tube-MPC``
    Nominal NMPC with input tightening and bounded ancillary feedback around
    an internally propagated nominal trajectory.
``Robust-MPC``
    Scenario min-max NMPC over explicit mass, tire-stiffness and friction
    vertices.

All three baselines use the same Frenet state order as the Koopman controller,
``[s, e_y, e_psi, v_x, v_y, r]``, and the same command order
``[steering, acceleration]``.  They do not call the RBF model or any archived
TF14 protection logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from time import perf_counter

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from config.vehicle_params import DycLinearParams
from src.cooperative_three_vehicle_control import (
    CooperativeErrors,
    FormationGeometry,
    vehicle_params_with_supported_load,
)
from src.path_tracking_control import ControlCommand, ReferencePath, TrackingConfig
from src.payload_force_proxy import PayloadSpec


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PhysicalUncertaintyVertex:
    """One parametric model used by scenario robust MPC."""

    name: str
    mass_scale: float = 1.0
    yaw_inertia_scale: float = 1.0
    cornering_stiffness_scale: float = 1.0
    friction_scale: float = 1.0

    def __post_init__(self) -> None:
        values = (
            self.mass_scale,
            self.yaw_inertia_scale,
            self.cornering_stiffness_scale,
            self.friction_scale,
        )
        if not self.name or any(not np.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("uncertainty vertex name and scales must be positive")


def default_robust_vertices() -> tuple[PhysicalUncertaintyVertex, ...]:
    """Return the uncertainty vertices used by the robust-MPC baseline.

    The bounds cover the formal experiment's 40 percent payload increase,
    40 percent cornering-stiffness loss and road-friction drop from 0.8 to
    0.35.  The combined corner prevents the optimizer from treating these
    uncertainties as mutually exclusive.
    """

    return (
        PhysicalUncertaintyVertex("nominal"),
        PhysicalUncertaintyVertex("payload_high", mass_scale=1.15, yaw_inertia_scale=1.20),
        PhysicalUncertaintyVertex("tire_soft", cornering_stiffness_scale=0.60),
        PhysicalUncertaintyVertex("low_mu", friction_scale=0.35 / 0.80),
        PhysicalUncertaintyVertex(
            "combined_corner",
            mass_scale=1.15,
            yaw_inertia_scale=1.20,
            cornering_stiffness_scale=0.70,
            friction_scale=0.35 / 0.80,
        ),
    )


@dataclass(frozen=True)
class PhysicalMPCConfig:
    """Shared finite-horizon settings for the three physical MPC baselines."""

    horizon_steps: int = 8
    control_blocks: int = 2
    max_iterations: int = 14
    function_tolerance: float = 1.0e-7
    state_weights: tuple[float, ...] = (0.15, 18.0, 5.0, 3.0, 0.4, 0.4)
    terminal_scale: float = 2.0
    formation_weight: float = 12.0
    input_weights: tuple[float, float] = (0.12, 0.04)
    input_rate_weights: tuple[float, float] = (0.35, 0.08)
    max_steer_rate_radps: float = 1.2
    max_accel_rate_mps3: float = 3.0
    robust_smooth_max_temperature: float = 1.0
    tube_steering_reserve_rad: float = np.deg2rad(4.0)
    tube_acceleration_reserve_mps2: float = 0.40
    tube_lateral_gain: float = 0.20
    tube_heading_gain: float = 0.70
    tube_lateral_velocity_gain: float = 0.025
    tube_yaw_rate_gain: float = 0.08
    tube_speed_gain: float = 0.55

    def __post_init__(self) -> None:
        if self.horizon_steps < 2 or self.control_blocks < 1:
            raise ValueError("horizon_steps must be >= 2 and control_blocks positive")
        if self.control_blocks > self.horizon_steps:
            raise ValueError("control_blocks cannot exceed horizon_steps")
        if self.max_iterations < 1 or self.function_tolerance <= 0.0:
            raise ValueError("optimizer settings must be positive")
        if len(self.state_weights) != 6 or len(self.input_weights) != 2 or len(self.input_rate_weights) != 2:
            raise ValueError("state and input weights have incompatible dimensions")
        if np.any(np.asarray(self.state_weights + self.input_weights + self.input_rate_weights) < 0.0):
            raise ValueError("MPC weights must be non-negative")


@dataclass
class PhysicalPredictiveMPCController:
    """Centralized nonlinear MPC with optional tube or min-max robust mode."""

    mode: str = "nmpc"
    mpc_config: PhysicalMPCConfig = field(default_factory=PhysicalMPCConfig)
    prediction_params: DycLinearParams = field(
        default_factory=lambda: vehicle_params_with_supported_load(
            DycLinearParams(), PayloadSpec().nominal_vertical_load_n
        )
    )
    uncertainty_vertices: tuple[PhysicalUncertaintyVertex, ...] = field(
        default_factory=default_robust_vertices
    )
    name: str = "NMPC"
    coordinate_frame: str = field(default="frenet", init=False)
    control_update_period_s: float | None = field(default=None, init=False)
    _warm_blocks: FloatArray | None = field(default=None, init=False, repr=False)
    _last_applied: FloatArray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False, repr=False
    )
    _tube_nominal_state: FloatArray | None = field(default=None, init=False, repr=False)
    last_status: str = field(default="not_run", init=False)
    last_objective: float = field(default=float("nan"), init=False)
    last_solver_time_ms: float = field(default=float("nan"), init=False)
    last_sqp_iterations: int = field(default=0, init=False)
    last_scenario_costs: dict[str, float] = field(default_factory=dict, init=False)
    last_tube_error_norm: float = field(default=float("nan"), init=False)

    def __post_init__(self) -> None:
        self.mode = str(self.mode).strip().lower()
        if self.mode not in {"nmpc", "tube", "robust"}:
            raise ValueError("mode must be one of: nmpc, tube, robust")
        if self.mode == "nmpc" and self.name == "NMPC":
            self.name = "Nonlinear MPC (NMPC)"
        elif self.mode == "tube" and self.name == "NMPC":
            self.name = "Tube MPC"
        elif self.mode == "robust" and self.name == "NMPC":
            self.name = "Scenario robust MPC"

    def reset(self) -> None:
        self._warm_blocks = None
        self._last_applied = np.zeros((3, 2), dtype=float)
        self._tube_nominal_state = None
        self.last_status = "not_run"
        self.last_objective = float("nan")
        self.last_solver_time_ms = float("nan")
        self.last_sqp_iterations = 0
        self.last_scenario_costs = {}
        self.last_tube_error_norm = float("nan")

    def compute(
        self,
        t_s: float,
        states: np.ndarray,
        errors: CooperativeErrors,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
    ) -> tuple[ControlCommand, ControlCommand, ControlCommand]:
        """Solve one receding-horizon problem and return three commands."""

        del t_s
        measured = cooperative_frenet_state(states, errors, path, geometry)
        initial = measured
        if self.mode == "tube":
            if self._tube_nominal_state is None:
                self._tube_nominal_state = measured.copy()
            initial = self._tube_nominal_state.copy()

        blocks, objective, result_status = self._solve(initial, path, geometry, config)
        nominal_control = blocks[:, 0, :].copy()
        applied = nominal_control.copy()

        if self.mode == "tube":
            state_error = measured - initial
            state_error[:, 2] = wrap_to_pi_array(state_error[:, 2])
            applied += self._tube_feedback(state_error)
            self.last_tube_error_norm = float(np.linalg.norm(state_error[:, 1:]))
            lower, upper = self._input_bounds(config, tightened=False)
            applied = np.clip(applied, lower, upper)
            curvature = interpolate_curvature(path, initial[:, 0])
            self._tube_nominal_state = frenet_rk2_step(
                initial,
                nominal_control,
                curvature,
                self.prediction_params,
                config.tire_mu,
                config.dt_s,
            )

        applied = self._enforce_first_move_rate(applied, config)
        self._last_applied = applied.copy()
        self._warm_blocks = shift_control_blocks(blocks)
        self.last_objective = float(objective)
        self.last_status = result_status
        return tuple(
            ControlCommand(acceleration_mps2=float(row[1]), steering_rad=float(row[0]))
            for row in applied
        )  # type: ignore[return-value]

    def _solve(
        self,
        initial: FloatArray,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
    ) -> tuple[FloatArray, float, str]:
        block_count = self.mpc_config.control_blocks
        if self._warm_blocks is None or self._warm_blocks.shape != (3, block_count, 2):
            guess = np.repeat(self._last_applied[:, None, :], block_count, axis=1)
        else:
            guess = self._warm_blocks.copy()

        lower, upper = self._input_bounds(config, tightened=self.mode == "tube")
        bounds = [(float(lower[j]), float(upper[j])) for _v in range(3) for _b in range(block_count) for j in range(2)]
        variants = self.uncertainty_vertices if self.mode == "robust" else (PhysicalUncertaintyVertex("nominal"),)

        lower_flat = np.tile(lower, 3 * block_count)
        upper_flat = np.tile(upper, 3 * block_count)

        def objective_with_gradient(flat: FloatArray) -> tuple[float, FloatArray]:
            """Evaluate all forward differences in one vectorized rollout."""

            center = np.asarray(flat, dtype=float)
            variable_count = center.size
            step = 1.0e-5
            candidates = np.repeat(center[None, :], variable_count + 1, axis=0)
            signed_steps = np.full(variable_count, step, dtype=float)
            signed_steps[center + step > upper_flat] = -step
            row = np.arange(variable_count) + 1
            candidates[row, np.arange(variable_count)] += signed_steps
            values = self._objective_batch(
                initial,
                candidates.reshape(variable_count + 1, 3, block_count, 2),
                path,
                geometry,
                config,
                variants,
            )
            gradient = (values[1:] - values[0]) / signed_steps
            return float(values[0]), np.asarray(gradient, dtype=float)

        started = perf_counter()
        result = minimize(
            objective_with_gradient,
            guess.reshape(-1),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={
                "maxiter": self.mpc_config.max_iterations,
                "ftol": self.mpc_config.function_tolerance,
                "maxls": 12,
            },
        )
        self.last_solver_time_ms = 1000.0 * (perf_counter() - started)
        self.last_sqp_iterations = int(getattr(result, "nit", 0))
        if result.x is None or not np.all(np.isfinite(result.x)) or not np.isfinite(result.fun):
            raise RuntimeError(f"{self.name} returned no finite optimizer iterate")

        blocks = np.asarray(result.x, dtype=float).reshape(3, block_count, 2)
        self.last_scenario_costs = {
            vertex.name: float(self._scenario_cost(initial, blocks, path, geometry, config, vertex))
            for vertex in variants
        }
        if bool(result.success):
            status = "solved"
        elif int(getattr(result, "status", -1)) == 1:
            status = "maximum iterations reached"
        else:
            # L-BFGS-B can stop its line search while still returning a finite,
            # bounded iterate.  Keep strict convergence separate from whether
            # the receding-horizon command is numerically usable.
            status = f"finite iterate (optimizer status {getattr(result, 'status', 'unknown')})"
        return blocks, float(result.fun), status

    def _objective_batch(
        self,
        initial: FloatArray,
        block_batch: FloatArray,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
        variants: tuple[PhysicalUncertaintyVertex, ...],
    ) -> FloatArray:
        scenario_costs = np.column_stack(
            [
                self._scenario_cost_batch(
                    initial, block_batch, path, geometry, config, vertex
                )
                for vertex in variants
            ]
        )
        if self.mode != "robust":
            return scenario_costs[:, 0]
        temperature = self.mpc_config.robust_smooth_max_temperature
        largest = np.max(scenario_costs, axis=1, keepdims=True)
        return (
            largest[:, 0]
            + temperature
            * np.log(np.sum(np.exp((scenario_costs - largest) / temperature), axis=1))
        )

    def _scenario_cost(
        self,
        initial: FloatArray,
        blocks: FloatArray,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
        vertex: PhysicalUncertaintyVertex,
    ) -> float:
        return float(
            self._scenario_cost_batch(
                initial,
                np.asarray(blocks, dtype=float)[None, ...],
                path,
                geometry,
                config,
                vertex,
            )[0]
        )

    def _scenario_cost_batch(
        self,
        initial: FloatArray,
        block_batch: FloatArray,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
        vertex: PhysicalUncertaintyVertex,
    ) -> FloatArray:
        """Roll out one model vertex for a batch of candidate control vectors."""

        parameters = replace(
            self.prediction_params,
            m=float(self.prediction_params.m * vertex.mass_scale),
            iz=float(self.prediction_params.iz * vertex.yaw_inertia_scale),
            kf=float(self.prediction_params.kf * vertex.cornering_stiffness_scale),
            kr=float(self.prediction_params.kr * vertex.cornering_stiffness_scale),
        )
        friction = float(np.clip(config.tire_mu * vertex.friction_scale, 0.05, 1.5))
        controls = expand_control_blocks(block_batch, self.mpc_config.horizon_steps)
        batch_size = controls.shape[0]
        state = np.broadcast_to(initial, (batch_size, 3, 6)).copy()
        target_front_s = float(initial[0, 0])
        offsets = geometry.offsets_front_body_m
        weights = np.asarray(self.mpc_config.state_weights, dtype=float)
        total = np.zeros(batch_size, dtype=float)
        previous = np.broadcast_to(self._last_applied, (batch_size, 3, 2)).copy()

        for step in range(self.mpc_config.horizon_steps):
            curvature = interpolate_curvature(path, state[..., 0])
            state = frenet_rk2_step(
                state,
                controls[:, :, step],
                curvature,
                parameters,
                friction,
                config.dt_s,
            )
            target_front_s += config.target_speed_mps * config.dt_s
            target = np.column_stack(
                (
                    target_front_s + offsets[:, 0],
                    offsets[:, 1],
                    np.zeros(3),
                    np.full(3, config.target_speed_mps),
                    np.zeros(3),
                    np.zeros(3),
                )
            )[None, ...]
            error = state - target
            error[..., 2] = wrap_to_pi_array(error[..., 2])
            scale = self.mpc_config.terminal_scale if step == self.mpc_config.horizon_steps - 1 else 1.0
            total += scale * np.sum(error * error * weights, axis=(1, 2))

            # Relative front-to-rear deformation directly measures how much the
            # common payload geometry is stretched or sheared.
            for rear in (1, 2):
                long_error = state[:, rear, 0] - state[:, 0, 0] - offsets[rear, 0]
                lat_error = state[:, rear, 1] - state[:, 0, 1] - offsets[rear, 1]
                total += self.mpc_config.formation_weight * (long_error**2 + lat_error**2)

            command = controls[:, :, step]
            total += np.sum(
                command * command * np.asarray(self.mpc_config.input_weights), axis=(1, 2)
            )
            rate = command - previous
            total += np.sum(
                rate * rate * np.asarray(self.mpc_config.input_rate_weights), axis=(1, 2)
            )
            previous = command
        return total

    def _input_bounds(self, config: TrackingConfig, *, tightened: bool) -> tuple[FloatArray, FloatArray]:
        steer_limit = float(config.max_steer_rad)
        accel_min = float(config.min_accel_mps2)
        accel_max = float(config.max_accel_mps2)
        if tightened:
            steer_limit = max(0.05, steer_limit - self.mpc_config.tube_steering_reserve_rad)
            accel_min += self.mpc_config.tube_acceleration_reserve_mps2
            accel_max -= self.mpc_config.tube_acceleration_reserve_mps2
        return np.array([-steer_limit, accel_min]), np.array([steer_limit, accel_max])

    def _tube_feedback(self, error: FloatArray) -> FloatArray:
        steering = -(
            self.mpc_config.tube_lateral_gain * error[:, 1]
            + self.mpc_config.tube_heading_gain * error[:, 2]
            + self.mpc_config.tube_lateral_velocity_gain * error[:, 4]
            + self.mpc_config.tube_yaw_rate_gain * error[:, 5]
        )
        acceleration = -self.mpc_config.tube_speed_gain * error[:, 3]
        steering = np.clip(
            steering,
            -self.mpc_config.tube_steering_reserve_rad,
            self.mpc_config.tube_steering_reserve_rad,
        )
        acceleration = np.clip(
            acceleration,
            -self.mpc_config.tube_acceleration_reserve_mps2,
            self.mpc_config.tube_acceleration_reserve_mps2,
        )
        return np.column_stack((steering, acceleration))

    def _enforce_first_move_rate(self, control: FloatArray, config: TrackingConfig) -> FloatArray:
        update_period = (
            float(config.dt_s)
            if self.control_update_period_s is None
            else float(self.control_update_period_s)
        )
        limit = np.array(
            [
                self.mpc_config.max_steer_rate_radps * update_period,
                self.mpc_config.max_accel_rate_mps3 * update_period,
            ],
            dtype=float,
        )
        return self._last_applied + np.clip(control - self._last_applied, -limit, limit)


def cooperative_frenet_state(
    states: np.ndarray,
    errors: CooperativeErrors,
    path: ReferencePath,
    geometry: FormationGeometry,
) -> FloatArray:
    """Build a coherent shared-path Frenet state for the complete formation."""

    values = np.asarray(states, dtype=float)
    if values.shape != (3, 6) or not np.all(np.isfinite(values)):
        raise ValueError("states must be finite with shape (3, 6)")
    front_s = float(path.s_m[errors.reference_index])
    offsets = geometry.offsets_front_body_m
    output = np.zeros((3, 6), dtype=float)
    output[0] = [front_s, errors.lateral_m[0], errors.heading_rad[0], *values[0, 3:6]]
    for vehicle in (1, 2):
        output[vehicle] = [
            front_s + offsets[vehicle, 0] + errors.longitudinal_m[vehicle],
            errors.lateral_m[0] + offsets[vehicle, 1] + errors.lateral_m[vehicle],
            errors.heading_rad[vehicle],
            *values[vehicle, 3:6],
        ]
    return output


def frenet_rhs(
    state: FloatArray,
    control: FloatArray,
    curvature_1pm: FloatArray,
    params: DycLinearParams,
    tire_mu: float,
) -> FloatArray:
    """Vectorized nonlinear dynamic-bicycle equations in Frenet coordinates."""

    x = np.asarray(state, dtype=float)
    u = np.asarray(control, dtype=float)
    curvature = np.asarray(curvature_1pm, dtype=float)
    if x.shape[-2:] != (3, 6) or u.shape[-2:] != (3, 2) or curvature.shape != x.shape[:-1]:
        raise ValueError(
            "Frenet predictor expects (..., 3, 6), (..., 3, 2), and (..., 3)"
        )
    lateral = x[..., 1]
    heading = x[..., 2]
    vx = x[..., 3]
    vy = x[..., 4]
    yaw_rate = x[..., 5]
    steering = u[..., 0]
    acceleration = u[..., 1]
    vx_safe = np.maximum(np.abs(vx), 0.2)
    lf, lr = float(params.a), float(params.b)
    mass, inertia = float(params.m), float(params.iz)
    cf, cr = abs(float(params.kf)), abs(float(params.kr))
    front_load = mass * params.g * lr / params.wheelbase
    rear_load = mass * params.g * lf / params.wheelbase
    alpha_front = steering - np.arctan2(vy + lf * yaw_rate, vx_safe)
    alpha_rear = -np.arctan2(vy - lr * yaw_rate, vx_safe)
    front_limit = max(float(tire_mu) * front_load, 1.0e-9)
    rear_limit = max(float(tire_mu) * rear_load, 1.0e-9)
    force_front = front_limit * np.tanh(cf * alpha_front / front_limit)
    force_rear = rear_limit * np.tanh(cr * alpha_rear / rear_limit)

    denominator = np.maximum(1.0 - curvature * lateral, 0.20)
    progress_rate = (vx * np.cos(heading) - vy * np.sin(heading)) / denominator
    lateral_rate = vx * np.sin(heading) + vy * np.cos(heading)
    heading_rate = yaw_rate - curvature * progress_rate
    vx_rate = acceleration + yaw_rate * vy - force_front * np.sin(steering) / mass
    vy_rate = (force_front * np.cos(steering) + force_rear) / mass - yaw_rate * vx
    yaw_rate_dot = (lf * force_front * np.cos(steering) - lr * force_rear) / inertia
    return np.stack(
        (progress_rate, lateral_rate, heading_rate, vx_rate, vy_rate, yaw_rate_dot),
        axis=-1,
    )


def frenet_rk2_step(
    state: FloatArray,
    control: FloatArray,
    curvature_1pm: FloatArray,
    params: DycLinearParams,
    tire_mu: float,
    dt_s: float,
) -> FloatArray:
    """Second-order midpoint integration used inside the real-time optimizer."""

    first = frenet_rhs(state, control, curvature_1pm, params, tire_mu)
    midpoint = state + 0.5 * float(dt_s) * first
    second = frenet_rhs(midpoint, control, curvature_1pm, params, tire_mu)
    output = state + float(dt_s) * second
    output[..., 2] = wrap_to_pi_array(output[..., 2])
    output[..., 3] = np.maximum(output[..., 3], 0.2)
    output[..., 4] = np.clip(output[..., 4], -8.0, 8.0)
    output[..., 5] = np.clip(output[..., 5], -2.5, 2.5)
    return output


def interpolate_curvature(path: ReferencePath, progress_m: FloatArray) -> FloatArray:
    return np.interp(
        np.asarray(progress_m, dtype=float),
        np.asarray(path.s_m, dtype=float),
        np.asarray(path.curvature_1pm, dtype=float),
    )


def expand_control_blocks(blocks: FloatArray, horizon_steps: int) -> FloatArray:
    """Expand piecewise-constant control blocks to every prediction step."""

    values = np.asarray(blocks, dtype=float)
    block_count = values.shape[-2]
    indices = np.minimum(
        np.arange(horizon_steps, dtype=int) * block_count // horizon_steps,
        block_count - 1,
    )
    return np.take(values, indices, axis=-2)


def shift_control_blocks(blocks: FloatArray) -> FloatArray:
    values = np.asarray(blocks, dtype=float)
    return np.concatenate((values[:, 1:, :], values[:, -1:, :]), axis=1)


def wrap_to_pi_array(values: FloatArray) -> FloatArray:
    return (np.asarray(values, dtype=float) + np.pi) % (2.0 * np.pi) - np.pi


def build_physical_mpc_baseline(
    method_id: str,
    mpc_config: PhysicalMPCConfig | None = None,
) -> PhysicalPredictiveMPCController:
    """Construct one named comparison baseline from its experiment identifier."""

    settings = mpc_config or PhysicalMPCConfig()
    normalized = str(method_id).strip().upper()
    if normalized == "NMPC":
        return PhysicalPredictiveMPCController("nmpc", settings, name="Nonlinear MPC (NMPC)")
    if normalized == "TMPC":
        return PhysicalPredictiveMPCController("tube", settings, name="Tube MPC")
    if normalized == "RMPC":
        return PhysicalPredictiveMPCController("robust", settings, name="Scenario robust MPC")
    raise KeyError(f"unknown physical MPC baseline: {method_id}")
