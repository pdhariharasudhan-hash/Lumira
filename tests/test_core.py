from types import SimpleNamespace

from app.core.lumira_core import LumiraCore
from app.core.system_status import SystemStatus


def test_system_status_reflects_degraded_subsystem_probes():
    class Registry:
        def list_services(self):
            return ["planner", "memory"]

    class Health:
        def snapshot(self):
            return {
                "success": True,
                "status": "degraded",
                "timestamp": "2026-11-12T00:00:00+00:00",
                "checks": {
                    "core_events": {"status": "healthy"},
                    "dependencies": {"status": "degraded", "missing": ["sample-package"]},
                },
                "degraded_subsystems": ["dependencies"],
            }

    status = SystemStatus(registry=Registry(), health_service=Health()).get_status()

    assert status == {
        "services": ["planner", "memory"],
        "service_count": 2,
        "health": "degraded",
        "checks": {
            "core_events": {"status": "healthy"},
            "dependencies": {"status": "degraded", "missing": ["sample-package"]},
        },
        "degraded_subsystems": ["dependencies"],
        "health_timestamp": "2026-11-12T00:00:00+00:00",
    }


def test_system_status_fails_closed_when_health_probe_raises():
    class Registry:
        def list_services(self):
            return ["planner"]

    class Health:
        def snapshot(self):
            raise RuntimeError("private diagnostic detail")

    status = SystemStatus(registry=Registry(), health_service=Health()).get_status()

    assert status["services"] == ["planner"]
    assert status["service_count"] == 1
    assert status["health"] == "degraded"
    assert status["degraded_subsystems"] == ["system_health_service"]
    assert status["checks"] == {
        "system_health_service": {
            "status": "degraded",
            "error": "health_probe_failed",
        }
    }
    assert "private diagnostic detail" not in str(status)


def test_system_status_fails_closed_when_health_snapshot_is_malformed():
    class Registry:
        def list_services(self):
            return ["planner"]

    class Health:
        def snapshot(self):
            return {
                "success": True,
                "status": ["healthy"],
                "checks": {"probe": {"status": ["degraded"]}},
            }

    status = SystemStatus(registry=Registry(), health_service=Health()).get_status()

    assert status["health"] == "degraded"
    assert status["degraded_subsystems"] == ["system_health_service"]
    assert status["checks"]["system_health_service"]["error"] == "health_probe_failed"


def test_lumira_core_status_aggregator_uses_core_registry(monkeypatch):
    class Registry:
        def list_services(self):
            return ["planner"]

    registry = Registry()
    from app.core import lumira_core

    monkeypatch.setattr(lumira_core, "ServiceRegistry", lambda: registry)
    core = LumiraCore()

    assert core.system_status.registry is core.registry is registry


def test_core_run_delegates_project_generation_to_brain_and_preserves_result_contract(monkeypatch):
    builder_result = {"status": "accept", "steps": ["create storage", "create routes"]}
    execution_result = {"status": "accept", "builder": builder_result, "execution_order": ["step_1"]}
    code_result = {"status": "accept", "code_target": "task_api", "files": {"main.py": "app = True"}}
    validation = {"success": True, "valid": True, "errors": []}
    capability_result = {
        "success": True,
        "status": "accept",
        "builder": builder_result,
        "execution": execution_result,
        "code": code_result,
        "validation": validation,
        "saved_path": "generated/task_api/v1",
    }
    requests = []

    class Brain:
        def execute(self, request):
            requests.append(request)
            return SimpleNamespace(
                success=True,
                error=None,
                state=SimpleNamespace(execution_result=capability_result),
            )

    class Registry:
        def get(self, name):
            raise AssertionError(f"legacy service path must not be used: {name}")

    from app.services.brain import brain_service
    monkeypatch.setattr(brain_service, "BrainService", Brain)
    core = LumiraCore.__new__(LumiraCore)
    core.registry = Registry()

    result = core.run("Build a task API")

    assert result == {
        "success": True,
        "status": "accept",
        "current_stage": "complete",
        "last_completed_stage": "save",
        "final_status": "completed",
        "retry_count": 0,
        "goal": "Build a task API",
        "builder": builder_result,
        "execution": execution_result,
        "code": code_result,
        "validation": validation,
        "saved_to": "generated/task_api/v1",
    }
    assert len(requests) == 1
    assert requests[0].message == "Build a task API"
    assert requests[0].metadata["execute_capability"] == "project_generation"
    assert requests[0].metadata["capability_payload"] == {"idea": "Build a task API"}


def test_core_run_does_not_report_success_when_brain_rejects_project_generation(monkeypatch):
    class Brain:
        def execute(self, request):
            return SimpleNamespace(success=False, error="Verification rejected execution", state=None)

    from app.services.brain import brain_service
    monkeypatch.setattr(brain_service, "BrainService", Brain)
    core = LumiraCore.__new__(LumiraCore)

    result = core.run("Build a task API")

    assert result["success"] is False
    assert result["status"] == "reject"
    assert result["current_stage"] == "brain"
    assert result["final_status"] == "failed"


def test_core_run_rejects_project_generation_with_invalid_validation_result(monkeypatch):
    capability_result = {
        "success": True,
        "builder": {"status": "accept"},
        "execution": {"status": "accept"},
        "code": {"status": "accept"},
        "validation": {"success": True, "valid": False, "errors": ["invalid"]},
        "saved_path": "generated/task_api/v1",
    }

    class Brain:
        def execute(self, request):
            return SimpleNamespace(
                success=True,
                error=None,
                state=SimpleNamespace(execution_result=capability_result),
            )

    from app.services.brain import brain_service
    monkeypatch.setattr(brain_service, "BrainService", Brain)
    core = LumiraCore.__new__(LumiraCore)

    result = core.run("Build a task API")

    assert result["success"] is False
    assert result["current_stage"] == "verify_code"


def test_core_run_rejects_incomplete_capability_success_payload(monkeypatch):
    capability_result = {
        "success": True,
        "validation": {"valid": True},
        "saved_path": "generated/task_api/v1",
    }

    class Brain:
        def execute(self, request):
            return SimpleNamespace(
                success=True,
                error=None,
                state=SimpleNamespace(execution_result=capability_result),
            )

    from app.services.brain import brain_service
    monkeypatch.setattr(brain_service, "BrainService", Brain)
    core = LumiraCore.__new__(LumiraCore)

    result = core.run("Build a task API")

    assert result["success"] is False
    assert result["current_stage"] == "brain"
