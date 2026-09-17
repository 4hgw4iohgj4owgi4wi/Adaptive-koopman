"""Frozen EXP-R1 reference geometry builders.

The hairpin uses arc length as its independent variable.  Two cubic-smoothstep
curvature ramps preserve continuous curvature and a total heading change of pi.
"""
from __future__ import annotations

import numpy as np


def _smoothstep(z):
    z=np.asarray(z,float)
    return 3*z*z-2*z*z*z


def build_hairpin(radius_m=11.5,straight_m=24.0,transition_m=11.0,ds_m=0.002):
    """Return a left 180-degree hairpin sampled by true path arc length.

    The constant-curvature length is ``pi*radius-transition`` because the two
    symmetric ramps together contribute the missing ``transition/radius``
    heading.  Therefore the requested heading change remains exactly pi rather
    than silently widening the turn by adding ramps to a full semicircle.
    """
    radius_m=float(radius_m);straight_m=float(straight_m);transition_m=float(transition_m);ds_m=float(ds_m)
    if min(radius_m,straight_m,transition_m,ds_m)<=0 or transition_m>=np.pi*radius_m:
        raise ValueError('invalid hairpin dimensions')
    constant_m=np.pi*radius_m-transition_m
    boundaries=np.cumsum([0.,straight_m,transition_m,constant_m,transition_m,straight_m])
    length=float(boundaries[-1]);count=int(np.ceil(length/ds_m))+1
    s=np.linspace(0.,length,count);k=np.zeros_like(s)
    entry=(s>=boundaries[1])&(s<boundaries[2]);z=(s[entry]-boundaries[1])/transition_m;k[entry]=_smoothstep(z)/radius_m
    middle=(s>=boundaries[2])&(s<boundaries[3]);k[middle]=1./radius_m
    leave=(s>=boundaries[3])&(s<boundaries[4]);z=(s[leave]-boundaries[3])/transition_m;k[leave]=(1.-_smoothstep(z))/radius_m
    h=np.zeros_like(s);d=np.diff(s);h[1:]=np.cumsum(.5*(k[:-1]+k[1:])*d)
    x=np.zeros_like(s);y=np.zeros_like(s)
    x[1:]=np.cumsum(.5*(np.cos(h[:-1])+np.cos(h[1:]))*d)
    y[1:]=np.cumsum(.5*(np.sin(h[:-1])+np.sin(h[1:]))*d)
    return {'s_m':s,'x_m':x,'y_m':y,'heading_rad':h,'curvature_1pm':k,'boundaries_m':boundaries,'radius_m':radius_m,'transition_m':transition_m,'constant_curvature_length_m':constant_m}
