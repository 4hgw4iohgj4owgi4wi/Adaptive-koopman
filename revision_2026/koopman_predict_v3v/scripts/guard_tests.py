"""G2 explicitly enumerated gate evidence. No formal training authorization here."""
import copy
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import torch
from run_v3t import N5,append,check,log,read_json,rows,sha,write_json
from guard_core import AccessGuard,Decoder,WindowData,component_errors,constraints,digest,evaluate,fit_normalization,fit_s0,full_k,loss,new_model,smooth_rmse,validate_rows
from guard_training import train_phase,validate

def run_g2(a,run,rev):
    dest=run/'g2' if a.attempt_name=='base' else run/'g2'/a.attempt_name
    dest.mkdir(exist_ok=False)
    src=rev/'koopman_predict_v3t'
    from frozen import FrozenN6
    from physics_decoder import R3Decoder
    from losses import group_rmse
    torch.set_num_threads(1)
    protocol=read_json(src/'config/protocol_v3s.json')
    frozen=FrozenN6(a.project_root,protocol)
    entries=rows(rev/N5/'data_manifest.csv');fm=rows(run/'g0/fold_manifest.csv')
    guard=AccessGuard(entries,fm,run/'split_access.jsonl','G2')
    fitids={str(r['trajectory']) for r in fm if int(r['fold'])==0 and r['role']=='fit'}
    innerids={str(r['trajectory']) for r in fm if int(r['fold'])==0 and r['role']=='inner'}
    fitentries=[e for e in entries if e['trajectory_id'] in fitids]
    innerentries=[e for e in entries if e['trajectory_id'] in innerids]
    tests=[]
    def passed(n,title,evidence):
        tests.append(dict(id=n,title=title,status='PASS',evidence=evidence))
        print(f'G2 test {n} PASS {title}',flush=True)
    try:
        norm=fit_normalization(fitentries,guard,0)
        s0=fit_s0(fitentries,norm,guard,0)
        np.savez(dest/'fold0_normalization.npz',**norm)
        np.savez(dest/'fold0_s0.npz',coefficients=s0['coefficients'])
        write_json(dest/'fold0_s0.json',{k:v for k,v in s0.items() if k!='coefficients'})
        d=Decoder(frozen.build_planar_grasp_matrix)
        nd=R3Decoder(frozen.build_planar_grasp_matrix)
        resolver=lambda e:frozen.resolved_params(int(e['seed']),protocol)
        data=WindowData(fitentries,norm,guard,0,'optimize',resolver,d,'cpu')
        inner=WindowData(innerentries,norm,guard,0,'monitor',resolver,d,'cpu')
        model=new_model(s0['coefficients'],994100)
        anchor_model=copy.deepcopy(model)
        with torch.no_grad():
            anchor_model.E.zero_()
        af,_=evaluate(anchor_model,data);ai,_=evaluate(anchor_model,inner)
        np.savez(dest/'fold0_anchors.npz',fit=af.numpy(),inner=ai.numpy())
        ix=data.sample(np.random.default_rng(994900),0)
        # 1 legacy T0 forward/grad equality.
        import importlib.util
        spec=importlib.util.spec_from_file_location('historical_unchanged_lift',rev/'koopman_predict_v3s/src/lift.py')
        old_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(old_module)
        coeff=s0['coefficients']
        old=old_module.TriangularResidualKoopman(coeff[:47].T,coeff[47:54].T,coeff[54],16,8,16)
        old.load_state_dict(model.state_dict());new=copy.deepcopy(model)
        pp=old.rollout(data.x[ix].float(),data.u[ix].float(),(1,5,10,20))['xhat']
        groups={'g0':(.3,slice(0,3)),'g1':(.2,slice(3,19)),'g2':(.2,slice(19,31)),'g3':(.3,slice(31,47))}
        from train import step_loss
        objective=step_loss(old,dict(x0=data.x[ix].float(),u_seq=data.u[ix].float(),x_target=torch.cat((data.x[ix,None,:],data.y[ix]),1).float()),protocol,'MH',groups,None,None)['total']
        value=loss(new,data,ix,'T0',af,torch.zeros(55))
        write_json(dest/'T0_comparison.json',dict(legacy_value=float(objective.detach()),candidate_value=float(value.detach()),absolute_difference=float((objective-value).abs().detach()),reference='unchanged v3s train.step_loss, not a manually reassociated expression'))
        objective.backward();value.backward()
        check(torch.equal(objective,value),'T0 objective mismatch')
        diff=max(float((p.grad-q.grad).abs().max()) for p,q in zip(old.parameters(),new.parameters()))
        check(diff<=1e-6,'T0 gradient mismatch')
        passed(1,'legacy T0 equality',dict(loss=float(value.detach()),gradient_max_abs=diff))
        # 2 both hardware/dtype pathways against frozen NumPy.
        parity=[]
        for entry in fitentries[:8]:
            cache=guard.load(entry,0,'optimize');params=resolver(entry)
            x=cache['relative_state47'][::max(1,len(cache['relative_state47'])//30)]
            for device in ('cpu','cuda'):
                for dtype,atol,rtol in ((torch.float64,1e-8,1e-10),(torch.float32,1e-4,1e-5)):
                    t=torch.tensor(x,device=device,dtype=dtype)
                    # Compare identical rounded input, so this tests decoder arithmetic,
                    # not ill-conditioned force sensitivity to state quantization.
                    nf,ni=nd.connector_force(t.cpu().double().numpy(),params,'R3')
                    f,inn=d(t,params,entry['params_sha256'])
                    f=f.detach().cpu().double().numpy();inn=inn.detach().cpu().double().numpy()
                    ok=np.allclose(f,nf,atol=atol,rtol=rtol) and np.allclose(inn,ni,atol=atol,rtol=rtol)
                    parity.append(dict(trajectory=entry['trajectory_id'],device=device,dtype=str(dtype),force_max_abs_N=float(np.max(abs(f-nf))),internal_max_abs_N=float(np.max(abs(inn-ni))),passed=bool(ok)))
        write_json(dest/'decoder_parity.json',parity)
        check(all(r['passed'] for r in parity),'decoder parity hard gate')
        passed(2,'CPU/CUDA f64/f32 physical parity',parity)
        # 3 decoder gradient and all expected h20 model paths.
        p=resolver(fitentries[0]);x=torch.zeros((2,47),dtype=torch.float64)
        x[:,31:47]=torch.tensor([.01,.004,.03,.02]*4,dtype=torch.float64)
        x.requires_grad_()
        check(torch.autograd.gradcheck(lambda t:d(t,p,'gradcheck'),(x,),eps=1e-7,atol=1e-4,rtol=1e-4),'decoder gradcheck failed')
        mg=copy.deepcopy(model)
        err,pred,target=data.errors(mg,ix)
        physical=err[:,3,3:5].mean();physical.backward()
        paths={name:float(p.grad.abs().sum()) if p.grad is not None else 0. for name,p in mg.named_parameters()}
        check(all(v>0 and np.isfinite(v) for v in paths.values()),'h20 physical gradient path missing')
        write_json(dest/'gradient_audit.json',paths);passed(3,'physical gradient paths',paths)
        # 4 E=0 equals explicit NumPy S0 at all registered horizons.
        z=copy.deepcopy(anchor_model).double()
        xx=data.x[ix[:8]].clone();uu=data.u[ix[:8]];out=z.rollout(xx,uu,(1,5,10,20))['xhat'];direct=xx.numpy().copy()
        maxdiff=0.
        for h in range(20):
            direct=direct@s0['coefficients'][:47]+uu[:,h].numpy()@s0['coefficients'][47:54]+s0['coefficients'][54]
            maxdiff=max(maxdiff,float(np.max(abs(direct-out[:,h].detach().numpy()))))
        check(maxdiff<1e-10,'Ezero mismatch');passed(4,'E zero fallback',dict(max_abs=maxdiff))
        # 5/6 exact direction and denominator tests.
        base=torch.ones((12,4,6),dtype=torch.float64)*.1
        g=constraints(base,base);check(g.shape==(55,) and bool((g<0).all()),'S0 infeasible')
        bad=base.clone();bad[:,0,0]*=1.4;check(float(constraints(bad,base)[0])>.36,'40pct short-term not blocked')
        passed(5,'55 constraints and short-term gate',dict(count=55,forty_pct_g=float(constraints(bad,base)[0])))
        bb=base.clone();bb[0,0,0]=.00295484;cc=bb.clone();cc[0,0,0]=.00405390
        degradation=float((cc[0,0,0]-bb[0,0,0])/.02*100)
        check(abs(degradation-5.4953)<1e-9 and float(constraints(cc,bb)[3])>0,'D0 floor denominator incorrect')
        check(float(constraints(bb*.8,bb).max())<0,'improvement sign wrong')
        passed(6,'D0 regression example',dict(degradation_pct=degradation))
        # 7 endpoint indexing (no u[k+20]) and target causal isolation.
        before=model.rollout(data.x[ix[:2]].float(),data.u[ix[:2]].float(),(20,))['xhat'].detach()
        target_clone=data.y.clone();data.y+=123
        after=model.rollout(data.x[ix[:2]].float(),data.u[ix[:2]].float(),(20,))['xhat'].detach()
        data.y=target_clone
        check(torch.equal(before,after) and data.u.shape[1]==20,'future-target leakage')
        passed(7,'horizon and target isolation',dict(controls=20,targets_enter_predictor=False))
        # 8 fit-only statistics plus perturbation of independently held-out arrays.
        norm2=fit_normalization(fitentries,guard,0);s02=fit_s0(fitentries,norm2,guard,0)
        baseline_sha=hashlib_arrays(norm2,s02['coefficients'])
        inner.x+=10000;inner.force*=7
        outer_synthetic=np.full((12,21,47),1e9) # deliberately not loaded outer data
        norm3=fit_normalization(fitentries,guard,0);s03=fit_s0(fitentries,norm3,guard,0)
        check(baseline_sha==hashlib_arrays(norm3,s03['coefficients']),'heldout perturbed fit identity')
        inner=WindowData(innerentries,norm,guard,0,'monitor',resolver,d,'cpu')
        wa=new_model(s02['coefficients'],994100);wb=new_model(s03['coefficients'],994100)
        check(all(torch.equal(x,y) for x,y in zip(wa.state_dict().values(),wb.state_dict().values())),'warm initialization changed')
        oa=torch.optim.AdamW(wa.parameters(),lr=.001);ob=torch.optim.AdamW(wb.parameters(),lr=.001)
        for _ in range(2):
            for mm,oo in ((wa,oa),(wb,ob)):
                oo.zero_grad();loss(mm,data,ix,'warm',af,torch.zeros(55)).backward();oo.step()
        check(all(torch.equal(x,y) for x,y in zip(wa.state_dict().values(),wb.state_dict().values())),'warm update changed after heldout perturbation')
        passed(8,'fit identity independent of heldout arrays',dict(identity=baseline_sha,outer_values_read=False,scope='inner numeric perturbation and no outer dependency; actual outer read denied in test12'))
        # 9 GPU evaluation clone cannot mutate original model.
        gpu=copy.deepcopy(model).cuda();state={k:(v.dtype,v.device, v.detach().clone()) for k,v in gpu.state_dict().items()};gpu.train()
        _=evaluate(gpu,inner)
        check(gpu.training and all(v.dtype==state[k][0] and v.device==state[k][1] and torch.equal(v,state[k][2]) for k,v in gpu.state_dict().items()),'evaluation mutated training model')
        passed(9,'evaluation copy isolation',dict(original_mode='train',original_device='cuda'))
        # 10/11 exact trainer resume on a small synthetic fit/inner fixture.
        data_resume=synthetic_fixture(data,994900)
        inner_resume=synthetic_fixture(data,994901)
        af_resume,_=evaluate(anchor_model,data_resume)
        ai_resume,_=evaluate(anchor_model,inner_resume)
        ident=dict(code=sha(src/'src/guard_training.py'),protocol=sha(a.protocol),data=sha(rev/N5/'data_manifest.csv'),fold=0,phase='T2',norm=baseline_sha,seed=995001)
        def fresh():
            random.seed(995001);np.random.seed(995001);torch.manual_seed(995001)
            return new_model(s0['coefficients'],995001)
        aa=fresh();train_phase(aa,data_resume,inner_resume,af_resume,ai_resume,'T2',995001,ident,dest/'resume_continuous',max_steps=600,min_steps=2000)
        bbm=fresh();train_phase(bbm,data_resume,inner_resume,af_resume,ai_resume,'T2',995001,ident,dest/'resume_split',max_steps=600,stop_at=350,min_steps=2000)
        train_phase(bbm,data_resume,inner_resume,af_resume,ai_resume,'T2',995001,ident,dest/'resume_split',max_steps=600,resume=dest/'resume_split/last.pt',min_steps=2000)
        pa=torch.load(dest/'resume_continuous/last.pt',weights_only=False);pb=torch.load(dest/'resume_split/last.pt',weights_only=False)
        for key in ('model','optimizer','rng','sampler','lambda','sample_hash','step','best','best_q','best_step','no_improve','last_monitor'):
            check(equal_nested(pa[key],pb[key]),f'resume mismatch {key}')
        rejected=[]
        for field in ('code','protocol','data','fold','phase','norm'):
            wrong=dict(ident);wrong[field]='bad'
            try:
                validate(pa,wrong)
            except ValueError:
                rejected.append(field)
        wrong=copy.deepcopy(pa);wrong['lambda'][0]=float('nan')
        try:
            validate(wrong,ident)
        except ValueError:
            rejected.append('lambda')
        check(len(rejected)==7,'bad checkpoint accepted')
        passed(10,'resume identity rejection and fresh formal AdamW',dict(rejected=rejected,formal_momentum='new optimizer per method; only explicit resume restores momentum'))
        resume_evidence=dict(continuous_steps=600,split_steps=[350,250],crossed_multiplier_update=500,bitwise_equal_fields=['model','optimizer','rng','sampler','lambda','sample_hash'],next_batch_identical=pa['sampler']==pb['sampler'],tolerance=1e-7)
        write_json(dest/'resume_equivalence.json',resume_evidence);passed(11,'atomic last and exact resume',resume_evidence)
        # 12 real forbidden opens, including raw bypass of guard.load.
        denials=[]
        for role in ('inner','outer'):
            rr=next(r for r in fm if int(r['fold'])==0 and r['role']==role)
            e=next(e for e in entries if e['trajectory_id']==rr['trajectory'])
            try:
                with guard.context(0,'optimize'):
                    with open(e['cache_path'],'rb') as f:
                        f.read(1)
            except PermissionError:
                denials.append(role)
        for split in ('validation','development'):
            e=next(e for e in entries if e['split']==split)
            try:
                guard.load(e,0,'optimize')
            except PermissionError:
                denials.append(split)
        for split in ('new_validation','confirm'):
            try:
                with open(rev/f'koopman_predict_v3t_data/{split}/denied.npz','rb') as f:
                    f.read(1)
            except PermissionError:
                denials.append(split)
        check(len(denials)==6,'permission gate failure')
        passed(12,'actual file-open denials',dict(denied=denials,fit_allowed=True,inner_monitor_allowed=True))
        # 13 effective fullK propagation convention.
        mm=copy.deepcopy(model).double();K=full_k(mm)
        check(torch.equal(K,mm.full_k_matrix()),'public full_k_matrix differs from effective propagation')
        x=torch.randn(3,47,dtype=torch.float64);eta=torch.randn(3,16,dtype=torch.float64)
        actual=torch.cat((x@mm.A0.T+eta@mm.E.T,eta@mm.f_matrix()),1)
        check(torch.allclose(torch.cat((x,eta),1)@K.T,actual,atol=1e-12,rtol=1e-12),'fullK transpose mismatch')
        passed(13,'full K effective column convention',dict(F_c='code_f_matrix.T'))
        # 14 subprocess nonzero, nonfinite and evidence completeness guards.
        code=subprocess.run([sys.executable,'-c','import sys;sys.exit(7)']).returncode
        check(code==7,'subprocess status lost')
        rejected=[]
        for val in (float('nan'),float('inf')):
            corrupt=synthetic_fixture(data,995005);corrupt.x[0,0]=val
            try:
                corrupt.errors(model,np.arange(12))
            except FloatingPointError:
                rejected.append(str(val))
        for invalid in (data.meta+[data.meta[0]],[m for m in data.meta if m['scenario']!=0]):
            try:
                validate_rows(invalid)
            except ValueError:
                rejected.append('invalid_rows')
        try:
            with open(dest/'missing_required_artifact.json','rb') as f:
                f.read()
        except FileNotFoundError:
            rejected.append('missing_file')
        check(len(rejected)==5,'negative fixtures failed to raise')
        keys=[(m['trajectory'],m['start']) for m in data.meta]
        check(len(keys)==len(set(keys)) and set(data.tree)==set(range(12)),'row coverage')
        passed(14,'failure signals preserved',dict(nonzero_exit=code,rejected=rejected,unique_rows=len(keys),scenario_count=12))
        # 15 numeric smooth bound and f32 rounding separately.
        err=torch.linspace(-1.,1.,1001,dtype=torch.float64).reshape(-1,1)
        diff=float((smooth_rmse(err)-smooth_rmse(err,smooth=False)).abs().max())
        check(diff<=1e-8+1e-15,'smooth bound failure')
        check(torch.allclose(smooth_rmse(err.float()).double(),smooth_rmse(err),atol=1e-6,rtol=1e-5),'f32 smooth rounding')
        passed(15,'smooth epsilon and dtype tolerance',dict(max_difference=diff))
        write_json(dest/'tests.json',dict(status='PASS',tests=sorted(tests,key=lambda x:x['id'])))
        modules={name:str(sys.modules[name].__file__) for name in ('guard_core','guard_training','lift','guard_tests','evaluation_v2')}
        write_json(dest/'module_paths.json',modules)
        source_manifest={str(p.relative_to(src)).replace('\\','/'):sha(p) for p in sorted(src.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.md') and '__pycache__' not in p.parts}
        write_json(dest/'source_manifest.json',source_manifest)
        (dest/'pytest.txt').write_text('Executed explicit Python assertion harness, not pytest collection.\n'+ '\n'.join(f"{t['id']}: PASS {t['title']}" for t in tests),encoding='utf-8')
        write_json(dest/'complete.json',dict(stage='G2',status='PASS',next_stage='G3'))
        log(run,'G2','PASS',dict(test_count=15))
    except Exception as exc:
        write_json(dest/'tests.json',dict(status='BLOCKED',passed_tests=tests,error=repr(exc)))
        write_json(dest/'complete.json',dict(stage='G2',status='BLOCKED',next_stage=None,error=repr(exc)))
        raise
    finally:
        guard.enabled=False

def hashlib_arrays(norm,coeff):
    import hashlib
    h=hashlib.sha256()
    for key in sorted(norm):
        h.update(key.encode());h.update(np.asarray(norm[key]).tobytes())
    h.update(coeff.tobytes());return h.hexdigest().upper()

def equal_nested(a,b):
    if isinstance(a,torch.Tensor):
        return torch.equal(a.cpu(),b.cpu())
    if isinstance(a,np.ndarray):
        return np.array_equal(a,b)
    if isinstance(a,dict):
        return a.keys()==b.keys() and all(equal_nested(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):
        return len(a)==len(b) and all(equal_nested(x,y) for x,y in zip(a,b))
    return a==b

def synthetic_fixture(source,seed):
    """Synthetic normalized states/targets, not historical windows relabelled synthetic."""
    obj=copy.copy(source)
    ix=[next(i for i,m in enumerate(source.meta) if m['scenario']==s) for s in range(12)]
    rng=np.random.default_rng(seed)
    obj.x=torch.tensor(rng.normal(0,.05,(12,47)),dtype=torch.float64)
    obj.u=torch.tensor(rng.normal(0,.05,(12,20,7)),dtype=torch.float64)
    obj.y=obj.x[:,None,:].repeat(1,20,1)+torch.tensor(rng.normal(0,.002,(12,20,47)),dtype=torch.float64)
    obj.projectors=source.projectors[ix].clone();obj.law_constants=source.law_constants[ix].clone()
    obj.meta=[dict(trajectory=f'synthetic_{seed}_{s}',family=f'synthetic_{seed}_{s}',scenario=s,start=0,params_sha=source.meta[ix[s]]['params_sha']) for s in range(12)]
    obj.scenario=torch.arange(12);obj.params=[source.params[i] for i in ix];obj.keys=[source.keys[i] for i in ix]
    obj.tree={s:{f'synthetic_{seed}_{s}':{f'synthetic_{seed}_{s}':[s]}} for s in range(12)}
    obj.force,obj.internal=obj.physical(obj.y,np.arange(12))
    return obj
