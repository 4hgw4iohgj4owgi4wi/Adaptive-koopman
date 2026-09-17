"""Independent disk-based G5 aggregation, gates, bootstrap and figures."""
import copy
import json
import time
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from run_v3t import N5,check,log,read_json,rows,sha,write_csv,write_json
from guard_core import Decoder,new_model

METHODS=('S0','T0','T1','T2');HS=(1,5,10,20)

def family_values(data,column='j_common'):
    values=defaultdict(lambda:defaultdict(list))
    for r in data:
        values[r['family']][r['trajectory']].append(float(r[column]))
    return {family:float(np.mean([np.mean(x) for x in trajectories.values()])) for family,trajectories in values.items()}

def summary(data,column='j_common'):
    if not data:
        raise ValueError('empty metric group')
    scenario={}
    for s in sorted({int(r['scenario']) for r in data}):
        scenario[s]=float(np.mean(list(family_values([r for r in data if int(r['scenario'])==s],column).values())))
    return float(np.mean(list(scenario.values())))

def weighted_distribution(data,column='j_common'):
    fam=defaultdict(lambda:defaultdict(list))
    for r in data:
        fam[r['family']][r['trajectory']].append(float(r[column]))
    if not fam:
        raise ValueError('missing registered distribution')
    vv=[];ww=[]
    for trajectories in fam.values():
        for vals in trajectories.values():
            vv.extend(vals);ww.extend([1/len(fam)/len(trajectories)/len(vals)]*len(vals))
    order=np.argsort(vv,kind='stable');v=np.asarray(vv)[order];w=np.asarray(ww)[order];cum=np.cumsum(w);cum[-1]=1.
    return dict(mean=float(np.sum(v*w)),p95=float(v[np.searchsorted(cum,.95)]),p99=float(v[np.searchsorted(cum,.99)]),maximum=float(v[-1]))

def bootstrap(base,candidate,column='j_common',seed=994500):
    rng=np.random.Generator(np.random.PCG64(seed));bb=[];cc=[]
    for s in range(12):
        b=family_values([r for r in base if int(r['scenario'])==s],column)
        c=family_values([r for r in candidate if int(r['scenario'])==s],column)
        if b.keys()!=c.keys() or not b:
            raise ValueError('bootstrap family pairing mismatch')
        keys=sorted(b);ind=rng.integers(len(keys),size=(2000,len(keys)))
        bb.append(np.array([b[k] for k in keys])[ind].mean(1));cc.append(np.array([c[k] for k in keys])[ind].mean(1))
    bv=np.mean(bb,axis=0);cv=np.mean(cc,axis=0)
    gain=100*(bv-cv)/np.maximum(bv,1e-12)
    return dict(candidate_mean_ci95=np.quantile(cv,[.025,.975],method='linear').tolist(),paired_improvement_ci95=np.quantile(gain,[.025,.975],method='linear').tolist(),replicates=2000,seed=seed,unit='scenario-stratified paired base family')

def latency(run,rev,method):
    from frozen import FrozenN6
    folder=run/'g4/fold_0';coeff=np.load(folder/'s0.npz')['coefficients']
    with np.load(folder/'normalization.npz') as z:
        norm={k:z[k] for k in z.files}
    with np.load(folder/f'outer/{method}.npz') as z:
        x=z['initial_n'][:1];u=z['control_n'][:1]
    meta=read_json(folder/'outer/windows.json')[0]
    entry=next(e for e in rows(rev/N5/'data_manifest.csv') if e['trajectory_id']==meta['trajectory'])
    protocol=read_json(rev/'koopman_predict_v3s/config/protocol_v3s.json');frozen=FrozenN6(rev.parent,protocol)
    p=frozen.resolved_params(int(entry['seed']),protocol);decoder=Decoder(frozen.build_planar_grasp_matrix)
    model=new_model(coeff,994100)
    if method=='S0':
        with torch.no_grad():model.E.zero_()
    else:
        model.load_state_dict(torch.load(folder/method/'best.pt',map_location='cpu',weights_only=False)['model'])
    result={}
    torch.set_num_threads(1)
    for device in ('cpu','cuda'):
        m=copy.deepcopy(model).to(device).eval()
        xx=torch.tensor(x,device=device,dtype=torch.float32);uu=torch.tensor(u,device=device,dtype=torch.float32)
        mean=torch.tensor(norm['relative_state47_mean'],device=device,dtype=torch.float32);scale=torch.tensor(norm['relative_state47_scale'],device=device,dtype=torch.float32)
        def infer():
            if method=='S0':
                state=xx;predictions=[]
                A=m.A0.float();B=m.B0.float();bias=m.b0.float()
                for h in range(20):
                    state=state@A.T+uu[:,h]@B.T+bias;predictions.append(state)
                pred=torch.stack(predictions,dim=1)
            else:
                pred=m.rollout(xx,uu,(20,))['xhat']
            return decoder(pred*scale+mean,p,entry['params_sha256'])
        with torch.no_grad():
            for _ in range(200):infer()
            samples=[]
            for _ in range(1000):
                if device=='cuda':torch.cuda.synchronize()
                start=time.perf_counter();infer()
                if device=='cuda':torch.cuda.synchronize()
                samples.append((time.perf_counter()-start)*1000)
        result[device]=dict(median_ms=float(np.median(samples)),p99_ms=float(np.quantile(samples,.99)),samples_ms=samples,warmup=200,repetitions=1000,batch=1,horizon=20,includes='all20state+force8+internal8 decode',transfers='excluded; inputs resident',cpu_threads=1)
        if device=='cuda':
            cpu_x=torch.tensor(x,dtype=torch.float32);cpu_u=torch.tensor(u,dtype=torch.float32)
            outputs=infer();h2d=[];d2h=[]
            for _ in range(1000):
                torch.cuda.synchronize();start=time.perf_counter();tx=cpu_x.cuda();tu=cpu_u.cuda();torch.cuda.synchronize();h2d.append((time.perf_counter()-start)*1000)
                start=time.perf_counter();a_cpu=outputs[0].detach().cpu();b_cpu=outputs[1].detach().cpu();torch.cuda.synchronize();d2h.append((time.perf_counter()-start)*1000)
            result['transfers']=dict(H2D_median_ms=float(np.median(h2d)),H2D_p99_ms=float(np.quantile(h2d,.99)),D2H_median_ms=float(np.median(d2h)),D2H_p99_ms=float(np.quantile(d2h,.99)),repetitions=1000,includes='host/device copy and output allocation, outside inference gate')
    result['parameter_count']=model.parameter_count()
    if method=='S0':
        result['parameter_count']=dict(trainable=0,total=int(coeff.size),frozen_s0=int(coeff.size))
    return result

def run_g5(a,run,rev):
    check(read_json(run/'g4/complete.json')['status']=='PASS','G4 not passed')
    out=run/'g5';out.mkdir(exist_ok=False)
    from guard_experiments import source_identity
    current_source=source_identity(rev/'koopman_predict_v3t')
    frozen_source=read_json(run/'g4/source_manifest.json')
    changed={k for k in set(current_source)|set(frozen_source) if current_source.get(k)!=frozen_source.get(k)}
    check(changed<= {'scripts/guard_report.py','scripts/guard_figures.py'},'non-report source drift after G4 freeze')
    write_json(out/'source_manifest.json',current_source)
    write_json(out/'report_source_changes.json',dict(changed_paths=sorted(changed),scope='report-only: baseline timing implementation, transfer measurement and registered worst-window figures; training/predictions unchanged',training_source_manifest_sha256=sha(run/'g4/source_manifest.json')))
    records=[];sources={}
    for fold in range(5):
        for method in METHODS:
            path=run/f'g4/fold_{fold}/outer/{method}_rows.csv';sources[str(path)]=sha(path)
            rr=rows(path)
            for r in rr:
                r['fold']=fold;r['scenario']=int(r['scenario']);r['horizon']=int(r['horizon']);r['start']=int(r['start'])
            keys=[(r['trajectory'],r['start'],r['horizon']) for r in rr]
            check(len(keys)==len(set(keys)),'duplicate outer rows')
            check({r['scenario'] for r in rr}==set(range(12)),'missing outer scenario')
            records+=rr
    by_method={m:[r for r in records if r['method']==m] for m in METHODS}
    key=lambda r:(r['fold'],r['family'],r['trajectory'],r['start'],r['horizon'])
    baselinekeys={key(r) for r in by_method['S0']}
    for m in METHODS:
        check({key(r) for r in by_method[m]}==baselinekeys,'S0 candidate pairing mismatch')
    # A second independent aggregation route uses a tabular groupby cascade.
    import pandas as pd
    frame=pd.DataFrame(records);frame['j_common']=frame['j_common'].astype(float)
    grouped=frame.groupby(['method','horizon','scenario','family','trajectory'],sort=True).j_common.mean().groupby(['method','horizon','scenario','family']).mean().groupby(['method','horizon','scenario']).mean().groupby(['method','horizon']).mean()
    horizon=[];scenario_rows=[];gates=[]
    def gate(method,scope,name,value,passed,limit):
        gates.append(dict(method=method,scope=scope,gate=name,value=value,limit=limit,passed=bool(passed)))
    for method in METHODS:
        for h in HS:
            b=[r for r in by_method['S0'] if r['horizon']==h];c=[r for r in by_method[method] if r['horizon']==h]
            bm=summary(b);cm=summary(c)
            check(abs(cm-float(grouped[method,h]))<=1e-12,'independent aggregation mismatch')
            ci=bootstrap(b,c)
            horizon.append(dict(method=method,horizon=h,s0=bm,candidate=cm,improvement_pct=100*(bm-cm)/max(bm,1e-12),ci_low=ci['candidate_mean_ci95'][0],ci_high=ci['candidate_mean_ci95'][1],improvement_ci_low=ci['paired_improvement_ci95'][0],improvement_ci_high=ci['paired_improvement_ci95'][1]))
    for method in ('T0','T1','T2'):
        positive=0
        for scope in ('pooled',0,1,2,3,4):
            b=[r for r in by_method['S0'] if scope=='pooled' or r['fold']==scope]
            c=[r for r in by_method[method] if scope=='pooled' or r['fold']==scope]
            for h in HS:
                bh=[r for r in b if r['horizon']==h];ch=[r for r in c if r['horizon']==h]
                bm=summary(bh);cm=summary(ch);improve=100*(bm-cm)/max(bm,1e-12)
                if h==20:
                    if scope=='pooled':gate(method,scope,'h20_gain_pct',improve,improve>=5,'>=5%')
                    elif improve>0:positive+=1
                else:
                    deg=100*(cm-bm)/max(bm,1e-12);gate(method,scope,f'h{h}_short_degradation_pct',deg,deg<=3,'<=3% no0.02floor')
                for s in range(12):
                    bs=[r for r in bh if r['scenario']==s];cs=[r for r in ch if r['scenario']==s]
                    js0=summary(bs);js=summary(cs);deg=100*(js-js0)/max(js0,.02)
                    gate(method,scope,f'D{s}_h{h}_degradation_pct',deg,deg<=3,'<=3% denominator max(S0,0.02)')
                    scenario_rows.append(dict(method=method,scope=scope,scenario=s,horizon=h,s0=js0,candidate=js,degradation_pct=deg))
                for component in ('e_force','e_internal'):
                    v0=summary(bh,component);v=summary(ch,component);deg=100*(v-v0)/max(v0,1e-12)
                    gate(method,scope,f'{component}_h{h}_degradation_pct',deg,deg<=5,'<=5% no0.02floor')
                for label,starts in (('all',None),('hard',[100,120]),('start100',[100]),('start120',[120])):
                    db=[r for r in bh if r['scenario']==5 and (starts is None or r['start'] in starts)]
                    dc=[r for r in ch if r['scenario']==5 and (starts is None or r['start'] in starts)]
                    if not db or not dc:
                        gate(method,scope,f'D5_{label}_h{h}_coverage',0,False,'registered rows required');continue
                    a0=weighted_distribution(db);aa=weighted_distribution(dc)
                    for stat in a0:
                        deg=100*(aa[stat]-a0[stat])/max(a0[stat],.02)
                        gate(method,scope,f'D5_{label}_h{h}_{stat}_degradation_pct',deg,deg<=3,'<=3% weighted inverseCDF')
            finite=all(np.isfinite(float(r['normalized_max_abs'])) and float(r['normalized_max_abs'])<=20 for r in c)
            gate(method,scope,'finite_and_normalized_error_le20',int(finite),finite,'finite and <=20')
        gate(method,'pooled','positive_h20_folds',positive,positive>=4,'>=4/5')
        ci=next(r for r in horizon if r['method']==method and r['horizon']==20)
        gate(method,'pooled','paired_h20_CI_lower_pct',ci['improvement_ci_low'],ci['improvement_ci_low']>0,'>0')
        new_div=0
        for fold in range(5):
            b=read_json(run/f'g4/fold_{fold}/outer/S0_stress40.json');c=read_json(run/f'g4/fold_{fold}/outer/{method}_stress40.json')
            idx={(r['trajectory'],r['start']):r for r in b}
            check(set(idx)=={(r['trajectory'],r['start']) for r in c},'stress pair mismatch')
            new_div+=sum(r['divergent'] and not idx[r['trajectory'],r['start']]['divergent'] for r in c)
        gate(method,'pooled','new_stress40_divergences',new_div,new_div==0,'0')
    times={}
    for method in METHODS:
        times[method]=latency(run,rev,method)
        if method!='S0':
            for device,stat,limit in (('cuda','median_ms',1.),('cuda','p99_ms',2.),('cpu','median_ms',5.)):
                v=times[method][device][stat];gate(method,'timing',f'{device}_{stat}',v,v<limit,f'<{limit}ms')
        print('G5 timed '+method,flush=True)
    write_json(out/'latency.json',times)
    write_csv(out/'horizons.csv',horizon);write_csv(out/'scenarios.csv',scenario_rows);write_csv(out/'gates.csv',gates)
    comparisons=[]
    for bmethod,cmethod in (('T0','T1'),('T1','T2')):
        for h in HS:
            b=[r for r in by_method[bmethod] if r['horizon']==h];c=[r for r in by_method[cmethod] if r['horizon']==h]
            comparisons.append(dict(reference=bmethod,candidate=cmethod,horizon=h,**bootstrap(b,c)))
    write_json(out/'paired_mechanism_comparisons.json',comparisons)
    stability=[];amplitudes=[]
    for fold in range(5):
        folder=run/f'g4/fold_{fold}';coeff=np.load(folder/'s0.npz')['coefficients']
        for method in METHODS:
            model=new_model(coeff,994100+fold).double()
            if method=='S0':
                with torch.no_grad():model.E.zero_()
                K=model.A0.detach().numpy()
            else:
                model.load_state_dict(torch.load(folder/method/'best.pt',map_location='cpu',weights_only=False)['model'])
                K=model.full_k_matrix().detach().numpy()
            A=model.A0.detach().numpy();E=model.E.detach().numpy()
            for h in (1,5,10,20,40):
                stability.append(dict(fold=fold,method=method,horizon=h,K_power_norm2=float(np.linalg.norm(np.linalg.matrix_power(K,h),2)),A0_spectral_radius=float(np.max(abs(np.linalg.eigvals(A)))),E_norm2=float(np.linalg.norm(E,2)),residual_radius_max=float(model.F.radius.max().detach()),claim='residual Schur bound is not whole-system or closed-loop stability'))
            with np.load(folder/f'outer/{method}.npz') as z:
                x=z['initial_n'];u=z['control_n']
            norms=[];corrections=[]
            with torch.no_grad():
                for start in range(0,len(x),256):
                    roll=model.rollout(torch.tensor(x[start:start+256]),torch.tensor(u[start:start+256]),(20,),return_eta=True)
                    eta=roll['eta'];norms.extend(torch.linalg.vector_norm(eta,dim=-1).flatten().tolist());corrections.extend(torch.linalg.vector_norm(eta@model.E.T,dim=-1).flatten().tolist())
            amplitudes.append(dict(fold=fold,method=method,eta_max=float(np.max(norms)),eta_p99=float(np.quantile(norms,.99)),E_eta_max=float(np.max(corrections)),E_eta_p99=float(np.quantile(corrections,.99)),units='normalized latent/state norms',source='frozen checkpoint and already-exported outer initial/control, no new model selection'))
    write_csv(out/'stability.csv',stability);write_csv(out/'residual_amplitude.csv',amplitudes)
    passed=[m for m in ('T0','T1','T2') if all(g['passed'] for g in gates if g['method']==m)]
    selected=None
    if passed:
        gains={r['method']:r['improvement_pct'] for r in horizon if r['horizon']==20 and r['method'] in passed}
        best=max(gains.values());selected=next(m for m in ('T0','T1','T2') if m in gains and best-gains[m]<.5)
    frozen_models=read_json(run/'g4/frozen_models.json')
    full_steps=None if selected is None else int(np.median([r['best_step'] for r in frozen_models['models'] if r['method']==selected]))
    write_json(out/'next_stage.json',dict(status='STOP_AFTER_G5',selected=selected,passed_methods=passed,authorized_to_run_V0=False,confirm_read_count=0,new_validation_generated=False,source_sha=sha(run/'g4/source_manifest.json'),protocol_sha=sha(a.protocol),data_sha=sha(rev/N5/'data_manifest.csv'),fold_models=frozen_models,remaining_entries=['V0','C0','MPC','network','DoS'],normalization='fit-only ddof0 floor1e-12; varies by fold',all_gates_file='gates.csv',full_train=dict(authorized=False,formal_step_rule='median of selected method five true best_step values',formal_steps=full_steps,warm_steps=2000,proposed_initialization_seeds=[994101,994102,994103,994104,994105],seed_semantics='initialization repeats, not sample bootstrap'),new_validation_plan=dict(registered_families=48,dual_plant_trajectories=168,R3_expected_trajectories=84,generated_by_this_run=False),confirm_plan=dict(existing_assets_claim='not generated by this run; no reads',proposed_R3_families=96,proposed_R3_trajectories=168,requires_new_authorization=True)))
    lines=['# Guard 结果','', '这是内部开发性五折证据，不是最终验证/确认集结论。','', '|方法|h1改善率|h5|h10|h20|门检验|','|---|---:|---:|---:|---:|---|']
    for m in ('T0','T1','T2'):
        values=[next(x['improvement_pct'] for x in horizon if x['method']==m and x['horizon']==h) for h in HS]
        failures=[g for g in gates if g['method']==m and not g['passed']]
        lines.append('|'+m+'|'+'|'.join(f'{v:.3f}%' for v in values)+'|'+('PASS' if not failures else f'FAIL ({len(failures)} gates)')+'|')
        lines+=[]
    lines+=['',f'冻结候选：{selected or "无：没有方法通过全部门"}。不自动进入V0/C0。','', '正改善率表示较S0误差降低；工况退化率另用max(S0,0.02)分母。完整负结果、D5加权分位数、物理误差和延迟见CSV/JSON。', '', '各折归一化不同，不能把归一化误差当成N/rad等物理单位。CSV另保留force/internal RMSE(N)。整体阵列横摆未由47维明确提供，不以四车均值替代。力方向不是货物材料撕裂判据。']
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    if not passed:
        worst=sorted([g for g in gates if not g['passed'] and isinstance(g['value'],(int,float))],key=lambda x:float(x['value']),reverse=True)[:20]
        doc=['# 未通过项与后续选择','', '事实：本轮无组同时通过全部门；不能把最高20步收益当作合格候选。','', '主要失败记录（仅便于定位，全部记录保留在gates.csv）：']+[f"- {g['method']} / {g['scope']} / {g['gate']}: {g['value']:.6g}, 要求 {g['limit']}" for g in worst]
        doc+=['','推断需结合paired_mechanism_comparisons、约束轨迹和G1诊断：T1−T0区分指标对齐作用，T2−T1区分保护项作用；不能单凭一次负相关归因。','', '建议：若仅延迟失败，可单独做保持数值/接口等价的推理实现优化并重测固定输入；若短期/工况保护失败，则当前固定预算经验优化没有证明可行，不扩大乘子上限、不删不利工况、不在已读外层回选模型。下一轮方法或数据变化须另立协议，保留本轮反证。']
        (out/'solutions.md').write_text('\n'.join(doc),encoding='utf-8')
    from guard_figures import figures
    figures(run,rev,out,horizon,scenario_rows,gates,times)
    write_json(out/'aggregation_audit.json',dict(independent_path='pandas trajectory/family/scenario hierarchy vs pure Python',tolerance=1e-12,sources=sources,passed=True))
    write_json(out/'complete.json',dict(stage='G5',status='COMPLETE_STOP',selected=selected,all_tasks_finished=True))
    log(run,'G5','COMPLETE_STOP',dict(selected=selected,passed_methods=passed))
