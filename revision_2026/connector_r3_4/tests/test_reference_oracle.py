from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from reference_oracle import OracleConfig,solve_oracle

def test_oracle_event_restart_and_residual():
    r=solve_oracle('R3',0.,.25,.02)
    assert r['status']=='PASS' and r['segments']>=2
    assert any(e['surface']=='smoothing' for e in r['events'])
    assert r['max_event_residual_m']<=1e-8 and r['time_conservation_residual_s']<=1e-12

def test_oracle_tolerance_tightening_is_stable():
    a=solve_oracle('V1',0.,.25,.02,OracleConfig())
    b=solve_oracle('V1',0.,.25,.02,OracleConfig(2.5e-12,2.5e-14,2.5e-12,2.5e-13))
    assert abs(a['impulse_ns']-b['impulse_ns'])/max(abs(b['impulse_ns']),1e-12)<=2e-4
