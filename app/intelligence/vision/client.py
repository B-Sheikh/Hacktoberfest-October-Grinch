"""Gemma image perception with bounded retries, validation and visible fallback."""
import asyncio
import json
import os
import logging
from dataclasses import dataclass, field
from google import genai
from google.genai import types, errors
from pydantic import ValidationError

from .. import physics as p
from ...settings import config
from .mock_data import mock_extract
from .prompts import flood_prompt
from .schemas import FloodExtraction, UnsupportedScene

OPTIONS = config('vision')
logger = logging.getLogger(__name__)
_semaphore = asyncio.Semaphore(OPTIONS['concurrent_calls'])

@dataclass
class Extraction:
    data: dict
    status: str
    depth: dict | None = None
    flags: list[str] = field(default_factory=list)

def provider_info():
    requested = os.getenv('VISION_PROVIDER', 'mock').lower()
    configured = requested == 'gemini' and bool(os.getenv('GEMINI_API_KEY'))
    model=(os.getenv('VISION_MODEL') or OPTIONS['default_model']) if configured else None
    return dict(provider='live' if configured else 'mock', configured_provider=requested,
                model=model,
                live_vision_implemented=True)

def parse_response(text):
    text = (text or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines)<3 or lines[-1].strip()!='```':
            raise ValueError('Incomplete JSON fence')
        text = '\n'.join(lines[1:-1])
    data = json.loads(text)
    if not isinstance(data, dict): raise ValueError('Expected JSON object')
    schema = FloodExtraction if data.get('scene_type')=='flood' else UnsupportedScene
    return schema.model_validate(data).model_dump()

async def _generate(client, model, image, prompt):
    generation = types.GenerateContentConfig(temperature=OPTIONS['temperature'],
        max_output_tokens=OPTIONS['max_output_tokens'])
    if model.startswith('gemma-4'):
        generation.thinking_config = types.ThinkingConfig(thinking_level='minimal')
    async with _semaphore:
        response = await client.aio.models.generate_content(
            model=model, contents=[prompt, types.Part.from_bytes(data=image,mime_type='image/jpeg')],
            config=generation)
    return response.text

async def _one(client, model, image):
    prompt = flood_prompt()
    for attempt in range(OPTIONS['max_attempts']):
        try:
            return parse_response(await _generate(client,model,image,prompt)), attempt>0
        except (ValueError, ValidationError):
            # Avoid including raw model output or request credentials in retry text.
            prompt = flood_prompt()+'\nYour last output was invalid JSON or schema. Return corrected JSON only.'
        except errors.APIError as exc:
            if exc.code not in [429,500,502,503,504]: raise
        if attempt+1<OPTIONS['max_attempts']:
            await asyncio.sleep(OPTIONS['backoff_seconds'][attempt])
    raise ValueError('Extraction retries exhausted')

def _photo_depth(runs):
    flags = []
    common = set(r['ref_id'] for r in runs[0]['references'] if r['touches_same_ground_as_water'])
    for run in runs[1:]:
        common &= {r['ref_id'] for r in run['references'] if r['touches_same_ground_as_water']}
    intervals=[]
    for ref_id in sorted(common):
        refs = [next(r for r in run['references'] if r['ref_id']==ref_id) for run in runs]
        low, high = p.ensemble_bin([r['waterline_bin'] for r in refs])
        if low!=high: flags.append('model_disagreement')
        a = p.ref_interval(ref_id,p.BINS[low])
        b = p.ref_interval(ref_id,p.BINS[high])
        intervals.append((a[0],b[1]))
    if not intervals: return None, ['no_common_reference']
    depth = p.fuse(intervals)
    depth['flags'] = sorted(set(depth['flags']+flags))
    return depth, depth['flags']

def _fallback(filename):
    data=mock_extract(filename)
    depth=p.fuse([p.ref_interval(r['ref_id'],r['waterline_bin']) for r in data['references']])
    return Extraction(data,'mock',depth)

def _failure_reason(exc):
    if isinstance(exc, errors.APIError):
        return {400:'invalid_provider_request',401:'invalid_api_key',403:'provider_access_denied',
                404:'model_not_found',429:'provider_rate_limit',504:'provider_timeout'}.get(exc.code,'provider_unavailable')
    if isinstance(exc, TimeoutError): return 'provider_timeout'
    if isinstance(exc, ValueError): return 'invalid_model_output'
    return 'provider_unavailable'

def _failure(reason):
    # Log only a fixed diagnostic code, never SDK text, URLs, headers or photo content.
    logger.warning('Photo analysis failed: %s', reason)
    return Extraction({},'failed',flags=['ai_unavailable',reason])

async def extract(filename, images):
    info=provider_info()
    if info['configured_provider']=='mock': return _fallback(filename)
    if info['provider']!='live': return _failure('missing_api_key')
    client=None
    try:
        client=genai.Client(api_key=os.environ['GEMINI_API_KEY'],http_options=types.HttpOptions(
            timeout=OPTIONS['timeout_ms'],retry_options=types.HttpRetryOptions(attempts=1)))
        return await asyncio.wait_for(_extract_live(client,info['model'],images,filename),
                                      timeout=OPTIONS['request_timeout_seconds'])
    except Exception as exc:
        # Raw SDK exceptions may include headers or URLs; never return/log them.
        return _failure(_failure_reason(exc))
    finally:
        if client is not None:
            try:
                await client.aio.aclose()
                client.close()
            except Exception:
                pass

async def _extract_live(client,model,images,filename):
    photo_results=[]
    retried=False
    for image in images:
        # Bounded SDK calls; no background task survives a failed extraction.
        outcomes=await asyncio.gather(*[_one(client,model,image) for _ in range(OPTIONS['flood_runs'])],return_exceptions=True)
        failures=[x for x in outcomes if isinstance(x,BaseException)]
        if failures: return _failure(_failure_reason(failures[0]))
        runs=[x[0] for x in outcomes];retried |= any(x[1] for x in outcomes)
        scenes={r['scene_type'] for r in runs}
        if scenes!={'flood'}:
            scene=runs[0]['scene_type'] if len(scenes)==1 else 'out_of_scope'
            return Extraction({'scene_type':scene},'manual_review',flags=['scene_requires_manual_review'])
        if not all(r['image_usable'] for r in runs):
            return Extraction(runs[0],'manual_review',flags=['unusable_image'])
        depth,flags=_photo_depth(runs)
        if depth is None: return Extraction(runs[0],'manual_review',flags=flags)
        photo_results.append((runs,depth))
    all_runs=[r for runs,_ in photo_results for r in runs]
    result=dict(all_runs[0])
    # Use conservative flow/debris classes; expose variation as uncertainty.
    flags=[f for _,d in photo_results for f in d['flags']]
    for key in ['flow_class','trend','debris']:
        values={r[key] for r in all_runs}
        if len(values)>1: flags.append('model_disagreement')
    result['flow_class']=max((r['flow_class'] for r in all_runs),key=lambda value:p.V_CLASS.get(value,-1))
    result['debris']=max((r['debris'] for r in all_runs),key=['none','some','heavy'].index)
    result['people']={'count_visible':max(r['people']['count_visible'] for r in all_runs),
                      'contexts':sorted({c for r in all_runs for c in r['people']['contexts']})}
    result['hazards']=sorted({h for r in all_runs for h in r['hazards'] if h!='none'})
    if any(r['wet_line_above_water'] or r['trend']=='receding' for r in all_runs):
        result.update(wet_line_above_water=True,trend='receding')
    depth=p.fuse([(d['lo'],d['hi']) for _,d in photo_results])
    depth['flags']=sorted(set(depth['flags']+flags))
    return Extraction(result,'retry_ok' if retried else 'ok',depth,depth['flags'])
