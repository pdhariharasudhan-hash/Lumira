import subprocess
from pathlib import Path

from app.services.workspace.container_sandbox_provider import ContainerSandboxProvider


class Result:
    def __init__(self, returncode=0, stdout="ok"):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_container_provider_reports_missing_runtime(monkeypatch):
    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.shutil.which", lambda name: None)
    status = ContainerSandboxProvider().status()
    assert status.available is False
    assert status.reason == "docker_not_installed"


def test_container_provider_verifies_runtime_without_shell(monkeypatch):
    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.shutil.which", lambda name: "/usr/bin/docker")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.subprocess.run", fake_run)
    status = ContainerSandboxProvider().status()
    assert status.available is True
    assert captured["kwargs"]["shell"] is False


def test_container_run_uses_restricted_boundary(monkeypatch, tmp_path):
    provider = ContainerSandboxProvider()
    monkeypatch.setattr(provider, "status", lambda: type("S", (), {"available": True, "reason": "verified"})())
    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.shutil.which", lambda name: "/usr/bin/docker")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.subprocess.run", fake_run)
    project = tmp_path / "project"
    project.mkdir()
    provider.run(("python", "-m", "pytest"), project, timeout=12)

    argv = captured["argv"]
    assert "--network" in argv and "none" in argv
    assert "--read-only" in argv
    assert "--cap-drop" in argv and "ALL" in argv
    assert captured["kwargs"]["shell"] is False
