from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.routes.session_insights as route


def session(session_id="s1", status="active", **updates):
    now = datetime.now(UTC).isoformat()
    value = {
        "session_id": session_id, "conversation_id": f"c-{session_id}", "workspace_id": "default",
        "project_id": "lumira", "active_project": "lumira", "active_version": "v1",
        "active_mode": "operations", "current_goal": "Build features", "goal_id": "g1",
        "last_command": "plan work", "status": status, "created_at": now, "updated_at": now,
        "conversation": {"summary": "Project session", "current_topic": "Lumira", "active_objective": "Ship",
                        "pending_questions": [], "recent_references": [], "language_context": "en"},
        "recent_messages": [{"role": "user", "content": "Build Lumira", "created_at": now}],
        "context_snapshots": [{"at": now}], "schema_version": 1,
    }
    value.update(updates)
    return value


class FakeSessions:
    def __init__(self, records):
        self.records = records

    def list_sessions(self, limit=50):
        return self.records[:limit]

    def get_session(self, session_id):
        return next((item for item in self.records if item["session_id"] == session_id), None)


class FakeWorkflows:
    def list_workflows(self, *, session_id, limit=50):
        return [{"workflow_id": "wf1", "session_id": session_id}][:limit]


@pytest.fixture
def fake_data(monkeypatch):
    records = [
        session("active-session"),
        session("paused-session", "paused", context_snapshots=[]),
        session("closed-session", "closed"),
    ]
    monkeypatch.setattr(route, "SessionManagerService", lambda: FakeSessions(records))
    monkeypatch.setattr(route, "WorkItemService", FakeWorkflows)
    return records


def test_summary_counts_statuses_and_recovery_snapshots(fake_data):
    result = route.session_summary()
    assert result["status_counts"] == {"active": 1, "paused": 1, "closed": 1}
    assert "active-session" in result["sessions_with_recovery_snapshots"]


def test_search_returns_metadata_not_full_message_bodies(fake_data):
    result = route.search_sessions(q="active-session")
    assert result["total"] == 1
    assert result["sessions"][0]["session_id"] == "active-session"
    assert "recent_messages" not in result["sessions"][0]


def test_export_omits_messages_by_default(fake_data):
    result = route.export_sessions(limit=2)
    assert result["count"] == 2
    assert all("recent_messages" not in item for item in result["sessions"])


def test_export_redacts_secrets_when_messages_are_included(fake_data):
    fake_data[0]["recent_messages"] = [{"role": "user", "content": "api_key=super-secret"}]
    result = route.export_sessions(include_recent_messages=True)
    exported = next(item for item in result["sessions"] if item["session_id"] == "active-session")
    assert "super-secret" not in str(exported)


def test_session_health_reports_recovery_and_context(fake_data):
    result = route.session_health("active-session")
    assert result["recovery_available"] is True
    assert result["context"]["has_current_goal"] is True
    assert result["recent_message_count"] == 1


def test_related_workflows_requires_existing_session(fake_data):
    result = route.session_related_workflows("active-session")
    assert result["count"] == 1
    with pytest.raises(HTTPException) as error:
        route.session_related_workflows("missing")
    assert error.value.status_code == 404


def test_search_rejects_whitespace_query(fake_data):
    with pytest.raises(HTTPException) as error:
        route.search_sessions(q="   ")
    assert error.value.status_code == 422
