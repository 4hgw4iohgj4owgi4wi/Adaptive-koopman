"""EXP-R4-B B2a: four fixed-QP serial/8-process exact regressions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from ..cli import sha
from ..controllers import physical_tracking_pilot as controller
from ..controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
from ..controllers.physical_tracking_pilot import PilotConfig
from ..e01_100m import params
from .qp_fd_trials import array_digest
from .qp_sensitivity import load_raw, reference_state, row_at, solve_fixed, state_and_previous


TIMES = (42.40, 42.58, 43.06, 43.12)


def problem_hashes(problem):
    return {name: array_digest(np.asarray(problem[name])) for name in ("P", "q", "A", "l", "u", "u_nom")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    protocol_path = Path(args.protocol).resolve(); json.loads(protocol_path.read_text(encoding="utf-8-sig"))
    if sha(protocol_path) != args.protocol_sha.lower(): raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    out = Path(args.out).resolve()
    if out.exists(): raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True); (out / "matrices").mkdir()
    source = Path(args.source).resolve(); values, columns = load_raw(source); model = params("P0")
    config = PilotConfig(horizon=20, lambda_internal=2.0, finite_difference_scale=1.0, frozen_dynamics_jacobian=False)
    report = {"schema_version":"EXP-R4B-B2a-v1","status":"RUNNING","protocol_sha256":sha(protocol_path),"source":{"path":str(source),"sha256":sha(source)},"times":list(TIMES),"pairs":[]}
    with ParallelFiniteDifferenceBackend(8) as backend:
        first = row_at(values, columns, TIMES[0]); warm_state, warm_previous = state_and_previous(first, columns); _,_,warm_u,_=reference_state(TIMES[0],model,warm_previous)
        report["pool_warmup_s"] = backend.warm(warm_state, warm_u[0], model)
        for index, time_s in enumerate(TIMES):
            sample = row_at(values, columns, time_s); z0, previous = state_and_previous(sample, columns); _,_,u_nom,refs=reference_state(time_s,model,previous)
            started=time.perf_counter(); serial=controller.build_problem(z0,u_nom,refs,model,config); serial_s=time.perf_counter()-started
            with install_parallel_linearization(backend):
                started=time.perf_counter(); parallel=controller.build_problem(z0,u_nom,refs,model,config); parallel_s=time.perf_counter()-started
            serial_solution=solve_fixed(serial,z0,model,config); parallel_solution=solve_fixed(parallel,z0,model,config)
            exact={name:bool(np.array_equal(np.asarray(serial[name]),np.asarray(parallel[name]),equal_nan=True)) for name in ("P","q","A","l","u","u_nom")}
            first_control_exact=bool(np.array_equal(serial_solution["control"][0],parallel_solution["control"][0]))
            np.savez_compressed(out/"matrices"/f"pair_{index}_{time_s:.2f}.npz", serial_P=serial["P"],serial_q=serial["q"],serial_A=serial["A"],serial_l=serial["l"],serial_u=serial["u"],serial_u_nom=serial["u_nom"],parallel_P=parallel["P"],parallel_q=parallel["q"],parallel_A=parallel["A"],parallel_l=parallel["l"],parallel_u=parallel["u"],parallel_u_nom=parallel["u_nom"])
            pair={"time_s":time_s,"serial_build_s":serial_s,"parallel_build_s":parallel_s,"exact":exact,"serial_hashes":problem_hashes(serial),"parallel_hashes":problem_hashes(parallel),"first_control_exact":first_control_exact,"first_control_sha256":array_digest(serial_solution["control"][0]),"serial_validation":serial_solution["validation"]["status"],"parallel_validation":parallel_solution["validation"]["status"],"solver_status_equal":serial_solution["status"]==parallel_solution["status"]}
            report["pairs"].append(pair); (out/"progress.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            print(json.dumps({"point":index+1,"time_s":time_s,"serial_s":serial_s,"parallel_s":parallel_s,"exact":all(exact.values()) and first_control_exact}),flush=True)
    report["checks"]={"exactly_four_pairs":len(report["pairs"])==4,"all_problem_arrays_exact":all(all(p["exact"].values()) for p in report["pairs"]),"all_first_controls_exact":all(p["first_control_exact"] for p in report["pairs"]),"all_validations_pass":all(p[side+"_validation"]=="PASS" for p in report["pairs"] for side in ("serial","parallel")),"all_solver_status_equal":all(p["solver_status_equal"] for p in report["pairs"])}
    report["status"]="PASS" if all(report["checks"].values()) else "FAIL"; report["source_sha256"]=sha(__file__)
    (out/"qp_equivalence.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":report["status"],"checks":report["checks"]}),flush=True)
    if report["status"]!="PASS": raise SystemExit(20)


if __name__ == "__main__": main()
