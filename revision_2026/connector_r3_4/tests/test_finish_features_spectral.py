from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from step_features import aggregate_step_audit,aggregate_control_interval
from spectral_metrics import spectral_metrics

def audit():
 end={'force_payload_world_n':np.zeros((4,2)),'force_payload_body_n':np.zeros((4,2))};seg=[{'dt_s':.001,'force_payload_world_n':np.ones((4,2)).tolist(),'signed_gap_m':[1,-1,1,-1],'smoothing_weight':[.2,0,.8,0],'contact_active':[1,0,1,0],'smoothing_active':[1,0,1,0]},{'dt_s':.001,'force_payload_world_n':(3*np.ones((4,2))).tolist(),'signed_gap_m':[2,-1,3,-1],'smoothing_weight':[.6,0,1,0],'contact_active':[1,0,1,0],'smoothing_active':[1,0,0,0]}];return {'endpoint_diagnostics':end,'interval_segments':seg,'events':[],'force_peak_n':np.ones(4)*3,'damping_work_j':np.zeros(4),'accepted_steps':2,'min_physical_dt_s':.001,'max_physical_dt_s':.001,'status':'PASS'}
def test_finish_interval_real_dt_weighting():
 f=aggregate_step_audit(np.zeros(30),np.zeros((4,2)),audit());np.testing.assert_allclose(f['force_mean_world'],2);np.testing.assert_allclose(f['contact_fraction'],[1,0,1,0]);np.testing.assert_allclose(f['g_mean'],[.4,0,.9,0]);np.testing.assert_allclose(f['g_min'],[.2,0,.8,0]);np.testing.assert_allclose(f['g_max'],[.6,0,1,0])
def test_finish_ten_steps_make_20ms():
 f=aggregate_step_audit(np.zeros(30),np.zeros((4,2)),audit());c=aggregate_control_interval([f]*10);assert abs(c['interval_duration_s']-.02)<=1e-12
def test_finish_spectral_sine_constant_parseval():
 t=np.arange(4096)*.002;s=np.sin(2*np.pi*20*t);m=spectral_metrics(s);assert abs(m['frequency_hz'][np.argmax(m['psd'])]-20)<.3;assert m['parseval_relative_error']<=.01;z=spectral_metrics(np.ones(4096));assert z['high_frequency_energy']<1e-20
