"""Shared two-level MPC architecture for the four extreme-condition methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
import osqp
from scipy import sparse

from src.cooperative_three_vehicle_control import (
    CooperativeErrors,
    FormationGeometry,
)
from src.path_tracking_control import ControlCommand, ReferencePath, TrackingConfig


@dataclass(frozen=True)
class LowerLevelMPCConfig:
    """Independent steering/acceleration actuator MPC settings."""

    horizon_steps: int = 6
    steering_time_constant_s: float = 0.12
    acceleration_time_constant_s: float = 0.20
    tracking_weights: tuple[float, float] = (24.0, 8.0)
    terminal_scale: float = 2.0
    drive_weights: tuple[float, float] = (0.02, 0.02)
    drive_rate_weights: tuple[float, float] = (0.45, 0.18)
    maximum_steering_rate_radps: float = 1.2
    maximum_acceleration_rate_mps3: float = 3.0
    solver_tolerance: float = 1.0e-6
    solver_maximum_iterations: int = 2000

    def __post_init__(self) -> None:
        if self.horizon_steps < 2:
            raise ValueError("lower-level MPC horizon_steps must be at least two")
        if self.steering_time_constant_s <= 0.0 or self.acceleration_time_constant_s <= 0.0:
            raise ValueError("actuator time constants must be positive")
        if self.terminal_scale <= 0.0 or self.solver_tolerance <= 0.0:
            raise ValueError("terminal scale and solver tolerance must be positive")
        if self.solver_maximum_iterations < 1:
            raise ValueError("solver_maximum_iterations must be positive")
        values = self.tracking_weights + self.drive_weights + self.drive_rate_weights
        if any(value < 0.0 for value in values):
            raise ValueError("lower-level MPC weights must be non-negative")


@dataclass
class IndependentActuatorMPC:
    """Three independent lower-level MPCs with identical tuning and state."""

    config: LowerLevelMPCConfig = field(default_factory=LowerLevelMPCConfig)
    actuator_state: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False
    )
    previous_drive: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False
    )
    warm_drives: np.ndarray | None = field(default=None, init=False, repr=False)
    last_statuses: tuple[str, str, str] = field(
        default=("not_run", "not_run", "not_run"), init=False
    )
    last_solve_time_ms: float = field(default=float("nan"), init=False)
    last_objective: float = field(default=float("nan"), init=False)
    _initialized: bool = field(default=False, init=False, repr=False)

    def reset(self) -> None:
        self.actuator_state = np.zeros((3, 2), dtype=float)
        self.previous_drive = np.zeros((3, 2), dtype=float)
        self.warm_drives = None
        self.last_statuses = ("not_run", "not_run", "not_run")
        self.last_solve_time_ms = float("nan")
        self.last_objective = float("nan")
        self._initialized = False

    def compute(
        self,
        target_controls: np.ndarray,
        tracking: TrackingConfig,
    ) -> np.ndarray:
        """Track upper-level ``[steering, acceleration]`` references."""

        targets = np.asarray(target_controls, dtype=float)
        if targets.shape != (3, 2) or not np.all(np.isfinite(targets)):
            raise ValueError("target_controls must be finite with shape (3, 2)")
        if not self._initialized:
            lower = np.array(
                [-tracking.max_steer_rad, tracking.min_accel_mps2], dtype=float
            )
            upper = np.array(
                [tracking.max_steer_rad, tracking.max_accel_mps2], dtype=float
            )
            initial = np.clip(targets, lower, upper)
            self.actuator_state = initial.copy()
            self.previous_drive = initial.copy()
            self._initialized = True
        started = perf_counter()
        outputs = np.empty((3, 2), dtype=float)
        drive_sequences = np.empty((3, self.config.horizon_steps, 2), dtype=float)
        statuses: list[str] = []
        objectives: list[float] = []
        for vehicle in range(3):
            warm = None if self.warm_drives is None else self.warm_drives[vehicle]
            drive, objective, status = self._solve_vehicle(
                self.actuator_state[vehicle],
                self.previous_drive[vehicle],
                targets[vehicle],
                tracking,
                warm,
            )
            transition, input_gain = self._actuator_matrices(tracking.dt_s)
            outputs[vehicle] = transition @ self.actuator_state[vehicle] + input_gain @ drive[0]
            drive_sequences[vehicle] = drive
            self.previous_drive[vehicle] = drive[0]
            statuses.append(status)
            objectives.append(objective)
        self.actuator_state = outputs
        self.warm_drives = np.concatenate(
            (drive_sequences[:, 1:, :], drive_sequences[:, -1:, :]), axis=1
        )
        self.last_statuses = tuple(statuses)  # type: ignore[assignment]
        self.last_objective = float(np.sum(objectives))
        self.last_solve_time_ms = 1000.0 * (perf_counter() - started)
        return outputs.copy()

    def _solve_vehicle(
        self,
        initial_state: np.ndarray,
        previous_drive: np.ndarray,
        target: np.ndarray,
        tracking: TrackingConfig,
        warm: np.ndarray | None,
    ) -> tuple[np.ndarray, float, str]:
        horizon = self.config.horizon_steps
        transition, input_gain = self._actuator_matrices(tracking.dt_s)
        prediction_map, initial_map = _prediction_matrices(
            transition,
            input_gain,
            horizon,
        )
        target_stack = np.tile(target, horizon)
        tracking_blocks = [np.diag(self.config.tracking_weights) for _ in range(horizon)]
        tracking_blocks[-1] = self.config.terminal_scale * tracking_blocks[-1]
        tracking_weight = np.zeros((2 * horizon, 2 * horizon), dtype=float)
        for step, block in enumerate(tracking_blocks):
            tracking_weight[2 * step : 2 * step + 2, 2 * step : 2 * step + 2] = block
        drive_weight = np.diag(np.tile(self.config.drive_weights, horizon))
        difference = _difference_matrix(horizon)
        difference_offset = np.zeros(2 * horizon, dtype=float)
        difference_offset[:2] = -previous_drive
        rate_weight = np.diag(np.tile(self.config.drive_rate_weights, horizon))
        initial_prediction = initial_map @ initial_state

        hessian = 2.0 * (
            prediction_map.T @ tracking_weight @ prediction_map
            + drive_weight
            + difference.T @ rate_weight @ difference
        )
        hessian += 1.0e-9 * np.eye(hessian.shape[0])
        gradient = 2.0 * (
            prediction_map.T @ tracking_weight @ (initial_prediction - target_stack)
            - drive_weight @ target_stack
            + difference.T @ rate_weight @ difference_offset
        )

        lower_one = np.array([-tracking.max_steer_rad, tracking.min_accel_mps2])
        upper_one = np.array([tracking.max_steer_rad, tracking.max_accel_mps2])
        rate_one = np.array(
            [
                self.config.maximum_steering_rate_radps * tracking.dt_s,
                self.config.maximum_acceleration_rate_mps3 * tracking.dt_s,
            ]
        )
        constraint = sparse.vstack(
            [sparse.eye(2 * horizon, format="csc"), sparse.csc_matrix(difference)],
            format="csc",
        )
        lower = np.concatenate(
            [
                np.tile(lower_one, horizon),
                np.tile(-rate_one, horizon) - difference_offset,
            ]
        )
        upper = np.concatenate(
            [
                np.tile(upper_one, horizon),
                np.tile(rate_one, horizon) - difference_offset,
            ]
        )
        solver = osqp.OSQP()
        solver.setup(
            P=sparse.csc_matrix((hessian + hessian.T) * 0.5),
            q=gradient,
            A=constraint,
            l=lower,
            u=upper,
            eps_abs=self.config.solver_tolerance,
            eps_rel=self.config.solver_tolerance,
            max_iter=self.config.solver_maximum_iterations,
            polishing=False,
            verbose=False,
        )
        if warm is not None and warm.shape == (horizon, 2):
            solver.warm_start(x=warm.reshape(-1))
        result = solver.solve(raise_error=False)
        status = str(result.info.status).lower()
        if result.x is None or status not in {"solved", "solved inaccurate"}:
            raise RuntimeError(f"lower-level actuator MPC failed: {result.info.status}")
        sequence = np.asarray(result.x, dtype=float).reshape(horizon, 2)
        return sequence, float(result.info.obj_val), status

    def _actuator_matrices(self, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
        time_constants = np.array(
            [
                self.config.steering_time_constant_s,
                self.config.acceleration_time_constant_s,
            ],
            dtype=float,
        )
        decay = np.exp(-float(dt_s) / time_constants)
        return np.diag(decay), np.diag(1.0 - decay)


@dataclass
class HierarchicalMPCController:
    """Upper cooperative MPC followed by the same lower MPC for every method."""

    upper_controller: object
    name: str
    lower_controller: IndependentActuatorMPC = field(
        default_factory=IndependentActuatorMPC
    )
    upper_update_period_s: float = 0.10
    lower_update_period_s: float = 0.05
    coordinate_frame: str = field(default="frenet", init=False)
    _upper_target: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False, repr=False
    )
    _last_output: np.ndarray = field(
        default_factory=lambda: np.zeros((3, 2), dtype=float), init=False, repr=False
    )
    _next_upper_update_s: float = field(default=0.0, init=False, repr=False)
    _next_lower_update_s: float = field(default=0.0, init=False, repr=False)
    last_upper_updated: bool = field(default=False, init=False)
    last_lower_updated: bool = field(default=False, init=False)
    last_upper_status: str = field(default="not_run", init=False)
    last_lower_status: str = field(default="not_run", init=False)
    last_upper_solve_time_ms: float = field(default=float("nan"), init=False)
    last_lower_solve_time_ms: float = field(default=float("nan"), init=False)
    last_status: str = field(default="not_run", init=False)
    last_objective: float = field(default=float("nan"), init=False)
    last_solver_time_ms: float = field(default=float("nan"), init=False)
    last_sqp_iterations: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.upper_update_period_s <= 0.0 or self.lower_update_period_s <= 0.0:
            raise ValueError("upper and lower MPC update periods must be positive")
        if not hasattr(self.upper_controller, "compute") or not hasattr(
            self.upper_controller, "reset"
        ):
            raise TypeError("upper_controller must implement compute and reset")
        if hasattr(self.upper_controller, "control_update_period_s"):
            self.upper_controller.control_update_period_s = float(
                self.upper_update_period_s
            )

    def reset(self) -> None:
        self.upper_controller.reset()
        self.lower_controller.reset()
        self._upper_target = np.zeros((3, 2), dtype=float)
        self._last_output = np.zeros((3, 2), dtype=float)
        self._next_upper_update_s = 0.0
        self._next_lower_update_s = 0.0
        self.last_upper_updated = False
        self.last_lower_updated = False
        self.last_status = "not_run"

    def set_environment(self, vehicle_tire_mu: np.ndarray, payload: object) -> None:
        """Forward measured environment values to upper costs that use them."""

        if hasattr(self.upper_controller, "set_environment"):
            self.upper_controller.set_environment(vehicle_tire_mu, payload)

    def set_road_grade_percent(self, road_grade_percent: np.ndarray) -> None:
        """Forward measured grades to an upper controller that models slope."""

        if hasattr(self.upper_controller, "set_road_grade_percent"):
            self.upper_controller.set_road_grade_percent(road_grade_percent)

    def compute(
        self,
        t_s: float,
        states: np.ndarray,
        errors: CooperativeErrors,
        path: ReferencePath,
        geometry: FormationGeometry,
        config: TrackingConfig,
    ) -> tuple[ControlCommand, ControlCommand, ControlCommand]:
        tolerance = 0.25 * max(float(config.dt_s), 1.0e-9)
        self.last_upper_updated = float(t_s) + tolerance >= self._next_upper_update_s
        if self.last_upper_updated:
            # The upper optimizer must anchor its first-move constraint to the
            # actuator state actually delivered by the lower MPC, not to its
            # previous (possibly unattained) target command.
            if hasattr(self.upper_controller, "set_actual_applied"):
                self.upper_controller.set_actual_applied(self._last_output.copy())
            elif hasattr(self.upper_controller, "_last_applied"):
                self.upper_controller._last_applied = self._last_output.copy()
            target_commands = self.upper_controller.compute(
                float(t_s), states, errors, path, geometry, config
            )
            self._upper_target = np.array(
                [
                    [command.steering_rad, command.acceleration_mps2]
                    for command in target_commands
                ],
                dtype=float,
            )
            self._next_upper_update_s = float(t_s) + self.upper_update_period_s
            self.last_upper_status = str(
                getattr(self.upper_controller, "last_status", "solved")
            )
            self.last_upper_solve_time_ms = float(
                getattr(self.upper_controller, "last_solver_time_ms", np.nan)
            )
            self.last_sqp_iterations = int(
                getattr(self.upper_controller, "last_sqp_iterations", 0)
            )

        self.last_lower_updated = float(t_s) + tolerance >= self._next_lower_update_s
        if self.last_lower_updated:
            self._last_output = self.lower_controller.compute(self._upper_target, config)
            self._next_lower_update_s = float(t_s) + self.lower_update_period_s
            self.last_lower_status = ",".join(self.lower_controller.last_statuses)
            self.last_lower_solve_time_ms = self.lower_controller.last_solve_time_ms

        upper_usable = self.last_upper_status in {
            "solved",
            "solved inaccurate",
            "maximum iterations reached",
        } or self.last_upper_status.startswith("finite iterate")
        lower_usable = all(
            status in {"solved", "solved inaccurate"}
            for status in self.lower_controller.last_statuses
        )
        self.last_status = (
            "solved"
            if upper_usable and lower_usable
            else f"upper={self.last_upper_status}; lower={self.last_lower_status}"
        )
        self.last_objective = float(
            getattr(self.upper_controller, "last_objective", 0.0)
            + self.lower_controller.last_objective
        )
        self.last_solver_time_ms = float(
            np.nansum(
                [self.last_upper_solve_time_ms, self.last_lower_solve_time_ms]
            )
        )
        return tuple(
            ControlCommand(
                acceleration_mps2=float(control[1]),
                steering_rad=float(control[0]),
            )
            for control in self._last_output
        )  # type: ignore[return-value]


@dataclass
class FixedBlendPredictiveController:
    """Blend physical and Koopman MPC commands with a fixed, non-switching weight."""

    physical_controller: object
    koopman_controller: object
    physical_weight: float = 0.75
    name: str = "固定融合上层模型预测控制"
    coordinate_frame: str = field(default="frenet", init=False)
    last_status: str = field(default="not_run", init=False)
    last_objective: float = field(default=float("nan"), init=False)
    last_solver_time_ms: float = field(default=float("nan"), init=False)
    last_sqp_iterations: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.physical_weight <= 1.0:
            raise ValueError("physical_weight must be in [0, 1]")

    def reset(self) -> None:
        self.physical_controller.reset()
        self.koopman_controller.reset()
        self.last_status = "not_run"
        self.last_objective = float("nan")
        self.last_solver_time_ms = float("nan")
        self.last_sqp_iterations = 0

    def set_environment(self, vehicle_tire_mu: np.ndarray, payload: object) -> None:
        for controller in (self.physical_controller, self.koopman_controller):
            if hasattr(controller, "set_environment"):
                controller.set_environment(vehicle_tire_mu, payload)

    def set_actual_applied(self, controls: np.ndarray) -> None:
        values = np.asarray(controls, dtype=float)
        for controller in (self.physical_controller, self.koopman_controller):
            if hasattr(controller, "_last_applied"):
                controller._last_applied = values.copy()

    def compute(self, *args):
        physical = self.physical_controller.compute(*args)
        koopman = self.koopman_controller.compute(*args)
        physical_values = np.array(
            [[item.steering_rad, item.acceleration_mps2] for item in physical],
            dtype=float,
        )
        koopman_values = np.array(
            [[item.steering_rad, item.acceleration_mps2] for item in koopman],
            dtype=float,
        )
        blended = (
            self.physical_weight * physical_values
            + (1.0 - self.physical_weight) * koopman_values
        )
        physical_status = str(getattr(self.physical_controller, "last_status", "solved"))
        koopman_status = str(getattr(self.koopman_controller, "last_status", "solved"))
        usable = (
            physical_status in {"solved", "maximum iterations reached"}
            or physical_status.startswith("finite iterate")
        ) and koopman_status in {"solved", "solved inaccurate"}
        self.last_status = "solved" if usable else (
            f"physical={physical_status}; koopman={koopman_status}"
        )
        self.last_objective = float(
            getattr(self.physical_controller, "last_objective", 0.0)
            + getattr(self.koopman_controller, "last_objective", 0.0)
        )
        self.last_solver_time_ms = float(
            np.nansum(
                [
                    getattr(self.physical_controller, "last_solver_time_ms", np.nan),
                    getattr(self.koopman_controller, "last_solver_time_ms", np.nan),
                ]
            )
        )
        self.last_sqp_iterations = int(
            getattr(self.koopman_controller, "last_sqp_iterations", 0)
        )
        return tuple(
            ControlCommand(
                acceleration_mps2=float(row[1]),
                steering_rad=float(row[0]),
            )
            for row in blended
        )


def _prediction_matrices(
    transition: np.ndarray,
    input_gain: np.ndarray,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    state_size = transition.shape[0]
    prediction = np.zeros((state_size * horizon, state_size * horizon), dtype=float)
    initial = np.zeros((state_size * horizon, state_size), dtype=float)
    for step in range(horizon):
        initial[step * state_size : (step + 1) * state_size] = np.linalg.matrix_power(
            transition, step + 1
        )
        for previous in range(step + 1):
            prediction[
                step * state_size : (step + 1) * state_size,
                previous * state_size : (previous + 1) * state_size,
            ] = np.linalg.matrix_power(transition, step - previous) @ input_gain
    return prediction, initial


def _difference_matrix(horizon: int) -> np.ndarray:
    matrix = np.zeros((2 * horizon, 2 * horizon), dtype=float)
    for step in range(horizon):
        start = 2 * step
        matrix[start : start + 2, start : start + 2] = np.eye(2)
        if step > 0:
            matrix[start : start + 2, start - 2 : start] = -np.eye(2)
    return matrix
