from __future__ import annotations
import argparse, csv, hashlib, io, json, os, platform, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

def sha(p):
    h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
def manifest(root):
    return {str(p.relative_to(root)).replace('\\','/'):{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
def main():
    a=argparse.ArgumentParser(); a.add_argument('--project-root',type=Path,required=True); x=a.parse_args()
    project=x.project_root.resolve(); src=project/'revision_2026/connector_r3_4'; out=project/'revision_2026/connector_r3_4_results/r0'; out.mkdir(parents=True,exist_ok=True)
    r33=json.loads((project/'revision_2026/connector_r3_3_results/n0/source_manifest.json').read_text(encoding='utf-8'))
    actual={}
    for rel in r33:
        p=project/'revision_2026/connector_r3_3'/rel; actual[rel]=sha(p) if p.exists() else None
    base={'expected':r33,'actual':actual,'passed':r33==actual}
    tasklines=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,text=True).stdout
    parsed=list(csv.reader(io.StringIO(tasklines))); active=[r for r in parsed if len(r)>1 and r[0].lower() in {'python.exe','matlab.exe'} and int(r[1])!=os.getpid()]
    env={'timestamp':datetime.now().astimezone().isoformat(),'host':platform.node(),'python':sys.executable,'python_version':platform.python_version(),'platform':platform.platform(),'disk_free_gib':shutil.disk_usage(project.drive+'\\').free/2**30,
         'packages':{},'active_conflicting_processes':active}
    for name in ('numpy','scipy','torch'):
        try: env['packages'][name]=__import__(name).__version__
        except Exception as e: env['packages'][name]='ERROR:'+repr(e)
    env['passed']=platform.node()=='DESKTOP-9IUUGEO' and env['disk_free_gib']>=50 and not active
    for name,obj in [('environment.json',env),('baseline_manifest.json',base),('source_manifest_prechange.json',manifest(src))]: (out/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
    passed=env['passed'] and base['passed']; (out/'complete.json').write_text(json.dumps({'stage':'S0','passed':passed,'protocol_sha256':sha(src/'protocol.md')},indent=2),encoding='utf-8')
    print(json.dumps({'stage':'S0','passed':passed,'disk_free_gib':env['disk_free_gib'],'baseline_match':base['passed']})); raise SystemExit(0 if passed else 2)
if __name__=='__main__': main()
