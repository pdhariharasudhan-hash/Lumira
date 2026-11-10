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


def test_container_provider_blocks_when_required_image_is_missing(monkeypatch):
    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.shutil.which", lambda name: "/usr/bin/docker")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[1:3] == ["image", "inspect"]:
            return Result(returncode=1, stdout="")
        return Result()

    monkeypatch.setattr("app.services.workspace.container_sandbox_provider.subprocess.run", fake_run)
    status = ContainerSandboxProvider().status()

    assert status.available is False
    assert status.provider == "docker"
    assert status.reason == "sandbox_image_unavailable"
    assert len(calls) == 2
    assert all(call[1]["shell"] is False for call in calls)


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
    assert "--ipc" in argv and "none" in argv
    assert "--read-only" in argv
    assert "--user" in argv and "65534:65534" in argv
    assert "--cap-drop" in argv and "ALL" in argv
    assert "--pids-limit" in argv and "128" in argv
    assert "--memory" in argv and "1g" in argv
    assert "--security-opt" in argv and "no-new-privileges" in argv
    assert "--ulimit" in argv and "nofile=256:256" in argv
    assert "--tmpfs" in argv and "nosuid" in argv[argv.index("--tmpfs") + 1]
    assert "-v" in argv and argv[argv.index("-v") + 1].endswith(":/workspace:ro")
    assert captured["kwargs"]["shell"] is False
