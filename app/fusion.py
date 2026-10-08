"""Time-aware planning state. All fixture values are explicitly simulated."""
from datetime import datetime, timezone
from . import physics as p
from .settings import TH, TEAM, TEXT, OCCUPANCY

def utcnow():
    return datetime.now(timezone.utc)

def stamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def aperture(multiple, ref_range):
    t = TH['aperture_tolerance']
    return [(1-t)*multiple*ref_range[0], (1+t)*multiple*ref_range[1]]

def compute(data, event_time, eta_scale=1, now=None):
    now = now or utcnow()
    eta = TH['eta_min'] * eta_scale
    result = dict(data)
    flags = list(data.get('flags', []))
    people = max(data.get('people_count', 0),1)
    result.update(eta_min=eta,people_count=people,flags=flags,
                  assumptions=['Typical reference dimensions','Rate and velocity classes','Tier cutoffs','Approximate ETA'])
    if data['family'] == 'flood':
        series = sorted(data['series'],key=lambda x:x['captured_at'])
        times = [(stamp(x['captured_at'])-stamp(series[0]['captured_at'])).total_seconds()/60 for x in series]
        fit = p.fit_rate(times,[x['mid'] for x in series],[(x['hi']-x['lo'])/2 for x in series]) if len(series)>1 else None
        prior = data.get('rate_class','moderate')
        rate,sigma = p.blend_rate(prior,fit)
        if prior == 'receding':
            rate = min(rate,0)
        recent = [x for x in series if (now-stamp(x['captured_at'])).total_seconds()/60 <= TH['recent_min']]
        d = p.fuse([(x['lo'],x['hi']) for x in recent]) if recent else dict(series[-1])
        flags.extend(d.get('flags',[]))
        for sample in series:
            flags.extend(f for f in sample.get('flags',[]) if f not in flags)
        if not recent:
            elapsed = max(0,(now-stamp(series[-1]['captured_at'])).total_seconds()/60)
            d = {k:p.depth_at(d[k],rate,elapsed,TH['depth_cap_m']) for k in ['lo','hi','mid']}
            flags.append('extrapolated')
        flow = data.get('flow_class','slow')
        if flow == 'unknown':
            flow = 'slow'
            flags.append('flow_assumed')
        contexts = data.get('contexts',[])
        mult = TH['stranded_multiplier'] if any(c in contexts for c in ['on_roof','stranded_ground_floor']) or ('in_vehicle' in contexts and d['mid'] >= TH['context_depth_m']['in_vehicle']) else 1
        if data.get('vulnerable'):
            mult *= TH['vulnerable_multiplier']
        mult = min(TH['multiplier_cap'],mult)
        # The latest capture time anchors the rate, not upload time.
        paths = []
        for minutes in range(0,TH['horizon_min']+1,10):
            paths.append(dict(t=minutes,best=p.depth_at(d['lo'],min(rate-sigma,0) if prior=='receding' else rate-sigma,minutes,TH['depth_cap_m']),
                              expected=p.depth_at(d['mid'],rate,minutes,TH['depth_cap_m']),
                              worst=p.depth_at(d['hi'],min(rate+sigma,0) if prior=='receding' else rate+sigma,minutes,TH['depth_cap_m'])))
        arriving = p.depth_at(d['mid'],rate,eta,TH['depth_cap_m'])
        critical = min([TH['context_depth_m'][c] for c in contexts if c in TH['context_depth_m']] or [TH['depths_m'][2]])
        deadline = p.time_to(critical,d['mid'],rate)
        worst_deadline = p.time_to(critical,d['hi'],min(rate+sigma,0) if prior=='receding' else rate+sigma)
        if deadline is not None and deadline < eta:
            flags.append('DEADLINE_RISK')
        result.update(depth=d,rate_m_min=rate,rate_sigma=sigma,flow_class=flow,multiplier=mult,
            depth_arrival_m=arriving,projections=paths,time_to_critical_min=deadline,worst_deadline_min=worst_deadline,
            threshold_times=[dict(depth_m=t,minutes=p.time_to(t,d['mid'],rate)) for t in TH['depths_m']],
            hazard_rating=p.hazard_rating(arriving,flow,data.get('debris','none')),
            hazard_class=p.hr_class(p.hazard_rating(arriving,flow,data.get('debris','none'))),
            priority_index=people*mult*p.severity(arriving,flow,data.get('debris','none')))
        result['assumptions'].extend(['Depth cap','Hazard floors','Vulnerability multipliers'])
        if prior == 'receding': flags.append('peaked or falling')
    else:
        zones = []
        for zone in data.get('zones',[]):
            h = sum(zone['height_m'])/2
            f = max(0,min(1,(h-TH['void_min_m'])/(TH['void_max_m']-TH['void_min_m'])))
            score = f*TH['type_factors'][zone['pattern']]*(.6+.2*zone.get('witness',0)+.2*zone.get('sign',0))*(1 if zone.get('access','easy')=='easy' else .7)
            zones.append(dict(zone,score=score,plausibility='high' if score>=TH['zone_classes'][0] else 'medium' if score>=TH['zone_classes'][1] else 'low',
                              entry='SHORE FIRST: do not enter' if zone.get('stability')=='unstable' else 'Structural assessment required'))
        zones.sort(key=lambda x:x['score'],reverse=True)
        z = max([x['score'] for x in zones] or [0])
        mass = data.get('mass_kg',[0,0])
        crew = 'manual_cribbing' if mass[1]<=TH['mass_limits_kg'][0] else 'airbags_hydraulic' if mass[1]<=TH['mass_limits_kg'][1] else 'crane_heavy'
        hours = max(0,(now-stamp(event_time)).total_seconds()/3600)
        pi = people*z*p.p_surv(hours+eta/60)
        result.update(zones=zones,zone_score=z,mass_kg=mass,crew=crew,event_age_h=hours,priority_index=pi,
                      time_to_critical_min=None,worst_deadline_min=None)
        if any(h in data.get('hazards',[]) for h in ['gas_smell','fire','live_wire']):
            flags.append('HOLD: hazard control first')
        if any(z.get('stability')=='unstable' for z in zones) or 'leaning_slab' in data.get('hazards',[]):
            flags.append('SHORE FIRST: do not enter')
        result['assumptions'].extend(['Aperture is an upper bound on interior space','Void fit and pattern factors','Illustrative survival curve','Slab density and extrication duration'])
    tier(result)
    result['footer'] = TEXT['footer']
    return result

def tier(site):
    a,b,c = TH['tiers']
    pi = site['priority_index']
    site['tier'] = 'P1' if pi>=a or 'DEADLINE_RISK' in site['flags'] else 'P2' if pi>=b else 'P3' if pi>=c else 'P4'
