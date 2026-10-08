import pytest
from app.office.auth import hash_password

TEST_PASSWORD = 'test-admin-password-only'
TEST_HASH = hash_password(TEST_PASSWORD)

@pytest.fixture(autouse=True)
def admin_credentials(monkeypatch):
    monkeypatch.setenv('ADMIN_USERNAME','test-admin')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',TEST_HASH)
    monkeypatch.setenv('ADMIN_COOKIE_SECURE','false')

def login_admin(client):
    response=client.post('/api/auth/login',data={'username':'test-admin','password':TEST_PASSWORD})
    assert response.status_code==200,response.text
    client.headers['X-Waterline-Request']='1'
