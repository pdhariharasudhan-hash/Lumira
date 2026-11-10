import json

import pytest

from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.security.security_audit_log_service import SecurityAuditLogService


def test_audit_log_appends_and_verifies_hash_chain(tmp_path):
    service = SecurityAuditLogService(tmp_path / "audit.json")
    first = service.append(
        event_type="instruction_preflight",
        action="code_generation",
        outcome="blocked",
        actor="main_brain",
        details={"finding_count": 1, "api_key": "must-not-be-stored"},
    )
    second = service.append(
        event_type="permission_check",
        action="code.execute",
        outcome="denied",
        details={"reason": "not approved"},
    )

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert "api_key" not in first["details"]
    assert service.verify_integrity()["valid"] is True
    assert service.verify_integrity()["event_count"] == 2
    assert service.recent_events(1)[0]["event_id"] == second["event_id"]


def test_audit_log_detects_modified_event(tmp_path):
    path = tmp_path / "audit.json"
    service = SecurityAuditLogService(path)
    service.append(event_type="test", action="read", outcome="allowed")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["events"][0]["outcome"] = "blocked"
    path.write_text(json.dumps(document), encoding="utf-8")

    assert service.verify_integrity()["valid"] is False
    with pytest.raises(PersistenceIntegrityError):
        service.append(event_type="test", action="write", outcome="allowed")


def test_audit_log_rejects_invalid_document_shape(tmp_path):
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"schema_version": 1, "events": {}, "last_hash": "x"}), encoding="utf-8")

    service = SecurityAuditLogService(path)
    assert service.verify_integrity()["valid"] is False
    with pytest.raises(PersistenceIntegrityError):
        service.recent_events()


def test_audit_log_rejects_invalid_limits_and_details(tmp_path):
    service = SecurityAuditLogService(tmp_path / "audit.json")
    with pytest.raises(ValueError):
        service.recent_events(0)
    with pytest.raises(ValueError):
        service.append(event_type="test", action="read", outcome="allowed", details=["not", "an object"])
