from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EFDR1Config:
    project_root: Path
    protocol_sha256: str = "F0682BAA2E01095E6B475DF8F3B4611040A58DE2A8BD5E233C06B05548866187"
    base_candidates: tuple[int, ...] = (201000, 211000, 221000)
    horizon: int = 20
    control_dt_s: float = .02
    plant_dt_s: float = .002
    epsilon_dir_m: float = 1e-8
    ridge_grid: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2)
    h2_sha256: str = "3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC"
    k1_sha256: str = "A3EA666624E3A01BCE2B173881990906BE1B1A2EEF10465FC82AC92C813757E3"

    @property
    def koopman(self) -> Path:
        return self.project_root / "revision_2026" / "koopman"

    @property
    def code_root(self) -> Path:
        return self.koopman / "innovation" / "efd_r1"

    @property
    def results(self) -> Path:
        return self.koopman / "innovation_efd_r1_results"

    def jsonable(self) -> dict:
        d = asdict(self); d["project_root"] = str(self.project_root); return d


def seed_block(base: int) -> dict[str, list[int]]:
    return {
        "pilot": list(range(base + 1, base + 17)),
        "train": list(range(base + 1001, base + 1257)),
        "validation": list(range(base + 2001, base + 2097)),
        "development": list(range(base + 3001, base + 3065)),
        "confirm": list(range(base + 4001, base + 4161)),
        "bootstrap": list(range(base + 5001, base + 5006)),
        "statistics": [base + 5999],
    }
