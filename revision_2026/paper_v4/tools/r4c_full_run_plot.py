"""Required single-run full-route figure for EXP-R4-C."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path: Path):
    with np.load(path, allow_pickle=False) as z:
        return z["values"].copy(), [str(x) for x in z["columns"]]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--protocol", type=Path, required=True)
    a = p.parse_args()
    run, audit_path, protocol = a.run.resolve(), a.audit.resolve(), a.protocol.resolve()
    figures = run / "figures"
    figures.mkdir(exist_ok=False)
    raw, columns = archive(run / "raw.npz")
    sub, subcolumns = archive(run / "substeps.npz")
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    solver = [json.loads(x) for x in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert metrics["status"] == "COMPLETED" and audit["status"] == "PASS" and len(raw) == len(solver) == 2379
    c, sc = {x:i for i,x in enumerate(columns)}, {x:i for i,x in enumerate(subcolumns)}
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from paper_v4_core.references import build_hairpin
    route = build_hairpin()
    distance = raw[:, c["reference_distance_m"]]
    reference = np.column_stack([np.interp(distance, route["s_m"], route[x]) for x in ("x_m", "y_m", "heading_rad")])
    position_error = np.linalg.norm(raw[:, [c["x24"], c["x25"]]] - reference[:, :2], axis=1)
    heading_error = np.rad2deg(np.arctan2(np.sin(raw[:,c["x26"]]-reference[:,2]), np.cos(raw[:,c["x26"]]-reference[:,2])))
    t, ts = raw[:,c["time_s"]], sub[:,sc["time_s"]]
    colors = ["#315a9c", "#d95f02", "#1b9e77", "#7570b3"]
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 12.0))
    axes[0,0].plot(route["x_m"], route["y_m"], "k--", label="Frozen reference")
    axes[0,0].plot(raw[:,c["x24"]], raw[:,c["x25"]], color="#315a9c", label="Payload actual")
    axes[0,0].set(title="Full payload route", xlabel="World X (m)", ylabel="World Y (m)"); axes[0,0].axis("equal")
    axes[0,1].plot(t, position_error, label="Position error")
    axh=axes[0,1].twinx(); axh.plot(t, heading_error, color="#d95f02", label="Heading error")
    axes[0,1].set(title="Payload tracking error", xlabel="Time (s)", ylabel="Position error (m)"); axh.set_ylabel("Heading error (deg)")
    for i,color in enumerate(colors): axes[1,0].plot(ts,sub[:,sc[f"force_peak{i}"]],color=color,lw=.7,label=f"Connection {i+1}")
    axes[1,0].set(title="Unsmoothed accepted-substep force peaks",xlabel="Time (s)",ylabel="Force (N)")
    for i,color in enumerate(colors):
        axes[1,1].plot(t,np.rad2deg(raw[:,c[f"request_delta{i}"]]),color=color,label=f"Vehicle {i+1} requested")
        axes[1,1].plot(t,np.rad2deg(raw[:,c[f"actual_delta{i}"]]),color=color,ls="--",alpha=.8,label=f"Vehicle {i+1} actual")
    axes[1,1].axhline(15,color="#d62728",ls=":"); axes[1,1].axhline(-15,color="#d62728",ls=":")
    axes[1,1].set(title="Requested and actual steering",xlabel="Time (s)",ylabel="Steering angle (deg)")
    wall=np.asarray([x["wall_s"] for x in solver]); axes[2,0].plot(t,wall,label="Optimization wall time"); axes[2,0].axhline(5,color="#d62728",ls=":",label="Original 5 s budget")
    axes[2,0].set(title=f"Optimization cost; total {metrics['wall_s']/3600:.3f} h",xlabel="Control tick time (s)",ylabel="Wall time (s)")
    ax=axes[2,1]; ax2=ax.twinx()
    for i,color in enumerate(colors):
        ax.plot(t,raw[:,c[f"tire_utilization{i}"]],color=color,label=f"Vehicle {i+1} tire")
        ax2.plot(t,raw[:,c[f"support_load{i}"]],color=color,ls="--",alpha=.7,label=f"Vehicle {i+1} support")
    ax.set(title="Tire utilization and support load",xlabel="Time (s)",ylabel="Tire utilization (1)"); ax2.set_ylabel("Support load (N)")
    for x in axes.flat: x.grid(alpha=.2)
    for x in (axes[0,0],axes[1,0],axes[1,1],axes[2,0]): x.legend(fontsize=7,ncol=2)
    lines,labels=ax.get_legend_handles_labels(); lines2,labels2=ax2.get_legend_handles_labels(); ax.legend(lines+lines2,labels+labels2,fontsize=7,ncol=2)
    lines,labels=axes[0,1].get_legend_handles_labels(); lines2,labels2=axh.get_legend_handles_labels(); axes[0,1].legend(lines+lines2,labels+labels2,fontsize=8)
    step=metrics["maximum_plant_step_s"]*1000
    fig.suptitle(f"Centralized Full-State Physical Model Predictive Control\nFull route; Plant Maximum Integration Step {step:g} ms; one deterministic simulation",fontsize=12)
    fig.tight_layout(rect=(0,0,1,.955)); stem=f"full_route_{step:g}ms_diagnostics"
    fig.savefig(figures/f"{stem}.png",dpi=240); fig.savefig(figures/f"{stem}.svg"); plt.close(fig)
    inputs=[run/x for x in ("raw.npz","substeps.npz","solver.jsonl","metrics.json")]+[audit_path,protocol]
    manifest={"run":run.name,"candidate_id":metrics["candidate_id"],"method_full_name":"Centralized Full-State Physical Model Predictive Control","information_boundary":"Centralized full simulation state; offline diagnostic upper bound.","plant_maximum_integration_step_ms":step,"source_files":[{"path":str(x),"sha256":sha(x)} for x in inputs],"generator":{"path":str(Path(__file__).resolve()),"sha256":sha(Path(__file__).resolve())},"figure":{"files":[f"{stem}.png",f"{stem}.svg"],"fields_units":"XY m; position error m; heading error deg; force N; steering deg; wall s; tire utilization 1; support load N","caption":f"Full registered route, {step:g} ms Plant Maximum Integration Step, centralized full-state offline diagnostic, one deterministic simulation; raw force peaks unsmoothed; original 5 s computation budget failed."},"science_status":"PASS_SINGLE_RUN_PHYSICAL_AND_EVIDENCE_CONVERGENCE_PENDING","figure_status":"PENDING_VISUAL_QA"}
    (figures/"figure_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (figures/"README.md").write_text(f"# 完整路线单条图表\n\n本目录对应`{run.name}`，含轨迹、误差、未平滑受力、输入、约束和耗时。单条通过不等于数值收敛；必须等待0.5 ms配对比较。\n",encoding="utf-8")
    print(json.dumps({"status":"FIGURES_CREATED","manifest":str(figures/"figure_manifest.json")},indent=2))


if __name__ == "__main__": main()
