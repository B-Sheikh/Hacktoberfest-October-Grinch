"""Office HTTP routes"""
from app import db
from app import settings
from app.citizen.service import public_link
from app.common import STATIC
from app.common import dump
from app.common import identity
from app.common import require_alert
from app.intelligence.fusion import utcnow
from app.office import auth
from app.office.models import AlertInput
from app.office.models import AreaInput
from app.office.models import ResidentInput
from app.office.service import area_residents
from app.office.service import sms_message
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from typing import Annotated
import json
import os
import secrets
import time
from fastapi import APIRouter

router = APIRouter()

@router.get('/admin/login')
def login_page(request:Request):
    if auth.session(request): return RedirectResponse('/office',status_code=303)
    return FileResponse(STATIC/'login.html',headers={'Cache-Control':'no-store'})


@router.post('/api/auth/login')
def login(request:Request,username:Annotated[str,Form(max_length=100)],password:Annotated[str,Form(max_length=512)]):
    if not auth.same_origin(request): raise HTTPException(403,'Invalid request origin')
    configured_user=os.getenv('ADMIN_USERNAME',''); configured_hash=os.getenv('ADMIN_PASSWORD_HASH','')
    if not configured_user or not configured_hash: raise HTTPException(503,'Admin login is not configured. Run the admin setup command on the server.')
    client=request.client.host if request.client else 'unknown'; now=time.time()
    with db.connection() as c:
        attempt=c.execute('SELECT * FROM login_attempts WHERE client=?',(client,)).fetchone()
        if attempt and now-attempt['started']<900 and attempt['failures']>=10:
            raise HTTPException(429,'Too many failed logins. Try again in 15 minutes.')
        # Evaluate the password for wrong usernames too, avoiding a username timing shortcut.
        valid=auth.verify_password(password,configured_hash) and secrets.compare_digest(username.encode(),configured_user.encode())
        if not valid:
            if not attempt or now-attempt['started']>=900:
                c.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,1,?)',(client,now))
            else: c.execute('UPDATE login_attempts SET failures=failures+1 WHERE client=?',(client,))
        else:
            c.execute('DELETE FROM login_attempts WHERE client=?',(client,))
            c.execute('DELETE FROM admin_sessions WHERE expires<=?',(now,))
            token=secrets.token_urlsafe(32)
            c.execute('INSERT INTO admin_sessions VALUES (?,?,?,?)',(auth.fingerprint(token),username,now+auth.SESSION_SECONDS,auth.credential_version()))
    if not valid: raise HTTPException(401,'Incorrect username or password')
    response=JSONResponse({'status':'signed_in','redirect':'/office'})
    secure=os.getenv('ADMIN_COOKIE_SECURE','false').lower()=='true' or request.url.scheme=='https'
    response.set_cookie(auth.COOKIE,token,max_age=auth.SESSION_SECONDS,httponly=True,secure=secure,samesite='strict')
    return response


@router.get('/api/auth/me')
def admin_identity(request:Request): return {'username':request.state.admin['username']}


@router.post('/api/auth/logout')
def logout(request:Request):
    with db.connection() as c: c.execute('DELETE FROM admin_sessions WHERE token_hash=?',(auth.fingerprint(request.cookies[auth.COOKIE]),))
    response=JSONResponse({'status':'signed_out'}); response.delete_cookie(auth.COOKIE); return response


@router.get('/api/office')
def office_summary():
    with db.connection() as c:
        campaigns=[]
        for row in c.execute('SELECT id,data FROM alerts ORDER BY rowid DESC').fetchall():
            item=json.loads(row['data'])
            counts=dict((r['status'],r['n']) for r in c.execute('SELECT status,count(*) n FROM recipients WHERE alert_id=? GROUP BY status',(row['id'],)))
            campaigns.append(dict(item,recipients=sum(counts.values()),pending=counts.get('pending',0),simulated=counts.get('simulated',0),reports=c.execute('SELECT count(*) FROM reports WHERE alert_id=?',(row['id'],)).fetchone()[0],report_url=public_link(c,row['id'])))
        residents=[dict(r) for r in c.execute('SELECT * FROM residents ORDER BY name')]
        return {'residents':residents,'campaigns':campaigns,'sms_mode':'simulated'}


@router.post('/api/residents')
def register_resident(body:ResidentInput):
    with db.connection() as c:
        c.execute('INSERT INTO residents(phone,name,lat,lon,consent) VALUES (?,?,?,?,?) ON CONFLICT(phone) DO UPDATE SET name=excluded.name,lat=excluded.lat,lon=excluded.lon,consent=excluded.consent',(body.phone,body.name,body.lat,body.lon,int(body.consent)))
    return {'status':'saved'}


@router.post('/api/residents/demo')
def demo_residents():
    with db.connection() as c:
        for index,(lat,lon) in enumerate([(11.0168,76.9558),(11.019,76.96),(11.012,76.951),(11.12,77.04)]):
            c.execute('INSERT OR IGNORE INTO residents VALUES (?,?,?,?,1)',(f'demo-resident-{index+1}',f'Demo resident {index+1}',lat,lon))
    return {'status':'saved','synthetic':True}


@router.post('/api/office/preview')
def preview_recipients(body:AreaInput):
    with db.connection() as c:
        residents=area_residents(c,body.center_lat,body.center_lon,body.radius_m)
        return {'count':len(residents),'residents':residents,'sms_mode':'simulated'}


@router.get('/api/office/recipients')
def office_recipients():
    with db.connection() as c:
        return [dict(row, message=row['message'] or sms_message(require_alert(c,row['alert_id']),row['token'])) for row in c.execute('SELECT * FROM recipients ORDER BY rowid DESC').fetchall()]


@router.get('/api/alerts')
def alerts():
    with db.connection() as c: return [json.loads(r['data']) for r in c.execute('SELECT data FROM alerts')]


@router.post('/api/alerts',status_code=201)
def create_alert(body:AlertInput):
    if body.event_time>utcnow(): raise HTTPException(422,'Event time cannot be in the future')
    value=body.model_dump(mode='json'); value.pop('phones'); value['id']=identity()
    tokens=[]
    with db.connection() as c:
        c.execute('INSERT INTO alerts(id,data) VALUES (?,?)',(value['id'],dump(value)))
        phones=[r['phone'] for r in area_residents(c,body.center_lat,body.center_lon,body.radius_m)] if body.recipient_source=='locality' else body.phones
        for phone in dict.fromkeys(phones):
            token=secrets.token_urlsafe(32)
            c.execute('INSERT INTO recipients(token,alert_id,phone) VALUES (?,?,?)',(token,value['id'],phone))
            tokens.append({'token':token,'link':f'{settings.PUBLIC_BASE_URL}/report/{token}'})
        shared=public_link(c,value['id'])
    return dict(value,recipients=tokens,report_url=shared)


@router.post('/api/alerts/{alert_id}/send')
def send(alert_id:str):
    with db.connection() as c:
        alert=require_alert(c,alert_id)
        changed=0
        for row in c.execute("SELECT * FROM recipients WHERE alert_id=? AND status='pending'",(alert_id,)).fetchall():
            registered=c.execute('SELECT consent FROM residents WHERE phone=?',(row['phone'],)).fetchone()
            if registered and not registered['consent']:
                c.execute("UPDATE recipients SET status='excluded' WHERE token=?",(row['token'],)); continue
            message=sms_message(alert,row['token'])
            c.execute("UPDATE recipients SET status='simulated',message=? WHERE token=?",(message,row['token']))
            changed+=1
    return {'status':'simulated','alert_id':alert_id,'count':changed,'real_sms_implemented':False}


@router.get('/api/outbox')
def outbox():
    with db.connection() as c: return [dict(r) for r in c.execute("SELECT * FROM recipients WHERE status='simulated'")]
