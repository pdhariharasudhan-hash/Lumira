import json

import pytest

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.sessions.session_manager_service import (
    MAX_RECENT_MESSAGES,
    SessionManagerService,
)


def test_session_create_reload_resume_and_bounded_messages(tmp_path):
    path = tmp_path / "sessions.json"
    manager = SessionManagerService(path)
    session = manager.create_session(workspace_id="workspace-a")

    for index in range(MAX_RECENT_MESSAGES + 3):
        manager.append_message(session["session_id"], "user", f"request {index}")

    manager.pause_session(session["session_id"])
    resumed = SessionManagerService(path).resume_session(session["session_id"])

    assert resumed["status"] == "active"
    assert len(resumed["recent_messages"]) == MAX_RECENT_MESSAGES
    assert resumed["recent_messages"][0]["content"] == "request 3"
    assert resumed["workspace_id"] == "workspace-a"


def test_session_redacts_credentials_and_rejects_unknown_schema(tmp_path):
    path = tmp_path / "sessions.json"
    manager = SessionManagerService(path)
    session = manager.create_session()
    manager.append_message(
        session["session_id"],
        "user",
        "Use api_key=top secret phrase with Bearer abc.def.ghi",
    )
    content = manager.get_session(session["session_id"])["recent_messages"][0]["content"]
    assert "topsecret" not in content
    assert "secret phrase" not in content
    assert "abc.def.ghi" not in content

    path.write_text(json.dumps({"schema_version": 88, "sessions": []}), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="Unsupported session schema"):
        manager.list_sessions()


def test_incomplete_session_record_fails_without_being_repaired(tmp_path):
    path = tmp_path / "sessions.json"
    manager = SessionManagerService(path)
    session = manager.create_session()
    document = json.loads(path.read_text(encoding="utf-8"))
    document["sessions"][0].pop("conversation_id")
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PersistenceIntegrityError, match="incomplete"):
        manager.get_session(session["session_id"])
    assert "conversation_id" not in json.loads(path.read_text(encoding="utf-8"))["sessions"][0]


def test_memory_records_consolidation_and_project_scoped_retrieval(tmp_path):
    memory = MemoryService(str(tmp_path / "project_memory.json"))
    goal = memory.create_goal(
        "Build expense API",
        "JWT-enabled expense service",
        project_id="expense_api",
    )
    decision = memory.record_decision(
        "Use JWT authentication",
        "Explicit user request",
        project_id="expense_api",
        goal_id=goal["goal_id"],
        constraints=["No external identity provider configured"],
        confidence=0.9,
    )
    experience = memory.record_experience(
        "success",
        "Generated expense routes were checked with authenticated and unauthenticated requests.",
        "Protected routes rejected missing tokens and accepted a valid token.",
        project_id="expense_api",
        goal_id=goal["goal_id"],
        lessons=["Verify every generated route for both missing and valid bearer credentials."],
        source_run="run-1",
        verified=True,
    )
    learning = memory.consolidate_learning(experience)

    relevant = memory.retrieve_relevant("continue expense API", project_id="expense_api")
    unrelated = memory.retrieve_relevant("continue expense API", project_id="other_api")

    assert relevant["goals"][0]["goal_id"] == goal["goal_id"]
    assert relevant["decisions"][0]["decision_id"] == decision["decision_id"]
    assert relevant["experiences"][0]["experience_id"] == experience["experience_id"]
    assert relevant["learning_records"][0]["learning_id"] == learning["learning_id"]
    assert unrelated == {"goals": [], "decisions": [], "experiences": [], "learning_records": []}
    assert all(record["schema_version"] == 1 for records in relevant.values() for record in records)


def test_memory_does_not_promote_transient_or_unverified_lessons(tmp_path):
    memory = MemoryService(str(tmp_path / "project_memory.json"))
    assert memory.consolidate_learning({
        "type": "workflow",
        "lessons": ["Completed"],
    }) is None
    assert memory.consolidate_learning({
        "type": "success",
        "verified": False,
        "lessons": ["A long enough lesson that still has no verified outcome."],
    }) is None
    assert memory.get_all()["learning_records"] == []


def test_corrupt_memory_is_preserved_and_reported(tmp_path):
    path = tmp_path / "project_memory.json"
    path.write_text("{not json", encoding="utf-8")
    memory = MemoryService(str(path))

    with pytest.raises(MemoryValidationError, match="valid JSON"):
        memory.get_all()

    assert path.read_text(encoding="utf-8") == "{not json"


def test_memory_rejects_unknown_schema_without_reinterpretation(tmp_path):
    path = tmp_path / "project_memory.json"
    path.write_text(json.dumps({"schema_version": 45, "goals": []}), encoding="utf-8")
    memory = MemoryService(str(path))

    with pytest.raises(MemoryValidationError, match="Unsupported memory schema"):
        memory.get_all()

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 45


def test_memory_migrates_legacy_v0_and_preserves_unknown_fields(tmp_path):
    path = tmp_path / "project_memory.json"
    path.write_text(json.dumps({"name": "legacy", "custom_legacy_key": {"keep": True}}), encoding="utf-8")

    memory = MemoryService(str(path))
    migrated = memory.get_all()

    assert migrated["schema_version"] == 1
    assert migrated["name"] == "legacy"
    assert migrated["custom_legacy_key"] == {"keep": True}
    assert migrated["learning_records"] == []
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_generic_memory_writes_redact_or_reject_credentials(tmp_path):
    memory = MemoryService(str(tmp_path / "project_memory.json"))
    memory.update(
        "safe_preferences",
        {"api_key": "do-not-store", "note": "password=also-secret"},
    )

    stored = memory.get_value("safe_preferences")
    assert stored == {
        "api_key": "[REDACTED]",
        "note": "password=[REDACTED]",
    }
    with pytest.raises(MemoryValidationError, match="credential-like"):
        memory.update("access_token", "do-not-store")


def test_cognitive_memory_rejects_corrupt_and_unknown_schema(tmp_path):
    memory = MemoryService(str(tmp_path / "project_memory.json"))
    path = tmp_path / "cognitive_memory.json"
    path.write_text(json.dumps({"schema_version": 8, "goals": []}), encoding="utf-8")

    with pytest.raises(MemoryValidationError, match="Unsupported cognitive memory schema"):
        memory.retrieve_relevant("expense")
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 8

    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(MemoryValidationError, match="valid JSON"):
        memory.retrieve_relevant("expense")
    assert path.read_text(encoding="utf-8") == "{broken"
