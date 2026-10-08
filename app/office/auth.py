"""Single-admin credentials and revocable, opaque server-side sessions."""
import hashlib
import hmac
import os
import secrets
import time
from getpass import getpass
from urllib.parse import urlsplit
from dotenv import set_key
from .. import db

COOKIE = 'waterline_admin'
SESSION_SECONDS = 8 * 60 * 60

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or not 100000 <= int(rounds) <= 2000000: return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError): return False

def fingerprint(token): return hashlib.sha256(token.encode()).hexdigest()

def credential_version():
    return fingerprint(os.getenv('ADMIN_USERNAME','') + ':' + os.getenv('ADMIN_PASSWORD_HASH',''))

def session(request):
    token = request.cookies.get(COOKIE)
    if not token: return None
    with db.connection() as c:
        row = c.execute('SELECT * FROM admin_sessions WHERE token_hash=? AND expires>? AND credential_version=?',
            (fingerprint(token), time.time(), credential_version())).fetchone()
    return dict(row) if row else None

def same_origin(request):
    origin = request.headers.get('origin')
    return not origin or urlsplit(origin).netloc == request.headers.get('host')

def setup():
    username = input('Admin username [admin]: ').strip() or 'admin'
    password = getpass('New admin password (at least 12 characters): ')
    if len(password) < 12: raise SystemExit('Use at least 12 characters.')
    if password != getpass('Confirm password: '): raise SystemExit('Passwords did not match.')
    set_key('.env','ADMIN_USERNAME',username)
    set_key('.env','ADMIN_PASSWORD_HASH',hash_password(password))
    print('Admin credentials saved to ignored .env. Restart the server; previous sessions will be invalidated.')

if __name__ == '__main__': setup()
