"""One detached, gated queue for the remaining KC experiments. No external service."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import threading
import time
import traceback

os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "src"))

import numpy as np
import torch
import guard_core as gc
import guard_training as gt
import refine_loss
from frozen import FrozenN6
from background_core import (H, METHODS, NAMES, CheckedAccess, build_data, complete_quality,
    curriculum_trigger, digest_arrays, evaluate_bundle, nominate, pure, read_json, residual_mse_loss,
    rows, select_gamma, sha, state_weights_equal, write_csv, write_json, hierarchy)

class StopRun(Exception):
    def __init__(self, message, code=22):
        super().__init__(message)
        self.code = code


class RunLock:
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def __enter__(self):
        import msvcrt
        self.file = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.file.close()
            raise StopRun("another background queue holds the project lock", 23)
        return self

    def __exit__(self, *args):
        import msvcrt
        self.file.seek(0)
        msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()


class Queue:
    def __init__(self, run, project, taskbook):
        self.run = Path(run).resolve()
        self.project = Path(project).resolve()
        self.rev = self.project / "revision_2026"
        self.taskbook = Path(taskbook).resolve()
        self.parent = self.rev / "koopman_predict_v3v_results/runs/20260904_224212_KC_R01"
        self.history = self.rev / "koopman_predict_v3t_results/runs/20260904_142331_KG_R02"
        n5 = "20260901_214725_AUTO_PREDICT_AUTO_R04_R01"
        self.manifest = self.rev / f"koopman_predict_auto_results/runs/{n5}/n5/data_manifest.csv"
        self.cache = self.rev / f"koopman_predict_auto_data/{n5}/n5_cache11"
        self.fold_path = self.history / "g0/fold_manifest.csv"
        self.started = time.monotonic()
        self.deadline = self.started + 12*3600
        self.current = "启动检查"
        self.done = threading.Event()
        self.run.mkdir(parents=True, exist_ok=True)
        self.entries = rows(self.manifest)
        self.folds = rows(self.fold_path)
        for e in self.entries:
            e["cache_path"] = str(self.cache / Path(e["cache_path"]).name)
        self.protocol = read_json(SOURCE / "config/protocol_v3s.json")
        self.frozen = FrozenN6(self.project, self.protocol)
        self.decoder = gc.Decoder(self.frozen.build_planar_grasp_matrix)
        self.guard = CheckedAccess(self.entries, self.folds, self.run, rows(self.cache / "cache11_manifest.csv"))
        self.contexts = {}
        self.calibrations = []
        self.source_manifest = self.code_identity()
        self.restore_budget()

    def restore_budget(self):
        p = self.run / "progress.json"
        # Reserve 90 min for the parent run (22:42--00:10), including idle and diagnostics.
        self.previous_s = float(read_json(p).get("elapsed_s",5400)) if p.exists() else 5400.
        self.deadline -= self.previous_s

    def code_identity(self):
        return {str(p.relative_to(SOURCE)):sha(p) for p in sorted(SOURCE.rglob("*"))
                if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in p.parts}

    def event(self, message, **extra):
        self.current = message
        rec = dict(time=dt.datetime.now().astimezone().isoformat(), pid=os.getpid(), stage=message, **extra)
        with (self.run / "events.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps(rec,ensure_ascii=False,allow_nan=False)+"\n")
        line = f"\n- {rec['time']} | {self.run.name} | {message} | {json.dumps(extra,ensure_ascii=False)}\n"
        for p in (self.run/"work_log.md", self.rev/"koopman_work_log.md"):
            with p.open("a",encoding="utf-8") as f:
                f.write(line)
        print(json.dumps(rec,ensure_ascii=False),flush=True)
        self.heartbeat()

    def heartbeat(self):
        write_json(self.run/"progress.json",dict(status="RUNNING",stage=self.current,pid=os.getpid(),
            host=socket.gethostname(), time=dt.datetime.now().astimezone().isoformat(),
            elapsed_s=self.previous_s+time.monotonic()-self.started))

    def pulse(self):
        while not self.done.wait(15):
            self.heartbeat()

    def resource_gate(self):
        if time.monotonic()>=self.deadline:
            raise StopRun("12小时累计预算用完，保存进度后停止",23)
        if shutil.disk_usage(self.rev).free < 60*1024**3:
            raise StopRun("D盘剩余空间不足60 GiB",23)
        if self.code_identity()!=self.source_manifest:
            raise StopRun("运行期间源码发生变化，拒绝继续",22)

    def prepare(self):
        self.resource_gate()
        if socket.gethostname().upper() != "DESKTOP-9IUUGEO":
            raise StopRun("wrong workstation")
        checks = dict(manifest=sha(self.manifest)=="B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9",
                      folds=sha(self.fold_path)=="2DBAF6D83B14594C444234E05EC03638C0FE66935F17F8C5A7D82A0E468D1AC0")
        if not all(checks.values()):
            raise StopRun("data split identity differs")
        identity = dict(source=self.source_manifest,taskbook_sha=sha(self.taskbook),checks=checks,
                        project=str(self.project),parent_run=str(self.parent),host=socket.gethostname(),
                        python=sys.executable,torch=torch.__version__,cuda=torch.version.cuda)
        p = self.run/"identity.json"
        if p.exists() and read_json(p)!=identity:
            raise StopRun("resume identity differs")
        write_json(p,identity)
        if not (self.run/"taskbook_snapshot.md").exists():
            shutil.copy2(self.taskbook,self.run/"taskbook_snapshot.md")
        write_json(self.run/"protocol_snapshot.json",dict(
            version="KC-R3-background",physical_parameter_protocol=self.protocol,
            controls=11,states=47,modes=16,horizons=H,gammas=[0,.25,.5,.75,1],
            methods=METHODS,pilot_seeds=[996100,996101,996102],formal_seed="997100+100*repeat+fold",
            warm_steps=2000,formal_steps=6000,curriculum_switch=1000,batch=256,
            precision_limits=dict(short=.03,scenario=.03,force=.05,tail=.03,max_state=20),
            gpu_budget_hours=12,minimum_free_GiB=60))
        write_json(self.run/"historical_deviations.json",dict(
            old_curriculum="RMSE, excluded from MSE comparison",old_gamma="double scaling in KC3 h1 only",
            old_log="KC stages appended to historical access log; preserved",
            historical_control11="672 caches previously derived; metadata exposure retained; this queue only train/R3",
            data_claim="Repeatedly used development pool; not independent blind testing"))
        self.event("启动检查通过", source_sha=sha(p))

    def smoke(self):
        full=self.context(0)
        chosen=[]
        for scenario in range(12):
            ee=[e for e in full["fit_e"] if e["scenario"]==f"D{scenario}"]
            families=sorted({e["base_family_id"] for e in ee})[:2]
            chosen += [e for e in ee if e["base_family_id"] in families]
        ctx=dict(full)
        ctx["fit"]=build_data(chosen,ctx["norm"],self.guard,0,"optimize",ctx["resolver"],self.decoder,"cuda")
        ctx["af"]=evaluate_bundle(ctx["anchor"],ctx["fit"])
        warm_path=self.train_unit(ctx,996900,"warm",None,self.run/"smoke/warm",steps=200)
        _,warm=self.load_model(warm_path,ctx,996900)
        for method in METHODS:
            self.train_unit(ctx,996900,method,warm["model"],self.run/f"smoke/{method}",steps=600,sampler_seed=1046900)
        self.event("三种方法短训练检查通过",windows=len(ctx["fit"].meta),warm_steps=200,method_steps=600)

    def context(self,fold):
        if fold in self.contexts:
            return self.contexts[fold]
        self.event("准备训练与内部验证数据",fold=fold)
        def es(role):
            ids={r["trajectory"] for r in self.folds if int(r["fold"])==fold and r["role"]==role}
            return [e for e in self.entries if e["trajectory_id"] in ids]
        fit_e, inner_e = es("fit"),es("inner")
        if not fit_e or not inner_e:
            raise StopRun("empty fold")
        norm=gc.fit_normalization(fit_e,self.guard,fold,input_dim=11)
        if "control11_mean" not in norm or np.shape(norm["control11_mean"])!=(11,):
            raise StopRun("invalid normalization schema")
        s0=gc.fit_s0(fit_e,norm,self.guard,fold)
        # Reuse the exact historical backbone for fold0, not a fresh floating-point solve.
        # Validate against the same fit-only ridge equations before importing the coefficients.
        if fold==0:
            from evaluation_v2 import design_matrix
            parent_path=self.parent/"kc4/seed0_aligned/last.pt"
            state=torch.load(parent_path,map_location="cpu",weights_only=False)["model"]
            frozen_coeff=np.r_[state["A0"].numpy().T,state["B0"].numpy().T,state["b0"].numpy()[None]]
            gram=np.zeros((59,59));cross=np.zeros((59,47))
            for entry in fit_e:
                x,y,_=design_matrix(self.guard.load(entry,fold,"S0"),"S0","M0_FIXED_LINEAR",norm)
                gram+=x.T@x;cross+=x.T@y
            reg=np.eye(59)*.01;reg[-1,-1]=0;gram+=reg
            def backward_error(c):
                return float(np.linalg.norm(gram@c-cross)/(np.linalg.norm(gram)*np.linalg.norm(c)+np.linalg.norm(cross)))
            evidence=dict(parent_checkpoint=str(parent_path),parent_sha=sha(parent_path),
                frozen_backward_error=backward_error(frozen_coeff),refit_backward_error=backward_error(s0["coefficients"]),
                coefficient_max_abs_difference=float(np.max(np.abs(frozen_coeff-s0["coefficients"]))),
                regularized_condition=float(s0["condition_number"]),
                decision="use the existing exact frozen backbone after verifying the same fit-only ridge equations")
            if evidence["frozen_backward_error"]>1e-12 or not np.isfinite(frozen_coeff).all():
                raise StopRun("parent backbone does not solve the registered fit equations")
            write_json(self.run/"folds/fold0/backbone_import.json",evidence)
            s0["coefficients"]=frozen_coeff
        resolver=lambda e:self.frozen.resolved_params(int(e["seed"]),self.protocol)
        fit=build_data(fit_e,norm,self.guard,fold,"optimize",resolver,self.decoder,"cuda")
        inner=build_data(inner_e,norm,self.guard,fold,"monitor",resolver,self.decoder,"cuda")
        anchor=pure(s0["coefficients"])
        folder=self.run/f"folds/fold{fold}"
        folder.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(folder/"normalization.npz",**norm)
        np.savez_compressed(folder/"s0.npz",coefficients=s0["coefficients"])
        af=evaluate_bundle(anchor,fit,folder/"baseline_fit.npz",dict(kind="pure11",fold=fold))
        ai=evaluate_bundle(anchor,inner,folder/"baseline_inner.npz",dict(kind="pure11",fold=fold))
        oracle=[]
        for role,ee,data in (("fit",fit_e,fit),("inner",inner_e,inner)):
            purpose="fit_monitor" if role=="fit" else "monitor"
            for e in ee:
                cache=self.guard.load(e,fold,purpose)
                with self.guard.context(fold,purpose):
                    if sha(e["raw_path"])!=e["raw_file_sha256"]:
                        raise StopRun("raw source hash mismatch")
                    with np.load(e["raw_path"],allow_pickle=False) as z:
                        req=z["requested_control4x2"][1:,:,0]
                        acc=z["base_acceleration_mps2"][1:]
                diff=float(np.max(np.abs(cache["control11"][:,7:]+acc[:,None]-req)))
                if diff>1e-12:
                    raise StopRun("input reconstruction failed")
                oracle.append(dict(trajectory=e["trajectory_id"],role=role,input_error=diff))
            with torch.no_grad():
                f,inn=data.physical(data.y,np.arange(len(data.meta)))
            ferr=float((f-data.force).abs().max())
            ierr=float((inn-data.internal).abs().max())
            if ferr>1e-8 or ierr>1e-8:
                raise StopRun(f"physical oracle failed {ferr}/{ierr}")
            oracle.append(dict(role=role,force_oracle_N=ferr,internal_oracle_N=ierr))
        write_json(folder/"oracle.json",oracle)
        ctx=dict(fold=fold,fit=fit,inner=inner,fit_e=fit_e,inner_e=inner_e,norm=norm,s0=s0,
                 anchor=anchor,af=af,ai=ai,outer_e=es("outer"),resolver=resolver,
                 norm_sha=digest_arrays(norm),s0_sha=digest_arrays(dict(coeff=s0["coefficients"])))
        self.contexts[fold]=ctx
        return ctx

    def load_model(self,path,ctx,seed):
        payload=torch.load(path,map_location="cpu",weights_only=False)
        model=gc.new_model(ctx["s0"]["coefficients"],seed,input_dim=11).cuda()
        frozen={k:v.clone().cpu() for k,v in model.state_dict().items() if k in ("A0","B0","b0")}
        model.load_state_dict(payload["model"])
        if not all(torch.equal(model.state_dict()[k].cpu(),v) for k,v in frozen.items()):
            raise StopRun("checkpoint frozen S0 differs: "+str(path))
        return model,payload

    def audit_pilot(self,ctx):
        self.event("复核九组已完成训练")
        imported=[]
        for si,seed in enumerate((996100,996101,996102)):
            sample_hashes=[]
            early=[]
            for method in METHODS:
                folder=self.parent/f"kc4/seed{si}_{method}"
                _,last=self.load_model(folder/"last.pt",ctx,seed)
                if last["step"]!=6000 or [c["step"] for c in last["curve"]]!=list(range(500,6001,500)):
                    raise StopRun("pilot incomplete")
                sample_hashes.append(last["sample_hash"])
                _,best=self.load_model(folder/"best.pt",ctx,seed)
                if best["step"]!=last["best_step"]:
                    raise StopRun("best identity differs")
                if method in ("fixed_guard","adaptive_guard"):
                    _,p=self.load_model(folder/"step_00500.pt",ctx,seed)
                    early.append(p["model"])
                imported.append(dict(seed=seed,method=method,path=str(folder/"best.pt"),
                    sha=sha(folder/"best.pt"),step=best["step"],sample_hash=last["sample_hash"],
                    status="REUSE_FOR_REEVALUATION",historical_preflight="not fully performed before original training"))
            if len(set(sample_hashes))!=1 or not state_weights_equal(*early):
                raise StopRun("pilot fairness witness failed")
        write_csv(self.run/"imported_units.csv",imported)
        return imported

    def calibrate(self,path,ctx,seed,method,folder):
        self.resource_gate()
        self.event("调整残差修正强度",fold=ctx["fold"],seed=seed,method=method)
        model,payload=self.load_model(path,ctx,seed)
        identity=dict(checkpoint=str(path),checkpoint_sha=sha(path),step=payload["step"],seed=seed,
                      method=method,fold=ctx["fold"],norm_sha=ctx["norm_sha"],s0_sha=ctx["s0_sha"])
        gamma_rows=[]
        saved=model.E.detach().clone()
        for gamma in (0.,.25,.5,.75,1.):
            candidate=copy.deepcopy(model)
            with torch.no_grad():
                candidate.E.copy_(gamma*saved)
            bundle=evaluate_bundle(candidate,ctx["inner"],Path(folder)/f"gamma_{gamma:.2f}.npz",dict(identity,gamma=gamma))
            if gamma==0. and not np.allclose(bundle["pred"],ctx["ai"]["pred"],rtol=0,atol=1e-10):
                raise StopRun("gamma=0 does not recover pure baseline")
            quality=complete_quality(bundle,ctx["ai"])
            write_json(Path(folder)/f"gamma_{gamma:.2f}_quality.json",quality)
            if not quality["finite"]:
                raise StopRun("nonfinite prediction during calibration",20)
            gamma_rows.append(dict(gamma=gamma,protected=quality["passed"],finite=quality["finite"],
                                   m20=quality["m20"],i20=quality["i20"]))
        result=dict(identity,raw=gamma_rows[-1],selected=select_gamma(gamma_rows),grid=gamma_rows)
        write_json(Path(folder)/"selection.json",result)
        return result

    def train_unit(self,ctx,seed,method,warm_state,folder,steps=6000,sampler_seed=None):
        self.resource_gate()
        folder=Path(folder)
        identity=dict(source=self.source_manifest,fold=ctx["fold"],seed=seed,phase=method,
                      norm_sha=ctx["norm_sha"],s0_sha=ctx["s0_sha"],run=self.run.name,steps=steps,
                      sampler_seed=seed if sampler_seed is None else sampler_seed)
        receipt=folder/"complete.json"
        if receipt.exists():
            done=read_json(receipt)
            if done["identity"]!=identity or done["last_sha"]!=sha(folder/"last.pt"):
                raise StopRun("completed unit identity mismatch")
            return folder/("last.pt" if method=="warm" else "best.pt")
        self.event("训练",fold=ctx["fold"],seed=seed,method=method,total_steps=steps)
        model=gc.new_model(ctx["s0"]["coefficients"],seed,input_dim=11).cuda()
        if warm_state is not None:
            model.load_state_dict(warm_state)
        resume=folder/"last.pt" if (folder/"last.pt").exists() else None
        af=torch.as_tensor(ctx["af"]["stats"],device="cuda")
        ai=torch.as_tensor(ctx["ai"]["stats"],device="cuda")
        def diagnostics(current,step):
            self.resource_gate()
            info=dict(step=step,selection_eligible=step>0 and step%500==0)
            if step in (0,100,250,750):
                fs,_=gc.evaluate(current,ctx["fit"])
                ins,_=gc.evaluate(current,ctx["inner"])
                info.update(fit=fs.cpu().tolist(),inner=ins.cpu().tolist())
            if step in (0,500,2500,6000):
                probe=copy.deepcopy(current)
                rng=np.random.Generator(np.random.PCG64(996800))
                params=list(probe.named_parameters())
                pairs=[]
                for _ in range(3):
                    ix=ctx["fit"].sample(rng,0)
                    err,_,_=refine_loss.batch_errors(probe,ctx["fit"],ix)
                    stats=gc.balanced_mean(err,ctx["fit"].scenario[ix])
                    ga=torch.autograd.grad(stats[:,0,0].mean(),[p for _,p in params],allow_unused=True,retain_graph=True)
                    gb=torch.autograd.grad(stats[:,3,0].mean(),[p for _,p in params],allow_unused=True)
                    row={}
                    for group in ("encoder_and_E","propagation"):
                        use=[i for i,(n,_) in enumerate(params) if ((n=="E" or n.startswith("encoder."))==(group=="encoder_and_E"))]
                        a=torch.cat([(torch.zeros_like(params[i][1]) if ga[i] is None else ga[i]).flatten() for i in use])
                        b=torch.cat([(torch.zeros_like(params[i][1]) if gb[i] is None else gb[i]).flatten() for i in use])
                        na=float(a.norm());nb=float(b.norm())
                        row[group]=dict(one_step_norm=na,multistep_norm=nb,cosine=None if min(na,nb)<=1e-12 else float(torch.dot(a,b)/(na*nb)))
                    pairs.append(row)
                info["gradient_diagnostics"]=pairs
            write_json(folder/f"diagnostics/step_{step:05d}.json",info)
        result=gt.train_phase(model,ctx["fit"],ctx["inner"],af,ai,method,
            seed if sampler_seed is None else sampler_seed,identity,folder,max_steps=steps,
            resume=resume,min_steps=steps,patience=steps+1,monitor_every=500,
            deadline=self.deadline,anchor_scale_m20=float(af[:,3,0].mean()),
            diagnostic_callback=None if method=="warm" else diagnostics)
        if result["step"]!=steps or result["status"]!="COMPLETE":
            raise StopRun("训练已保存，等待资源恢复: "+result["status"],23)
        write_json(receipt,dict(identity=identity,last_sha=sha(folder/"last.pt"),
                               best_step=result["best_step"],elapsed_s=result["elapsed_s"]))
        self.event("单组训练完成",fold=ctx["fold"],seed=seed,method=method,steps=result["step"])
        return folder/("last.pt" if method=="warm" else "best.pt")

    def pilot_and_selection(self):
        ctx=self.context(0)
        imported=self.audit_pilot(ctx)
        for unit in imported:
            self.calibrations.append(self.calibrate(unit["path"],ctx,unit["seed"],unit["method"],
                self.run/f"pilot/seed{unit['seed']}/{unit['method']}"))
        selected=nominate(self.calibrations,list(METHODS))
        curves=[torch.load(self.parent/f"kc4/seed{i}_fixed_guard/last.pt",map_location="cpu",weights_only=False)["curve"] for i in range(3)]
        trigger=curriculum_trigger(selected is None,curves)
        write_json(self.run/"curriculum_trigger.json",trigger)
        methods=list(METHODS)
        if trigger["triggered"]:
            methods.append("residual_curriculum")
            self.event("满足条件，开始正确均方误差的分段训练")
            for si,seed in enumerate((996100,996101,996102)):
                _,warm=self.load_model(self.parent/f"kc4/seed{si}_warm/last.pt",ctx,seed)
                if warm["step"]!=2000:
                    raise StopRun("wrong warm budget")
                path=self.train_unit(ctx,seed,"residual_curriculum",warm["model"],
                    self.run/f"pilot/seed{seed}/residual_curriculum/train",sampler_seed=seed+50000)
                self.calibrations.append(self.calibrate(path,ctx,seed,"residual_curriculum",
                    self.run/f"pilot/seed{seed}/residual_curriculum/calibration"))
            selected=nominate(self.calibrations,methods)
        write_json(self.run/"pilot_calibrations.json",self.calibrations)
        write_json(self.run/"nomination.json",dict(nominated=selected,methods=methods,trigger=trigger,
                                                   calibration_sha=sha(self.run/"pilot_calibrations.json")))
        if selected is None:
            raise StopRun("完整校准及允许的课程分支后仍无合格候选，停止正式训练",20)
        self.event("内部比较通过，进入五折三次重复训练",nomination=selected)
        return methods,selected

    def formal(self,methods,selected):
        units=[]
        for repeat in range(3):
            for fold in range(5):
                self.contexts.clear()
                torch.cuda.empty_cache()
                ctx=self.context(fold)
                seed=997100+100*repeat+fold
                base=self.run/f"formal/repeat{repeat}/fold{fold}"
                warm_path=self.train_unit(ctx,seed,"warm",None,base/"warm",steps=2000)
                _,warm=self.load_model(warm_path,ctx,seed)
                order=methods[(fold+repeat)%len(methods):]+methods[:(fold+repeat)%len(methods)]
                for method in order:
                    path=self.train_unit(ctx,seed,method,warm["model"],base/method/"train",sampler_seed=seed+50000)
                    cal=self.calibrate(path,ctx,seed,method,base/method/"calibration")
                    cal["repeat"]=repeat
                    units.append(cal)
        if len(units)!=15*len(methods):
            raise StopRun("formal unit completeness failed")
        if any(not u["selected"].get("finite",False) for u in units):
            raise StopRun("formal calibration missing finite fallback",20)
        write_json(self.run/"formal_freeze.json",dict(units=units,nomination=selected,source=self.source_manifest,
                                                      frozen_at=dt.datetime.now().astimezone().isoformat()))
        self.guard.outer_frozen=True
        self.event("全部模型已冻结，开始统一外层评价",units=len(units))
        self.outer(units,selected,methods)

    def outer(self,units,selected,methods):
        collected={}
        baseline_folds=[]
        all_gates=[]
        pressure=[]
        for fold in range(5):
            self.contexts.clear()
            ctx=self.context(fold)
            outer=build_data(ctx["outer_e"],ctx["norm"],self.guard,fold,"outer_evaluate",ctx["resolver"],self.decoder,"cuda")
            base=evaluate_bundle(ctx["anchor"],outer,self.run/f"outer/fold{fold}/pure11.npz",dict(kind="pure11",fold=fold))
            baseline_folds.append(base)
            outer40=build_data(ctx["outer_e"],ctx["norm"],self.guard,fold,"outer_evaluate",ctx["resolver"],self.decoder,"cuda",40)
            base40=self.pressure(ctx["anchor"],outer40)
            for unit in [u for u in units if u["fold"]==fold]:
                model,_=self.load_model(unit["checkpoint"],ctx,unit["seed"])
                for calibrated in (False,True):
                    gamma=unit["selected"]["gamma"] if calibrated else 1.
                    candidate=copy.deepcopy(model)
                    with torch.no_grad():
                        candidate.E.mul_(gamma)
                    key=(unit["method"],calibrated,unit["repeat"])
                    folder=self.run/f"outer/fold{fold}/repeat{unit['repeat']}/{unit['method']}/{int(calibrated)}"
                    b=evaluate_bundle(candidate,outer,folder/"predictions.npz",dict(unit,gamma=gamma))
                    q=complete_quality(b,base)
                    write_json(folder/"quality.json",q)
                    collected.setdefault(key,[]).append(b)
                    all_gates.append(dict(method=key[0],calibrated=key[1],repeat=key[2],fold=fold,**q))
                    cand40=self.pressure(candidate,outer40)
                    new_bad=bool(np.any(cand40 & ~base40))
                    pressure.append(dict(method=key[0],calibrated=key[1],repeat=key[2],fold=fold,new_divergence=new_bad,
                                         baseline_bad=int(base40.sum()),candidate_bad=int(cand40.sum()),n=len(cand40)))
                    if fold==0 and unit["repeat"]==0 and unit["method"]==selected["method"] and calibrated==selected["calibrated"]:
                        self.timing_target=(copy.deepcopy(candidate).cpu(),copy.deepcopy(outer))
        def merge(parts):
            b={k:np.concatenate([p[k] for p in parts]) for k in ("pred","target","force","internal","force_target","internal_target","errors")}
            b["meta"]=[m for p in parts for m in p["meta"]]
            b["stats"]=hierarchy(b["errors"],b["meta"])
            return b
        base=merge(baseline_folds)
        pooled=[]
        merged={}
        for key,parts in collected.items():
            merged[key]=merge(parts)
            q=complete_quality(merged[key],base)
            positive=sum(x["i20"]>0 for x in all_gates if (x["method"],x["calibrated"],x["repeat"])==key)
            pooled.append(dict(method=key[0],calibrated=key[1],repeat=key[2],positive_folds=positive,**q))
        nkey=(selected["method"],selected["calibrated"])
        q_selected=[q for q in all_gates if (q["method"],q["calibrated"])==nkey]
        pooled_selected=[q for q in pooled if (q["method"],q["calibrated"])==nkey]
        ci=self.bootstrap(base,[merged[(nkey[0],nkey[1],r)] for r in range(3)])
        passed=(all(q["passed"] for q in q_selected+pooled_selected) and
                all(q["i20"]>=5 and q["positive_folds"]>=4 for q in pooled_selected) and ci[0]>0 and
                not any(q["new_divergence"] for q in pressure if (q["method"],q["calibrated"])==nkey))
        write_json(self.run/"formal_verdict.json",dict(passed=passed,nomination=selected,folds=all_gates,
            pooled=pooled,pressure40=pressure,paired_family_ci95=ci))
        if not passed:
            raise StopRun("五折重复验证未全部通过，保留改善与退化工况并停止速度优化",20)
        self.latency()

    def pressure(self,model,data):
        m=copy.deepcopy(model)
        if isinstance(m,torch.nn.Module):
            m=m.cuda().double().eval()
        with torch.no_grad():
            p=m.rollout(data.x,data.u,(40,))["xhat"].cpu().numpy()
        err=np.abs(p-data.y.cpu().numpy())
        return (~np.isfinite(err).all(axis=(1,2))) | (np.nanmax(err,axis=(1,2))>20)

    def bootstrap(self,base,candidates):
        meta=base["meta"]
        records=[]
        for s in range(12):
            for fam in sorted({m["family"] for m in meta if m["scenario"]==s}):
                tids=sorted({m["trajectory"] for m in meta if m["scenario"]==s and m["family"]==fam})
                bv=[];cv=[]
                for tid in tids:
                    ix=[i for i,m in enumerate(meta) if m["scenario"]==s and m["family"]==fam and m["trajectory"]==tid]
                    bv.append(base["errors"][ix,3,0].mean())
                    cv.append(np.mean([c["errors"][ix,3,0].mean() for c in candidates]))
                records.append((s,float(np.mean(bv)),float(np.mean(cv))))
        rng=np.random.Generator(np.random.PCG64(997500))
        boots=[]
        for _ in range(2000):
            b=[];c=[]
            for s in range(12):
                a=np.asarray([r[1:] for r in records if r[0]==s])
                selected=a[rng.integers(len(a),size=len(a))]
                b.append(selected[:,0].mean());c.append(selected[:,1].mean())
            boots.append(100*(np.mean(b)-np.mean(c))/max(np.mean(b),1e-12))
        return np.quantile(boots,[.025,.975],method="linear").tolist()

    def latency(self):
        self.event("检查完整20步预测速度")
        from background_speed import benchmark
        model,data=self.timing_target
        result=benchmark(model,data)
        write_json(self.run/"latency.json",result)
        if not result["passed"]:
            raise StopRun("预测精度通过，但完整预测速度尚未达标",20)

    def finish(self,status,code,message):
        self.done.set()
        result=dict(status=status,exit_code=code,message=message,stage=self.current,
                    time=dt.datetime.now().astimezone().isoformat(),run=str(self.run),pid=os.getpid(),
                    elapsed_s=self.previous_s+time.monotonic()-self.started)
        write_json(self.run/"exit.json",result)
        write_json(self.run/"progress.json",result)
        from background_report import report
        try:
            report(self.run,result)
        except Exception:
            (self.run/"report_error.txt").write_text(traceback.format_exc(),encoding="utf-8")
        if code:
            (self.run/"solutions.md").write_text(
                "# 停止原因与处理方向\n\n"+message+"\n\n"
                "先查看exit.json、events.jsonl和对应quality文件。输入、身份或数值错误先修同一问题；"
                "精度失败保留各工况、时域和负结果，不调整3%/5%门、不增加训练预算。"
                "若只是资源暂停，使用相同源码、任务书和run恢复已保存单元；不要重复启动一个新队列。\n",
                encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project",required=True)
    ap.add_argument("--run",required=True)
    ap.add_argument("--taskbook",required=True)
    ap.add_argument("--preflight-only",action="store_true")
    ap.add_argument("--smoke-only",action="store_true")
    args=ap.parse_args()
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    if not torch.cuda.is_available():
        raise RuntimeError("5080 CUDA unavailable")
    q=Queue(args.run,args.project,args.taskbook)
    with RunLock(q.rev/"koopman_background.lock"):
        threading.Thread(target=q.pulse,daemon=True).start()
        try:
            q.prepare()
            if args.preflight_only or args.smoke_only:
                q.context(0)
                q.audit_pilot(q.context(0))
                if args.smoke_only:
                    q.smoke()
                q.finish("PREFLIGHT_PASSED",0,"输入、受力读出和已有训练身份核查通过")
                return
            verification=read_json(q.run/"verification.json")
            if not verification.get("passed") or verification.get("source")!=q.source_manifest:
                raise StopRun("后台长实验缺少同版本已通过的前置检查")
            methods,selected=q.pilot_and_selection()
            q.formal(methods,selected)
            q.finish("COMPLETED",0,"所有有前置依据的实验与验收完成")
        except StopRun as exc:
            q.finish("STOPPED",exc.code,str(exc))
            raise SystemExit(exc.code)
        except Exception as exc:
            (q.run/"traceback.txt").write_text(traceback.format_exc(),encoding="utf-8")
            q.finish("FAILED",24,str(exc))
            raise


if __name__=="__main__":
    main()
