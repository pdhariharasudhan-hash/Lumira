import json

import pytest

from app.routes import code as code_route
from app.routes import execute as execute_route
from app.routes.code import CodeRequest
from app.routes.execute import ExecuteRequest
from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.code.code_service import CodeService
from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.projects.project_paths import resolve_project_path


def test_code_service_refuses_missing_or_unaccepted_execution_plan():
    missing = CodeService().generate("Build an expense API", {})
    rejected = CodeService().generate(
        "Build an expense API",
        {"status": "refine", "execution_order": ["step_1"], "task_steps": ["step_1"]},
    )

    assert missing["status"] == "reject"
    assert missing["files"] == {}
    assert rejected["status"] == "reject"
    assert "accepted execution plan" in rejected["error"]


def test_code_endpoint_does_not_generate_after_execution_refines(monkeypatch):
    called = False

    def unexpected_generate(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("code generation must stop after an unaccepted execution plan")

    monkeypatch.setattr(code_route.code_service, "generate", unexpected_generate)
    response = code_route.code_endpoint(
        CodeRequest(input="Build an expense API", execute={"status": "refine"})
    )

    assert response["success"] is False
    assert response["status"] == "refine"
    assert response["data"]["result"]["files"] == {}
    assert called is False


def test_code_endpoint_validates_generated_source_before_accepting(monkeypatch):
    monkeypatch.setattr(
        code_route.code_service,
        "generate",
        lambda *_: {
            "code_target": "expense_api",
            "files": {"main.py": "def broken(:", "requirements.txt": "fastapi"},
            "file_plan": ["main.py", "requirements.txt"],
            "implementation_steps": ["generate"],
            "test_steps": ["run"],
            "priority": "high",
            "status": "accept",
        },
    )
    response = code_route.code_endpoint(
        CodeRequest(
            input="Build an expense API",
            execute={"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]},
        )
    )

    assert response["success"] is False
    assert response["status"] == "refine"
    assert response["data"]["result"]["validation"]["valid"] is False


def test_execute_endpoint_does_not_relabel_invalid_result_as_success(monkeypatch):
    monkeypatch.setattr(execute_route.execute_service, "execute", lambda *_: {"status": "accept"})

    response = execute_route.execute_endpoint(
        ExecuteRequest(input="Build an expense API", builder={"status": "accept"})
    )

    assert response["success"] is False
    assert response["status"] == "refine"
    assert response["data"]["result"]["status"] == "refine"


def test_artifact_index_corruption_is_reported_and_preserved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    index_path = tmp_path / "memory" / "artifact_index.json"
    index_path.parent.mkdir()
    index_path.write_text("{broken", encoding="utf-8")
    manager = ArtifactManagerService()

    with pytest.raises(PersistenceIntegrityError, match="valid JSON"):
        manager.get_all_artifacts()

    assert index_path.read_text(encoding="utf-8") == "{broken"


def test_artifact_deletion_rejects_index_path_escape_without_mutating_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    index_path = tmp_path / "memory" / "artifact_index.json"
    index_path.parent.mkdir()
    document = {
        "artifacts": [
            {
                "artifact_id": "artifact-1",
                "type": "exports",
                "source": "test",
                "file": str(tmp_path / "outside.txt"),
                "timestamp": "now",
            }
        ]
    }
    index_path.write_text(json.dumps(document), encoding="utf-8")
    manager = ArtifactManagerService()

    with pytest.raises(ValueError, match="outside the artifact store"):
        manager.delete_artifact("artifact-1")

    assert json.loads(index_path.read_text(encoding="utf-8")) == document


def test_project_path_resolver_rejects_traversal_and_invalid_versions(tmp_path):
    assert resolve_project_path("../app", "v1", root=tmp_path) is None
    assert resolve_project_path("expense_api", "../../memory", root=tmp_path) is None
    assert resolve_project_path("expense_api", "v1", "../../secret.txt", root=tmp_path) is None


def test_memory_search_and_session_api_payloads_are_bounded(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    oversized_memory = client.post(
        "/memory",
        json={"key": "oversized", "value": "x" * 250001},
    )
    assert oversized_memory.status_code == 400
    assert client.get("/search", params={"q": "x" * 501}).status_code == 422
    assert client.get("/sessions", params={"limit": 201}).status_code == 422
