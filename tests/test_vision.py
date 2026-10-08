import asyncio
import json
from types import SimpleNamespace
import pytest
from google.genai import errors
from app.intelligence.vision import client as vision
from app.intelligence.vision.mock_data import FLOOD
from app import settings
from fastapi.testclient import TestClient
from tests.test_api import picture, alert
from tests.conftest import login_admin

@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv('VISION_PROVIDER','gemini')
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    monkeypatch.setenv('VISION_MODEL','gemma-4-31b-it')
    monkeypatch.setitem(vision.OPTIONS,'backoff_seconds',[0,0,0])
    class FakeClient:
        def __init__(self,*args,**kwargs): self.aio=self
        async def aclose(self): pass
        def close(self): pass
    monkeypatch.setattr(vision.genai,'Client',FakeClient)

def test_fenced_json_and_strict_enums():
    assert vision.parse_response('```json\n'+json.dumps(FLOOD)+'\n```')['scene_type']=='flood'
    bad=dict(FLOOD,flow_class='tsunami')
    with pytest.raises(ValueError): vision.parse_response(json.dumps(bad))
    with pytest.raises(ValueError): vision.parse_response('not json')
    with pytest.raises(ValueError): vision.parse_response(json.dumps(dict(FLOOD,depth_cm=40)))

def test_live_three_run_disagreement(live,monkeypatch):
    calls=[]
    async def generate(*args):
        bins=['q2','q4','q3']
        data=json.loads(json.dumps(FLOOD));data['references'][0]['waterline_bin']=bins[len(calls)]
        calls.append(args);return json.dumps(data)
    monkeypatch.setattr(vision,'_generate',generate)
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert len(calls)==3 and result.status=='ok'
    assert result.depth['lo']==pytest.approx(.07)
    assert result.depth['hi']==pytest.approx(.36)
    assert 'model_disagreement' in result.flags

def test_validation_retry(live,monkeypatch):
    calls=[]
    async def generate(*args):
        calls.append(args)
        return 'invalid' if len(calls)==1 else json.dumps(FLOOD)
    monkeypatch.setattr(vision,'_generate',generate)
    assert asyncio.run(vision.extract('flood.jpg',[b'image'])).status=='retry_ok'

@pytest.mark.parametrize('scene',['out_of_scope','collapse','damaged_standing'])
def test_non_flood_never_fabricates_depth(live,monkeypatch,scene):
    async def generate(*args): return json.dumps({'scene_type':scene})
    monkeypatch.setattr(vision,'_generate',generate)
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert result.depth is None and result.status=='manual_review'

def test_no_reference_requires_manual_review(live,monkeypatch):
    async def generate(*args): return json.dumps(dict(FLOOD,references=[]))
    monkeypatch.setattr(vision,'_generate',generate)
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert result.depth is None and result.status=='manual_review'

def test_live_failure_does_not_fabricate_measurement(live,monkeypatch):
    async def generate(*args): raise RuntimeError('secret-containing exception must not escape')
    monkeypatch.setattr(vision,'_generate',generate)
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert result.status=='failed' and result.depth is None and result.data=={}
    assert 'ai_unavailable' in result.flags
    assert 'secret' not in repr(result)

def test_missing_key_requires_manual_review(monkeypatch):
    monkeypatch.setenv('VISION_PROVIDER','gemini');monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    assert vision.provider_info()['provider']=='mock'
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert result.status=='failed' and result.depth is None
    assert 'missing_api_key' in result.flags

def test_api_live_and_manual_review(live,monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(settings,'UPLOADS',tmp_path/'uploads')
    async def generate(*args): return json.dumps(FLOOD)
    monkeypatch.setattr(vision,'_generate',generate)
    with TestClient(__import__('app.main',fromlist=['app']).app) as c:
        login_admin(c)
        token=alert(c)['recipients'][0]['token']
        fields=dict(token=token,lat=11.0168,lon=76.9558)
        receipt=c.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')}).json()
        assert receipt['extraction_status']=='ok'
        site=c.get('/api/incidents').json()[0]
        assert site['simulated'] is False
        assert 'MOCK' not in receipt['simulation_notice']
        async def non_flood(*args): return '{"scene_type":"out_of_scope"}'
        monkeypatch.setattr(vision,'_generate',non_flood)
        receipt=c.post('/api/reports',data=fields,files={'images':('other.jpg',picture(),'image/jpeg')}).json()
        assert receipt['extraction_status']=='manual_review'
        assert len(c.get('/api/incidents').json())==1

def test_live_failure_receipt_has_no_mock_priority(live,monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(settings,'UPLOADS',tmp_path/'uploads')
    async def generate(*args): raise RuntimeError('private credential must not appear')
    monkeypatch.setattr(vision,'_generate',generate)
    with TestClient(__import__('app.main',fromlist=['app']).app) as c:
        login_admin(c)
        token=alert(c)['recipients'][0]['token']
        response=c.post('/api/reports',data=dict(token=token,lat=11,lon=77),files={'images':('flood.jpg',picture(),'image/jpeg')})
        assert response.status_code==201
        receipt=response.json()
        assert receipt['extraction_status']=='failed'
        assert 'Help is being prioritised' not in receipt['message']
        assert 'MOCK extraction' not in receipt['simulation_notice']
        assert 'private credential' not in response.text
        assert c.get('/api/incidents').json()==[]
        assert c.get('/api/office').json()['campaigns'][0]['reports']==1

def test_real_retry_replaces_mock_observation(live,monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(settings,'UPLOADS',tmp_path/'uploads')
    async def generate(*args): return json.dumps(FLOOD)
    monkeypatch.setattr(vision,'_generate',generate)
    with TestClient(__import__('app.main',fromlist=['app']).app) as c:
        login_admin(c)
        token=alert(c)['recipients'][0]['token']
        fields=dict(token=token,lat=11,lon=77)
        monkeypatch.setenv('VISION_PROVIDER','mock')
        assert c.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')}).json()['extraction_status']=='mock'
        monkeypatch.setenv('VISION_PROVIDER','gemini')
        receipt=c.post('/api/reports',data=fields,files={'images':('flood.jpg',picture(),'image/jpeg')}).json()
        assert receipt['extraction_status']=='ok' and receipt['duplicate'] is False
        site=c.get('/api/incidents').json()[0]
        assert site['simulated'] is False and site['extraction_status']=='ok'

def test_sdk_disables_gemma_thinking(monkeypatch):
    captured={}
    async def generate_content(**kwargs): captured.update(kwargs); return SimpleNamespace(text='{}')
    client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    asyncio.run(vision._generate(client,'gemma-4-26b-a4b-it',b'image','prompt'))
    assert captured['config'].thinking_config.thinking_level.value=='MINIMAL'

def test_request_timeout_returns_manual_review(live,monkeypatch):
    monkeypatch.setitem(vision.OPTIONS,'request_timeout_seconds',.01)
    async def generate(*args): await asyncio.sleep(1)
    monkeypatch.setattr(vision,'_generate',generate)
    result=asyncio.run(vision.extract('flood.jpg',[b'image']))
    assert result.status=='failed' and result.depth is None
    assert 'provider_timeout' in result.flags
