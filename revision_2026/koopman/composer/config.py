from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ComposerConfig:
    koopman_root: Path
    horizon: int = 20
    state_dim_s3: int = 46
    state_dim_main: int = 30
    control_dim_u1: int = 8
    expert_names: tuple[str, ...] = ("K0", "K1", "K4", "K5F2")
    fallback_expert: str = "K1"
    force_warning_ratio: float = 0.8
    control_period_s: float = 0.02
    max_switch_hz: float = 0.5
    min_dwell_s: float = 1.0
    selector_seeds: tuple[int, ...] = (109001, 109002, 109003, 109004, 109005)

    @property
    def composer_root(self) -> Path:
        return self.koopman_root / "composer"

    @property
    def result_root(self) -> Path:
        return self.koopman_root / "composer_results"

    @property
    def universal_root(self) -> Path:
        return self.koopman_root / "universal_v2"


def resolved(here: Path) -> ComposerConfig:
    return ComposerConfig(koopman_root=here.resolve().parent)

