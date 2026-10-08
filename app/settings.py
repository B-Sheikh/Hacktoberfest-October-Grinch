"""Editable assumptions and runtime settings; reference maths stays unchanged."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .intelligence import physics as p

load_dotenv()
CONFIG_DIR = Path(__file__).parent / 'config'
def config(name):
    return json.loads((CONFIG_DIR / f'{name}.json').read_text(encoding='utf-8'))

REFERENCES = config('references')
RATES = config('rates')
TH = config('thresholds')
TEAM = config('teams')
SURVIVAL = config('survival')
OCCUPANCY = config('occupancy')
TEXT = config('templates')
p.REFS = REFERENCES['flood']
p.RATE_PRIOR = RATES['priors']
p.V_CLASS = RATES['velocity']
p.SURV = SURVIVAL['curve']
p.T_EXT = SURVIVAL['extrication_min']
p.TYPE_F = TH['type_factors']
p.DRY_ABS = TH['dry_m']
p.TEAMS_SPEC = {k:(v['speed_kmh'],v['max_depth_m'],set(v['capabilities'])) for k,v in TEAM['specs'].items()}
DB_PATH = Path(os.getenv('WATERLINE_DB', 'data/waterline.db'))
UPLOADS = Path(os.getenv('WATERLINE_UPLOADS', 'uploads'))
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000').rstrip('/')
