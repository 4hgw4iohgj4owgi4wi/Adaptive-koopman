import numpy as np
from scipy import sparse

class linear_Dynamics:
    """
    定义线性系统动力学（支持稀疏矩阵，兼容多车编队 block_diag）
    """

    def __init__(self, A, B, C):
        """
        :param A: 离散漂移矩阵 (稀疏或稠密)
        :param B: 离散输入矩阵 (稀疏或稠密)
        :param C: 输出矩阵 (稀疏或稠密)
        """
        # ====================== 关键修复：统一转为 csc 格式 ======================
        self.A = sparse.csc_matrix(A) if not sparse.issparse(A) else A
        self.B = sparse.csc_matrix(B) if not sparse.issparse(B) else B
        self.C = sparse.csc_matrix(C) if not sparse.issparse(C) else C

        self.nz = self.A.shape[0]   # lifted states 维度（多车为 92）
        self.nx = self.C.shape[0]   # base states 维度（多车为 24）
        self.m = int(self.B.shape[1])  # 控制输入维度（多车为 8）

    def eval_dot(self, z, u, t=None):
        """
        计算 z_{k+1} = A z + B u
        """
        return self.A @ z + self.B @ u

    def get_linearization(self, z0, z1, u):
        """
        计算线性化矩阵（多车场景下 A、B 已为 block_diag）
        """
        # 转为稠密数组（因为后续 construct_constraint_matrix_data_ 需要数值运算）
        A_lin = self.A.toarray()
        B_lin = self.B.toarray()

        z_next = self.eval_dot(z0, u)

        r_lin = z_next - z1

        return A_lin, B_lin, r_lin