from __future__ import annotations
import argparse,json,time
from pathlib import Path
from typing import Any
import audit
from config import EFDR12Config,seed_block

HERE=Path(__file__).resolve().parent

def write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")

def log(cfg:EFDR12Config,number:str,title:str,lines:list[str])->None:
    path=cfg.results/"work_log.md";path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_text("# EFD-R1.2工作记录\n",encoding="utf-8")
    with path.open("a",encoding="utf-8") as h:h.write(f"\n## {number} {title}\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"+"\n".join(f"- {x}" for x in lines)+"\n")

def solution(cfg:EFDR12Config,title:str,facts:list[str],causes:list[str],alternatives:list[str],actions:list[str],impact:str,recovery:str)->None:
    path=cfg.results/"solutions.md";path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_text("# EFD-R1.2问题与处置\n",encoding="utf-8")
    sections=(("已核实事实",facts),("最可能原因",causes),("替代解释",alternatives),("允许修复与成本",actions))
    with path.open("a",encoding="utf-8") as h:
        h.write(f"\n## {title}\n")
        for name,rows in sections:h.write(f"\n### {name}\n\n"+"\n".join(f"- {x}" for x in rows)+"\n")
        h.write(f"\n### 论文影响\n\n{impact}\n\n### 恢复条件\n\n{recovery}\n")

def t0(cfg:EFDR12Config)->bool:
    stage=cfg.results/"t0_freeze";protocol=HERE/"protocol.md";actual=audit.sha256(protocol)
    if actual!=cfg.protocol_sha256:
        write_json(stage/"complete.json",{"stage":"T0","passed":False,"expected":cfg.protocol_sha256,"actual":actual});return False
    from history_audit import run as history
    hist=history(cfg.project_root);write_json(stage/"r11_history_audit.json",hist)
    audits={};selected=None
    for base in cfg.base_candidates:
        check=audit.seed_collisions(cfg.project_root/"revision_2026",sum(seed_block(base).values(),[]));audits[str(base)]=check
        if check["passed"]:selected=base;break
    write_json(stage/"seed_audit.json",{"candidates":audits,"selected_base":selected})
    source={"protocol":protocol,"plant":cfg.project_root/"revision_2026"/"model"/"four_vehicle_coupled.py","compare_pipeline":cfg.koopman/"compare_pipeline.py","actual_irsp":cfg.project_root/"revision_2026"/"03_irsp"/"actual_irsp_matrices.npz","H2":cfg.koopman/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz"}
    hashes={k:{"path":str(p),"sha256":audit.sha256(p),"bytes":p.stat().st_size} for k,p in source.items()};write_json(stage/"source_hashes.json",hashes);write_json(stage/"environment.json",audit.environment())
    passed=bool(hist["passed"] and selected is not None);result={"stage":"T0","passed":passed,"selected_base":selected,"protocol_sha256":actual,"r11_evidence_role":hist["r11_evidence_role"],"source_hashes":hashes}
    write_json(stage/"complete.json",result);log(cfg,"R12001","T0证据链、seed和历史树冻结",[f"结果={result}",f"seed审计={audits}","R1.1修复后S2=12/12通过，S3为正式证据，S4正式失败"]);return passed

def t1(cfg:EFDR12Config)->bool:
    if not t0(cfg):return False
    from legacy_adapter import run as regress
    stage=cfg.results/"t1_legacy_adapter";result=regress(cfg.project_root);write_json(stage/"method_identity.json",result["method_identity"]);write_json(stage/"tests.json",result)
    passed=bool(result["passed"]);write_json(stage/"complete.json",{"stage":"T1","passed":passed,"reason":result["method_identity"].get("reason")})
    log(cfg,"R12002","T1真实历史适配器与方法身份门",[f"结果={result}","结论=停止，不生成R1.2 pilot"])
    if not passed:
        ident=result["method_identity"]
        solution(cfg,"T1方法身份不成立",[ident["reason"],f"compare K3 shapes={ident['compare_k3_shapes']}",f"actual IRSP shapes={ident['actual_irsp_shapes']}",f"continuous audit={ident['actual_irsp_audit']['continuous_domain_audit']}"],["R1.2把compare_pipeline中的结构化低秩K3误写成bilinear+IRSP；二者不是同一个冻结模型。"],["真正IRSP位于revision_2026/03_irsp，来自TF14的31维lift/2输入模型；它不能直接消费四车92维fixed lift和8维控制。"],["小修不可解决。需修订协议：将C2/F3拆为K3-structured与TF14-IRSP-reference，或为四车模型预注册并重新训练新的IRSP；约0.5天修协议，1—2天训练/审计。"],"当前不能声称已复现历史四车IRSP，也不能用K3.npz代替IRSP支撑论文稳定保护主张。","提供真实四车IRSP冻结artifact及其历史输出cache，或发布R1.2a协议明确删除四车IRSP逐元素复现门后，重新从T0开始。")
    return passed

def blocked(cfg:EFDR12Config,stage:str)->bool:
    if not t1(cfg):
        write_json(cfg.results/stage/"complete.json",{"stage":stage.upper(),"passed":False,"blocked_by":"T1 method identity hard gate","executed":False});return False
    raise NotImplementedError(stage)

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--stage",choices=tuple(f"t{i}" for i in range(10)),required=True);p.add_argument("--workers",type=int,default=8);a=p.parse_args();cfg=EFDR12Config(a.project_root.resolve())
    ok=t0(cfg) if a.stage=="t0" else t1(cfg) if a.stage=="t1" else blocked(cfg,a.stage)
    print(json.dumps({"stage":a.stage,"passed":ok,"results":str(cfg.results)},ensure_ascii=False),flush=True);raise SystemExit(0 if ok else 2)

if __name__=="__main__":main()
