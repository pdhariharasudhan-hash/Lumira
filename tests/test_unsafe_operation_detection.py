from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.security import router as security_router
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.security.unsafe_operation_detection_service import UnsafeOperationDetectionService


def _client_with_audit(monkeypatch, tmp_path):
    audit = SecurityAuditLogService(tmp_path / "security-audit.json")
    monkeypatch.setattr("app.routes.security.SecurityAuditLogService", lambda: audit)
    app = FastAPI()
    app.include_router(security_router)
    return TestClient(app), audit


def test_safe_instruction_is_allowed():
    result = UnsafeOperationDetectionService.analyze("Create a read-only project report")
    assert result["success"] is True
    assert result["allowed"] is True
    assert result["findings"] == []


def test_risky_instruction_requires_approval_without_executing():
    result = UnsafeOperationDetectionService.analyze("Delete the entire directory and disable the firewall")
    assert result["success"] is True
    assert result["allowed"] is False
    assert {item["rule"] for item in result["findings"]} == {
        "destructive_filesystem",
        "unsafe_privilege_change",
    }


def test_invalid_instruction_fails_closed():
    result = UnsafeOperationDetectionService.analyze("")
    assert result == {"success": False, "code": "invalid_instruction", "allowed": False, "findings": []}


def test_security_preflight_route_blocks_and_audits_unsafe_instruction(monkeypatch, tmp_path):
    client, audit = _client_with_audit(monkeypatch, tmp_path)
    response = client.post(
        "/security/preflight",
        json={"instruction": "Delete the entire directory and disable the firewall"},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is False
    assert response.json()["action"] == "block_pending_approval"
    assert audit.verify_integrity()["event_count"] == 1
    assert audit.recent_events()[0]["outcome"] == "blocked"


def test_security_preflight_route_rejects_unexpected_fields(monkeypatch, tmp_path):
    client, _ = _client_with_audit(monkeypatch, tmp_path)
    response = client.post(
        "/security/preflight",
        json={"instruction": "Create a report", "approved": True},
    )
    assert response.status_code == 422


def test_security_audit_routes_expose_integrity_and_recent_events(monkeypatch, tmp_path):
    client, audit = _client_with_audit(monkeypatch, tmp_path)
    audit.append(event_type="test", action="read", outcome="allowed")

    integrity = client.get("/security/audit/integrity")
    events = client.get("/security/audit/events?limit=10")

    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
    assert events.status_code == 200
    assert events.json()["count"] == 1
