"""Operations HTTP routes"""
from app import db
from app import settings
from app.common import STATIC
from app.common import dump
from app.common import identity
from app.intelligence.fusion import utcnow
from app.operations.dispatch import plan
from app.operations.models import DispatchInput
from app.operations.models import FieldUpdate
from app.operations.models import TeamInput
from app.operations.seed import scenario
from app.operations.service import list_sites
from datetime import timedelta
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Annotated
import json
from fastapi import APIRouter

router = APIRouter()

@router.get('/authority')
@router.get('/office')
@router.get('/command')
@router.get('/responders')
@router.get('/field/{team_id}')
def console(team_id: str | None=None): return FileResponse(STATIC/'index.html')


@router.post('/api/seed')
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


@router.get('/api/incidents')
def incidents(eta_scale:Annotated[float,Query(ge=.5,le=3)]=1,alert_id:str|None=None):
    with db.connection() as c: return list_sites(c,eta_scale,alert_id)


@router.get('/api/incidents/{incident_id}')
def incident(incident_id:str,eta_scale:Annotated[float,Query(ge=.5,le=3)]=1):
    with db.connection() as c:
        site=next((s for s in list_sites(c,eta_scale) if s['id']==incident_id),None)
        if not site: raise HTTPException(404,'Site not found')
        return site


@router.get('/api/incidents/{incident_id}/reports')
def site_reports(incident_id:str):
    with db.connection() as c:
        if not c.execute('SELECT 1 FROM incidents WHERE id=?',(incident_id,)).fetchone():
            raise HTTPException(404,'Site not found')
        result=[]
        for row in c.execute('SELECT id,data FROM reports WHERE incident_id=?',(incident_id,)):
            value=json.loads(row['data'])
            result.append({'id':row['id'],'created_at':value['created_at'],'note':value.get('note_text',''),
                'kind':'photo_report','team_id':value.get('team_id'),'extraction_status':value['extraction_status'],
                'photos':[f"/api/reports/{row['id']}/photos/{i}" for i,_ in enumerate(value.get('image_paths',[]))]})
        for row in c.execute('SELECT id,data FROM field_updates WHERE incident_id=?',(incident_id,)):
            value=json.loads(row['data'])
            result.append({'id':row['id'],'created_at':value['created_at'],'note':value.get('note',''),
                'kind':'field_update','team_id':value['team_id'],'extraction_status':'field_observation',
                'status':value.get('status'),'depth_cm':value.get('depth_cm'),'rescued_count':value.get('count'),'photos':[]})
        return sorted(result,key=lambda x:x['created_at'],reverse=True)


@router.get('/api/reports/{report_id}/photos/{index}')
def report_photo(report_id:str,index:int):
    with db.connection() as c:
        row=c.execute('SELECT data FROM reports WHERE id=?',(report_id,)).fetchone()
        if not row: raise HTTPException(404,'Photo not found')
        photos=json.loads(row['data']).get('image_paths',[])
        if index<0 or index>=len(photos): raise HTTPException(404,'Photo not found')
        path=Path(photos[index]).resolve()
        if path.parent!=settings.UPLOADS.resolve() or not path.is_file():
            raise HTTPException(404,'Photo not found')
        return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})


@router.get('/api/teams')
def teams():
    with db.connection() as c: return [json.loads(r['data']) for r in c.execute('SELECT data FROM teams')]


@router.post('/api/teams')
def upsert_team(body:TeamInput):
    value=body.model_dump()
    with db.connection() as c: c.execute('INSERT OR REPLACE INTO teams(id,data) VALUES (?,?)',(body.id,dump(value)))
    return value


@router.post('/api/dispatch/run')
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


@router.post('/api/incidents/{incident_id}/field_update')
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
