from fastapi.testclient import TestClient
from conftest import register, upload


def test_register_login_logout_flow(client):
    r = register(client)
    assert r.status_code == 201 and r.json()["user"]["email"] == "a@example.com"
    assert "password" not in r.text
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    ok = client.post("/api/auth/login", json={"email": "A@Example.com", "password": "Passw0rdX"})
    assert ok.status_code == 200


def test_duplicate_email_and_bad_inputs(client):
    register(client)
    assert register(client).status_code == 409
    assert register(client, email="nope").status_code == 400
    assert register(client, email="b@example.com", password="short").status_code == 400
    assert register(client, email="c@example.com", password="allletters").status_code == 400


def test_invalid_credentials_and_throttle(client):
    register(client)
    client.cookies.clear()
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "Passw0rdX"}).status_code == 429


def test_password_is_hashed_in_db(client, env):
    register(client)
    import sqlite3
    row = sqlite3.connect(env.settings.db_path).execute("select password_hash from users").fetchone()[0]
    assert row.startswith("scrypt$") and "Passw0rdX" not in row


def test_protected_routes_require_login(client):
    for path in ["/api/dashboard", "/api/predictions", "/api/analytics", "/api/library", "/api/activity", "/api/profile", "/api/crop/info", "/api/weather?location=x"]:
        assert client.get(path).status_code == 401, path
    assert client.post("/api/predict", files={"file": ("a.png", b"x")}).status_code == 401
    assert client.post("/api/crop/recommend", json={}).status_code == 401


def test_users_cannot_see_each_others_records(env):
    a, b = TestClient(env.app), TestClient(env.app)
    register(a, "a@example.com"); register(b, "b@example.com")
    pid = upload(a).json()["id"]
    rec = a.post("/api/fertilizer/recommend", json={"crop": "rice", "n_level": "low"}).json()["id"]
    cid = a.post("/api/crop/recommend", json=dict(N=80, P=45, K=40, temperature=24, humidity=82, ph=6.4, rainfall=230)).json()["id"]
    for path in (f"/api/predictions/{pid}", f"/api/predictions/{pid}/image", f"/api/recommendations/{rec}", f"/api/recommendations/{cid}"):
        assert b.get(path).status_code == 404, path
    assert b.delete(f"/api/predictions/{pid}").status_code == 404
    assert b.delete(f"/api/recommendations/{rec}").status_code == 404
    assert b.get("/api/predictions").json()["total"] == 0 and b.get("/api/activity").json()["total"] == 0
    assert b.post("/api/consultations", json={"prediction_id": pid, "name": "B", "contact": "b@example.com", "message": "please help"}).status_code == 404
    assert a.get(f"/api/predictions/{pid}").status_code == 200


def test_profile_update_and_password_change(authed):
    assert authed.patch("/api/profile", json={"name": "New Name"}).json()["user"]["name"] == "New Name"
    assert authed.post("/api/profile/password", json={"current_password": "bad", "new_password": "Another1234"}).status_code == 400
    assert authed.post("/api/profile/password", json={"current_password": "Passw0rdX", "new_password": "weak"}).status_code == 400
    assert authed.post("/api/profile/password", json={"current_password": "Passw0rdX", "new_password": "Another1234"}).status_code == 200
    authed.cookies.clear()
    assert authed.post("/api/auth/login", json={"email": "a@example.com", "password": "Another1234"}).status_code == 200
