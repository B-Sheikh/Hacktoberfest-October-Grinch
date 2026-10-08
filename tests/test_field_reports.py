from tests.test_api import client, picture
from app.intelligence.vision.client import Extraction

def assignment(client,family='flood'):
    client.post('/api/seed')
    sites={s['id']:s for s in client.get('/api/incidents').json()}
    rows=client.post('/api/dispatch/run',json={}).json()
    return next(r for r in rows if r['team_id'] and sites[r['incident_id']]['family']==family),sites

def submit(client,row,**fields):
    data=dict(team_id=row['team_id'],incident_id=row['incident_id'],lat=11.02,lon=76.96,note='Access is blocked. Bring additional ropes.')
    data.update(fields)
    return client.post('/api/field/reports',data=data,files={'images':('flood.jpg',picture(),'image/jpeg')})

def test_field_photos_saved_with_site_and_team(client):
    row,sites=assignment(client)
    result=submit(client,row)
    assert result.status_code==201,result.text
    assert result.json()['extraction_status']=='mock'
    reports=client.get('/api/incidents/'+row['incident_id']+'/reports').json()
    assert len(reports)==1 and reports[0]['team_id']==row['team_id']
    assert reports[0]['note'].startswith('Access is blocked')
    photo=client.get(reports[0]['photos'][0])
    assert photo.status_code==200 and photo.headers['content-type']=='image/jpeg'
    assert photo.headers['cache-control']=='private, no-store'
    assert client.get('/api/reports/'+reports[0]['id']+'/photos/99').status_code==404
    assert client.get('/api/incidents/'+row['incident_id']).json()['name']==sites[row['incident_id']]['name']

def test_field_rejects_unassigned_team(client):
    row,_=assignment(client)
    assert submit(client,row,team_id='unassigned').status_code==409
    assert submit(client,row,team_id='').status_code==422
    assert client.get('/api/incidents/'+row['incident_id']+'/reports').json()==[]

def test_collapse_evidence_does_not_change_family(client):
    row,_=assignment(client,'collapse')
    result=submit(client,row)
    assert result.status_code==201
    assert client.get('/api/incidents/'+row['incident_id']).json()['family']=='collapse'
    assert len(client.get('/api/incidents/'+row['incident_id']+'/reports').json())==1

def test_unmeasurable_field_photo_keeps_assignment_context(client,monkeypatch):
    row,_=assignment(client)
    async def extraction(*args): return Extraction({'scene_type':'out_of_scope'},'manual_review')
    monkeypatch.setattr('app.citizen.routes.extract',extraction)
    result=submit(client,row)
    assert result.status_code==201 and result.json()['extraction_status']=='manual_review'
    assert len(client.get('/api/incidents/'+row['incident_id']+'/reports').json())==1

def test_new_pages_and_upload_script(client):
    assert client.get('/responders').status_code==200
    assert client.get('/static/upload.js').status_code==200

def test_status_only_report_appears_in_history(client):
    row,_=assignment(client)
    response=client.post('/api/incidents/'+row['incident_id']+'/field_update',json={
        'team_id':row['team_id'],'status':'on_scene','depth_cm':45,'count':2,'note':'Measured from doorway.'})
    assert response.status_code==200
    history=client.get('/api/incidents/'+row['incident_id']+'/reports').json()
    assert history[0]['kind']=='field_update'
    assert history[0]['depth_cm']==45 and history[0]['rescued_count']==2
    assert history[0]['note']=='Measured from doorway.'
