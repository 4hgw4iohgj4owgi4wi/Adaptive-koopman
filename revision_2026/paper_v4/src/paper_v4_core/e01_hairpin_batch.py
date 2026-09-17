import argparse,json
from pathlib import Path
from .e01_hairpin import run
from .cli import save
def main(root):
 root=Path(root);root.mkdir(parents=True,exist_ok=False);done=[]
 for p in ['P0','P1','P2']:
  for label,step in [('2ms',.002),('1ms',.001),('0.5ms',.0005)]:
   run(root/f'{p}_{label}',p,step);done.append(f'{p}_{label}');save(root,'batch.json',{'status':'RUNNING','completed':done})
 save(root,'batch.json',{'status':'PASS','completed':done});print(json.dumps({'status':'PASS','completed':len(done)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);main(p.parse_args().root)
