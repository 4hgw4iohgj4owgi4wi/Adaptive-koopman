from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from four_vehicle_common import ModelParams,initialize_state
from steering_allocator import allocate_controls,kinematic_targets

def test_finish_straight_allocator_zero():
 p=ModelParams();s=initialize_state(p);u,d=allocate_controls(s,0,0,0,p);assert np.max(np.abs(u[:,1]))==0;assert d['max_normal_velocity_residual_mps']==0
def test_finish_mirror_and_icr_residual():
 p=ModelParams();a=kinematic_targets(2,np.deg2rad(4),np.deg2rad(-2),p);b=kinematic_targets(2,np.deg2rad(-4),np.deg2rad(2),p);mirror=np.array([1,0,3,2]);np.testing.assert_allclose(a['relative_heading_rad'],-b['relative_heading_rad'][mirror],atol=1e-12);np.testing.assert_allclose(a['speed_mps'],b['speed_mps'][mirror],atol=1e-12);np.testing.assert_allclose(a['feedforward_steering_rad'],-b['feedforward_steering_rad'][mirror],atol=1e-12);np.testing.assert_allclose(a['icr_payload_body_m'][0],b['icr_payload_body_m'][0],atol=1e-12);np.testing.assert_allclose(a['icr_payload_body_m'][1],-b['icr_payload_body_m'][1],atol=1e-12);np.testing.assert_allclose(a['vehicle_centers_payload_body_m'][:,0],b['vehicle_centers_payload_body_m'][mirror,0],atol=1e-12);np.testing.assert_allclose(a['vehicle_centers_payload_body_m'][:,1],-b['vehicle_centers_payload_body_m'][mirror,1],atol=1e-12);assert max(np.max(np.abs(a['normal_velocity_residual_mps'])),np.max(np.abs(b['normal_velocity_residual_mps'])))<=1e-8
def test_finish_allocator_clip_audit():
 p=ModelParams();s=initialize_state(p);_,d=allocate_controls(s,0,30,-15,p);assert 'unclipped_steering_rad' in d and 'steering_clipped' in d and 0<=d['steering_clipped_fraction']<=1
