"""Citizen HTTP routes"""
from PIL import Image
from PIL import ImageOps
from PIL import UnidentifiedImageError
from app import db
from app import settings
from app.citizen.service import public_link
from app.citizen.service import token_alert
from app.common import STATIC
from app.common import dump
from app.common import identity
from app.common import require_alert
from app.intelligence import physics as p
from app.intelligence.fusion import utcnow
from app.intelligence.vision.client import extract
from app.office import auth
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from typing import Annotated
import io
import json
from fastapi import APIRouter

router = APIRouter()

@router.get('/')
def home(): return RedirectResponse('/report')


@router.get('/report')
def public_portal(): return FileResponse(STATIC/'portal.html')


@router.get('/api/public/alerts')
def public_alerts():
    with db.connection() as c:
        output=[]
        for row in c.execute('SELECT id,data,demo FROM alerts ORDER BY rowid DESC').fetchall():
            value=json.loads(row['data'])
            output.append({key:value[key] for key in ['id','hazard','center_lat','center_lon','radius_m','event_time']} | {'report_url':public_link(c,row['id']),'simulated':bool(row['demo'])})
        return output


@router.get('/report/{token}')
@router.get('/r/{token}')
def resident(token: str):
    with db.connection() as c:
        if not token_alert(c,token): raise HTTPException(404,'Invalid reporting link')
    return FileResponse(STATIC/'report.html')


@router.get('/api/report-link/{token}')
def report_context(token:str):
    with db.connection() as c:
        row=token_alert(c,token)
        if not row: raise HTTPException(404,'Invalid reporting link')
        return require_alert(c,row['alert_id'])


@router.post('/api/reports',status_code=201)
@router.post('/api/field/reports',status_code=201)
async def report(request:Request,images:Annotated[list[UploadFile],File()],
                 lat:Annotated[float,Form(ge=-90,le=90)],lon:Annotated[float,Form(ge=-180,le=180)],
                 token:Annotated[str,Form()]='',team_id:Annotated[str,Form()]='',incident_id:Annotated[str,Form()]='',
                 accuracy:Annotated[float,Form(gt=0)]=100,pin:Annotated[bool,Form()]=False,
                 state:Annotated[str,Form()]='safe',people_count:Annotated[int,Form(ge=0,le=10000)]=0,
                 note:Annotated[str,Form(max_length=2000)]='',vulnerable:Annotated[str,Form()]=''):
    if state not in ['need_help','safe','third_party']: raise HTTPException(422,'Unknown reporter state')
    if team_id and not auth.session(request): raise HTTPException(401,'Admin login required for team reporting')
    if team_id and (request.headers.get('x-waterline-request')!='1' or not auth.same_origin(request)):
        raise HTTPException(403,'Invalid request origin')
    if request.url.path=='/api/field/reports' and not team_id:
        raise HTTPException(422,'Choose your assigned team before reporting')
    if not 1<=len(images)<=settings.TH['max_images']: raise HTTPException(422,'Supply one to four photos')
    target=None
    with db.connection() as c:
        if team_id:
            if not c.execute('SELECT 1 FROM assignments WHERE incident_id=? AND team_id=?',(incident_id,team_id)).fetchone():
                raise HTTPException(409,'Team is not assigned to this site')
            target=c.execute('SELECT * FROM incidents WHERE id=?',(incident_id,)).fetchone()
            alert=require_alert(c,target['alert_id'])
        else:
            row=token_alert(c,token)
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
    image_bytes=[]
    for image,_,_ in prepared:
        output=io.BytesIO();image.save(output,format='JPEG',quality=settings.TH['jpeg_quality'])
        image_bytes.append(output.getvalue())
    now=utcnow(); result=await extract(prepared[0][2],image_bytes)
    extraction,status=result.data,result.status
    if result.depth is None or (target and target['family']!='flood'):
        if target and target['family']!='flood':
            status='manual_review'
        report_id=identity();paths=[]
        for image,_,_ in prepared:
            path=settings.UPLOADS/(identity()+'.jpg');image.save(path,quality=settings.TH['jpeg_quality']);paths.append(str(path))
        record=dict(id=report_id,created_at=now.isoformat(),captured_at=now.isoformat(),captured_at_source='submission',
                    lat=lat,lon=lon,loc_accuracy_m=accuracy,loc_source='pin' if pin else 'browser',
                    reporter_state=state,people_count=people_count,note_text=note,image_paths=paths,
                    extraction=extraction,extraction_status=status,flags=result.flags,team_id=team_id or None)
        with db.connection() as c:
            if target and not c.execute('SELECT 1 FROM assignments WHERE incident_id=? AND team_id=?',(target['id'],team_id)).fetchone():
                raise HTTPException(409,'Assignment changed. Refresh your team workspace.')
            c.execute('INSERT INTO reports(id,alert_id,incident_id,ahash,duplicate,data) VALUES (?,?,?,?,0,?)',
                      (report_id,alert['id'],target['id'] if target else None,prepared[0][1],dump(record)))
        return {'report_id':report_id,'message':'Report saved. AI analysis is unavailable; the office must review the photos.' if status=='failed' else 'Report received for manual review; no automated priority assigned.',
                'extraction_status':status,'flags':result.flags,'tips':settings.TEXT['safety'],
                'simulation_notice':'Photos were attached to the assigned site for review.' if target else 'No automated depth or mock measurement was assigned.'}
    d=result.depth; sample=dict(d,captured_at=now.isoformat())
    outside=p.haversine((lat,lon),(alert['center_lat'],alert['center_lon']))*1000>alert['radius_m']
    paths=[]
    # Parse before persistence so invalid photos never leave partial reports.
    with db.connection() as c:
        if target and not c.execute('SELECT 1 FROM assignments WHERE incident_id=? AND team_id=?',(target['id'],team_id)).fetchone():
            raise HTTPException(409,'Assignment changed. Refresh your team workspace.')
        # A previously simulated or failed attempt must not block a real re-analysis.
        compatible_statuses={'mock'} if status=='mock' else {'ok','retry_ok'}
        hashes=[r['ahash'] for r in c.execute('SELECT ahash,data FROM reports WHERE alert_id=?',(alert['id'],))
                if r['ahash'] and json.loads(r['data']).get('extraction_status') in compatible_statuses]
        duplicate=any(sum(a!=b for a,b in zip(prepared[0][1],h))<=settings.TH['duplicate_hamming'] for h in hashes)
        nearest=(0,target) if target else None
        for row in ([] if target else c.execute("SELECT * FROM incidents WHERE alert_id=? AND family='flood' AND status!='resolved'",(alert['id'],))):
            distance=p.haversine((lat,lon),(row['lat'],row['lon']))*1000
            if distance<=settings.TH['cluster_m'] and (nearest is None or distance<nearest[0]): nearest=(distance,row)
        incident_id=nearest[1]['id'] if nearest else identity()
        flags=sorted(set(d['flags']+result.flags))+(['outside_geofence'] if outside else [])+(['location_accuracy_warning'] if accuracy>settings.TH['accuracy_warn_m'] else [])
        rate_class={'receding':'receding','steady':'steady','rising_slow':'slow','rising_moderate':'moderate','rising_rapid':'rapid'}.get(extraction['trend'],settings.RATES['default'][alert['hazard']])
        value=dict(id=incident_id,name=json.loads(target['data'])['name'] if target else 'Citizen flood report',family='flood',scene_type='flood',series=[sample],rate_class=rate_class,
                   flow_class=extraction['flow_class'],debris=extraction['debris'],people_count=people_count or extraction['people']['count_visible'],
                   contexts=extraction['people']['contexts'],vulnerable=[v for v in vulnerable.split(',') if v],hazards=extraction['hazards'],flags=flags,
                   extraction_status=status,simulated=status in ['mock','failed'],lat=lat,lon=lon,location_weight=1/accuracy)
        if nearest:
            old=json.loads(nearest[1]['data'])
            if not duplicate:
                # Keep simulated and live observations out of the same rate fit.
                value['series']=(old['series'] if old.get('simulated')==value['simulated'] else [])+[sample]
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
        record['team_id']=team_id or None
        c.execute('INSERT INTO reports(id,alert_id,incident_id,ahash,duplicate,data) VALUES (?,?,?,?,?,?)',(report_id,alert['id'],incident_id,prepared[0][1],int(duplicate),dump(record)))
    notice='Live Gemma extraction; verify estimates before acting.' if status in ['ok','retry_ok'] else 'MOCK extraction: photo contents have not been assessed.'
    if status=='failed': notice='AI extraction failed, manual review. '+notice
    return {'report_id':report_id,'message':'Help is being prioritised','extraction_status':status,'duplicate':duplicate,
            'outside_geofence':outside,'tips':settings.TEXT['flood_tips'],'simulation_notice':notice,'flags':result.flags}
