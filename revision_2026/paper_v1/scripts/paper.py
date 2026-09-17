from __future__ import annotations

import argparse, datetime as dt, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from contracts import validate_protocol
from identity import audit_sources


def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".partial")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,p)


def main():
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="command",required=True)
    for name in ("validate","plan","smoke"):
        p=sp.add_parser(name);p.add_argument("--project",required=name=="validate")
        p.add_argument("--protocol",required=True);p.add_argument("--batch",default="Q1")
        p.add_argument("--taskbook",default=str(ROOT/"protocol"/"paper_run.md"))
    p=sp.add_parser("audit-resume");p.add_argument("--run",required=True)
    args=ap.parse_args()
    if args.command=="audit-resume":
        run=Path(args.run).resolve();root=(ROOT.parent/"paper_results"/"runs").resolve()
        if root not in run.parents or not (run/"identity.json").is_file(): raise SystemExit(22)
        print(json.dumps({"passed":True,"run":str(run)},ensure_ascii=False));return
    cfg=validate_protocol(args.protocol)
    if args.batch!="Q1" or cfg["batch"]!="Q1": raise SystemExit(22)
    project=Path(args.project).resolve() if args.project else ROOT.parent.parent
    if args.command=="validate":
        result=audit_sources(project,args.protocol,args.taskbook);result["passed"]=True
        write(ROOT/"last_validate.json",result);print(json.dumps(result,ensure_ascii=False));return
    old=Path(cfg["old_run"]); existing=len(list((old/"outer").rglob("quality.json")))
    result={"batch":"Q1","frozen_models":45,"candidate_states":90,"legal_existing_candidates":existing,
            "new_evaluations":90,"reuse_decision":"rerun in isolated source to keep one implementation identity",
            "training":0,"estimated_wall_hours":2.5,"estimated_new_gib":3.0,
            "prerequisites":["R0","P0","K0"],"stop":"K1 verdict"}
    if args.command=="plan": print(json.dumps(result,ensure_ascii=False,indent=2));return
    stamp=dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run=ROOT.parent/"paper_results"/"runs"/(stamp+"_Q1_SMOKE")
    cmd=[sys.executable,"-B",str(Path(cfg["predictor_source"])/"scripts"/"resume_outer.py"),
         "--project",str(project),"--run",str(run),"--old-run",cfg["old_run"],
         "--taskbook",args.taskbook,"--smoke"]
    cp=subprocess.run(cmd,check=False)
    if cp.returncode: raise SystemExit(cp.returncode)
    print(json.dumps({"passed":True,"run":str(run)},ensure_ascii=False))


if __name__=="__main__": main()
