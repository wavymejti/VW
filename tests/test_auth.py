import pytest
from tools.server import app
import json
import uuid

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    with app.test_client() as client:
        yield client

def test_register_login_logout(client):
    """Test the full register, login, logout flow."""
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "testpassword"
    display_name = "Test User"

    # 1. Register
    reg_resp = client.post('/api/register', json={
        "email": email,
        "password": password,
        "display_name": display_name
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.get_json()
    assert reg_data["status"] == "success"
    assert reg_data["user"]["email"] == email

    # 2. Check /api/me (should be logged in automatically after register)
    me_resp = client.get('/api/me')
    assert me_resp.status_code == 200
    me_data = me_resp.get_json()
    assert me_data["user"]["email"] == email

    # 3. Logout
    logout_resp = client.post('/api/logout')
    assert logout_resp.status_code == 200
    assert logout_resp.get_json()["status"] == "success"

    # 4. Check /api/me (should be logged out)
    me_resp2 = client.get('/api/me')
    assert me_resp2.status_code == 401

    # 5. Login
    login_resp = client.post('/api/login', json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()
    assert login_data["status"] == "success"
    assert login_data["user"]["email"] == email

def test_login_invalid_credentials(client):
    """Test login with wrong password."""
    email = "admin@example.com" # Should exist if seeded, or use random
    login_resp = client.post('/api/login', json={
        "email": email,
        "password": "wrongpassword"
    })
    assert login_resp.status_code == 401
    assert login_resp.get_json()["status"] == "error"

def test_protected_routes_unauthorized(client):
    """Test that protected routes return 401 when not logged in."""
    routes = [
        ('/api/plan_route', 'POST'),
        ('/api/upload_photo', 'POST'),
        ('/api/generate_summary', 'POST'),
        ('/api/trips', 'GET')
    ]
    for url, method in routes:
        if method == 'POST':
            resp = client.post(url, json={})
        else:
            resp = client.get(url)
        assert resp.status_code == 401
