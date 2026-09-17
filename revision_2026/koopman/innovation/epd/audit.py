from __future__ import annotations
import hashlib,json,platform,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write_json(path:Path,value)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def log(results:Path,rid:str,title:str,lines:list[str])->None:
 p=results/'work_log.md';p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a',encoding='utf-8') as f:f.write(f"\n## {rid} {title}\n\n- 时间：{datetime.now(timezone.utc).astimezone().isoformat()}\n"+''.join(f'- {x}\n' for x in lines))
def solution(results:Path,title:str,facts:list[str],kind:str,hyp:list[str],allowed:list[str],impact:list[str],recovery:list[str])->None:
 p=results/'solutions.md'
 with p.open('a',encoding='utf-8') as f:
  f.write(f'\n## {title}\n\n### 已核实事实\n'+''.join(f'- {x}\n' for x in facts)+f'\n### 判断\n- {kind}\n\n### 可能原因（假设）\n'+''.join(f'- {x}\n' for x in hyp)+'\n### 允许修复\n'+''.join(f'- {x}\n' for x in allowed)+'\n### 论文影响\n'+''.join(f'- {x}\n' for x in impact)+'\n### 恢复条件和成本\n'+''.join(f'- {x}\n' for x in recovery))

