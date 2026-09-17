"""Finite sequential E01 100 m batch; stops on first failed trajectory."""
import argparse,time,traceback
from pathlib import Path
from .cli import save,sha
from .e01_100m import run,PARAMS

def main(root):
 root=Path(root)
 if root.exists():raise ValueError('refuse existing batch root')
 root.mkdir(parents=True)
 registration={'task':'E01 100m subset','role':'DEV','seed':'deterministic','parameters':PARAMS,'max_step_ms':[2.,1.,.5],'order':[f'{p}_{s:g}ms' for p in PARAMS for s in [2.,1.,.5]],'stop':'first non-PASS','expected':9,'required_outputs':['raw.npz','substeps.npz','metrics.json'],'runner_sha':sha(Path(__file__).with_name('e01_100m.py')),'batch_sha':sha(__file__)}
 save(root,'registration.json',registration);done=[];started=time.time();status='PASS'
 for p in PARAMS:
  for step in [2.,1.,.5]:
   name=f'{p}_{step:g}ms'
   try:
    run(root/name,p,step/1000,None);done.append({'run':name,'status':'PASS'})
   except BaseException as exc:
    status='FAIL';done.append({'run':name,'status':'FAIL','error':repr(exc),'traceback':traceback.format_exc()});save(root,'batch.json',{'status':status,'completed':done,'started_unix':started,'updated_unix':time.time()});raise
   save(root,'batch.json',{'status':status,'completed':done,'started_unix':started,'updated_unix':time.time()})
 print({'status':status,'completed':len(done)})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);main(p.parse_args().root)
