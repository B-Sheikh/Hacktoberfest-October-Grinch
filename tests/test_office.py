from datetime import datetime, timezone, timedelta
from tests.test_api import client, picture


def resident(client, phone='demo-inside', lat=11.0168, lon=76.9558, consent=True):
    return client.post('/api/residents', json=dict(name='Test resident',phone=phone,lat=lat,lon=lon,consent=consent))


def campaign(client):
    response=client.post('/api/alerts',json=dict(hazard='flash_flood',center_lat=11.0168,center_lon=76.9558,radius_m=3000,event_time=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),recipient_source='locality',message='Report local conditions.'))
    assert response.status_code==201,response.text
    return response.json()


def test_locality_matches_only_registered_consented_residents(client):
    assert resident(client).status_code==200
    resident(client,'demo-outside',lat=12)
    resident(client,'demo-opted-out',consent=False)
    preview=client.post('/api/office/preview',json=dict(center_lat=11.0168,center_lon=76.9558,radius_m=3000)).json()
    assert preview['count']==1
    alert=campaign(client)
    assert len(alert['recipients'])==1
    summary=client.get('/api/office').json()
    assert len(summary['residents'])==3
    assert summary['campaigns'][0]['pending']==1
    assert summary['campaigns'][0]['simulated']==0
    assert client.get('/api/outbox').json()==[]
    row=client.get('/api/office/recipients').json()[0]
    assert row['phone']=='demo-inside'
    assert 'Report local conditions.' in row['message'] and '/report/' in row['message']


def test_simulated_send_is_repeat_safe(client):
    resident(client)
    alert=campaign(client)
    endpoint=f"/api/alerts/{alert['id']}/send"
    assert client.post(endpoint).json()['count']==1
    assert client.post(endpoint).json()['count']==0
    assert len(client.get('/api/outbox').json())==1
    assert client.get('/api/office').json()['campaigns'][0]['simulated']==1


def test_withdrawn_consent_excludes_drafted_recipient(client):
    resident(client)
    alert=campaign(client)
    resident(client,consent=False)
    assert client.post(f"/api/alerts/{alert['id']}/send").json()['count']==0
    assert client.get('/api/outbox').json()==[]
    assert client.get('/api/office/recipients').json()[0]['status']=='excluded'


def test_civilian_can_report_without_personal_sms(client):
    alert=campaign(client)
    assert alert['recipients']==[]
    public=client.get('/api/public/alerts').json()
    assert len(public)==1
    assert not {'phone','recipients','name','message'} & public[0].keys()
    link=public[0]['report_url']
    assert link==client.get('/api/public/alerts').json()[0]['report_url']
    assert client.get(link).status_code==200
    token=link.split('/')[-1]
    assert client.get('/api/report-link/'+token).json()['id']==alert['id']
    response=client.post('/api/reports',data=dict(token=token,lat=11.0168,lon=76.9558,state='need_help',people_count=2),files={'images':('scene.jpg',picture(),'image/jpeg')})
    assert response.status_code==201,response.text
    assert client.get('/api/office').json()['campaigns'][0]['reports']==1
    assert len(client.get('/api/incidents').json())==1


def test_registration_updates_and_validates(client):
    assert resident(client,phone='not-a-phone').status_code==422
    assert resident(client,lat=91).status_code==422
    resident(client)
    resident(client,lat=12,consent=False)
    rows=client.get('/api/office').json()['residents']
    assert len(rows)==1 and rows[0]['lat']==12 and rows[0]['consent']==0
    assert client.post('/api/office/preview',json=dict(center_lat=11,center_lon=77,radius_m=0)).status_code==422


def test_demo_registration_idempotent_and_public_pages(client):
    client.post('/api/residents/demo')
    client.post('/api/residents/demo')
    assert len(client.get('/api/office').json()['residents'])==4
    for url in ['/report','/office','/authority','/static/portal.js']:
        assert client.get(url).status_code==200
    assert client.get('/',follow_redirects=False).headers['location']=='/report'
