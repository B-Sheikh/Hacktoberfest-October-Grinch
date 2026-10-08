"""Shared utilities"""
from pathlib import Path
from fastapi import HTTPException
import json
import uuid

def dump(value): return json.dumps(value,allow_nan=False)


def identity(): return uuid.uuid4().hex


def require_alert(c,alert_id):
    row=c.execute('SELECT data FROM alerts WHERE id=?',(alert_id,)).fetchone()
    if not row: raise HTTPException(404,'Alert not found')
    return json.loads(row['data'])

STATIC = Path(__file__).parent / "static"
