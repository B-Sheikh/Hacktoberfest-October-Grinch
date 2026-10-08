import time
from tests.test_api import client, alert, picture
from tests.conftest import TEST_PASSWORD, login_admin
from app import db
from app.office import auth

def sign_out(client):
    assert client.post('/api/auth/logout').status_code==200

def test_office_and_sensitive_apis_require_session(client):
    sign_out(client)
    for path in ['/office','/authority','/command','/responders','/field/demo-team-1','/static/index.html','/docs']:
        response=client.get(path,follow_redirects=False)
        assert response.status_code==303 and response.headers['location']=='/admin/login'
    for path in ['/api/office','/api/office/recipients','/api/alerts','/api/incidents','/api/teams','/api/outbox','/api/reports/anything/photos/0']:
        assert client.get(path).status_code==401
    assert client.post('/api/residents/demo').status_code==401
    assert client.post('/api/seed').status_code==401

def test_login_cookie_and_logout_revocation(client):
    token=client.cookies.get(auth.COOKIE)
    with db.connection() as c:
        row=c.execute('SELECT * FROM admin_sessions').fetchone()
        assert row['token_hash']==auth.fingerprint(token) and row['token_hash']!=token
    assert client.get('/api/auth/me').json()['username']=='test-admin'
    assert client.get('/office').headers['cache-control']=='no-store'
    sign_out(client)
    client.cookies.set(auth.COOKIE,token)
    assert client.get('/api/office').status_code==401

def test_wrong_password_and_login_throttle(client):
    sign_out(client)
    for _ in range(10):
        response=client.post('/api/auth/login',data={'username':'test-admin','password':'wrong'})
        assert response.status_code==401 and 'password' not in response.json()
    assert client.post('/api/auth/login',data={'username':'test-admin','password':TEST_PASSWORD}).status_code==429

def test_expired_session_and_password_rotation(client,monkeypatch):
    with db.connection() as c: c.execute('UPDATE admin_sessions SET expires=?',(time.time()-1,))
    assert client.get('/api/office').status_code==401
    login_admin(client)
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',auth.hash_password('another-test-password'))
    assert client.get('/api/office').status_code==401

def test_admin_mutations_reject_cross_origin_and_missing_header(client):
    assert client.post('/api/seed',headers={'Origin':'https://another-site.example'}).status_code==403
    del client.headers['X-Waterline-Request']
    assert client.post('/api/residents/demo').status_code==403
    assert client.post('/api/auth/login',data={'username':'test-admin','password':TEST_PASSWORD},headers={'Origin':'https://another-site.example'}).status_code==403

def test_sms_form_standalone_without_admin_login(client):
    campaign=alert(client)
    token=campaign['recipients'][0]['token']
    client.post('/api/alerts/'+campaign['id']+'/send')
    message=client.get('/api/outbox').json()[0]['message']
    assert '/report/'+token in message
    sign_out(client)
    page=client.get('/report/'+token)
    assert page.status_code==200
    assert 'href="/office"' not in page.text and 'href="/command"' not in page.text
    assert 'href="/office"' not in client.get('/report').text
    assert client.get('/api/report-link/'+token).status_code==200
    response=client.post('/api/reports',data=dict(token=token,lat=11.0168,lon=76.9558),files={'images':('scene.jpg',picture(),'image/jpeg')})
    assert response.status_code==201
    assert client.post('/api/reports',data=dict(team_id='demo-team',incident_id='demo-site',lat=11,lon=77),files={'images':('scene.jpg',picture(),'image/jpeg')}).status_code==401

def test_secure_cookie_and_unconfigured_admin(client,monkeypatch):
    sign_out(client)
    monkeypatch.setenv('ADMIN_COOKIE_SECURE','true')
    response=client.post('/api/auth/login',data={'username':'test-admin','password':TEST_PASSWORD})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie and 'secure' in cookie
    monkeypatch.delenv('ADMIN_PASSWORD_HASH')
    assert client.post('/api/auth/login',data={'username':'test-admin','password':TEST_PASSWORD}).status_code==503
