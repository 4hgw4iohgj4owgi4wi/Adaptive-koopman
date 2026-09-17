"""KC background evaluation: fixed inputs, one gamma, full protected metrics."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch

import guard_core as gc
from pure_linear import PureLinearKoopman

H = (1, 5, 10, 20)
METHODS = ("aligned", "fixed_guard", "adaptive_guard")
NAMES = (
    "直线匀速", "直线加速—匀速—制动", "100米加速—正反阶跃转向—减速",
    "持续稳态转弯", "单移线", "回头弯", "直线入弯—持续转弯—出弯",
    "前后车辆反向加减速", "左右车辆反向转向", "对角车辆差动操纵",
    "往复转向扫频与连接器边界激励", "加减速与转向混合操纵",
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest().upper()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + ".partial")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temp, p)


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, records):
    if not records:
        raise ValueError("refuse empty evidence table")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in records for k in r))
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)


def digest_arrays(arrays):
    h = hashlib.sha256()
    for k in sorted(arrays):
        a = np.asarray(arrays[k])
        h.update(k.encode())
        h.update(str((a.shape, a.dtype)).encode())
        h.update(a.tobytes())
    return h.hexdigest().upper()


class CheckedAccess(gc.AccessGuard):
    """Inherited OS-open audit, plus hash/schema checks before cached values are used."""
    def __init__(self, entries, folds, run, cache_manifest):
        super().__init__(entries, folds, Path(run) / "split_access.jsonl", "G4")
        self.cache_sha = {r["trajectory_id"]: r["cache11_sha256"] for r in cache_manifest}
        self.verified = set()

    def load(self, entry, fold, purpose):
        with self.context(fold, purpose):
            p = Path(entry["cache_path"])
            key = (str(p), p.stat().st_size, p.stat().st_mtime_ns)
            if key not in self.verified:
                if sha(p) != self.cache_sha[entry["trajectory_id"]]:
                    raise ValueError("cache11 identity changed: " + str(p))
                self.verified.add(key)
            with np.load(p, allow_pickle=False) as z:
                out = {k: z[k] for k in z.files}
        u = out["control11"]
        x = out["relative_state47"]
        if u.ndim != 2 or u.shape[1] != 11 or x.shape != (len(u) + 1, 47):
            raise ValueError("explicit u11/x47 contract failed")
        if not np.array_equal(u[:, :7], out["control7"]):
            raise ValueError("control7 prefix changed")
        return out


def build_data(entries, norm, guard, fold, purpose, resolver, decoder, device, horizon=20):
    data = gc.WindowData(entries, norm, guard, fold, purpose, resolver, decoder, device, horizon)
    lookup = {e["trajectory_id"]: e for e in entries}
    for m in data.meta:
        e = lookup[m["trajectory"]]
        m.update(member=e["member"], direction=e["direction"], scenario_name=NAMES[m["scenario"]],
                 fold=fold, role=guard.roles[(fold, m["trajectory"])])
    gc.validate_rows(data.meta)
    return data


def pure(coeff):
    return PureLinearKoopman(coeff[:47].T, coeff[47:58].T, coeff[58], 11)


def hierarchy(values, meta):
    """Window -> trajectory -> family -> scenario; all grouping keys are scoped."""
    out = []
    for s in range(12):
        si = [i for i, m in enumerate(meta) if m["scenario"] == s]
        if not si:
            raise ValueError("missing required scenario")
        fs = []
        for fam in sorted({meta[i]["family"] for i in si}):
            fi = [i for i in si if meta[i]["family"] == fam]
            ts = []
            for tid in sorted({meta[i]["trajectory"] for i in fi}):
                ix = [i for i in fi if meta[i]["trajectory"] == tid]
                ts.append(values[ix].mean(axis=0))
            fs.append(np.mean(ts, axis=0))
        out.append(np.mean(fs, axis=0))
    return np.asarray(out)


def weighted_tail(values, meta):
    if len(values) != len(meta) or not len(meta):
        raise ValueError("missing required tail windows")
    fams = {m["family"] for m in meta}
    w = []
    for m in meta:
        fm = [x for x in meta if x["family"] == m["family"]]
        tids = {x["trajectory"] for x in fm}
        n = sum(x["trajectory"] == m["trajectory"] for x in fm)
        w.append(1.0 / (len(fams) * len(tids) * n))
    w = np.asarray(w)
    order = np.argsort(values, kind="stable")
    v = np.asarray(values)[order]
    cdf = np.cumsum(w[order]) / w.sum()
    return [float(np.dot(w, values) / w.sum()),
            float(v[min(np.searchsorted(cdf, .95), len(v)-1)]),
            float(v[min(np.searchsorted(cdf, .99), len(v)-1)]), float(v[-1])]


def evaluate_bundle(model, data, path=None, identity=None, batch=256):
    use = copy.deepcopy(model)
    if isinstance(use, torch.nn.Module):
        use = use.to(data.device).double().eval()
    preds, forces, internals, errors = [], [], [], []
    hs = [h-1 for h in H]
    with torch.no_grad():
        for start in range(0, len(data.meta), batch):
            ix = np.arange(start, min(start+batch, len(data.meta)))
            p = use.rollout(data.x[ix], data.u[ix], H)["xhat"][:, hs]
            f, inn = data.physical(p, ix)
            err = gc.component_errors(p, data.y[ix][:, hs], f, inn, data.force[ix][:, hs],
                                      data.internal[ix][:, hs], data.norm, False)
            for source, dest in ((p,preds),(f,forces),(inn,internals),(err,errors)):
                dest.append(source.cpu().numpy())
    bundle = dict(pred=np.concatenate(preds), force=np.concatenate(forces), internal=np.concatenate(internals),
                  errors=np.concatenate(errors), target=data.y[:, hs].cpu().numpy(),
                  force_target=data.force[:, hs].cpu().numpy(), internal_target=data.internal[:, hs].cpu().numpy())
    bundle["stats"] = hierarchy(bundle["errors"], data.meta)
    bundle["meta"] = data.meta
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, **{k:v for k,v in bundle.items() if k != "meta"},
                            state_mean=data.norm["relative_state47_mean"], state_scale=data.norm["relative_state47_scale"])
        write_json(p.with_suffix(".json"), dict(identity=identity, meta=data.meta, horizons=H, array_sha=sha(p)))
    return bundle


def complete_quality(candidate, anchor):
    if candidate["meta"] != anchor["meta"]:
        raise ValueError("unpaired evaluation rows")
    for b in (candidate, anchor):
        if not all(np.isfinite(b[k]).all() for k in ("pred","target","force","internal","errors","stats")):
            return dict(passed=False, finite=False, rows=[dict(name="finite", passed=False)], i20=None)
    s, a = candidate["stats"], anchor["stats"]
    g = gc.constraints(torch.from_numpy(s), torch.from_numpy(a)).numpy()
    out = [dict(name=f"training_guard_{i:02d}", violation=float(v), passed=bool(v<=0)) for i,v in enumerate(g)]
    def add(name, val, base, denominator, limit):
        d = (val-base)/denominator
        out.append(dict(name=name, value=float(val), baseline=float(base), denominator=float(denominator),
                        limit=float(limit), violation=float(d-limit), passed=bool(d<=limit)))
    for hidx in (1,2):
        for c, name in ((3,"force"),(4,"internal")):
            val, base = s[:,hidx,c].mean(), a[:,hidx,c].mean()
            add(f"{name}_h{H[hidx]}", val, base, max(base,1e-12), .05)
    for subset in ("all", "hard"):
        ix = [i for i,m in enumerate(candidate["meta"]) if m["scenario"]==5 and (subset=="all" or m["start"] in (100,120))]
        if not ix:
            raise ValueError("missing required hairpin tail subset: " + subset)
        mm = [candidate["meta"][i] for i in ix]
        cv = weighted_tail(candidate["errors"][ix,3,0], mm)
        av = weighted_tail(anchor["errors"][ix,3,0], mm)
        for key,v,b in zip(("mean","p95","p99","max"), cv,av):
            add(f"hairpin20_{subset}_{key}", v,b,max(b,.02),.03)
    maximum = float(np.max(np.abs(candidate["pred"]-candidate["target"])))
    out.append(dict(name="max_normalized_error", value=maximum, limit=20., passed=maximum<=20.))
    base = float(a[:,3,0].mean())
    return dict(passed=all(r["passed"] for r in out), finite=True, rows=out,
                m20=float(s[:,3,0].mean()), i20=100*(base-float(s[:,3,0].mean()))/max(base,1e-12))


def select_gamma(records):
    if len(records)!=5 or {r["gamma"] for r in records}!={0.,.25,.5,.75,1.}:
        raise ValueError("incomplete gamma grid")
    good = [r for r in records if r["protected"] and r["i20"]>=5 and r["gamma"]>0]
    options = good or [r for r in records if r["protected"]]
    if not options:
        return dict(status="NO_PROTECTED_POINT", gamma=None, i20=None, finite=False)
    best = options[0]
    for r in options[1:]:
        if r["m20"] < best["m20"]-1e-10 or (abs(r["m20"]-best["m20"])<=1e-10 and r["gamma"]<best["gamma"]):
            best = r
    return dict(best, status="CANDIDATE" if good else "PROTECTED_BUT_LOW_GAIN")


def nominate(calibrations, methods):
    candidates = []
    for method in methods:
        units = [u for u in calibrations if u["method"]==method]
        if len(units)!=3 or len({u["seed"] for u in units})!=3:
            raise ValueError("three complete seeds required")
        for calibrated in (False,True):
            selected = [u["selected"] if calibrated else dict(u["raw"],status="CANDIDATE" if u["raw"]["protected"] and u["raw"]["i20"]>=5 else "FAILED") for u in units]
            if all(r.get("finite",False) for r in selected) and sum(r["status"]=="CANDIDATE" for r in selected)>=2:
                candidates.append(dict(method=method, calibrated=calibrated,
                                       median_i20=float(np.median([r["i20"] for r in selected]))))
    if not candidates:
        return None
    best = max(candidates, key=lambda x:x["median_i20"])
    near = [c for c in candidates if best["median_i20"]-c["median_i20"]<=.5]
    return min(near,key=lambda c:(methods.index(c["method"]),c["calibrated"]))


def curriculum_trigger(no_candidate, curves):
    if len(curves)!=3:
        raise ValueError("three fixed guard curves required")
    result = []
    one_idx = [0]+[3+4*s for s in range(12)]+[51,53]
    for curve in curves:
        pts = [c for c in curve if c["step"] in (5000,5500,6000)]
        if [c["step"] for c in pts] != [5000,5500,6000]:
            raise ValueError("missing final fit monitors")
        vals = [np.asarray(c["fit_g"], dtype=float) for c in pts]
        if any(v.shape!=(55,) or not np.isfinite(v).all() for v in vals):
            raise ValueError("invalid final fit guards")
        result.append(all(np.max(v[one_idx])>0 for v in vals))
    return dict(no_main_candidate=bool(no_candidate), per_seed_fit_failure=result,
                triggered=bool(no_candidate and sum(result)>=2))


def mse_data_loss(error, scenario):
    if error.ndim!=2 or error.shape[1]!=47 or set(scenario.tolist())!=set(range(12)):
        raise ValueError("MSE curriculum requires x47 and all twelve sampled scenarios")
    per = sum(w*error[:, sl].square().mean(-1) for w,sl in
              ((.3,slice(0,3)),(.2,slice(3,19)),(.2,slice(19,31)),(.3,slice(31,47))))
    return torch.stack([per[scenario==s].mean() for s in range(12)]).mean()


def residual_mse_loss(model, data, ix):
    pred = model.rollout(data.x[ix].float(), data.u[ix,:1].float(), (1,))["xhat"][:,0]
    error = pred-data.y[ix,0].float()
    return mse_data_loss(error,data.scenario[ix]) + 1e-4*model.E.square().sum() + 1e-5*sum(p.square().sum() for p in model.parameters())


def state_weights_equal(a,b):
    return a.keys()==b.keys() and all(torch.equal(a[k].cpu(), b[k].cpu()) for k in a)
