"""Exact precomputed affine propagation; full state/force/internal readout timed."""
import copy
import time
import numpy as np
import torch


class FastPredict:
    def __init__(self,model,horizon=20):
        self.model=copy.deepcopy(model).double().eval()
        self.horizon=horizon
        m=self.model
        with torch.no_grad():
            k=torch.zeros((64,64),device=m.A0.device,dtype=torch.float64)
            k[:47,:47]=m.A0;k[:47,47:63]=m.E;k[:47,63]=m.b0
            k[47:63,47:63]=m.f_matrix().T;k[47:63,63]=m.c;k[63,63]=1
            b=torch.zeros((64,11),device=k.device,dtype=k.dtype)
            b[:47]=m.B0;b[47:63]=m.G
            powers=[torch.eye(64,device=k.device,dtype=k.dtype)]
            for _ in range(horizon):powers.append(powers[-1]@k)
            self.zmap=torch.cat([powers[h+1][:47] for h in range(horizon)])
            self.umap=torch.zeros((horizon*47,horizon*11),device=k.device,dtype=k.dtype)
            for h in range(horizon):
                for i in range(h+1):self.umap[h*47:(h+1)*47,i*11:(i+1)*11]=(powers[h-i]@b)[:47]

    def rollout(self,x,u,horizons):
        eta=self.model.encoder(x,u[:,0])
        z=torch.cat((x,eta,torch.ones_like(x[:,:1])),dim=1)
        return {"xhat":(z@self.zmap.T+u[:,:self.horizon].reshape(len(x),-1)@self.umap.T).reshape(len(x),self.horizon,47)}


def benchmark(model,data):
    results=[]
    if len(data.meta)!=1:
        raise ValueError("benchmark requires one deterministic minimal case")
    idx=min(range(len(data.meta)),key=lambda i:(data.meta[i]["family"],data.meta[i]["trajectory"],data.meta[i]["start"]))
    for device in ("cpu","cuda"):
        model1=copy.deepcopy(model).to(device).double().eval()
        d=copy.copy(data)
        d.law_constants=data.law_constants[idx:idx+1].to(device)
        d.projectors=data.projectors[idx:idx+1].to(device)
        x=data.x[idx:idx+1].to(device);u=data.u[idx:idx+1,:20].to(device)
        start=time.perf_counter();fast=FastPredict(model1)
        if device=="cuda":torch.cuda.synchronize()
        preparation=time.perf_counter()-start
        def forward(m):
            p=m.rollout(x,u,(20,))["xhat"]
            f,inn=d.physical(p,np.array([0]))
            return p,f,inn
        with torch.no_grad():
            a=forward(model1);b=forward(fast)
            errors=[float((v-w).abs().max()) for v,w in zip(a,b)]
            if not all(torch.allclose(v,w,atol=1e-8,rtol=1e-10) for v,w in zip(a,b)):
                raise ValueError("precomputed inference is not equivalent")
            for label,m in (("original",model1),("precomputed",fast)):
                for _ in range(200):forward(m)
                if device=="cuda":torch.cuda.synchronize()
                ms=[]
                for _ in range(1000):
                    t=time.perf_counter();forward(m)
                    if device=="cuda":torch.cuda.synchronize()
                    ms.append((time.perf_counter()-t)*1000)
                results.append(dict(device=device,variant=label,median_ms=float(np.median(ms)),
                                    p99_ms=float(np.quantile(ms,.99)),preparation_s=preparation,
                                    max_abs_state_force_internal=errors,includes="encoder+20 state+20 force+20 internal"))
    cpu=next(r for r in results if r["device"]=="cpu" and r["variant"]=="precomputed")
    gpu=next(r for r in results if r["device"]=="cuda" and r["variant"]=="precomputed")
    return dict(passed=cpu["median_ms"]<5 and gpu["median_ms"]<1 and gpu["p99_ms"]<2,results=results,
                batch=1,cpu_threads=1,warmup=200,measurements=1000,input_resident=True)
