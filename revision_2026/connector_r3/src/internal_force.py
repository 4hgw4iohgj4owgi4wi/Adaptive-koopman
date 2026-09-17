from __future__ import annotations
import numpy as np
CORNER_ORDER=('FL','FR','RL','RR');SVD_RTOL=1e-12

def build_planar_grasp_matrix(anchor_body:np.ndarray)->np.ndarray:
    r=np.asarray(anchor_body,float)
    if r.shape!=(4,2):raise ValueError('anchor_body must be [FL,FR,RL,RR] shape (4,2)')
    g=np.zeros((3,8));g[0,0::2]=1.;g[1,1::2]=1.;g[2,0::2]=-r[:,1];g[2,1::2]=r[:,0];return g
def _pinv(a,rtol=SVD_RTOL):
    u,s,vt=np.linalg.svd(a,full_matrices=False);tol=rtol*(s[0] if len(s) else 0.);inv=np.where(s>tol,1./s,0.);return (vt.T*inv)@u.T,int(np.sum(s>tol)),float(s[0]/s[np.sum(s>tol)-1]) if np.any(s>tol) else float('inf')
def decompose_planar_point_forces(force_body:np.ndarray,anchor_body:np.ndarray,rtol=SVD_RTOL):
    f=np.asarray(force_body,float).reshape(8);g=build_planar_grasp_matrix(anchor_body);pinv,rank,cond=_pinv(g,rtol);w=g@f;motion=pinv@w;internal=f-motion
    return {'generalized_payload_wrench':w,'motion_force_vector':motion,'internal_force_vector':internal,'internal_force_norm_n':float(np.linalg.norm(internal)),'grasp_rank':rank,'grasp_condition':cond,'null_residual':g@internal,'reconstruction_residual':f-motion-internal}
def build_radial_grasp_matrix(anchor_body:np.ndarray,normals_body:np.ndarray)->np.ndarray:
    g=build_planar_grasp_matrix(anchor_body);n=np.asarray(normals_body,float)
    if n.shape!=(4,2):raise ValueError('normals must have shape (4,2)')
    b=np.zeros((8,4));
    for i in range(4):b[2*i:2*i+2,i]=n[i]
    return g@b
def decompose_radial_forces(magnitudes:np.ndarray,anchor_body:np.ndarray,normals_body:np.ndarray,rtol=SVD_RTOL):
    q=np.asarray(magnitudes,float).reshape(4);gr=build_radial_grasp_matrix(anchor_body,normals_body);pinv,rank,cond=_pinv(gr,rtol);w=gr@q;motion=pinv@w;internal=q-motion
    return {'radial_motion':motion,'radial_internal':internal,'radial_internal_norm_n':float(np.linalg.norm(internal)),'radial_rank':rank,'radial_condition':cond,'radial_null_residual':gr@internal}
def legacy_q_fr_q_lr(force_body:np.ndarray)->np.ndarray:
    f=np.asarray(force_body,float).reshape(4,2);return np.asarray([.5*((f[0,0]+f[1,0])-(f[2,0]+f[3,0])),.5*((f[0,1]+f[2,1])-(f[1,1]+f[3,1]))])
def diagonal_tension_modes(force_body:np.ndarray)->np.ndarray:
    f=np.asarray(force_body,float).reshape(4,2);return np.asarray([.5*np.linalg.norm(f[0]-f[3]),.5*np.linalg.norm(f[1]-f[2])])

