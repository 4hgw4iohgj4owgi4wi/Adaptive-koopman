"""Independent EXP-R2 R2b audit and frozen-candidate selection."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from .cli import save,sha
from .references import build_hairpin


def load(folder):
    with np.load(folder/"raw.npz",allow_pickle=False) as z:a=z["values"];c={str(x):i for i,x in enumerate(z["columns"])}
    with np.load(folder/"substeps.npz",allow_pickle=False) as z:b=z["values"];s={str(x):i for i,x in enumerate(z["columns"])}
    m=json.loads((folder/"metrics.json").read_text(encoding="utf-8"));solver=[json.loads(x) for x in (folder/"solver.jsonl").read_text(encoding="utf-8").splitlines()]
    return a,c,b,s,m,solver


def audit(label,folder):
    a,c,b,s,m,solver=load(folder);point=max(float(np.max(a[:,[c[f"point_force_norm{i}"] for i in range(4)]])),float(np.max(b[:,[s[f"force_peak{i}"] for i in range(4)]])));tire=max(float(np.max(a[:,[c[f"tire_utilization{i}"] for i in range(4)]])),float(np.max(b[:,[s[f"tire_utilization{i}"] for i in range(4)]])));support=min(float(np.min(a[:,[c[f"support_load{i}"] for i in range(4)]])),float(np.min(b[:,[s[f"support_load{i}"] for i in range(4)]])));walls=np.asarray([x["wall_s"] for x in solver]);checks={"three_arrays":len(a)==900 and len(b)>=9000,"solver_count":len(solver)==900,"all_solver_pass":all(x["status"]=="PASS" and x["solver_status"] in ("solved","solved inaccurate") and x["validation"]["status"]=="PASS" for x in solver),"time_complete":np.isclose(a[-1,c["time_s"]],18.,atol=1e-12),"reference_complete":np.isclose(a[-1,c["reference_distance_m"]],36.,atol=1e-9),"point_force":point<=15000.,"tire":tire<=1.,"support":support>=0.,"metrics_match":abs(point-m["maximum_point_force_n"])<1e-8 and abs(tire-m["maximum_tire_utilization"])<1e-10 and abs(support-m["minimum_support_load_n"])<1e-8}
    row={"label":label,"folder":str(folder),"status":"PASS" if all(checks.values()) else "FAIL","checks":{k:bool(v) for k,v in checks.items()},"reference_distance_m":float(a[-1,c["reference_distance_m"]]),"actual_payload_path_m":float(a[-1,c["actual_payload_path_m"]]),"maximum_point_force_n":point,"maximum_internal_force_norm_n":float(np.max(a[:,c["internal_force_norm_n"]])),"maximum_tire_utilization":tire,"minimum_support_load_n":support,"maximum_configuration_error_m":float(np.max(a[:,c["max_e_g_m"]])),"maximum_abs_request_steering_deg":float(np.rad2deg(np.max(np.abs(a[:,[c[f"request_delta{i}"] for i in range(4)]])))),"maximum_abs_actual_steering_deg":float(np.rad2deg(np.max(np.abs(a[:,[c[f"actual_delta{i}"] for i in range(4)]])))),"maximum_abs_acceleration_mps2":float(np.max(np.abs(a[:,[c[f"request_accel{i}"] for i in range(4)]]))),"solver_wall_mean_s":float(np.mean(walls)),"solver_wall_p95_s":float(np.quantile(walls,.95)),"solver_wall_max_s":float(np.max(walls)),"solver_over_5s_count":int(np.sum(walls>5.))}
    return row,(a,c,b,s,solver)


def main():
    import matplotlib;matplotlib.use("Agg");import matplotlib.pyplot as plt
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--candidate",action="append",nargs=2,required=True);z=p.parse_args();out=Path(z.out);out.mkdir(parents=True,exist_ok=False);audits=[];data={}
    for label,path in z.candidate:row,raw=audit(label,Path(path));audits.append(row);data[label]=raw
    passed=[r for r in audits if r["status"]=="PASS"]
    preferred=min(passed,key=lambda r:(r["maximum_internal_force_norm_n"],r["maximum_configuration_error_m"],r["solver_wall_mean_s"]))["label"] if passed else None
    remaining=[r["label"] for r in passed if r["label"]!=preferred]
    report={"status":"PASS" if len(passed)==2 else "FAIL","selection_rule":"R2b only orders R2c; final R3 selection requires both R2c full routes","r2c_order":[preferred,*remaining] if preferred else [],"selected_for_r3":None,"audits":audits,"development_selection_only":True,"source_sha256":sha(__file__)};save(out,"comparison.json",report)
    with (out/"comparison.csv").open("w",newline="",encoding="utf-8-sig") as h:w=csv.DictWriter(h,fieldnames=[k for k in audits[0] if k!="checks"]);w.writeheader();w.writerows([{k:v for k,v in r.items() if k!="checks"} for r in audits])
    fig,axes=plt.subplots(3,2,figsize=(12,10),constrained_layout=True)
    for label,(a,c,b,s,solver) in data.items():
        t=a[:,c["time_s"]];axes[0,0].plot(t,np.max(a[:,[c[f"point_force_norm{i}"] for i in range(4)]],axis=1),label=label);axes[0,1].plot(t,a[:,c["internal_force_norm_n"]],label=label);axes[1,0].plot(t,a[:,c["max_e_g_m"]],label=label);axes[1,1].plot(t,np.max(a[:,[c[f"tire_utilization{i}"] for i in range(4)]],axis=1),label=label);axes[2,0].plot(t,np.rad2deg(np.max(np.abs(a[:,[c[f"request_delta{i}"] for i in range(4)]]),axis=1)),label=label);axes[2,1].plot(t,[x["wall_s"] for x in solver],label=label)
    for ax,y in zip(axes.ravel(),["max point force (N)","internal force norm (N)","max |e_g| (m)","max tire utilization","max request steer (deg)","solver wall time (s)"]):ax.set_xlabel("time (s)");ax.set_ylabel(y);ax.grid(alpha=.25);ax.legend()
    axes[2,1].axhline(5.,color="r",ls="--",lw=1,label="5 s budget");fig.suptitle("EXP-R2 R2b centralized full-state physical MPC candidates");fig.savefig(out/"r2b_comparison.png",dpi=180);plt.close(fig)
    route=build_hairpin();fig,ax=plt.subplots(figsize=(8,6),constrained_layout=True);mask=route["s_m"]<=36.0001;ax.plot(route["x_m"][mask],route["y_m"][mask],"k--",label="frozen 11 m-transition reference")
    for label,(a,c,_,_,_) in data.items():ax.plot(a[:,c["x24"]],a[:,c["x25"]],label=label)
    theta=np.linspace(0,np.pi,500);ideal_x=np.r_[np.linspace(0,24,200),24+11.5*np.sin(theta)];ideal_y=np.r_[np.zeros(200),11.5*(1-np.cos(theta))];ax.plot(ideal_x,ideal_y,":",color="0.5",label="ideal instantaneous 11.5 m semicircle");ax.axis("equal");ax.set_xlabel("x (m)");ax.set_ylabel("y (m)");ax.legend();ax.set_title("R2b paths and disclosed ideal geometry");fig.savefig(out/"r2b_paths.png",dpi=180);plt.close(fig)
    lines=["# R2b候选比较","",f"状态：{report['status']}；短片段仅决定R2c顺序为 `{', '.join(report['r2c_order'])}`。两套候选都必须完成R2c后才能冻结R3候选；当前`selected_for_r3=null`。","","|候选|点力峰值 N|内力峰值 N|最大构形误差 m|轮胎利用率|最小支撑 N|平均/P95/最大求解 s|", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in audits:lines.append(f"|{r['label']}|{r['maximum_point_force_n']:.6f}|{r['maximum_internal_force_norm_n']:.6f}|{r['maximum_configuration_error_m']:.9f}|{r['maximum_tire_utilization']:.6f}|{r['minimum_support_load_n']:.3f}|{r['solver_wall_mean_s']:.3f}/{r['solver_wall_p95_s']:.3f}/{r['solver_wall_max_s']:.3f}|")
    lines+=['',"两者均完成同一18秒/36米参考且无硬违约。λ=2的内力峰值仅小幅下降，不能表述为显著或普适优势；R2c完整回头弯仍可能失败。个别求解超过5秒说明它尚非实时实现。"]
    (out/"comparison.md").write_text("\n".join(lines),encoding="utf-8");print(json.dumps({"status":report["status"],"r2c_order":report["r2c_order"],"selected_for_r3":None}))
    if report["status"]!="PASS":raise SystemExit(20)
if __name__=="__main__":main()
