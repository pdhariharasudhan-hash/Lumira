from app.services.workspace.container_sandbox_provider import ContainerSandboxProvider
from app.services.workspace.project_terminal_service import ProjectTerminalService
from app.services.workspace.sandbox_readiness_service import SandboxReadinessService
from app.services.workspace.windows_sandbox_provider import WindowsSandboxProvider


def test_windows_terminal_and_readiness_use_windows_sandbox_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.workspace.sandbox_provider_factory.sys.platform", "win32")

    terminal = ProjectTerminalService(tmp_path / "runs.json")
    readiness = SandboxReadinessService()

    assert isinstance(terminal.sandbox, WindowsSandboxProvider)
    assert isinstance(readiness.sandbox, WindowsSandboxProvider)


def test_non_windows_terminal_and_readiness_use_container_provider(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.workspace.sandbox_provider_factory.sys.platform", "linux")

    terminal = ProjectTerminalService(tmp_path / "runs.json")
    readiness = SandboxReadinessService()

    assert isinstance(terminal.sandbox, ContainerSandboxProvider)
    assert isinstance(readiness.sandbox, ContainerSandboxProvider)


def test_default_windows_provider_does_not_enable_terminal(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.workspace.sandbox_provider_factory.sys.platform", "win32")
    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    terminal = ProjectTerminalService(tmp_path / "runs.json")

    result = terminal.run("demo", "v1", "compileall", trusted_project=True)

    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"
    assert not (tmp_path / "runs.json").exists()


def test_readiness_distinguishes_host_prerequisites_from_live_execution():
    from app.services.workspace.sandbox_readiness_service import SandboxReadinessService

    class HostFeatureProbe:
        def status(self):
            return type(
                "Status",
                (),
                {
                    "available": True,
                    "provider": "windows_sandbox",
                    "reason": "verified",
                },
            )()

    snapshot = SandboxReadinessService(HostFeatureProbe()).snapshot()

    assert snapshot["success"] is True
    assert snapshot["status"] == "prerequisites_available"
    assert snapshot["execution_enabled"] is False
    assert snapshot["live_execution_verified"] is False
    assert snapshot["network"] == "configured_disabled_not_live_verified"
    assert snapshot["project_mount"] == "configured_read_only_not_live_verified"
