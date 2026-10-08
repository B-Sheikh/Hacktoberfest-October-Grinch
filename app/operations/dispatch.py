"""Assignment benefits decrease with delay; headline severity may increase."""
import numpy as np
from scipy.optimize import linear_sum_assignment
from ..intelligence import physics as p
from ..settings import TH, TEAM

def plan(teams, sites, scale=1, horizon=None):
    available = [t for t in teams if t['available']]
    sites = [s for s in sites if s['status'] not in ['resolved','escalate']]
    matrix = np.full((len(available),len(sites)),-1000.0)
    etas = {}
    for i,team in enumerate(available):
        for j,site in enumerate(sites):
            depth = site.get('depth',{}).get('mid',0)
            dist = p.haversine((team['base_lat'],team['base_lon']),(site['lat'],site['lon']))
            eta = p.travel_min(team['type'],dist,depth,TEAM['mobilise_min'],TEAM['detour'])*scale
            etas[i,j] = eta
            if any('HOLD' in f for f in site['flags']): continue
            if site['family']=='flood':
                d_arr = p.depth_at(depth,site['rate_m_min'],eta,TH['depth_cap_m'])
                kind=team['type']; spec=TEAM['specs'][kind]
                if kind=='boat':
                    ok=d_arr>=TEAM['boat_min_depth_m'] and (site['flow_class']!='rapid' or team['swiftwater_trained'])
                else:
                    ok=d_arr<=spec['max_depth_m'] and (kind!='light_crew' or p.hazard_rating(d_arr,site['flow_class'],site.get('debris','none'))<TEAM['light_max_hr'])
                if ok:
                    matrix[i,j]=p.flood_benefit(site['people_count'],site['multiplier'],depth,site['rate_m_min'],site['flow_class'],site.get('debris','none'),eta,horizon or TH['horizon_min'])
            elif team['type']=='heavy_usar':
                matrix[i,j]=p.collapse_benefit(site['people_count'],site['zone_score'],site['event_age_h'],eta,site['crew'])*site.get('compound_multiplier',1)
    chosen={}
    if matrix.size:
        rows,cols=linear_sum_assignment(-matrix)
        chosen={j:i for i,j in zip(rows,cols) if matrix[i,j]>0}
    outcomes=[]
    for j,site in enumerate(sites):
        flags=[]; i=chosen.get(j)
        candidates=[etas[k,j] for k in range(len(available)) if matrix[k,j]>=0]
        if not candidates:
            flags.append('NO_CAPABLE_TEAM')
        elif i is None:
            flags.append('NO_AVAILABLE_TEAM')
        deadline=site.get('time_to_critical_min')
        if candidates and deadline is not None and min(candidates)>deadline:
            flags.append('UNREACHABLE_IN_TIME')
        if i is not None and site.get('worst_deadline_min') is not None and etas[i,j]>site['worst_deadline_min']:
            flags.append('DEADLINE_RISK')
        outcomes.append(dict(incident_id=site['id'],team_id=available[i]['id'] if i is not None else None,
            eta_min=etas[i,j] if i is not None else None,benefit=float(matrix[i,j]) if i is not None else 0,flags=flags))
    return outcomes
