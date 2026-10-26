from __future__ import annotations

from app.services.autonomous_development.worker.openai_compatible_provider import (
    OpenAICompatibleDevelopmentProvider,
)
from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.autonomous_development.worker.development_worker import DevelopmentWorker


def test_provider_fails_closed_when_authoritative_file_exceeds_budget(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "max_provider_files": 6,
            "max_file_characters": 100,
            "max_context_characters": 1000,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("provider must not be called with incomplete source context")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        forbidden_request,
    )
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )

    result = provider.generate_changes(
        goal="Update the source file",
        workspace="/workspace",
        files=[
            {
                "path": "module.py",
                "content": "x" * 101,
            }
        ],
    )

    assert result["success"] is False
    assert result["code"] == "provider_file_too_large"
    assert result["file"] == "module.py"
    assert result["file_character_limit"] == 100


def test_provider_defers_when_resource_pressure_is_critical(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"resource_pressure": "critical"},
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("provider must not be called under critical memory pressure")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        forbidden_request,
    )
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )

    result = provider.generate_changes(
        goal="Make a small change",
        workspace="/workspace",
        files=[],
    )

    assert result["success"] is False
    assert result["state"] == "deferred"
    assert result["code"] == "resource_pressure_critical"


def test_worker_blocks_oversized_source_instead_of_truncating(tmp_path, monkeypatch):
    source = tmp_path / "app" / "sample.py"
    source.parent.mkdir(parents=True)
    source.write_text("x" * 12001, encoding="utf-8")

    worker = DevelopmentWorker(tmp_path)
    monkeypatch.setattr(
        worker,
        "inspect",
        lambda: {
            "workspace": str(tmp_path),
            "files": ["app/sample.py"],
            "audit_findings": [],
        },
    )

    result = worker.generate_changes(
        goal="Update sample module",
        iteration=1,
    )

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "provider_file_too_large"
    assert result["file"] == "app/sample.py"


def test_worker_blocks_total_context_overflow_instead_of_truncating(tmp_path, monkeypatch):
    relative_files = [
        "app/sample_one.py",
        "app/sample_two.py",
        "app/sample_three.py",
    ]
    for relative_path in relative_files:
        source = tmp_path / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("x" * 11000, encoding="utf-8")

    worker = DevelopmentWorker(tmp_path)
    monkeypatch.setattr(
        worker,
        "inspect",
        lambda: {
            "workspace": str(tmp_path),
            "files": relative_files,
            "audit_findings": [],
        },
    )

    result = worker.generate_changes(
        goal="Update sample modules",
        iteration=1,
    )

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "provider_context_too_large"
    assert result["context_character_limit"] == 30000


def test_provider_rejects_excess_source_files_instead_of_omitting_them(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "max_provider_files": 1,
            "max_file_characters": 100,
            "max_context_characters": 1000,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("provider must not be called with silently omitted source files")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_request)
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )

    result = provider.generate_changes(
        goal="Update both files",
        workspace="/workspace",
        files=[
            {"path": "one.py", "content": "one"},
            {"path": "two.py", "content": "two"},
        ],
    )

    assert result["success"] is False
    assert result["code"] == "provider_file_count_exceeded"
    assert result["file_count"] == 2
    assert result["file_count_limit"] == 1


def test_provider_rejects_malformed_source_file_entry(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "max_provider_files": 6,
            "max_file_characters": 100,
            "max_context_characters": 1000,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("provider must not be called with malformed source context")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_request)
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )

    result = provider.generate_changes(
        goal="Update the source",
        workspace="/workspace",
        files=[{"path": "one.py", "content": "one"}, None],
    )

    assert result["success"] is False
    assert result["code"] == "provider_invalid_source_file"
    assert result["file_index"] == 1
