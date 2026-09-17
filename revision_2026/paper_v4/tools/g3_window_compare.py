"""G3 window comparator: restart reconstruction, CPU/GPU closed-loop equivalence, hard gates.

Read-only with respect to the runs it compares.  Applies the gates frozen in the
protocol, so tolerances cannot be tuned after seeing the result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

POSITION_INDEX = (0, 1, 6, 7, 12, 13, 18, 19, 24, 25)
HEADING_INDEX = (2, 8, 14, 20, 26)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def compare(source_raw, source_index, run_raw, run_index, ticks) -> dict:
    """Align by tick_index so a windowed run cannot be silently mis-indexed."""
    run_ticks = run_raw[:, run_index["tick_index"]].astype(int)
    positions = []
    for tick in ticks:
        matches = np.flatnonzero(run_ticks == tick)
        if matches.size != 1:
            raise ValueError(f"TICK_NOT_UNIQUELY_PRESENT:{tick}:{matches.size}")
        positions.append(int(matches[0]))
    rows = np.asarray(positions, dtype=int)
    source_rows = np.asarray(ticks, dtype=int)
    source_state = source_raw[np.ix_(source_rows, [source_index[f"x{i}"] for i in range(30)])]
    run_state = run_raw[np.ix_(rows, [run_index[f"x{i}"] for i in range(30)])]
    state_delta = np.abs(run_state - source_state)
    force_source = source_raw[np.ix_(source_rows, [source_index[f"point_force_norm{i}"] for i in range(4)])]
    force_run = run_raw[np.ix_(rows, [run_index[f"point_force_norm{i}"] for i in range(4)])]
    return {
        "ticks": [int(t) for t in ticks],
        "position_max_abs_per_tick_m": state_delta[:, list(POSITION_INDEX)].max(axis=1).tolist(),
        "heading_max_abs_per_tick_rad": state_delta[:, list(HEADING_INDEX)].max(axis=1).tolist(),
        "state_max_abs_m": float(state_delta.max()),
        "position_max_abs_m": float(state_delta[:, list(POSITION_INDEX)].max()),
        "heading_max_abs_rad": float(state_delta[:, list(HEADING_INDEX)].max()),
        "force_source_peak_n": float(force_source.max()),
        "force_run_peak_n": float(force_run.max()),
        "force_peak_relative_difference": float(abs(force_run.max() - force_source.max()) / max(force_source.max(), np.finfo(float).tiny)),
        "force_series_source": force_source.tolist(),
        "force_series_run": force_run.tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "G3-CLOSED-LOOP-WINDOW-v1":
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["comparison_output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    gates = protocol["gates"]
    results = []
    for window in protocol["windows"]:
        source_run = paper / window["source_run"]
        source_raw, source_columns = load_archive(source_run / "raw.npz")
        source_index = {name: position for position, name in enumerate(source_columns)}
        first_tick = int(window["start_tick"])
        ticks = list(range(first_tick, first_tick + int(window["ticks"])))
        entry = {"window": window["name"], "start_tick": first_tick, "ticks": int(window["ticks"]), "backends": {}}
        for run in protocol["runs"]:
            if run["window"] != window["name"]:
                continue
            run_dir = paper / run["output"]
            metrics_path = run_dir / "metrics.json"
            if not metrics_path.is_file():
                entry["backends"][run["backend"]] = {"status": "RUN_MISSING_OR_INCOMPLETE", "run": run["output"]}
                continue
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            run_raw, run_columns = load_archive(run_dir / "raw.npz")
            run_index = {name: position for position, name in enumerate(run_columns)}
            comparison = compare(source_raw, source_index, run_raw, run_index, ticks)
            entry["backends"][run["backend"]] = {
                "status": metrics["status"], "reason": metrics.get("reason"), "run": run["output"],
                "maximum_point_force_n": metrics["maximum_point_force_n"],
                "maximum_tire_utilization": metrics["maximum_tire_utilization"],
                "minimum_support_load_n": metrics["minimum_support_load_n"],
                "wall_s": metrics["wall_s"], "comparison": comparison,
                "replay_closure": metrics.get("replay_closure"),
            }
        # ---- gate verdicts, frozen in the protocol --------------------------
        cpu = entry["backends"].get("cpu", {})
        gpu = entry["backends"].get("gpu", {})
        verdicts = {}
        verdicts["cpu_run_completed"] = cpu.get("status") == "COMPLETED"
        verdicts["gpu_run_completed"] = gpu.get("status") == "COMPLETED"
        if "comparison" in cpu:
            verdicts["restart_position_within_tolerance"] = cpu["comparison"]["position_max_abs_m"] <= gates["restart_position_atol_m"]
            verdicts["restart_heading_within_tolerance"] = cpu["comparison"]["heading_max_abs_rad"] <= gates["restart_heading_atol_rad"]
        else:
            verdicts["restart_position_within_tolerance"] = False
            verdicts["restart_heading_within_tolerance"] = False
        if "comparison" in gpu:
            verdicts["gpu_position_within_tolerance"] = gpu["comparison"]["position_max_abs_m"] <= gates["window_position_atol_m"]
            verdicts["gpu_heading_within_tolerance"] = gpu["comparison"]["heading_max_abs_rad"] <= gates["window_heading_atol_rad"]
            verdicts["gpu_force_peak_within_tolerance"] = gpu["comparison"]["force_peak_relative_difference"] <= gates["window_force_peak_relative"]
        else:
            verdicts["gpu_position_within_tolerance"] = False
            verdicts["gpu_heading_within_tolerance"] = False
            verdicts["gpu_force_peak_within_tolerance"] = False
        physical = []
        for name, payload in (("cpu", cpu), ("gpu", gpu)):
            if "status" not in payload:
                physical.append(False)
                continue
            physical.append(
                payload["status"] == "COMPLETED"
                and payload["maximum_point_force_n"] <= gates["original_ultimate_force_n"] + 1e-6
                and payload["maximum_tire_utilization"] <= gates["original_tire_limit"] + 1e-9
                and payload["minimum_support_load_n"] >= 0.0
            )
        verdicts["original_hard_gates_hold"] = all(physical)
        entry["verdicts"] = verdicts
        entry["pass"] = all(verdicts.values())
        results.append(entry)

    report = {
        "status": "PASS_G3_ALL_WINDOWS" if all(item["pass"] for item in results) else "FAIL_G3_STOP",
        "scope": protocol["scope"],
        "parameter_id": protocol["parameter_id"],
        "gates": gates,
        "windows": results,
        "decision_rule": protocol["decision_rule"],
    }
    (output / "g3_restart_equivalence.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ------------------------------------------------------------
    figure, axes = plt.subplots(2, 2, figsize=(14.5, 9.2))
    names = [item["window"] for item in results]
    width = 0.36
    positions = np.arange(len(results))
    restart_pos = [item["backends"].get("cpu", {}).get("comparison", {}).get("position_max_abs_m", np.nan) for item in results]
    gpu_pos = [item["backends"].get("gpu", {}).get("comparison", {}).get("position_max_abs_m", np.nan) for item in results]
    restart_head = [item["backends"].get("cpu", {}).get("comparison", {}).get("heading_max_abs_rad", np.nan) for item in results]
    gpu_head = [item["backends"].get("gpu", {}).get("comparison", {}).get("heading_max_abs_rad", np.nan) for item in results]

    floor = 1e-16
    axes[0, 0].bar(positions - width / 2, np.maximum(restart_pos, floor), width, label="CPU replay vs saved", color="#1f77b4")
    axes[0, 0].bar(positions + width / 2, np.maximum(gpu_pos, floor), width, label="GPU replay vs saved", color="#ff7f0e")
    axes[0, 0].axhline(gates["restart_position_atol_m"], color="#1f77b4", linestyle=":", label=f"restart gate {gates['restart_position_atol_m']:.0e} m")
    axes[0, 0].axhline(gates["window_position_atol_m"], color="#ff7f0e", linestyle="--", label=f"window gate {gates['window_position_atol_m']:.0e} m")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set(xticks=positions, xticklabels=names, ylabel="max position deviation (m, log)",
                   title="Checkpoint reconstruction and GPU closed-loop divergence\nworst over the window, per backend")
    axes[0, 0].legend(fontsize=7.5)
    axes[0, 0].grid(axis="y", which="both", alpha=0.25)

    axes[0, 1].bar(positions - width / 2, np.maximum(restart_head, 1e-18), width, label="CPU replay vs saved", color="#1f77b4")
    axes[0, 1].bar(positions + width / 2, np.maximum(gpu_head, 1e-18), width, label="GPU replay vs saved", color="#ff7f0e")
    axes[0, 1].axhline(gates["restart_heading_atol_rad"], color="#1f77b4", linestyle=":", label=f"restart gate {gates['restart_heading_atol_rad']:.0e} rad")
    axes[0, 1].axhline(gates["window_heading_atol_rad"], color="#ff7f0e", linestyle="--", label=f"window gate {np.rad2deg(gates['window_heading_atol_rad']):.3f} deg")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(xticks=positions, xticklabels=names, ylabel="max heading deviation (rad, log)",
                   title="Heading divergence\nradian gate shown for the restart, degrees for the window")
    axes[0, 1].legend(fontsize=7.5)
    axes[0, 1].grid(axis="y", which="both", alpha=0.25)

    force_window = next((item for item in results if "force" in item["window"]), results[0])
    source_series = force_window["backends"].get("cpu", {}).get("comparison", {}).get("force_series_source")
    if source_series:
        ticks = force_window["backends"]["cpu"]["comparison"]["ticks"]
        axes[1, 0].plot(ticks, np.max(source_series, axis=1), marker="o", markersize=3, label="saved P1 trajectory", color="#2ca02c")
        gpu_series = force_window["backends"].get("gpu", {}).get("comparison", {}).get("force_series_run")
        cpu_series = force_window["backends"].get("cpu", {}).get("comparison", {}).get("force_series_run")
        if cpu_series:
            axes[1, 0].plot(ticks, np.max(cpu_series, axis=1), marker="s", markersize=3, label="CPU replay", color="#1f77b4")
        if gpu_series:
            axes[1, 0].plot(ticks, np.max(gpu_series, axis=1), marker="^", markersize=3, label="GPU replay", color="#ff7f0e")
        axes[1, 0].set(xlabel="tick index", ylabel="max point force (N)",
                       title=f"Force-bearing window `{force_window['window']}` — largest connector force per tick")
        axes[1, 0].legend(fontsize=8)
        axes[1, 0].grid(alpha=0.25)

    labels, values, colors = [], [], []
    for item in results:
        for name, value in item["verdicts"].items():
            labels.append(f"{item['window'][:10]}/{name.replace('_', ' ')}")
            values.append(1.0 if value else 0.0)
            colors.append("#2ca02c" if value else "#8b0000")
    axes[1, 1].barh(np.arange(len(labels)), values, color=colors)
    axes[1, 1].set(yticks=np.arange(len(labels)), yticklabels=labels, xlim=(0, 1.35), xticks=(0, 1), xticklabels=("FAIL", "PASS"),
                   title=f"Frozen gate verdicts — overall {report['status']}")
    axes[1, 1].tick_params(axis="y", labelsize=6.5)
    axes[1, 1].grid(axis="x", alpha=0.25)

    figure.suptitle("G3 bounded closed-loop windows: checkpoint reconstruction, CPU/GPU equivalence, original hard gates", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.01, 1, 0.97))
    figures = []
    for suffix in ("png", "svg"):
        name = f"g3_windows.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "figures": figures,
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [{"path": "g3_restart_equivalence.json", "sha256": sha(output / "g3_restart_equivalence.json")}],
        "claim_boundary": "Bounded windows only. No full-route, real-time or P1-root-cause claim.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# G3 有界闭环短窗比较\n\n"
        "对每个窗口分别做两件事：①CPU后端从重建检查点重放，与已保存的P1行逐tick比较，用于验证检查点重建；"
        "②GPU后端从同一检查点闭环重放，与保存轨迹及CPU重放比较，用于验证CUDA后端的闭环等价性与原硬门。\n\n"
        "门在协议中事前冻结，比较器只读运行产物。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "windows": [
        {"window": item["window"], "pass": item["pass"], "verdicts": item["verdicts"]} for item in results
    ]}, indent=2, ensure_ascii=False))
    if report["status"] != "PASS_G3_ALL_WINDOWS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
