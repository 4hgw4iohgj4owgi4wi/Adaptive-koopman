from __future__ import annotations
from typing import Any
import numpy as np
from heads import RidgeHead
from physics_decoder import unit,reconstruct_load
from metrics import evaluate
def predictions(data:dict[str,Any],mag:RidgeHead,point:RidgeHead,direction_floor:float)->dict[str,dict[str,np.ndarray]]:
    n=data["norms"];out={};p1=data["h2"];p1phys=p1[...,46:64]*n["force_std"]+n["force_mean"];out["E1"]={"x":p1[...,:46],"points":p1phys[...,:8].reshape(len(p1),20,4,2),"q":p1phys[...,8:10]}
    if "k1x" in data:
        kf=data["k1f"]*n["force_std"]+n["force_mean"];out["E0"]={"x":data["k1x"],"points":kf[...,:8].reshape(len(kf),20,4,2),"q":kf[...,8:10]}
    state=p1[...,:46]*n["x_std"]+n["x_mean"];d=state[...,30:38].reshape(len(state),20,4,2);direction,valid=unit(d,direction_floor);m=mag.predict(data["x0"],data["u"]);p=m[...,None]*direction;out["E2"]={"x":p1[...,:46],"points":p,"q":reconstruct_load(p),"valid":valid};p=point.predict(data["x0"],data["u"]);out["E3"]={"x":p1[...,:46],"points":p,"q":reconstruct_load(p)};return out
