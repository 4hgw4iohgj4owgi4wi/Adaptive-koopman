"""Independent geometry checks for the frozen EXP-R1 hairpin."""
import argparse,json
from pathlib import Path
import numpy as np
from .cli import save,sha
from .references import build_hairpin

def main(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);r=build_hairpin();s=r['s_m'];x=r['x_m'];y=r['y_m'];h=r['heading_rad'];k=r['curvature_1pm'];b=r['boundaries_m']
 # During the turning portion, radial error from the unsmoothed R=11.5 m
 # semicircle is a transparent geometry-deviation diagnostic.
 turn=(s>=b[1])&(s<=b[4]);radial=np.abs(np.hypot(x[turn]-24.,y[turn]-r['radius_m'])-r['radius_m'])
 report={'status':'PASS','route_length_m':float(s[-1]),'entry_straight_m':24.,'exit_straight_m':24.,'radius_m':r['radius_m'],'transition_m':r['transition_m'],'heading_change_rad':float(h[-1]),'heading_error_from_pi_rad':float(abs(h[-1]-np.pi)),'curvature_min_1pm':float(k.min()),'curvature_max_1pm':float(k.max()),'max_adjacent_curvature_jump_1pm':float(np.max(abs(np.diff(k)))),'terminal_xy_m':[float(x[-1]),float(y[-1])],'terminal_heading_rad':float(h[-1]),'max_turn_radial_deviation_from_ideal_semicircle_m':float(radial.max()),'source_sha':sha(__file__),'reference_sha':sha(Path(__file__).with_name('references.py'))}
 if report['heading_error_from_pi_rad']>2e-7 or abs(k[0])>1e-14 or abs(k[-1])>1e-14:report['status']='FAIL'
 np.savez_compressed(out/'hairpin.npz',**r);save(out,'geometry.json',report);print(json.dumps(report))
 if report['status']!='PASS':raise SystemExit(20)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
