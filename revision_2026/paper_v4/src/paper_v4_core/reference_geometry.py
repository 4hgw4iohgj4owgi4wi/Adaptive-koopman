"""Steady rigid-reference geometry, rear-axle no-slip (EXP-R1 equation 6).

Not a dynamic allocator: beta_dot and actuator limits require trajectory handling.
"""
import numpy as np
from .plant.four_vehicle_common import rotation

def transition_targets(payload_velocity, yaw_rate, beta, params):
    """Rigid anchor-compatible moving reference with rear-axle no-slip.

    beta is integrated reference state, not reset to the instantaneous steady value.
    Returns requested geometry without silently clipping infeasible wheel angles.
    """
    v=np.asarray(payload_velocity,dtype=float);beta=np.asarray(beta,dtype=float)
    if v.shape!=(2,) or beta.shape!=(4,) or not np.all(np.isfinite(np.r_[v,beta,yaw_rate])):
        raise ValueError('invalid transition state')
    q=[];qd=[];vel=[];rates=[];bd=[];delta=[];body=[]
    for i,(b,d) in enumerate(zip(params.payload_anchor_body_m,np.asarray(params.vehicle_anchor_body_m))):
        arm=d[0]+params.vehicle.lr_m
        if abs(arm)<1e-10:raise ValueError('singular anchor to rear axle distance')
        rot=rotation(beta[i]);av=v+yaw_rate*np.array([-b[1],b[0]])
        ri=float((rot.T@av)[1]/arm);db=ri-yaw_rate
        qi=b-rot@d;dqi=-db*rot@np.array([-d[1],d[0]])
        vi=v+yaw_rate*np.array([-qi[1],qi[0]])+dqi
        vb=rot.T@vi
        if vb[0]<=1e-10:raise ValueError('non-forward transition not supported')
        di=np.arctan2(vb[1]+params.vehicle.lf_m*ri,vb[0])
        q.append(qi);qd.append(dqi);vel.append(vi);rates.append(ri);bd.append(db);delta.append(di);body.append(vb)
    return {'centers':np.asarray(q),'center_rates':np.asarray(qd),'velocity_payload_frame':np.asarray(vel),'vehicle_yaw_rates':np.asarray(rates),'beta_dot':np.asarray(bd),'steering':np.asarray(delta),'velocity_vehicle_frame':np.asarray(body)}

def steady_targets(payload_velocity, yaw_rate, params):
    v=np.asarray(payload_velocity,dtype=float)
    if v.shape!=(2,) or not np.all(np.isfinite(v)) or not np.isfinite(yaw_rate):
        raise ValueError('invalid twist')
    headings=[];centers=[];velocities=[];steers=[]
    for b,d in zip(params.payload_anchor_body_m,np.asarray(params.vehicle_anchor_body_m)):
        anchor_v=v+yaw_rate*np.array([-b[1],b[0]])
        length=np.linalg.norm(anchor_v)
        numerator=yaw_rate*(d[0]+params.vehicle.lr_m)
        if length<1e-12:
            if abs(yaw_rate)>1e-12:raise ValueError('singular rear-axle geometry')
            beta=0.
        else:
            ratio=numerator/length
            if abs(ratio)>1:raise ValueError('infeasible rear-axle geometry')
            beta=np.arctan2(anchor_v[1],anchor_v[0])-np.arcsin(ratio)
        q=b-rotation(beta)@d
        cog_v=v+yaw_rate*np.array([-q[1],q[0]])
        body_v=rotation(beta).T@cog_v
        if body_v[0]<-1e-12:raise ValueError('reverse branch not implemented')
        delta=np.arctan2((params.vehicle.lf_m+params.vehicle.lr_m)*yaw_rate,body_v[0]) if abs(yaw_rate)>1e-12 else 0.
        headings.append(beta);centers.append(q);velocities.append(cog_v);steers.append(delta)
    return {'relative_heading_rad':np.array(headings),'vehicle_centers_payload_body_m':np.array(centers),'point_velocity_payload_body_mps':np.array(velocities),'feedforward_steering_rad':np.array(steers),'yaw_rate_radps':float(yaw_rate)}
