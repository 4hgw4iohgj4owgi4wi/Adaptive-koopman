"""Finite identity tests for EXP-R2 R1 diagnostic frames and decomposition."""
import argparse
from pathlib import Path

import numpy as np

from .cli import save, sha
from .diagnostics.internal_loading import decompose
from .diagnostics.relative_motion import extract
from .e01_100m import params
from .plant.four_vehicle_common import initialize_state, rotation


def run(out):
    model=params("P0");q=model.payload_anchor_body_m-np.asarray(model.vehicle_anchor_body_m);beta=np.zeros(4)
    x=initialize_state(model,2.0);base=extract(x,model,q,beta)
    tests=[{"name":"initial_relative_identity","pass":bool(np.max(np.abs(base["e_g_m"]))<1e-12 and np.max(np.abs(base["e_beta_rad"]))<1e-12 and np.max(np.abs(base["relative_velocity_body_mps"]))<1e-12)}]
    xr=x.copy();xr[26]=np.pi/2
    for i in range(4):
        xr[6*i:6*i+2]=rotation(np.pi/2)@q[i];xr[6*i+2]=np.pi/2;xr[6*i+3]=2.0;xr[6*i+4]=0.0
    xr[24:26]=0.0;xr[27]=2.0;xr[28]=0.0
    xr[0:2]+=np.asarray([0.0,1e-3])
    rotated=extract(xr,model,q,beta)
    tests.append({"name":"payload_frame_rotation","pass":bool(np.allclose(rotated["e_g_m"][0],[1e-3,0.0],atol=1e-12))})
    force=np.asarray([[2.,1.],[-1.,3.],[4.,-2.],[-3.,-2.]])
    dec=decompose(force,model.payload_anchor_body_m,0.0,np.zeros((4,2)))
    tests.append({"name":"internal_nullspace","pass":bool(np.max(np.abs(dec["null_residual_n_nm"]))<1e-10)})
    relv=np.zeros((4,2));relv[0]=[1.,0.];power=decompose(np.asarray([[1.,0.],[0.,0.],[0.,0.],[0.,0.]]),model.payload_anchor_body_m,0.0,relv)
    tests.append({"name":"pair_power_sign","pass":bool(np.allclose(power["connector_pair_power_w"],[-1.,0.,0.,0.]))})
    report={"status":"PASS" if all(t["pass"] for t in tests) else "FAIL","tests":tests,"source_sha256":sha(__file__)}
    save(Path(out),"r1_diagnostic_tests.json",report);print(report)
    if report["status"]!="PASS":raise SystemExit(20)


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args();run(a.out)


if __name__=="__main__":main()
