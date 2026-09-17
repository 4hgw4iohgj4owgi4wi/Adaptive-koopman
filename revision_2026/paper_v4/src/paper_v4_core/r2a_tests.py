"""EXP-R2 R2a identity, gradient and boundary tests for the physical MPC pilot."""
import argparse
from dataclasses import replace
from pathlib import Path
import numpy as np

from .cli import save,sha
from .controllers.physical_tracking_pilot import PilotConfig,build_problem,linearize_step,solve
from .e01_100m import params
from .plant.four_vehicle_common import initialize_state


def references(model,n):
    q=model.payload_anchor_body_m-np.asarray(model.vehicle_anchor_body_m);payload=np.asarray([0.,0.,0.,2.,0.,0.]);ref={"payload":payload,"q_star":q,"beta_star":np.zeros(4),"q_dot_star":np.zeros((4,2)),"steering_nominal":np.zeros(4),"previous_u":np.zeros(8)}
    return [dict(ref) for _ in range(n)]


def run(out):
    model=params("P0");z=np.r_[initialize_state(model,2.),np.zeros(4)];tests=[];details={}
    for n in (1,20):
        u=np.zeros((n,8));ref=references(model,n);problem=build_problem(z,u,ref,model,PilotConfig(horizon=n));result=solve(z,u,ref,model,PilotConfig(horizon=n,max_iter=4000));ok=problem["P"].shape==(8*n,8*n) and np.all(np.isfinite(problem["P"])) and result["solver_status"] not in ("non convex",)
        tests.append({"name":f"horizon_{n}_real_optimizer","pass":bool(ok)});details[f"N{n}"]={"solver_status":result["solver_status"],"validation":result["validation"],"wall_s":result["wall_s"]}
    p=build_problem(z,np.zeros((1,8)),references(model,1),model,PilotConfig(horizon=1));d=np.linspace(-1e-5,1e-5,8);analytic=float(p["q"]@d+0.5*d@p["P"]@d);eps=1e-3;fd=(0.5*(eps*d)@p["P"]@(eps*d)+p["q"]@(eps*d))/eps
    tests.append({"name":"quadratic_directional_gradient","pass":bool(abs(analytic-fd)<1e-5)})
    saturated=np.zeros((1,8));saturated[0,1::2]=np.deg2rad(30);result=solve(z,saturated,references(model,1),model,PilotConfig(horizon=1));within=np.max(abs(result["control"][0,1::2]))<=np.deg2rad(15)+1e-9
    tests.append({"name":"steering_bound_enforced","pass":bool(within)})
    bad=z.copy();bad[0]+=2.0;infeasible=solve(bad,np.zeros((1,8)),references(model,1),model,PilotConfig(horizon=1,max_iter=1000));tests.append({"name":"infeasible_or_nonlinear_rejected","pass":bool(infeasible["status"]=="FAIL")})
    perturbed=replace(model,connector=replace(model.connector,stiffness_npm=1.1*model.connector.stiffness_npm));excited=z.copy();excited[0]+=model.connector.free_play_m+model.connector.smoothing_width_m+0.005;excited[3]+=0.05
    f0,A,B=linearize_step(excited,np.zeros(8),model);f1,A1,B1=linearize_step(excited,np.zeros(8),perturbed);changed={"prediction":float(np.max(abs(f0-f1))),"A":float(np.max(abs(A-A1))),"B":float(np.max(abs(B-B1)))}
    tests.append({"name":"model_perturbation_changes_prediction_or_jacobian","pass":bool(max(changed.values())>1e-9)});details["model_perturbation_change_max_abs"]=changed
    report={"status":"PASS" if all(t["pass"] for t in tests) else "FAIL","tests":tests,"details":details,"identity":"Centralized Full-State Physical Model Predictive Control diagnostic upper bound; no Koopman","source_sha256":sha(__file__)};save(Path(out),"r2a_tests.json",report);print(report)
    if report["status"]!="PASS":raise SystemExit(20)


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args();run(a.out)
if __name__=="__main__":main()
