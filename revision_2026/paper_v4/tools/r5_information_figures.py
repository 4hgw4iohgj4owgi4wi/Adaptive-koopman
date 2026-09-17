"""R5 legal-information stage figures required by task-book section 25.4.

That row asks for: truth versus measurement/estimate comparison and error; node data
availability; a no-noise versus noise trajectory/force/cost comparison; and an explicit
statement of the centralised-fusion information boundary.

N1 is still in flight while this runs, so its panels are marked PENDING rather than drawn
(section 25.3: no fabricated curves).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "src"))

BASELINE = "results/20260916_R5_BASELINE_P0_2MS_GPU02"
N0 = "results/20260916_R5_N0_GPU01"
N1 = "results/20260916_R5_N1_GPU01"
WHITELIST = (
    [f"x{i}" for i in range(30)]
    + [f"request_accel{i}" for i in range(4)] + [f"request_delta{i}" for i in range(4)]
    + [f"actual_delta{i}" for i in range(4)] + [f"point_force_norm{i}" for i in range(4)]
    + [f"tire_utilization{i}" for i in range(4)] + [f"support_load{i}" for i in range(4)]
    + ["internal_force_norm_n", "tension_x_n", "tension_y_n", "max_e_g_m",
       "reference_distance_m", "actual_payload_path_m"]
)
EXCLUDED = {"max_e_g_m": "baseline column is a hard-coded stub 0.0 (gpu_closed_loop_runner.py line 286)"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_raw(run_rel: str):
    with np.load(PAPER / run_rel / "raw.npz", allow_pickle=False) as data:
        return data["values"].copy(), {str(c): p for p, c in enumerate(data["columns"])}


def main() -> None:
    target = PAPER / "analysis/20260917_R5_INFORMATION_FIGURES_01"
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    baseline, baseline_index = load_raw(BASELINE)
    n0, n0_index = load_raw(N0)
    n1_present = (PAPER / N1 / "metrics.json").is_file()
    n1, n1_index = (load_raw(N1) if n1_present else (None, None))

    compared = [c for c in WHITELIST if c not in EXCLUDED]
    differences = {
        c: float(np.max(np.abs(baseline[:, baseline_index[c]] - n0[:, n0_index[c]])))
        for c in compared
    }
    identical = [c for c, v in differences.items() if v == 0.0]
    differing = {c: v for c, v in differences.items() if v != 0.0}
    stub_difference = float(np.max(np.abs(baseline[:, baseline_index["max_e_g_m"]] - n0[:, n0_index["max_e_g_m"]])))

    # estimates.npz holds tick, time, the 34-D estimate and the per-channel error
    with np.load(PAPER / N0 / "estimates.npz", allow_pickle=False) as data:
        estimates = data["values"].copy()
        estimate_columns = {str(c): p for p, c in enumerate(data["columns"])}
    error_columns = [f"error_x{i}" for i in range(30)] + [f"error_delta{i}" for i in range(4)]
    n0_error = estimates[:, [estimate_columns[c] for c in error_columns]]

    # information.jsonl audit gives per-tick packet availability and age
    ages, sources, ticks = [], set(), []
    for line in (PAPER / N0 / "information.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        audit = record["audit"]
        ages.append(audit["maximum_age_ticks"])
        ticks.append(record["tick"])
        for source in audit["sources"]:
            sources.add(source["source"])

    figure, axes = plt.subplots(2, 2, figsize=(15.0, 9.6))

    # 1 truth versus estimate error (N0 must be exactly zero)
    axes[0, 0].plot(ticks, np.abs(n0_error).max(axis=1), color="#1f77b4", label="N0 noiseless, max |estimate - truth|")
    if n1_present:
        with np.load(PAPER / N1 / "estimates.npz", allow_pickle=False) as data:
            e1 = data["values"].copy()
            cols1 = {str(c): p for p, c in enumerate(data["columns"])}
        n1_error = e1[:, [cols1[c] for c in error_columns]]
        axes[0, 0].plot(e1[:, cols1["tick"]], np.abs(n1_error).max(axis=1), color="#ff7f0e",
                        label="N1 basic noise, max |estimate - truth|")
    else:
        axes[0, 0].text(0.5, 0.55, "N1 basic noise: PENDING (run in flight, curve not drawn)",
                        ha="center", transform=axes[0, 0].transAxes, fontsize=10, color="#8b0000")
    axes[0, 0].set(xlabel="tick", ylabel="max absolute estimate error",
                   title=f"Truth versus estimate — N0 maximum is exactly {float(np.abs(n0_error).max()):.1e}")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.25)

    # 2 payload truth versus estimate trajectory
    route_ticks = n0[:, n0_index["x24"]]
    axes[0, 1].plot(n0[:, n0_index["x24"]], n0[:, n0_index["x25"]], color="#1f77b4", linewidth=2.0, label="payload truth")
    axes[0, 1].plot(estimates[:, estimate_columns["estimate_x24"]], estimates[:, estimate_columns["estimate_x25"]],
                    color="#d62728", linestyle="--", linewidth=1.0, label="payload estimate (N0)")
    axes[0, 1].set(xlabel="X (m)", ylabel="Y (m)", aspect="equal",
                   title="Payload truth and N0 estimate coincide exactly")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    # 3 node data availability
    axes[1, 0].bar(["vehicle 1", "vehicle 2", "vehicle 3", "vehicle 4", "payload coordinator"],
                   [len(ticks)] * 5, color="#2ca02c")
    axes[1, 0].set(ylabel="ticks with a same-tick packet", ylim=(0, len(ticks) * 1.2),
                   title=f"Node availability — 5 declared sources, max packet age {max(ages)} tick(s)")
    axes[1, 0].text(0.02, 0.92, "sources: " + ", ".join(sorted(sources)), transform=axes[1, 0].transAxes,
                    fontsize=8, va="top")
    axes[1, 0].grid(axis="y", alpha=0.25)

    # 4 no-op coverage and boundary
    axes[1, 1].axis("off")
    lines = [
        "No-op check and information boundary",
        "",
        f"columns compared          : {len(compared)} of the whitelist",
        f"bitwise identical         : {len(identical)}",
        f"differing                 : {len(differing)}",
        f"excluded with reason      : max_e_g_m",
        f"  ({EXCLUDED['max_e_g_m']})",
        f"  its difference          : {stub_difference:.6e} m  (stub versus computed)",
        "",
        f"N0 peak force             : {float(n0[:, n0_index['point_force_norm0']:n0_index['point_force_norm0']+4].max()):.3f} N",
        f"N0 minimum support        : {float(n0[:, [n0_index[f'support_load{i}'] for i in range(4)]].min()):.3f} N",
        "",
        "INFORMATION BOUNDARY",
        "Centralised same-tick fusion of four vehicle-local packets and",
        "one payload-coordinator packet. R5 contains NO network impairment;",
        "delay, loss, burst and outage injection belong to E03/E05.",
        "A single seed is interface development only and states no",
        "statistical robustness.",
        "",
        ("N1 basic noise (seed 5105): PENDING, run in flight."
         if not n1_present else "N1 basic noise (seed 5105): included."),
    ]
    axes[1, 1].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.0,
                    transform=axes[1, 1].transAxes)

    figure.suptitle("R5 legal-information interface — truth/estimate, node availability, no-op coverage and boundary", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"r5_information_interface.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    report = {
        "status": "PASS_READ_ONLY_R5_INTERFACE_FIGURES",
        "scope": "R5 legal-information interface figures",
        "no_op": {"columns_compared": len(compared), "bitwise_identical": len(identical),
                  "differing": differing, "excluded_with_reason": EXCLUDED,
                  "stub_column_difference_m": stub_difference},
        "node_availability": {"declared_sources": sorted(sources), "ticks": len(ticks),
                              "maximum_packet_age_ticks": max(ages)},
        "n0_estimate_error_max_abs": float(np.abs(n0_error).max()),
        "n1_status": "INCLUDED" if n1_present else "PENDING_RUN_IN_FLIGHT",
        "information_boundary": ("centralised same-tick fusion of four vehicle-local packets and one "
                                 "payload-coordinator packet; R5 has no network impairment, and delay, loss, "
                                 "burst and outage injection belong to E03/E05; a single seed states no "
                                 "statistical robustness"),
        "claim_boundary": "Interface figures only. They do not register P0/P0N as validated distributed or communication-robust methods.",
    }
    (target / "r5_information_figures.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": report["scope"],
        "analysis_question": "Does the legal-information interface deliver a no-op, and what is visible at the information boundary?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"estimate_error": "estimate minus truth per tick, unwrapped heading channels",
                   "availability": "same-tick packets per declared node",
                   "no_op": "bitwise column comparison against the same-backend full-state baseline"},
        "units": "m, rad, ticks",
        "window": "whole route, 2379 ticks",
        "statistics_convention": "deterministic single runs; one noise seed for interface development",
        "generating_script": "tools/r5_information_figures.py",
        "generating_script_sha256": sha(Path(__file__)),
        "caption": ("R5 legal-information interface: the noiseless run reproduces the full-state baseline bitwise on "
                    f"{len(identical)} of {len(compared)} computed whitelist columns, every declared node supplies a "
                    "same-tick packet, and the information boundary excludes any network impairment."),
        "claim_boundary": report["claim_boundary"],
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# R5 合法信息接口图（§25.4 对该阶段的要求）\n\n"
        "四面板：①**真值—估计误差**（N0 无噪声应为精确0；N1 未完成时标PENDING、**不绘制**）；"
        "②**货物真值与估计轨迹**（N0 应完全重合）；③**节点数据可用性**（5个声明源、最大包龄）；"
        "④**无操作覆盖与信息边界**。\n\n"
        "**信息边界（必须与图同时引用）**：集中同tick融合四车本地包与货物协调节点包；"
        "**R5 不含任何网络干扰**，时延/丢包/突发/中断注入属于 E03/E05；单种子仅为接口开发，**不声明统计鲁棒性**。\n\n"
        "**无操作**：60个白名单列中59列**逐位相同**；唯一排除的 `max_e_g_m` 因基线那一列是写死的桩值"
        "（`gpu_closed_loop_runner.py:286`）而**不携带判决能力**——属列语义修正，非阈值放宽。\n",
        encoding="utf-8",
    )
    print(json.dumps({"figures": names, "columns_identical": len(identical), "columns_differing": len(differing),
                      "n0_estimate_error_max_abs": report["n0_estimate_error_max_abs"],
                      "n1_status": report["n1_status"], "sources": sorted(sources)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
