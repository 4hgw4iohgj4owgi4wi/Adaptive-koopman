"""Read-only historical identity/access audit. Never reads confirmation arrays."""
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest().upper()

def array_digest(p, aliases=None):
    h=hashlib.sha256()
    with np.load(p,allow_pickle=False) as z:
        for k in sorted(z.files):
            a=z[k];h.update((aliases or {}).get(k,k).encode());h.update(str((a.shape,a.dtype)).encode());h.update(a.tobytes())
    return h.hexdigest().upper()

def main(out):
    rev=Path(__file__).resolve().parents[3]
    run=rev/'koopman_predict_v3w_results/runs/20260905_221832_KC_BG02'
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    source=json.loads((run/'identity.json').read_text())['source']
    source_checks=[]
    for rel,expected in source.items():
        p=rev/'koopman_predict_v3w'/rel
        actual=sha(p) if p.exists() else None
        source_checks.append({'path':str(p),'expected':expected,'actual':actual,'match':actual==expected})
    manifest=rev/'koopman_predict_auto_results/runs/20260901_214725_AUTO_PREDICT_AUTO_R04_R01/n5/data_manifest.csv'
    with manifest.open(encoding='utf-8-sig',newline='') as f:entries=list(csv.DictReader(f))
    byname={Path(r['cache_path']).name.lower():r for r in entries}
    counters=Counter();pools=defaultdict(set);families=defaultdict(set);denied=[];unmapped=[]
    with (run/'split_access.jsonl').open(encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);ctx=r.get('context');ctxkey=json.dumps(ctx,sort_keys=True)
            role=r.get('role','UNKNOWN');counters[(ctxkey,role)]+=1
            if not r.get('allowed',False):denied.append(r)
            key=Path(r['path']).name.lower();entry=byname.get(key)
            if entry is None:unmapped.append(key)
            fold=ctx[0] if isinstance(ctx,list) and ctx else 'UNKNOWN'
            pools[(str(fold),role)].add(key)
            if entry:families[(str(fold),role)].add(entry['base_family_id'])
    overlap=[]
    for fold in sorted({k[0] for k in families}):
        roles=sorted({k[1] for k in families if k[0]==fold})
        for i,a in enumerate(roles):
            for b in roles[i+1:]:
                shared=families[(fold,a)]&families[(fold,b)]
                if shared:overlap.append({'fold':fold,'roles':[a,b],'shared_families':sorted(shared)})
    checkpoint_expected=['988AEB514191071EC2A9770A58FA201051EA81559206A6926118215044FDB268','59737EFAB937B6938D39856BBB7F00FC9594ACEe7D5FDF87C1B7708B434C9621'.upper(),'81A5A974778DBA009128092B9983D321539A1376BDAD9ED7D869811A7AB0106F']
    checkpoints=[]
    for repeat,expected in enumerate(checkpoint_expected):
        p=run/f'formal/repeat{repeat}/fold0/fixed_guard/train/best.pt'
        checkpoints.append({'repeat':repeat,'path':str(p),'sha256':sha(p),'expected':expected,'match':sha(p)==expected,'seed':997100+100*repeat,'gamma':[.75,.5,.5][repeat]})
    norm=run/'folds/fold0/normalization.npz';s0=run/'folds/fold0/s0.npz'
    report={'status':'PARTIAL','source_checks':source_checks,'checkpoint_checks':checkpoints,'normalization':{'path':str(norm),'file_sha256':sha(norm),'array_content_digest':array_digest(norm)},'S0':{'path':str(s0),'file_sha256':sha(s0),'array_content_digest':array_digest(s0)},'manifest':{'path':str(manifest),'sha256':sha(manifest),'rows':len(entries),'columns':list(entries[0])},'access_ledger':{'path':str(run/'split_access.jsonl'),'sha256':sha(run/'split_access.jsonl'),'total_records':sum(counters.values()),'denied':denied,'unmapped':sorted(set(unmapped))},'roles':[{'context':json.loads(ctx),'role':role,'reads':n} for (ctx,role),n in sorted(counters.items())],'pools':[{'fold':fold,'role':role,'files':sorted(names),'families':sorted(families[(fold,role)])} for (fold,role),names in sorted(pools.items())],'cross_role_family_overlap':overlap,'confirmation_blindness':'NOT_PROVEN_BY_SINGLE_RUN_LEDGER','remaining':['trace historical production source freeze','trace imported backbone/model fit and selection','audit all later 42/84 selection accesses','verify normalization fit pool']}
    report['S0']['registered_content_digest']=array_digest(s0,{'coefficients':'coeff'})
    report['S0']['digest_definition_source']='koopman_predict_v3w/scripts/run_background.py:252; digest_arrays(dict(coeff=s0[coefficients]))'
    report['S0']['registered_match']=report['S0']['registered_content_digest']=='4F0B403E0115A0E196D9F4BCBC2979155B67CAF67F79A12F5DD214F5596CCF07'
    assert report['S0']['registered_match']
    (out/'data_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'source_total':len(source_checks),'source_mismatches':[r['path'] for r in source_checks if not r['match']],'checkpoint_checks':checkpoints,'norm_digest':report['normalization']['array_content_digest'],'s0_digest':report['S0']['array_content_digest'],'manifest_rows':len(entries),'ledger_records':sum(counters.values()),'roles':sorted({k[1] for k in counters}),'unmapped':len(set(unmapped)),'family_overlaps':len(overlap)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
