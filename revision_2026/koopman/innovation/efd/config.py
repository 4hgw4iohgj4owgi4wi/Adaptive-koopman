from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path

@dataclass(frozen=True)
class EFDConfig:
    project_root:Path
    horizon:int=20;control_dt_s:float=.02;plant_dt_s:float=.002
    h2_sha256:str="3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC"
    k1_sha256:str="A3EA666624E3A01BCE2B173881990906BE1B1A2EEF10465FC82AC92C813757E3"
    ridge_grid:tuple[float,...]=(1e-8,1e-6,1e-4,1e-2);theta_grid:tuple[int,...]=(15,30,45)
    @property
    def koopman(self)->Path:return self.project_root/"revision_2026"/"koopman"
    @property
    def code_root(self)->Path:return self.koopman/"innovation"/"efd"
    @property
    def results(self)->Path:return self.koopman/"innovation_efd_results"
    def jsonable(self)->dict:
        d=asdict(self);d["project_root"]=str(self.project_root);return d
