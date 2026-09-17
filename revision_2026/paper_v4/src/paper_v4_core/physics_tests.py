"""E01 deterministic force identities, not trajectory convergence acceptance."""
import argparse
from pathlib import Path
import numpy as np
from .cli import save, sha
from .plant.four_vehicle_common import ModelParams, initialize_state, connector_diagnostics, assemble_derivative, rotation

def run(out):
    p=ModelParams(); rows=[]; states=[]; forces=[]
    for kind in ['static','translation','single_extension','rotated_extension']:
        x=initialize_state(p,0. if kind=='static' else 2.)
        if 'extension' in kind:
            x[0]+=.025; x[1]+=.012; x[3]+=.03; x[4]+=.02
        if kind=='rotated_extension':
            for i in range(5):
                j=6*i;x[j:j+2]=rotation(.7)@x[j:j+2]+[5.,-3.];x[j+2]+=.7
        dx,d=assemble_derivative(x,np.zeros((4,2)),p,'R3',True,True)
        c=d['connectors'];f=c['force_payload_world_n'];v=c['force_vehicle_world_n']
        scale=max(1.,float(np.max(np.linalg.norm(f,axis=1))))
        residuals={
            'action_reaction':float(np.max(abs(f+v))/scale),
            'common_origin_moment':float(np.max(abs(c['common_origin_internal_moment_residual_nm']))/(scale*5.)),
            'internal_projection':float(np.max(abs(c['internal_null_residual']))/(scale*5.)),
            'vertical_support':float(np.max(abs(d['support_constraint_relative_residual']))),
        }
        if kind in ['static','translation']:
            residuals['acceleration']=float(np.max(abs(dx.reshape(5,6)[:,3:])))
        # With load transfer held disabled, difference must be exact connector contribution.
        on,diag=assemble_derivative(x,np.zeros((4,2)),p,'R3',True,False)
        off,_=assemble_derivative(x,np.zeros((4,2)),p,'R3',False,False)
        residuals['force_enters_rhs']=float(np.max(abs(on-off-diag['connector_derivative']))/max(1.,float(np.max(abs(on)))))
        rows.append({'case':kind,'normalized_residuals':residuals,'pass':all(v<=1e-8 for v in residuals.values())})
        states.append(x);forces.append(f)
    # Rotation covariance: same body loads and inertial acceleration, rotated world vectors.
    cov=float(np.max(abs(forces[3]-forces[2]@rotation(.7).T)) / max(1.,float(np.max(abs(forces[2])))))
    rows.append({'case':'rotation_covariance','normalized_residuals':{'force':cov},'pass':cov<=1e-8})
    out=Path(out);(out/'E01').mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'E01/static_raw.npz',states=np.asarray(states),payload_world_force=np.asarray(forces))
    result={'status':'PASS' if all(r['pass'] for r in rows) else 'FAIL','tests':rows,'source_sha256':sha(__file__),'scope':'force identities only','plant_gate':'NOT_RUN','remaining':'geometric ICR, actuator, 33 trajectories and numerical convergence'}
    save(out,'E01/static_tests.json',result)
    print(result)
    return 0 if result['status']=='PASS' else 20

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    raise SystemExit(run(parser.parse_args().out))
