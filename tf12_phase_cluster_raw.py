"""TF12 wrapper for raw phase-cluster plotting.

This module keeps the TF12 import path stable:
    from tf12_phase_cluster_raw import plot_raw_phase_clusters
"""

from tf11_a1_phase_cluster_raw import (
    DEFAULT_PHASE_CLUSTER_CFG as _BASE_DEFAULT_PHASE_CLUSTER_CFG,
)
from tf11_a1_phase_cluster_raw import (
    plot_raw_phase_clusters as _plot_raw_phase_clusters,
)


DEFAULT_PHASE_CLUSTER_CFG = dict(_BASE_DEFAULT_PHASE_CLUSTER_CFG)
DEFAULT_PHASE_CLUSTER_CFG.update(
    {
        # Keep TF12 default naming and slightly denser initial-state cloud.
        "traj_only_samples": max(
            600, int(_BASE_DEFAULT_PHASE_CLUSTER_CFG.get("traj_only_samples", 520))
        ),
        "traj_only_len": max(
            130, int(_BASE_DEFAULT_PHASE_CLUSTER_CFG.get("traj_only_len", 120))
        ),
    }
)


def plot_raw_phase_clusters(
    *,
    main_result,
    team_state_hist,
    xt_actual_vehicles,
    dt,
    num_vehicles=4,
    cfg=None,
    save_path=None,
    show=True,
):
    run_cfg = dict(DEFAULT_PHASE_CLUSTER_CFG)
    if cfg:
        run_cfg.update(cfg)
    return _plot_raw_phase_clusters(
        main_result=main_result,
        team_state_hist=team_state_hist,
        xt_actual_vehicles=xt_actual_vehicles,
        dt=dt,
        num_vehicles=num_vehicles,
        cfg=run_cfg,
        save_path=save_path,
        show=show,
    )


__all__ = ["plot_raw_phase_clusters", "DEFAULT_PHASE_CLUSTER_CFG"]

