# =============================================================================
# koopman_linear_gpu.py
# Koopman DNN — 完整GPU优化版（兼容主脚本所有调用接口）
# =============================================================================

import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader, TensorDataset


# =============================================================================
# 1. KoopmanNet_linear — 基础网络（无控制输入）
# =============================================================================

class KoopmanNet_linear(nn.Module):
    """
    基础线性Koopman网络。
    支持：
      - net_params 字典初始化
      - standardizer_x 标准化
      - first_obs_const（第一个观测维度固定为常数1）
      - override_C（是否用单位阵覆盖解码矩阵C）
      - 特征值损失（eig_loss）
      - lifted空间正则损失
      - L1 / L2 正则
    """

    def __init__(self,
                 params: dict,
                 standardizer_x=None,
                 device: torch.device = None):
        super().__init__()

        # ── 设备 ──────────────────────────────────────────────────────────────
        self.device = (device if device is not None
                       else torch.device("cuda" if torch.cuda.is_available() else "cpu"))

        # ── 超参数解析 ─────────────────────────────────────────────────────────
        self.state_dim          = params["state_dim"]
        self.encoder_hidden_w   = params.get("encoder_hidden_width", 128)
        self.encoder_hidden_d   = params.get("encoder_hidden_depth", 2)
        self.encoder_output_dim = params.get("encoder_output_dim", 16)
        self.activation_type    = params.get("activation_type", "tanh")
        self.first_obs_const    = params.get("first_obs_const", True)
        self.override_C         = params.get("override_C", True)
        self.dt                 = params.get("dt", 0.1)

        # 损失系数
        self.eig_loss          = params.get("eig_loss", False)
        self.eig_loss_coeff    = params.get("eig_loss_coeff", 0.0)
        self.lifted_loss_pen   = params.get("lifted_loss_penalty", 0.0)
        self.l2_reg            = params.get("l2_reg", 0.0)
        self.l1_reg            = params.get("l1_reg", 0.0)
        # loss_mode: "delta" | "absolute" | "hybrid"
        self.loss_mode         = str(params.get("loss_mode", "delta")).lower().strip()
        self.delta_loss_use_scale = bool(params.get("delta_loss_use_scale", True))
        self.delta_scale_min   = float(params.get("delta_scale_min", 1e-3))
        # hybrid mode: pred = w_abs * abs_loss + w_delta * delta_loss
        self.hybrid_abs_weight = float(params.get("hybrid_abs_weight", 1.0))
        self.hybrid_delta_weight = float(params.get("hybrid_delta_weight", 0.15))
        # logging
        self.log_process_align = bool(params.get("log_process_align", False))

        # 标准化器
        self.standardizer_x = standardizer_x

        # ── lifted 维度 ────────────────────────────────────────────────────────
        # 若 first_obs_const=True，第0维固定=1，故 lifted_dim = encoder_output_dim
        # 原始状态维度也并入 lifted 空间（常见 Koopman 设计）：
        #   z = [1, x, phi(x)]  → total = 1 + state_dim + encoder_output_dim
        if self.first_obs_const:
            self.lifted_dim = 1 + self.state_dim + self.encoder_output_dim
        else:
            self.lifted_dim = self.state_dim + self.encoder_output_dim

        # ── 网络层构建 ─────────────────────────────────────────────────────────
        self._build_encoder()
        self._build_dynamics()
        # delta loss 归一化尺度（在 process(train_mode=True) 中根据训练集刷新）
        self.register_buffer("delta_scale_x", torch.ones(self.state_dim, dtype=torch.float32))

        self.to(self.device)

    # ──────────────────────────────────────────────────────────────────────────
    # 网络构建
    # ──────────────────────────────────────────────────────────────────────────

    def _get_activation(self):
        act_map = {
            "tanh":    nn.Tanh(),
            "relu":    nn.ReLU(),
            "elu":     nn.ELU(),
            "gelu":    nn.GELU(),
            "sigmoid": nn.Sigmoid(),
        }
        return act_map.get(self.activation_type, nn.Tanh())

    def _build_encoder(self):
        """构建多层编码器 φ: R^n → R^encoder_output_dim"""
        layers = []
        in_dim = self.state_dim
        for _ in range(self.encoder_hidden_d):
            layers += [nn.Linear(in_dim, self.encoder_hidden_w), self._get_activation()]
            in_dim = self.encoder_hidden_w
        layers.append(nn.Linear(in_dim, self.encoder_output_dim))
        self.encoder = nn.Sequential(*layers)

    def _build_dynamics(self):
        """构建 Koopman 动力学矩阵 A 和解码矩阵 C"""
        # Koopman 矩阵 A：lifted_dim × lifted_dim
        self.A = nn.Linear(self.lifted_dim, self.lifted_dim, bias=False)
        nn.init.eye_(self.A.weight)          # 初始化为单位阵（稳定性好）

        # 解码矩阵 C：lifted_dim → state_dim
        self.C = nn.Linear(self.lifted_dim, self.state_dim, bias=False)
        if self.override_C:
            # 固定 C = [0 | I | 0]（提取 lifted 向量中原始状态部分）
            # z 结构：[const(1), x(state_dim), phi(encoder_output_dim)]
            with torch.no_grad():
                C_fixed = torch.zeros(self.state_dim, self.lifted_dim)
                offset = 1 if self.first_obs_const else 0
                C_fixed[:, offset:offset + self.state_dim] = torch.eye(self.state_dim)
                self.C.weight.copy_(C_fixed)
            # 冻结 C（override 时不参与训练）
            self.C.weight.requires_grad_(False)

    # ──────────────────────────────────────────────────────────────────────────
    # 核心方法
    # ──────────────────────────────────────────────────────────────────────────

    def lift(self, x: torch.Tensor) -> torch.Tensor:
        """
        将原始状态 x 提升到 Koopman 空间。
        z = [1, x, φ(x)]  （若 first_obs_const=True）
        z = [x, φ(x)]     （否则）
        """
        phi = self.encoder(x)                          # (B, encoder_output_dim)
        if self.first_obs_const:
            ones = torch.ones(x.shape[0], 1, device=self.device)
            z = torch.cat([ones, x, phi], dim=-1)      # (B, 1+n+p)
        else:
            z = torch.cat([x, phi], dim=-1)            # (B, n+p)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.C(z)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """一步Koopman传播：z_next = A z"""
        return self.A(z)

    def process(self,
                data_x: np.ndarray,
                data_u: np.ndarray = None,
                train_mode: bool = True) -> tuple:
        """
        最严格对齐版 process：完全以 data_x 的有效长度为基准，强制同步 u
        """
        if data_x is None:
            raise ValueError("data_x cannot be None")

        N, T, n = data_x.shape

        # 关键：强制使用与对齐后轨迹长度一致的切片
        # 对齐后 T=499，因此 T-1 = 498
        effective_T = T  # 已经是对齐后的长度

        X_curr = data_x[:, :effective_T - 1, :].reshape(-1, n)  # (N*(T-1), state_dim)
        X_next = data_x[:, 1:effective_T, :].reshape(-1, n)  # (N*(T-1), state_dim)

        if self.standardizer_x is not None:
            X_curr = self.standardizer_x.transform(X_curr)
            X_next = self.standardizer_x.transform(X_next)

        if data_u is not None:
            # 以 X_curr 的样本数为绝对基准
            effective_samples = X_curr.shape[0]

            # u 的切片（使用相同 effective_T-1）
            U_curr = data_u[:, :effective_T - 1, :].reshape(-1, self.ctrl_dim)

            # 安全检查 + 强制对齐
            if U_curr.shape[0] != effective_samples:
                print(f"[WARN] U_curr sample mismatch: {U_curr.shape[0]} vs X_curr {effective_samples}. Truncating.")
                min_samples = min(U_curr.shape[0], effective_samples)
                U_curr = U_curr[:min_samples]
                X_curr = X_curr[:min_samples]
                X_next = X_next[:min_samples]
            else:
                if self.log_process_align:
                    print(f"[INFO] U_curr aligned with X_curr: {effective_samples} samples")

            if self.standardizer_u is not None:
                U_curr = self.standardizer_u.transform(U_curr)

            # 拼接
            X_in = np.concatenate([X_curr, U_curr], axis=-1)
        else:
            X_in = X_curr

        # 使用训练数据更新 delta loss 的归一化尺度（在 scaled 空间计算）
        if train_mode:
            delta_x = X_next - X_curr
            scale = np.std(delta_x, axis=0)
            scale = np.where(np.isfinite(scale), scale, 1.0)
            scale = np.maximum(scale, self.delta_scale_min)
            with torch.no_grad():
                self.delta_scale_x.copy_(
                    torch.from_numpy(scale.astype(np.float32)).to(self.device)
                )

        return X_in.astype(np.float32), X_next.astype(np.float32)

    def loss(self,
             x_curr: torch.Tensor,
             x_next: torch.Tensor) -> tuple:
        """
        计算总损失。

        Returns
        -------
        (total_loss, pred_loss, lifted_loss)
        """
        z_curr = self.lift(x_curr)           # (B, lifted_dim)
        z_next_pred = self.forward(z_curr)   # (B, lifted_dim)

        # 预测损失（支持 absolute / delta 两种形式）
        x_next_pred = self.decode(z_next_pred)
        if self.loss_mode == "delta":
            delta_true = x_next - x_curr
            delta_pred = x_next_pred - x_curr
            if self.delta_loss_use_scale:
                denom = self.delta_scale_x.unsqueeze(0).clamp_min(self.delta_scale_min)
                pred_loss = torch.mean(((delta_true - delta_pred) / denom) ** 2)
            else:
                pred_loss = torch.mean((delta_true - delta_pred) ** 2)
        elif self.loss_mode == "hybrid":
            abs_loss = torch.mean((x_next - x_next_pred) ** 2)
            delta_true = x_next - x_curr
            delta_pred = x_next_pred - x_curr
            if self.delta_loss_use_scale:
                denom = self.delta_scale_x.unsqueeze(0).clamp_min(self.delta_scale_min)
                delta_loss = torch.mean(((delta_true - delta_pred) / denom) ** 2)
            else:
                delta_loss = torch.mean((delta_true - delta_pred) ** 2)
            pred_loss = self.hybrid_abs_weight * abs_loss + self.hybrid_delta_weight * delta_loss
        else:
            pred_loss = torch.mean((x_next - x_next_pred) ** 2)

        # lifted 空间线性一致性损失
        with torch.no_grad():
            z_next_true = self.lift(x_next)
        lifted_loss = torch.mean((z_next_true - z_next_pred) ** 2)

        total = pred_loss + self.lifted_loss_pen * lifted_loss

        # 特征值损失（鼓励 A 的谱半径 ≤ 1，提升稳定性）
        if self.eig_loss and self.training:
            eigvals = torch.linalg.eigvals(self.A.weight)
            eig_penalty = torch.mean(torch.relu(eigvals.abs() - 1.0))
            total = total + self.eig_loss_coeff * eig_penalty

        # L2 正则（weight_decay 之外的补充）
        if self.l2_reg > 0:
            l2 = sum(p.pow(2).sum() for p in self.encoder.parameters())
            total = total + self.l2_reg * l2

        # L1 正则
        if self.l1_reg > 0:
            l1 = sum(p.abs().sum() for p in self.encoder.parameters())
            total = total + self.l1_reg * l1

        return total, pred_loss, lifted_loss


# =============================================================================
# 2. KoopmanNetCtrl_linear — 带控制输入的扩展
# =============================================================================
class KoopmanNetCtrl_linear(KoopmanNet_linear):
    """
    带控制输入的线性Koopman网络。
    Koopman动力学：z_{t+1} = A z_t + B u_t
    """

    def __init__(self,
                 params: dict,
                 standardizer_x=None,
                 standardizer_u=None,
                 device: torch.device = None):
        super().__init__(params, standardizer_x=standardizer_x, device=device)

        self.ctrl_dim       = params["ctrl_dim"]
        self.standardizer_u = standardizer_u

        # 控制矩阵 B：lifted_dim × ctrl_dim
        self.B = nn.Linear(self.ctrl_dim, self.lifted_dim, bias=False)
        nn.init.zeros_(self.B.weight)

        self.to(self.device)

    def forward(self, z: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        """z_next = A z + B u"""
        return self.A(z) + self.B(u)

    # 注意：这里不要再写 process 方法！让它继承父类的严格版本

    def loss(self,
             xu_curr: torch.Tensor,
             x_next: torch.Tensor) -> tuple:
        x_curr = xu_curr[:, :self.state_dim]
        u_curr = xu_curr[:, self.state_dim:]

        z_curr    = self.lift(x_curr)
        z_next_pred = self.forward(z_curr, u_curr)

        x_next_pred = self.decode(z_next_pred)
        if self.loss_mode == "delta":
            delta_true = x_next - x_curr
            delta_pred = x_next_pred - x_curr
            if self.delta_loss_use_scale:
                denom = self.delta_scale_x.unsqueeze(0).clamp_min(self.delta_scale_min)
                pred_loss = torch.mean(((delta_true - delta_pred) / denom) ** 2)
            else:
                pred_loss = torch.mean((delta_true - delta_pred) ** 2)
        elif self.loss_mode == "hybrid":
            abs_loss = torch.mean((x_next - x_next_pred) ** 2)
            delta_true = x_next - x_curr
            delta_pred = x_next_pred - x_curr
            if self.delta_loss_use_scale:
                denom = self.delta_scale_x.unsqueeze(0).clamp_min(self.delta_scale_min)
                delta_loss = torch.mean(((delta_true - delta_pred) / denom) ** 2)
            else:
                delta_loss = torch.mean((delta_true - delta_pred) ** 2)
            pred_loss = self.hybrid_abs_weight * abs_loss + self.hybrid_delta_weight * delta_loss
        else:
            pred_loss = torch.mean((x_next - x_next_pred) ** 2)

        with torch.no_grad():
            z_next_true = self.lift(x_next)
        lifted_loss = torch.mean((z_next_true - z_next_pred) ** 2)

        total = pred_loss + self.lifted_loss_pen * lifted_loss

        if self.eig_loss and self.training:
            eigvals    = torch.linalg.eigvals(self.A.weight)
            eig_penalty = torch.mean(torch.relu(eigvals.abs() - 1.0))
            total      = total + self.eig_loss_coeff * eig_penalty

        if self.l2_reg > 0:
            l2    = sum(p.pow(2).sum() for p in self.encoder.parameters())
            total = total + self.l2_reg * l2

        if self.l1_reg > 0:
            l1    = sum(p.abs().sum() for p in self.encoder.parameters())
            total = total + self.l1_reg * l1

        return total, pred_loss, lifted_loss


# =============================================================================
# 3. KoopDNN_linear — 训练 & 模型封装
# =============================================================================

class KoopDNN_linear:
    """
    Koopman DNN 训练封装。
    兼容主脚本的所有调用接口：
      - set_datasets()
      - model_pipeline()
      - construct_koopman_model()
      - train_loss_hist / val_loss_hist
    """

    def __init__(self, net: KoopmanNet_linear):
        self.net    = net
        self.device = net.device

        # 数据集（由 set_datasets 填充）
        self.x_train = self.u_train = None
        self.x_val   = self.u_val   = None

        # DataLoader（由外部注入或 model_pipeline 内部构建）
        self.train_loader = None
        self.val_loader   = None

        # 损失历史：每个元素 = (total, pred, lifted)
        self.train_loss_hist = []
        self.val_loss_hist   = []

        # AMP
        if self.device.type == "cuda":
            self.scaler  = torch.amp.GradScaler("cuda", enabled=True)
            self.use_amp = True
        else:
            self.scaler  = None
            self.use_amp = False

    # ──────────────────────────────────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────────────────────────────────

    def set_datasets(self,
                     x_train: np.ndarray,
                     u_train: np.ndarray = None,
                     x_val:   np.ndarray = None,
                     u_val:   np.ndarray = None):
        """存储原始轨迹数据（主脚本调用）"""
        self.x_train = x_train
        self.u_train = u_train
        self.x_val   = x_val
        self.u_val   = u_val

    def model_pipeline(self,
                       net_params: dict,
                       print_epoch: bool = True):
        """
        主训练流水线（主脚本调用）。
        若外部已注入 train_loader / val_loader，直接使用；
        否则内部自动构建。
        """
        lr         = net_params.get("lr", 1e-3)
        epochs     = net_params.get("epochs", 100)
        batch_size = net_params.get("batch_size", 512)

        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=lr)
        # ====================== 【新增】学习率调度 ======================
        # 推荐使用 CosineAnnealingLR（平滑衰减，适合300 epoch左右的训练）
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=epochs,      # 完整周期 = 总epoch数
            eta_min=1e-6       # 最低学习率
        )

        # 如果你更喜欢根据验证损失自适应衰减，可以改用下面这行（二选一）：
        # self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        #     self.optimizer, mode='min', factor=0.5, patience=15,
        #     verbose=True, min_lr=1e-6
        # )
        # ── 构建 DataLoader（若外部未注入）────────────────────────────────────
        if self.train_loader is None:
            self.train_loader, self.val_loader = self._build_loaders(batch_size)

        # ── 训练循环 ───────────────────────────────────────────────────────────
        self._train_loop(epochs, print_epoch)

    def construct_koopman_model(self):
        """
        训练完成后提取 Koopman 矩阵（numpy格式），供 MPC 使用。
        统一赋值到 self.C_np（不再混用 C / C_np）。
        """
        self.net.eval()
        with torch.no_grad():
            self.A_lin = self.net.A.weight.detach().cpu().numpy()   # (lifted, lifted)
            self.C_np  = self.net.C.weight.detach().cpu().numpy()   # (state, lifted)

            if isinstance(self.net, KoopmanNetCtrl_linear):
                self.B_lin = self.net.B.weight.detach().cpu().numpy()  # (lifted, ctrl)

        print(f"[INFO] Koopman model built | A: {self.A_lin.shape}"
              + (f" | B: {self.B_lin.shape}" if hasattr(self, "B_lin") else "")
              + f" | C: {self.C_np.shape}")

    # ──────────────────────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────────────────────

    def _build_loaders(self, batch_size: int):
        """内部自动从原始轨迹数据构建 DataLoader"""
        X_tr, y_tr = self.net.process(self.x_train, self.u_train, train_mode=True)
        X_va, y_va = self.net.process(self.x_val,   self.u_val,   train_mode=False)

        train_ds = TensorDataset(
            torch.from_numpy(X_tr),
            torch.from_numpy(y_tr)
        )
        val_ds = TensorDataset(
            torch.from_numpy(X_va),
            torch.from_numpy(y_va)
        )

        train_loader = DataLoader(
            train_ds,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=(self.device.type == "cuda"),
            drop_last=True
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=(self.device.type == "cuda")
        )
        return train_loader, val_loader

    def _train_loop(self, epochs: int, print_epoch: bool):
        """核心训练循环（AMP + 梯度裁剪）"""
        for epoch in range(epochs):

            # ── 训练阶段 ───────────────────────────────────────────────────────
            self.net.train()
            tr_total = tr_pred = tr_lifted = 0.0

            for X_batch, y_batch in self.train_loader:
                X_batch = X_batch.to(self.device, non_blocking=True)
                y_batch = y_batch.to(self.device, non_blocking=True)

                self.optimizer.zero_grad(set_to_none=True)

                if self.use_amp:
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        total, pred, lifted = self.net.loss(X_batch, y_batch)
                    self.scaler.scale(total).backward()
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.net.parameters(), max_norm=1.0)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    total, pred, lifted = self.net.loss(X_batch, y_batch)
                    total.backward()
                    torch.nn.utils.clip_grad_norm_(self.net.parameters(), max_norm=1.0)
                    self.optimizer.step()

                n = len(self.train_loader)
                tr_total  += total.item()  / n
                tr_pred   += pred.item()   / n
                tr_lifted += lifted.item() / n

            self.train_loss_hist.append((tr_total, tr_pred, tr_lifted))

            # ── 验证阶段 ───────────────────────────────────────────────────────
            va_total = va_pred = va_lifted = 0.0
            if self.val_loader is not None:
                self.net.eval()
                with torch.no_grad():
                    for X_batch, y_batch in self.val_loader:
                        X_batch = X_batch.to(self.device, non_blocking=True)
                        y_batch = y_batch.to(self.device, non_blocking=True)

                        if self.use_amp:
                            with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                                total, pred, lifted = self.net.loss(X_batch, y_batch)
                        else:
                            total, pred, lifted = self.net.loss(X_batch, y_batch)

                        n = len(self.val_loader)
                        va_total  += total.item()  / n
                        va_pred   += pred.item()   / n
                        va_lifted += lifted.item() / n

            self.val_loss_hist.append((va_total, va_pred, va_lifted))
            # ====================== 【新增】更新学习率 ======================
            # CosineAnnealingLR 在每个epoch结束调用 step()
            self.scheduler.step()

            # 如果你用的是 ReduceLROnPlateau，则改成下面这行（传入 val loss）：
            # self.scheduler.step(va_total)   # 或 va_pred
            # ── 打印 ────────────────────────────────────────────────────────────
            if print_epoch and (epoch + 1) % 10 == 0:
                print(f"Epoch [{epoch+1:>4}/{epochs}] "
                      f"| Train  total={tr_total:.4e}  pred={tr_pred:.4e}  lifted={tr_lifted:.4e}"
                      f"| Val    total={va_total:.4e}  pred={va_pred:.4e}  lifted={va_lifted:.4e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 推理工具
    # ──────────────────────────────────────────────────────────────────────────

    def lift_np(self, x: np.ndarray) -> np.ndarray:
        """将 numpy 状态 (T, n) 提升到 Koopman 空间 (T, lifted_dim)"""
        self.net.eval()
        with torch.no_grad():
            xt = torch.from_numpy(x.astype(np.float32)).to(self.device)
            return self.net.lift(xt).cpu().numpy()

    def predict(self,
                x0:    np.ndarray,
                steps: int = 1,
                u_seq: np.ndarray = None) -> np.ndarray:
        """多步开环预测 (numpy接口)"""
        self.net.eval()
        with torch.no_grad():
            x   = torch.from_numpy(x0.astype(np.float32)).unsqueeze(0).to(self.device)
            z   = self.net.lift(x)
            traj = [x0]

            for t in range(steps):
                if u_seq is not None and isinstance(self.net, KoopmanNetCtrl_linear):
                    u_t = torch.from_numpy(
                        u_seq[t].astype(np.float32)
                    ).unsqueeze(0).to(self.device)
                    z = self.net.forward(z, u_t)
                else:
                    z = self.net.forward(z)

                x_pred = self.net.decode(z)
                traj.append(x_pred.squeeze(0).cpu().numpy())

            return np.array(traj)
