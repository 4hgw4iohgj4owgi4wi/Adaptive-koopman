from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from event_substep import EventSubstepConfig,StepRecord,_dt_class,_empty_step_audit,_scalar_candidate,_vector_crossings,integrate

Q95=0.054984709782141795

def q95_run():
    return integrate('R3',-Q95*(0.002+0.00075),Q95,0.02275,'ES',keep_trace=True)

def test_floating_closure_no_state_advance():
    assert _dt_class(1e-13,EventSubstepConfig())=='FLOATING_CLOSURE'

def test_v1_outer_remainder_1p443us_no_event():
    v=.25;r=integrate('V1',-v*(.002+.001375),v,.023375,'ES',keep_trace=True)
    hit=[x for x in r['step_records'] if 1e-12<x['advanced_dt_s']<2e-6]
    assert any(x['selection_cause']=='OUTER_REMAINDER' and x['event_relation']=='NO_EVENT' for x in hit)

def test_q95_outer_remainder_splits_at_smoothing_root():
    r=q95_run(); hits=[x for x in r['step_records'] if x['candidate_origin']=='OUTER_REMAINDER']
    assert any(x['selection_cause']=='EVENT_ROOT' and x['event_relation']=='ENDS_AT_EVENT' and 'smoothing' in x['event_ids'] for x in hits)

def test_sub2us_event_alignment_is_allowed_and_logged():
    speed=.25
    r=integrate('V1',-speed*1e-6,speed,5e-6,'ES',keep_trace=True)
    assert r['status']=='PASS'
    assert any(x['selection_cause']=='EVENT_ROOT' and x['dt_class']=='FINITE_SUBMINIMUM_DT' for x in r['step_records'])

def test_zone_resolution_below_2us_fails():
    cfg=EventSubstepConfig();dt,cause,bad=_scalar_candidate(np.array([cfg.smoothing_width_m/2,20.0]),1e-3,cfg)
    assert bad and cause=='ZONE_RESOLUTION'

def test_time_conservation_each_outer_step():
    assert q95_run()['time_conservation_residual_s']<=1e-12

def test_no_duplicate_endpoint_event():
    r=q95_run(); keys=[(round(x['time_s'],12),x['surface']) for x in r['events']];assert len(keys)==len(set(keys))

def test_two_and_four_simultaneous_events():
    cfg=EventSubstepConfig();s=np.ones((4,2));m=np.ones((4,2));e=np.ones((4,2));s[:,0]=-.1;m[:,0]=0;e[:,0]=.1
    c=_vector_crossings(s,m,e,cfg);assert len({x[0] for x in c})==4

def test_double_crossing_detected():
    cfg=EventSubstepConfig();s=np.array([[-1.,1.]]);m=np.array([[1.,1.]]);e=np.array([[-1.,1.]])
    assert len(_vector_crossings(s,m,e,cfg))==2

def test_scalar_and_vehicle_audit_schema_equal():
    scalar=set(StepRecord(0,1,'REGULAR_DT','PROBE_LIMIT','PROBE_LIMIT','NO_EVENT').__dict__)
    vehicle=set(StepRecord(0,1,'REGULAR_DT','PROBE_LIMIT','PROBE_LIMIT','NO_EVENT').__dict__)
    assert scalar==vehicle and 'step_records' in _empty_step_audit()
