import io
import json
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from . import db, settings, physics as p
from .dispatch import plan
from .fusion import compute, tier, utcnow
from .guidance import briefing
from .models import AlertInput, DispatchInput, TeamInput, FieldUpdate
from .seed import scenario
from .vision.client import extract

STATIC=Path(__file__).parent/'static'
def dump(value): return json.dumps(value,allow_nan=False)
def identity(): return uuid.uuid4().hex

@asynccontextmanager
async def lifespan(app):
    db.init()
    settings.UPLOADS.mkdir(parents=True,exist_ok=True)
    yield

app=FastAPI(title='Waterline',version='0.1.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=STATIC),name='static')

def require_alert(c,alert_id):
    row=c.execute('SELECT data FROM alerts WHERE id=?',(alert_id,)).fetchone()
    if not row: raise HTTPException(404,'Alert not found')
    return json.loads(row['data'])

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

@app.get('/')
def home(): return RedirectResponse('/command')

@app.get('/authority')
@app.get('/command')
@app.get('/field/{team_id}')
def console(team_id: str | None=None): return FileResponse(STATIC/'index.html')

@app.get('/r/{token}')
def resident(token: str):
    with db.connection() as c:
        if not c.execute('SELECT 1 FROM recipients WHERE token=?',(token,)).fetchone(): raise HTTPException(404,'Invalid reporting link')
    return FileResponse(STATIC/'report.html')

@app.get('/api/config')
def public_config():
    return {'thresholds':settings.TH,'templates':settings.TEXT,'teams':settings.TEAM}

@app.get('/api/health')
def health():
    with db.connection() as c: c.execute('SELECT 1').fetchone()
    return {'status':'ok','db':'ok','provider':'mock','model':None,'version':'0.1.0','live_vision_implemented':False}

@app.get('/api/alerts')
def alerts():
    with db.connection() as c: return [json.loads(r['data']) for r in c.execute('SELECT data FROM alerts')]

@app.post('/api/alerts',status_code=201)
def create_alert(body:AlertInput):
    if body.event_time>utcnow(): raise HTTPException(422,'Event time cannot be in the future')
    value=body.model_dump(mode='json'); value.pop('phones'); value['id']=identity()
    tokens=[]
    with db.connection() as c:
        c.execute('INSERT INTO alerts(id,data) VALUES (?,?)',(value['id'],dump(value)))
        for phone in body.phones:
            token=secrets.token_urlsafe(32)
            c.execute('INSERT INTO recipients(token,alert_id,phone) VALUES (?,?,?)',(token,value['id'],phone))
            tokens.append({'token':token,'link':f'{settings.PUBLIC_BASE_URL}/r/{token}'})
    return dict(value,recipients=tokens)

@app.get('/api/report-link/{token}')
def report_context(token:str):
    with db.connection() as c:
        row=c.execute('SELECT alert_id FROM recipients WHERE token=?',(token,)).fetchone()
        if not row: raise HTTPException(404,'Invalid reporting link')
        return require_alert(c,row['alert_id'])

@app.post('/api/alerts/{alert_id}/send')
def send(alert_id:str):
    with db.connection() as c:
        alert=require_alert(c,alert_id)
        for row in c.execute('SELECT * FROM recipients WHERE alert_id=?',(alert_id,)).fetchall():
            link=f"{settings.PUBLIC_BASE_URL}/r/{row['token']}"
            message=(alert['message']+' '+link) if alert['message'] else settings.TEXT['sms'].format(hazard=alert['hazard'],link=link)
            c.execute("UPDATE recipients SET status='simulated',message=? WHERE token=?",(message,row['token']))
    return {'status':'simulated','alert_id':alert_id,'real_sms_implemented':False}

@app.get('/api/outbox')
def outbox():
    with db.connection() as c: return [dict(r) for r in c.execute("SELECT * FROM recipients WHERE status!='pending'")]

@app.post('/api/seed')
def seed():
    now,sites,teams=scenario()
    alert={'id':'demo-alert','hazard':'flash_flood','center_lat':11.0168,'center_lon':76.9558,'radius_m':3000,'event_time':(now-timedelta(minutes=40)).isoformat(),'message':'Simulated demonstration','magnitude':None}
    with db.connection() as c:
        c.execute('DELETE FROM alerts WHERE demo=1')
        c.execute('INSERT INTO alerts(id,data,demo) VALUES (?,?,1)',('demo-alert',dump(alert)))
        for site in sites:
            site.update(simulated=True,demo_fixture=True,extraction_status='mock')
            c.execute('INSERT INTO incidents(id,alert_id,family,lat,lon,data) VALUES (?,?,?,?,?,?)',(site['id'],'demo-alert',site['family'],site['lat'],site['lon'],dump(site)))
        for team in teams: c.execute('INSERT OR REPLACE INTO teams(id,data) VALUES (?,?)',(team['id'],dump(team)))
    return {'alert_id':'demo-alert','incidents':len(sites),'teams':len(teams),'simulated':True}

@app.get('/api/incidents')
def incidents(eta_scale:Annotated[float,Query(ge=.5,le=3)]=1,alert_id:str|None=None):
    with db.connection() as c: return list_sites(c,eta_scale,alert_id)

@app.get('/api/incidents/{incident_id}')
def incident(incident_id:str,eta_scale:Annotated[float,Query(ge=.5,le=3)]=1):
    with db.connection() as c:
        site=next((s for s in list_sites(c,eta_scale) if s['id']==incident_id),None)
        if not site: raise HTTPException(404,'Site not found')
        return site

@app.get('/api/teams')
def teams():
    with db.connection() as c: return [json.loads(r['data']) for r in c.execute('SELECT data FROM teams')]

@app.post('/api/teams')
def upsert_team(body:TeamInput):
    value=body.model_dump()
    with db.connection() as c: c.execute('INSERT OR REPLACE INTO teams(id,data) VALUES (?,?)',(body.id,dump(value)))
    return value

@app.post('/api/dispatch/run')
def dispatch(body:DispatchInput):
    with db.connection() as c:
        teams=[json.loads(r['data']) for r in c.execute('SELECT data FROM teams')]
        result=plan(teams,list_sites(c,body.eta_scale),body.eta_scale,body.horizon_min)
        c.execute('DELETE FROM assignments')
        c.execute("UPDATE incidents SET status='open' WHERE status='assigned'")
        for value in result:
            if value['team_id']:
                c.execute('INSERT INTO assignments(team_id,incident_id,data) VALUES (?,?,?)',(value['team_id'],value['incident_id'],dump(value)))
                c.execute("UPDATE incidents SET status='assigned' WHERE id=? AND status='open'",(value['incident_id'],))
    return result

@app.post('/api/incidents/{incident_id}/field_update')
def field_update(incident_id:str,body:FieldUpdate):
    with db.connection() as c:
        if not c.execute('SELECT 1 FROM incidents WHERE id=?',(incident_id,)).fetchone(): raise HTTPException(404,'Site not found')
        if not c.execute('SELECT 1 FROM assignments WHERE incident_id=? AND team_id=?',(incident_id,body.team_id)).fetchone(): raise HTTPException(409,'Team is not assigned to this site')
        value=dict(body.model_dump(),created_at=utcnow().isoformat())
        site=next(s for s in list_sites(c) if s['id']==incident_id)
        value['estimate_at_measurement']=site.get('depth')
        c.execute('INSERT INTO field_updates(id,incident_id,data) VALUES (?,?,?)',(identity(),incident_id,dump(value)))
        if body.status: c.execute('UPDATE incidents SET status=? WHERE id=?',(body.status,incident_id))
    return value

@app.get('/api/benchmark')
def benchmark():
    with db.connection() as c: updates=[json.loads(r['data']) for r in c.execute('SELECT data FROM field_updates')]
    samples=[]
    for u in updates:
        d=u.get('estimate_at_measurement')
        if u['depth_cm'] is not None and d:
            samples.append(dict(error_cm=abs(u['depth_cm']-d['mid']*100),inside_interval=d['lo']*100<=u['depth_cm']<=d['hi']*100))
    return {'sample_count':len(samples),'mean_absolute_error_cm':sum(s['error_cm'] for s in samples)/len(samples) if samples else None,
            'fraction_inside_interval':sum(s['inside_interval'] for s in samples)/len(samples) if samples else None,'samples':samples}

@app.post('/api/reports',status_code=201)
async def report(token:Annotated[str,Form()],images:Annotated[list[UploadFile],File()],
                 lat:Annotated[float,Form(ge=-90,le=90)],lon:Annotated[float,Form(ge=-180,le=180)],
                 accuracy:Annotated[float,Form(gt=0)]=100,pin:Annotated[bool,Form()]=False,
                 state:Annotated[str,Form()]='safe',people_count:Annotated[int,Form(ge=0,le=10000)]=0,
                 note:Annotated[str,Form(max_length=2000)]='',vulnerable:Annotated[str,Form()]=''):
    if state not in ['need_help','safe','third_party']: raise HTTPException(422,'Unknown reporter state')
    if not 1<=len(images)<=settings.TH['max_images']: raise HTTPException(422,'Supply one to four photos')
    with db.connection() as c:
        row=c.execute('SELECT alert_id FROM recipients WHERE token=?',(token,)).fetchone()
        if not row: raise HTTPException(403,'Invalid reporting link')
        alert=require_alert(c,row['alert_id'])
    prepared=[]
    for upload in images:
        raw=await upload.read(settings.TH['max_upload_bytes']+1)
        if len(raw)>settings.TH['max_upload_bytes']: raise HTTPException(413,'Photo exceeds upload limit')
        try:
            image=Image.open(io.BytesIO(raw))
            if image.width*image.height>settings.TH['max_image_pixels']: raise HTTPException(413,'Photo has too many pixels')
            image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((settings.TH['resize_px'],settings.TH['resize_px']))
            grey=list(image.convert('L').resize((8,8)).tobytes())
            mean=sum(grey)/len(grey)
            hashed=''.join('1' if v>=mean else '0' for v in grey)
            prepared.append((image,hashed,upload.filename or 'flood'))
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            raise HTTPException(422,'Unreadable image')
    now=utcnow(); extraction,status=extract(prepared[0][2])
    intervals=[p.ref_interval(r['ref_id'],r['waterline_bin']) for r in extraction['references'] if r['touches_same_ground_as_water']]
    if not intervals: raise HTTPException(422,'No valid references; manual review required')
    d=p.fuse(intervals); sample=dict(d,captured_at=now.isoformat())
    outside=p.haversine((lat,lon),(alert['center_lat'],alert['center_lon']))*1000>alert['radius_m']
    paths=[]
    # Parse before persistence so invalid photos never leave partial reports.
    with db.connection() as c:
        hashes=[r['ahash'] for r in c.execute('SELECT ahash FROM reports WHERE alert_id=?',(alert['id'],)) if r['ahash']]
        duplicate=any(sum(a!=b for a,b in zip(prepared[0][1],h))<=settings.TH['duplicate_hamming'] for h in hashes)
        nearest=None
        for row in c.execute("SELECT * FROM incidents WHERE alert_id=? AND family='flood' AND status!='resolved'",(alert['id'],)):
            distance=p.haversine((lat,lon),(row['lat'],row['lon']))*1000
            if distance<=settings.TH['cluster_m'] and (nearest is None or distance<nearest[0]): nearest=(distance,row)
        incident_id=nearest[1]['id'] if nearest else identity()
        flags=d['flags']+(['outside_geofence'] if outside else [])+(['location_accuracy_warning'] if accuracy>settings.TH['accuracy_warn_m'] else [])
        rate_class={'receding':'receding','steady':'steady','rising_slow':'slow','rising_moderate':'moderate','rising_rapid':'rapid'}.get(extraction['trend'],settings.RATES['default'][alert['hazard']])
        value=dict(id=incident_id,name='Citizen flood report',family='flood',scene_type='flood',series=[sample],rate_class=rate_class,
                   flow_class=extraction['flow_class'],debris=extraction['debris'],people_count=people_count or extraction['people']['count_visible'],
                   contexts=extraction['people']['contexts'],vulnerable=[v for v in vulnerable.split(',') if v],hazards=extraction['hazards'],flags=flags,
                   extraction_status=status,simulated=True,lat=lat,lon=lon,location_weight=1/accuracy)
        if nearest:
            old=json.loads(nearest[1]['data'])
            if not duplicate:
                value['series']=old['series']+[sample]
                value['people_count']=max(old['people_count'],value['people_count'])
                weight=old.get('location_weight',1/accuracy)
                value['lat']=(nearest[1]['lat']*weight+lat/accuracy)/(weight+1/accuracy)
                value['lon']=(nearest[1]['lon']*weight+lon/accuracy)/(weight+1/accuracy)
                value['location_weight']=weight+1/accuracy
                c.execute('UPDATE incidents SET lat=?,lon=?,data=? WHERE id=?',(value['lat'],value['lon'],dump(value),incident_id))
        else:
            c.execute('INSERT INTO incidents(id,alert_id,family,lat,lon,data) VALUES (?,?,?,?,?,?)',(incident_id,alert['id'],'flood',lat,lon,dump(value)))
        for image,_,_ in prepared:
            path=settings.UPLOADS/(identity()+'.jpg'); image.save(path,quality=settings.TH['jpeg_quality']); paths.append(str(path))
        report_id=identity()
        record=dict(id=report_id,captured_at=now.isoformat(),captured_at_source='submission',created_at=now.isoformat(),lat=lat,lon=lon,
            loc_source='pin' if pin else 'browser',loc_accuracy_m=accuracy,outside_geofence=outside,reporter_state=state,people_count=people_count,
            note_text=note,image_paths=paths,extraction=extraction,extraction_status=status)
        c.execute('INSERT INTO reports(id,alert_id,incident_id,ahash,duplicate,data) VALUES (?,?,?,?,?,?)',(report_id,alert['id'],incident_id,prepared[0][1],int(duplicate),dump(record)))
    return {'report_id':report_id,'message':'Help is being prioritised','extraction_status':status,'duplicate':duplicate,
            'outside_geofence':outside,'tips':settings.TEXT['flood_tips'],'simulation_notice':'MOCK extraction: photo contents have not been assessed.'}
