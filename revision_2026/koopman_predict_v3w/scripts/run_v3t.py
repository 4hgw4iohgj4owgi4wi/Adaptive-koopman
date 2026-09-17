"""Guard protocol entry point; stages are implemented and admitted incrementally."""
import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

# Use sequential MKL to avoid loading a second OpenMP runtime alongside Torch.
# Do not suppress duplicate-runtime errors with KMP_DUPLICATE_LIB_OK.
os.environ['MKL_THREADING_LAYER'] = 'SEQUENTIAL'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
import numpy as np

DATA_SHA = 'B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9'
BOOK_SHA = '8F9367990910DA45B6EABB726C1FF717EFB8C745338DAFCCE382DCDF3D8A058D'
N5 = 'koopman_predict_auto_results/runs/20260901_214725_AUTO_PREDICT_AUTO_R04_R01/n5'
HISTORY = {
    'v3r': ('koopman_predict_v3r_results/runs/20260903_215712_AB_F4E19_R01/f4', 49, 'CAC4D2DD37A90C72524968A6AF7146EDE13D808D2E932DF3F7D63802DE3B7EAC'),
    'v3s': ('koopman_predict_v3s_results/runs/20260903_222641_AB_SB_SB_R01/sb4', 52, '1FB39681A4834D8601E644F8E54D3F60C01D1EB13E29431B3D4D3D2103302645'),
}

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest().upper()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write_json(path, obj):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)

def append(path, obj):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False, allow_nan=False) + '\n')

def log(run, stage, status, detail):
    append(run / 'decision_log.jsonl', dict(time=datetime.now().isoformat(), stage=stage, status=status, detail=detail))

def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, data):
    with Path(path).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)

def check(ok, msg):
    if not ok:
        raise RuntimeError(msg)

def folds(entries):
    outer = {}
    by_s = {}
    for s in range(12):
        fam = sorted({e['base_family_id'] for e in entries if e['scenario'] == f'D{s}'})
        check(len(fam) == 8, f'D{s} family count {len(fam)} !=8')
        np.random.Generator(np.random.PCG64(994700 + s)).shuffle(fam)
        by_s[s] = fam
        outer.update({x: (j + s) % 5 for j, x in enumerate(fam)})
    out = []
    for fold in range(5):
        inner = set()
        for s in range(12):
            # Sorting before seeded choice gives a canonical candidate ordering.
            eligible = sorted(x for x in by_s[s] if outer[x] != fold)
            rng = np.random.Generator(np.random.PCG64(995700 + 100 * fold + s))
            inner.add(str(rng.choice(eligible)))
        roles = {x: ('outer' if outer[x] == fold else 'inner' if x in inner else 'fit') for x in outer}
        count = Counter(roles.values())
        check(count == {'outer': [19,20,20,19,18][fold], 'inner':12, 'fit':[65,64,64,65,66][fold]}, f'fold count {count}')
        for role in ('fit','inner','outer'):
            check(len({e['scenario'] for e in entries if roles[e['base_family_id']] == role}) == 12, f'fold{fold}/{role} scenario missing')
        for e in entries:
            out.append(dict(family=e['base_family_id'], trajectory=e['trajectory_id'], scenario=e['scenario'], plant=e['plant'], law=e['law'], fold=fold, role=roles[e['base_family_id']], seed=e['seed'], cache_sha256=e['cache_sha256'], cache_path=e['cache_path']))
    return out

def g0(a, run, rev):
    dest = run / 'g0'
    dest.mkdir()
    import torch
    env = dict(time=datetime.now().isoformat(), hostname=platform.node(), python=sys.executable, python_version=sys.version,
               numpy=np.__version__, torch=torch.__version__, cuda=torch.cuda.is_available(), free_gib=shutil.disk_usage(rev).free/2**30)
    env['processes'] = subprocess.check_output(['powershell','-NoProfile','-Command', "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|MATLAB)\\.exe$' } | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"], text=True)
    env['current_pid'] = os.getpid()
    env['MKL_THREADING_LAYER'] = os.environ.get('MKL_THREADING_LAYER')
    write_json(dest/'environment.json',env)
    check(env['cuda'] and env['free_gib'] >= 60, 'resource gate failed')
    historical = {}
    for version,(rel,n,p_sha) in HISTORY.items():
        root = rev/f'koopman_predict_{version}'
        manifest = read_json(rev/rel/'source_manifest.json')
        bad = [name for name,h in manifest.items() if not (root/name).is_file() or sha(root/name)!=h.upper()]
        check(len(manifest)==n and not bad, f'{version} source mismatch {bad}')
        check(sha(root/'config'/f'protocol_{version}.json')==p_sha, f'{version} protocol mismatch')
        ident = read_json(rev/rel/'identity.json')
        check(ident['data_manifest_sha256']==DATA_SHA, f'{version} data identity mismatch')
        historical[version] = dict(file_count=n,mismatch_count=0,identity=ident,source_manifest_sha256=sha(rev/rel/'source_manifest.json'))
    manifest_path = rev/N5/'data_manifest.csv'
    check(sha(manifest_path)==DATA_SHA, 'N5 manifest identity mismatch')
    all_entries = rows(manifest_path)
    train = [e for e in all_entries if e['split']=='train']
    main = [e for e in train if e['plant']=='R3-ES' and e['law']=='R3']
    check(len(train)==336 and len({e['base_family_id'] for e in train})==96, 'train count mismatch')
    check(len(main)==168 and len({e['base_family_id'] for e in main})==96, 'R3 count mismatch')
    family_splits={}
    for e in all_entries:
        family_splits.setdefault(e['base_family_id'],set()).add(e['split'])
    check(all(len(x)==1 for x in family_splits.values()), 'historical split family leakage')
    check(not any(e['split']=='confirm' for e in all_entries), 'confirm present in visible manifest')
    audited=[]
    for i,e in enumerate(train):
        for k,hkey in [('raw_path','raw_file_sha256'),('cache_path','cache_sha256')]:
            actual=sha(e[k])
            append(run/'split_access.jsonl',dict(stage='G0',purpose='identity_hash_only',split='train',trajectory=e['trajectory_id'],path=e[k],numeric_decode=False))
            audited.append(dict(trajectory=e['trajectory_id'],kind=k,path=e[k],expected=e[hkey],actual=actual))
            check(actual==e[hkey].upper(),f'identity mismatch {e[k]}')
        if (i+1)%48==0:
            print(f'G0 hashed {i+1}/336 train trajectories',flush=True)
    write_json(dest/'baseline_files.json',audited)
    fold_rows=folds(main)
    write_csv(dest/'fold_manifest.csv',fold_rows)
    historical.update(data_manifest_sha256=DATA_SHA,train_trajectories=len(train),train_families=96,R3_trajectories=len(main),R3_families=96,
                      numeric_reads=0,forbidden_numeric_reads=0,inner_choice_order='lexicographic candidates before seeded PCG64 choice')
    write_json(dest/'historical_identity.json',historical)
    policy=dict(default='DENY',G0='metadata and hashes only; no numeric decoding',G1=dict(purpose='historical_audit',split='train',plants=['R3-ES','V1-ES']),
                G2_G3_G4_train={'normalization':['fit'],'S0':['fit'],'warm':['fit'],'optimize':['fit'],'monitor':['inner']},
                outer_evaluate='G4 only after all 15 final checkpoints and identities frozen',denied=['validation','development','new_validation','confirm'],
                enforcement_required_before_G2='actual file-open guard with stage/purpose/fold/role context; this JSON alone is not enforcement')
    write_json(dest/'data_access_policy.json',policy)
    src=rev/'koopman_predict_v3t'
    write_json(dest/'source_manifest.json',{str(p.relative_to(src)).replace('\\','/'):sha(p) for p in sorted(src.rglob('*')) if p.is_file() and '__pycache__' not in p.parts})
    write_json(dest/'complete.json',dict(status='PASS',stage='G0',data_sha256=DATA_SHA,taskbook_sha256=sha(a.taskbook),fold_manifest_sha256=sha(dest/'fold_manifest.csv'),next_stage='G1'))
    log(run,'G0','PASS',historical)
    print('G0 PASS '+str(run),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage',required=True,choices=['G0','G1','G2','G3','G4','G5'])
    p.add_argument('--project-root',required=True,type=Path)
    p.add_argument('--protocol',required=True,type=Path)
    p.add_argument('--taskbook',required=True,type=Path)
    p.add_argument('--run-tag')
    p.add_argument('--receipt-path',required=True,type=Path)
    p.add_argument('--resume-run')
    p.add_argument('--attempt-name',default='base')
    p.add_argument('--g2-attempt',default='attempt_003')
    a=p.parse_args()
    rev=a.project_root/'revision_2026'
    check(sha(a.taskbook)==BOOK_SHA,'taskbook changed; re-register required')
    if a.resume_run:
        receipt=read_json(a.receipt_path)
        check(receipt['run_id']==a.resume_run,'receipt run mismatch')
        run=rev/'koopman_predict_v3t_results/runs'/a.resume_run
        identity=read_json(run/'run_identity.json')
        check(receipt==identity,'receipt identity mismatch')
        check(identity['taskbook_sha256']==sha(a.taskbook) and identity['protocol_sha256']==sha(a.protocol) and identity['data_manifest_sha256']==sha(rev/N5/'data_manifest.csv'),'resume identity mismatch')
    else:
        check(a.stage=='G0' and a.run_tag,'new runs must start G0 with run-tag')
        check(not a.receipt_path.exists(),'receipt already exists; do not overwrite')
        run_id=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+a.run_tag
        run=rev/'koopman_predict_v3t_results/runs'/run_id
        run.mkdir(parents=True,exist_ok=False)
        identity=dict(run_id=run_id,run_tag=a.run_tag,taskbook_sha256=sha(a.taskbook),protocol_sha256=sha(a.protocol),data_manifest_sha256=DATA_SHA)
        write_json(run/'run_identity.json',identity)
        a.receipt_path.parent.mkdir(parents=True,exist_ok=True)
        write_json(a.receipt_path,identity)
        shutil.copyfile(a.taskbook,run/'taskbook_snapshot.md')
        shutil.copyfile(a.protocol,run/'protocol_snapshot.json')
    try:
        if a.stage=='G0':
            g0(a,run,rev)
        elif a.stage=='G1':
            check(read_json(run/'g0/complete.json')['status']=='PASS','G0 not passed')
            from guard_diagnosis import run_g1
            run_g1(a,run,rev)
        elif a.stage=='G2':
            check(read_json(run/'g1/complete.json')['status']=='PASS','G1 not passed')
            sys.path.insert(0,str(rev/'koopman_predict_v3t/src'))
            from guard_tests import run_g2
            run_g2(a,run,rev)
        else:
            sys.path.insert(0,str(rev/'koopman_predict_v3t/src'))
            if a.stage=='G3':
                from guard_experiments import run_g3
                run_g3(a,run,rev)
            elif a.stage=='G4':
                from guard_experiments import run_g4
                run_g4(a,run,rev)
            else:
                from guard_report import run_g5
                run_g5(a,run,rev)
    except Exception:
        detail=traceback.format_exc()
        log(run,a.stage,'BLOCKED',detail)
        (run/f'{a.stage.lower()}_failure.txt').write_text(detail,encoding='utf-8')
        print(detail,file=sys.stderr)
        raise

if __name__=='__main__':
    main()
