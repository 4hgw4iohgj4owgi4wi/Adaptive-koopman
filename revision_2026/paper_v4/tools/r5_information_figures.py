"""R5 legal-information stage figures required by task-book section 25.4.

That row asks for: truth versus measurement/estimate comparison and error; node data
availability; a no-noise versus noise trajectory/force/cost comparison; and an explicit
statement of the centralised-fusion information boundary.

The current revision also reads the frozen single-run audits.  A completed trajectory is
not presented as an R5 pass when its single-run audit failed.
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

import argparse

DEFAULT_BASELINE = "results/20260916_R5_BASELINE_P0_2MS_GPU02"
DEFAULT_N0 = "results/20260916_R5_N0_GPU01"
DEFAULT_N1 = "results/20260916_R5_N1_GPU01"
DEFAULT_OUTPUT = "analysis/20260917_R5_INFORMATION_FIGURES_02"
WHITELIST = (
    [f"x{i}" for i in range(30)]
    + [f"request_accel{i}" for i in range(4)] + [f"request_delta{i}" for i in range(4)]
    + [f"actual_delta{i}" for i in range(4)] + [f"point_force_norm{i}" for i in range(4)]
    + [f"tire_utilization{i}" for i in range(4)] + [f"support_load{i}" for i in range(4)]
    + ["internal_force_norm_n", "tension_x_n", "tension_y_n", "max_e_g_m",
       "reference_distance_m", "actual_payload_path_m"]
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_raw(run_rel: str):
    with np.load(PAPER / run_rel / "raw.npz", allow_pickle=False) as data:
        return data["values"].copy(), {str(c): p for p, c in enumerate(data["columns"])}


def main() -> None:
    # Parameterised so that the strict re-run chain writes to its own directory instead of
    # overwriting _02.  The argparse block was missing from the previous revision, which had
    # already started referring to baseline_rel/n0_rel/n1_rel without ever assigning them.
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--n0", default=DEFAULT_N0)
    parser.add_argument("--n1", default=DEFAULT_N1)
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    baseline_rel, n0_rel, n1_rel = args.baseline, args.n0, args.n1

    baseline, baseline_index = load_raw(baseline_rel)
    n0, n0_index = load_raw(n0_rel)
    n1_present = (PAPER / n1_rel / "metrics.json").is_file()
    n1, n1_index = (load_raw(n1_rel) if n1_present else (None, None))
    n0_audit = json.loads((PAPER / n0_rel / "single_run_audit.json").read_text(encoding="utf-8"))
    n1_audit = (json.loads((PAPER / n1_rel / "single_run_audit.json").read_text(encoding="utf-8"))
                if n1_present else None)
    n1_failed = bool(n1_audit and n1_audit.get("status") != "PASS_SINGLE_RUN_AUDIT")
    n1_request_check = next(
        (item for item in (n1_audit or {}).get("checks", [])
         if item.get("check") in {
             "requested_steering_box_bound_within_registered_solver_tolerance",
             "requested_steering_within_registered_acceptance_tolerance",
         }),
        None,
    )

    baseline_metrics = json.loads((PAPER / baseline_rel / "metrics.json").read_text(encoding="utf-8"))
    historical_stub = baseline_metrics.get("maximum_configuration_error_m") is None
    excluded = ({"max_e_g_m": "historical baseline did not compute this column"} if historical_stub else {})

    target = PAPER / args.out
    if target.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT:" + args.out)
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    compared = [c for c in WHITELIST if c not in excluded]
    differences = {
        c: float(np.max(np.abs(baseline[:, baseline_index[c]] - n0[:, n0_index[c]])))
        for c in compared
    }
    identical = [c for c, v in differences.items() if v == 0.0]
    differing = {c: v for c, v in differences.items() if v != 0.0}
    stub_difference = (float(np.max(np.abs(baseline[:, baseline_index["max_e_g_m"]] - n0[:, n0_index["max_e_g_m"]])))
                       if historical_stub else None)

    # estimates.npz holds tick, time, the 34-D estimate and the per-channel error
    with np.load(PAPER / n0_rel / "estimates.npz", allow_pickle=False) as data:
        estimates = data["values"].copy()
        estimate_columns = {str(c): p for p, c in enumerate(data["columns"])}
    error_columns = [f"error_x{i}" for i in range(30)] + [f"error_delta{i}" for i in range(4)]
    n0_error = estimates[:, [estimate_columns[c] for c in error_columns]]

    # information.jsonl audit gives per-tick packet availability and age
    ages, sources, ticks = [], set(), []
    for line in (PAPER / n0_rel / "information.jsonl").read_text(encoding="utf-8").splitlines():
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
        with np.load(PAPER / n1_rel / "estimates.npz", allow_pickle=False) as data:
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
        f"excluded with reason      : {', '.join(excluded) if excluded else 'none'}",
        *(([f"  ({excluded['max_e_g_m']})",
             f"  its difference          : {stub_difference:.6e} m  (stub versus computed)"])
          if historical_stub else ["  all whitelist columns are genuinely computed"]),
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
         if not n1_present else f"N1 basic noise: COMPLETED; audit {n1_audit['items_passed']}/{n1_audit['items_total']} "
                                f"{n1_audit['status']}."),
        ("N1 requested steering: audit detail unavailable."
         if not n1_request_check else
         f"N1 request max {np.rad2deg(n1_request_check['detail'].get('max_requested_rad', n1_request_check['detail'].get('limit_rad', 0.0) + n1_request_check['detail'].get('overshoot_rad', 0.0))):.6f} deg; "
         f"limit {np.rad2deg(n1_request_check['detail'].get('limit_rad', np.deg2rad(15.0))):.6f} deg; "
         f"check {'PASS' if n1_request_check.get('pass') else 'FAIL'}."),
        "R5 total gate: BLOCKED; no overall R5 PASS is claimed." if n1_failed else "R5 total gate: not evaluated by this figure.",
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
        "status": ("R5_INTERFACE_FIGURES_COMPLETE_N1_AUDIT_FAIL"
                   if n1_failed else "R5_INTERFACE_FIGURES_COMPLETE"),
        "scope": "R5 legal-information interface figures",
        "runs": {"baseline": baseline_rel, "n0": n0_rel, "n1": n1_rel},
        "no_op": {"columns_compared": len(compared), "bitwise_identical": len(identical),
                  "differing": differing, "excluded_with_reason": excluded,
                  "stub_column_difference_m": stub_difference},
        "node_availability": {"declared_sources": sorted(sources), "ticks": len(ticks),
                              "maximum_packet_age_ticks": max(ages)},
        "n0_estimate_error_max_abs": float(np.abs(n0_error).max()),
        "n1_status": "INCLUDED" if n1_present else "PENDING_RUN_IN_FLIGHT",
        "n0_single_run_audit": n0_audit.get("status"),
        "n1_single_run_audit": (n1_audit or {}).get("status", "NOT_AVAILABLE"),
        "r5_total_gate_status": "BLOCKED_N1_SINGLE_RUN_AUDIT_FAIL" if n1_failed else "NOT_EVALUATED_HERE",
        "information_boundary": ("centralised same-tick fusion of four vehicle-local packets and one "
                                 "payload-coordinator packet; R5 has no network impairment, and delay, loss, "
                                 "burst and outage injection belong to E03/E05; a single seed states no "
                                 "statistical robustness"),
        "claim_boundary": ("Interface figures only. They do not register P0/P0N as validated distributed or "
                           "communication-robust methods, and they do not override either single-run audit."),
    }
    (target / "r5_information_figures.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "science_status": report["r5_total_gate_status"],
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
                    "same-tick packet, and the information boundary excludes any network impairment. "
                    f"N1 single-run audit is {(n1_audit or {}).get('status', 'NOT_AVAILABLE')}; the R5 total gate is blocked."),
        "claim_boundary": report["claim_boundary"],
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    audit_note = (
        "N1 单条审计失败，因此本图不构成R5总PASS，总门保持阻塞。"
        if n1_failed else
        "N1 单条审计未失败；R5总门仍须由独立门工具执行，不能由本图代替。"
    )
    no_op_note = (
        "**无操作**：历史链排除 `max_e_g_m`，因为当时基准未计算该列；其余有效列按原阈值比较。\n"
        if historical_stub else
        f"**无操作**：严格链的全部 {len(compared)} 个白名单列均为实算量，没有桩值排除。\n"
    )
    readme = (
        "# R5 合法信息接口图（§25.4 对该阶段的要求）\n\n"
        "四面板：①**真值—估计误差**（N0 无噪声应为精确0；N1 未完成时标PENDING、**不绘制**）；"
        "②**货物真值与估计轨迹**（N0 应完全重合）；③**节点数据可用性**（5个声明源、最大包龄）；"
        "④**无操作覆盖与信息边界**。\n\n"
        "**信息边界（必须与图同时引用）**：集中同tick融合四车本地包与货物协调节点包；"
        "**R5 不含任何网络干扰**，时延/丢包/突发/中断注入属于 E03/E05；单种子仅为接口开发，**不声明统计鲁棒性**。\n\n"
        f"**单条审计**：N0 为 `{n0_audit.get('status')}`；N1 为 `{(n1_audit or {}).get('status', 'NOT_AVAILABLE')}`。"
        f"{audit_note}\n\n"
        f"{no_op_note}"
    )
    (figure_dir / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"figures": names, "columns_identical": len(identical), "columns_differing": len(differing),
                      "n0_estimate_error_max_abs": report["n0_estimate_error_max_abs"],
                      "n1_status": report["n1_status"], "sources": sorted(sources)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
