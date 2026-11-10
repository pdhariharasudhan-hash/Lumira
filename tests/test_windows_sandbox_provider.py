import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.services.workspace.windows_sandbox_provider import WindowsSandboxProvider


class Result:
    returncode = 0
    stdout = "Deployment Image Servicing and Management tool\nState : Enabled"
    stderr = ""


def test_windows_sandbox_status_verifies_windows_feature(monkeypatch, tmp_path):
    executable = tmp_path / "WindowsSandbox.exe"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(WindowsSandboxProvider, "_sandbox_executable", staticmethod(lambda: executable))
    monkeypatch.setattr(WindowsSandboxProvider, "_dism_executable", staticmethod(lambda: "dism.exe"))
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr("app.services.workspace.windows_sandbox_provider.subprocess.run", fake_run)

    status = WindowsSandboxProvider().status()

    assert status.available is True
    assert status.provider == "windows_sandbox"
    assert status.reason == "verified"
    assert captured["argv"][-1] == "/FeatureName:Containers-DisposableClientVM"
    assert captured["kwargs"]["shell"] is False


def test_windows_sandbox_status_fails_when_feature_disabled(monkeypatch, tmp_path):
    executable = tmp_path / "WindowsSandbox.exe"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(WindowsSandboxProvider, "_sandbox_executable", staticmethod(lambda: executable))
    monkeypatch.setattr(WindowsSandboxProvider, "_dism_executable", staticmethod(lambda: "dism.exe"))
    monkeypatch.setattr(
        "app.services.workspace.windows_sandbox_provider.subprocess.run",
        lambda *args, **kwargs: type("R", (), {"returncode": 0, "stdout": "State : Disabled", "stderr": ""})(),
    )

    status = WindowsSandboxProvider().status()

    assert status.available is False
    assert status.reason == "windows_sandbox_feature_disabled"


def test_sandbox_memory_limit_rejects_values_below_windows_minimum():
    with pytest.raises(ValueError, match="between 2048"):
        WindowsSandboxProvider(memory_mb=1024)


def test_project_snapshot_excludes_secrets_and_development_state(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app").mkdir()
    (source / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (source / ".env").write_text("SECRET=value", encoding="utf-8")
    (source / "credentials.json").write_text("{}", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("private", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "private.py").write_text("private", encoding="utf-8")
    destination = tmp_path / "snapshot"

    WindowsSandboxProvider._copy_snapshot(source, destination)

    assert (destination / "app" / "main.py").is_file()
    assert not (destination / ".env").exists()
    assert not (destination / "credentials.json").exists()
    assert not (destination / ".git").exists()
    assert not (destination / ".venv").exists()


def test_project_snapshot_rejects_symbolic_links(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        (source / "escape.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic-link creation is unavailable on this host")

    with pytest.raises(ValueError, match="symbolic link or reparse"):
        WindowsSandboxProvider._validate_project_tree(source)


def test_wsb_configuration_disables_network_and_limits_shared_folders(tmp_path):
    control = tmp_path / "control"
    project = tmp_path / "project"
    output = tmp_path / "output"
    python_home = tmp_path / "python"
    python_site = tmp_path / "site"
    for path in (control, project, output, python_home, python_site):
        path.mkdir()
    config = tmp_path / "test.wsb"

    WindowsSandboxProvider._write_wsb(
        config, control, project, output, python_home, python_site, None, 2048
    )
    root = ET.parse(config).getroot()
    settings = {node.tag: node.text for node in root if node.tag != "MappedFolders" and node.tag != "LogonCommand"}
    assert settings["Networking"] == "Disable"
    assert settings["VGpu"] == "Disable"
    assert settings["ClipboardRedirection"] == "Disable"
    assert settings["ProtectedClient"] == "Enable"
    assert settings["MemoryInMB"] == "2048"
    mappings = root.find("MappedFolders").findall("MappedFolder")
    assert len(mappings) == 5
    by_guest = {item.findtext("SandboxFolder"): item.findtext("ReadOnly") for item in mappings}
    assert by_guest[r"C:\LumiraControl"] == "true"
    assert by_guest[r"C:\LumiraProject"] == "false"
    assert by_guest[r"C:\LumiraPython"] == "true"
    assert by_guest[r"C:\LumiraSitePackages"] == "true"
    assert by_guest[r"C:\LumiraResult"] == "false"


def test_safe_result_requires_guest_identity_nonce_and_bounded_output(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps({
            "nonce": "expected",
            "identity": r"guest\wdagutilityaccount",
            "exit_code": 0,
            "timed_out": False,
            "job_limits_applied": True,
            "stdout": "passed",
            "stderr": "",
        }),
        encoding="utf-8",
    )

    result = WindowsSandboxProvider._safe_result(result_path, "expected")

    assert result["exit_code"] == 0
    assert result["stdout"] == "passed"
    with pytest.raises(RuntimeError, match="correlated"):
        WindowsSandboxProvider._safe_result(result_path, "different")


def test_run_rejects_non_allowlisted_command_before_launch(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    provider = WindowsSandboxProvider()

    with pytest.raises(ValueError, match="not allowlisted"):
        provider.run(("powershell.exe", "-Command", "whoami"), project, timeout=5)


def test_run_rejects_timeout_outside_bounds(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    provider = WindowsSandboxProvider()

    with pytest.raises(ValueError, match="between 1 and 120"):
        provider.run(("python", "-m", "pytest", "-q"), project, timeout=121)



def test_host_folder_access_grants_interactive_user_inheritance(monkeypatch, tmp_path):
    calls = []
    responses = [
        type("Identity", (), {"returncode": 0, "stdout": "LAP\\Tester\n", "stderr": ""})(),
        type("Grant", (), {"returncode": 0, "stdout": "processed", "stderr": ""})(),
    ]
    monkeypatch.setattr(
        "app.services.workspace.windows_sandbox_provider.shutil.which",
        lambda name: name,
    )

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(
        "app.services.workspace.windows_sandbox_provider.subprocess.run",
        fake_run,
    )

    WindowsSandboxProvider._grant_host_folder_access(tmp_path)

    assert calls[0][0] == ["whoami.exe"]
    assert calls[1][0][1:] == [
        str(tmp_path), "/inheritance:e", "/grant", "LAP\\Tester:(OI)(CI)F", "/T", "/C"
    ]
    assert all(call[1]["shell"] is False for call in calls)


def test_host_folder_access_fails_closed_when_acl_update_fails(monkeypatch, tmp_path):
    responses = [
        type("Identity", (), {"returncode": 0, "stdout": "LAP\\Tester", "stderr": ""})(),
        type("Grant", (), {"returncode": 1, "stdout": "", "stderr": "denied"})(),
    ]
    monkeypatch.setattr(
        "app.services.workspace.windows_sandbox_provider.shutil.which",
        lambda name: name,
    )
    monkeypatch.setattr(
        "app.services.workspace.windows_sandbox_provider.subprocess.run",
        lambda *args, **kwargs: responses.pop(0),
    )

    with pytest.raises(RuntimeError, match="sandbox_temp_acl_setup_failed"):
        WindowsSandboxProvider._grant_host_folder_access(tmp_path)



def test_safe_result_rejects_unapplied_resource_limits(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps({
            "nonce": "expected",
            "identity": r"guest\wdagutilityaccount",
            "exit_code": 0,
            "timed_out": False,
            "job_limits_applied": False,
            "stdout": "",
            "stderr": "",
        }),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="resource_limits_unverified"):
        WindowsSandboxProvider._safe_result(result_path, "expected")


def test_guest_script_contains_cpu_memory_and_process_limits():
    script = WindowsSandboxProvider._guest_script()

    assert "cpu.CpuRate = 5000" in script
    assert "ActiveProcessLimit = 64" in script
    assert "768UL * 1024UL * 1024UL" in script
    assert "1024UL * 1024UL * 1024UL" in script
    assert "0x2000" in script



def test_process_lock_rejects_a_second_concurrent_runner(tmp_path):
    lock_path = tmp_path / "sandbox.lock"
    first = WindowsSandboxProvider._acquire_process_lock(lock_path)
    try:
        with pytest.raises(RuntimeError, match="windows_sandbox_busy"):
            WindowsSandboxProvider._acquire_process_lock(lock_path)
    finally:
        WindowsSandboxProvider._release_process_lock(first)

    second = WindowsSandboxProvider._acquire_process_lock(lock_path)
    WindowsSandboxProvider._release_process_lock(second)
