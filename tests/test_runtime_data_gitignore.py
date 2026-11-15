from __future__ import annotations

import shutil
import subprocess

import pytest


def _repo_root() -> str:
    return str(__import__("pathlib").Path(__file__).resolve().parents[1])


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is unavailable")
def test_runtime_and_personal_output_paths_are_ignored():
    candidates = [
        "memory/new-session.json",
        "data/new-memory.json",
        "artifacts/research/new-report.md",
        "generated/new-project/main.py",
        "app.db",
        "project_memory.json",
        "final-audit-result.json",
        ".agents/memory/session.md",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        input=b"\0".join(path.encode("utf-8") for path in candidates) + b"\0",
        capture_output=True,
        cwd=_repo_root(),
        check=False,
    )

    assert result.returncode == 0
    assert {path.decode("utf-8") for path in result.stdout.split(b"\0") if path} == set(candidates)


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is unavailable")
def test_personal_runtime_stores_are_not_tracked():
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--",
            "memory",
            "data",
            "artifacts",
            "generated",
            "app.db",
            "project_memory.json",
            "final-audit-result.json",
            ".agents/memory",
        ],
        text=True,
        capture_output=True,
        cwd=_repo_root(),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
