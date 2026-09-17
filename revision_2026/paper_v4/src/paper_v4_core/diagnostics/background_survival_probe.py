"""Short child-process survival probe for long EXP-R4-B runs."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--seconds",type=float,default=15.0);a=p.parse_args();out=Path(a.out).resolve()
    started=time.time();time.sleep(a.seconds);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({"status":"PASS","pid_survived_s":a.seconds,"started_unix":started,"finished_unix":time.time()},indent=2),encoding="utf-8")


if __name__=="__main__":main()
