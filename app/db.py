import sqlite3
from contextlib import contextmanager
from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
 id TEXT PRIMARY KEY, data TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS recipients (
 token TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
 phone TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', message TEXT);
CREATE TABLE IF NOT EXISTS incidents (
 id TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
 family TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'open', data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
 incident_id TEXT REFERENCES incidents(id) ON DELETE CASCADE, ahash TEXT,
 duplicate INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teams (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assignments (
 team_id TEXT PRIMARY KEY REFERENCES teams(id), incident_id TEXT UNIQUE REFERENCES incidents(id) ON DELETE CASCADE,
 data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS field_updates (
 id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS report_incident ON reports(incident_id);
"""

@contextmanager
def connection():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init():
    with connection() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript(SCHEMA)
