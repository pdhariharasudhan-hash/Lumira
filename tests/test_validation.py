from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.history.pipeline_history_service import PipelineHistoryService
from app.services.memory.memory_service import MemoryService
from app.services.projects.project_writer import ProjectWriter


def test_brain_route_builds_valid_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/brain", json={"input": "Build a FastAPI expense API with authentication"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["stage"] == "complete"
    assert payload["data"]["state"]["goal"]["primary_goal"]
    assert [entry["module"] for entry in payload["data"]["trace"]] == [
        "conversation",
        "goal",
        "objective",
        "context",
        "constraints",
        "reasoning",
        "decision",
        "planner",
        "prediction",
        "verification",
        "reflection",
        "learning",
    ]


def test_command_route_parses_request(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/command", json={"input": "Build a FastAPI expense API with authentication"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["parsed"]["success"] is True
    assert payload["brain"]["state"]["goal"]["primary_goal"]
    assert payload["brain"]["state"]["mode"]["active_mode"] == "builder"
    assert [entry["module"] for entry in payload["brain"]["trace"]][-3:] == [
        "verification",
        "reflection",
        "learning",
    ]

    generated_path = Path(payload["result"]["saved_path"])
    generated_source = (generated_path / "main.py").read_text(encoding="utf-8")
    generated_namespace = {}
    exec(compile(generated_source, str(generated_path / "main.py"), "exec"), generated_namespace)
    generated_client = TestClient(generated_namespace["app"])

    registered = generated_client.post(
        "/register",
        params={"username": "owner", "password": "correct horse"},
    )
    assert registered.status_code == 200
    login = generated_client.post(
        "/login",
        params={"username": "owner", "password": "correct horse"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    assert generated_client.get("/expenses").status_code == 401
    assert generated_client.delete("/expenses/0").status_code == 401
    authorized = generated_client.get(
        "/expenses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authorized.status_code == 200
    assert authorized.json() == []


def test_builder_mode_project_and_followups_keep_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    mode = client.post("/command", json={"input": "Lumira, enter Builder Mode."}).json()
    assert mode["result"]["mode"] == "builder"

    created = client.post("/command", json={"input": "Create a FastAPI expense API."}).json()
    assert created["result"]["project_name"] == "expense_api"
    assert created["context"]["active_project"] == "expense_api"
    assert created["brain"]["state"]["mode"]["active_mode"] == "builder"

    auth = client.post("/command", json={"input": "Add JWT authentication."}).json()
    tests = client.post("/command", json={"input": "Add tests."}).json()
    assert auth["result"]["success"] is True
    assert tests["result"]["success"] is True
    assert tests["context"]["active_project"] == "expense_api"
    assert tests["context"]["active_version"] != created["context"]["active_version"]
    assert tests["result"]["instructions"] == [
        "add jwt authentication.",
        "add tests.",
    ]
    assert "generated/expense_api/" in tests["result"]["saved_to"].replace("\\", "/")


def test_voice_upload_persists_audio_and_reports_missing_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    uploaded = client.post(
        "/voice/upload",
        files={"audio": ("sample.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")},
    )
    assert uploaded.status_code == 200
    artifact = uploaded.json()["data"]["artifact"]
    assert artifact["type"] == "audio"
    assert (tmp_path / artifact["file"]).is_file()

    transcript = client.post(
        "/voice/transcript",
        json={"artifact_id": artifact["artifact_id"]},
    )
    assert transcript.status_code == 501
    assert transcript.json()["detail"]["code"] == "provider_unavailable"


def test_unified_search_finds_records_in_all_supported_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    ProjectWriter().save(
        "needle_project",
        {"main.py": "app = True"},
        {"idea": "needle project API", "entity": "needle", "project_type": "api"},
    )
    ArtifactManagerService().create_artifact(
        "diagrams",
        "diagram contents",
        "needle artifact source",
    )
    MemoryService().add_feature_history({"feature": "needle feature"})
    PipelineHistoryService().record(
        execution_id="needle-execution",
        request_id="needle-request",
        session_id="search-test",
        project_id="needle_project",
        user_input="needle pipeline input",
        success=True,
        trace=[],
    )

    response = client.get("/search", params={"q": "needle"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results["projects"]
    assert results["artifacts"]
    assert results["memory"]
    assert results["feature_history"]
    assert results["pipeline_history"]
