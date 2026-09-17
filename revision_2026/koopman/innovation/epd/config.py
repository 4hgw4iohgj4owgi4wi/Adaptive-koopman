from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class EPDConfig:
    project: Path
    @property
    def code(self): return self.project/'revision_2026'/'koopman'/'innovation'/'epd'
    @property
    def results(self): return self.project/'revision_2026'/'koopman'/'innovation_epd_results'
    @property
    def data(self): return self.project/'revision_2026'/'koopman'/'innovation_efd_r13_results'/'u4_data'
    @property
    def core_model(self): return self.project/'revision_2026'/'koopman'/'innovation_efd_r13_results'/'u5_vehicle_fair'/'models'/'V-FL92-U8.npz'
    ridge_grid=(1e-8,1e-6,1e-4,1e-2,1.,1e2)
    base_candidates=(261000,271000,281000)

