"""G3 cost qualification and G4 five-fold training; outer opens only after freeze."""
import copy
import json
import shutil
import sys
import time
from pathlib import Path
import numpy as np
import torch
from run_v3t import N5,check,log,read_json,rows,sha,write_csv,write_json
from guard_core import AccessGuard,Decoder,WindowData,digest,evaluate,fit_normalization,fit_s0,new_model
from guard_training import train_phase,atomic_save

def context(a,run,rev,stage):
    from frozen import FrozenN6
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    src=rev/'koopman_predict_v3t'
    protocol=read_json(src/'config/protocol_v3s.json');frozen=FrozenN6(a.project_root,protocol)
    entries=rows(rev/N5/'data_manifest.csv');fm=rows(run/'g0/fold_manifest.csv')
    guard=AccessGuard(entries,fm,run/'split_access.jsonl',stage)
    dec=Decoder(frozen.build_planar_grasp_matrix)
    return entries,fm,guard,dec,lambda e:frozen.resolved_params(int(e['seed']),protocol)

def select(entries,fm,fold,role):
    ids={r['trajectory'] for r in fm if int(r['fold'])==fold and r['role']==role}
    return [e for e in entries if e['trajectory_id'] in ids]

def source_identity(src):
    return {str(p.relative_to(src)).replace('\\','/'):sha(p) for p in sorted(src.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.md') and '__pycache__' not in p.parts}

def prepare_fold(entries,fm,guard,dec,resolver,fold,out,smoke=False):
    fitentries=select(entries,fm,fold,'fit');innerentries=select(entries,fm,fold,'inner')
    norm=fit_normalization(fitentries,guard,fold);s0=fit_s0(fitentries,norm,guard,fold)
    np.savez(out/'normalization.npz',**norm);np.savez(out/'s0.npz',coefficients=s0['coefficients'])
    write_json(out/'s0.json',{k:v for k,v in s0.items() if k!='coefficients'})
    if smoke:
        fams=set()
        for s in range(12):
            fams.update(sorted({e['base_family_id'] for e in fitentries if e['scenario']==f'D{s}'})[:2])
        fitentries=[e for e in fitentries if e['base_family_id'] in fams]
    fit=WindowData(fitentries,norm,guard,fold,'optimize',resolver,dec,'cuda')
    inner=WindowData(innerentries,norm,guard,fold,'monitor',resolver,dec,'cuda')
    model=new_model(s0['coefficients'],994900 if smoke else 994100+fold).cuda()
    anchor_model=copy.deepcopy(model)
    with torch.no_grad():
        anchor_model.E.zero_()
    anchor_fit,_=evaluate(anchor_model,fit);anchor_inner,_=evaluate(anchor_model,inner)
    np.savez(out/'anchors.npz',fit=anchor_fit.cpu().numpy(),inner=anchor_inner.cpu().numpy())
    write_json(out/'windows.json',dict(fit=fit.meta,inner=inner.meta))
    return fit,inner,model,anchor_fit,anchor_inner,norm

def run_g3(a,run,rev):
    g2=run/'g2'/a.g2_attempt
    check(read_json(g2/'complete.json')['status']=='PASS','G2 not passed')
    check(source_identity(rev/'koopman_predict_v3t')==read_json(g2/'source_manifest.json'),'source changed after G2; retest required')
    out=run/'g3';out.mkdir(exist_ok=False)
    entries,fm,guard,dec,resolver=context(a,run,rev,'G3')
    started=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    try:
        fit,inner,model,af,ai,norm=prepare_fold(entries,fm,guard,dec,resolver,0,out,True)
        identity=dict(fold=0,phase='warm',code=digest(source_identity(rev/'koopman_predict_v3t')),protocol=sha(a.protocol),data=sha(rev/N5/'data_manifest.csv'),norm=sha(out/'normalization.npz'),s0=sha(out/'s0.npz'),folds=sha(run/'g0/fold_manifest.csv'),seed=994900,smoke=True)
        warm=train_phase(model,fit,inner,af,ai,'warm',994900,identity,out/'warm',max_steps=200,monitor_every=500)
        warmstate=copy.deepcopy(model.state_dict());results={}
        for method in ('T0','T1','T2'):
            mm=copy.deepcopy(model);mm.load_state_dict(warmstate)
            ident=dict(identity,phase=method)
            result=train_phase(mm,fit,inner,af,ai,method,1044900,ident,out/method,max_steps=500,min_steps=2000)
            stats,v=evaluate(mm,inner)
            np.savez(out/f'{method}_inner.npz',errors=v.cpu().numpy(),stats=stats.cpu().numpy())
            results[method]=result
        # Full fit monitoring measured, not extrapolated solely from small smoke set.
        fullfit=WindowData(select(entries,fm,0,'fit'),norm,guard,0,'fit_monitor',resolver,dec,'cuda')
        torch.cuda.synchronize();t=time.perf_counter();evaluate(mm,fullfit);torch.cuda.synchronize();fullmonitor=time.perf_counter()-t
        formal_seconds=sum(max(0.,v['elapsed_s']-sum(c['monitor_s'] for c in v['curve']))/500*15000*5 for v in results.values())
        monitor_seconds=sum(max(c['monitor_s'] for c in v['curve'])*30*5 for v in results.values())+fullmonitor*30*5
        estimate=warm['elapsed_s']/200*2000*5+formal_seconds+monitor_seconds
        free=shutil.disk_usage(rev).free/2**30
        resource=dict(estimated_G4_gpu_hours=estimate/3600,qualification_limit_hours=12,full_fit_monitor_s=fullmonitor,smoke_gpu_wall_s=time.perf_counter()-started,peak_gpu_bytes=torch.cuda.max_memory_allocated(),free_gib=free,projected_output_gib=5,smoke_fit_windows=len(fit.meta),full_fit_windows=len(fullfit.meta),inner_windows=len(inner.meta),methods=results,warm=warm)
        write_json(out/'cost.json',resource)
        status='PASS' if estimate<=12*3600 and free-5>=60 else 'COST_BLOCKED'
        write_json(out/'complete.json',dict(stage='G3',status=status,next_stage='G4' if status=='PASS' else None))
        log(run,'G3',status,resource)
        if status!='PASS':
            (run/'solutions.md').write_text(f'# 成本门停止\n\nG4估计占用GPU {estimate/3600:.3f} 小时，高于12小时或磁盘余量不足。不得缩减折数、步数或监控。建议检查等价向量化/数据驻留与重复解码成本，通过数值等价测试后重新登记冒烟。\n',encoding='utf-8')
        print(f'G3 {status}; estimated G4 {estimate/3600:.3f} GPU hours',flush=True)
    finally:
        guard.enabled=False

def export_outer(model,data,out,label):
    model=copy.deepcopy(model).double().eval();allpred=[];allforce=[];allinternal=[];allerrors=[]
    with torch.no_grad():
        for start in range(0,len(data.meta),256):
            ix=np.arange(start,min(start+256,len(data.meta)))
            pred=model.rollout(data.x[ix],data.u[ix],(1,5,10,20))['xhat']
            f,inn=data.physical(pred,ix)
            from guard_core import component_errors
            hix=[0,4,9,19]
            err=component_errors(pred[:,hix],data.y[ix][:,hix],f[:,hix],inn[:,hix],data.force[ix][:,hix],data.internal[ix][:,hix],data.norm,False)
            if not torch.isfinite(pred).all() or not torch.isfinite(err).all():
                raise FloatingPointError('outer nonfinite')
            allpred.append(pred.cpu().numpy());allforce.append(f.cpu().numpy());allinternal.append(inn.cpu().numpy());allerrors.append(err.cpu().numpy())
    pred=np.concatenate(allpred);f=np.concatenate(allforce);inn=np.concatenate(allinternal);errors=np.concatenate(allerrors)
    target=data.y.cpu().numpy();ft=data.force.cpu().numpy();it=data.internal.cpu().numpy()
    np.savez_compressed(out/f'{label}.npz',prediction_n=pred,target_n=target,force=f,internal=inn,true_force=ft,true_internal=it,errors=errors,initial_n=data.x.cpu().numpy(),control_n=data.u.cpu().numpy())
    records=[]
    for i,m in enumerate(data.meta):
        for j,h in enumerate((1,5,10,20)):
            delta=pred[i,h-1]-target[i,h-1]
            records.append(dict(method=label,**m,horizon=h,j_common=float(errors[i,j,0]),e_core=float(errors[i,j,1]),e_relative=float(errors[i,j,2]),e_force=float(errors[i,j,3]),e_internal=float(errors[i,j,4]),e_yaw=float(errors[i,j,5]),normalized_max_abs=float(np.max(abs(delta))),divergent=bool(np.max(abs(delta))>20),force_rmse_N=float(np.sqrt(np.mean((f[i,h-1]-ft[i,h-1])**2))),internal_rmse_N=float(np.sqrt(np.mean((inn[i,h-1]-it[i,h-1])**2)))))
    write_csv(out/f'{label}_rows.csv',records)

def stress(model,data):
    model=copy.deepcopy(model).double().eval();result=[]
    with torch.no_grad():
        for start in range(0,len(data.meta),256):
            ix=np.arange(start,min(start+256,len(data.meta)))
            pred=model.rollout(data.x[ix],data.u[ix],(40,))['xhat']
            mx=(pred-data.y[ix]).abs().amax(dim=(1,2)).cpu().numpy()
            for j,i in enumerate(ix):
                result.append(dict(**data.meta[i],max_abs=float(mx[j]),divergent=bool(not np.isfinite(mx[j]) or mx[j]>20)))
    return result

def run_g4(a,run,rev):
    check(read_json(run/'g3/complete.json')['status']=='PASS','G3 not passed')
    out=run/'g4';out.mkdir(exist_ok=False)
    sources=source_identity(rev/'koopman_predict_v3t')
    check(sources==read_json(run/'g2'/a.g2_attempt/'source_manifest.json'),'source drift after G2')
    write_json(out/'source_manifest.json',sources)
    entries,fm,guard,dec,resolver=context(a,run,rev,'G4')
    start=time.perf_counter();deadline=start+12*3600;models=[]
    try:
        for fold in range(5):
            folder=out/f'fold_{fold}';folder.mkdir()
            fit,inner,model,af,ai,norm=prepare_fold(entries,fm,guard,dec,resolver,fold,folder)
            ident=dict(fold=fold,code=digest(sources),protocol=sha(a.protocol),taskbook=sha(a.taskbook),data=sha(rev/N5/'data_manifest.csv'),norm=sha(folder/'normalization.npz'),s0=sha(folder/'s0.npz'),folds=sha(run/'g0/fold_manifest.csv'),seed=994100+fold)
            warm=train_phase(model,fit,inner,af,ai,'warm',994100+fold,dict(ident,phase='warm'),folder/'warm',max_steps=2000,deadline=deadline)
            if warm['status']=='COST_PAUSE':
                write_json(out/'cost_pause.json',dict(fold=fold,phase='warm',result=warm));return
            common=copy.deepcopy(model.state_dict());order=['T0','T1','T2'];order=order[fold%3:]+order[:fold%3]
            results={}
            for method in order:
                mm=copy.deepcopy(model);mm.load_state_dict(common)
                result=train_phase(mm,fit,inner,af,ai,method,1044100+fold,dict(ident,phase=method),folder/method,max_steps=15000,deadline=deadline)
                results[method]=result
                if result['status']=='COST_PAUSE':
                    write_json(out/'cost_pause.json',dict(fold=fold,phase=method,result=result));return
                ck=folder/method/'best.pt';check(ck.exists(),'missing frozen best')
                models.append(dict(fold=fold,method=method,path=str(ck),sha256=sha(ck),best_step=result['best_step'],stop_step=result['step'],identity=dict(ident,phase=method)))
            write_json(folder/'training_complete.json',dict(status='PASS',order=order,warm=warm,methods=results))
            del fit,inner,model,mm;torch.cuda.empty_cache()
        check(len(models)==15,'not all formal checkpoints exist')
        write_json(out/'frozen_models.json',dict(models=models,source_sha=digest(sources),elapsed_s=time.perf_counter()-start))
        guard.outer_frozen=True
        log(run,'G4','OUTER_OPENED',dict(final_checkpoints=15,ledger_sha=sha(out/'frozen_models.json')))
        for fold in range(5):
            folder=out/f'fold_{fold}';outer=folder/'outer';outer.mkdir()
            with np.load(folder/'normalization.npz') as z:
                norm={k:z[k] for k in z.files}
            coeff=np.load(folder/'s0.npz')['coefficients']
            selected=select(entries,fm,fold,'outer')
            data=WindowData(selected,norm,guard,fold,'outer_evaluate',resolver,dec,'cuda')
            stressdata=WindowData(selected,norm,guard,fold,'outer_evaluate',resolver,dec,'cuda',40)
            write_json(outer/'windows.json',data.meta);write_json(outer/'stress_windows.json',dict(valid=stressdata.meta,missing_count=stressdata.missing))
            for method in ('S0','T0','T1','T2'):
                model=new_model(coeff,994100+fold).cuda()
                if method=='S0':
                    with torch.no_grad():model.E.zero_()
                else:
                    rec=next(x for x in models if x['fold']==fold and x['method']==method)
                    check(sha(rec['path'])==rec['sha256'],'best changed after freeze')
                    model.load_state_dict(torch.load(rec['path'],map_location='cuda',weights_only=False)['model'])
                export_outer(model,data,outer,method)
                write_json(outer/f'{method}_stress40.json',stress(model,stressdata))
            write_json(folder/'fold_complete.json',dict(status='PASS',outer_evaluated_once=True))
            del data,stressdata,model;torch.cuda.empty_cache()
        write_json(out/'complete.json',dict(stage='G4',status='PASS',gpu_wall_s=time.perf_counter()-start,next_stage='G5'))
        log(run,'G4','PASS',dict(models=15,gpu_wall_s=time.perf_counter()-start))
    finally:
        guard.enabled=False
