import numpy as np


class RigidPayloadCoordinatorA2:
    """A2-specific rigid payload coordination helper.

    A2 uses a team-level controller. This helper keeps the rigid-body
    bookkeeping separate from the generic controller code so the version stays
    independently runnable.
    """

    def __init__(self, payload_module, payload_cfg):
        self.payload_module = payload_module
        self.payload_cfg = dict(payload_cfg)

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
        for k in range(num_steps):
            ref_states_k = self.payload_module.team_to_corner_states(
                team_ref_hist[k, :], payload_cfg=self.payload_cfg
            )
            for vid in range(num_vehicles):
                corner_hist[vid][k, :] = ref_states_k[vid]

        return {
            "team_ref_hist": team_ref_hist,
            "corner_ref_histories": corner_hist,
        }

    def build_reference_bundle(self, x_ref_raw, horizon_pad=0):
        ref_pack = self.build_corner_reference_histories(x_ref_raw)
        team_ref = ref_pack["team_ref_hist"]
        pad_rows = int(max(0, horizon_pad))
        if pad_rows > 0:
            team_ref_pad = np.vstack((team_ref, np.repeat(team_ref[-1:, :], pad_rows, axis=0)))
        else:
            team_ref_pad = team_ref.copy()
        ref_pack["team_ref_hist_padded"] = team_ref_pad
        return ref_pack

    def team_hist_to_corner_histories(self, team_state_hist):
        team_hist = np.asarray(team_state_hist, dtype=float)
        num_steps = team_hist.shape[0]
        num_vehicles = len(self.payload_cfg["corner_offsets"])
        corner_hist = [np.zeros((num_steps, 6), dtype=float) for _ in range(num_vehicles)]
        for k in range(num_steps):
            states_k = self.payload_module.team_to_corner_states(
                team_hist[k, :], payload_cfg=self.payload_cfg
            )
            for vid in range(num_vehicles):
                corner_hist[vid][k, :] = states_k[vid]
        return corner_hist

    def window_team_reference(self, ref_bundle, step_idx, horizon):
        team_ref = np.asarray(ref_bundle["team_ref_hist_padded"], dtype=float)
        k0 = int(step_idx)
        k1 = int(step_idx + horizon + 1)
        if k1 > team_ref.shape[0]:
            pad_rows = k1 - team_ref.shape[0]
            team_ref = np.vstack((team_ref, np.repeat(team_ref[-1:, :], pad_rows, axis=0)))
        return team_ref[k0:k1, :].T.copy()

    def compute_team_errors(self, team_state_hist, team_ref_hist):
        x_hist = np.asarray(team_state_hist, dtype=float)
        x_ref = np.asarray(team_ref_hist, dtype=float)
        n_eval = min(x_hist.shape[0], x_ref.shape[0])
        err = x_hist[:n_eval, :] - x_ref[:n_eval, :]
        return {
            "e_s": err[:, 0],
            "e_y": err[:, 1],
            "e_psi": err[:, 2],
            "e_vx": err[:, 3],
            "e_vy": err[:, 4],
            "e_r": err[:, 5],
        }

    def compute_corner_errors(self, corner_histories, corner_ref_histories):
        errors = []
        for x_hist, x_ref in zip(corner_histories, corner_ref_histories):
            x_hist = np.asarray(x_hist, dtype=float)
            x_ref = np.asarray(x_ref, dtype=float)
            n_eval = min(x_hist.shape[0], x_ref.shape[0])
            errors.append({
                "e_s": x_hist[:n_eval, 0] - x_ref[:n_eval, 0],
                "e_y": x_hist[:n_eval, 1] - x_ref[:n_eval, 1],
                "e_psi": x_hist[:n_eval, 2] - x_ref[:n_eval, 2],
            })
        return errors
