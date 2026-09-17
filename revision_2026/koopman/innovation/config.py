from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InnovationConfig:
    project_root: Path
    horizon: int = 20
    control_dt_s: float = 0.02
    plant_dt_s: float = 0.002
    state_s3_dim: int = 46
    state_main_dim: int = 30
    control_dim: int = 8
    point_force_shape: tuple[int, int] = (4, 2)
    load_dim: int = 2
    ranks: tuple[int, ...] = (1, 2, 4, 8)
    ridge_grid: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2)
    min_mode_train_windows: int = 2000
    min_mode_validation_windows: int = 500
    min_mode_development_windows: int = 500
    max_switch_hz: float = 0.5
    min_dwell_s: float = 1.0
    force_warning_ratio: float = 0.8
    component_seeds: tuple[int, ...] = (151001, 151002, 151003, 151004, 151005)

    @property
    def koopman_root(self) -> Path:
        return self.project_root / "revision_2026" / "koopman"

    @property
    def innovation_root(self) -> Path:
        return self.koopman_root / "innovation"

    @property
    def results_root(self) -> Path:
        return self.koopman_root / "innovation_results"

