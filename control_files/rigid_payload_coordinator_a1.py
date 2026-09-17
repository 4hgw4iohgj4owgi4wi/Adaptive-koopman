import numpy as np


class RigidPayloadCoordinatorA1:
    """A1-specific rigid-payload coordination helper.

    This class intentionally lives beside the generic controllers so the A1
    version can keep its own runnable logic without mutating the shared TF
    pipeline.
    """

    def __init__(
        self,
        payload_module,
        payload_cfg,
        leader_idx=0,
        spread_blend=0.45,
        delta_spread_threshold=0.045,
        ax_spread_threshold=0.20,
        prev_u_smooth=0.18,
    ):
        self.payload_module = payload_module
        self.payload_cfg = dict(payload_cfg)
        self.leader_idx = int(leader_idx)
        self.spread_blend = float(spread_blend)
        self.delta_spread_threshold = float(delta_spread_threshold)
        self.ax_spread_threshold = float(ax_spread_threshold)
        self.prev_u_smooth = float(prev_u_smooth)

    def _as_team_ref_history(self, x_ref_raw):
        arr = np.asarray(x_ref_raw, dtype=float)
        if arr.ndim != 2:
            raise ValueError("x_ref_raw must be a 2D array")
        if arr.shape[0] == 6:
            return arr.T.copy()
        if arr.shape[1] == 6:
            return arr.copy()
        raise ValueError(f"x_ref_raw must have one axis of length 6, got {arr.shape}")

    def build_corner_reference_histories(self, x_ref_raw):
        team_ref_hist = self._as_team_ref_history(x_ref_raw)
        num_steps = team_ref_hist.shape[0]
        num_vehicles = len(self.payload_cfg["corner_offsets"])

        corner_hist = [np.zeros((num_steps, 6), dtype=float) for _ in range(num_vehicles)]
        leader_rel_targets = [np.zeros((num_steps, 2), dtype=float) for _ in range(num_vehicles)]

        for k in range(num_steps):
            ref_states_k = self.payload_module.team_to_corner_states(
                team_ref_hist[k, :], payload_cfg=self.payload_cfg
            )
            leader_state_k = ref_states_k[self.leader_idx]
            for vid in range(num_vehicles):
                corner_hist[vid][k, :] = ref_states_k[vid]
                leader_rel_targets[vid][k, 0] = ref_states_k[vid][0] - leader_state_k[0]
                leader_rel_targets[vid][k, 1] = ref_states_k[vid][1] - leader_state_k[1]

        return {
            "team_ref_hist": team_ref_hist,
            "corner_ref_histories": corner_hist,
            "leader_relative_targets": leader_rel_targets,
        }

    def build_mpc_reference_bundle(self, x_ref_raw, standardizer_x, horizon_pad=0):
        ref_pack = self.build_corner_reference_histories(x_ref_raw)
        pad_cols = int(max(0, horizon_pad))

        raw_vehicle_refs = []
        scaled_vehicle_refs = []
        mpc_vehicle_refs = []
        for ref_hist in ref_pack["corner_ref_histories"]:
            ref_raw_v = ref_hist.T.copy()
            ref_scaled_v = standardizer_x.transform(ref_hist).T
            if pad_cols > 0:
                ref_mpc_v = np.hstack(
                    (ref_scaled_v, np.tile(ref_scaled_v[:, -1].reshape(-1, 1), pad_cols))
                )
            else:
                ref_mpc_v = ref_scaled_v
            raw_vehicle_refs.append(ref_raw_v)
            scaled_vehicle_refs.append(ref_scaled_v)
            mpc_vehicle_refs.append(ref_mpc_v)

        ref_pack["raw_vehicle_refs"] = raw_vehicle_refs
        ref_pack["scaled_vehicle_refs"] = scaled_vehicle_refs
        ref_pack["mpc_vehicle_refs"] = mpc_vehicle_refs
        return ref_pack

    def aggregate_controls(self, u_vehicle_stack, prev_team_u=None):
        u_arr = np.asarray(u_vehicle_stack, dtype=float)
        if u_arr.ndim != 2 or u_arr.shape[1] != 2:
            raise ValueError("u_vehicle_stack must have shape (n_vehicle, 2)")

        u_mean = np.mean(u_arr, axis=0)
        u_med = np.median(u_arr, axis=0)
        delta_spread = float(np.std(u_arr[:, 0]))
        ax_spread = float(np.std(u_arr[:, 1]))

        delta_mix = np.clip(
            (delta_spread - self.delta_spread_threshold) / max(self.delta_spread_threshold, 1e-6),
            0.0,
            1.0,
        ) * self.spread_blend
        ax_mix = np.clip(
            (ax_spread - self.ax_spread_threshold) / max(self.ax_spread_threshold, 1e-6),
            0.0,
            1.0,
        ) * self.spread_blend

        u_team = np.array(
            [
                (1.0 - delta_mix) * u_mean[0] + delta_mix * u_med[0],
                (1.0 - ax_mix) * u_mean[1] + ax_mix * u_med[1],
            ],
            dtype=float,
        )
        if prev_team_u is not None:
            prev_team_u = np.asarray(prev_team_u, dtype=float).reshape(-1)
            if prev_team_u.shape[0] == 2:
                u_team = self.prev_u_smooth * prev_team_u + (1.0 - self.prev_u_smooth) * u_team

        diag = {
            "delta_spread": delta_spread,
            "ax_spread": ax_spread,
            "delta_mean": float(u_mean[0]),
            "ax_mean": float(u_mean[1]),
            "delta_median": float(u_med[0]),
            "ax_median": float(u_med[1]),
            "delta_mix": float(delta_mix),
            "ax_mix": float(ax_mix),
        }
        return u_team, diag

    def get_vehicle_step_ref(self, ref_bundle, vehicle_idx, step_idx):
        ref_hist = ref_bundle["corner_ref_histories"][int(vehicle_idx)]
        idx = int(np.clip(step_idx, 0, ref_hist.shape[0] - 1))
        return ref_hist[idx, :].copy()

    def get_leader_relative_target(self, ref_bundle, vehicle_idx, step_idx):
        rel_hist = ref_bundle["leader_relative_targets"][int(vehicle_idx)]
        idx = int(np.clip(step_idx, 0, rel_hist.shape[0] - 1))
        return {
            "ds": float(rel_hist[idx, 0]),
            "dey": float(rel_hist[idx, 1]),
        }

    def compute_vehicle_errors(self, x_hist, ref_hist):
        x_hist = np.asarray(x_hist, dtype=float)
        ref_hist = np.asarray(ref_hist, dtype=float)
        n_eval = min(x_hist.shape[0], ref_hist.shape[0])
        e_long = x_hist[:n_eval, 0] - ref_hist[:n_eval, 0]
        e_lat = x_hist[:n_eval, 1] - ref_hist[:n_eval, 1]
        return e_long, e_lat
