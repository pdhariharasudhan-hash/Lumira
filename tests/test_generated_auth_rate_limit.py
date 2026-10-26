import base64
import json
import sys

from fastapi.testclient import TestClient

from app.services.code.code_service import CodeService


def test_generated_auth_limits_repeated_requests_per_client_ip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMIRA_AUTH_DATA_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    generated = CodeService().generate(
        "Build an expense API with authentication",
        {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]},
    )
    module_name = "generated_auth_rate_limit_app"
    module = type(sys)(module_name)
    exec(compile(generated["files"]["main.py"], module_name, "exec"), module.__dict__)
    client = TestClient(module.app)

    payload = {"username": "unknown-user", "password": "a-valid-length-password"}
    for _ in range(10):
        assert client.post("/login", json=payload).status_code == 401

    limited = client.post("/login", json=payload)
    assert limited.status_code == 429
    assert "Too many authentication attempts" in limited.json()["detail"]



def test_generated_auth_users_and_signing_key_survive_app_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMIRA_AUTH_DATA_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    generated = CodeService().generate(
        "Build an expense API with authentication",
        {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]},
    )
    source = generated["files"]["main.py"]

    first_module = type(sys)("generated_auth_persistence_first")
    exec(compile(source, first_module.__name__, "exec"), first_module.__dict__)
    first_client = TestClient(first_module.app)
    credentials = {"username": "persistent-user", "password": "a-strong-password-123"}
    assert first_client.post("/register", json=credentials).status_code == 200
    token = first_client.post("/login", json=credentials).json()["access_token"]

    second_module = type(sys)("generated_auth_persistence_second")
    exec(compile(source, second_module.__name__, "exec"), second_module.__dict__)
    second_client = TestClient(second_module.app)

    assert second_module.jwt_secret == first_module.jwt_secret
    response = second_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "persistent-user"


def test_generated_auth_rejects_malformed_base64_bearer_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMIRA_AUTH_DATA_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    generated = CodeService().generate(
        "Build an expense API with authentication",
        {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]},
    )
    module = type(sys)("generated_auth_malformed_token_app")
    exec(compile(generated["files"]["main.py"], module.__name__, "exec"), module.__dict__)
    client = TestClient(module.app)

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "nobody", "exp": 9_999_999_999}, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()

    malformed = client.get("/me", headers={"Authorization": f"Bearer {header}.{payload}.%%%"})
    non_ascii = client.get("/me", headers={"Authorization": f"Bearer é.{payload}.signature"})
    oversized = client.get("/me", headers={"Authorization": "Bearer " + ("a" * 5000)})
    assert malformed.status_code == 401
    assert non_ascii.status_code == 401
    assert oversized.status_code == 401



def test_generated_auth_rejects_signed_tokens_with_invalid_claim_types(tmp_path, monkeypatch):
    import hashlib
    import hmac

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMIRA_AUTH_DATA_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    generated = CodeService().generate(
        "Build an expense API with authentication",
        {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]},
    )
    module = type(sys)("generated_auth_claim_types_app")
    exec(compile(generated["files"]["main.py"], module.__name__, "exec"), module.__dict__)
    client = TestClient(module.app)

    header = module._b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    invalid_claims = [
        {"sub": "nobody", "exp": "9999999999"},
        {"sub": "nobody", "exp": True},
        ["nobody", 9999999999],
    ]

    for claims in invalid_claims:
        payload = module._b64encode(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{header}.{payload}"
        signature = hmac.new(
            module.jwt_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        token = f"{signing_input}.{module._b64encode(signature)}"
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
