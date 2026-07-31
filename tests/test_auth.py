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
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    # First register user
    client.post('/api/register', json={"email": email, "password": "correctpassword"})
    client.post('/api/logout')

    # Try wrong password
    login_resp = client.post('/api/login', json={
        "email": email,
        "password": "wrongpassword"
    })
    assert login_resp.status_code == 401
    assert login_resp.get_json()["status"] == "error"

def test_register_validation(client):
    """Test registration input validation."""
    # Missing password
    resp1 = client.post('/api/register', json={"email": "nopass@example.com"})
    assert resp1.status_code == 400
    assert resp1.get_json()["status"] == "error"

    # Missing email
    resp2 = client.post('/api/register', json={"password": "somepassword"})
    assert resp2.status_code == 400
    assert resp2.get_json()["status"] == "error"

def test_register_duplicate_email(client):
    """Test registering duplicate email fails."""
    email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
    res1 = client.post('/api/register', json={"email": email, "password": "pass1"})
    assert res1.status_code == 200

    # Duplicate registration
    res2 = client.post('/api/register', json={"email": email, "password": "pass2"})
    assert res2.status_code == 400
    assert res2.get_json()["status"] == "error"
    assert "already registered" in res2.get_json()["message"]

def test_protected_routes_unauthorized(client):
    """Test that protected routes return 401 when not logged in."""
    routes = [
        ('/api/plan_route', 'POST'),
        ('/api/upload_photo', 'POST'),
        ('/api/generate_summary', 'POST'),
        ('/api/trips', 'GET'),
        ('/api/preferences', 'GET'),
        ('/api/preferences', 'PUT')
    ]
    for url, method in routes:
        if method == 'POST' or method == 'PUT':
            resp = client.post(url, json={}) if method == 'POST' else client.put(url, json={})
        else:
            resp = client.get(url)
        assert resp.status_code == 401

def test_preferences_flow(client):
    """Test fetching and updating VW California vehicle preferences."""
    email = f"vw_driver_{uuid.uuid4().hex[:6]}@example.com"
    client.post('/api/register', json={
        "email": email,
        "password": "californiapass",
        "display_name": "California Driver"
    })

    # 1. Fetch default preferences
    pref_get_resp = client.get('/api/preferences')
    assert pref_get_resp.status_code == 200
    prefs = pref_get_resp.get_json()["preferences"]
    assert prefs["vehicle_model"] == "VW California"
    assert prefs["max_daily_drive_hours"] == 6.0
    assert prefs["preferred_amenities"] == []

    # 2. Update vehicle preferences
    updated_payload = {
        "max_daily_drive_hours": 4.5,
        "preferred_amenities": ["shore_power", "water_hookup", "dog_friendly"],
        "budget_per_night_eur": 35.0,
        "hookup_type": "230V CEE",
        "vehicle_model": "VW California Ocean T6.1"
    }
    pref_put_resp = client.put('/api/preferences', json=updated_payload)
    assert pref_put_resp.status_code == 200
    put_data = pref_put_resp.get_json()
    assert put_data["status"] == "success"
    assert put_data["preferences"]["vehicle_model"] == "VW California Ocean T6.1"
    assert put_data["preferences"]["max_daily_drive_hours"] == 4.5
    assert put_data["preferences"]["preferred_amenities"] == ["shore_power", "water_hookup", "dog_friendly"]
    assert put_data["preferences"]["hookup_type"] == "230V CEE"

    # 3. Fetch preferences again to verify persistence
    pref_get_resp2 = client.get('/api/preferences')
    assert pref_get_resp2.status_code == 200
    prefs2 = pref_get_resp2.get_json()["preferences"]
    assert prefs2["vehicle_model"] == "VW California Ocean T6.1"
    assert prefs2["max_daily_drive_hours"] == 4.5
    assert prefs2["hookup_type"] == "230V CEE"

def test_preferences_invalid_type(client):
    """Test updating preferences with invalid field types."""
    email = f"invalid_pref_{uuid.uuid4().hex[:6]}@example.com"
    client.post('/api/register', json={"email": email, "password": "password123"})

    # Invalid max_daily_drive_hours (string instead of int/float)
    resp = client.put('/api/preferences', json={"max_daily_drive_hours": "not_a_number"})
    assert resp.status_code == 400
    assert resp.get_json()["status"] == "error"
    assert "Invalid type for max_daily_drive_hours" in resp.get_json()["message"]

    # Invalid preferred_amenities (dict instead of list)
    resp2 = client.put('/api/preferences', json={"preferred_amenities": "should_be_list"})
    assert resp2.status_code == 400
    assert resp2.get_json()["status"] == "error"
    assert "Invalid type for preferred_amenities" in resp2.get_json()["message"]

