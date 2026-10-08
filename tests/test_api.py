import io
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app import settings

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(settings,'UPLOADS',tmp_path/'uploads')
    with TestClient(app) as c: yield c

def alert(client):
    r=client.post('/api/alerts',json=dict(hazard='flash_flood',center_lat=11.0168,center_lon=76.9558,radius_m=3000,event_time=(datetime.now(timezone.utc)-timedelta(minutes=40)).isoformat(),phones=['demo']))
    assert r.status_code==201
    return r.json()

def picture():
    b=io.BytesIO(); Image.new('RGB',(32,32),'blue').save(b,format='JPEG');return b.getvalue()

def test_seed_rank_projection_and_dispatch(client):
    assert client.get('/api/health').json()['provider']=='mock'
    assert client.post('/api/seed').json()['incidents']==11
    assert client.post('/api/seed').json()['incidents']==11
    a=client.get('/api/incidents').json();b=client.get('/api/incidents?eta_scale=2').json()
    assert len(a)==11
    assert [s['priority_index'] for s in a]==sorted([s['priority_index'] for s in a],reverse=True)
    assert all(s['tier'] in ['P1','P2','P3','P4'] for s in a)
    assert any(s['priority_index']!=next(x['priority_index'] for x in b if x['id']==s['id']) for s in a)
    assert 'inconsistent' in next(s for s in a if s['id']=='demo-5')['flags']
    assert 'HOLD: hazard control first' in next(s for s in a if s['id']=='demo-10')['flags']
    assigned=client.post('/api/dispatch/run',json={'eta_scale':1}).json()
    teams=[s['team_id'] for s in assigned if s['team_id']]
    assert len(teams)==len(set(teams))
    assert client.get('/api/benchmark').json()['sample_count']==0

def test_report_and_duplicate(client):
    a=alert(client);token=a['recipients'][0]['token']
    assert client.get('/r/'+token).status_code==200
    fields=dict(token=token,lat=11.0168,lon=76.9558,accuracy=10,state='need_help',people_count=2)
    r=client.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')})
    assert r.status_code==201,r.text
    assert r.json()['extraction_status']=='mock'
    assert r.json()['duplicate'] is False
    r=client.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')})
    assert r.json()['duplicate'] is True
    sites=client.get('/api/incidents').json()
    assert len(sites)==1 and sites[0]['n_reports']==1

def test_invalid_token_image_and_geofence(client):
    a=alert(client);fields=dict(token='bad',lat=11,lon=77)
    assert client.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')}).status_code==403
    fields['token']=a['recipients'][0]['token']
    assert client.post('/api/reports',data=fields,files={'images':('bad.jpg',b'not an image','image/jpeg')}).status_code==422
    r=client.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')})
    assert r.status_code==201 and r.json()['outside_geofence'] is True

def test_simulated_outbox_and_field(client):
    a=alert(client)
    assert client.post('/api/alerts/'+a['id']+'/send').json()['status']=='simulated'
    assert len(client.get('/api/outbox').json())==1
    client.post('/api/seed')
    rows=client.post('/api/dispatch/run',json={}).json()
    assigned=next(x for x in rows if x['team_id'])
    r=client.post('/api/incidents/'+assigned['incident_id']+'/field_update',json={'team_id':assigned['team_id'],'status':'on_scene','depth_cm':30})
    assert r.status_code==200
    assert client.post('/api/incidents/'+assigned['incident_id']+'/field_update',json={'team_id':'unknown','status':'resolved'}).status_code==409

def test_pages(client):
    for url in ['/command','/authority','/field/demo-team-1','/static/app.js','/static/report.js','/static/style.css']:
        assert client.get(url).status_code==200
