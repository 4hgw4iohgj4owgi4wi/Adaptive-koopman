from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import regenerate_all_figures_r42_20260514 as basefig


HERE = Path(__file__).resolve().parent
OUT = HERE / "figures" / "fig_nrkdcc_error_diagnostics.png"


def _row(rows, scenario: str, method: str):
    hit = rows[(rows["scenario"].eq(scenario)) & (rows["method"].eq(method))]
    if hit.empty:
        raise RuntimeError(f"missing E0 row: scenario={scenario}, method={method}")
    return hit.iloc[0]


def _limit_common_time(ax, traces) -> None:
    if not traces:
        return
    max_t = min(float(t[-1]) for t, _ in traces if len(t))
    ax.set_xlim(0.0, max_t)


def main() -> None:
    rows = basefig.load_e0_rows()
    scenarios = [
        ("dlc_comm_noise_high", "High communication degradation"),
        ("dlc_mixed_fault_noise", "Mixed fault/noise"),
    ]
    methods = ["baseline", "tf14_main", "tf14_phase_role"]

    fig, axes = plt.subplots(3, 2, figsize=(10.2, 9.25), sharex=False)
    fig.subplots_adjust(top=0.84, bottom=0.13, hspace=0.72, wspace=0.34)

    for col, (scenario, scenario_title) in enumerate(scenarios):
        team_ey_traces = []
        team_es_traces = []

        ax = axes[0, col]
        for method in methods:
            core = basefig.load_core(_row(rows, scenario, method)["core_npz"])
            t, _, ey, _ = basefig.team_errors(core)
            team_ey_traces.append((t, ey))
            ax.plot(t, ey, color=basefig.COLORS[method], lw=1.22, label=basefig.LABELS[method])
        _limit_common_time(ax, team_ey_traces)
        ax.set_title(f"{scenario_title}: team lateral error", pad=8)
        ax.set_ylabel("team e_y [m]")
        basefig.style_ax(ax, zero=True)

        ax = axes[1, col]
        for method in methods:
            core = basefig.load_core(_row(rows, scenario, method)["core_npz"])
            t, _, _, es = basefig.team_errors(core)
            team_es_traces.append((t, es))
            ax.plot(t, es, color=basefig.COLORS[method], lw=1.22, label=basefig.LABELS[method])
        _limit_common_time(ax, team_es_traces)
        ax.set_title(f"{scenario_title}: team longitudinal error", pad=8)
        ax.set_ylabel("team e_s [m]")
        ax.set_xlabel("time [s]")
        basefig.style_ax(ax, zero=True)

        ax = axes[2, col]
        for method, ls, alpha, lw in [
            ("baseline", ":", 0.58, 1.05),
            ("tf14_phase_role", "-", 0.95, 1.18),
        ]:
            core = basefig.load_core(_row(rows, scenario, method)["core_npz"])
            t, vehicle_errors = basefig.vehicle_ey(core)
            for i, e in enumerate(vehicle_errors):
                ax.plot(t, e, color=basefig.VEHICLE[i], lw=lw, ls=ls, alpha=alpha)
        ax.set_title(f"{scenario_title}: vehicle lateral error", pad=8)
        ax.set_ylabel("vehicle e_y [m]")
        ax.set_xlabel("time [s]")
        basefig.style_ax(ax, zero=True)

    method_handles = [
        Line2D([0], [0], color=basefig.COLORS[m], lw=1.35, label=basefig.LABELS[m])
        for m in methods
    ]
    vehicle_handles = [
        Line2D([0], [0], color=basefig.VEHICLE[i], lw=1.35, label=f"v{i + 1}")
        for i in range(4)
    ]
    style_handles = [
        Line2D([0], [0], color=basefig.TEXT, lw=1.2, ls=":", alpha=0.65, label="AKE-M vehicle"),
        Line2D([0], [0], color=basefig.TEXT, lw=1.2, ls="-", alpha=0.95, label="NR-KDCC vehicle"),
    ]

    fig.legend(handles=method_handles, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=3, frameon=False, fontsize=7.8)
    fig.legend(handles=style_handles + vehicle_handles, loc="lower center", bbox_to_anchor=(0.5, 0.025), ncol=6, frameon=False, fontsize=7.4)
    fig.suptitle("E0 representative team and vehicle error diagnostics", y=0.985, color=basefig.TEXT, fontsize=12)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
