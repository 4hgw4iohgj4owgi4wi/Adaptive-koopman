from __future__ import annotations
import numpy as np
from scipy.signal import welch

def spectral_metrics(signal,dt_s=.002,high_hz=25.):
    x=np.asarray(signal,float);n=2**int(np.floor(np.log2(max(2,min(1024,len(x))))));fs=1/dt_s
    f,p=welch(x,fs=fs,window='hann',nperseg=n,noverlap=n//2,detrend='constant',scaling='density')
    variance=float(np.mean((x-np.mean(x))**2));integral=float(np.trapezoid(p,f));parseval=abs(integral-variance)/max(variance,1e-30);mask=f>high_hz;hf=float(np.trapezoid(p[mask],f[mask])) if np.count_nonzero(mask)>1 else 0.;j=np.abs(np.diff(x))
    return {'frequency_hz':f,'psd':p,'high_frequency_energy':hf,'high_frequency_fraction':hf/max(integral,1e-30),'parseval_relative_error':parseval,'rms':float(np.sqrt(np.mean(x*x))),'jump_max':float(np.max(j)) if len(j) else 0.,'jump_p95':float(np.percentile(j,95)) if len(j) else 0.,'jump_p99':float(np.percentile(j,99)) if len(j) else 0.}
