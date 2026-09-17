"""System-reference MPC with three independent adaptive Koopman-RBF MPCs.

The layers have deliberately different contracts:

* :class:`SystemReferenceMPC` coordinates the transported payload and returns
  per-vehicle Frenet reference trajectories.  It never returns actuator
  commands.
* :class:`IndependentAdaptiveKoopmanRbfMPC` owns one MPC state, one warm start,
  and one Koopman model snapshot per vehicle.  RBF stability margins enter the
  three local objectives, not a centralized steering allocator.
* :class:`IndependentActuatorMPC` remains the innermost actuator tracker.

Plant commands include uphill gravity compensation, whereas the Koopman model
and online adaptation use the net tangent acceleration seen by the plant.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Any

import numpy as np
import osqp
from scipy import sparse

from src.controllers.hierarchical_mpc import IndependentActuatorMPC
from src.cooperative_three_vehicle_control import CooperativeErrors, FormationGeometry
from src.koopman.bilinear_dynamics import BilinearKoopmanDynamics
from src.koopman.coupled_state import CoupledStateTail, build_coupled_state_tail
from src.koopman.fast_physical_context import (
    FastPhysicalContextConfig,
    FastPhysicalContextHorizon,
    NonlinearPhysicsContextBatch,
    NonlinearPhysicsContextPredictor,
    NonlinearPhysicsRolloutConfig,
    NonlinearPhysicsRolloutSnapshot,
    context_identity_lifted_rows,
    predict_fast_physical_context,
)
from src.koopman.model_bank import VEHICLE_NAMES, ThreeVehicleModelBank
from src.koopman.online_adapter import OnlineAdaptationConfig
from src.koopman.runtime_adaptation import AsyncThreeVehicleAdaptationRuntime
from src.koopman.state_adapter import KoopmanStateAdapter
from src.path_tracking_control import ControlCommand, ReferencePath, TrackingConfig
from src.payload_force_proxy import (
    PayloadForceConfig,
    PayloadForceDiagnostics,
    PayloadSpec,
    compute_payload_force_diagnostics,
)
from src.rbf_feature_builder import (
    RBF_INPUT_COLUMNS_NEW_PHYSICAL_CONNECTOR_22,
    RBF_INPUT_COLUMNS_THREE_VEHICLE,
    build_new_physical_connector_rbf_feature_row,
    build_rbf_feature_row,
)
from src.rbf_model import RBFBoundaryModel
from src.rbf_safety_layer import (
    evaluate_rbf_boundary_batch,
    stability_margin,
)


@dataclass(frozen=True)
class VehicleReferenceHorizon:
    """Upper-layer output in Frenet coordinates, never actuator commands."""

    target_states: np.ndarray
    world_heading_rad: np.ndarray
    curvature_1pm: np.ndarray
    feedforward_controls: np.ndarray
    target_speed_mps: np.ndarray
    reference_s_m: np.ndarray

    def __post_init__(self) -> None:
        target = np.asarray(self.target_states, dtype=float)
        if target.ndim != 3 or target.shape[0] != 3 or target.shape[2] != 6:
            raise ValueError("target_states must have shape (3, horizon, 6)")
        horizon = target.shape[1]
        expected = (3, horizon)
        if np.asarray(self.world_heading_rad).shape != expected:
            raise ValueError("world_heading_rad must have shape (3, horizon)")
        if np.asarray(self.curvature_1pm).shape != expected:
            raise ValueError("curvature_1pm must have shape (3, horizon)")
        if np.asarray(self.feedforward_controls).shape != (3, horizon, 2):
            raise ValueError("feedforward_controls must have shape (3, horizon, 2)")
        if np.asarray(self.target_speed_mps).shape != expected:
            raise ValueError("target_speed_mps must have shape (3, horizon)")
        if np.asarray(self.reference_s_m).shape != expected:
            raise ValueError("reference_s_m must have shape (3, horizon)")
        for values in (
            target,
            self.world_heading_rad,
            self.curvature_1pm,
            self.feedforward_controls,
            self.target_speed_mps,
            self.reference_s_m,
        ):
            if not np.all(np.isfinite(values)):
                raise ValueError("reference horizon must contain only finite values")


@dataclass(frozen=True)
class SystemStabilityFeedback:
    """Measured risk information returned from the vehicle layer to the system layer."""

    rbf_margin: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=float))
    vertical_load_ratio: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=float))
    connection_ratio: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    local_solver_feasible: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=bool))

    def __post_init__(self) -> None:
        for name in ("rbf_margin", "vertical_load_ratio", "connection_ratio"):
            values = np.asarray(getattr(self, name), dtype=float)
            if values.shape != (3,):
                raise ValueError(f"{name} must have shape (3,)")
        if np.asarray(self.local_solver_feasible, dtype=bool).shape != (3,):
            raise ValueError("local_solver_feasible must have shape (3,)")


@dataclass(frozen=True)
class SystemReferenceMPCConfig:
    """System-level reference-governor MPC settings."""

    horizon_steps: int = 10
    heading_weight: float = 28.0
    speed_weight: float = 12.0
    heading_rate_weight: float = 5.0
    speed_rate_weight: float = 3.0
    heading_agreement_weight: float = 8.0
    speed_agreement_weight: float = 5.0
    lateral_feedback_gain: float = 0.42
    heading_feedback_gain: float = 0.85
    longitudinal_speed_gain: float = 0.30
    maximum_heading_correction_rad: float = 0.35
    maximum_heading_rate_radps: float = 0.65
    maximum_speed_rate_mps2: float = 1.5
    enable_risk_speed_scaling: bool = False
    minimum_speed_scale: float = 0.65
    rbf_slowdown_start_margin: float = 0.10
    connection_slowdown_start_ratio: float = 0.75
    support_slowdown_start_ratio: float = 0.25
    solver_tolerance: float = 1.0e-6
    solver_maximum_iterations: int = 3000

    def __post_init__(self) -> None:
        if self.horizon_steps < 2:
            raise ValueError("system reference horizon must be at least two")
        if not 0.0 < self.minimum_speed_scale <= 1.0:
            raise ValueError("minimum_speed_scale must be in (0, 1]")


@dataclass
class SystemReferenceMPC:
    """Coordinate the payload by optimizing heading and speed references."""

    config: SystemReferenceMPCConfig = field(default_factory=SystemReferenceMPCConfig)
    last_status: str = field(default="not_run", init=False)
    last_objective: float = field(default=float("nan"), init=False)
    last_solver_time_ms: float = field(default=float("nan"), init=False)
    last_control_deadline_met: bool = field(default=False, init=False)
    last_runtime_classification: str = field(
        default="not_run",
        init=False,
    )
    last_speed_scale: float = field(default=1.0, init=False)
    last_reference: VehicleReferenceHorizon | None = field(default=None, init=False)
    _previous_first_move: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False, repr=False
    )
    _warm_solution: np.ndarray | None = field(default=None, init=False, repr=False)
    _adapter: KoopmanStateAdapter = field(
        default_factory=lambda: KoopmanStateAdapter(search_window_segments=120),
        init=False,
        repr=False,
    )

    def reset(self) -> None:
        self.last_status = "not_run"
        self.last_objective = float("nan")
        self.last_solver_time_ms = float("nan")
        self.last_control_deadline_met = False
        self.last_runtime_classification = "not_run"
        self.last_speed_scale = 1.0
        self.last_reference = None
        self._previous_first_move = np.zeros((3, 2), dtype=float)
        self._warm_solution = None

    def compute(
        self,
        states: np.ndarray,
        errors: CooperativeErrors,
        path: ReferencePath,
        geometry: FormationGeometry,
        tracking: TrackingConfig,
        feedback: SystemStabilityFeedback,
    ) -> VehicleReferenceHorizon:
        """Return per-vehicle ``[s,e_y,e_psi,vx,vy,r]`` references."""

        cfg = self.config
        horizon = cfg.horizon_steps
        dt = float(tracking.dt_s)
        current_frenet = np.vstack(
            [
                self._adapter.world_to_koopman(
                    states[index], path, reference_index=errors.reference_index
                )
                for index in range(3)
            ]
        )
        speed_scale = self._risk_speed_scale(feedback)
        self.last_speed_scale = speed_scale
        common_speed = max(
            float(tracking.min_speed_mps),
            float(tracking.target_speed_mps) * speed_scale,
        )

        desired_heading = np.clip(
            -cfg.lateral_feedback_gain * np.asarray(errors.lateral_m)
            - cfg.heading_feedback_gain * np.asarray(errors.heading_rad),
            -cfg.maximum_heading_correction_rad,
            cfg.maximum_heading_correction_rad,
        )
        desired_speed = np.full(3, common_speed, dtype=float)
        desired_speed[1:] -= cfg.longitudinal_speed_gain * np.asarray(
            errors.longitudinal_m[1:], dtype=float
        )
        desired_speed = np.clip(
            desired_speed,
            max(tracking.min_speed_mps, common_speed * 0.75),
            common_speed * 1.15,
        )
        if self.last_status == "not_run":
            self._previous_first_move[:, 0] = 0.0
            self._previous_first_move[:, 1] = np.asarray(states[:, 3], dtype=float)

        n_variables = 3 * horizon * 2
        p_matrix = np.eye(n_variables, dtype=float) * 1.0e-9
        q_vector = np.zeros(n_variables, dtype=float)

        def selector(vehicle: int, step: int) -> np.ndarray:
            matrix = np.zeros((2, n_variables), dtype=float)
            start = (vehicle * horizon + step) * 2
            matrix[:, start : start + 2] = np.eye(2)
            return matrix

        selectors = tuple(
            tuple(selector(vehicle, step) for step in range(horizon))
            for vehicle in range(3)
        )
        state_weight = np.array([cfg.heading_weight, cfg.speed_weight], dtype=float)
        rate_weight = np.array(
            [cfg.heading_rate_weight, cfg.speed_rate_weight], dtype=float
        )
        target = np.column_stack([desired_heading, desired_speed])
        for vehicle in range(3):
            previous_map = np.zeros((2, n_variables), dtype=float)
            previous_value = self._previous_first_move[vehicle]
            for step in range(horizon):
                p_matrix, q_vector = _add_residual(
                    p_matrix,
                    q_vector,
                    selectors[vehicle][step],
                    -target[vehicle],
                    state_weight,
                )
                p_matrix, q_vector = _add_residual(
                    p_matrix,
                    q_vector,
                    selectors[vehicle][step] - previous_map,
                    -previous_value,
                    rate_weight,
                )
                previous_map = selectors[vehicle][step]
                previous_value = np.zeros(2, dtype=float)
        for vehicle in (1, 2):
            for step in range(horizon):
                agreement = selectors[vehicle][step] - selectors[0][step]
                p_matrix, q_vector = _add_residual(
                    p_matrix,
                    q_vector,
                    agreement,
                    np.zeros(2),
                    np.array(
                        [cfg.heading_agreement_weight, cfg.speed_agreement_weight]
                    ),
                )

        identity = np.eye(n_variables, dtype=float)
        lower_one = np.array(
            [-cfg.maximum_heading_correction_rad, tracking.min_speed_mps]
        )
        upper_one = np.array(
            [cfg.maximum_heading_correction_rad, tracking.target_speed_mps * 1.20]
        )
        rate_one = np.array(
            [cfg.maximum_heading_rate_radps * dt, cfg.maximum_speed_rate_mps2 * dt]
        )
        difference = _difference_matrix(3, horizon)
        difference_offset = np.zeros(n_variables, dtype=float)
        for vehicle in range(3):
            difference_offset[(vehicle * horizon) * 2 : (vehicle * horizon) * 2 + 2] = (
                -self._previous_first_move[vehicle]
            )
        constraint = sparse.vstack(
            [sparse.csc_matrix(identity), sparse.csc_matrix(difference)], format="csc"
        )
        lower = np.concatenate(
            [
                np.tile(lower_one, 3 * horizon),
                np.tile(-rate_one, 3 * horizon) - difference_offset,
            ]
        )
        upper = np.concatenate(
            [
                np.tile(upper_one, 3 * horizon),
                np.tile(rate_one, 3 * horizon) - difference_offset,
            ]
        )
        solver = osqp.OSQP()
        solver.setup(
            P=sparse.csc_matrix((p_matrix + p_matrix.T) * 0.5),
            q=q_vector,
            A=constraint,
            l=lower,
            u=upper,
            eps_abs=cfg.solver_tolerance,
            eps_rel=cfg.solver_tolerance,
            max_iter=cfg.solver_maximum_iterations,
            polishing=False,
            verbose=False,
        )
        if self._warm_solution is not None:
            solver.warm_start(x=self._warm_solution.reshape(-1))
        started = perf_counter()
        result = solver.solve(raise_error=False)
        self.last_solver_time_ms = 1000.0 * (perf_counter() - started)
        self.last_status = str(result.info.status).lower()
        if result.x is None or self.last_status not in {"solved", "solved inaccurate"}:
            raise RuntimeError(f"system reference MPC failed: {result.info.status}")
        solution = np.asarray(result.x, dtype=float).reshape(3, horizon, 2)
        self.last_objective = float(result.info.obj_val)
        self._previous_first_move = solution[:, 0].copy()
        self._warm_solution = np.concatenate(
            [solution[:, 1:, :], solution[:, -1:, :]], axis=1
        )
        self.last_reference = self._build_reference(
            solution, current_frenet, path, geometry, tracking
        )
        return self.last_reference

    def _risk_speed_scale(self, feedback: SystemStabilityFeedback) -> float:
        cfg = self.config
        if not cfg.enable_risk_speed_scaling:
            return 1.0
        finite_margin = np.asarray(feedback.rbf_margin, dtype=float)
        finite_margin = finite_margin[np.isfinite(finite_margin)]
        if finite_margin.size:
            rbf_scale = np.clip(
                np.min(finite_margin) / max(cfg.rbf_slowdown_start_margin, 1.0e-9),
                cfg.minimum_speed_scale,
                1.0,
            )
        else:
            rbf_scale = 1.0
        connection = np.asarray(feedback.connection_ratio, dtype=float)
        connection = connection[np.isfinite(connection)]
        if connection.size:
            excess = max(float(np.max(connection)) - cfg.connection_slowdown_start_ratio, 0.0)
            connection_scale = np.clip(1.0 - excess, cfg.minimum_speed_scale, 1.0)
        else:
            connection_scale = 1.0
        support = np.asarray(feedback.vertical_load_ratio, dtype=float)
        support = support[np.isfinite(support)]
        if support.size:
            support_scale = np.clip(
                float(np.min(support)) / max(cfg.support_slowdown_start_ratio, 1.0e-9),
                cfg.minimum_speed_scale,
                1.0,
            )
        else:
            support_scale = 1.0
        feasible_scale = 1.0 if np.all(feedback.local_solver_feasible) else cfg.minimum_speed_scale
        return float(min(rbf_scale, connection_scale, support_scale, feasible_scale))

    def _build_reference(
        self,
        solution: np.ndarray,
        current_frenet: np.ndarray,
        path: ReferencePath,
        geometry: FormationGeometry,
        tracking: TrackingConfig,
    ) -> VehicleReferenceHorizon:
        horizon = solution.shape[1]
        dt = float(tracking.dt_s)
        offsets = geometry.offsets_front_body_m
        reference_s = np.empty((3, horizon), dtype=float)
        target_states = np.empty((3, horizon, 6), dtype=float)
        world_heading = np.empty((3, horizon), dtype=float)
        curvature = np.empty((3, horizon), dtype=float)
        feedforward = np.empty((3, horizon, 2), dtype=float)
        for vehicle in range(3):
            progress = float(current_frenet[0, 0] + offsets[vehicle, 0])
            previous_speed = float(current_frenet[vehicle, 3])
            for step in range(horizon):
                heading_correction, speed = solution[vehicle, step]
                progress += float(speed) * dt
                progress = float(np.clip(progress, path.s_m[0], path.s_m[-1]))
                yaw = float(np.interp(progress, path.s_m, np.unwrap(path.yaw_rad)))
                kappa = float(np.interp(progress, path.s_m, path.curvature_1pm))
                acceleration = (float(speed) - previous_speed) / dt
                previous_speed = float(speed)
                reference_s[vehicle, step] = progress
                curvature[vehicle, step] = kappa
                world_heading[vehicle, step] = yaw + float(heading_correction)
                target_states[vehicle, step] = [
                    progress,
                    offsets[vehicle, 1],
                    heading_correction,
                    speed,
                    0.0,
                    speed * kappa,
                ]
                feedforward[vehicle, step] = [
                    np.arctan(float(tracking.wheelbase_m) * kappa),
                    acceleration,
                ]
        return VehicleReferenceHorizon(
            target_states=target_states,
            world_heading_rad=world_heading,
            curvature_1pm=curvature,
            feedforward_controls=feedforward,
            target_speed_mps=solution[:, :, 1].copy(),
            reference_s_m=reference_s,
        )


@dataclass(frozen=True)
class LocalAdaptiveKoopmanMPCConfig:
    """Identical settings used by each independent vehicle MPC."""

    horizon_steps: int = 8
    sqp_iterations: int = 2
    state_weights: tuple[float, ...] = (0.15, 24.0, 8.0, 4.0, 0.8, 0.8)
    terminal_scale: float = 2.0
    input_weights: tuple[float, float] = (0.10, 0.05)
    input_rate_weights: tuple[float, float] = (0.50, 0.12)
    stabilizing_reference_weights: tuple[float, float] = (2.0, 0.5)
    stabilizing_lateral_gain: float = 0.35
    stabilizing_heading_gain: float = 1.20
    stabilizing_yaw_rate_gain: float = 0.15
    stabilizing_speed_gain: float = 1.0
    stabilizing_decay_steps: float = 5.0
    maximum_steering_rate_radps: float = 1.4
    maximum_acceleration_rate_mps3: float = 3.0
    enable_rbf_cost: bool = False
    rbf_cost_weight: float = 45.0
    rbf_activation_margin: float = 0.20
    rbf_target_margin: float = 0.08
    rbf_minimum_linearization_margin: float = -0.50
    rbf_maximum_gradient_norm: float = 4.0
    rbf_safety_scale: float = 0.85
    rbf_finite_difference_steer_rad: float = 0.01
    rbf_finite_difference_acceleration_mps2: float = 0.05
    rbf_beta_derivative_time_constant_s: float = 0.08
    rbf_strict_training_domain: bool = False
    fast_physical_context_mode: str = "measured_constant"
    fast_physical_context_validation_passed: bool = False
    nonlinear_physics_substep_s: float = 0.001
    nonlinear_physics_gpu_batch_threshold: int = 8
    nonlinear_physics_prefer_cuda: bool = True
    nonlinear_physics_require_cuda: bool = False
    nonlinear_physics_realtime_deadline_ms: float = 25.0
    progress_recenter_m: float | None = 28.681157
    solver_tolerance: float = 1.0e-5
    solver_maximum_iterations: int = 4000

    def __post_init__(self) -> None:
        if self.horizon_steps < 1 or self.sqp_iterations < 1:
            raise ValueError("local horizon and SQP iterations must be positive")
        if len(self.state_weights) != 6:
            raise ValueError("local state_weights must follow [s,e_y,e_psi,vx,vy,r]")
        if len(self.stabilizing_reference_weights) != 2:
            raise ValueError("stabilizing_reference_weights must contain steering and acceleration weights")
        if self.stabilizing_decay_steps <= 0.0:
            raise ValueError("stabilizing_decay_steps must be positive")
        if self.rbf_target_margin > self.rbf_activation_margin:
            raise ValueError("RBF target margin cannot exceed activation margin")
        if self.rbf_minimum_linearization_margin >= self.rbf_activation_margin:
            raise ValueError("RBF minimum linearization margin must be below activation margin")
        if self.rbf_maximum_gradient_norm <= 0.0:
            raise ValueError("rbf_maximum_gradient_norm must be positive")
        if self.fast_physical_context_mode not in {
            "measured_constant",
            "first_order_physics",
            "nonlinear_physics_rollout",
        }:
            raise ValueError(
                "fast_physical_context_mode must be measured_constant, "
                "first_order_physics or nonlinear_physics_rollout"
            )
        nonlinear_values = (
            self.nonlinear_physics_substep_s,
            self.nonlinear_physics_gpu_batch_threshold,
            self.nonlinear_physics_realtime_deadline_ms,
        )
        if any(
            float(value) <= 0.0 or not np.isfinite(value)
            for value in nonlinear_values
        ):
            raise ValueError("nonlinear physics timing and batch limits must be positive")
        if self.progress_recenter_m is not None and not np.isfinite(
            self.progress_recenter_m
        ):
            raise ValueError("progress_recenter_m must be finite or None")


@dataclass
class IndependentAdaptiveKoopmanRbfMPC:
    """Three independent local MPCs backed by isolated online Koopman models."""

    model_bank: ThreeVehicleModelBank
    lifting: Any
    rbf_model: RBFBoundaryModel
    payload: PayloadSpec
    config: LocalAdaptiveKoopmanMPCConfig = field(
        default_factory=LocalAdaptiveKoopmanMPCConfig
    )
    _adapter: KoopmanStateAdapter = field(
        default_factory=lambda: KoopmanStateAdapter(search_window_segments=120),
        init=False,
        repr=False,
    )
    _warm_controls: list[np.ndarray | None] = field(
        default_factory=lambda: [None, None, None], init=False, repr=False
    )
    _last_applied: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False, repr=False
    )
    _previous_beta_deg: np.ndarray = field(
        default_factory=lambda: np.zeros(3, dtype=float), init=False, repr=False
    )
    last_statuses: tuple[str, str, str] = field(
        default=("not_run", "not_run", "not_run"), init=False
    )
    last_objectives: np.ndarray = field(
        default_factory=lambda: np.full(3, np.nan), init=False
    )
    last_solve_time_ms: np.ndarray = field(
        default_factory=lambda: np.full(3, np.nan), init=False
    )
    last_rbf_min_margin: np.ndarray = field(
        default_factory=lambda: np.full(3, np.nan), init=False
    )
    last_rbf_slack: np.ndarray = field(default_factory=lambda: np.zeros(3), init=False)
    last_rbf_cost: np.ndarray = field(default_factory=lambda: np.zeros(3), init=False)
    last_rbf_active_count: np.ndarray = field(
        default_factory=lambda: np.zeros(3, dtype=int), init=False
    )
    last_rbf_support_fraction: np.ndarray = field(
        default_factory=lambda: np.full(3, np.nan), init=False
    )
    last_model_versions: np.ndarray = field(
        default_factory=lambda: np.zeros(3, dtype=int), init=False
    )
    last_rbf_runtime_backends: tuple[str, str, str] = field(
        default=("not_run", "not_run", "not_run"), init=False
    )
    connector_working_penetration_m: float = field(
        default=0.0013, init=False, repr=False
    )
    payload_roll_limit_rad: float = field(
        default=float(np.deg2rad(8.0)), init=False, repr=False
    )
    payload_roll_rate_limit_radps: float = field(
        default=float(np.deg2rad(25.0)), init=False, repr=False
    )
    _latest_max_tire_utilization: np.ndarray = field(
        default_factory=lambda: np.zeros(3), init=False, repr=False
    )
    _latest_min_wheel_load_ratio: np.ndarray = field(
        default_factory=lambda: np.ones(3), init=False, repr=False
    )
    _previous_min_wheel_load_ratio: np.ndarray = field(
        default_factory=lambda: np.ones(3), init=False, repr=False
    )
    _current_fast_context_tail: CoupledStateTail | None = field(
        default=None, init=False, repr=False
    )
    _previous_fast_context_tail: CoupledStateTail | None = field(
        default=None, init=False, repr=False
    )
    _connector_ultimate_force_n: float = field(
        default=19_500.0, init=False, repr=False
    )
    _nonlinear_context_predictor: NonlinearPhysicsContextPredictor = field(
        default_factory=NonlinearPhysicsContextPredictor,
        init=False,
        repr=False,
    )
    _current_planned_controls: list[np.ndarray | None] = field(
        default_factory=lambda: [None, None, None],
        init=False,
        repr=False,
    )
    last_fast_physical_context: FastPhysicalContextHorizon | None = field(
        default=None, init=False
    )
    last_fast_physical_context_mode: str = field(
        default="not_run", init=False
    )
    last_fast_physical_context_time_ms: float = field(
        default=0.0,
        init=False,
    )
    last_fast_physical_context_backends: tuple[str, ...] = field(
        default=(),
        init=False,
    )
    last_fast_physical_context_realtime: str = field(
        default="not_run",
        init=False,
    )

    def reset(self) -> None:
        self._warm_controls = [None, None, None]
        self._last_applied = np.zeros((3, 2), dtype=float)
        self._previous_beta_deg = np.zeros(3, dtype=float)
        self.last_statuses = ("not_run", "not_run", "not_run")
        self.last_objectives = np.full(3, np.nan)
        self.last_solve_time_ms = np.full(3, np.nan)
        self.last_rbf_min_margin = np.full(3, np.nan)
        self.last_rbf_slack = np.zeros(3)
        self.last_rbf_cost = np.zeros(3)
        self.last_rbf_active_count = np.zeros(3, dtype=int)
        self.last_rbf_support_fraction = np.full(3, np.nan)
        self.last_model_versions = np.zeros(3, dtype=int)
        self.last_rbf_runtime_backends = ("not_run", "not_run", "not_run")
        self._latest_max_tire_utilization = np.zeros(3)
        self._latest_min_wheel_load_ratio = np.ones(3)
        self._previous_min_wheel_load_ratio = np.ones(3)
        self._current_fast_context_tail = None
        self._previous_fast_context_tail = None
        self._current_planned_controls = [None, None, None]
        self._nonlinear_context_predictor = NonlinearPhysicsContextPredictor()
        self.last_fast_physical_context = None
        self.last_fast_physical_context_mode = "not_run"
        self.last_fast_physical_context_time_ms = 0.0
        self.last_fast_physical_context_backends = ()
        self.last_fast_physical_context_realtime = "not_run"

    def set_physical_limits(
        self,
        *,
        connector_working_penetration_m: float,
        payload_roll_limit_rad: float,
        payload_roll_rate_limit_radps: float,
    ) -> None:
        values = np.asarray(
            [
                connector_working_penetration_m,
                payload_roll_limit_rad,
                payload_roll_rate_limit_radps,
            ],
            dtype=float,
        )
        if np.any(~np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("new-object RBF physical limits must be finite and positive")
        self.connector_working_penetration_m = float(values[0])
        self.payload_roll_limit_rad = float(values[1])
        self.payload_roll_rate_limit_radps = float(values[2])

    def set_fast_physical_context_observation(
        self,
        current_tail: CoupledStateTail,
        previous_tail: CoupledStateTail | None,
        *,
        connector_ultimate_force_n: float,
    ) -> None:
        """Attach measured fast states without changing the controller layers."""

        if not isinstance(current_tail, CoupledStateTail):
            raise TypeError("current_tail must be a CoupledStateTail")
        if previous_tail is not None and not isinstance(
            previous_tail, CoupledStateTail
        ):
            raise TypeError("previous_tail must be a CoupledStateTail or None")
        ultimate_force = float(connector_ultimate_force_n)
        if not np.isfinite(ultimate_force) or ultimate_force <= 0.0:
            raise ValueError("connector ultimate force must be finite and positive")
        self._current_fast_context_tail = current_tail
        self._previous_fast_context_tail = previous_tail
        self._connector_ultimate_force_n = ultimate_force

    def set_nonlinear_physics_observation(
        self,
        snapshot: NonlinearPhysicsRolloutSnapshot,
    ) -> None:
        """Attach the complete measured plant for candidate-specific rollout."""

        desired_config = NonlinearPhysicsRolloutConfig(
            horizon_steps=self.config.horizon_steps,
            control_dt_s=float(snapshot.tracking.dt_s),
            physics_substep_s=self.config.nonlinear_physics_substep_s,
            gpu_batch_threshold=(
                self.config.nonlinear_physics_gpu_batch_threshold
            ),
            prefer_cuda=self.config.nonlinear_physics_prefer_cuda,
            require_cuda=self.config.nonlinear_physics_require_cuda,
            realtime_deadline_ms=(
                self.config.nonlinear_physics_realtime_deadline_ms
            ),
        )
        if self._nonlinear_context_predictor.config != desired_config:
            self._nonlinear_context_predictor = (
                NonlinearPhysicsContextPredictor(desired_config)
            )
        self._nonlinear_context_predictor.set_snapshot(snapshot)

    def set_wheel_observation(
        self,
        wheel_friction_utilization: np.ndarray,
        wheel_vertical_loads_n: np.ndarray,
        effective_vehicle_mass_kg: np.ndarray,
        gravity_mps2: float,
    ) -> None:
        utilization = np.asarray(wheel_friction_utilization, dtype=float)
        loads = np.asarray(wheel_vertical_loads_n, dtype=float)
        masses = np.asarray(effective_vehicle_mass_kg, dtype=float)
        gravity = float(gravity_mps2)
        if utilization.shape != (3, 4) or loads.shape != (3, 4):
            raise ValueError("wheel observations must have shape (3, 4)")
        if masses.shape != (3,) or gravity <= 0.0:
            raise ValueError("effective masses must have shape (3,) and gravity must be positive")
        if (
            np.any(~np.isfinite(utilization))
            or np.any(~np.isfinite(loads))
            or np.any(~np.isfinite(masses))
            or np.any(masses <= 0.0)
        ):
            raise ValueError("wheel observations must be finite with positive masses")
        nominal = masses * gravity / 4.0
        self._previous_min_wheel_load_ratio = (
            self._latest_min_wheel_load_ratio.copy()
        )
        self._latest_max_tire_utilization = np.max(utilization, axis=1)
        self._latest_min_wheel_load_ratio = np.min(loads, axis=1) / nominal

    def _predict_fast_physical_context(
        self,
        tracking: TrackingConfig,
    ) -> FastPhysicalContextHorizon | None:
        if self.config.fast_physical_context_mode == "nonlinear_physics_rollout":
            if self._nonlinear_context_predictor.snapshot is None:
                self.last_fast_physical_context = None
                self.last_fast_physical_context_mode = "unavailable"
                return None
            self.last_fast_physical_context = None
            self.last_fast_physical_context_mode = (
                "nonlinear_physics_rollout"
            )
            return None
        if self._current_fast_context_tail is None:
            self.last_fast_physical_context = None
            self.last_fast_physical_context_mode = "unavailable"
            return None
        current = np.column_stack(
            [np.zeros((3, 6), dtype=float), self._current_fast_context_tail.values]
        )
        previous = None
        if self._previous_fast_context_tail is not None:
            previous = np.column_stack(
                [
                    np.zeros((3, 6), dtype=float),
                    self._previous_fast_context_tail.values,
                ]
            )
        prediction = predict_fast_physical_context(
            current,
            previous_states=previous,
            current_minimum_wheel_load_ratio=(
                self._latest_min_wheel_load_ratio
            ),
            previous_minimum_wheel_load_ratio=(
                self._previous_min_wheel_load_ratio
            ),
            dt_s=float(tracking.dt_s),
            mode=self.config.fast_physical_context_mode,
            config=FastPhysicalContextConfig(
                horizon_steps=self.config.horizon_steps,
                connector_ultimate_force_n=self._connector_ultimate_force_n,
            ),
        )
        self.last_fast_physical_context = prediction
        self.last_fast_physical_context_mode = prediction.mode
        return prediction

    def set_last_applied(self, controls: np.ndarray) -> None:
        values = np.asarray(controls, dtype=float)
        if values.shape != (3, 2) or not np.all(np.isfinite(values)):
            raise ValueError("last applied local controls must have shape (3, 2)")
        self._last_applied = values.copy()

    def compute(
        self,
        states: np.ndarray,
        errors: CooperativeErrors,
        path: ReferencePath,
        references: VehicleReferenceHorizon,
        tracking: TrackingConfig,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: np.ndarray,
        coupled_tail: CoupledStateTail | None = None,
    ) -> np.ndarray:
        """Solve three QPs and return net controls in ``[steering, acceleration]`` order."""

        controls = np.empty((3, 2), dtype=float)
        statuses: list[str] = []
        objectives = np.empty(3, dtype=float)
        solve_times = np.empty(3, dtype=float)
        margins = np.empty(3, dtype=float)
        slacks = np.empty(3, dtype=float)
        costs = np.empty(3, dtype=float)
        active = np.empty(3, dtype=int)
        support_fraction = np.empty(3, dtype=float)
        versions = np.empty(3, dtype=int)
        self.last_fast_physical_context_time_ms = 0.0
        self.last_fast_physical_context_backends = ()
        self.last_fast_physical_context_realtime = "not_run"
        self._current_planned_controls = [
            (
                warm.copy()
                if warm is not None
                else np.broadcast_to(
                    self._last_applied[vehicle],
                    (self.config.horizon_steps, 2),
                ).copy()
            )
            for vehicle, warm in enumerate(self._warm_controls)
        ]
        fast_physical_context = (
            self._predict_fast_physical_context(tracking)
            if self.config.enable_rbf_cost
            else None
        )
        progress_shift_m = 0.0
        if self.config.progress_recenter_m is not None:
            front_projection = self._adapter.project(
                states[0], path, reference_index=errors.reference_index
            )
            progress_shift_m = float(
                front_projection.s_m - self.config.progress_recenter_m
            )
        for vehicle, name in enumerate(VEHICLE_NAMES):
            model = self.model_bank.model(name)
            versions[vehicle] = model.version
            x0_base = self._adapter.world_to_koopman(
                states[vehicle], path, reference_index=errors.reference_index
            )
            x0_base[0] -= progress_shift_m
            state_dimension = int(getattr(self.lifting, "state_dimension", 6))
            if state_dimension == 6:
                x0 = x0_base
            elif state_dimension == 24:
                if coupled_tail is None:
                    raise RuntimeError(
                        "the 24-state Koopman model requires a coupled-plant observation"
                    )
                x0 = np.concatenate([x0_base, coupled_tail.values[vehicle]])
            else:
                raise ValueError(
                    f"unsupported Koopman state dimension: {state_dimension}"
                )
            z0 = np.asarray(self.lifting.lift(x0), dtype=float).reshape(-1)
            if z0.shape != (model.nz,):
                raise ValueError(f"lifting/model mismatch for {name}: {z0.shape} vs {model.nz}")
            result = self._solve_vehicle(
                vehicle,
                model,
                z0,
                references,
                tracking,
                diagnostics,
                float(tire_mu[vehicle]),
                progress_shift_m,
                fast_physical_context,
            )
            sequence, objective, status, elapsed, risk = result
            controls[vehicle] = sequence[0]
            self._current_planned_controls[vehicle] = sequence.copy()
            self._warm_controls[vehicle] = np.concatenate(
                [sequence[1:], sequence[-1:]], axis=0
            )
            statuses.append(status)
            objectives[vehicle] = objective
            solve_times[vehicle] = elapsed
            margins[vehicle], slacks[vehicle], costs[vehicle], active[vehicle], support_fraction[vehicle] = risk
        self._last_applied = controls.copy()
        self._previous_beta_deg = np.rad2deg(
            np.arctan2(states[:, 4], np.maximum(np.abs(states[:, 3]), 1.0e-9))
        )
        self.last_statuses = tuple(statuses)  # type: ignore[assignment]
        self.last_objectives = objectives
        self.last_solve_time_ms = solve_times
        self.last_rbf_min_margin = margins
        self.last_rbf_slack = slacks
        self.last_rbf_cost = costs
        self.last_rbf_active_count = active
        self.last_rbf_support_fraction = support_fraction
        self.last_model_versions = versions
        return controls

    def _solve_vehicle(
        self,
        vehicle: int,
        model: Any,
        initial: np.ndarray,
        references: VehicleReferenceHorizon,
        tracking: TrackingConfig,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: float,
        progress_shift_m: float,
        fast_physical_context: FastPhysicalContextHorizon | None,
    ) -> tuple[np.ndarray, float, str, float, tuple[float, float, float, int, float]]:
        cfg = self.config
        horizon = cfg.horizon_steps
        target = _resize_horizon(references.target_states[vehicle], horizon)
        target[:, 0] -= progress_shift_m
        feedforward = _resize_horizon(references.feedforward_controls[vehicle], horizon)
        curvature = _resize_horizon(references.curvature_1pm[vehicle, :, None], horizon)[:, 0]
        decoded_initial = np.asarray(model.output(initial), dtype=float)[:6]
        steering_correction = (
            -cfg.stabilizing_lateral_gain * (decoded_initial[1] - target[0, 1])
            - cfg.stabilizing_heading_gain * (decoded_initial[2] - target[0, 2])
            - cfg.stabilizing_yaw_rate_gain * (decoded_initial[5] - target[0, 5])
        )
        acceleration_correction = cfg.stabilizing_speed_gain * (
            target[0, 3] - decoded_initial[3]
        )
        decay = np.exp(-np.arange(horizon, dtype=float) / cfg.stabilizing_decay_steps)
        feedforward[:, 0] += decay * steering_correction
        feedforward[:, 1] += decay * acceleration_correction
        nominal = self._warm_controls[vehicle]
        if nominal is None or nominal.shape != (horizon, 2):
            nominal = feedforward.copy()
            nominal[0] = self._last_applied[vehicle]
        sequence = nominal.copy()
        risk = (float("nan"), 0.0, 0.0, 0, float("nan"))
        total_solve_time = 0.0
        status = "not_run"
        objective = float("nan")
        iterations = cfg.sqp_iterations if isinstance(model, BilinearKoopmanDynamics) else 1
        for _ in range(iterations):
            linearizations = []
            z_nominal = initial.copy()
            for step in range(horizon):
                linearizations.append(model.linearize(z_nominal, sequence[step]))
                z_nominal = model.predict(z_nominal, sequence[step])
            (
                sequence,
                objective,
                status,
                elapsed,
                risk,
            ) = self._solve_vehicle_qp(
                vehicle,
                model,
                initial,
                tuple(linearizations),
                sequence,
                target,
                feedforward,
                curvature,
                tracking,
                diagnostics,
                tire_mu,
                fast_physical_context,
            )
            total_solve_time += elapsed
        return sequence, objective, status, total_solve_time, risk

    def _solve_vehicle_qp(
        self,
        vehicle: int,
        model: Any,
        initial: np.ndarray,
        linearizations: tuple[tuple[np.ndarray, np.ndarray, np.ndarray], ...],
        nominal: np.ndarray,
        target: np.ndarray,
        feedforward: np.ndarray,
        curvature: np.ndarray,
        tracking: TrackingConfig,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: float,
        fast_physical_context: FastPhysicalContextHorizon | None,
    ) -> tuple[np.ndarray, float, str, float, tuple[float, float, float, int, float]]:
        cfg = self.config
        horizon = cfg.horizon_steps
        n_variables = 2 * horizon
        selectors = []
        output_maps = []
        output_offsets = []
        state_map = np.zeros((model.nz, n_variables), dtype=float)
        state_offset = initial.copy()
        for step, (a_matrix, b_matrix, affine) in enumerate(linearizations):
            select = np.zeros((2, n_variables), dtype=float)
            select[:, 2 * step : 2 * step + 2] = np.eye(2)
            selectors.append(select)
            state_map = a_matrix @ state_map + b_matrix @ select
            state_offset = a_matrix @ state_offset + affine
            output_maps.append(np.asarray(model.C @ state_map, dtype=float))
            output_offsets.append(np.asarray(model.C @ state_offset, dtype=float))

        p_matrix = np.eye(n_variables, dtype=float) * 1.0e-9
        q_vector = np.zeros(n_variables, dtype=float)
        state_weights = np.asarray(cfg.state_weights, dtype=float)
        for step in range(horizon):
            scale = cfg.terminal_scale if step == horizon - 1 else 1.0
            p_matrix, q_vector = _add_residual(
                p_matrix,
                q_vector,
                output_maps[step][:6],
                output_offsets[step][:6] - target[step],
                state_weights * scale,
            )
        input_weights = np.asarray(cfg.input_weights, dtype=float)
        rate_weights = np.asarray(cfg.input_rate_weights, dtype=float)
        stabilizing_weights = np.asarray(
            cfg.stabilizing_reference_weights, dtype=float
        )
        previous_map = np.zeros((2, n_variables), dtype=float)
        previous_value = self._last_applied[vehicle]
        for step in range(horizon):
            p_matrix, q_vector = _add_residual(
                p_matrix,
                q_vector,
                selectors[step],
                -feedforward[step],
                input_weights,
            )
            p_matrix, q_vector = _add_residual(
                p_matrix,
                q_vector,
                selectors[step],
                -feedforward[step],
                stabilizing_weights,
            )
            p_matrix, q_vector = _add_residual(
                p_matrix,
                q_vector,
                selectors[step] - previous_map,
                -previous_value,
                rate_weights,
            )
            previous_map = selectors[step]
            previous_value = np.zeros(2, dtype=float)

        nominal_vector = nominal.reshape(-1)
        if cfg.enable_rbf_cost:
            margin_nominal, support = self._rbf_margin_horizon(
                vehicle,
                output_maps,
                output_offsets,
                nominal_vector,
                curvature,
                target,
                diagnostics,
                tire_mu,
                tracking,
                fast_physical_context,
            )
            finite_supported = support & np.isfinite(margin_nominal)
            active_mask = (
                finite_supported
                & (margin_nominal < cfg.rbf_activation_margin)
                & (margin_nominal >= cfg.rbf_minimum_linearization_margin)
            )
        else:
            margin_nominal = np.full(horizon, np.nan, dtype=float)
            support = np.zeros(horizon, dtype=bool)
            active_mask = np.zeros(horizon, dtype=bool)
        if cfg.enable_rbf_cost and cfg.rbf_strict_training_domain and not np.all(support):
            raise RuntimeError(
                f"local RBF horizon for {VEHICLE_NAMES[vehicle]} left the training domain"
            )
        if cfg.enable_rbf_cost and np.any(active_mask):
            jacobian = self._rbf_shared_channel_jacobian(
                vehicle,
                output_maps,
                output_offsets,
                nominal_vector,
                curvature,
                target,
                diagnostics,
                tire_mu,
                tracking,
                fast_physical_context,
            )
            for step in np.flatnonzero(active_mask):
                gradient = jacobian[step].copy()
                gradient_norm = float(np.linalg.norm(gradient))
                if gradient_norm > cfg.rbf_maximum_gradient_norm:
                    gradient *= cfg.rbf_maximum_gradient_norm / gradient_norm
                offset = margin_nominal[step] - gradient @ nominal_vector
                p_matrix, q_vector = _add_residual(
                    p_matrix,
                    q_vector,
                    -gradient.reshape(1, -1),
                    np.array([cfg.rbf_target_margin - offset]),
                    cfg.rbf_cost_weight,
                )

        lower_one = np.array([-tracking.max_steer_rad, tracking.min_accel_mps2])
        upper_one = np.array([tracking.max_steer_rad, tracking.max_accel_mps2])
        difference = _difference_matrix(1, horizon)
        difference_offset = np.zeros(n_variables, dtype=float)
        difference_offset[:2] = -self._last_applied[vehicle]
        rate_one = np.array(
            [
                cfg.maximum_steering_rate_radps * tracking.dt_s,
                cfg.maximum_acceleration_rate_mps3 * tracking.dt_s,
            ]
        )
        constraint = sparse.vstack(
            [sparse.eye(n_variables, format="csc"), sparse.csc_matrix(difference)],
            format="csc",
        )
        lower = np.concatenate(
            [np.tile(lower_one, horizon), np.tile(-rate_one, horizon) - difference_offset]
        )
        upper = np.concatenate(
            [np.tile(upper_one, horizon), np.tile(rate_one, horizon) - difference_offset]
        )
        solver = osqp.OSQP()
        solver.setup(
            P=sparse.csc_matrix((p_matrix + p_matrix.T) * 0.5),
            q=q_vector,
            A=constraint,
            l=lower,
            u=upper,
            eps_abs=cfg.solver_tolerance,
            eps_rel=cfg.solver_tolerance,
            max_iter=cfg.solver_maximum_iterations,
            polishing=False,
            verbose=False,
        )
        solver.warm_start(x=nominal_vector)
        started = perf_counter()
        result = solver.solve(raise_error=False)
        elapsed = 1000.0 * (perf_counter() - started)
        status = str(result.info.status).lower()
        if result.x is None or status not in {"solved", "solved inaccurate"}:
            raise RuntimeError(f"local Koopman-RBF MPC failed for {VEHICLE_NAMES[vehicle]}: {result.info.status}")
        solution = np.asarray(result.x, dtype=float).reshape(horizon, 2)
        if cfg.enable_rbf_cost:
            solved_margin, solved_support = self._rbf_margin_horizon(
                vehicle,
                output_maps,
                output_offsets,
                solution.reshape(-1),
                curvature,
                target,
                diagnostics,
                tire_mu,
                tracking,
                fast_physical_context,
            )
            supported_margins = solved_margin[
                solved_support & np.isfinite(solved_margin)
            ]
            minimum_margin = (
                float(np.min(supported_margins))
                if supported_margins.size
                else float("nan")
            )
            slack = (
                float(max(cfg.rbf_target_margin - minimum_margin, 0.0))
                if np.isfinite(minimum_margin)
                else 0.0
            )
            rbf_cost = float(cfg.rbf_cost_weight * slack * slack)
            support_fraction = float(np.mean(solved_support))
        else:
            minimum_margin = float("nan")
            slack = 0.0
            rbf_cost = 0.0
            support_fraction = float("nan")
        risk = (
            minimum_margin,
            slack,
            rbf_cost,
            int(np.count_nonzero(active_mask)),
            support_fraction,
        )
        return solution, float(result.info.obj_val), status, elapsed, risk

    def _rbf_shared_channel_jacobian(
        self,
        vehicle: int,
        output_maps: list[np.ndarray],
        output_offsets: list[np.ndarray],
        nominal: np.ndarray,
        curvature: np.ndarray,
        target: np.ndarray,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: float,
        tracking: TrackingConfig,
        fast_physical_context: FastPhysicalContextHorizon | None = None,
    ) -> np.ndarray:
        horizon = self.config.horizon_steps
        jacobian = np.zeros((horizon, 2 * horizon), dtype=float)
        step_sizes = (
            self.config.rbf_finite_difference_steer_rad,
            self.config.rbf_finite_difference_acceleration_mps2,
        )
        candidates = []
        for variable in range(2 * horizon):
            step_size = step_sizes[variable % 2]
            perturbation = np.zeros_like(nominal)
            perturbation[variable] = step_size
            candidates.extend((nominal + perturbation, nominal - perturbation))
        candidate_margins, _ = self._rbf_margin_horizon_batch(
            vehicle,
            output_maps,
            output_offsets,
            np.asarray(candidates, dtype=float),
            curvature,
            target,
            diagnostics,
            tire_mu,
            tracking,
            fast_physical_context,
        )
        for variable in range(2 * horizon):
            step_size = step_sizes[variable % 2]
            plus = candidate_margins[2 * variable]
            minus = candidate_margins[2 * variable + 1]
            derivative = (plus - minus) / (2.0 * step_size)
            derivative = np.where(np.isfinite(derivative), derivative, 0.0)
            jacobian[:, variable] = derivative
        for step in range(horizon):
            jacobian[step, 2 * (step + 1) :] = 0.0
        return jacobian

    def _rbf_margin_horizon(
        self,
        vehicle: int,
        output_maps: list[np.ndarray],
        output_offsets: list[np.ndarray],
        controls: np.ndarray,
        curvature: np.ndarray,
        target: np.ndarray,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: float,
        tracking: TrackingConfig,
        fast_physical_context: FastPhysicalContextHorizon | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        margins, support = self._rbf_margin_horizon_batch(
            vehicle,
            output_maps,
            output_offsets,
            np.asarray(controls, dtype=float).reshape(1, -1),
            curvature,
            target,
            diagnostics,
            tire_mu,
            tracking,
            fast_physical_context,
        )
        return margins[0], support[0]

    def _nonlinear_context_for_candidates(
        self,
        vehicle: int,
        controls_array: np.ndarray,
    ) -> NonlinearPhysicsContextBatch:
        """Embed one local candidate batch in complete three-vehicle commands."""

        batch = len(controls_array)
        horizon = self.config.horizon_steps
        full_commands = np.empty((batch, horizon, 3, 2), dtype=float)
        for peer in range(3):
            planned = self._current_planned_controls[peer]
            if planned is None:
                planned = np.broadcast_to(
                    self._last_applied[peer],
                    (horizon, 2),
                )
            planned_values = np.asarray(planned, dtype=float)
            if planned_values.shape != (horizon, 2):
                raise ValueError("peer command plan must match the MPC horizon")
            full_commands[:, :, peer] = planned_values
        full_commands[:, :, vehicle] = controls_array.reshape(
            batch,
            horizon,
            2,
        )
        snapshot = self._nonlinear_context_predictor.snapshot
        if snapshot is None:
            raise RuntimeError("nonlinear physics snapshot is not configured")
        full_commands[:, :, :, 1] += (
            snapshot.payload.g
            * np.sin(snapshot.road_pitch_rad_by_vehicle)[None, None, :]
        )
        result = self._nonlinear_context_predictor.predict(full_commands)
        self.last_fast_physical_context_time_ms += result.wall_time_ms
        self.last_fast_physical_context_backends = (
            *self.last_fast_physical_context_backends,
            result.backend,
        )
        if result.deployment_classification == "simulation_only":
            self.last_fast_physical_context_realtime = "simulation_only"
        elif self.last_fast_physical_context_realtime != "simulation_only":
            self.last_fast_physical_context_realtime = "realtime_candidate"
        self.last_fast_physical_context = result.context(0)
        self.last_fast_physical_context_mode = "nonlinear_physics_rollout"
        return result

    def _rbf_margin_horizon_batch(
        self,
        vehicle: int,
        output_maps: list[np.ndarray],
        output_offsets: list[np.ndarray],
        controls_batch: np.ndarray,
        curvature: np.ndarray,
        target: np.ndarray,
        diagnostics: PayloadForceDiagnostics,
        tire_mu: float,
        tracking: TrackingConfig,
        fast_physical_context: FastPhysicalContextHorizon | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Evaluate multiple horizon control sequences in one RBF matrix call."""

        horizon = self.config.horizon_steps
        controls_array = np.asarray(controls_batch, dtype=float)
        if controls_array.ndim != 2 or controls_array.shape[1] != 2 * horizon:
            raise ValueError("controls_batch must have shape (batch, 2 * horizon)")
        output_full = np.stack(
            [
                controls_array @ output_maps[step].T + output_offsets[step]
                for step in range(horizon)
            ],
            axis=1,
        )
        output = output_full[..., :6]
        model_columns = tuple(self.rbf_model.input_columns)
        use_new_object_features = (
            model_columns == tuple(RBF_INPUT_COLUMNS_NEW_PHYSICAL_CONNECTOR_22)
        )
        nonlinear_mode = (
            getattr(
                self.config,
                "fast_physical_context_mode",
                "measured_constant",
            )
            == "nonlinear_physics_rollout"
        )
        if model_columns not in {
            tuple(RBF_INPUT_COLUMNS_THREE_VEHICLE),
            tuple(RBF_INPUT_COLUMNS_NEW_PHYSICAL_CONNECTOR_22),
        }:
            raise ValueError(f"unsupported local RBF input contract: {model_columns}")
        if (
            use_new_object_features
            and fast_physical_context is None
            and not nonlinear_mode
        ):
            raise RuntimeError(
                "the 22-input RBF cost requires measured_constant, "
                "first_order_physics or nonlinear_physics_rollout context"
            )
        if (
            use_new_object_features
            and not self.config.fast_physical_context_validation_passed
        ):
            raise RuntimeError(
                "the 22-input RBF cost is blocked until the selected fast "
                "physical context passes all four validation gates"
            )
        nonlinear_context = None
        if use_new_object_features and nonlinear_mode:
            if self._nonlinear_context_predictor.snapshot is None:
                raise RuntimeError(
                    "nonlinear_physics_rollout requires the complete current "
                    "three-vehicle and payload observation"
                )
            nonlinear_context = self._nonlinear_context_for_candidates(
                vehicle,
                controls_array,
            )
        if (
            fast_physical_context is not None
            and (
                fast_physical_context.horizon_steps != horizon
                or fast_physical_context.vehicle_count != 3
            )
        ):
            raise ValueError(
                "fast physical context must match the local MPC horizon and "
                "three-vehicle layout"
            )
        rows = []
        for batch_index in range(len(controls_array)):
            for step in range(horizon):
                if nonlinear_context is not None:
                    vertical_load_n = float(
                        nonlinear_context.vertical_load_n[
                            batch_index,
                            step,
                            vehicle,
                        ]
                    )
                    connection_force_body_n = (
                        nonlinear_context.connector_force_body_n[
                            batch_index,
                            step,
                            vehicle,
                        ]
                    )
                elif fast_physical_context is None:
                    vertical_load_n = float(
                        diagnostics.vertical_loads_n[vehicle]
                    )
                    connection_force_body_n = (
                        diagnostics.connection_forces_body_n[vehicle]
                    )
                else:
                    vertical_load_n = float(
                        fast_physical_context.vertical_load_n[step, vehicle]
                    )
                    connection_force_body_n = (
                        fast_physical_context.connector_force_body_n[
                            step, vehicle
                        ]
                    )
                common = dict(
                    vx_mps=float(output[batch_index, step, 3]),
                    steering_rad=float(controls_array[batch_index, 2 * step]),
                    curvature_1pm=float(curvature[step]),
                    lateral_error_m=float(
                        output[batch_index, step, 1] - target[step, 1]
                    ),
                    longitudinal_error_m=float(
                        output[batch_index, step, 0] - target[step, 0]
                    ),
                    vertical_load_n=vertical_load_n,
                    connection_force_body_n=connection_force_body_n,
                    connection_moment_z_n=float(
                        diagnostics.connection_moment_z_n[vehicle]
                    ),
                    payload=self.payload,
                    mu=tire_mu,
                )
                if use_new_object_features:
                    if nonlinear_context is not None:
                        connector_penetration_m = float(
                            nonlinear_context.connector_penetration_m[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                        connector_normal_velocity_mps = float(
                            nonlinear_context.connector_normal_velocity_mps[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                        payload_roll_rad = float(
                            nonlinear_context.payload_roll_rad[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                        payload_roll_rate_radps = float(
                            nonlinear_context.payload_roll_rate_radps[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                        minimum_wheel_load_ratio = float(
                            nonlinear_context.minimum_wheel_load_ratio[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                        local_tire_utilization = float(
                            nonlinear_context.maximum_tire_friction_utilization[
                                batch_index,
                                step,
                                vehicle,
                            ]
                        )
                    else:
                        assert fast_physical_context is not None
                        connector_penetration_m = float(
                            fast_physical_context.connector_penetration_m[
                                step,
                                vehicle,
                            ]
                        )
                        connector_normal_velocity_mps = float(
                            fast_physical_context.connector_normal_velocity_mps[
                                step,
                                vehicle,
                            ]
                        )
                        payload_roll_rad = float(
                            fast_physical_context.payload_roll_rad[
                                step,
                                vehicle,
                            ]
                        )
                        payload_roll_rate_radps = float(
                            fast_physical_context.payload_roll_rate_radps[
                                step,
                                vehicle,
                            ]
                        )
                        minimum_wheel_load_ratio = float(
                            fast_physical_context.minimum_wheel_load_ratio[
                                step,
                                vehicle,
                            ]
                        )
                        local_tire_utilization = float(
                            self._latest_max_tire_utilization[vehicle]
                        )
                    rows.append(
                        build_new_physical_connector_rbf_feature_row(
                            **common,
                            connector_penetration_m=connector_penetration_m,
                            connector_working_penetration_m=(
                                self.connector_working_penetration_m
                            ),
                            contact_normal_velocity_mps=(
                                connector_normal_velocity_mps
                            ),
                            payload_roll_rad=payload_roll_rad,
                            payload_roll_limit_rad=self.payload_roll_limit_rad,
                            payload_roll_rate_radps=payload_roll_rate_radps,
                            payload_roll_rate_limit_radps=(
                                self.payload_roll_rate_limit_radps
                            ),
                            local_max_tire_friction_utilization=(
                                local_tire_utilization
                            ),
                            minimum_wheel_load_n=minimum_wheel_load_ratio,
                            nominal_wheel_load_n=1.0,
                        )
                    )
                else:
                    rows.append(build_rbf_feature_row(**common))
        beta = np.rad2deg(
            np.arctan2(output[:, :, 4], np.maximum(np.abs(output[:, :, 3]), 1.0e-9))
        )
        raw_dbeta = np.empty_like(beta)
        raw_dbeta[:, 0] = (
            beta[:, 0] - self._previous_beta_deg[vehicle]
        ) / tracking.dt_s
        if horizon > 1:
            raw_dbeta[:, 1:] = np.diff(beta, axis=1) / tracking.dt_s
        alpha = tracking.dt_s / (
            self.config.rbf_beta_derivative_time_constant_s + tracking.dt_s
        )
        dbeta = np.empty_like(beta)
        filtered = np.zeros(len(controls_array), dtype=float)
        for step in range(horizon):
            filtered += alpha * (raw_dbeta[:, step] - filtered)
            dbeta[:, step] = filtered
        feature_matrix = np.asarray(
            [
                [float(row[column]) for column in model_columns]
                for row in rows
            ],
            dtype=float,
        )
        evaluation = evaluate_rbf_boundary_batch(
            self.rbf_model,
            feature_matrix,
            beta=beta.reshape(-1),
            dbeta=dbeta.reshape(-1),
            safety_scale=self.config.rbf_safety_scale,
        )
        backends = list(self.last_rbf_runtime_backends)
        backends[vehicle] = evaluation.backend
        self.last_rbf_runtime_backends = tuple(backends)  # type: ignore[assignment]
        assert evaluation.support is not None
        assert evaluation.margins is not None
        support = evaluation.support.reshape(len(controls_array), horizon)
        margins = evaluation.margins.reshape(len(controls_array), horizon)
        return np.where(support, margins, np.nan), support


@dataclass
class AdaptiveSystemVehicleHierarchicalMPC:
    """Complete hierarchy with an optional isolated online adaptation runtime."""

    nominal_model: Any
    lifting: Any
    rbf_model: RBFBoundaryModel
    payload: PayloadSpec
    online_config: OnlineAdaptationConfig
    system_reference_controller: SystemReferenceMPC = field(
        default_factory=SystemReferenceMPC
    )
    local_controller_config: LocalAdaptiveKoopmanMPCConfig = field(
        default_factory=LocalAdaptiveKoopmanMPCConfig
    )
    actuator_controller: IndependentActuatorMPC = field(
        default_factory=IndependentActuatorMPC
    )
    name: str = "在线自适应Koopman-RBF双层模型预测控制"
    online_adaptation_enabled: bool = True
    deterministic_adaptation: bool = True
    use_rbf_system_feedback: bool = False
    use_rbf_adaptation_gate: bool = False
    coordinate_frame: str = field(default="frenet", init=False)
    model_bank: ThreeVehicleModelBank = field(init=False)
    local_controller: IndependentAdaptiveKoopmanRbfMPC = field(init=False)
    adaptation_runtime: AsyncThreeVehicleAdaptationRuntime = field(init=False)
    last_status: str = field(default="not_run", init=False)
    last_objective: float = field(default=float("nan"), init=False)
    last_solver_time_ms: float = field(default=float("nan"), init=False)
    last_system_reference: VehicleReferenceHorizon | None = field(default=None, init=False)
    last_net_controls: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False
    )
    last_gross_controls: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False
    )
    last_force_diagnostics: PayloadForceDiagnostics | None = field(default=None, init=False)
    stability_feedback: SystemStabilityFeedback = field(
        default_factory=SystemStabilityFeedback, init=False
    )
    _road_grade_percent: np.ndarray = field(
        default_factory=lambda: np.zeros(3), init=False, repr=False
    )
    _vehicle_tire_mu: np.ndarray = field(
        default_factory=lambda: np.full(3, 0.85), init=False, repr=False
    )
    _previous_states: np.ndarray | None = field(default=None, init=False, repr=False)
    _previous_formation_errors: np.ndarray | None = field(default=None, init=False, repr=False)
    _runtime_closed: bool = field(default=False, init=False, repr=False)
    _current_coupled_tail: CoupledStateTail | None = field(
        default=None, init=False, repr=False
    )
    _transition_next_coupled_tail: CoupledStateTail | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        context_rows = context_identity_lifted_rows(
            int(getattr(self.lifting, "state_dimension", 6))
        )
        if context_rows:
            preserved_rows = tuple(
                sorted(
                    set(self.online_config.preserve_lifted_rows).union(
                        context_rows
                    )
                )
            )
            self.online_config = replace(
                self.online_config,
                preserve_lifted_rows=preserved_rows,
            )
        runtime_model = (
            self.nominal_model.to_runtime_dynamics()
            if hasattr(self.nominal_model, "to_runtime_dynamics")
            else self.nominal_model
        )
        self._nominal_runtime_model = runtime_model.clone()
        self.model_bank = ThreeVehicleModelBank(runtime_model)
        self.local_controller = IndependentAdaptiveKoopmanRbfMPC(
            self.model_bank,
            self.lifting,
            self.rbf_model,
            self.payload,
            self.local_controller_config,
        )
        self.adaptation_runtime = self._new_runtime()

    def _new_runtime(self) -> AsyncThreeVehicleAdaptationRuntime:
        self._runtime_closed = False
        return AsyncThreeVehicleAdaptationRuntime(
            self.model_bank,
            self.lifting,
            self.online_config,
            enabled=bool(self.online_adaptation_enabled),
            deterministic_publication=self.deterministic_adaptation,
            progress_recenter_m=self.local_controller_config.progress_recenter_m,
        )

    def _restore_online_context_identity_rows(self) -> None:
        """Undo any spectral-projection drift in the nine context rows."""

        rows = context_identity_lifted_rows(
            int(getattr(self.lifting, "state_dimension", 6))
        )
        if not rows:
            return
        indices = np.asarray(rows, dtype=int)
        nominal_a = np.asarray(self._nominal_runtime_model.A, dtype=float)
        nominal_b = np.asarray(self._nominal_runtime_model.B, dtype=float)
        for name in VEHICLE_NAMES:
            snapshot = self.model_bank.snapshot(name)
            if np.array_equal(
                snapshot.A[indices], nominal_a[indices]
            ) and np.array_equal(snapshot.B[indices], nominal_b[indices]):
                continue
            corrected_a = snapshot.A.copy()
            corrected_b = snapshot.B.copy()
            corrected_a[indices] = nominal_a[indices]
            corrected_b[indices] = nominal_b[indices]
            self.model_bank.update(
                name,
                A=corrected_a,
                B=corrected_b,
                expected_version=snapshot.version,
            )

    def reset(self) -> None:
        if not self._runtime_closed:
            self.adaptation_runtime.close()
        for name in VEHICLE_NAMES:
            self.model_bank.reset_vehicle(name, self._nominal_runtime_model)
        self.system_reference_controller.reset()
        self.local_controller.reset()
        self.actuator_controller.reset()
        self.adaptation_runtime = self._new_runtime()
        self.last_status = "not_run"
        self.last_objective = float("nan")
        self.last_solver_time_ms = float("nan")
        self.last_system_reference = None
        self.last_net_controls = np.zeros((3, 2), dtype=float)
        self.last_gross_controls = np.zeros((3, 2), dtype=float)
        self.last_force_diagnostics = None
        self.stability_feedback = SystemStabilityFeedback()
        self._previous_states = None
        self._previous_formation_errors = None
        self._current_coupled_tail = None
        self._transition_next_coupled_tail = None

    def close(self) -> None:
        if not self._runtime_closed:
            self.adaptation_runtime.close()
            self._runtime_closed = True

    def set_environment(self, vehicle_tire_mu: np.ndarray, payload: object) -> None:
        values = np.asarray(vehicle_tire_mu, dtype=float)
        if values.shape != (3,) or np.any(~np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("vehicle_tire_mu must contain three finite positive values")
        self._vehicle_tire_mu = values.copy()
        if isinstance(payload, PayloadSpec):
            self.payload = payload
            self.local_controller.payload = payload

    def set_road_grade_percent(self, values: np.ndarray) -> None:
        grade = np.asarray(values, dtype=float)
        if grade.shape != (3,) or np.any(~np.isfinite(grade)):
            raise ValueError("road grade must have shape (3,)")
        self._road_grade_percent = grade.copy()

    def _build_coupled_tail(
        self,
        diagnostics: object,
        payload_state: object,
        connector: object,
    ) -> CoupledStateTail:
        from src.coupled_transport_dynamics import (
            CoupledStepDiagnostics,
            PayloadDynamicState,
            PhysicalConnectorConfig,
        )

        if not isinstance(diagnostics, CoupledStepDiagnostics):
            raise TypeError("diagnostics must be CoupledStepDiagnostics")
        if not isinstance(payload_state, PayloadDynamicState):
            raise TypeError("payload_state must be PayloadDynamicState")
        if not isinstance(connector, PhysicalConnectorConfig):
            raise TypeError("connector must be PhysicalConnectorConfig")
        return build_coupled_state_tail(
            diagnostics,
            payload_state,
            self.payload,
            connector,
            self._vehicle_tire_mu,
            self._road_grade_percent,
        )

    def set_coupled_observation(
        self,
        diagnostics: object,
        payload_state: object,
        connector: object,
        payload_roll: object | None = None,
    ) -> None:
        """Attach the current measured connector and payload state."""

        previous_tail = self._current_coupled_tail
        self._current_coupled_tail = self._build_coupled_tail(
            diagnostics, payload_state, connector
        )
        from src.coupled_transport_dynamics import PhysicalConnectorConfig
        from src.payload_roll_support import PayloadRollConfig

        if isinstance(connector, PhysicalConnectorConfig):
            roll_limit = (
                payload_roll.roll_angle_limit_rad
                if isinstance(payload_roll, PayloadRollConfig)
                else np.deg2rad(8.0)
            )
            roll_rate_limit = (
                payload_roll.roll_rate_limit_radps
                if isinstance(payload_roll, PayloadRollConfig)
                else np.deg2rad(25.0)
            )
            self.local_controller.set_physical_limits(
                connector_working_penetration_m=(
                    connector.maximum_working_displacement_m
                ),
                payload_roll_limit_rad=float(roll_limit),
                payload_roll_rate_limit_radps=float(roll_rate_limit),
            )
            self.local_controller.set_fast_physical_context_observation(
                self._current_coupled_tail,
                previous_tail,
                connector_ultimate_force_n=connector.ultimate_force_n,
            )

    def set_wheel_observation(
        self,
        wheel_friction_utilization: np.ndarray,
        wheel_vertical_loads_n: np.ndarray,
        effective_vehicle_mass_kg: np.ndarray,
        gravity_mps2: float,
    ) -> None:
        """Hold the latest measured wheel risks across the next MPC horizon."""

        self.local_controller.set_wheel_observation(
            wheel_friction_utilization,
            wheel_vertical_loads_n,
            effective_vehicle_mass_kg,
            gravity_mps2,
        )

    def set_nonlinear_physics_observation(
        self,
        *,
        vehicle_states: np.ndarray,
        payload_state: object,
        vehicle_params: tuple[object, object, object],
        support_points_payload_body_m: np.ndarray,
        connector_config: object,
        roll_config: object,
        tracking: TrackingConfig,
        wheel_mu: np.ndarray,
        road_pitch_rad_by_vehicle: np.ndarray,
    ) -> None:
        """Provide the full coupled plant snapshot used by local candidates."""

        from src.coupled_transport_dynamics import (
            PayloadDynamicState,
            PhysicalConnectorConfig,
        )
        from src.payload_roll_support import PayloadRollConfig

        if not isinstance(payload_state, PayloadDynamicState):
            raise TypeError("payload_state must be a PayloadDynamicState")
        if not isinstance(connector_config, PhysicalConnectorConfig):
            raise TypeError("connector_config must be a PhysicalConnectorConfig")
        if not isinstance(roll_config, PayloadRollConfig):
            raise TypeError("roll_config must be a PayloadRollConfig")
        snapshot = NonlinearPhysicsRolloutSnapshot(
            vehicle_states=np.asarray(vehicle_states, dtype=float),
            payload_state=payload_state,
            vehicle_params=vehicle_params,  # type: ignore[arg-type]
            support_points_payload_body_m=(
                support_points_payload_body_m
            ),
            payload=self.payload,
            connector_config=connector_config,
            roll_config=roll_config,
            wheel_mu=np.asarray(wheel_mu, dtype=float),
            tracking=tracking,
            road_pitch_rad_by_vehicle=np.asarray(
                road_pitch_rad_by_vehicle,
                dtype=float,
            ),
            payload_road_pitch_rad=float(
                np.mean(road_pitch_rad_by_vehicle)
            ),
            current_commands=self.last_net_controls,
        )
        self.local_controller.set_nonlinear_physics_observation(snapshot)

    def set_transition_coupled_observation(
        self,
        diagnostics: object,
        payload_state: object,
        connector: object,
    ) -> None:
        """Attach the post-integration observation for online adaptation."""

        self._transition_next_coupled_tail = self._build_coupled_tail(
            diagnostics, payload_state, connector
        )

    def compute(
        self,
        t_s: float,
        states: np.ndarray,
        errors: CooperativeErrors,
        path: ReferencePath,
        geometry: FormationGeometry,
        tracking: TrackingConfig,
    ) -> tuple[ControlCommand, ControlCommand, ControlCommand]:
        del t_s
        started = perf_counter()
        force_config = PayloadForceConfig(dt_s=tracking.dt_s, wheelbase_m=tracking.wheelbase_m)
        net_commands_for_force = np.column_stack(
            [self.last_net_controls[:, 1], self.last_net_controls[:, 0]]
        )
        diagnostics = compute_payload_force_diagnostics(
            states,
            net_commands_for_force,
            errors,
            geometry,
            self.payload,
            force_config,
            previous_states=self._previous_states,
            previous_formation_errors_body_m=self._previous_formation_errors,
            road_grade_percent=self._road_grade_percent,
        )
        references = self.system_reference_controller.compute(
            states,
            errors,
            path,
            geometry,
            tracking,
            self.stability_feedback,
        )
        self.local_controller.set_last_applied(self.last_net_controls)
        net_controls = self.local_controller.compute(
            states,
            errors,
            path,
            references,
            tracking,
            diagnostics,
            self._vehicle_tire_mu,
            self._current_coupled_tail,
        )
        grade_angle = np.arctan(self._road_grade_percent / 100.0)
        gross_targets = net_controls.copy()
        gross_targets[:, 1] += self.payload.g * np.sin(grade_angle)
        gross_output = self.actuator_controller.compute(gross_targets, tracking)
        self.last_system_reference = references
        self.last_net_controls = net_controls.copy()
        self.last_gross_controls = gross_output.copy()
        self.last_force_diagnostics = diagnostics
        self._previous_states = np.asarray(states, dtype=float).copy()
        self._previous_formation_errors = np.column_stack(
            [errors.longitudinal_m, errors.lateral_m]
        )
        local_ok = all(
            status in {"solved", "solved inaccurate"}
            for status in self.local_controller.last_statuses
        )
        actuator_ok = all(
            status in {"solved", "solved inaccurate"}
            for status in self.actuator_controller.last_statuses
        )
        system_ok = self.system_reference_controller.last_status in {
            "solved",
            "solved inaccurate",
        }
        self.last_status = "solved" if system_ok and local_ok and actuator_ok else (
            f"system={self.system_reference_controller.last_status};"
            f"local={self.local_controller.last_statuses};"
            f"actuator={self.actuator_controller.last_statuses}"
        )
        self.last_objective = float(
            self.system_reference_controller.last_objective
            + np.sum(self.local_controller.last_objectives)
            + self.actuator_controller.last_objective
        )
        self.last_solver_time_ms = 1000.0 * (perf_counter() - started)
        deadline_ms = 1000.0 * float(tracking.dt_s)
        self.last_control_deadline_met = bool(
            self.last_solver_time_ms <= deadline_ms
        )
        local_simulation_only = (
            self.local_controller.last_fast_physical_context_realtime
            == "simulation_only"
        )
        self.last_runtime_classification = (
            "realtime_candidate"
            if self.last_control_deadline_met and not local_simulation_only
            else "simulation_only"
        )
        return tuple(
            ControlCommand(
                acceleration_mps2=float(control[1]),
                steering_rad=float(control[0]),
            )
            for control in gross_output
        )  # type: ignore[return-value]

    def observe_transition(
        self,
        step: int,
        previous_states: np.ndarray,
        applied_commands: tuple[ControlCommand, ControlCommand, ControlCommand],
        current_states: np.ndarray,
        path: ReferencePath,
        reference_index: int,
        rbf_margins: np.ndarray,
        support_ratios: np.ndarray,
        connection_ratios: np.ndarray,
    ) -> None:
        """Feed one measured transition to all three independent online adapters."""

        grade_angle = np.arctan(self._road_grade_percent / 100.0)
        net_commands = tuple(
            ControlCommand(
                acceleration_mps2=float(
                    command.acceleration_mps2
                    - self.payload.g * np.sin(grade_angle[index])
                ),
                steering_rad=float(command.steering_rad),
            )
            for index, command in enumerate(applied_commands)
        )
        local_margins = self.local_controller.last_rbf_min_margin
        measured_margins = np.asarray(rbf_margins, dtype=float)
        gate_margins = np.where(
            np.isfinite(measured_margins), measured_margins, local_margins
        )
        if self.last_force_diagnostics is not None:
            local_connection = (
                self.last_force_diagnostics.connection_force_norm_n
                / max(self.payload.connection_force_limit_n, 1.0e-9)
            )
            local_support = self.last_force_diagnostics.vertical_load_ratio
        else:
            local_connection = connection_ratios
            local_support = support_ratios
        adaptation_margins = (
            gate_margins
            if self.use_rbf_adaptation_gate
            else np.ones(3, dtype=float)
        )
        adaptation_support = (
            np.asarray(local_support, dtype=float)
            if self.use_rbf_adaptation_gate
            else np.ones(3, dtype=float)
        )
        adaptation_connection = (
            np.asarray(local_connection, dtype=float)
            if self.use_rbf_adaptation_gate
            else np.zeros(3, dtype=float)
        )
        feedback_margins = (
            gate_margins
            if self.use_rbf_system_feedback
            else np.ones(3, dtype=float)
        )
        self.adaptation_runtime.add_world_transition(
            int(step),
            previous_states,
            net_commands,
            current_states,
            path,
            reference_index=int(reference_index),
            rbf_margins=np.where(
                np.isfinite(adaptation_margins), adaptation_margins, 1.0
            ),
            support_ratios=adaptation_support,
            connection_ratios=adaptation_connection,
            previous_coupled_tail=(
                None
                if self._current_coupled_tail is None
                else self._current_coupled_tail.values
            ),
            current_coupled_tail=(
                None
                if self._transition_next_coupled_tail is None
                else self._transition_next_coupled_tail.values
            ),
        )
        self._restore_online_context_identity_rows()
        self.stability_feedback = SystemStabilityFeedback(
            rbf_margin=np.asarray(feedback_margins, dtype=float).copy(),
            vertical_load_ratio=np.asarray(local_support, dtype=float).copy(),
            connection_ratio=np.asarray(local_connection, dtype=float).copy(),
            local_solver_feasible=np.array(
                [status in {"solved", "solved inaccurate"} for status in self.local_controller.last_statuses],
                dtype=bool,
            ),
        )

    def adaptation_rows(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.adaptation_runtime.diagnostics_rows()]


def _add_residual(
    p_matrix: np.ndarray,
    q_vector: np.ndarray,
    matrix: np.ndarray,
    offset: np.ndarray,
    weight: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    residual_map = np.atleast_2d(np.asarray(matrix, dtype=float))
    residual_offset = np.atleast_1d(np.asarray(offset, dtype=float))
    weights = np.asarray(weight, dtype=float)
    if weights.ndim == 0:
        weighted_map = float(weights) * residual_map
        weighted_offset = float(weights) * residual_offset
    else:
        weighted_map = weights[:, None] * residual_map
        weighted_offset = weights * residual_offset
    return (
        p_matrix + 2.0 * residual_map.T @ weighted_map,
        q_vector + 2.0 * residual_map.T @ weighted_offset,
    )


def _difference_matrix(vehicle_count: int, horizon: int) -> np.ndarray:
    size = vehicle_count * horizon * 2
    matrix = np.zeros((size, size), dtype=float)
    for vehicle in range(vehicle_count):
        for step in range(horizon):
            start = (vehicle * horizon + step) * 2
            matrix[start : start + 2, start : start + 2] = np.eye(2)
            if step > 0:
                matrix[start : start + 2, start - 2 : start] = -np.eye(2)
    return matrix


def _resize_horizon(values: np.ndarray, horizon: int) -> np.ndarray:
    rows = np.asarray(values, dtype=float)
    if rows.ndim != 2 or rows.shape[0] < 1:
        raise ValueError("horizon values must be a nonempty matrix")
    if rows.shape[0] >= horizon:
        return rows[:horizon].copy()
    return np.concatenate(
        [rows, np.repeat(rows[-1:, :], horizon - rows.shape[0], axis=0)], axis=0
    )
