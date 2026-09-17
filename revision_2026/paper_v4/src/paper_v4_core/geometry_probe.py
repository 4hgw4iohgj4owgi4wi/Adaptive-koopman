"""Detect CG/rear-axle confusion using independently evaluated wheel velocities."""
import argparse
from pathlib import Path
import numpy as np
from .cli import save,sha
from .plant.four_vehicle_common import ModelParams,rotation
from .plant.steering_allocator import kinematic_targets
from .reference_geometry import steady_targets

def residuals(t,p):
    rear=[];front=[];anchors=[]
    for i,beta in enumerate(t['relative_heading_rad']):
        r=t['yaw_rate_radps'];v=rotation(beta).T@t['point_velocity_payload_body_mps'][i]
        rear.append(v[1]-p.vehicle.lr_m*r)
        vf=v+np.array([0.,p.vehicle.lf_m*r]);delta=t['feedforward_steering_rad'][i]
        front.append(float(np.array([-np.sin(delta),np.cos(delta)])@vf))
        anchors.append(t['vehicle_centers_payload_body_m'][i]+rotation(beta)@np.asarray(p.vehicle_anchor_body_m[i])-p.payload_anchor_body_m[i])
    return {'rear_lateral_mps':rear,'front_normal_mps':front,'anchor_error_m':np.asarray(anchors).tolist()}

def main(out):
    p=ModelParams();out=Path(out);out.mkdir(parents=True,exist_ok=False);rows=[]
    for speed in [1.,2.,4.]:
        for front,rear in [(0.,0.),(5.,-2.5),(-5.,2.5)]:
            old=kinematic_targets(speed,np.deg2rad(front),np.deg2rad(rear),p)
            r=old['yaw_rate_radps'];vc=np.array([speed,0. if r==0 else -r*old['icr_payload_body_m'][0]])
            new=steady_targets(vc,r,p)
            a=residuals(old,p);b=residuals(new,p)
            assert max(abs(np.asarray(b['rear_lateral_mps'])))<1e-10
            assert max(abs(np.asarray(b['front_normal_mps'])))<1e-10
            assert np.max(abs(np.asarray(b['anchor_error_m'])))<1e-12
            rows.append({'speed_mps':speed,'front_deg':front,'rear_deg':rear,'old':a,'corrected_steady_reference':b,'new_heading_rad':new['relative_heading_rad'].tolist(),'new_steer_rad':new['feedforward_steering_rad'].tolist()})
    old_max=max(abs(x) for row in rows for x in row['old']['rear_lateral_mps'])
    new_max=max(abs(x) for row in rows for x in row['corrected_steady_reference']['rear_lateral_mps'])
    assert old_max>1e-3
    save(out,'geometry.json',{'legacy_geometry':'FAIL_REAR_AXLE_CONTRACT','corrected_steady_geometry':'PASS','old_max_rear_residual_mps':old_max,'new_max_rear_residual_mps':new_max,'cases':rows,'scope':'steady reference only; dynamic beta_dot, constraints, trajectory rollout NOT_RUN','source_sha':sha(__file__),'reference_sha':sha(Path(__file__).with_name('reference_geometry.py'))})
    print({'old_max_rear_mps':old_max,'new_max_rear_mps':new_max,'cases':len(rows)})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);main(parser.parse_args().out)
