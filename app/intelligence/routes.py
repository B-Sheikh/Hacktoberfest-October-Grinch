"""Intelligence HTTP routes"""
from app import db
from app import settings
from app.intelligence.vision.client import provider_info
import json
from fastapi import APIRouter

router = APIRouter()

@router.get('/api/config')
def public_config():
    return {'thresholds':settings.TH,'templates':settings.TEXT,'teams':settings.TEAM,'vision':provider_info()}


@router.get('/api/health')
def health():
    with db.connection() as c: c.execute('SELECT 1').fetchone()
    return {'status':'ok','db':'ok','version':'0.1.0',**provider_info()}


@router.get('/api/benchmark')
def benchmark():
    with db.connection() as c: updates=[json.loads(r['data']) for r in c.execute('SELECT data FROM field_updates')]
    samples=[]
    for u in updates:
        d=u.get('estimate_at_measurement')
        if u['depth_cm'] is not None and d:
            samples.append(dict(error_cm=abs(u['depth_cm']-d['mid']*100),inside_interval=d['lo']*100<=u['depth_cm']<=d['hi']*100))
    return {'sample_count':len(samples),'mean_absolute_error_cm':sum(s['error_cm'] for s in samples)/len(samples) if samples else None,
            'fraction_inside_interval':sum(s['inside_interval'] for s in samples)/len(samples) if samples else None,'samples':samples}
