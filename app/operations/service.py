"""Operations domain helpers"""
from app import settings
from app.common import require_alert
from app.intelligence import physics as p
from app.intelligence.fusion import compute
from app.intelligence.fusion import tier
from app.operations.guidance import briefing
from urllib.parse import urlencode
import json

def list_sites(c,scale=1,alert_id=None):
    rows=c.execute('SELECT * FROM incidents'+(' WHERE alert_id=?' if alert_id else ''),(alert_id,) if alert_id else ()).fetchall()
    output=[]
    for row in rows:
        alert=require_alert(c,row['alert_id'])
        state=compute(json.loads(row['data']),alert['event_time'],scale)
        state.update(id=row['id'],alert_id=row['alert_id'],lat=row['lat'],lon=row['lon'],status=row['status'])
        state['n_reports']=c.execute('SELECT count(*) FROM reports WHERE incident_id=? AND duplicate=0',(row['id'],)).fetchone()[0]
        if state.get('demo_fixture'): state['n_reports']=len(state.get('series',[])) or 1
        assigned=c.execute('SELECT data FROM assignments WHERE incident_id=?',(row['id'],)).fetchone()
        state['assignment']=json.loads(assigned['data']) if assigned else None
        output.append(state)
    for site in output:
        if site['family']=='collapse' and any(f['family']=='flood' and f['alert_id']==site['alert_id'] and f['depth_arrival_m']>=settings.TH['depths_m'][0] and p.haversine((site['lat'],site['lon']),(f['lat'],f['lon']))*1000<=settings.TH['compound_m'] for f in output):
            site['flags'].append('rubble voids may flood')
            site['compound_multiplier']=settings.TH['compound_multiplier']
            site['priority_index']*=site['compound_multiplier']
            site['assumptions'].append('Compound hazard multiplier')
            tier(site)
        site['briefing']=briefing(site)
        coords=f"{site['lat']},{site['lon']}"
        site['navigation']={'Google Maps':'https://www.google.com/maps/dir/?'+urlencode({'api':1,'destination':coords,'travelmode':'driving'}),
                            'Apple Maps':'https://maps.apple.com/?'+urlencode({'daddr':coords}),'Geo':'geo:'+coords}
    return sorted(output,key=lambda s:(-s['priority_index'],s['id']))
