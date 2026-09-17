from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class DirectionConfig:
    project_root:Path
    horizon:int=20; control_dt_s:float=.02; state_dim:int=46; control_dim:int=8; point_count:int=4
    ridge_grid:tuple[float,...]=(1e-8,1e-6,1e-4,1e-2); scale_grid:tuple[float,...]=(.5,1.,2.)
    train_seeds:tuple[int,...]=(181001,181002,181003,181004,181005); max_direction_fallback_rate:float=.01; prediction_p99_ms:float=8.
    @property
    def koopman_root(self)->Path:return self.project_root/"revision_2026"/"koopman"
    @property
    def old_code(self)->Path:return self.koopman_root/"innovation"
    @property
    def old_results(self)->Path:return self.koopman_root/"innovation_results"
    @property
    def code_root(self)->Path:return self.old_code/"direction"
    @property
    def results_root(self)->Path:return self.koopman_root/"innovation_direction_results"
