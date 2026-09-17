from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from reference_oracle import solve_oracle
print(json.dumps(solve_oracle('R3',0.,.25,.02),indent=2))
