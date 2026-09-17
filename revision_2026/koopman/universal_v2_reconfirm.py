"""Strict G6 recovery confirmation after a protocol-path versioning error."""

from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import stat
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE/"universal_v2"
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import universal_v2_modules as m
import universal_v2_external_stats as es


def trace(profile,trace_id,steps):
    pi=("iid","burst","delay","dos").index(profile);rng=np.random.default_rng(1080000+100*pi+trace_id)
    mask=np.zeros((steps,8),np.int8);delay=np.zeros((steps,4),np.int16)
    if profile=="iid":mask=(rng.random((steps,8))<.25).astype(np.int8)
    elif profile=="burst":
        for begin in (int(.18*steps),int(.48*steps),int(.76*steps)):mask[begin:min(steps,begin+75)]=1
        mask|=(rng.random((steps,8))<.05).astype(np.int8)
    elif profile=="delay":delay=rng.integers(3,9,size=(steps,4),dtype=np.int16)
    else:mask[int(.25*steps):int(.36*steps)]=1;mask[int(.62*steps):int(.74*steps)]=1
    drop=np.maximum(mask[:,0::2],mask[:,1::2]);aoi=delay.copy()
    for k in range(1,steps):aoi[k]=np.where(drop[k]>0,aoi[k-1]+1,delay[k])
    network=np.c_[drop.max(1),delay.max(1),aoi.max(1),1-np.minimum(aoi.max(1)/10,1)]
    return mask,aoi,network.astype(np.float32)


def overlay(source_path,output,profile,trace_id):
    with np.load(source_path,allow_pickle=False) as source:
        arrays={k:np.asarray(source[k]) for k in source.files if k!="metadata_json"};meta=json.loads(str(source["metadata_json"].item()))
    mask,aoi,network=trace(profile,trace_id,len(arrays["u1_four"]));arrays["network"]=network;arrays["network_mask"]=mask;arrays["network_aoi4"]=aoi
    meta.update({"confirm_kind":"network-recovery","network_profile":profile,"network_trace_id":trace_id,"physical_truth_source":source_path.name,"plant_truth_unchanged":True})
    np.savez_compressed(output,**arrays,metadata_json=np.asarray(json.dumps(meta,ensure_ascii=False)))
    return {"file":output.name,"sha256":m.uv2.sha256(output),"kind":"network","profile":profile,"trace_id":trace_id,"physical_truth_source":source_path.name,"steps":len(arrays["u1_four"])}


def load_rows(stage,kind):
    manifest=json.loads((stage/"manifest.json").read_text(encoding="utf-8"));items=[r for r in manifest["physical"] if r["kind"]==kind] if kind!="network" else manifest["network"]
    rows=[]
    for item in items:
        path=stage/"trajectories"/item["file"]
        if m.uv2.sha256(path)!=item["sha256"]:raise RuntimeError(f"hash mismatch {path}")
        with np.load(path,allow_pickle=False) as src:
            arrays={k:np.asarray(src[k],dtype=np.float64) for k in m.cp.ARRAY_KEYS}
            for k in ("network_mask","network_aoi4"):
                if k in src.files:arrays[k]=np.asarray(src[k])
            meta=json.loads(str(src["metadata_json"].item()))
        meta.update(item);rows.append({"meta":meta,"arrays":arrays,"path":path})
    return rows


def generate():
    stage=OUT/"d3_recovery";complete=stage/"complete.json"
    if complete.exists():return stage
    data=stage/"trajectories";data.mkdir(parents=True,exist_ok=True)
    tasks=m.parameter_tasks();scales=m.uv2.v1.compare_gen.train_scales(HERE/"k2"/"data_full")
    scan=m.uv2.v1.load_scan_rows(m.uv2.V1_OUT/"t1"/"force_coverage_scan.csv");cands=m.uv2.v1.coverage_candidates(scan);pending=[]
    for si,scene in enumerate(m.uv2.v1.SCENES):
        for offset in range(20):
            seed=1060000+1000*si+offset;job={"scenario":scene,"physical_scene":scene,"scene_index":si,"split":"reconfirm","offset":offset,"seed":seed,"traj_id":offset,"external":False,"parameter_external":False,"network_profile":"clean","network_trace_id":"clean"}
            tier=None if scene in ("E0","E1") else ("L1","L2","L3")[(offset+si)%3];config=None if tier is None else cands[tier][(offset+si)%len(cands[tier])];job["coverage_tier"]="nominal" if tier is None else tier
            pending.append((job,config,scales,None,str(data/f"internal_{scene}_{seed}.npz")))
    for index,task in enumerate(tasks[30:38]):
        for scene,off in (("E1",0),("E2",1),("E3",2)):
            seed=1070000+10*index+off;job={"scenario":scene,"physical_scene":scene,"split":"reconfirm-external","seed":seed,"traj_id":seed,"external":True,"parameter_external":True,"network_profile":"clean","network_trace_id":"clean"}
            pending.append((job,None,scales,task,str(data/f"external_task{int(task['task_id']):02d}_{scene}_{seed}.npz")))
    recovered=OUT/"protocol_v2_d2_frozen.md";expected="BB745366E5D27BB3CF6B3E0084ABD8DE484F1971FD35617342C9739BEA3C7025"
    if not recovered.exists() or m.uv2.sha256(recovered)!=expected:raise RuntimeError("recovered D2 protocol bytes unavailable")
    freeze={"status":"frozen_before_recovery_generation","reason":"strict G6 recovery","protocol_sha256":m.uv2.sha256(OUT/"protocol_v2.md"),"recovered_D2_protocol_sha256":expected,
            "script_sha256":m.uv2.sha256(Path(__file__).resolve()),"candidate_files":m.freeze_candidates(),"jobs":[{"file":Path(x[4]).name,"seed":x[0]["seed"]} for x in pending],"network_seeds":[1080000+100*i+j for i in range(4) for j in range(10)]}
    m.write_json(stage/"freeze.json",freeze);done=[];fail=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(m.d2_physical_job,*x):x for x in pending}
        for i,future in enumerate(as_completed(futures),1):
            try:done.append(future.result())
            except Exception as exc:fail.append({"file":Path(futures[future][4]).name,"error":repr(exc)})
            print(f"D3 [{i:03d}/184] failures={len(fail)}",flush=True)
    done.sort(key=lambda r:(r["kind"],r["file"]));internal=[r for r in done if r["kind"]=="internal"];nets=[]
    if not fail and len(internal)==160:
        sources=sorted(internal,key=lambda r:r["file"])
        for i,(profile,j) in enumerate((p,j) for p in ("iid","burst","delay","dos") for j in range(10)):
            nets.append(overlay(data/sources[i]["file"],data/f"network_{profile}_{j:02d}.npz",profile,j));print(f"D3 network [{i+1:02d}/40]",flush=True)
    m.write_json(stage/"manifest.json",{"planned":{"internal":160,"external":24,"network":40},"physical":done,"network":nets,"failures":fail})
    accepted=not fail and len(internal)==160 and len([r for r in done if r["kind"]=="external"])==24 and len(nets)==40 and all(r["finite"] and r["ultimate_exceeded_steps"]==0 for r in done)
    m.write_json(complete,{"accepted":accepted,"status":"pass" if accepted else "fail","manifest_sha256":m.uv2.sha256(stage/"manifest.json"),"freeze_sha256":m.uv2.sha256(stage/"freeze.json")})
    if accepted:
        for path in data.glob("*.npz"):
            try:path.chmod(stat.S_IREAD)
            except OSError:pass
    return stage


def evaluate(stage):
    out=OUT/"t7_recovery";complete=out/"complete.json"
    if complete.exists():return
    _,norms,_,models=m.context();internal=load_rows(stage,"internal");external=load_rows(stage,"external");network=load_rows(stage,"network")
    cdev=json.loads((OUT/"t5"/"c_results.json").read_text(encoding="utf-8"));adev=json.loads((OUT/"t5"/"adaptation_results.json").read_text(encoding="utf-8"));results={};stats={}
    for name in m.amend_g2():
        model=models[name]
        with np.load(OUT/"t3"/"models"/f"{name}.npz",allow_pickle=False) as src:head={k:np.asarray(src[k]) for k in ("coef","feature_mean","feature_std","clip")}
        p0=m.evaluate_confirm_variant(model,name,internal,norms,"P0");f2=m.evaluate_confirm_variant(model,name,internal,norms,"F2",head=head)
        p=cdev[name]["selected_period"];cm=m.evaluate_confirm_variant(model,name,internal,norms,"C",period=None if p=="infinity" else int(p))
        with np.load(OUT/"t5"/f"A-{name}.npz",allow_pickle=False) as src:basis=np.asarray(src["basis"]);prior=float(src["prior"])
        condition=adev[name]["best_adaptive_condition"];seconds=float(condition.split("-")[1][:-1]) if condition.startswith("A1-") else 1.
        e0=m.eval_task_adaptation(model,external,norms,set(range(30,38)),None,prior,0.);ea=m.eval_task_adaptation(model,external,norms,set(range(30,38)),basis,prior,seconds)
        b,c=es.per_trajectory(model,external,norms,basis,prior,seconds);astat=m.paired_bootstrap(b,c);astat["condition"]=condition
        net={}
        for profile in ("iid","burst","delay","dos"):
            subset=[r for r in network if r["meta"]["profile"]==profile];net[profile]={"unprotected":m.evaluate_network(model,subset,norms,False),"protected_state_propagation":m.evaluate_network(model,subset,norms,True)}
        results[name]={"internal":{"P0":p0,"F2-diagnostic":f2,"C-selected":cm},"external":{"A0-zero":e0,condition:ea},"network":net};stats[name]={"A":astat,"F2":m.paired_bootstrap(p0["per_trajectory_J"],f2["per_trajectory_J"]),"C":m.paired_bootstrap(p0["per_trajectory_J"],cm["per_trajectory_J"])}
        print(f"D3 eval {name}: P0={p0['J_pred']:.4g} F2={f2['J_pred']:.4g} A0={e0['J_pred']:.4g} A={ea['J_pred']:.4g}",flush=True)
    # Holm separately for fixed internal and external families.
    for family,key in (("external","A"),("internal_F","F2"),("internal_C","C")):
        tests=sorted((stats[n][key]["bootstrap_p"],n) for n in stats);running=0
        for i,(p,n) in enumerate(tests):running=max(running,min(1,(len(tests)-i)*p));stats[n][key]["holm_p"]=running
    epass=[n for n in stats if stats[n]["A"]["mean_improvement"]>=.08 and stats[n]["A"]["ci95_low"]>0 and stats[n]["A"]["holm_p"]<.05]
    ipass=[]
    for n in stats:
        for key in ("F2","C"):
            s=stats[n][key];base=results[n]["internal"]["P0"];cand=results[n]["internal"]["F2-diagnostic" if key=="F2" else "C-selected"]
            if s["mean_improvement"]>=.08 and s["ci95_low"]>0 and s["holm_p"]<.05 and cand["divergence_rate"]<=base["divergence_rate"]:ipass.append(f"{n}|{key}")
    m.write_json(out/"confirm_results.json",results);m.write_json(out/"paired_statistics.json",stats)
    gates=read_json(OUT/"universality_gates.json") if False else json.loads((OUT/"universality_gates.json").read_text(encoding="utf-8"));gates.update({"evidence_version":"D3_recovery","D2_status":"invalid_protocol_path_changed_after_view","internal_relative_candidates":ipass,"external_adaptation_candidates":epass,"absolute_deployment_candidates":[],"closed_loop_official":[]})
    m.write_json(OUT/"universality_gates_final.json",gates);m.write_json(complete,{"status":"complete","evaluated_once":True,"internal_passing":ipass,"external_passing":epass,"results_sha256":m.uv2.sha256(out/"confirm_results.json"),"gates_sha256":m.uv2.sha256(OUT/"universality_gates_final.json")})
    m.uv2.append_log("W0074","G6恢复确认",[f"原D2降级为协议路径变更后的审计集；全新D3完成160 internal+24 external+40 network并一次性评估。",f"D3 internal通过={ipass}；external适应通过={epass}；正式部署候选仍为0。",f"结果hash={m.uv2.sha256(out/'confirm_results.json')}；最终门hash={m.uv2.sha256(OUT/'universality_gates_final.json')}。"])


if __name__=="__main__":
    stage=generate();
    if not json.loads((stage/"complete.json").read_text(encoding="utf-8"))["accepted"]:raise SystemExit(2)
    evaluate(stage)
