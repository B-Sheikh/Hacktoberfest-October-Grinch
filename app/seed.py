"""Eleven explicitly simulated sites from section 11 of the supplied spec."""
from datetime import timedelta
from .fusion import utcnow
from . import physics as p

def scenario():
    now=utcnow()
    def point(lo,hi,minutes=0):
        return dict(lo=lo,hi=hi,mid=(lo+hi)/2,captured_at=(now-timedelta(minutes=minutes)).isoformat())
    floods=[
        ('Rising water / vehicle',[point(.21,.36,10),point(.225,.45)],'rapid','moderate',2,['in_vehicle'],[],[]),
        ('Deep water / children',[point(.7,.9)],'steady','slow',3,[],['children'],[]),
        ('Slow rise',[point(.15,.25)],'slow','slow',1,[],[],[]),
        ('Water has peaked',[point(.3,.5)],'receding','slow',1,[],[],[]),
        ('Conflicting references',[dict(point(.10,.21),flags=['inconsistent'])],'moderate','slow',1,[],[],[]),
        ('Roof refuge',[point(.7,1)],'moderate','moderate',2,['on_roof'],[],[]),
        ('Submerged socket',[point(.3,.5)],'moderate','moderate',1,[],[],['live_wire'])]
    sites=[]
    for i,(name,series,rate,flow,people,contexts,vulnerable,hazards) in enumerate(floods):
        sites.append(dict(id=f'demo-{i+1}',name=name,family='flood',scene_type='flood',lat=11.0168+i*.004,lon=76.9558+i*.003,
            series=series,rate_class=rate,flow_class=flow,people_count=people,contexts=contexts,vulnerable=vulnerable,hazards=hazards,debris='some' if i==0 else 'none',flags=[]))
    def zone(id,lo,hi,pattern,sign=0,stability='uncertain'):
        return dict(zone_id=id,height_m=[lo,hi],pattern=pattern,sign=sign,witness=sign,access='easy',stability=stability)
    sites.extend([
        dict(id='demo-8',name='Lean-to / reported tapping',family='collapse',scene_type='collapse',lat=11.048,lon=76.96,people_count=2,
             zones=[zone('A',.1,.14,'pancake'),zone('B',.30,.4,'lean_to',1),zone('C',.2,.4,'cantilever',stability='unstable')],mass_kg=[2160,8400],hazards=['leaning_slab'],flags=[]),
        dict(id='demo-9',name='School / pancake',family='collapse',scene_type='collapse',lat=11.052,lon=76.97,people_count=120,
             zones=[zone('A',.1,.14,'pancake')],mass_kg=[4320,16800],hazards=[],flags=['assumed occupancy']),
        dict(id='demo-10',name='Damaged standing / gas reported',family='collapse',scene_type='damaged_standing',lat=11.04,lon=76.985,people_count=2,
             zones=[zone('A',.2,.4,'unknown',stability='unstable')],mass_kg=[2160,8400],hazards=['gas_smell'],flags=[]),
        dict(id='demo-11',name='Rubble near rising flood',family='collapse',scene_type='collapse',lat=11.017,lon=76.956,people_count=2,
             zones=[zone('A',.3,.5,'lean_to',1)],mass_kg=[2160,8400],hazards=['water_entering'],flags=[])])
    teams=[]
    for i,kind in enumerate(['boat','boat','rescue_4x4','rescue_4x4','heavy_usar','light_crew','light_crew']):
        teams.append(dict(id=f'demo-team-{i+1}',name=f'{kind.replace("_"," ").title()} {i+1}',type=kind,base_lat=11.007+i*.008,base_lon=76.95+i*.004,available=True,swiftwater_trained=False))
    return now,sites,teams
