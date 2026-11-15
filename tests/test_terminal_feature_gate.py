import tempfile
from pathlib import Path

import pytest

from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.workspace.project_terminal_service import ProjectTerminalService
from app.services.features.feature_registry_service import FeatureRegistryService
from app.services.features.feature_activation_service import FeatureActivationService


def test_terminal_cannot_be_activated_without_verified_os_sandbox():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))

        allowed, blockers = registry.can_enable("terminal")
        assert allowed is False
        assert any("verified OS-level sandbox" in blocker for blocker in blockers)

        enabled, enable_blockers = registry.enable("terminal")
        assert enabled is False
        assert any("verified OS-level sandbox" in blocker for blocker in enable_blockers)
        assert registry.is_enabled("terminal") is False



def test_feature_list_reports_activation_blockers_for_terminal():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        activation = FeatureActivationService(registry)

        result = activation.list_features()

        assert result["success"] is True
        assert "terminal" in result["activation_blocked"]
        assert any(
            "verified OS-level sandbox" in blocker
            for blocker in result["activation_blocked"]["terminal"]
        )



def test_terminal_history_rejects_invalid_root_without_overwriting(tmp_path):
    path = tmp_path / "terminal_runs.json"
    original = '{"schema_version": 99}'
    path.write_text(original, encoding="utf-8")
    service = ProjectTerminalService(path)

    with pytest.raises(PersistenceIntegrityError, match="run history"):
        service.list_runs()

    assert path.read_text(encoding="utf-8") == original


def test_terminal_run_rejects_boolean_sandbox_flag_without_real_verifier(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    service = ProjectTerminalService(tmp_path / "terminal_runs.json")

    result = service.run(
        "demo",
        "v1",
        "compileall",
        trusted_project=True,
    )

    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"
    assert not (tmp_path / "terminal_runs.json").exists()


def test_terminal_os_error_does_not_disclose_machine_paths(tmp_path, monkeypatch):
    project = tmp_path / "generated" / "demo" / "v1"
    project.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    monkeypatch.setattr(ProjectTerminalService, "_os_sandbox_verified", lambda self: True)

    class FailingSandbox:
        def run(self, command, project_path, *, timeout):
            raise OSError(r"C:\\private\\machine\\path\\python.exe not found")

    service = ProjectTerminalService(
        tmp_path / "terminal_runs.json", sandbox=FailingSandbox()
    )

    result = service.run("demo", "v1", "compileall", trusted_project=True)

    assert result["success"] is False
    assert result["code"] == "terminal_execution_failed"
    assert result["message"] == "The project validation command could not be started."
    assert "private" not in str(result)
    assert result["error_type"] == "OSError"
    assert not (tmp_path / "terminal_runs.json").exists()


def test_project_terminal_is_hard_disabled_by_default():
    assert ProjectTerminalService.OS_SANDBOX_ENABLED is False


def test_default_factory_provider_is_not_trusted_without_explicit_injection(monkeypatch, tmp_path):
    class ReadySandbox:
        def status(self):
            return type("Status", (), {"available": True, "reason": "verified"})()

    monkeypatch.setattr(
        "app.services.workspace.project_terminal_service.create_sandbox_provider",
        lambda: ReadySandbox(),
    )
    service = ProjectTerminalService(tmp_path / "runs.json")

    assert service._os_sandbox_verified() is False
    assert ProjectTerminalService.OS_SANDBOX_ENABLED is False


def test_terminal_service_delegates_allowlisted_run_to_explicit_provider(monkeypatch, tmp_path):
    import subprocess

    calls = []

    class ReadySandbox:
        def status(self):
            return type("Status", (), {"available": True, "reason": "verified"})()

        def run(self, command, project_path, *, timeout):
            calls.append((command, project_path, timeout))
            return subprocess.CompletedProcess(command, 0, "sandbox pass", "")

    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "generated" / "demo" / "v1"
    project.mkdir(parents=True)

    service = ProjectTerminalService(tmp_path / "runs.json", sandbox=ReadySandbox())
    result = service.run("demo", "v1", "compileall", trusted_project=True)

    assert result["success"] is True
    assert calls == [(("python", "-m", "compileall", "app"), project, 120)]
    assert service.list_runs("demo", "v1")[0]["return_code"] == 0


def test_project_terminal_route_injects_concrete_platform_provider():
    from app.routes import project_terminal as terminal_route

    assert terminal_route.service._sandbox_explicit is True
    assert callable(terminal_route.service.sandbox.status)
    assert callable(terminal_route.service.sandbox.run)
    assert ProjectTerminalService.OS_SANDBOX_ENABLED is False
