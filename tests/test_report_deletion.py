import io
import json
from pathlib import Path
from PIL import Image, ImageDraw
from app import db
from app.intelligence.vision.client import Extraction
from app.intelligence.vision.mock_data import FLOOD
from tests.test_api import client, alert, picture

def submit(client,token,image=None):
    return client.post('/api/reports',data=dict(token=token,lat=11.0168,lon=76.9558,note='Test observation'),files={'images':('scene.jpg',image or picture(),'image/jpeg')}).json()

def test_delete_photo_report_cleans_counts_photos_and_empty_estimate(client):
    token=alert(client)['recipients'][0]['token']
    report=submit(client,token)
    listing=client.get('/api/office/reports').json()
    assert len(listing)==1 and listing[0]['id']==report['report_id']
    photo=listing[0]['photos'][0]
    with db.connection() as c:
        row=c.execute('SELECT data,incident_id FROM reports').fetchone()
        file=Path(json.loads(row['data'])['image_paths'][0]); site=row['incident_id']
    assert file.exists()
    assert client.delete('/api/reports/'+report['report_id']).status_code==200
    assert not file.exists()
    assert client.get(photo).status_code==404
    assert client.get('/api/office/reports').json()==[]
    assert client.get('/api/incidents').json()==[]
    assert client.get('/api/office').json()['campaigns'][0]['reports']==0
    assert client.get('/api/incidents/'+site+'/reports').json()==[]
    assert client.delete('/api/reports/'+report['report_id']).status_code==404

def test_delete_requires_admin_and_origin_header(client):
    report=submit(client,alert(client)['recipients'][0]['token'])
    endpoint='/api/reports/'+report['report_id']
    assert client.delete(endpoint,headers={'Origin':'https://evil.example'}).status_code==403
    client.post('/api/auth/logout')
    assert client.delete(endpoint).status_code==401
    assert client.get('/api/office/reports').status_code==401

def test_manual_review_reports_can_be_deleted(client,monkeypatch):
    async def manual(*args): return Extraction({},'failed',flags=['provider_timeout'])
    monkeypatch.setattr('app.citizen.routes.extract',manual)
    report=submit(client,alert(client)['recipients'][0]['token'])
    assert report['extraction_status']=='failed'
    assert client.get('/api/office/reports').json()[0]['incident_id'] is None
    assert client.delete('/api/reports/'+report['report_id']).status_code==200
    assert client.get('/api/office/reports').json()==[]

def test_deletion_recomputes_remaining_depth_and_preserves_other_report(client,monkeypatch):
    depths=iter([.2,1.0])
    async def estimate(*args):
        depth=next(depths)
        return Extraction(FLOOD,'mock',dict(lo=depth,hi=depth,mid=depth,flags=[]))
    monkeypatch.setattr('app.citizen.routes.extract',estimate)
    token=alert(client)['recipients'][0]['token']
    first=submit(client,token)
    image=Image.new('RGB',(32,32),'white'); ImageDraw.Draw(image).rectangle((0,0,15,31),fill='black')
    output=io.BytesIO(); image.save(output,format='JPEG')
    second=submit(client,token,output.getvalue())
    assert not second['duplicate']
    assert client.delete('/api/reports/'+second['report_id']).status_code==200
    with db.connection() as c:
        value=json.loads(c.execute('SELECT data FROM incidents').fetchone()['data'])
        assert len(value['series'])==1 and value['series'][0]['mid']==.2
    assert client.get('/api/office/reports').json()[0]['id']==first['report_id']
    assert client.get('/api/incidents').status_code==200

def test_delete_duplicate_does_not_remove_original_estimate(client):
    token=alert(client)['recipients'][0]['token']
    first=submit(client,token); second=submit(client,token)
    assert second['duplicate']
    client.delete('/api/reports/'+second['report_id'])
    assert len(client.get('/api/incidents').json())==1
    assert client.get('/api/office/reports').json()[0]['id']==first['report_id']

def test_delete_never_unlinks_paths_outside_uploads(client,tmp_path):
    report=submit(client,alert(client)['recipients'][0]['token'])
    outside=tmp_path/'keep.txt';outside.write_text('keep')
    with db.connection() as c:
        record=json.loads(c.execute('SELECT data FROM reports').fetchone()['data'])
        record['image_paths']=[str(outside)]
        c.execute('UPDATE reports SET data=?',(json.dumps(record),))
    client.delete('/api/reports/'+report['report_id'])
    assert outside.read_text()=='keep'

def test_deleting_last_photo_preserves_field_updates_and_releases_assignment(client):
    report=submit(client,alert(client)['recipients'][0]['token'])
    with db.connection() as c:
        site=c.execute('SELECT incident_id FROM reports').fetchone()['incident_id']
        c.execute('INSERT INTO teams VALUES (?,?)',('test-team','{}'))
        c.execute('INSERT INTO assignments VALUES (?,?,?)',('test-team',site,json.dumps({'team_id':'test-team','eta_min':1})))
    assert client.post('/api/incidents/'+site+'/field_update',json={'team_id':'test-team','status':'on_scene','depth_cm':45,'note':'Independent field observation'}).status_code==200
    client.delete('/api/reports/'+report['report_id'])
    with db.connection() as c:
        assert c.execute('SELECT count(*) FROM field_updates').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM assignments').fetchone()[0]==0
    history=client.get('/api/incidents/'+site+'/reports').json()
    assert len(history)==1 and history[0]['note']=='Independent field observation'
