from fastapi import HTTPException

from app.routes import intelligence
from app.services.language.language_detection_service import LanguageDetectionService


def test_analyze_endpoint_returns_intent_language_and_mode_without_execution():
    result = intelligence.analyze_input(intelligence.AnalyzeRequest(text="build my project"))
    assert result["success"] is True
    assert result["intent"] == "build"
    assert result["language"]["language"] == "en"
    assert "selected_mode" in result["mode"]
    assert result["execution_started"] is False


def test_language_detection_recognizes_common_romanized_tamil_and_mixed_input():
    detector = LanguageDetectionService()

    assert detector.detect("naan epdi")["language"] == "ta"
    assert detector.detect("naan build project pannunga")["language"] == "ta-en"
    assert detector.detect("please konjam help pannunga")["language"] == "ta-en"
    assert detector.detect("build my project")["language"] == "en"
    assert detector.detect("நான் project build செய்ய வேண்டும்")["language"] == "ta-en"


def test_history_endpoint_returns_filtered_pipeline_records(monkeypatch):
    class FakeHistory:
        def query(self, **kwargs):
            assert kwargs == {
                "session_id": "session-1",
                "project_id": "project-1",
                "success": False,
                "limit": 5,
                "newest_first": True,
            }
            return [{"execution_id": "run-1", "success": False}]

        def stats(self):
            return {"total": 4, "failed": 1}

    monkeypatch.setattr(intelligence, "PipelineHistoryService", FakeHistory)
    result = intelligence.intelligence_history(
        session_id="session-1", project_id="project-1", success=False, limit=5
    )
    assert result["count"] == 1
    assert result["history"][0]["execution_id"] == "run-1"
    assert result["stats"]["failed"] == 1


def test_mode_list_exposes_registered_modes():
    result = intelligence.list_modes()
    identifiers = {item["id"] for item in result["modes"]}
    assert result["success"] is True
    assert result["count"] >= 8
    assert {"personal", "builder", "research", "operations"}.issubset(identifiers)


def test_mode_selection_persists_to_active_session(monkeypatch):
    class FakeSessions:
        def get_session(self, session_id):
            return {"session_id": session_id, "status": "active"}

        def update_context(self, session_id, **values):
            return {"session_id": session_id, **values}

    monkeypatch.setattr(intelligence, "SessionManagerService", FakeSessions)
    result = intelligence.select_mode(
        intelligence.SelectModeRequest(session_id="session-1", mode_id="builder")
    )
    assert result["success"] is True
    assert result["active_mode"] == "builder"
    assert result["session_id"] == "session-1"


def test_auto_mode_clears_persisted_manual_mode(monkeypatch):
    class FakeSessions:
        def get_session(self, session_id):
            return {"session_id": session_id, "status": "active", "active_mode": "builder"}

        def update_context(self, session_id, **values):
            return {"session_id": session_id, **values}

    monkeypatch.setattr(intelligence, "SessionManagerService", FakeSessions)
    result = intelligence.select_mode(
        intelligence.SelectModeRequest(session_id="session-1", mode_id="auto")
    )
    assert result["success"] is True
    assert result["active_mode"] == "auto"
    assert result["mode"] is None


def test_mode_selection_rejects_unknown_mode(monkeypatch):
    class FakeSessions:
        def get_session(self, session_id):
            return {"session_id": session_id, "status": "active"}

    monkeypatch.setattr(intelligence, "SessionManagerService", FakeSessions)
    try:
        intelligence.select_mode(
            intelligence.SelectModeRequest(session_id="session-1", mode_id="unknown")
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("unknown mode should be rejected")


def test_mode_selection_rejects_non_active_session(monkeypatch):
    class FakeSessions:
        def get_session(self, session_id):
            return {"session_id": session_id, "status": "paused"}

    monkeypatch.setattr(intelligence, "SessionManagerService", FakeSessions)
    try:
        intelligence.select_mode(
            intelligence.SelectModeRequest(session_id="session-1", mode_id="builder")
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("paused session should not change mode")
