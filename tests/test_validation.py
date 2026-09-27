from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.history.pipeline_history_service import PipelineHistoryService
from app.services.memory.memory_service import MemoryService
from app.services.projects.project_writer import ProjectWriter
from app.services.sessions.session_manager_service import SessionManagerService


def test_brain_route_builds_valid_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/brain", json={"input": "Build a FastAPI expense API with authentication"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["stage"] == "complete"
    assert payload["data"]["state"]["goal"]["primary_goal"]
    session_id = payload["data"]["state"]["execution_context"]["session_id"]
    assert client.get(f"/sessions/{session_id}").status_code == 200
    assert client.get(f"/brain/state/{session_id}").json()["cognitive_state"]["goal"]
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
    session_id = mode["session_id"]

    created = client.post("/command", json={"input": "Create a FastAPI expense API.", "session_id": session_id}).json()
    assert created["result"]["project_name"] == "expense_api"
    assert created["context"]["active_project"] == "expense_api"
    assert created["brain"]["state"]["mode"]["active_mode"] == "builder"

    auth = client.post("/command", json={"input": "Add JWT authentication.", "session_id": session_id}).json()
    tests = client.post("/command", json={"input": "Add tests.", "session_id": session_id}).json()
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
    memory = MemoryService()
    goal = memory.create_goal("needle durable goal", project_id="needle_project")
    memory.record_decision(
        "needle decision",
        "explicit choice",
        project_id="needle_project",
        goal_id=goal["goal_id"],
    )
    experience = memory.record_experience(
        "success",
        "needle verified experience",
        "needle workflow passed",
        project_id="needle_project",
        goal_id=goal["goal_id"],
        lessons=["needle pattern was verified with the project test suite."],
        verified=True,
    )
    memory.consolidate_learning(experience)
    session = SessionManagerService().create_session(project_id="needle_project")
    SessionManagerService().append_message(session["session_id"], "user", "needle conversation")
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
    assert results["sessions"]
    assert results["conversations"]
    assert results["goals"]
    assert results["decisions"]
    assert results["experiences"]
    assert results["learning"]


def test_session_restart_recovers_project_decision_and_scoped_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first_process = TestClient(app)

    created = first_process.post(
        "/command",
        json={"input": "Build a FastAPI expense API."},
    ).json()
    session_id = created["session_id"]
    assert created["result"]["project_name"] == "expense_api"

    authenticated = first_process.post(
        "/command",
        json={"input": "Add authentication.", "session_id": session_id},
    ).json()
    assert authenticated["result"]["success"] is True
    version_after_auth = authenticated["context"]["active_version"]

    remembered = first_process.post(
        "/command",
        json={
            "input": "Remember that this project should use JWT authentication.",
            "session_id": session_id,
        },
    ).json()
    assert remembered["result"]["success"] is True
    assert remembered["result"]["decision"]["project_id"] == "expense_api"

    MemoryService().record_decision(
        "Use an unrelated datastore",
        "Different project requirement",
        project_id="unrelated_project",
    )

    # A new TestClient and fresh services model a backend process restart.
    restarted_process = TestClient(app)
    recovered = restarted_process.get(f"/sessions/{session_id}")
    assert recovered.status_code == 200
    session = recovered.json()
    assert session["active_project"] == "expense_api"
    assert session["active_version"] == version_after_auth
    assert session["current_goal"]
    assert session["cognitive_state_id"]
    assert len(session["recent_messages"]) >= 6
    brain_state = restarted_process.get(f"/brain/state/{session_id}").json()
    assert brain_state["cognitive_state"]["execution_status"] == "completed"
    assert brain_state["context_snapshot"][0]["active_project"] == "expense_api"

    relevant_memory = restarted_process.get(
        "/memory/relevant",
        params={"q": "JWT authentication", "session_id": session_id},
    ).json()["data"]
    assert any("JWT authentication" in item["decision"] for item in relevant_memory["decisions"])
    assert relevant_memory["learning_records"]
    project_goals = restarted_process.get("/goals", params={"project_id": "expense_api"}).json()["goals"]
    assert any(goal["goal_id"] == session["goal_id"] for goal in project_goals)

    resumed = restarted_process.post(
        "/command",
        json={"input": "Continue the expense API.", "session_id": session_id},
    ).json()
    decisions = resumed["brain"]["state"]["relevant_memory"]["decisions"]
    assert any("JWT authentication" in item["decision"] for item in decisions)
    assert all(item["project_id"] != "unrelated_project" for item in decisions)
    assert resumed["context"]["active_project"] == "expense_api"

    dashboard = restarted_process.post(
        "/command",
        json={"input": "Add a dashboard.", "session_id": session_id},
    ).json()
    assert dashboard["result"]["success"] is True
    assert "dashboard" in dashboard["result"]["new_idea"].lower()
    assert "generated/expense_api/" in dashboard["result"]["saved_to"].replace("\\", "/")
    assert dashboard["context"]["active_project"] == "expense_api"
    assert dashboard["context"]["active_version"] != version_after_auth


def test_session_lifecycle_api_and_ambiguous_reference(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    created = client.post("/sessions", json={"workspace_id": "test-workspace"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    from app.services.sessions.session_manager_service import SessionManagerService

    manager = SessionManagerService()
    manager.add_reference(session_id, "expense_api")
    manager.add_reference(session_id, "dashboard_app")
    ambiguous = client.post(
        "/command",
        json={"input": "Make it dark.", "session_id": session_id},
    )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["clarification_required"] is True
    assert ambiguous.json()["reference_resolution"]["status"] == "ambiguous"

    paused = client.post(f"/sessions/{session_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    resumed = client.post(f"/sessions/{session_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    closed = client.post(f"/sessions/{session_id}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert client.post(f"/sessions/{session_id}/pause").status_code == 409
    assert client.post(f"/sessions/{session_id}/resume").status_code == 409
    rejected = client.post(
        "/command",
        json={"input": "Continue the project.", "session_id": session_id},
    )
    assert rejected.status_code == 409


def test_goal_api_creates_lists_and_updates_durable_goal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    created = client.post(
        "/goals",
        json={
            "title": "Expense API",
            "objective": "Ship JWT-secured expense management",
            "project_id": "expense_api",
            "parent_goal_id": "portfolio-root",
            "priority": "high",
        },
    )
    assert created.status_code == 200
    goal_id = created.json()["goal_id"]

    updated = client.patch(
        f"/goals/{goal_id}",
        json={"status": "in_progress", "progress": 0.4, "milestones": [{"title": "Authentication", "complete": True}]},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    assert updated.json()["progress"] == 0.4

    listing = client.get("/goals", params={"project_id": "expense_api", "status": "in_progress"})
    assert listing.status_code == 200
    assert [goal["goal_id"] for goal in listing.json()["goals"]] == [goal_id]


def test_missing_memory_key_keeps_not_found_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).get("/memory/not-a-known-key")
    assert response.status_code == 404


def test_artifact_api_supports_crud_and_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    created = client.post(
        "/artifacts",
        json={
            "type": "exports",
            "content": "exported report",
            "source": "test",
            "extension": "md",
        },
    )
    assert created.status_code == 201
    artifact = created.json()["artifact"]
    artifact_id = artifact["artifact_id"]

    listed = client.get("/artifacts", params={"artifact_type": "exports"})
    assert listed.status_code == 200
    assert listed.json()["artifacts"][0]["artifact_id"] == artifact_id
    assert client.get(f"/artifacts/{artifact_id}").json()["artifact"]["source"] == "test"
    assert client.get(f"/artifacts/{artifact_id}/content").text == "exported report"
    assert client.get("/artifacts/stats").json()["stats"]["total"] == 1

    deleted = client.delete(f"/artifacts/{artifact_id}")
    assert deleted.status_code == 200
    assert client.get(f"/artifacts/{artifact_id}").status_code == 404
