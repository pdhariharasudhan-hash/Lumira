import asyncio

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth.local_auth_service import LocalAuthService


def test_local_signing_key_persists_and_issues_verifiable_single_owner_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token_response = TestClient(app).post("/auth/local-token")
    assert token_response.status_code == 200
    body = token_response.json()
    principal = LocalAuthService().verify(body["access_token"])
    assert principal["owner_id"] == "local"
    assert body["token_type"] == "bearer"
    assert LocalAuthService().verify(body["access_token"])["subject"] == "local"


def test_remote_private_apis_require_a_valid_bearer_and_bootstrap_is_loopback_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token = TestClient(app).post("/auth/local-token").json()["access_token"]

    async def requests():
        transport = httpx.ASGITransport(app=app, client=("198.51.100.42", 4321))
        async with httpx.AsyncClient(transport=transport, base_url="http://lumira") as client:
            missing = await client.get("/sessions")
            authorized = await client.get("/sessions", headers={"Authorization": f"Bearer {token}"})
            bootstrap = await client.post("/auth/local-token", headers={"Authorization": f"Bearer {token}"})
            invalid = await client.get("/sessions", headers={"Authorization": "Bearer invalid.token.value"})
            return missing, authorized, bootstrap, invalid

    missing, authorized, bootstrap, invalid = asyncio.run(requests())
    assert missing.status_code == 401
    assert authorized.status_code == 200
    assert bootstrap.status_code == 403
    assert invalid.status_code == 401


def test_invalid_local_origin_cannot_bootstrap_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/auth/local-token",
        headers={"Origin": "https://attacker.invalid"},
    )
    assert response.status_code == 403
