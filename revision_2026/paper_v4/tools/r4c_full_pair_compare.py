"""Independent 1 ms versus 0.5 ms full-route comparison for EXP-R4-C."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


THRESHOLDS = {
    "peak_relative": 0.02,
    "impulse_vector_relative": 0.02,
    "terminal_position_m": 0.001,
    "terminal_heading_deg": 0.01,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        values = data["values"].copy()
        columns = [str(value) for value in data["columns"]]
    return values, {name: index for index, name in enumerate(columns)}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_run(folder: Path, audit_path: Path):
    raw, columns = archive(folder / "raw.npz")
    substeps, subcolumns = archive(folder / "substeps.npz")
    metrics = read_json(folder / "metrics.json")
    audit = read_json(audit_path)
    solver = [
        json.loads(line)
        for line in (folder / "solver.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    peaks = np.asarray(
        [
            max(
                float(np.max(raw[:, columns[f"point_force_norm{i}"]])),
                float(np.max(substeps[:, subcolumns[f"force_peak{i}"]])),
            )
            for i in range(4)
        ]
    )
    impulses = np.column_stack(
        [
            [float(np.sum(substeps[:, subcolumns[f"force_impulse_x{i}"]])) for i in range(4)],
            [float(np.sum(substeps[:, subcolumns[f"force_impulse_y{i}"]])) for i in range(4)],
        ]
    )
    return {
        "folder": folder,
        "audit_path": audit_path,
        "raw": raw,
        "columns": columns,
        "substeps": substeps,
        "subcolumns": subcolumns,
        "metrics": metrics,
        "audit": audit,
        "solver": solver,
        "peaks": peaks,
        "impulses": impulses,
        "terminal_position": raw[-1, [columns["x24"], columns["x25"]]],
        "terminal_heading": float(raw[-1, columns["x26"]]),
    }


def wrapped_angle_difference(a, b):
    return np.arctan2(np.sin(a - b), np.cos(a - b))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse", type=Path, required=True)
    parser.add_argument("--fine", type=Path, required=True)
    parser.add_argument("--coarse-audit", type=Path, required=True)
    parser.add_argument("--fine-audit", type=Path, required=True)
    parser.add_argument("--coarse-protocol", type=Path, required=True)
    parser.add_argument("--fine-protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    coarse = load_run(args.coarse.resolve(), args.coarse_audit.resolve())
    fine = load_run(args.fine.resolve(), args.fine_audit.resolve())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    figures = out / "figures"
    figures.mkdir()

    peak_relative_by_connector = np.abs(coarse["peaks"] - fine["peaks"]) / np.maximum(np.abs(fine["peaks"]), 1.0)
    impulse_relative_by_connector = np.linalg.norm(coarse["impulses"] - fine["impulses"], axis=1) / np.maximum(
        np.linalg.norm(fine["impulses"], axis=1), 1.0
    )
    terminal_position = float(np.linalg.norm(coarse["terminal_position"] - fine["terminal_position"]))
    terminal_heading = float(
        np.rad2deg(abs(wrapped_angle_difference(coarse["terminal_heading"], fine["terminal_heading"])))
    )
    quantities = {
        "peak_max_relative": float(np.max(peak_relative_by_connector)),
        "peak_relative_by_connector": peak_relative_by_connector.tolist(),
        "point_force_peaks_1ms_n": coarse["peaks"].tolist(),
        "point_force_peaks_0p5ms_n": fine["peaks"].tolist(),
        "impulse_vector_max_relative": float(np.max(impulse_relative_by_connector)),
        "impulse_vector_relative_by_connector": impulse_relative_by_connector.tolist(),
        "force_impulse_1ms_ns": coarse["impulses"].tolist(),
        "force_impulse_0p5ms_ns": fine["impulses"].tolist(),
        "terminal_payload_position_m": terminal_position,
        "terminal_payload_heading_deg": terminal_heading,
    }
    gate_checks = {
        "peak_relative_le_0p02": quantities["peak_max_relative"] <= THRESHOLDS["peak_relative"],
        "impulse_vector_relative_le_0p02": quantities["impulse_vector_max_relative"] <= THRESHOLDS["impulse_vector_relative"],
        "terminal_position_m_le_0p001": terminal_position <= THRESHOLDS["terminal_position_m"],
        "terminal_heading_deg_le_0p01": terminal_heading <= THRESHOLDS["terminal_heading_deg"],
    }
    coarse_protocol = read_json(args.coarse_protocol.resolve())
    fine_protocol = read_json(args.fine_protocol.resolve())
    coarse_identity = {
        row["path"]: row["sha256"] for row in coarse_protocol["identity_files"] if row["path"].startswith("src/")
    }
    fine_identity = {
        row["path"]: row["sha256"] for row in fine_protocol["identity_files"] if row["path"].startswith("src/")
    }
    evidence_checks = {
        "coarse_audit_pass": coarse["audit"].get("status") == "PASS",
        "fine_audit_pass": fine["audit"].get("status") == "PASS",
        "coarse_completed": coarse["metrics"].get("status") == "COMPLETED",
        "fine_completed": fine["metrics"].get("status") == "COMPLETED",
        "coarse_2379_ticks": len(coarse["raw"]) == len(coarse["solver"]) == 2379,
        "fine_2379_ticks": len(fine["raw"]) == len(fine["solver"]) == 2379,
        "same_control_time_grid": np.array_equal(
            coarse["raw"][:, coarse["columns"]["time_s"]], fine["raw"][:, fine["columns"]["time_s"]]
        ),
        "coarse_step_is_1ms": np.isclose(coarse["metrics"].get("maximum_plant_step_s"), 0.001, rtol=0.0, atol=1e-15),
        "fine_step_is_0p5ms": np.isclose(fine["metrics"].get("maximum_plant_step_s"), 0.0005, rtol=0.0, atol=1e-15),
        "same_candidate": coarse["metrics"].get("candidate_id") == fine["metrics"].get("candidate_id"),
        "same_taskbook_parent_sha": coarse_protocol["taskbook"]["pre_execution_sha256"]
        == fine_protocol["taskbook"]["pre_execution_sha256"],
        "same_compute_identity": coarse_identity == fine_identity,
    }
    evidence_checks = {name: bool(value) for name, value in evidence_checks.items()}
    status = "PASS" if all(evidence_checks.values()) and all(gate_checks.values()) else "FAIL"
    report = {
        "status": status,
        "scope": "EXP-R4-C selected candidate full-route 1 ms to 0.5 ms decisive numerical pairing",
        "method_full_name": "Centralized Full-State Physical Model Predictive Control",
        "information_boundary": "Centralized full simulation state; offline diagnostic upper bound.",
        "thresholds": THRESHOLDS,
        "near_zero_policy": "Connector impulse vector norm uses a 1 N*s denominator floor.",
        "evidence_checks": evidence_checks,
        "gate_checks": gate_checks,
        "comparison": quantities,
        "runs": {"1ms": str(coarse["folder"]), "0.5ms": str(fine["folder"])},
        "source_sha256": sha(Path(__file__).resolve()),
    }
    (out / "r3_convergence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    c, f = coarse["columns"], fine["columns"]
    time = coarse["raw"][:, c["time_s"]]
    position_difference = np.linalg.norm(
        coarse["raw"][:, [c["x24"], c["x25"]]] - fine["raw"][:, [f["x24"], f["x25"]]], axis=1
    )
    heading_difference = np.rad2deg(
        np.abs(wrapped_angle_difference(coarse["raw"][:, c["x26"]], fine["raw"][:, f["x26"]]))
    )
    colors = ["#315a9c", "#d95f02", "#1b9e77", "#7570b3"]
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 12.0))
    axes[0, 0].plot(coarse["raw"][:, c["x24"]], coarse["raw"][:, c["x25"]], label="1 ms")
    axes[0, 0].plot(fine["raw"][:, f["x24"]], fine["raw"][:, f["x25"]], "--", label="0.5 ms")
    axes[0, 0].set(title="Payload trajectory overlap", xlabel="World X (m)", ylabel="World Y (m)")
    axes[0, 0].axis("equal")
    axes[0, 1].plot(time, 1000.0 * position_difference, label="Position difference")
    axes[0, 1].axhline(1.0, color="#d62728", ls=":", label="Terminal gate (reference)")
    twin = axes[0, 1].twinx()
    twin.plot(time, heading_difference, color="#d95f02", label="Heading difference")
    twin.axhline(0.01, color="#9467bd", ls=":")
    axes[0, 1].set(title="Same-tick payload difference", xlabel="Time (s)", ylabel="Position difference (mm)")
    twin.set_ylabel("Heading difference (deg)")
    for run, style, label in ((coarse, "-", "1 ms"), (fine, "--", "0.5 ms")):
        subtime = run["substeps"][:, run["subcolumns"]["time_s"]]
        maximum_force = np.max(
            np.column_stack([run["substeps"][:, run["subcolumns"][f"force_peak{i}"]] for i in range(4)]), axis=1
        )
        axes[1, 0].plot(subtime, maximum_force, style, lw=0.65, label=label)
    axes[1, 0].set(title="Unsmoothed maximum point force", xlabel="Time (s)", ylabel="Force (N)")
    x = np.arange(4)
    axes[1, 1].bar(x - 0.18, np.linalg.norm(coarse["impulses"], axis=1), 0.36, label="1 ms")
    axes[1, 1].bar(x + 0.18, np.linalg.norm(fine["impulses"], axis=1), 0.36, label="0.5 ms")
    axes[1, 1].set(title="Full-route connector impulse-vector norm", xlabel="Connection", ylabel="Impulse norm (N s)")
    axes[1, 1].set_xticks(x, [str(i + 1) for i in x])
    request_difference = np.max(
        np.column_stack(
            [np.abs(wrapped_angle_difference(coarse["raw"][:, c[f"request_delta{i}"]], fine["raw"][:, f[f"request_delta{i}"]])) for i in range(4)]
        ), axis=1
    )
    axes[2, 0].plot(time, np.rad2deg(request_difference), label="Maximum requested-steering difference")
    axes[2, 0].set(title="Closed-loop input divergence", xlabel="Time (s)", ylabel="Difference (deg)")
    wall_coarse = np.asarray([row["wall_s"] for row in coarse["solver"]])
    wall_fine = np.asarray([row["wall_s"] for row in fine["solver"]])
    axes[2, 1].boxplot([wall_coarse, wall_fine], tick_labels=["1 ms", "0.5 ms"], showfliers=False)
    axes[2, 1].axhline(5.0, color="#d62728", ls=":", label="Original 5 s budget")
    axes[2, 1].set(title="Optimization wall time", ylabel="Wall time per control tick (s)")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(fontsize=8)
    handles, labels = axes[0, 1].get_legend_handles_labels()
    handles2, labels2 = twin.get_legend_handles_labels()
    axes[0, 1].legend(handles + handles2, labels + labels2, fontsize=8)
    fig.suptitle("EXP-R4-C full-route numerical pairing: 1 ms versus 0.5 ms", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(figures / "full_route_pair_diagnostics.png", dpi=240)
    fig.savefig(figures / "full_route_pair_diagnostics.svg")
    plt.close(fig)

    gate_values = [
        100.0 * quantities["peak_max_relative"],
        100.0 * quantities["impulse_vector_max_relative"],
        1000.0 * terminal_position,
        terminal_heading,
    ]
    gate_limits = [2.0, 2.0, 1.0, 0.01]
    labels = ["Peak force (%)", "Impulse vector (%)", "Terminal position (mm)", "Terminal heading (deg)"]
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5), constrained_layout=True)
    for axis, value, limit, label, passed in zip(axes.flat, gate_values, gate_limits, labels, gate_checks.values()):
        axis.bar(["Observed", "Registered limit"], [value, limit], color=["#2ca02c" if passed else "#d62728", "#7f7f7f"])
        axis.set_title(f"{label}: {'PASS' if passed else 'FAIL'}")
        axis.set_ylabel(label)
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle(f"EXP-R4-C decisive numerical-resolution gates: {status}")
    fig.savefig(figures / "r3_registered_gates.png", dpi=240)
    fig.savefig(figures / "r3_registered_gates.svg")
    plt.close(fig)

    sources = [
        coarse["folder"] / name for name in ("raw.npz", "substeps.npz", "solver.jsonl", "metrics.json")
    ] + [
        fine["folder"] / name for name in ("raw.npz", "substeps.npz", "solver.jsonl", "metrics.json")
    ] + [
        coarse["audit_path"], fine["audit_path"], args.coarse_protocol.resolve(), args.fine_protocol.resolve()
    ]
    manifest = {
        "comparison": "EXP-R4-C full-route 1 ms versus 0.5 ms",
        "method_full_name": report["method_full_name"],
        "information_boundary": report["information_boundary"],
        "source_files": [{"path": str(path), "sha256": sha(path)} for path in sources],
        "generator": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        "figures": [
            {
                "files": ["full_route_pair_diagnostics.png", "full_route_pair_diagnostics.svg"],
                "question": "Do the two accepted full-route simulations overlap, and where do state, force, input, and cost differences arise?",
                "fields_units": "XY m; position mm; heading deg; force N; impulse N s; steering deg; wall s",
            },
            {
                "files": ["r3_registered_gates.png", "r3_registered_gates.svg"],
                "question": "Does the decisive 1 ms to 0.5 ms pair meet every preregistered numerical-resolution limit?",
                "fields_units": "relative difference percent; terminal position mm; terminal heading deg",
            },
        ],
        "science_status": status,
        "figure_status": "PENDING_VISUAL_QA",
    }
    (figures / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (figures / "README.md").write_text(
        "# EXP-R4-C 完整路线配对图\n\n"
        "本目录比较同一冻结候选的 1 ms 与 0.5 ms 最大植物积分步长。图中受力未经平滑；"
        "配对裁决同时要求单条审计和四项注册数值门通过。图表视觉检查完成前，figure_status 保持 PENDING_VISUAL_QA。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "comparison": quantities, "gate_checks": gate_checks}, indent=2))
    if status != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
