"""Evidence-first EXP-R2/EXP-R3 entrypoint; unimplemented stages fail closed."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import time
from dataclasses import asdict
import numpy as np

REV = Path(__file__).resolve().parents[3]
EXPECTED = {
    'koopman_predict_auto/plant/four_vehicle_common.py':'6d7a2092fc6b9772347fc6d9812ba920bb139c8271f5cbba1ac96cc4f12bca80',
    'koopman_predict_auto/plant/event_substep.py':'9aa0e8bd62dd8b83b8bd0c15414cbd21f915f0203b7ca978d5f46bc45746d77c',
    'paper_v3/src/controllers.py':'c504bb0941990443fc0becdefaf6ab6d97ff9b14ae4180b546d714eea044c797',
}
TASKBOOK_SHA256_BY_PROTOCOL = {
    'EXP-R2': '417cfcdbf22a026973dff617e29e4814361f9013aed7ca06f065992c20f0d81d',
    'EXP-R3': 'eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87',
    'EXP-R4': '97d79f764f0ed308539e9a911d0498ecc571a82dda2942761a092ddb3fce1144',
    'EXP-R4B': '5586d94a6484f564b735003e27384d57cf39cc831a166dff81382b66b74bb2ac',
}
EXPECTED_METHOD_KEYS = {'P0', 'P0N', 'K0', 'K0N', 'K1', 'K1N'}
EXPECTED_REVIEW_IDS = {'AE-1', 'AE-2'} | {
    f'R{reviewer}-{item}'
    for reviewer, count in ((1, 6), (2, 7), (3, 7))
    for item in range(1, count + 1)
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(out, name, obj):
    p = out / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def require_hash(p, digest):
    if sha(p) != digest:
        raise ValueError('IDENTITY_MISMATCH: '+str(p))

def require_packet(sample_tick, arrival_tick, now):
    if not (sample_tick < arrival_tick <= now):
        raise ValueError('NON_CAUSAL_PACKET')

def require_interval(state_tick, input_start, next_tick):
    if not (input_start == state_tick and next_tick == state_tick + 1):
        raise ValueError('SHIFTED_INPUT_INTERVAL')

def require_source(entry):
    if entry.get('status') != 'SOURCE_QUALIFIED' or not entry.get('source_sha256'):
        raise ValueError('SOURCE_PENDING')

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def require_registries_data(methods, review):
    method_rows = methods.get('core_methods', [])
    method_keys = [row.get('key') for row in method_rows]
    review_rows = review.get('items', [])
    review_ids = [row.get('id') for row in review_rows]
    if len(method_keys) != 6 or set(method_keys) != EXPECTED_METHOD_KEYS:
        raise ValueError('METHOD_REGISTRY_INCOMPLETE')
    if len(review_ids) != 22 or set(review_ids) != EXPECTED_REVIEW_IDS:
        raise ValueError('REVIEW_MATRIX_INCOMPLETE')
    if len(method_keys) != len(set(method_keys)) or len(review_ids) != len(set(review_ids)):
        raise ValueError('DUPLICATE_REGISTRY_KEY')
    return methods, review

def require_registries(methods_path, review_path):
    return require_registries_data(load_json(methods_path), load_json(review_path))

def require_taskbook_protocol(path, protocol_version):
    if protocol_version not in TASKBOOK_SHA256_BY_PROTOCOL:
        raise ValueError('UNKNOWN_PROTOCOL_VERSION')
    require_hash(path, TASKBOOK_SHA256_BY_PROTOCOL[protocol_version])

def certificate(base_norm, coupling_bound, radius):
    if coupling_bound < 0 or radius <= 0 or base_norm < 0:
        raise ValueError('invalid domain')
    if base_norm > radius:
        return {'status':'NOT_CERTIFIABLE_BY_THIS_BOUND','gamma':None}
    gamma = 1.0 if coupling_bound == 0 else min(1.0, (radius-base_norm)/coupling_bound)
    return {'status':'CERTIFIED_BY_SUFFICIENT_BOUND','gamma':gamma}

def preflight(args):
    out = Path(args.out)
    if out.exists():
        raise ValueError('refusing to overwrite existing run')
    original=[]
    for rel, expected in EXPECTED.items():
        p=REV/rel
        require_hash(p,expected)
        original.append({'path':str(p),'sha256':sha(p)})
    task=Path(args.taskbook)
    require_taskbook_protocol(task, args.protocol_version)
    methods, review = require_registries(args.methods, args.review_matrix)
    from .plant import four_vehicle_common as plant
    from .plant import event_substep as event
    from .plant import steering_allocator
    modules=[]
    for name, mod in sorted(sys.modules.copy().items()):
        if name.startswith('paper_v4_core') and getattr(mod,'__file__',None):
            p=Path(mod.__file__).resolve()
            if not p.is_relative_to(Path(__file__).resolve().parent):
                raise ValueError('FOREIGN_IMPORT: '+str(p))
            modules.append({'module':name,'path':str(p),'sha256':sha(p)})
    localdir=Path(plant.__file__).parent
    conversions=[]
    for p in sorted(localdir.glob('*.py')):
        original_path=REV/'koopman_predict_auto/plant'/p.name
        if not original_path.exists():
            continue
        old=ast.parse(original_path.read_text(encoding='utf-8-sig'))
        new=ast.parse(p.read_text(encoding='utf-8-sig'))
        for node in ast.walk(old):
            if isinstance(node,ast.ImportFrom) and node.module and (localdir/(node.module+'.py')).exists():
                node.level=1
        if ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):
            raise ValueError('NON_IMPORT_CHANGE: '+p.name)
        conversions.append({'original':str(original_path),'original_sha256':sha(original_path),'isolated':str(p),'isolated_sha256':sha(p),'change':'relative imports only; AST equivalent after import normalization'})
    out.mkdir(parents=True)
    save(out,'audit/identity.json',{'status':'PARTIAL','host':platform.node(),'python':sys.version,'created_unix':time.time(),'protocol_version':args.protocol_version,'taskbook':{'path':str(task),'sha256':sha(task),'registered_sha256':TASKBOOK_SHA256_BY_PROTOCOL[args.protocol_version]},'frozen_top_sources':original,'plant_import_identity':'PASS','actuator_contract':'IMPLEMENTED_SIMULATION_ASSUMPTION_NOT_MEASURED','all_E00_complete':False})
    save(out,'audit/imports.json',{'runtime_modules':modules,'recursive_plant_conversion':conversions,'params':asdict(plant.ModelParams()),'event_defaults':asdict(event.EventSubstepConfig()),'allocation_defaults':asdict(steering_allocator.AllocationConfig())})
    roles={'status':'SOURCE_PENDING','training':'NOT_AUDITED','selection':'NOT_AUDITED','normalization':'NOT_AUDITED','historical_42_84':'EXPOSURE_AUDIT_REQUIRED','formal_data_authorized':False}
    save(out,'audit/data_roles.json',roles)
    save(out,'audit/submission_match.json',{'status':'SOURCE_PENDING','reason':'candidate TEX is not proof of submitted PDF identity'})
    save(out,'review/review_matrix.json',review)
    save(out,'protocol/methods.json',methods)
    save(out,'gates/E00.json',{'status':'PARTIAL','plant_source_identity':'PASS','actuator':'SOURCE_PENDING','data_role':'SOURCE_PENDING','input_time':'SOURCE_PENDING','submission':'SOURCE_PENDING','formal_allowed':False})
    print(json.dumps({'out':str(out),'plant_import_identity':'PASS','E00':'PARTIAL'}))

def self_test(args):
    out=Path(args.out)
    tests=[]
    def rejects(name,fn):
        try: fn()
        except ValueError: tests.append({'test':name,'pass':True}); return
        raise AssertionError(name+' accepted invalid input')
    rejects('modified_checkpoint_hash',lambda:require_hash(__file__,'0'*64))
    rejects('shifted_timestamp',lambda:require_interval(10,11,11))
    rejects('future_packet',lambda:require_packet(11,12,10))
    rejects('same_tick_delivery',lambda:require_packet(10,10,10))
    rejects('missing_baseline_source',lambda:require_source({'status':'SOURCE_PENDING'}))
    rejects('old_taskbook_as_new_protocol',lambda:require_taskbook_protocol(REV/'paper_v4/inputs/experiment_EXP-R2_417CFCDB.md','EXP-R3'))
    rejects('new_taskbook_as_old_protocol',lambda:require_taskbook_protocol(REV/'paper_v4/inputs/experiment.md','EXP-R2'))
    rejects('old_taskbook_as_exp_r4',lambda:require_taskbook_protocol(REV/'paper_v4/inputs/experiment.md','EXP-R4'))
    rejects('unknown_protocol_version',lambda:require_taskbook_protocol(REV/'paper_v4/inputs/experiment.md','EXP-R999'))
    rejects('incomplete_method_registry',lambda:require_registries_data({'core_methods':[]},{'items':[{'id':i} for i in EXPECTED_REVIEW_IDS]}))
    rejects('incomplete_review_matrix',lambda:require_registries_data({'core_methods':[{'key':i} for i in EXPECTED_METHOD_KEYS]},{'items':[]}))
    require_interval(10,10,11)
    require_packet(9,10,10)
    # Exact scalar pulse tests the new interval schema only, NOT the legacy recorder.
    u=np.array([0.,2.,0.,0.]);x=np.r_[0.,np.cumsum(.02*u)]
    assert np.allclose(np.diff(x),.02*u) and x[1]==0 and x[2]==.04
    tests.append({'test':'new_schema_pulse','pass':True,'legacy_recorder_proven':False})
    save(out,'tests/mandatory.json',{'status':'PASS','scope':'guard utility tests only; full experiment mandatory suite NOT_IMPLEMENTED','tests':tests})
    examples={'base_above':certificate(1.1,1.,.95),'zero_coupling':certificate(.9,0.,.95),'boundary_zero_coupling':certificate(.95,0.,.95),'boundary_positive_coupling':certificate(.95,1.,.95),'inside':certificate(.8,.3,.95)}
    assert examples['base_above']['gamma'] is None
    assert examples['boundary_positive_coupling']['gamma']==0
    a=np.array([[.9,10.],[0.,.9]])
    a1=np.array([[.5,2.],[0.,.5]]);a2=a1.T
    rho=lambda m:float(max(abs(np.linalg.eigvals(m))))
    examples.update({'nonnormal':{'matrix':a.tolist(),'rho':rho(a),'norm2':float(np.linalg.norm(a,2))},'switching':{'A1':a1.tolist(),'A2':a2.tolist(),'rho_A1':rho(a1),'rho_A2':rho(a2),'rho_product':rho(a2@a1)},'submitted_formula_match':'SOURCE_PENDING','full_closed_loop_proof':'NOT_RUN'})
    assert examples['nonnormal']['norm2']>1 and examples['switching']['rho_product']>1
    save(out,'E16/counterexamples.json',examples)
    print('PASS: utility negative tests and algebraic counterexamples; legacy time semantics and full theory NOT_RUN')

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('preflight');p.add_argument('--protocol-version',choices=sorted(TASKBOOK_SHA256_BY_PROTOCOL),required=True);p.add_argument('--taskbook',required=True);p.add_argument('--methods',required=True);p.add_argument('--review-matrix',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('self-test');p.add_argument('--suite',choices=['mandatory'],required=True);p.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        if args.command=='preflight':preflight(args)
        else:self_test(args)
    except (ValueError,AssertionError) as exc:
        print(str(exc),file=sys.stderr);return 22
    return 0

if __name__=='__main__':
    raise SystemExit(main())
