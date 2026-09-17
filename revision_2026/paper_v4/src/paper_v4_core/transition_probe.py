"""Independent position differentiation for EXP-R1 moving anchor reference."""
import argparse
from pathlib import Path
import numpy as np
from .cli import save,sha
from .plant.four_vehicle_common import ModelParams,rotation
from .reference_geometry import transition_targets

def twist(t):
    # Diagnostic only, not the registered hairpin or 100 m input replacement.
    return np.array([2.,0.]),.12*np.sin(2*np.pi*t/10.)**3

def rhs(t,z,p):
    v,r=twist(t);g=transition_targets(v,r,z[3:],p)
    return np.r_[rotation(z[2])@v,r,g['beta_dot']]

def positions(z,p):
    q=np.array([b-rotation(beta)@np.asarray(d) for b,d,beta in zip(p.payload_anchor_body_m,p.vehicle_anchor_body_m,z[3:])])
    return z[:2]+q@rotation(z[2]).T

def main(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);p=ModelParams();z=np.zeros(7);dt=.01
    raw=[];fdmax=rearmax=frontmax=anchormax=0.
    for k in range(2001):
        t=k*dt;v,r=twist(t);g=transition_targets(v,r,z[3:],p);dz=rhs(t,z,p)
        eps=1e-5
        diff=(positions(z+eps*dz,p)-positions(z-eps*dz,p))/(2*eps)
        velocity=g['velocity_payload_frame']@rotation(z[2]).T
        fdmax=max(fdmax,float(np.max(abs(diff-velocity))))
        vb=g['velocity_vehicle_frame'];ri=g['vehicle_yaw_rates'];delta=g['steering']
        rearmax=max(rearmax,float(np.max(abs(vb[:,1]-p.vehicle.lr_m*ri))))
        frontmax=max(frontmax,float(np.max(abs(-np.sin(delta)*vb[:,0]+np.cos(delta)*(vb[:,1]+p.vehicle.lf_m*ri)))))
        for i in range(4):
            anchor_v=velocity[i]+rotation(z[2]+z[3+i])@(ri[i]*np.array([-p.vehicle_anchor_body_m[i][1],p.vehicle_anchor_body_m[i][0]]))
            target=rotation(z[2])@(v+r*np.array([-p.payload_anchor_body_m[i,1],p.payload_anchor_body_m[i,0]]))
            anchormax=max(anchormax,float(np.max(abs(anchor_v-target))))
        raw.append(np.r_[t,z,delta,ri,g['beta_dot']])
        a=rhs(t,z,p);b=rhs(t+dt/2,z+dt*a/2,p);c=rhs(t+dt/2,z+dt*b/2,p);d=rhs(t+dt,z+dt*c,p)
        z=z+dt*(a+2*b+2*c+d)/6
    raw=np.asarray(raw);np.savez_compressed(out/'transition.npz',values=raw,columns=np.asarray(['time','px','py','yaw','beta1','beta2','beta3','beta4','delta1','delta2','delta3','delta4','r1','r2','r3','r4','bd1','bd2','bd3','bd4']))
    delta=raw[:,8:12];angle=float(np.max(abs(delta)));rate=float(np.max(abs(np.diff(delta,axis=0)/dt)))
    result={'scope':'20s diagnostic reference only, not plant or registered trajectories','samples':len(raw),'position_difference_velocity_error_mps':fdmax,'rear_residual_mps':rearmax,'front_residual_mps':frontmax,'anchor_velocity_residual_mps':anchormax,'max_steer_deg':float(np.rad2deg(angle)),'sampled_max_steer_rate_radps':rate,'geometry_pass':fdmax<1e-8 and max(rearmax,frontmax,anchormax)<1e-10,'angle_limit_pass':angle<=np.deg2rad(15),'sampled_rate_limit_pass':rate<=1.2,'plant_gate':'NOT_RUN','source_sha':sha(__file__),'reference_sha':sha(Path(__file__).with_name('reference_geometry.py'))}
    result={k:(v.item() if isinstance(v,np.generic) else v) for k,v in result.items()}
    save(out,'transition.json',result);print(result)
    assert result['geometry_pass']

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);main(parser.parse_args().out)
