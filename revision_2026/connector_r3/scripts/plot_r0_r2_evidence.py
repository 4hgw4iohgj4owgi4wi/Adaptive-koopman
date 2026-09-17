from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    z = np.load(path)
    return {k: z[k] for k in z.files}


def save(fig, out, name):
    fig.tight_layout(); fig.savefig(out / name, dpi=180, bbox_inches="tight"); plt.close(fig)


def main():
    root = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    ds = float(sys.argv[3]); k, c, gap = 30000.0, 3500.0, .002

    # 01: event-aligned high-rate onset comparison for all specified speeds.
    fig, axs = plt.subplots(2, 2, figsize=(11, 7.5))
    onset_rows = []
    for ax, speed in zip(axs.ravel(), (.01, .05, .25, 1.0)):
        a = load(root / f"contact_v{speed}.npz")
        active = np.flatnonzero(a["contact_active_raw"]); i = int(active[0]); t0 = a["time_s"][i]
        keep = (a["time_s"] >= t0 - .0002) & (a["time_s"] <= t0 + .0022)
        v1 = k * np.maximum(a["delta_m"], 0) + c * np.maximum(a["normal_speed_mps"], 0) * a["contact_active_raw"]
        tms = (a["time_s"] - t0) * 1e3
        ax.plot(tms[keep], v1[keep], "--", lw=1.2, label="V1")
        ax.plot(tms[keep], a["raw_force_n"][keep], lw=1.2, label="R3")
        ax.axvline(2, color="black", lw=.6, alpha=.5); ax.grid(alpha=.2)
        ax.set_title(f"v = {speed:g} m/s"); ax.set_xlabel("Time from first active sample (ms)"); ax.set_ylabel("Force (N)"); ax.legend()
        for j in np.flatnonzero(keep):
            onset_rows.append([speed, float(tms[j]), float(v1[j]), float(a["raw_force_n"][j]), float(a["delta_m"][j]), float(a["smoothing_weight"][j])])
    save(fig, out, "01_v1_r3_contact_onset.png")
    with (out / "01_v1_r3_contact_onset.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["speed_mps","time_from_onset_ms","v1_force_n","r3_force_n","penetration_m","smoothing_weight"]); w.writerows(onset_rows)

    # 02: analytic smoothing and force transition.
    delta = np.linspace(0, 2 * ds, 1001); s = np.clip(delta / ds, 0, 1); g = np.where(delta >= ds, 1, 3*s*s-2*s*s*s)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
    axs[0].plot(delta * 1e3, g, color="#0072B2"); axs[0].axvline(ds*1e3, color="black", ls="--", lw=.8); axs[0].set(xlabel="Penetration (mm)",ylabel="g(delta)",title="Frozen damping-entry weight")
    for speed in (.01,.05,.25,1.0):
        axs[1].plot(delta*1e3, k*delta+c*g*speed, label=f"R3 {speed:g} m/s")
    axs[1].set(xlabel="Penetration (mm)",ylabel="Force (N)",title="R3 force within smoothing zone"); axs[1].legend()
    for ax in axs: ax.grid(alpha=.2)
    save(fig,out,"02_smoothing_weight_and_force.png")
    np.savetxt(out/"02_smoothing_weight_and_force.csv",np.c_[delta,g,k*delta+c*g*.01,k*delta+c*g*.05,k*delta+c*g*.25,k*delta+c*g],delimiter=",",header="penetration_m,g,r3_0p01_n,r3_0p05_n,r3_0p25_n,r3_1p0_n",comments="")

    # 03: static global equivalence.
    delta = np.linspace(0,.5,2001); v1=k*delta; r3=k*delta
    fig,ax=plt.subplots(figsize=(8.5,4.8));ax.plot(delta*1e3,v1,"--",lw=2,label="V1 static");ax.plot(delta*1e3,r3,lw=1,label="R3 static");ax.axhline(12000,color="#E69F00",ls=":",label="12 kN numerical diagnostic");ax.axhline(15000,color="#D55E00",ls=":",label="15 kN numerical stop");ax.set(xlabel="Penetration (mm)",ylabel="Static force (N)",title="Global static-force equivalence (curves overlap)");ax.grid(alpha=.2);ax.legend()
    save(fig,out,"03_static_force_global_equivalence.png")
    np.savetxt(out/"03_static_force_global_equivalence.csv",np.c_[delta,v1,r3],delimiter=",",header="penetration_m,v1_force_n,r3_force_n",comments="")

    # 04: energy audits.
    cons, damp = load(root/"conservative.npz"), load(root/"damped.npz")
    fig,axs=plt.subplots(2,1,figsize=(9.5,6.5),sharex=True)
    axs[0].plot(cons["time_s"],cons["total_mechanical_energy_j"],label="No damping total energy")
    axs[0].plot(damp["time_s"],damp["total_mechanical_energy_j"],label="R3 damped total energy")
    axs[1].plot(damp["time_s"],damp["damping_power_w"],color="#D55E00",label="Damping power")
    axs[0].set(ylabel="Energy (J)",title="Single-connector energy audit");axs[1].set(xlabel="Time (s)",ylabel="Power (W)")
    for ax in axs: ax.grid(alpha=.2);ax.legend()
    save(fig,out,"04_energy_and_dissipation.png")
    n=min(len(cons["time_s"]),len(damp["time_s"]));np.savetxt(out/"04_energy_and_dissipation.csv",np.c_[cons["time_s"][:n],cons["total_mechanical_energy_j"][:n],damp["total_mechanical_energy_j"][:n],damp["damping_power_w"][:n]],delimiter=",",header="time_s,conservative_total_j,damped_total_j,damping_power_w",comments="")


if __name__ == "__main__":
    main()
