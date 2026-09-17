"""Execute the original recorder with a declared short pulse; no training."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main(out):
    rev=Path(__file__).resolve().parents[3]
    root=rev/'koopman_predict_auto'
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    sys.path[:0]=[str(root/'scripts'),str(root/'src'),str(root/'plant')]
    import generate_data as gen
    from scenarios import ScenarioCommand,ScenarioSpec
    from four_vehicle_common import ModelParams
    from dataset import prediction_cache_from_raw
    protocol=json.loads((root/'config/protocol_predict_auto.json').read_text(encoding='utf-8-sig'))
    seen=[]
    def pulse(spec,t,d,t30,dec):
        k=int(round(t/.02))
        seen.append([k,t])
        # Small, distinguishable pulse in every requested control group.
        active=k==2
        return ScenarioCommand(.25 if active else 0.,1. if active else 0.,-.5 if active else 0.,'E00_PULSE',(.01,-.01,.02,-.02) if active else (0.,)*4)
    gen.command_for=pulse
    params=ModelParams()
    summary,raw=gen.simulate_trajectory(ScenarioSpec('D0','none',.12,None,False),'R3',2026090912,params,protocol,actuator_mode='A3',load_transfer_enabled=True)
    cache=prediction_cache_from_raw(raw,params,protocol)
    control11=np.c_[cache['control7'],raw['requested_control4x2'][1:,:,0]-raw['base_acceleration_mps2'][1:,None]]
    np.savez_compressed(out/'pulse_raw.npz',**raw)
    np.savez_compressed(out/'pulse_cache.npz',**cache,control11=control11)
    assert summary['status']=='PASS',summary
    assert len(raw['state30'])==6
    assert np.allclose(raw['time_s'],.02*np.arange(1,7),rtol=0,atol=1e-12)
    assert np.flatnonzero(raw['base_acceleration_mps2']).tolist()==[2]
    assert np.flatnonzero(control11[:,0]).tolist()==[1]
    assert np.allclose(control11[:,3:7],raw['requested_control4x2'][1:,:,1],rtol=0,atol=0)
    assert np.allclose(control11[:,7:]+control11[:,0,None],raw['requested_control4x2'][1:,:,0],rtol=0,atol=1e-12)
    # Independent actual-plant replay from recorded x_k and actual delta_k.
    from steering_actuator import SteeringActuatorConfig,step_actuator_mode
    from event_substep import EventSubstepConfig,advance_outer_step
    errors=[]
    for k in range(5):
        x=raw['state30'][k].copy();delta=raw['actual_steering_rad'][k].copy()
        req=raw['requested_control4x2'][k+1].copy()
        for j in range(10):
            delta=step_actuator_mode(req[:,1],delta,.002,SteeringActuatorConfig(),'A3')['delta_act_next_rad']
            applied=req.copy();applied[:,1]=delta
            x,audit=advance_outer_step(x,applied,'R3',params,.002,'ES',EventSubstepConfig(),load_transfer_enabled=True)
            assert audit['status']=='PASS'
        errors.append(float(np.max(abs(x-raw['state30'][k+1]))))
    assert max(errors)<=1e-12,errors
    imports=[]
    for name,module in sorted(sys.modules.copy().items()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(rev):
            imports.append({'module':name,'path':str(Path(file).resolve()),'sha256':sha(file)})
    report={'status':'PASS','scope':'current original producer runtime pulse and independent interval replay; historical generation identity still requires manifest','dt_s':.02,'raw_rows':6,'command_start_ticks':seen,'raw_pulse_row':2,'cache_pulse_row':1,'state_replay_max_abs':max(errors),'actuator_parameters':protocol['actuator'],'protocol_sha256':sha(root/'config/protocol_predict_auto.json'),'imports':imports,'script_sha256':sha(__file__)}
    (out/'recorder.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='imports'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True)
    main(p.parse_args().out)
