from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from four_vehicle_common import ModelParams,assemble_derivative,connector_diagnostics,initialize_state,rotation,split_state
from internal_force import build_planar_grasp_matrix,decompose_planar_point_forces,tension_load_proxies

def loaded_state(index=None):
 p=ModelParams();s=initialize_state(p,2.);v,load=split_state(s);dirs=p.payload_anchor_body_m/np.linalg.norm(p.payload_anchor_body_m,axis=1)[:,None]
 ids=range(4) if index is None else [index]
 for i in ids:v[i,:2]+=dirs[i]*.003
 s[:24]=v.ravel();return p,s

def test_finish_action_reaction_and_common_origin_moment():
 p,s=loaded_state();d=connector_diagnostics(s,p,'R3');assert np.max(np.linalg.norm(d['action_reaction_residual_n'],axis=1))<1e-10;scale=np.maximum(1.,np.abs(d['payload_moment_nm']));assert np.max(np.abs(d['common_origin_internal_moment_residual_nm'])/scale)<1e-8

def test_finish_frame_rotation_roundtrip_and_inactive_direction():
 p,s=loaded_state();d=connector_diagnostics(s,p,'R3');_,payload=split_state(s);np.testing.assert_allclose(d['force_payload_body_n']@rotation(payload[2]).T,d['force_payload_world_n'],atol=1e-12)
 z=connector_diagnostics(initialize_state(p),p,'R3');assert set(z['force_direction_status'])=={'INACTIVE'}

def test_finish_connector_derivative_wiring_each_point():
 for i in range(4):
  p,s=loaded_state(i);u=np.zeros((4,2));total,diag=assemble_derivative(s,u,p,'R3',True);zero,_=assemble_derivative(s,u,p,'R3',False);np.testing.assert_allclose(total-zero,diag['connector_derivative'],rtol=1e-10,atol=1e-12);assert np.linalg.norm((total-zero)[6*i+3:6*i+6])>0;assert np.linalg.norm((total-zero)[27:30])>0

def test_finish_internal_force_nullspace_modes():
 p=ModelParams();g=build_planar_grasp_matrix(p.payload_anchor_body_m);f=np.array([[1,0],[-1,0],[-1,0],[1,0.]])*100;d=decompose_planar_point_forces(f,p.payload_anchor_body_m);assert np.linalg.norm(g@d['internal_force_vector'])<1e-8*max(1,d['internal_force_norm_n'])

def test_finish_tension_proxies_longitudinal_lateral_and_mirror():
 fx=np.array([[10,0],[10,0],[-10,0],[-10,0.]]);fy=np.array([[0,10],[0,-10],[0,10],[0,-10.]])
 assert tension_load_proxies(fx)['tension_x_n']==20;assert tension_load_proxies(fy)['tension_y_n']==20;assert tension_load_proxies(-fx)['tension_x_n']==0
