from __future__ import annotations

from typing import Any


GROUPS = ("G0_slack_low", "G1_loading", "G2_sustained", "G3_transition")

CONFIGS: dict[str, dict[str, Any] | None] = {
    "nominal": None,
    "loading": {"config_id": 150, "speed": 2.5, "front_deg": 10.0, "rear_ratio": -0.5, "mode": "front-rear", "profile": "hold"},
    "high_round1": {"config_id": 151, "speed": 4.0, "front_deg": 15.0, "rear_ratio": -1.0, "mode": "left-right", "profile": "hold"},
    "high_round2": {"config_id": 152, "speed": 2.5, "front_deg": 15.0, "rear_ratio": -1.0, "mode": "diagonal", "profile": "hold"},
    "high_round3": {"config_id": 153, "speed": 4.0, "front_deg": 15.0, "rear_ratio": -1.0, "mode": "diagonal", "profile": "hold"},
    "transition": {"config_id": 154, "speed": 2.5, "front_deg": 15.0, "rear_ratio": -1.0, "mode": "diagonal", "profile": "reversal"},
}


def pilot_jobs() -> list[dict[str, Any]]:
    jobs=[]
    for local,seed in enumerate(range(130001,130049)):
        group=local//12; within=local%12
        if group==0: config="nominal"; scene=("E0","E2")[within%2]
        elif group==1: config="loading"; scene=("E1","E6")[within%2]
        elif group==2: config=("high_round1","high_round2","high_round3")[within//4]; scene="E5"
        else: config="transition"; scene=("E3","E6")[within%2]
        jobs.append({"seed":seed,"traj_id":seed,"split":"pilot","group":GROUPS[group],"scenario":scene,"physical_scene":scene,
                     "external":False,"parameter_external":False,"network_profile":"clean","network_trace_id":"clean",
                     "coverage_tier":config,"config_name":config})
    return jobs


def formal_jobs(selected_high: str) -> list[dict[str, Any]]:
    jobs=[]
    for split,start,per_group in (("train",131001,60),("validation",132001,20),("development",133001,20)):
        for group in range(4):
            for within in range(per_group):
                seed=start+group*per_group+within
                if group==0: config="nominal"; scene=("E0","E2")[within%2]
                elif group==1: config="loading"; scene=("E1","E6")[within%2]
                elif group==2: config=selected_high; scene=("E5","E2")[within%2]
                else: config="transition"; scene=("E3","E6")[within%2]
                jobs.append({"seed":seed,"traj_id":seed,"split":split,"group":GROUPS[group],"scenario":scene,"physical_scene":scene,
                             "external":False,"parameter_external":False,"network_profile":"clean","network_trace_id":"clean",
                             "coverage_tier":config,"config_name":config})
    return jobs

