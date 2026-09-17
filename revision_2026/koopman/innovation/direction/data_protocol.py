from __future__ import annotations
from typing import Any

GROUPS=("G0","G1","G2","G3")
SPEED=(2.,2.5,3.,4.); FRONT=(8.,10.,12.,15.); REAR=(-.3,-.5,-1.); PROFILE=("hold","reversal")

def config_for(group:int,index:int)->dict[str,Any]|None:
    if group==0 and index%2==0:return None
    speed=SPEED[index%4]; front=FRONT[(index//2)%4]; rear=REAR[(index//3)%3]; profile=PROFILE[(index//5)%2]
    if group==0:front=min(front,10.); profile="hold"; mode="front-rear"
    elif group==1:mode="front-rear"; profile="hold"
    elif group==2:mode="diagonal"; front=max(front,12.)
    else:mode="diagonal"; profile="reversal"
    return {"config_id":200+group*20+index,"speed":speed,"front_deg":front,"rear_ratio":rear,"mode":mode,"profile":profile}

def _job(seed:int,split:str,group:int,index:int)->dict[str,Any]:
    scenes=(("E0","E2"),("E1","E6"),("E5","E2"),("E3","E6")); config=config_for(group,index)
    return {"seed":seed,"traj_id":seed,"split":split,"group":GROUPS[group],"scenario":scenes[group][index%2],"physical_scene":scenes[group][index%2],"external":False,"parameter_external":False,
            "network_profile":"clean","network_trace_id":"clean","coverage_tier":"nominal" if config is None else f"D{config['config_id']}","config":config}

def pilot_jobs()->list[dict[str,Any]]:return [_job(seed,"pilot",(seed-180001)//4,(seed-180001)%4) for seed in range(180001,180017)]

def formal_jobs()->list[dict[str,Any]]:
    jobs=[]
    for split,start,per in (("train",161001,48),("validation",162001,16),("development",163001,16)):
        for group in range(4):
            for index in range(per):jobs.append(_job(start+group*per+index,split,group,index))
    return jobs

def append_jobs(round_id:int)->list[dict[str,Any]]:
    if round_id not in (1,2):raise ValueError(round_id)
    start=167001 if round_id==1 else 168001;jobs=[];scenes=(("E0","E2"),("E1","E6"),("E5","E2"),("E3","E6"))
    for group in range(4):
        for index in range(8):
            seed=start+group*8+index
            if group==0:config=None if index%2==0 else {"config_id":300+round_id*10+index,"speed":2.,"front_deg":8.,"rear_ratio":-.3,"mode":"front-rear","profile":"hold"}
            elif group==1:config={"config_id":320+round_id*10+index,"speed":2.5,"front_deg":10.,"rear_ratio":-.5,"mode":"front-rear","profile":"hold"}
            elif group==2:config={"config_id":340+round_id*10+index,"speed":4.,"front_deg":15.,"rear_ratio":-1.,"mode":"diagonal","profile":"hold"}
            else:config={"config_id":360+round_id*10+index,"speed":4.,"front_deg":15.,"rear_ratio":-1.,"mode":"diagonal","profile":"reversal"}
            jobs.append({"seed":seed,"traj_id":seed,"split":"train","group":GROUPS[group],"scenario":scenes[group][index%2],"physical_scene":scenes[group][index%2],"external":False,"parameter_external":False,"network_profile":"clean","network_trace_id":"clean","coverage_tier":f"append_r{round_id}","config":config,"append_round":round_id})
    return jobs

def all_requested_seeds()->list[int]:return list(range(180001,180017))+list(range(161001,161193))+list(range(162001,162065))+list(range(163001,163065))+list(range(167001,167033))+list(range(168001,168033))+list(range(181001,181006))+[182999]+list(range(171001,171161))
