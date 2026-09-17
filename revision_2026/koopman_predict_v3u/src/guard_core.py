"""v3t fold-local data, balanced sampling, physical readout and protections."""
import contextlib
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
import numpy as np
import torch

H=(1,5,10,20)
HW=(.1,.2,.25,.45)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper()

class AccessGuard:
    """An actual CPython file-open audit, not a self-reported loader ledger."""
    def __init__(self,entries,fold_rows,log_path,stage='G2'):
        self.by_path={}
        for e in entries:
            for key in ('cache_path','raw_path'):
                if key in e:
                    self.by_path[self.canon(e[key])]=e
        self.roles={(int(r['fold']),str(r['trajectory'])):r['role'] for r in fold_rows}
        self.log_path=Path(log_path);self.stage=stage;self.current=None;self.outer_frozen=False;self.enabled=True
        sys.addaudithook(self._audit)
    @staticmethod
    def canon(p):
        return os.path.normcase(os.path.abspath(os.fspath(p)))
    def _audit(self,event,args):
        if not self.enabled or event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):
            return
        path=self.canon(args[0]);entry=self.by_path.get(path)
        protected=entry is not None or any(x in path.lower() for x in ('koopman_predict_auto_data','new_validation','confirm'))
        if not protected:
            return
        allow=False;role=None
        if entry is not None and self.current is not None:
            fold,purpose=self.current
            role=self.roles.get((fold,str(entry['trajectory_id'])))
            allow=entry.get('split')=='train' and entry.get('plant')=='R3-ES' and entry.get('law')=='R3'
            if purpose in ('normalization','S0','warm','optimize','fit_monitor'):
                allow=allow and role=='fit'
            elif purpose=='monitor':
                allow=allow and role=='inner'
            elif purpose=='outer_evaluate':
                allow=allow and role=='outer' and self.stage=='G4' and self.outer_frozen
            else:
                allow=False
        record=dict(stage=self.stage,context=self.current,role=role,path=path,allowed=bool(allow))
        with self.log_path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(record)+'\n')
        if not allow:
            raise PermissionError(f'denied numeric asset open: {record}')
    @contextlib.contextmanager
    def context(self,fold,purpose):
        before=self.current;self.current=(int(fold),purpose)
        try:
            yield
        finally:
            self.current=before
    def load(self,entry,fold,purpose):
        with self.context(fold,purpose):
            with np.load(entry['cache_path'],allow_pickle=False) as z:
                return {k:z[k] for k in z.files}

def u_field(norm):
    """Choose the cache control field by which normalization keys are present.
    7-dim baseline -> control7; 11-dim input protocol -> control11."""
    if "control11_mean" in norm and "control11_scale" in norm:
        return "control11"
    return "control7"


def fit_normalization(entries,guard,fold,input_dim=7):
    control_key = "control11" if int(input_dim) >= 11 else "control7"
    keys=('relative_state47','actual_steering4',control_key,'force_payload_body8','internal_force8')
    values={k:[] for k in keys}
    for e in entries:
        cache=guard.load(e,fold,'normalization')
        assert len(cache['relative_state47'])==len(cache[control_key])+1
        for k in keys:
            values[k].append(np.asarray(cache[k],dtype=np.float64))
    result={}
    for k,parts in values.items():
        arr=np.concatenate(parts)
        result[k+'_mean']=arr.mean(0)
        result[k+'_scale']=np.maximum(arr.std(0,ddof=0),1e-12)
        result[k+'_row_count']=np.asarray(len(arr))
    return result

def fit_s0(entries,norm,guard,fold):
    from evaluation_v2 import design_matrix,solve_model
    cdim = 11 if u_field(norm) == "control11" else 7
    width = 47 + cdim + 1
    gram=np.zeros((width,width));cross=np.zeros((width,47));n=0;layout=None
    for e in entries:
        cache=guard.load(e,fold,'S0')
        X,Y,layout=design_matrix(cache,'S0','M0_FIXED_LINEAR',norm)
        gram+=X.T@X;cross+=X.T@Y;n+=len(X)
    result=solve_model(dict(gram=gram,cross=cross,layout=layout,row_count=n),variant='S0',model_kind='M0_FIXED_LINEAR',ridge=.01,rank=None)
    if not np.isfinite(result['coefficients']).all() or result['condition_number']>1e14:
        raise RuntimeError('fold S0 condition/finite hard gate failed')
    return result

class Decoder:
    """Frozen parameter constants keyed by canonical params SHA, dtype and device."""
    def __init__(self,grasp):
        self.grasp=grasp;self.cache={}
    def constants(self,p,key,like):
        actual=digest(dict(free=p.connector.free_play_m,width=p.connector.smoothing_width_m,k=p.connector.stiffness_npm,c=p.connector.damping_nspm,anchors=np.asarray(p.payload_anchor_body_m).tolist()))
        ck=(key,actual,str(like.device),str(like.dtype))
        if ck not in self.cache:
            W=self.grasp(np.asarray(p.payload_anchor_body_m,dtype=np.float64))
            P=np.eye(8)-np.linalg.pinv(W)@W
            self.cache[ck]=(torch.tensor(P,dtype=like.dtype,device=like.device),p.connector.free_play_m,p.connector.smoothing_width_m,p.connector.stiffness_npm,p.connector.damping_nspm)
        return self.cache[ck]
    def __call__(self,x,p,key):
        P,free,width,k,c=self.constants(p,key,x)
        shape=x.shape;v=x.reshape(-1,47)[:,31:47].reshape(-1,4,4)
        d=v[:,:,:2];vel=v[:,:,2:];dist=torch.linalg.vector_norm(d,dim=-1)
        normal=d/torch.clamp(dist[...,None],min=1e-12)
        pen=torch.clamp(dist-free,min=0)
        t=torch.clamp(pen/width,0,1)
        w=torch.where(pen<=0,torch.zeros_like(pen),torch.where(pen>=width,torch.ones_like(pen),3*t**2-2*t**3))
        mag=k*pen+c*w*torch.clamp(torch.sum(vel*normal,dim=-1),min=0)
        f=(mag[...,None]*normal).reshape(*shape[:-1],8)
        return f,f@P.T

def new_model(coeff,seed,input_dim=7):
    from lift import TriangularResidualKoopman
    torch.manual_seed(seed)
    cdim=int(input_dim)
    return TriangularResidualKoopman(coeff[:47].T,coeff[47:47+cdim].T,coeff[47+cdim],16,8,16,input_dim=cdim)

def full_k(model):
    A=model.A0.double();E=model.E.double();F=model.f_matrix().double().T
    return torch.cat((torch.cat((A,E),1),torch.cat((torch.zeros((16,47),device=A.device,dtype=A.dtype),F),1)),0)

def validate_rows(meta):
    if not meta:
        raise ValueError('empty rows')
    keys=[(m['trajectory'],m['start']) for m in meta]
    if len(keys)!=len(set(keys)):
        raise ValueError('duplicate rows')
    if {m['scenario'] for m in meta}!=set(range(12)):
        raise ValueError('missing scenario')

def smooth_rmse(err,dim=-1,smooth=True):
    sq=torch.mean(err**2,dim=dim)
    return torch.sqrt(sq+1e-16)-1e-8 if smooth else torch.sqrt(sq)

def component_errors(pred,target,force_pred,int_pred,force_target,int_target,norm,smooth=True):
    # pred and target are normalized; force targets are physical N.
    err=pred-target
    fs=torch.as_tensor(norm['force_payload_body8_scale'],dtype=pred.dtype,device=pred.device)
    ins=torch.as_tensor(norm['internal_force8_scale'],dtype=pred.dtype,device=pred.device)
    cols=[smooth_rmse(err[...,:3],smooth=smooth),smooth_rmse(err[...,3:],smooth=smooth),smooth_rmse((force_pred-force_target)/fs,smooth=smooth),smooth_rmse((int_pred-int_target)/ins,smooth=smooth),smooth_rmse(err[...,[2,21,24,27,30]],smooth=smooth)]
    comp=torch.stack(cols,-1)
    weights=torch.tensor([.25,.2,.2,.15,.1],device=pred.device,dtype=pred.dtype)
    return torch.cat(((comp*weights).sum(-1,keepdim=True)/.9,comp),-1)

def constraints(stats,anchor):
    # stats: scenario(12), horizon(4), [J,core,relative,force,internal,yaw]
    m=stats.mean(0);b=anchor.mean(0)
    short=(m[:3,0]-b[:3,0])/b[:3,0].clamp_min(1e-12)-.03
    scenario=((stats[:,:,0]-anchor[:,:,0])/anchor[:,:,0].clamp_min(.02)-.03).reshape(-1)
    physical=torch.stack([(m[h,c]-b[h,c])/b[h,c].clamp_min(1e-12)-.05 for c in (3,4) for h in (0,3)])
    return torch.cat((short,scenario,physical))

def balanced_mean(values,scenario):
    return torch.stack([values[scenario==s].mean(0) for s in range(12)])

def hierarchy_mean(values,meta):
    # Deterministic differentiable reduction window->trajectory->family->scenario.
    result=[]
    for s in range(12):
        families=sorted({m['family'] for m in meta if m['scenario']==s})
        if not families:
            raise ValueError('missing scenario')
        famvalues=[]
        for fam in families:
            tids=sorted({m['trajectory'] for m in meta if m['family']==fam})
            tr=[]
            for tid in tids:
                ix=[i for i,m in enumerate(meta) if m['trajectory']==tid]
                tr.append(values[ix].mean(0))
            famvalues.append(torch.stack(tr).mean(0))
        result.append(torch.stack(famvalues).mean(0))
    return torch.stack(result)

class WindowData:
    def __init__(self,entries,norm,guard,fold,purpose,params_resolver,decoder,device='cpu',horizon=20):
        self.meta=[];self.params=[];self.keys=[];xs=[];us=[];ys=[];fs=[];ins=[]
        self.norm=norm;self.device=device;self.decoder=decoder
        self.missing=0
        ukey = u_field(norm)
        unorm_mean = norm[f"{ukey}_mean"]
        unorm_scale = norm[f"{ukey}_scale"]
        for e in entries:
            c=guard.load(e,fold,purpose)
            p=params_resolver(e)
            for start in c['window_start'].astype(int):
                if start+horizon>=len(c['relative_state47']) or start+horizon>len(c[ukey]):
                    self.missing+=1
                    if horizon==20:
                        raise ValueError('registered window lacks targets/controls')
                    continue
                self.meta.append(dict(trajectory=str(e['trajectory_id']),family=e['base_family_id'],scenario=int(e['scenario'][1:]),start=int(start),params_sha=e['params_sha256']))
                xs.append((c['relative_state47'][start]-norm['relative_state47_mean'])/norm['relative_state47_scale'])
                us.append((c[ukey][start:start+horizon]-unorm_mean)/unorm_scale)
                ys.append((c['relative_state47'][start+1:start+horizon+1]-norm['relative_state47_mean'])/norm['relative_state47_scale'])
                fs.append(c['force_payload_body8'][start+1:start+horizon+1]);ins.append(c['internal_force8'][start+1:start+horizon+1])
                self.params.append(p);self.keys.append(e['params_sha256'])
        self.x=torch.tensor(np.array(xs),device=device,dtype=torch.float64)
        self.u=torch.tensor(np.array(us),device=device,dtype=torch.float64)
        self.y=torch.tensor(np.array(ys),device=device,dtype=torch.float64)
        self.force=torch.tensor(np.array(fs),device=device,dtype=torch.float64)
        self.internal=torch.tensor(np.array(ins),device=device,dtype=torch.float64)
        self.scenario=torch.tensor([m['scenario'] for m in self.meta],device=device)
        constants=[self.decoder.constants(p,k,self.x) for p,k in zip(self.params,self.keys)]
        self.projectors=torch.stack([c[0] for c in constants])
        self.law_constants=torch.tensor([[c[1],c[2],c[3],c[4]] for c in constants],device=device,dtype=torch.float64)
        self.tree={}
        for i,m in enumerate(self.meta):
            self.tree.setdefault(m['scenario'],{}).setdefault(m['family'],{}).setdefault(m['trajectory'],[]).append(i)
        if set(self.tree)!=set(range(12)):
            raise ValueError('missing scenario in window data')
        if not all(torch.isfinite(t).all() for t in (self.x,self.u,self.y,self.force,self.internal)):
            raise ValueError('nonfinite cache data')
    def sample(self,rng,step):
        out=[]
        extra={(4*step+j)%12 for j in range(4)}
        for s in range(12):
            fams=sorted(self.tree[s])
            for _ in range(21+(s in extra)):
                fam=fams[int(rng.integers(len(fams)))];tids=sorted(self.tree[s][fam]);tid=tids[int(rng.integers(len(tids)))];ix=self.tree[s][fam][tid]
                out.append(ix[int(rng.integers(len(ix)))])
        return np.array(out,dtype=np.int64)
    def physical(self,pred,indices):
        # Vectorized over batch and horizons; fixed constants per sample.
        mean=torch.as_tensor(self.norm['relative_state47_mean'],device=pred.device,dtype=pred.dtype)
        scale=torch.as_tensor(self.norm['relative_state47_scale'],device=pred.device,dtype=pred.dtype)
        raw=pred*scale+mean
        law=self.law_constants[indices].to(pred)
        free,width,k,c=[law[:,j,None,None] for j in range(4)]
        v=raw[...,31:47].reshape(len(indices),-1,4,4)
        d=v[...,:2];vel=v[...,2:];dist=torch.linalg.vector_norm(d,dim=-1)
        normal=d/dist[...,None].clamp_min(1e-12)
        pen=(dist-free).clamp_min(0);t=(pen/width).clamp(0,1)
        weight=torch.where(pen<=0,torch.zeros_like(pen),torch.where(pen>=width,torch.ones_like(pen),3*t**2-2*t**3))
        mag=k*pen+c*weight*(vel*normal).sum(-1).clamp_min(0)
        f=(mag[...,None]*normal).reshape(len(indices),-1,8)
        return f,torch.bmm(f,self.projectors[indices].to(pred).transpose(1,2))
    def errors(self,model,indices,smooth=True,dtype=torch.float32):
        pred=model.rollout(self.x[indices].to(dtype),self.u[indices].to(dtype),H)['xhat'][:,[h-1 for h in H]]
        f,inn=self.physical(pred,indices)
        target=self.y[indices][:,[h-1 for h in H]].to(dtype)
        ft=self.force[indices][:,[h-1 for h in H]].to(dtype);it=self.internal[indices][:,[h-1 for h in H]].to(dtype)
        errors=component_errors(pred,target,f,inn,ft,it,self.norm,smooth)
        if not torch.isfinite(errors).all():
            raise FloatingPointError('nonfinite prediction/metric')
        return errors,pred,target

def evaluate(model,data,batch=256):
    clone=copy.deepcopy(model).to(data.device).double().eval()
    parts=[]
    with torch.no_grad():
        for start in range(0,len(data.meta),batch):
            ix=np.arange(start,min(start+batch,len(data.meta)))
            errors,_,_=data.errors(clone,ix,smooth=False,dtype=torch.float64)
            parts.append(errors)
    v=torch.cat(parts)
    return hierarchy_mean(v,data.meta),v

def loss(model,data,ix,method,anchor,lam):
    from losses import group_rmse
    errors,pred,target=data.errors(model,ix)
    reg=1e-4*(model.E**2).sum()+1e-5*sum((p**2).sum() for p in model.parameters())
    if method in ('warm','T0'):
        groups={'g0':(.3,slice(0,3)),'g1':(.2,slice(3,19)),'g2':(.2,slice(19,31)),'g3':(.3,slice(31,47))}
        val=group_rmse(pred[:,0],target[:,0],groups) if method=='warm' else sum(w*group_rmse(pred[:,j],target[:,j],groups) for j,w in enumerate(HW))
    else:
        stats=balanced_mean(errors,data.scenario[ix])
        val=sum(w*stats[:,j,0].mean() for j,w in enumerate(HW))
        if method=='T2':
            g=constraints(stats,anchor.to(stats))
            val=val+anchor[:,3,0].mean()/55*((lam.to(g)*g)+.5*g.clamp_min(0)**2).sum()
    return val+reg

def score(stats,anchor):
    g=constraints(stats,anchor)
    if not torch.isfinite(g).all():
        raise FloatingPointError('nonfinite selection')
    pos=g.clamp_min(0)
    return (float(pos.max()),float(pos.sum()),float(stats[:,3,0].mean()))

def improves(new,old,tol=1e-10):
    if old is None:
        return True
    for n,o in zip(new,old):
        if n<o-tol:
            return True
        if n>o+tol:
            return False
    return False
