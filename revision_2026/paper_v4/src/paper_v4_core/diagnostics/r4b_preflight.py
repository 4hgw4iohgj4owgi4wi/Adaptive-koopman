"""EXP-R4-B B0/B1 frozen budget and incremental identity gate."""
from __future__ import annotations
import argparse,json,platform,sys,time
from pathlib import Path
from ..cli import save,sha

PAPER=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser();p.add_argument("--protocol",required=True);p.add_argument("--protocol-sha",required=True);p.add_argument("--active-process-count",type=int,required=True);p.add_argument("--out",required=True);a=p.parse_args()
    out=Path(a.out).resolve()
    if out.exists():raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    protocol_path=Path(a.protocol).resolve();protocol=json.loads(protocol_path.read_text(encoding="utf-8-sig"));snapshot=PAPER/protocol["source_snapshot"]
    current={"pilot_runner.py":PAPER/"src/paper_v4_core/pilot_runner.py","r2c_analyze.py":PAPER/"src/paper_v4_core/r2c_analyze.py","controllers/physical_tracking_pilot.py":PAPER/"src/paper_v4_core/controllers/physical_tracking_pilot.py","controllers/parallel_fd_backend.py":PAPER/"src/paper_v4_core/controllers/parallel_fd_backend.py","diagnostics/r4b_qp_equivalence.py":PAPER/"src/paper_v4_core/diagnostics/r4b_qp_equivalence.py","diagnostics/r4b_window_runner.py":PAPER/"src/paper_v4_core/diagnostics/r4b_window_runner.py","diagnostics/r4b_window_analyze.py":PAPER/"src/paper_v4_core/diagnostics/r4b_window_analyze.py"}
    expected=protocol["source_sha256"]
    u1=json.loads((PAPER/"results/20260913_U1_IDENTITY01/identity_reaudit.json").read_text(encoding="utf-8"));u3=json.loads((PAPER/"results/20260913_U3_PARALLEL_EQ01/parallel_equivalence.json").read_text(encoding="utf-8"))
    checks={"protocol_sha":sha(protocol_path)==a.protocol_sha.lower(),"taskbook_sha":sha(PAPER/protocol["taskbook"]["path"])==protocol["taskbook"]["sha256"],"parent_sha":sha(PAPER/"inputs/experiment_EXP-R4_97D79F76.md")==protocol["parent_protocol"]["sha256"],"current_sources":all(path.is_file() and sha(path)==expected[name] for name,path in current.items()),"snapshot_sources":all((snapshot/name).is_file() and sha(snapshot/name)==digest for name,digest in expected.items()),"historical_2ms_unchanged":sha(PAPER/"results/20260911_R3_UNFROZEN_FULL01/status.json")==protocol["historical_2ms_status_sha256"],"u1_identity":u1["status"]=="PASS_RECONSTRUCTED_IDENTITY","u3_parallel8_problem_exact":all(u3["matrix_exact_saved"].values()),"no_active_experiment":a.active_process_count==0}
    report={"schema_version":"EXP-R4B-B0B1-v1","status":"PASS" if all(checks.values()) else "FAIL","host":platform.node(),"python":sys.version,"created_unix":time.time(),"protocol":str(protocol_path),"protocol_sha256":sha(protocol_path),"active_process_count_external_observation":a.active_process_count,"checks":checks,"claim_limits":protocol["claim_limits"]}
    out.mkdir(parents=True);save(out,"preflight.json",report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if report["status"]!="PASS":raise SystemExit(20)


if __name__=="__main__":main()
