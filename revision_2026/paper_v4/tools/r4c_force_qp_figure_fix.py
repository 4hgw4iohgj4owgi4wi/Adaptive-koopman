"""Post-processing-only QA correction for the EXP-R4-C force QP figure."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "20260914_R4C_FORCE_QP01"
REPORT = json.loads((OUT / "force_qp_report.json").read_text(encoding="utf-8"))
with np.load(OUT / "qp_arrays.npz", allow_pickle=False) as data:
    arrays = {name: np.asarray(data[name]) for name in data.files}
names = ["P", "q", "A", "l", "u", "u_nom"]
diff = {}
for name in names:
    a, b = arrays[f"serial_{name}"], arrays[f"parallel_{name}"]
    equal = (a == b) | (np.isnan(a) & np.isnan(b))
    finite = np.isfinite(a) & np.isfinite(b)
    value = np.zeros_like(a, dtype=float)
    value[finite] = np.abs(a[finite] - b[finite])
    value[~equal & ~finite] = np.inf
    diff[name] = float(np.max(value))

serial = arrays["serial_u_nom"][0]
parallel = arrays["parallel_u_nom"][0]
timing = REPORT["timing_s"]
fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
axes[0].plot(names, [diff[k] for k in names], "o", color="#438a5e", markersize=7)
axes[0].axhline(0.0, color="#438a5e", linewidth=1)
axes[0].set_ylim(-0.05, 0.05)
axes[0].set(title="Serial / parallel QP difference", ylabel="Maximum absolute difference")
x=np.arange(8); axes[1].plot(x, serial, "o-", label="serial"); axes[1].plot(x, parallel, "x--", label="parallel (8)")
axes[1].set(title="Nominal first-step input", xlabel="Control component", ylabel="Native command unit"); axes[1].legend()
labels=["Serial build","Parallel build","Serial solve+check","Parallel solve+check"]
values=[timing["serial_build"],timing["parallel_build"],timing["serial_solve_and_validate"],timing["parallel_solve_and_validate"]]
axes[2].bar(labels,values,color=["#315a9c","#e18437","#7094c4","#efb275"]); axes[2].axhline(5,color="red",ls=":",label="Original 5 s budget")
axes[2].tick_params(axis="x",rotation=25); axes[2].set(title="Registered-point wall time",ylabel="Wall time (s)"); axes[2].legend()
for ax in axes: ax.grid(alpha=.2)
fig.tight_layout()
for ext in ("png","svg"): fig.savefig(OUT/f"force_qp_preflight_qa.{ext}",dpi=300)
plt.close(fig)
correction={
  "status":"POSTPROCESS_QA_CORRECTED",
  "original_science_status":REPORT["status"],
  "original_figure_preserved":"force_qp_preflight.png/.svg",
  "reason":"Original max-difference display evaluated equal infinite bounds as inf-inf and produced NaN.",
  "corrected_matrix_max_absolute_difference":diff,
  "qp_arrays_still_bitwise_exact":all(REPORT["matrix_exact"].values()),
  "dynamics_or_qp_rerun":False,
  "generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
}
(OUT/"figure_qa_correction.json").write_text(json.dumps(correction,indent=2),encoding="utf-8")
print(json.dumps(correction))
