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

    def fail_to_start(*args, **kwargs):
        raise OSError(r"C:\\private\\machine\\path\\python.exe not found")

    monkeypatch.setattr("app.services.workspace.project_terminal_service.subprocess.run", fail_to_start)
    service = ProjectTerminalService(tmp_path / "terminal_runs.json")

    result = service.run("demo", "v1", "compileall", trusted_project=True)

    assert result["success"] is False
    assert result["code"] == "terminal_execution_failed"
    assert result["message"] == "The project validation command could not be started."
    assert "private" not in str(result)
    assert result["error_type"] == "OSError"
    assert not (tmp_path / "terminal_runs.json").exists()
