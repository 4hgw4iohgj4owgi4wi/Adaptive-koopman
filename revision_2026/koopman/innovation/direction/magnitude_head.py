from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class DirectAxialMagnitudeHead:
    coef:np.ndarray;feature_mean:np.ndarray;feature_std:np.ndarray;feature_dims:np.ndarray;force_scale:np.ndarray;force_floor:np.ndarray
    def predict_latent(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:
        out=[]
        for h in range(1,21):
            f=np.c_[np.ones(len(x0)),x0,u[:,:h].reshape(len(x0),-1)];d=int(self.feature_dims[h-1]);out.append(((f-self.feature_mean[h-1,:d])/self.feature_std[h-1,:d])@self.coef[h-1,:d])
        return np.stack(out,axis=1)
    def predict_magnitude(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:return self.force_scale*np.logaddexp(0.,self.predict_latent(x0,u))

@dataclass
class DirectPointHead:
    coef:np.ndarray;feature_mean:np.ndarray;feature_std:np.ndarray;feature_dims:np.ndarray
    def predict(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:
        out=[]
        for h in range(1,21):
            f=np.c_[np.ones(len(x0)),x0,u[:,:h].reshape(len(x0),-1)];d=int(self.feature_dims[h-1]);out.append(((f-self.feature_mean[h-1,:d])/self.feature_std[h-1,:d])@self.coef[h-1,:d])
        return np.stack(out,axis=1).reshape(len(x0),20,4,2)
