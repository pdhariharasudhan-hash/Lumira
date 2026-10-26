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


def test_local_workbench_origin_remains_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).get(
        "/sessions",
        headers={"Origin": "http://127.0.0.1:5000"},
    )
    assert response.status_code == 200


def test_untrusted_browser_origin_cannot_use_loopback_api_trust(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/voice/wake-word/start",
        headers={"Origin": "https://attacker.invalid"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted browser origin"


def test_unregistered_local_port_is_not_a_trusted_workbench_origin(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/voice/wake-word/start",
        headers={"Origin": "http://127.0.0.1:4321"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted browser origin"


def test_malformed_local_origin_port_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/voice/wake-word/start",
        headers={"Origin": "http://localhost:99999"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted browser origin"


def test_invalid_local_origin_cannot_bootstrap_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/auth/local-token",
        headers={"Origin": "https://attacker.invalid"},
    )
    assert response.status_code == 403


def test_malformed_base64_bearer_tokens_are_rejected_without_raising(tmp_path):
    service = LocalAuthService(tmp_path / "local_api_signing_key.json")
    token = service.issue_local_token()["access_token"]
    header, payload, _signature = token.split(".")

    assert service.verify(f"{header}.{payload}.%%%") is None
    assert service.verify(f"{header}.{payload}.é") is None



def test_local_auth_rejects_signed_tokens_with_invalid_claim_shapes_and_types(tmp_path):
    import hashlib
    import hmac
    import json
    import time

    service = LocalAuthService(tmp_path / "local_api_signing_key.json")
    header = service._encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    valid_base = {
        "iss": service.ISSUER,
        "sub": "local",
        "owner_id": "local",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "jti": "test",
    }
    invalid_payloads = [
        [],
        {**valid_base, "exp": True},
        {**valid_base, "exp": str(valid_base["exp"])},
        {**valid_base, "iat": True},
        {**valid_base, "iat": str(valid_base["iat"])},
        {**valid_base, "iat": 0},
        {**valid_base, "exp": valid_base["iat"] - 1},
        {**valid_base, "exp": valid_base["iat"] + service.TOKEN_LIFETIME_SECONDS + 1},
    ]

    for payload in invalid_payloads:
        payload_part = service._encode(json.dumps(payload).encode())
        signing_input = f"{header}.{payload_part}"
        signature = hmac.new(
            service._signing_key(),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        token = f"{signing_input}.{service._encode(signature)}"
        assert service.verify(token) is None
