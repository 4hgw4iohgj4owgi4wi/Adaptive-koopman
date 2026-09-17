from __future__ import annotations

import hashlib, json, os, platform, shutil, socket, sys
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest().upper()


def audit_sources(project, protocol, taskbook):
    project=Path(project).resolve(); p=Path(protocol).resolve(); t=Path(taskbook).resolve()
    cfg=json.loads(p.read_text(encoding="utf-8-sig"))
    paths={"project":project,"revision":project/"revision_2026","old_run":Path(cfg["old_run"]),
           "predictor_source":Path(cfg["predictor_source"]),"taskbook":t}
    missing=[k for k,v in paths.items() if not v.exists()]
    if missing: raise ValueError(f"missing sources: {missing}")
    if sha(t)!=cfg["taskbook_sha256"]: raise ValueError("taskbook identity changed")
    free=shutil.disk_usage(project).free
    if free < int(cfg["minimum_free_gib"])*1024**3: raise ValueError("disk reserve gate failed")
    return {"host":socket.gethostname(),"python":sys.executable,"platform":platform.platform(),
            "project":str(project),"protocol":str(p),"protocol_sha":sha(p),"taskbook":str(t),
            "taskbook_sha":sha(t),"old_run":str(paths["old_run"].resolve()),
            "predictor_source":str(paths["predictor_source"].resolve()),"free_bytes":free,
            "authorization":"R0/P0/K0/Q1 only; no training; stop after K1 verdict"}
