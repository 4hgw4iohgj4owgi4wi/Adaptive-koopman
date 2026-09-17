from __future__ import annotations

import numpy as np


class DirectMultiHorizonHead:
    def __init__(self,coef:np.ndarray,feature_mean:np.ndarray,feature_std:np.ndarray,feature_dims:np.ndarray):
        self.coef=np.asarray(coef,float); self.feature_mean=np.asarray(feature_mean,float); self.feature_std=np.asarray(feature_std,float); self.feature_dims=np.asarray(feature_dims,int)

    def predict_horizon(self,h:int,x0:np.ndarray,u_prefix:np.ndarray)->np.ndarray:
        index=int(h)-1; feature=np.r_[1.0,np.asarray(x0,float),np.asarray(u_prefix,float).reshape(-1)]; d=int(self.feature_dims[index])
        normalized=(feature-self.feature_mean[index,:d])/self.feature_std[index,:d]; return normalized@self.coef[index,:d]

    def predict(self,x0:np.ndarray,u_future:np.ndarray)->np.ndarray:
        return np.asarray([self.predict_horizon(h,x0,u_future[:h]) for h in range(1,21)])
