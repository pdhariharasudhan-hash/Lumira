from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.workspace.project_preview_service import ProjectPreviewService
from app.services.workspace.project_terminal_service import ProjectTerminalService


def test_preview_registration_persists_and_rejects_remote(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    version = root / "demo" / "v1"
    version.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    service = ProjectPreviewService(tmp_path / "previews.json")
    assert service.register("demo", "v1", "http://127.0.0.1:3000")["success"] is True
    assert service.get("demo", "v1")["preview"]["status"] == "registered"
    assert service.register("demo", "v1", "https://example.com:443")["success"] is False
    assert service.stop("demo", "v1")["preview"]["status"] == "stopped"


def test_preview_rejects_malformed_ports_and_authorities_without_raising(tmp_path, monkeypatch):
    project = tmp_path / "generated" / "demo" / "v1"
    project.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    service = ProjectPreviewService(tmp_path / "previews.json")

    for url in (
        "http://localhost:not-a-port",
        "http://localhost:65536",
        "http://localhost:0",
        "http://[invalid-ipv6:3000",
        "http://user:secret@localhost:3000",
        "http://localhost.evil:3000",
    ):
        result = service.register("demo", "v1", url)
        assert result["success"] is False
        assert result["code"] == "unsafe_preview_url"


class FakeSandbox:
    def __init__(self, available=False, reason="not_available"):
        self.available = available
        self.reason = reason

    def status(self):
        from app.services.workspace.container_sandbox_provider import SandboxStatus
        return SandboxStatus(self.available, "fake" if self.available else None, self.reason)


def test_terminal_requires_a_verified_execution_boundary():
    assert ProjectTerminalService.OS_SANDBOX_ENABLED is True
    service = ProjectTerminalService(sandbox=FakeSandbox(False))
    assert service._os_sandbox_verified() is False


def test_boolean_flag_cannot_enable_terminal_without_verified_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    monkeypatch.setenv("LUMIRA_ALLOW_UNSANDBOXED_PROJECT_COMMANDS", "1")
    service = ProjectTerminalService(tmp_path / "terminal.json", sandbox=FakeSandbox(False))

    result = service.run("demo", "v1", "pytest", trusted_project=True)

    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"


def test_terminal_command_allowlist_rejects_arbitrary_commands(tmp_path, monkeypatch):
    project = tmp_path / "generated" / "demo" / "v1"
    project.mkdir(parents=True)
    (project / "main.py").write_text("print('ok')", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    service = ProjectTerminalService(tmp_path / "terminal.json")
    assert "pytest" in service.list_commands()
    result = service.run("demo", "v1", "pytest")
    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"

    monkeypatch.setenv("LUMIRA_ALLOW_UNSANDBOXED_PROJECT_COMMANDS", "1")
    result = service.run("demo", "v1", "pytest", trusted_project=True)
    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"

    result = service.run("demo", "v1", "dir", trusted_project=True)
    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"


def test_terminal_service_refuses_execution_without_os_sandbox(tmp_path, monkeypatch):
    project = tmp_path / "generated" / "demo" / "v1"
    project.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMIRA_ALLOW_UNSANDBOXED_PROJECT_COMMANDS", "1")
    service = ProjectTerminalService(tmp_path / "terminal.json")
    result = service.run("demo", "v1", "compileall", trusted_project=True)
    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"


def test_terminal_route_requires_explicit_trust_confirmation():
    client = TestClient(app)
    response = client.post(
        "/projects/demo/v1/terminal/run",
        json={"project": "demo", "version": "v1", "command_id": "pytest"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == "project_execution_disabled"


def test_project_capability_routes_are_registered():
    client = TestClient(app)
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/projects/{project}/{version}/terminal/commands" in paths
    assert "/projects/{project}/{version}/preview" in paths



def test_terminal_never_calls_subprocess_when_sandbox_verification_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectTerminalService, "OS_SANDBOX_ENABLED", True)
    monkeypatch.setattr(ProjectTerminalService, "_os_sandbox_verified", lambda self: False)

    def unexpected_run(*args, **kwargs):
        raise AssertionError("subprocess.run must not be reached without verified isolation")

    monkeypatch.setattr(
        "app.services.workspace.project_terminal_service.subprocess.run",
        unexpected_run,
    )
    service = ProjectTerminalService(tmp_path / "terminal.json")

    result = service.run("demo", "v1", "pytest", trusted_project=True)

    assert result["success"] is False
    assert result["code"] == "project_execution_disabled"
