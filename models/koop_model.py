# import torch
# import numpy as np
# from core.koopman_core import KoopDNN,KoopmanNet,KoopmanNetCtrl
#
# def model_matricies(file):
#     model_koop_dnn = torch.load(file)
#     # Koopman model parameters
#     A = np.array(model_koop_dnn.A)
#     #B = np.array(model_koop_dnn.B).reshape(-1,num_inputs*n_obs)
#     B = np.array(model_koop_dnn.B)
#     #B_tensor = np.empty((num_inputs,n_obs, n_obs))
#     #for ii, b in enumerate(B):
#         #B_tensor[ii] = b
#     C = np.array(model_koop_dnn.C)
#
#     print(A.shape, B.shape, C.shape)
#     return A,B,C
#
#
# def lift(x,model_koop_dnn, params):
#     first_obs_const = params['first_obs_const']
#     override_C = params['override_C']
#     if first_obs_const == 1:
#         if override_C:
#             Z = np.concatenate((np.ones((1,)),x,model_koop_dnn.net.encode_forward_(torch.from_numpy(x).float()).detach().numpy()))
#         else:
#             Z = np.concatenate((np.ones((1,)),model_koop_dnn.net.encode_forward_(torch.from_numpy(x).float()).detach().numpy()))
#     else:
#         if override_C:
#             Z = np.concatenate((x,model_koop_dnn.net.encode_forward_(torch.from_numpy(x).float()).detach().numpy()))
#         else:
#             Z = (model_koop_dnn.net.encode_forward_(torch.from_numpy(x).float()).detach().numpy())
#     return Z

import torch
import numpy as np

from core.koopman_core_linear import KoopDNN_linear, KoopmanNet_linear, KoopmanNetCtrl_linear


def model_matricies(file):
    model_koop_dnn = torch.load(file, map_location="cpu")
    A = np.array(model_koop_dnn.A)
    B = np.array(model_koop_dnn.B)
    C = np.array(model_koop_dnn.C)

    print(A.shape, B.shape, C.shape)
    return A, B, C


def lift_raw(x, model_koop_dnn, params=None):
    """
    x: 原始物理状态（未标准化）
    返回 lifted state
    """
    x = np.asarray(x, dtype=np.float32).reshape(1, -1)

    if model_koop_dnn.net.standardizer_x is not None:
        x_scaled = model_koop_dnn.net.standardizer_x.transform(x)
    else:
        x_scaled = x

    return model_koop_dnn.net.encode(x_scaled).squeeze()


def lift_scaled(x, model_koop_dnn, params=None):
    """
    将标准化后的状态 x 提升到 lifted space（兼容当前 KoopmanNetCtrl_linear）
    x: shape (state_dim,) 或 (1, state_dim) —— 已经过 standardizer_x 变换
    """
    net = model_koop_dnn.net

    # 确保输入是 2D tensor (batch_size=1, state_dim)
    x_np = np.asarray(x, dtype=np.float32).reshape(1, -1)

    with torch.no_grad():
        x_t = torch.from_numpy(x_np).to(net.device)
        z_t = net.lift(x_t)  # ← 使用模型已实现的 lift 方法

    return z_t.squeeze(0).cpu().numpy()  # 返回 (lifted_dim,)

# def lift_scaled(x, model_koop_dnn, params=None):
#     """
#     x: 已经标准化后的状态
#     返回 lifted state
#     """
#     x_scaled = np.asarray(x, dtype=np.float32).reshape(1, -1)
#     return model_koop_dnn.net.encode(x_scaled).squeeze()


# 为了兼容旧代码，默认把 lift 当成 raw 版本
def lift(x, model_koop_dnn, params=None):
    return lift_raw(x, model_koop_dnn, params)




# import torch
# import numpy as np
#
# # 如果你后面其实用的是 linear 版本，建议改成对应导入
# # from core.koopman_core_linear import KoopDNN_linear, KoopmanNet_linear, KoopmanNetCtrl_linear
# from core.koopman_core import KoopDNN, KoopmanNet, KoopmanNetCtrl
#
#
# def model_matricies(file):
#     model_koop_dnn = torch.load(file, map_location="cpu")
#     A = np.array(model_koop_dnn.A)
#     B = np.array(model_koop_dnn.B)
#     C = np.array(model_koop_dnn.C)
#
#     print(A.shape, B.shape, C.shape)
#     return A, B, C
#
# def lift(x, model_koop_dnn, params):
#     x = np.asarray(x, dtype=np.float32).reshape(1, -1)
#
#     if model_koop_dnn.net.standardizer_x is not None:
#         x_scaled = model_koop_dnn.net.standardizer_x.transform(x)
#     else:
#         x_scaled = x
#
#     return model_koop_dnn.net.encode(x_scaled).squeeze()
# # def lift(x, model_koop_dnn, params):
# #     x = np.asarray(x, dtype=np.float32).reshape(1, -1)
# #     return model_koop_dnn.net.encode(x).squeeze()