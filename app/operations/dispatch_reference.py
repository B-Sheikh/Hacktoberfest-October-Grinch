import numpy as np
from scipy.optimize import linear_sum_assignment
from ..intelligence.physics import *
sites = {  # id: (lat,lon, P, M, d0, rate, v)
 "S1": (10.000,76.000, 2,1.5, 0.40,0.020,"moderate"),
 "S2": (10.020,76.010, 3,1.0, 0.80,0.000,"moderate"),
 "S3": (10.050,76.050, 1,1.0, 0.20,0.003,"slow"),
}
base=(10.0,76.0); teams={"T1":"rescue_4x4","T2":"boat","T3":"light_crew"}
def run(scale=1.0):
    ids=list(sites); tn=list(teams); V=np.zeros((len(tn),len(ids)))
    for i,t in enumerate(tn):
        for j,s in enumerate(ids):
            la,lo,P,M,d0,rt,v=sites[s]; ty=teams[t]
            dist=haversine(base,(la,lo)); T=travel_min(ty,dist,d0)*scale
            d_arr=depth_at(d0,rt,T)
            ok=feasible(ty,d_arr,v)
            V[i,j]= flood_benefit(P,M,d0,rt,v,"none",T) if ok else -1e3
    r,c=linear_sum_assignment(-V)
    return [(tn[i],ids[j],round(V[i,j],3)) for i,j in zip(r,c) if V[i,j]>0], np.round(V,2)
