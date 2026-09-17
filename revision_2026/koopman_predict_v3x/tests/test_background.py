import copy
import numpy as np
import pytest
import torch
import guard_core as gc
from background_core import (mse_data_loss,complete_quality,select_gamma,nominate,
    curriculum_trigger,hierarchy,weighted_tail,pure,residual_mse_loss)
from background_speed import FastPredict


def test_mse_value_gradient_and_unbalanced_scenarios():
    e=torch.ones(25,47,dtype=torch.float64,requires_grad=True)
    scenario=torch.tensor(list(range(12))*2+[0])
    a=mse_data_loss(e,scenario);a.backward();grad=e.grad.clone()
    x=(e.detach()*2).requires_grad_();b=mse_data_loss(x,scenario);b.backward()
    assert torch.allclose(b,4*a) and torch.allclose(x.grad,2*grad)
    assert float(a)==pytest.approx(1.)
    error=torch.zeros_like(e);error[scenario==0]=12
    assert float(mse_data_loss(error,scenario))==pytest.approx(12.)


def fixture_bundles():
    meta=[dict(scenario=s,family=f'f{s}',trajectory=f't{s}',start=start) for s in range(12) for start in (100,120)]
    errors=np.ones((24,4,6))*.1
    a=dict(meta=meta,errors=errors,pred=np.ones((24,4,47))*.1,target=np.zeros((24,4,47)),
           force=np.zeros((24,4,8)),internal=np.zeros((24,4,8)))
    a['stats']=hierarchy(errors,meta)
    return a,copy.deepcopy(a)


def test_complete_gate_catches_missing_physical_guard():
    a,b=fixture_bundles();assert complete_quality(b,a)['passed']
    b['errors'][:,1,3]*=1.1;b['stats']=hierarchy(b['errors'],b['meta'])
    assert not complete_quality(b,a)['passed']


def test_complete_gate_catches_single_large_error_and_tail():
    a,b=fixture_bundles();b['pred'][0,0,0]=21
    assert not complete_quality(b,a)['passed']
    a,b=fixture_bundles();b['errors'][10,3,0]=.108;b['stats']=hierarchy(b['errors'],b['meta'])
    q=complete_quality(b,a)
    assert not q['passed'] and any('hairpin' in r['name'] and not r['passed'] for r in q['rows'])


def test_gamma_zero_retained_and_missing_seed_rejected():
    rr=[dict(gamma=g,protected=g==0,finite=True,i20=0.,m20=.1) for g in (0.,.25,.5,.75,1.)]
    sel=select_gamma(rr)
    assert sel['gamma']==0 and sel['status']=='PROTECTED_BUT_LOW_GAIN'
    with pytest.raises(ValueError):nominate([],['aligned'])


def test_curriculum_trigger_is_conjunction_and_complete():
    curve=[dict(step=s,fit_g=[.01]*55) for s in (5000,5500,6000)]
    assert curriculum_trigger(True,[curve]*3)['triggered']
    assert not curriculum_trigger(False,[curve]*3)['triggered']
    with pytest.raises(ValueError):curriculum_trigger(True,[curve[:-1]]*3)


def test_gamma_once_affine_40_and_pure():
    rng=np.random.default_rng(40)
    coeff=rng.normal(0,.001,(59,47));coeff[:47]=np.eye(47)*.95
    model=gc.new_model(coeff,42,input_dim=11).double()
    x=torch.randn(3,47,dtype=torch.float64);u=torch.randn(3,40,11,dtype=torch.float64)
    base=pure(coeff).rollout(x,u,(40,))['xhat'];raw=model.rollout(x,u,(40,))['xhat']
    for g in (.75,0.,.25,1.,.5):
        m=copy.deepcopy(model)
        with torch.no_grad():m.E.mul_(g)
        out=m.rollout(x,u,(40,))['xhat']
        assert torch.allclose(out,base+g*(raw-base),atol=1e-12,rtol=1e-12)
    fast=FastPredict(model)
    assert torch.allclose(fast.rollout(x,u[:,:20],(20,))['xhat'],raw[:,:20],atol=1e-12,rtol=1e-12)


def test_hierarchy_scoped_and_tail_weighted():
    meta=[dict(scenario=s,family='same',trajectory='same',start=0) for s in range(12)]
    values=np.arange(12)[:,None]
    assert np.array_equal(hierarchy(values,meta),values)
    mm=[dict(family='a',trajectory='a')]*9+[dict(family='b',trajectory='b')]
    assert weighted_tail(np.array([0.]*9+[10.]),mm)==pytest.approx([5.,10.,10.,10.])


def test_guard_objective_agrees_at_zero_lambda():
    from refine_loss import loss_kc
    # Test the shared penalty directly on constraints that include positive and negative values.
    stats=torch.ones(12,4,6,dtype=torch.float64,requires_grad=True)*.1
    anchor=torch.ones_like(stats)*.095
    g=gc.constraints(stats,anchor)
    fixed=.5*g.clamp_min(0).square().sum()
    adaptive=(torch.zeros(55)*g+.5*g.clamp_min(0).square()).sum()
    assert torch.equal(fixed,adaptive)
    assert torch.equal(torch.autograd.grad(fixed,stats,retain_graph=True)[0],torch.autograd.grad(adaptive,stats)[0])


class Synthetic:
    def __init__(self):
        self.device='cpu'
        r=np.random.default_rng(91)
        self.x=torch.from_numpy(r.normal(0,.0001,(12,47)))
        self.u=torch.from_numpy(r.normal(0,.001,(12,20,11)))
        self.y=self.x[:,None,:]*torch.tensor([.9**(i+1) for i in range(20)])[None,:,None]
        self.scenario=torch.arange(12)
        self.meta=[dict(scenario=s,family=str(s),trajectory=str(s),start=100) for s in range(12)]
        self.norm=dict(force_payload_body8_scale=np.ones(8),internal_force8_scale=np.ones(8))
        self.force=torch.zeros(12,20,8,dtype=torch.float64)
        self.internal=torch.zeros_like(self.force)

    def physical(self,pred,indices):
        f=pred[...,:8]*0
        return f,f

    def sample(self,rng,step):
        return np.arange(12)

    def errors(self,model,indices,smooth=True,dtype=torch.float32):
        p=model.rollout(self.x[indices].to(dtype),self.u[indices].to(dtype),(1,5,10,20))['xhat'][:,[0,4,9,19]]
        f,i=self.physical(p,indices);target=self.y[indices][:,[0,4,9,19]].to(dtype)
        err=gc.component_errors(p,target,f,i,self.force[indices][:,[0,4,9,19]].to(dtype),
                                self.internal[indices][:,[0,4,9,19]].to(dtype),self.norm,smooth)
        return err,p,target


@pytest.mark.parametrize('method',['adaptive_guard','residual_curriculum'])
def test_new_trainer_exact_resume_across_500_and_1000(tmp_path,method):
    import guard_training as gt
    torch.set_num_threads(1)
    data=Synthetic();coeff=np.zeros((59,47));coeff[:47]=np.eye(47)*.9
    initial=gc.new_model(coeff,321,input_dim=11)
    anchor=copy.deepcopy(initial)
    with torch.no_grad():anchor.E.zero_()
    a,_=gc.evaluate(anchor,data)
    identity=dict(test=method)
    def train(path,resume=None,stop=None):
        m=copy.deepcopy(initial)
        return gt.train_phase(m,data,data,a,a,method,99,identity,path,max_steps=1002,
            stop_at=stop,resume=resume,min_steps=1002,patience=1003,anchor_scale_m20=float(a[:,3,0].mean()))
    train(tmp_path/'full')
    train(tmp_path/'split',stop=450)
    train(tmp_path/'split',resume=tmp_path/'split/last.pt')
    p=torch.load(tmp_path/'full/last.pt',weights_only=False)
    q=torch.load(tmp_path/'split/last.pt',weights_only=False)
    assert all(torch.equal(p['model'][k],q['model'][k]) for k in p['model'])
    assert p['sample_hash']==q['sample_hash'] and p['sampler']==q['sampler']
    assert torch.equal(p['lambda'],q['lambda'])
    for key in p['optimizer']['state']:
        for field,value in p['optimizer']['state'][key].items():
            other=q['optimizer']['state'][key][field]
            assert torch.equal(value,other) if isinstance(value,torch.Tensor) else value==other
    if method=='adaptive_guard':
        early=torch.load(tmp_path/'full/step_00500.pt',weights_only=False)
        assert early['updates_completed']==1 and early['updates_applied_to_weights']==0
    else:
        assert p['curriculum_phase']=='multi_step'


def test_curriculum_actual_function_uses_registered_mse():
    from refine_loss import residual_loss
    data=Synthetic();coeff=np.zeros((59,47));coeff[:47]=np.eye(47)*.9
    model=gc.new_model(coeff,322,input_dim=11)
    ix=np.arange(12)
    assert torch.equal(residual_loss(model,data,ix),residual_mse_loss(model,data,ix))


def test_windows_project_lock_rejects_second_owner(tmp_path):
    from run_background import RunLock,StopRun
    with RunLock(tmp_path/'queue.lock'):
        with pytest.raises(StopRun):
            with RunLock(tmp_path/'queue.lock'):
                pass
