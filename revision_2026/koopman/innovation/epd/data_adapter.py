from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
H=20
def _params(meta):
 p=meta['params'];return {'mass':p['payload']['mass_kg'],'mu':p['vehicle']['mu'],'k':p['connector']['stiffness_npm'],'c':p['connector']['damping_nspm'],'l0':p['connector']['free_play_m'],'length':p['payload'].get('length_m',5.),'width':p['payload'].get('width_m',2.)}
def rows(root:Path,splits):
 man=json.loads((root/'manifest.json').read_text(encoding='utf-8'))['completed'];out=[]
 for m in man:
  if m['split'] not in splits:continue
  with np.load(root/m['split']/m['base_file'],allow_pickle=False) as z:
   meta=json.loads(str(z['metadata_json'].item()));arr={k:np.asarray(z[k]) for k in ('state46','state30','control','connector_disp','connector_vel','force_payload','q','initial_state64','control64') if k in z.files}
  meta.update({k:m[k] for k in ('split','scenario','seed','base_family_id') if k in m});out.append({'meta':meta,'params':_params(meta),'arrays':arr})
 return out
def windows(rs):
 out={k:[] for k in ('x0','u','truth','force','q')};family=[];scenario=[];pars={k:[] for k in ('mass','mu','k','c','l0','length','width')}
 for i,r in enumerate(rs):
  a=r['arrays'];orig=np.arange(0,len(a['control'])-H+1,H);n=len(orig)
  out['x0'].append(a['state46'][orig]);out['u'].append(np.asarray([a['control'][j:j+H] for j in orig]));out['truth'].append(np.asarray([a['state46'][j+1:j+H+1] for j in orig]));out['force'].append(np.asarray([a['force_payload'][j+1:j+H+1] for j in orig]));out['q'].append(np.asarray([a['q'][j+1:j+H+1] for j in orig]));family.extend([i]*n);scenario.extend([r['meta']['scenario']]*n)
  for k in pars:pars[k].extend([r['params'][k]]*n)
 return {**{k:np.concatenate(v) for k,v in out.items()},'family':np.asarray(family),'scenario':np.asarray(scenario),**{k:np.asarray(v) for k,v in pars.items()}}
