"""Scientific figures only from frozen G4 and G5 artifacts."""
import json
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_v3t import N5,read_json,rows,sha,write_csv,write_json
from guard_core import Decoder

COLORS={'S0':'#555555','T0':'#377eb8','T1':'#ff7f00','T2':'#4daf4a'}

def figures(run,rev,out,horizon,scenario_rows,gates,times):
    figdir=out/'figures';figdir.mkdir()
    manifest=[];plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.2,'figure.dpi':130})
    source_paths=[out/'horizons.csv',out/'scenarios.csv',out/'gates.csv',out/'latency.json']
    def save(fig,name,units,filter_note,extra=()):
        fig.tight_layout()
        for ext in ('png','pdf'):
            p=figdir/f'{name}.{ext}';fig.savefig(p,dpi=170,bbox_inches='tight')
            manifest.append(dict(file=p.name,sha256=sha(p),script_sha256=sha(Path(__file__)),data_sha256={str(s):sha(s) for s in source_paths+list(extra)},filter=filter_note,units=units,statistics='window->trajectory->family->scenario; paired family bootstrap where shown'))
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4))
    for m in COLORS:
        rr=sorted((r for r in horizon if r['method']==m),key=lambda r:r['horizon'])
        x=[r['horizon'] for r in rr];y=np.array([r['candidate'] for r in rr]);lo=np.array([r['ci_low'] for r in rr]);hi=np.array([r['ci_high'] for r in rr])
        ax.plot(x,y,'o-',label=m,color=COLORS[m]);ax.fill_between(x,lo,hi,alpha=.13,color=COLORS[m])
    ax.set(xlabel='Prediction steps (0.02 s each)',ylabel='J common (normalized)',title='Frozen outer estimates; 95% family bootstrap intervals');ax.legend()
    save(fig,'01_horizon','dimensionless','all five folds; all 12 scenarios')
    fig,axes=plt.subplots(1,3,figsize=(12,6),sharey=True)
    for ax,m in zip(axes,('T0','T1','T2')):
        matrix=np.array([[next(r['degradation_pct'] for r in scenario_rows if r['method']==m and r['scope']=='pooled' and r['scenario']==s and r['horizon']==h) for h in (1,5,10,20)] for s in range(12)])
        vmax=max(3,float(np.max(abs(matrix))))
        im=ax.imshow(matrix,cmap='RdBu_r',vmin=-vmax,vmax=vmax,aspect='auto');ax.set_xticks(range(4),[1,5,10,20]);ax.set_yticks(range(12),[f'D{s}' for s in range(12)]);ax.set_title(m+' (positive = degradation)');ax.set_xlabel('Horizon')
        for s in range(12):
            for h in range(4):
                ax.text(h,s,f'{matrix[s,h]:.1f}'+('*' if matrix[s,h]>3 else ''),ha='center',va='center',fontsize=7)
        fig.colorbar(im,ax=ax,label='%; * exceeds 3% gate')
    save(fig,'02_scenarios','percent','pooled12scenarios; denominator max(S0,0.02)')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    curve_paths=[]
    for m in ('T0','T1','T2'):
        for fold in range(5):
            p=run/f'g4/fold_{fold}/{m}/last.pt';curve_paths.append(p)
            ck=torch.load(p,map_location='cpu',weights_only=False)
            anchor=np.load(run/f'g4/fold_{fold}/anchors.npz')['inner'].mean(0)
            points=[]
            for c in ck['curve']:
                if c['inner_g'] is not None:
                    g=np.array(c['inner_g']);x=anchor[0,0]*(1+g[0]+.03)
                    # scenario h20 anchor needed for exact M20 reconstruction.
                    a=np.load(run/f'g4/fold_{fold}/anchors.npz')['inner'][:,:,0]
                    sg=g[3:51].reshape(12,4);y=np.mean(a[:,3]+(sg[:,3]+.03)*np.maximum(a[:,3],.02));points.append((x,y))
            if points:
                pts=np.array(points);axes[0].plot(pts[:,0],pts[:,1],'.-',color=COLORS[m],alpha=.35,label=m if fold==0 else None)
                valid_curves=[c for c in ck['curve'] if c['inner_g'] is not None]
                best_idx=next((i for i,c in enumerate(valid_curves) if c['step']==ck['best_step']),None)
                if best_idx is not None:
                    axes[0].scatter(*pts[best_idx],color=COLORS[m],marker='*',s=45)
                axes[0].scatter(*pts[-1],color=COLORS[m],marker='s',s=12)
        rr={r['horizon']:r for r in horizon if r['method']==m}
        axes[1].scatter(rr[1]['candidate'],rr[20]['candidate'],label=m,color=COLORS[m],s=65)
    for ax,title in zip(axes,('Inner monitoring history ONLY','Outer: frozen main checkpoints ONLY')):
        ax.set(xlabel='M1',ylabel='M20',title=title);ax.legend()
    anchor_paths=[run/f'g4/fold_{f}/anchors.npz' for f in range(5)]
    save(fig,'03_pareto','dimensionless','inner all monitor points; star=best, square=last; outer no reselection',curve_paths+anchor_paths)
    # Deterministic ordinary diagnostic windows, plus worst cases recorded separately.
    selected=[]
    for s in (0,1):
        candidates=[]
        for fold in range(5):
            meta=read_json(run/f'g4/fold_{fold}/outer/windows.json')
            candidates += [(fold,i,m) for i,m in enumerate(meta) if m['scenario']==s]
        preferred=[x for x in candidates if s==1 and x[2]['start']==360]
        chosen=min(preferred or candidates,key=lambda x:(int(x[2]['trajectory']),x[2]['start']))
        f,i,meta=chosen;meta=dict(meta,selection_tag='fixed')
        selected.append((f,i,meta))
    # Post-hoc diagnostic examples are not used to reselect any checkpoint.
    worst_records=[]
    for method in ('T0','T1','T2'):
        candidate=[]
        for fold in range(5):
            b=rows(run/f'g4/fold_{fold}/outer/S0_rows.csv');c=rows(run/f'g4/fold_{fold}/outer/{method}_rows.csv')
            lookup={(r['trajectory'],r['start'],r['horizon']):float(r['j_common']) for r in b}
            for r in c:
                candidate.append((float(r['j_common'])-lookup[r['trajectory'],r['start'],r['horizon']],fold,r))
        delta,fold,r=max(candidate,key=lambda x:(x[0],-int(x[2]['trajectory']),-int(x[2]['start'])))
        meta=read_json(run/f'g4/fold_{fold}/outer/windows.json');i=next(i for i,m in enumerate(meta) if m['trajectory']==r['trajectory'] and m['start']==int(r['start']))
        selected.append((fold,i,dict(meta[i],selection_tag='worst_'+method)))
        worst_records.append(dict(method=method,fold=fold,trajectory=r['trajectory'],start=int(r['start']),horizon=int(r['horizon']),absolute_J_increase=delta,selection='posthoc largest absolute candidate-S0 J increase, not model selection'))
    write_csv(out/'worst_windows.csv',worst_records)
    write_json(out/'figure_windows.json',[dict(fold=f,index=i,metadata=m,selection=m['selection_tag']) for f,i,m in selected])
    direction=[]
    traces=[]
    for fold,index,meta in selected:
        folder=run/f'g4/fold_{fold}';norm=np.load(folder/'normalization.npz');data={}
        for m in COLORS:
            with np.load(folder/f'outer/{m}.npz') as z:
                data[m]={k:z[k][index] for k in ('prediction_n','target_n','force','internal','true_force','true_internal','control_n')}
        t=(meta['start']+np.arange(1,21))*.02
        truth=data['S0'];s=meta['scenario'];extra=[folder/f'outer/{m}.npz' for m in COLORS]
        fig,axes=plt.subplots(4,4,figsize=(14,10),sharex=True)
        for point in range(4):
            for col,(field,comp) in enumerate((('force',0),('force',1),('internal',0),('internal',1))):
                ax=axes[point,col];component=2*point+comp
                ax.plot(t,truth['true_'+field][:,component],color='black',lw=2,label='true')
                for m in COLORS:
                    ax.plot(t,data[m][field][:,component],color=COLORS[m],label=m,alpha=.8)
                changes=np.flatnonzero(np.any(np.abs(np.diff(data['S0']['control_n'],axis=0))>1e-12,axis=1))+1
                for change in changes:
                    ax.axvline((meta['start']+change)*.02,color='gray',alpha=.25,ls=':')
                ax.set_ylabel(f'P{point+1} '+('Fx' if comp==0 else 'Fy')+' (N)');ax.set_title(field if point==0 else '')
                if point==3:ax.set_xlabel('Time (s)')
        axes[0,0].legend(fontsize=7);fig.suptitle(f'D{s} {meta["selection_tag"]}: single 20-step window; t0={meta["start"]*.02:.2f}s',y=1.01)
        save(fig,f'04_force_D{s}_{meta["selection_tag"]}','N',meta['selection_tag']+'; not repeated rolling predictions; dotted lines mark input changes',extra)
        for m in COLORS:
            f=data[m]['force'].reshape(20,4,2)
            for h in range(20):
                for point in range(4):
                    mag=float(np.linalg.norm(f[h,point]));angle=None if mag<1e-6 else float(np.arctan2(f[h,point,1],f[h,point,0]))
                    direction.append(dict(scenario=s,trajectory=meta['trajectory'],start=meta['start'],method=m,time_s=float(t[h]),point=point+1,Fx_N=float(f[h,point,0]),Fy_N=float(f[h,point,1]),direction_rad=angle,near_zero_N=1e-6))
        raw={m:data[m]['prediction_n']*norm['relative_state47_scale']+norm['relative_state47_mean'] for m in COLORS}
        true=data['S0']['target_n']*norm['relative_state47_scale']+norm['relative_state47_mean']
        traces.append((fold,meta,t,data,raw,true))
    write_csv(out/'force_directions.csv',direction)
    trace_sources=[run/f'g4/fold_{fold}/outer/{m}.npz' for fold,meta,t,data,raw,true in traces[:2] for m in COLORS]
    trace_sources+=[run/f'g4/fold_{fold}/normalization.npz' for fold,meta,t,data,raw,true in traces[:2]]
    fig,axes=plt.subplots(7,2,figsize=(13,15),sharex='col')
    for col,(fold,meta,t,data,raw,true) in enumerate(traces[:2]):
        for row in range(7):
            ax=axes[row,col]
            def variable(x):
                if row==0:return x[:,2]
                if row<=4:return x[:,2]+x[:,21+3*(row-1)]
                if row==5:return np.linalg.norm(x[:,31:33],axis=1)
                return np.linalg.norm(x[:,33:35],axis=1)
            ax.plot(t,variable(true),'k',label='true')
            for m in COLORS:ax.plot(t,variable(raw[m]),label=m,color=COLORS[m])
            ax.set_ylabel(('Payload yaw rate (rad/s)' if row==0 else f'Vehicle{row} yaw rate (rad/s)') if row<5 else ('P1 displacement norm (m)' if row==5 else 'P1 relative speed (m/s)'))
            if row==0:ax.set_title(f'D{meta["scenario"]}; system yaw NOT available')
            if row==6:ax.set_xlabel('Time (s)')
    axes[0,0].legend(fontsize=7);save(fig,'05_motion','rad/s, m, m/s','same fixed D0/D1 windows; single vehicle yaw=relative yaw+payload yaw',trace_sources)
    from frozen import FrozenN6
    protocol=read_json(rev/'koopman_predict_v3s/config/protocol_v3s.json');frozen=FrozenN6(rev.parent,protocol);decoder=Decoder(frozen.build_planar_grasp_matrix)
    manifest_entries=rows(rev/N5/'data_manifest.csv')
    fig,axes=plt.subplots(4,2,figsize=(12,10),sharex='col')
    for col,(fold,meta,t,data,raw,true) in enumerate(traces[:2]):
        entry=next(e for e in manifest_entries if e['trajectory_id']==meta['trajectory']);p=frozen.resolved_params(int(entry['seed']),protocol)
        g3=true[:,31:47].reshape(20,4,4);gap=np.linalg.norm(g3[...,:2],axis=-1)-p.connector.free_play_m
        axes[0,col].plot(t,gap);axes[0,col].axhline(0,color='black');axes[0,col].axhline(p.connector.smoothing_width_m,color='gray',ls='--');axes[0,col].set_ylabel('True gap (m)')
        axes[1,col].step(t,(gap>0).sum(1),where='post');axes[1,col].set_ylabel('Active contacts (0-4)')
        jacd=[];jacv=[]
        for x in true:
            xt=torch.tensor(x,dtype=torch.float64,requires_grad=True)
            jac=torch.autograd.functional.jacobian(lambda v:decoder(v,p,entry['params_sha256'])[0],xt).detach().numpy()[:,31:47].reshape(8,4,4)
            jacd.append(np.linalg.norm(jac[:,:,:2]));jacv.append(np.linalg.norm(jac[:,:,2:]))
        axes[2,col].plot(t,jacd,label='dF/dd N/m');axes[2,col].plot(t,jacv,label='dF/dv N s/m');axes[2,col].set_ylabel('Separate Jacobian block norms');axes[2,col].legend(fontsize=7)
        for m in COLORS:axes[3,col].plot(t,np.linalg.norm(data[m]['force']-data[m]['true_force'],axis=1),label=m,color=COLORS[m])
        axes[3,col].set(ylabel='Force error norm (N)',xlabel='Time (s)');axes[0,col].set_title(f'D{meta["scenario"]}; derivatives at kinks are one branch')
    axes[3,0].legend();save(fig,'06_contact','m, contact count, N/m, N s/m, N','true-state local Jacobian; G1 one-sided diagnostics cover kinks',trace_sources+[rev/N5/'data_manifest.csv'])
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for m in ('T0','T1','T2'):
        for fold in range(5):
            ck=torch.load(run/f'g4/fold_{fold}/{m}/last.pt',map_location='cpu',weights_only=False);curve=ck['curve'];steps=[c['step'] for c in curve]
            if not curve:continue
            gs=np.array([c['inner_g'] for c in curve]);ls=np.array([c['lambda_values'] for c in curve]);label=m if fold==0 else None
            axes[0,0].plot(steps,np.maximum(gs,0).max(1),color=COLORS[m],alpha=.45,label=label)
            axes[0,1].plot(steps,(gs>0).sum(1),color=COLORS[m],alpha=.45,label=label)
            axes[1,0].plot(steps,(ls>=20).sum(1),color=COLORS[m],alpha=.45,label=label)
            a=np.load(run/f'g4/fold_{fold}/anchors.npz')['inner'];m1=a[:,0,0].mean()*(1+gs[:,0]+.03);m20=np.mean(a[:,3,0][None,:]+(gs[:,3:51].reshape(-1,12,4)[:,:,3]+.03)*np.maximum(a[:,3,0],.02)[None,:],1)
            axes[1,1].plot(steps,m1,color=COLORS[m],alpha=.45,ls='--',label=(m+' M1') if fold==0 else None);axes[1,1].plot(steps,m20,color=COLORS[m],alpha=.45,label=(m+' M20') if fold==0 else None)
    for ax,title in zip(axes.flat,('Maximum positive inner violation','Number of violated constraints','Saturated fit multipliers','Inner M1 dashed / M20 solid')):
        ax.set(title=title,xlabel='Optimization step');ax.legend(fontsize=7)
    save(fig,'07_constraints','dimensionless / counts','all five folds; multipliers update from fit, selection constraints from inner',curve_paths+anchor_paths)
    fig,axes=plt.subplots(2,2,figsize=(11,8));methods=list(COLORS)
    axes[0,0].bar(methods,[times[m]['parameter_count']['trainable'] if m!='S0' else 0 for m in methods]);axes[0,0].set_title('Trainable residual parameters')
    hours=[]
    for m in methods:
        hours.append(0 if m=='S0' else sum(read_json(run/f'g4/fold_{f}/training_complete.json')['methods'][m]['elapsed_s'] for f in range(5))/3600)
    axes[0,1].bar(methods,hours);axes[0,1].set(title='Formal training time (5 folds)',ylabel='GPU wall hours incl. monitoring')
    x=np.arange(4);axes[1,0].bar(x-.2,[times[m]['cuda']['median_ms'] for m in methods],.4,label='GPU median');axes[1,0].bar(x+.2,[times[m]['cuda']['p99_ms'] for m in methods],.4,label='GPU P99');axes[1,0].set_xticks(x,methods);axes[1,0].axhline(1,color='gray',ls='--');axes[1,0].axhline(2,color='gray',ls=':');axes[1,0].set_ylabel('batch1 20-step + force decode (ms)');axes[1,0].legend()
    axes[1,1].bar(methods,[times[m]['cpu']['median_ms'] for m in methods]);axes[1,1].axhline(5,color='gray',ls='--');axes[1,1].set(title=f'CPU median; smoke peak GPU {read_json(run/"g3/cost.json")["peak_gpu_bytes"]/2**30:.2f} GiB',ylabel='ms, one CPU thread')
    save(fig,'08_cost','parameters, GPU wall hours, ms, GiB','timing fold0 frozen checkpoint; warmup200 measure1000 with CUDA synchronization',[run/'g3/cost.json']+[run/f'g4/fold_{f}/training_complete.json' for f in range(5)])
    write_json(out/'figure_manifest.json',manifest)
