from app.services.brain.brain_execution_coordinator import BrainExecutionCoordinator
from app.services.modes.models.mode_state import ModeState
from app.services.security.security_audit_log_service import SecurityAuditLogService


def _use_test_audit_log(monkeypatch, tmp_path):
    audit = SecurityAuditLogService(tmp_path / "security-audit.json")
    monkeypatch.setattr(
        "app.services.brain.brain_execution_coordinator.SecurityAuditLogService",
        lambda: audit,
    )
    return audit


class Router:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, capability, payload):
        self.calls.append((capability, payload))
        return self.result


class ModeAwareRouter:
    def __init__(self):
        self.calls = []

    def execute(self, capability, payload, mode_state=None):
        self.calls.append((capability, payload, mode_state))
        return {"success": True}


def test_coordinator_requires_verified_plan_before_side_effect():
    router = Router({"success": True, "status": "accept"})
    result = BrainExecutionCoordinator(router).execute(
        capability="planning",
        payload={"request": "build it"},
        ready_for_execution=False,
    )

    assert result["code"] == "verification_required"
    assert router.calls == []


def test_coordinator_routes_explicit_interactive_capability():
    router = Router({"success": True, "status": "accept", "result": {"ok": True}})
    result = BrainExecutionCoordinator(router).execute(
        capability="planning",
        payload={"request": "build it"},
        ready_for_execution=True,
    )

    assert result["success"] is True
    assert router.calls == [("planning", {"request": "build it"})]


def test_coordinator_preserves_active_mode_when_routing_capability():
    router = ModeAwareRouter()
    mode_state = ModeState(active_mode="builder")

    result = BrainExecutionCoordinator(router).execute(
        capability="planning",
        payload={"request": "build it"},
        ready_for_execution=True,
        mode_state=mode_state,
    )

    assert result["success"] is True
    assert router.calls == [("planning", {"request": "build it"}, mode_state)]


def test_coordinator_routes_read_only_conversation_without_execution_authorization():
    capability_router = Router({"success": True})

    class ConversationRouter:
        def __init__(self):
            self.calls = []

        def chat(self, message, *, history=None, context=None):
            self.calls.append((message, history, context))
            return "A provider-backed answer."

    conversation_router = ConversationRouter()
    result = BrainExecutionCoordinator(
        capability_router,
        conversation_router=conversation_router,
    ).execute(
        capability="conversation",
        payload={
            "message": "Explain photosynthesis.",
            "history": [{"role": "user", "content": "What is a plant?"}],
            "context": "Relevant remembered facts.",
        },
        ready_for_execution=False,
    )

    assert result["success"] is True
    assert result["message"] == "A provider-backed answer."
    assert capability_router.calls == []
    assert conversation_router.calls == [
        (
            "Explain photosynthesis.",
            [{"role": "user", "content": "What is a plant?"}],
            "Relevant remembered facts.",
        )
    ]


def test_coordinator_blocks_unsafe_instruction_before_side_effect(monkeypatch, tmp_path):
    audit = _use_test_audit_log(monkeypatch, tmp_path)
    router = Router({"success": True, "status": "accept"})
    result = BrainExecutionCoordinator(router).execute(
        capability="code_generation",
        payload={"idea": "perform requested operation"},
        ready_for_execution=True,
        instruction="Delete the entire directory and disable the firewall",
    )

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["code"] == "unsafe_operation_requires_approval"
    assert router.calls == []
    integrity = audit.verify_integrity()
    assert integrity["valid"] is True
    assert integrity["event_count"] == 1
    assert audit.recent_events()[0]["outcome"] == "blocked"


def test_coordinator_allows_safe_explicit_instruction(monkeypatch, tmp_path):
    audit = _use_test_audit_log(monkeypatch, tmp_path)
    router = Router({"success": True, "status": "accept"})
    result = BrainExecutionCoordinator(router).execute(
        capability="code_generation",
        payload={"idea": "create a read-only report"},
        ready_for_execution=True,
        instruction="Create a read-only report from the project files",
    )

    assert result["success"] is True
    assert len(router.calls) == 1
    assert audit.verify_integrity()["event_count"] == 1
    assert audit.recent_events()[0]["outcome"] == "allowed"


def test_coordinator_fails_closed_when_security_audit_cannot_be_written(monkeypatch):
    class BrokenAudit:
        def append(self, **kwargs):
            raise OSError("disk unavailable")

    monkeypatch.setattr(
        "app.services.brain.brain_execution_coordinator.SecurityAuditLogService",
        lambda: BrokenAudit(),
    )
    router = Router({"success": True, "status": "accept"})
    result = BrainExecutionCoordinator(router).execute(
        capability="code_generation",
        payload={"idea": "create a read-only report"},
        ready_for_execution=True,
        instruction="Create a read-only report",
    )

    assert result["success"] is False
    assert result["code"] == "security_audit_unavailable"
    assert router.calls == []


def test_coordinator_rejects_autonomous_code_without_permission(monkeypatch):
    router = Router({"success": True, "status": "accept"})
    monkeypatch.setattr(
        "app.services.brain.brain_execution_coordinator.AutonomyPermissionService.authorize",
        lambda *args, **kwargs: {
            "allowed": False,
            "code": "autonomous_permission_required",
            "message": "permission required",
        },
    )

    result = BrainExecutionCoordinator(router).execute(
        capability="code_generation",
        payload={"idea": "create a file"},
        ready_for_execution=True,
        autonomous=True,
    )

    assert result["success"] is False
    assert result["code"] == "autonomous_permission_required"
    assert router.calls == []


def test_coordinator_rejects_autonomous_persistent_workflow_capabilities_without_permission(monkeypatch):
    router = Router({"success": True, "status": "planned"})
    authorization_calls = []

    def deny(self, operation, *, autonomous):
        authorization_calls.append((operation, autonomous))
        return {
            "allowed": False,
            "code": "autonomous_permission_required",
            "message": "permission required",
        }

    monkeypatch.setattr(
        "app.services.brain.brain_execution_coordinator.AutonomyPermissionService.authorize",
        deny,
    )

    for capability in ("workflow_automation", "business_operations"):
        result = BrainExecutionCoordinator(router).execute(
            capability=capability,
            payload={"request": "Create a scheduled review workflow"},
            ready_for_execution=True,
            autonomous=True,
        )

        assert result["success"] is False
        assert result["code"] == "autonomous_permission_required"

    assert authorization_calls == [
        ("workflow.run", True),
        ("workflow.run", True),
    ]
    assert router.calls == []
