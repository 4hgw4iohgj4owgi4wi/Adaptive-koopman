"""Historical-only G1 diagnostics. Never initializes a new training run."""
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from run_v3t import HISTORY, N5, append, check, log, read_json, rows, sha, write_csv, write_json

def summarize(values):
    a=np.asarray(values,dtype=float)
    check(np.isfinite(a).all(),'nonfinite historical metric')
    return dict(mean=float(a.mean()),p95=float(np.quantile(a,.95)),p99=float(np.quantile(a,.99)),maximum=float(a.max()),n=len(a))

def macro(data,h):
    by_s=defaultdict(list)
    for r in data:
        if int(r['horizon'])==h:
            by_s[r['scenario']].append(float(r['j_common']))
    check(bool(by_s),'missing historical horizon')
    return float(np.mean([np.mean(v) for v in by_s.values()]))

def audited_rows(path,run,train_ids):
    result=rows(path)
    check(all(r['split']=='train' and str(r['trajectory_id']) in train_ids for r in result),f'nontrain historical rows {path}')
    keys=[(r['trajectory_id'],r['window_start'],r['horizon']) for r in result]
    check(len(keys)==len(set(keys)),f'duplicate historical rows {path}')
    append(run/'split_access.jsonl',dict(stage='G1',purpose='historical_audit',split='train',path=str(path),sha256=sha(path),rows=len(result)))
    return result

def run_g1(a,run,rev):
    dest=run/'g1'
    dest.mkdir(exist_ok=False)
    src=rev/'koopman_predict_v3t'
    sys.path.insert(0,str(src/'src'))
    from frozen import FrozenN6
    from physics_decoder import R3Decoder
    from physics_decoder_torch import TorchR3Decoder
    import torch
    torch.set_num_threads(1)
    protocol=read_json(src/'config/protocol_v3s.json')
    frozen=FrozenN6(a.project_root,protocol)
    identity=frozen.verify_identity(protocol)
    write_json(dest/'frozen_dependencies.json',identity)
    check(identity['passed'],'frozen N6 dependency identity mismatch')
    entries=[e for e in rows(rev/N5/'data_manifest.csv') if e['split']=='train']
    ids={e['trajectory_id'] for e in entries}
    methods={}
    base=[]
    for fold in range(5):
        f4=rev/HISTORY['v3r'][0]/f'fold_{fold}'
        base.append(audited_rows(f4/'s0_rows.csv',run,ids))
        for method in ('ONE16','MH16','MHC16','BCV16'):
            methods.setdefault(method,[]).append(audited_rows(f4/method/'rows_best.csv',run,ids))
        sb=rev/HISTORY['v3s'][0]/f'fold_{fold}'
        for method in ('SB16EQ','SB16UP'):
            methods.setdefault(method,[]).append(audited_rows(sb/method/'rows_best.csv',run,ids))
        ar=rev/'koopman_ab_results/runs/20260903_193821_AB_Q0_R01/ar2/spec_A_scenario_D1'/f'composed_fold{fold}.csv'
        methods.setdefault('AR',[]).append(audited_rows(ar,run,ids))
    hist=[]
    details=[]
    for method,folds in methods.items():
        for h in (1,5,10,20):
            gain=[]
            for fold,rr in enumerate(folds):
                keys=lambda data:{(r['trajectory_id'],r['window_start'],r['horizon']) for r in data}
                check(keys(rr)==keys(base[fold]),f'{method}/fold{fold} pairing mismatch')
                b=macro(base[fold],h); m=macro(rr,h)
                gain.append(100*(b-m)/max(b,1e-12))
                hist.append(dict(method=method,fold=str(fold),horizon=h,s0=b,candidate=m,improvement_pct=gain[-1],aggregation='historical within-fold scenario mean of windows'))
            hist.append(dict(method=method,fold='mean_folds',horizon=h,s0=float(np.mean([macro(x,h) for x in base])),candidate=float(np.mean([macro(x,h) for x in folds])),improvement_pct=float(np.mean(gain)),aggregation='mean of five fold improvement percentages'))
            pooled=sum(folds,[]); pooledbase=sum(base,[])
            b=macro(pooledbase,h);m=macro(pooled,h)
            hist.append(dict(method=method,fold='pooled',horizon=h,s0=b,candidate=m,improvement_pct=100*(b-m)/max(b,1e-12),aggregation='pooled12scenario macro window mean'))
        grouped=defaultdict(list)
        for r in sum(folds,[]):
            for component in ('j_common','e_core','e_relative','e_force4','e_internal','e_yaw','force8_rmse_n','internal8_rmse_n'):
                if component in r and r[component] not in ('','None'):
                    grouped[(r['plant'],r['scenario'],int(r['horizon']),component)].append(float(r[component]))
        for (plant,scenario,h,c),vals in grouped.items():
            details.append(dict(method=method,plant=plant,scenario=scenario,horizon=h,component=c,quantile_method='linear_unweighted_historical_diagnostic',**summarize(vals)))
    write_csv(dest/'history_horizons.csv',hist)
    write_csv(dest/'plant_scenario_metrics.csv',details)
    print('G1 historical tables recomputed',flush=True)
    # Freeze ordinary and diagnostic selections BEFORE loading state arrays.
    chosen={}
    mh=sum(methods['MH16'],[])
    def select(r,reason):
        key=(r['trajectory_id'],int(r['window_start']))
        chosen.setdefault(key,set()).add(reason)
    for s in range(12):
        rr=sorted((r for r in mh if r['scenario']==f'D{s}' and int(r['horizon'])==1),key=lambda r:(int(r['trajectory_id']),int(r['window_start'])))
        select(rr[0],'fixed_ordinary_per_scenario')
    for r in mh:
        if r['scenario']=='D1' and int(r['window_start'])==360 and int(r['horizon'])==1:
            select(r,'D1_start360')
    for r in sum(methods['SB16EQ'],[])+sum(methods['SB16UP'],[]):
        if r['scenario']=='D0' and int(r['horizon'])==1:
            select(r,'SB_D0')
    blookup={(r['trajectory_id'],r['window_start'],r['horizon']):float(r['j_common']) for r in sum(base,[])}
    bad=sorted((r for r in mh if int(r['horizon'])==1), key=lambda r:float(r['j_common'])-blookup[(r['trajectory_id'],r['window_start'],r['horizon'])],reverse=True)[:12]
    for r in bad:
        select(r,'top12_MH_absolute_one_step_degradation')
    selection=[dict(trajectory_id=tid,window_start=start,reasons=';'.join(sorted(reason))) for (tid,start),reason in sorted(chosen.items(),key=lambda x:(int(x[0][0]),x[0][1]))]
    write_csv(dest/'selected_windows.csv',selection)
    decoder=R3Decoder(frozen.build_planar_grasp_matrix)
    td=TorchR3Decoder(frozen.build_planar_grasp_matrix)
    oracle=[]
    boundary=[]
    cache_by_id={}
    params_by_id={}
    for e in entries:
        tid=e['trajectory_id']
        windows=[s for (t,s) in chosen if t==tid]
        if not windows:
            continue
        append(run/'split_access.jsonl',dict(stage='G1',purpose='historical_audit',split='train',trajectory=tid,path=e['cache_path'],sha256=sha(e['cache_path'])))
        with np.load(e['cache_path'],allow_pickle=False) as z:
            cache={k:z[k] for k in ('relative_state47','control7','force_payload_body8','internal_force8','window_start')}
        cache_by_id[tid]=cache
        params=frozen.resolved_params(int(e['seed']),protocol)
        params_by_id[tid]=params
        indices=sorted({k for s in windows for k in range(s,min(s+21,len(cache['relative_state47'])))})
        x=cache['relative_state47'][indices].astype(np.float64)
        nf,ni=decoder.connector_force(x,params,e['law'])
        tf,ti=td.connector_force(torch.tensor(x,dtype=torch.float64),params,e['law'])
        tf=tf.detach().numpy();ti=ti.detach().numpy()
        truth=cache['force_payload_body8'][indices]; intruth=cache['internal_force8'][indices]
        one=dict(trajectory_id=tid,scenario=e['scenario'],plant=e['plant'],law=e['law'],states=len(indices),
                 numpy_cache_force_max_abs_N=float(np.max(abs(nf-truth))),numpy_cache_internal_max_abs_N=float(np.max(abs(ni-intruth))),
                 torch_numpy_force_max_abs_N=float(np.max(abs(tf-nf))),torch_numpy_internal_max_abs_N=float(np.max(abs(ti-ni))),
                 passed=bool(np.allclose(nf,truth,atol=1e-8,rtol=1e-10) and np.allclose(ni,intruth,atol=1e-8,rtol=1e-10) and np.allclose(tf,nf,atol=1e-8,rtol=1e-10) and np.allclose(ti,ni,atol=1e-8,rtol=1e-10)))
        oracle.append(one)
        g3=x[:,31:47].reshape(-1,4,4)
        for pos,k in enumerate(indices):
            for point in range(4):
                dq=g3[pos,point,:2];dv=g3[pos,point,2:];d=float(np.linalg.norm(dq)); gap=d-params.connector.free_play_m
                boundary.append(dict(trajectory_id=tid,index=k,point=point,scenario=e['scenario'],plant=e['plant'],gap_m=gap,dq_x_m=float(dq[0]),dq_y_m=float(dq[1]),dv_x_mps=float(dv[0]),dv_y_mps=float(dv[1]),normal_speed_mps=float(dv@dq/max(d,1e-12)),contact=gap>0,transition=0<gap<params.connector.smoothing_width_m,oracle_force_error_N=float(np.linalg.norm(nf[pos,2*point:2*point+2]-truth[pos,2*point:2*point+2]))))
    result=dict(status='PASS' if all(x['passed'] for x in oracle) else 'BLOCKED',scope='preselected historical train windows, all endpoints k..k+20',windows=len(selection),trajectories=len(oracle),rows=oracle,atol_N=1e-8,rtol=1e-10)
    write_json(dest/'force_oracle.json',result)
    write_csv(dest/'boundary_diagnostics.csv',boundary)
    if result['status']!='PASS':
        text='# G1：连接力 oracle 硬门未通过\n\n事实：真实状态经现有 NumPy/Torch 解码未能全部按预注册容差恢复缓存力，详见 force_oracle.json。\n\n停止新学习路线；G2—G5 未执行。下一步限定为确认参数身份、端点对齐、坐标变换与解码力律。不允许通过放宽容差或替换缓存使检查通过。\n'
        (dest/'diagnosis.md').write_text(text,encoding='utf-8')
        (run/'solutions.md').write_text(text,encoding='utf-8')
        write_json(dest/'complete.json',dict(status='BLOCKED',reason='true-state force oracle mismatch',next_stage=None))
        raise RuntimeError('G1 force oracle hard gate failed; learning stopped')
    print('G1 force oracle passed; continuing correction and gradient diagnostics',flush=True)
    from guard_model_diagnosis import finish_diagnosis
    finish_diagnosis(a,run,rev,dest,entries,methods,base,hist,cache_by_id,params_by_id,selection,protocol,frozen,decoder,td)
