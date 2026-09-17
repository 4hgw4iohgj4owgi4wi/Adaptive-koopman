from __future__ import annotations

import numpy as np


class SharedBackboneRegimeResidual:
    def __init__(self,weights:np.ndarray,rank:int,n_modes:int=4,max_ratio:float=.25):
        self.weights=np.asarray(weights,float); self.rank=int(rank); self.n_modes=int(n_modes); self.max_ratio=float(max_ratio)

    def residual_step(self,xn:np.ndarray,un:np.ndarray,alpha:np.ndarray)->np.ndarray:
        phi=np.r_[1.0,np.asarray(xn,float),np.asarray(un,float)]; return np.einsum("m,mij,i->j",alpha,self.weights,phi)

    def protect(self,base:np.ndarray,residual:np.ndarray)->tuple[np.ndarray,float]:
        ratio=float(np.linalg.norm(residual)/(np.linalg.norm(base)+1e-12)); scale=1.0 if ratio<=self.max_ratio else self.max_ratio/ratio
        return residual*scale,ratio*scale

    def step(self,base:np.ndarray,xn:np.ndarray,un:np.ndarray,alpha:np.ndarray)->tuple[np.ndarray,float]:
        residual=self.residual_step(xn,un,alpha); residual,ratio=self.protect(base,residual); return base+residual,ratio

    def residual_ratio(self,xn:np.ndarray,un:np.ndarray,alpha:np.ndarray,base:np.ndarray)->float:
        _,ratio=self.protect(base,self.residual_step(xn,un,alpha)); return ratio


def ridge_low_rank(gram:np.ndarray,cross:np.ndarray,ridge:float,rank:int)->tuple[np.ndarray,dict[str,float|list[float]]]:
    regularized=np.asarray(gram,float)+float(ridge)*np.eye(len(gram)); weight=np.linalg.solve(regularized,np.asarray(cross,float))
    u,s,vt=np.linalg.svd(weight,full_matrices=False); kept=min(int(rank),len(s)); truncated=(u[:,:kept]*s[:kept])@vt[:kept]
    return truncated,{"condition_number":float(np.linalg.cond(regularized)),"effective_rank":int(np.linalg.matrix_rank(truncated)),"singular_values":s[:min(12,len(s))].tolist()}
