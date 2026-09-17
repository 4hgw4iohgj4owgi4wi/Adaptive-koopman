"""Correction identity and local Jacobians for immutable historical models."""
import math
import numpy as np
import torch
from run_v3t import HISTORY, append, check, log, read_json, sha, write_csv, write_json

def finish_diagnosis(a,run,rev,dest,entries,methods,base,hist,caches,params_by_id,selection,protocol,frozen,decoder,td):
    from checkpoint import load_checkpoint
    from evaluation_v3 import build_gdmrk
    from losses import group_rmse,group_slices_from_protocol
    with np.load(frozen.n5_normalization_path(),allow_pickle=False) as z:
        norm={k:z[k] for k in z.files}
    append(run/'split_access.jsonl',dict(stage='G1',purpose='historical_audit',kind='historical_train_normalization',path=str(frozen.n5_normalization_path()),sha256=sha(frozen.n5_normalization_path())))
    mean=norm['relative_state47_mean'];scale=norm['relative_state47_scale']
    um=norm['control7_mean'];us=norm['control7_scale']
    selected={(r['trajectory_id'],r['window_start']) for r in selection}
    corrections=[];gradients=[];jac=[]
    groups=group_slices_from_protocol(protocol)
    for fold in range(5):
        foldpath=rev/HISTORY['v3r'][0]/f'fold_{fold}'
        ck=load_checkpoint(foldpath/'MH16/best.pt')
        model=build_gdmrk(frozen,16,16)
        model.load_state_dict(ck['model_state']);model.double()
        foldids={r['trajectory_id'] for r in base[fold]}
        relevant=[r for r in selection if r['trajectory_id'] in foldids]
        xs=[];uu=[];targets=[]
        for r in relevant:
            tid=r['trajectory_id'];start=r['window_start'];cache=caches[tid]
            x=(cache['relative_state47'][start]-mean)/scale
            u=(cache['control7'][start:start+20]-um)/us
            target=(cache['relative_state47'][start+1:start+21]-mean)/scale
            check(len(u)==20 and len(target)==20,'diagnostic horizon missing')
            xt=torch.tensor(x,dtype=torch.float64)[None];ut=torch.tensor(u,dtype=torch.float64)[None]
            with torch.no_grad():
                correction=(model.encoder(xt,ut[:,0])@model.E.T)[0].numpy()
                prediction=x@model.A0.numpy().T+u[0]@model.B0.numpy().T+model.b0.numpy()
            residual=target[0]-prediction
            rr=float(residual@residual);cc=float(correction@correction);cross=float(2*residual@correction)
            cosine=None if rr*cc<1e-24 else float(np.clip((cross/2)/math.sqrt(rr*cc),-1,1))
            lhs=float((residual-correction)@(residual-correction)-rr)
            check(abs(lhs-(cc-cross))<=1e-10*max(abs(lhs),1),'correction identity failed')
            corrections.append(dict(fold=fold,trajectory_id=tid,window_start=start,omega='I47_in_normalized_coordinates_not_J_common',residual_norm=math.sqrt(rr),correction_norm=math.sqrt(cc),cosine=cosine,angle_deg=None if cosine is None else math.degrees(math.acos(cosine)),amplitude_ratio=None if rr<1e-24 else math.sqrt(cc/rr),correction_sq=cc,two_residual_dot_correction=cross,squared_error_change=cc-cross,identity_abs_error=abs(lhs-(cc-cross))))
            xs.append(x);uu.append(u);targets.append(target)
        check(bool(xs),f'no selected windows fold{fold}')
        xt=torch.tensor(np.array(xs),dtype=torch.float64);ut=torch.tensor(np.array(uu),dtype=torch.float64);yt=torch.tensor(np.array(targets),dtype=torch.float64)
        for phase in ('initial_reconstructed','warm'):
            torch.manual_seed(int(protocol['training']['central_seed'])+fold)
            mm=build_gdmrk(frozen,16,16)
            if phase=='warm':
                payload=load_checkpoint(foldpath/'warm/last.pt')
                mm.load_state_dict(payload['model_state'])
            mm.double()
            pred=mm.rollout(xt,ut,(1,5,10,20))['xhat']
            losses={h:group_rmse(pred[:,h-1],yt[:,h-1],groups) for h in (1,5,10,20)}
            parameters=list(mm.parameters())
            def vec(loss):
                g=torch.autograd.grad(loss,parameters,retain_graph=True,allow_unused=True)
                return torch.cat([(torch.zeros_like(p) if x is None else x).flatten() for p,x in zip(parameters,g)])
            g20=vec(losses[20]);n20=float(g20.norm())
            for h in (1,5,10):
                g=vec(losses[h]);n=float(g.norm());cos=None if min(n,n20)<1e-12 else float((g@g20)/(n*n20))
                gradients.append(dict(fold=fold,phase=phase,horizon_short=h,windows=len(xs),norm_short=n,norm20=n20,cosine=cos,status='NA_zero_norm' if cos is None else 'valid',scope='same preselected historical windows, state-group objective, no updates'))
    write_csv(dest/'one_step_correction.csv',corrections)
    write_csv(dest/'gradient_conflict.csv',gradients)
    # Jacobian away from boundary for fixed ordinary windows; synthetic boundary
    # is tied to the same actual parameter set and labelled separately.
    entrymap={e['trajectory_id']:e for e in entries}
    for r in selection:
        if 'fixed_ordinary_per_scenario' not in r['reasons']:
            continue
        tid=r['trajectory_id'];e=entrymap[tid];p=params_by_id[tid]
        x=caches[tid]['relative_state47'][r['window_start']].astype(float).copy()
        for sample in ('ordinary','synthetic_freeplay_positive_side'):
            xx=x.copy()
            if sample!='ordinary':
                xx[31:35]=[p.connector.free_play_m,0,.02,0]
            for col in range(31,47):
                step=1e-8 if col%4 in (3,0) else 1e-8
                plus=xx.copy();minus=xx.copy();plus[col]+=step;minus[col]-=step
                fplus=decoder.connector_force(plus,p,e['law'])[0];fminus=decoder.connector_force(minus,p,e['law'])[0]
                point=(col-31)//4
                dq=xx[31+4*point:33+4*point];dv=xx[33+4*point:35+4*point]
                d=np.linalg.norm(dq);gap=d-p.connector.free_play_m;v=float(dv@dq/max(d,1e-12))
                boundary=(abs(gap)<2e-8 or abs(gap-p.connector.smoothing_width_m)<2e-8 or abs(v)<2e-8 or d<2e-8)
                if boundary:
                    # Evaluate autograd from each side, do not equate central differences
                    # with the arbitrary derivative of clamp at the kink.
                    for direction in (-1,1):
                        shifted=xx.copy();shifted[col]+=direction*step
                        t=torch.tensor(shifted,dtype=torch.float64,requires_grad=True)
                        j=torch.autograd.functional.jacobian(lambda z:td.connector_force(z,p,e['law'])[0],t).detach().numpy()[:,col]
                        f0=decoder.connector_force(xx,p,e['law'])[0]
                        fd=(fplus-f0)/step if direction==1 else (f0-fminus)/step
                        jac.append(dict(trajectory_id=tid,window_start=r['window_start'],sample=sample,column=col,scheme=f'one_sided_{direction}',step=step,max_abs_error=float(np.max(abs(j-fd))),jacobian_max_abs=float(np.max(abs(j))),hard_parity_required=False))
                else:
                    t=torch.tensor(xx,dtype=torch.float64,requires_grad=True)
                    j=torch.autograd.functional.jacobian(lambda z:td.connector_force(z,p,e['law'])[0],t).detach().numpy()[:,col]
                    fd=(fplus-fminus)/(2*step)
                    jac.append(dict(trajectory_id=tid,window_start=r['window_start'],sample=sample,column=col,scheme='central',step=step,max_abs_error=float(np.max(abs(j-fd))),jacobian_max_abs=float(np.max(abs(j))),hard_parity_required=True))
    write_csv(dest/'force_jacobian.csv',jac)
    exact=max(x['identity_abs_error'] for x in corrections)
    negative=sum(r['cosine'] is not None and r['cosine']<0 for r in gradients)
    bad=sum(x['squared_error_change']>0 for x in corrections)
    doc=f'''# G1 历史诊断\n\n本阶段只读历史train，不是新五折训练或泛化验证。\n\n- 7条历史路线的逐窗CSV重算见 history_horizons.csv；mean_folds和pooled两种口径分列。\n- 真实状态/NumPy/Torch CPU float64三方force oracle通过，详见 force_oracle.json；后续CUDA和float32仍需G2验收。\n- {len(corrections)}个预选窗口中，{bad}个一步归一化平方误差被修正项增大；恒等式最大绝对差 {exact:.3g}。这个统计不是J_common，也不是代表总体的随机样本。\n- 初始/共同warm同批短期与20步梯度诊断共{len(gradients)}项，负余弦{negative}项。负相关仅支持局部优化冲突，不证明唯一根因。\n- 力局部雅可比见force_jacobian.csv：边界用单侧，普通点用中心差分；合成边界样例已单独标记，不作为实验时序证据。\n\n允许进入G2实现和测试；不允许直接启动长训练。历史模型与全train归一化仅用于G1审计，不能复用为新折的拟合结果。\n'''
    (dest/'diagnosis.md').write_text(doc,encoding='utf-8')
    write_json(dest/'source_manifest.json',{str(p.relative_to(rev/'koopman_predict_v3t')).replace('\\','/'):sha(p) for p in sorted((rev/'koopman_predict_v3t').rglob('*.py')) if '__pycache__' not in p.parts})
    write_json(dest/'complete.json',dict(stage='G1',status='PASS',next_stage='G2',new_training_started=False))
    log(run,'G1','PASS',dict(correction_windows=len(corrections),gradient_pairs=len(gradients)))
    print('G1 PASS',flush=True)
