from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from connector_v2 import ConnectorV2Params
from paired_maneuvers import run_all
if __name__=='__main__':
 p=ConnectorV2Params(**json.loads(Path(sys.argv[2]).read_text()));r=run_all(Path(sys.argv[1]),p,Path(sys.argv[3]));print(json.dumps({'passed':r['passed'],'g4':r['g4_checks'],'g5':r['g5_passed']}));raise SystemExit(0 if r['passed'] else 2)
