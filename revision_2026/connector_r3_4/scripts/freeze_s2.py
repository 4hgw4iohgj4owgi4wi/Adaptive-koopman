from __future__ import annotations
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root.parent/'connector_r3_4_results/r0/source_manifest_s2.json'
def sha(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
m={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix.lower() in {'.py','.md','.json'}}
out.write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps({'files':len(m),'path':str(out)}))
