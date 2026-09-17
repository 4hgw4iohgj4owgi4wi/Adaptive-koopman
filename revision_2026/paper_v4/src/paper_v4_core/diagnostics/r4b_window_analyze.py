"""Exact serial/parallel/source comparison for EXP-R4-B B2b."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from ..cli import sha


def archive(path):
    with np.load(path,allow_pickle=False) as z:return np.asarray(z["values"],float),[str(x) for x in z["columns"]]


def records(path):return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    p=argparse.ArgumentParser();p.add_argument("--serial",required=True);p.add_argument("--parallel",required=True);p.add_argument("--source",required=True);p.add_argument("--out",required=True);a=p.parse_args();out=Path(a.out).resolve()
    if out.exists():raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True);serial=Path(a.serial).resolve();parallel=Path(a.parallel).resolve();source=Path(a.source).resolve()
    sr,sc=archive(serial/"raw.npz");pr,pc=archive(parallel/"raw.npz");rr,rc=archive(source)
    ss,ssc=archive(serial/"substeps.npz");ps,psc=archive(parallel/"substeps.npz");rs,rsc=archive(source.parent/"substeps.npz")
    source_rows=rr[(rr[:,rc.index("time_s")]>42.0)&(rr[:,rc.index("time_s")]<=44.5)];source_sub=rs[(rs[:,rsc.index("time_s")]>42.0)&(rs[:,rsc.index("time_s")]<=44.5+1e-12)]
    comparable=[i for i,n in enumerate(sc) if n!="solver_wall_s"]; source_indices=[rc.index(sc[i]) for i in comparable]
    serial_records=records(serial/"solver.jsonl");parallel_records=records(parallel/"solver.jsonl");source_records=[r for r in records(source.parent/"solver.jsonl") if 42.0-1e-12<=float(r["time_s"])<44.5-1e-12]
    problem_exact=all(s["problem_hashes"]==q["problem_hashes"] for s,q in zip(serial_records,parallel_records))
    first_exact=all(s["first_control"]==q["first_control"] for s,q in zip(serial_records,parallel_records))
    checks={"column_identity":sc==pc and sc==rc and ssc==psc and ssc==rsc,"row_counts":len(sr)==len(pr)==len(source_rows)==125,"substep_counts":len(ss)==len(ps)==len(source_sub),"serial_reproduces_source_raw":bool(np.array_equal(sr[:,comparable],source_rows[:,source_indices],equal_nan=True)),"serial_reproduces_source_substeps":bool(np.array_equal(ss,source_sub,equal_nan=True)),"serial_reproduces_source_first_controls":len(serial_records)==len(source_records)==125 and all(s["first_control"]==r["first_control"] for s,r in zip(serial_records,source_records)),"serial_parallel_raw_exact":bool(np.array_equal(sr[:,comparable],pr[:,comparable],equal_nan=True)),"serial_parallel_substeps_exact":bool(np.array_equal(ss,ps,equal_nan=True)),"serial_parallel_problem_hashes_exact":problem_exact,"serial_parallel_first_controls_exact":first_exact,"both_completed":json.loads((serial/"metrics.json").read_text())["status"]==json.loads((parallel/"metrics.json").read_text())["status"]=="COMPLETED"}
    report={"schema_version":"EXP-R4B-B2b-compare-v1","status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"serial":str(serial),"parallel":str(parallel),"source":str(source),"serial_wall_s":json.loads((serial/"metrics.json").read_text())["wall_s"],"parallel_wall_s":json.loads((parallel/"metrics.json").read_text())["wall_s"],"source_sha256":sha(__file__)}
    (out/"window_equivalence.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(report,ensure_ascii=False),flush=True)
    if report["status"]!="PASS":raise SystemExit(20)


if __name__=="__main__":main()
