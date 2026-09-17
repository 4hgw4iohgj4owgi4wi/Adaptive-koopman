"""Single-device phased trainer with atomic, identity-checked exact resume."""
import copy
import hashlib
import json
import os
import random
import time
from pathlib import Path
import numpy as np
import torch
from guard_core import constraints,evaluate,improves,loss,score

def atomic_save(path,value,immutable=False):
    path=Path(path)
    if immutable and path.exists():
        raise FileExistsError(path)
    temp=path.with_suffix(path.suffix+'.partial')
    torch.save(value,temp);os.replace(temp,path)

def rng_state():
    return dict(python=random.getstate(),numpy=np.random.get_state(),cpu=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])

def restore_rng(state):
    random.setstate(state['python']);np.random.set_state(state['numpy']);torch.set_rng_state(state['cpu'])
    if state['cuda']:
        torch.cuda.set_rng_state_all(state['cuda'])

def validate(payload,identity):
    if payload['identity']!=identity:
        raise ValueError('checkpoint identity mismatch')
    lam=payload['lambda']
    if lam.shape!=(55,) or not torch.isfinite(lam).all() or not ((lam>=0)&(lam<=20)).all():
        raise ValueError('invalid lambda')

def train_phase(model,fit,inner,anchor_fit,anchor_inner,method,seed,identity,out,max_steps=15000,stop_at=None,resume=None,monitor_every=500,min_steps=2000,patience=2000,deadline=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001 if method=='warm' else .0003,betas=(.9,.999),eps=1e-8,weight_decay=.01)
    rng=np.random.Generator(np.random.PCG64(seed))
    lam=torch.zeros(55,device=fit.device,dtype=torch.float64)
    step=0;best=None;best_q=None;best_step=0;no_improve=0;last_monitor=0;curve=[];sample_hash='';elapsed=0.
    if resume:
        payload=torch.load(resume,map_location='cpu',weights_only=False)
        validate(payload,identity)
        model.load_state_dict(payload['model']);optimizer.load_state_dict(payload['optimizer'])
        rng.bit_generator.state=payload['sampler'];restore_rng(payload['rng'])
        lam=payload['lambda'].to(fit.device);step=payload['step'];best=payload['best'];best_q=payload['best_q'];best_step=payload['best_step'];no_improve=payload['no_improve'];last_monitor=payload['last_monitor'];curve=payload['curve'];sample_hash=payload['sample_hash'];elapsed=payload['elapsed_s']
    start=time.perf_counter();last100=start;status='COMPLETE'
    def pack():
        return dict(identity=identity,model=model.state_dict(),optimizer=optimizer.state_dict(),rng=rng_state(),sampler=copy.deepcopy(rng.bit_generator.state),lambda_=None,**{'lambda':lam},step=step,best=best,best_q=best_q,best_step=best_step,no_improve=no_improve,last_monitor=last_monitor,curve=curve,sample_hash=sample_hash,elapsed_s=elapsed+time.perf_counter()-start)
    while step<max_steps:
        if deadline is not None and time.perf_counter()>=deadline:
            status='COST_PAUSE';break
        if stop_at is not None and step>=stop_at:
            status='CONTROLLED_PAUSE';break
        ix=fit.sample(rng,step)
        sample_hash=hashlib.sha256(sample_hash.encode()+ix.tobytes()).hexdigest()
        model.train();optimizer.zero_grad(set_to_none=True)
        objective=loss(model,fit,ix,method,anchor_fit,lam)
        if not torch.isfinite(objective):
            raise FloatingPointError('nonfinite loss')
        objective.backward()
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
        optimizer.step();step+=1
        if step%100==0:
            if torch.cuda.is_available() and str(fit.device).startswith('cuda'):
                torch.cuda.synchronize()
            now=time.perf_counter()
            with (out/f'timing_{step:05d}.json').open('x',encoding='utf-8') as f:
                json.dump(dict(step=step,elapsed_block_s=now-last100,elapsed_s=elapsed+now-start),f)
            last100=now
        if step%monitor_every==0:
            started=time.perf_counter();fit_g=None;stats=None;new_best=False;new_q=False
            if method!='warm':
                if method=='T2':
                    fit_stats,_=evaluate(model,fit)
                    fit_g=constraints(fit_stats,anchor_fit)
                    lam=(lam+.5*fit_g).clamp(0,20)
                stats,_=evaluate(model,inner)
                selected=score(stats,anchor_inner)
                q=float(sum(w*stats[:,j,0].mean() for j,w in enumerate((.1,.2,.25,.45))))
                new_best=improves(selected,best)
                if new_best:
                    best=selected;best_step=step;no_improve=0
                else:
                    no_improve+=step-last_monitor
                new_q=best_q is None or q<best_q-1e-10
                if new_q:
                    best_q=q
                last_monitor=step
            item=dict(step=step,objective=float(objective.detach()),grad_norm=float(norm),best=best,best_step=best_step,best_q=best_q,lambda_values=lam.detach().cpu().tolist(),fit_g=None if fit_g is None else fit_g.detach().cpu().tolist(),inner_g=None if stats is None else constraints(stats,anchor_inner).detach().cpu().tolist(),monitor_s=time.perf_counter()-started,elapsed_s=elapsed+time.perf_counter()-start)
            curve.append(item)
            payload=pack()
            atomic_save(out/f'step_{step:05d}.pt',payload,immutable=True)
            atomic_save(out/'last.pt',payload)
            if new_best:
                atomic_save(out/'best.pt',payload)
            if new_q:
                atomic_save(out/'best_q.pt',payload)
            print(f'{identity.get("fold")} {method} step={step} loss={item["objective"]:.6g} elapsed={item["elapsed_s"]:.1f}s',flush=True)
            if method!='warm' and step>=min_steps and no_improve>=patience:
                status='EARLY_STOP';break
    payload=pack();atomic_save(out/'last.pt',payload)
    return dict(status=status,step=step,best_step=best_step,elapsed_s=payload['elapsed_s'],curve=curve,best=best,sample_hash=sample_hash)
