from datetime import datetime, timedelta, timezone

from app.services.reminders.reminder_service import ReminderService


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {"success": True, "context": {"session_id": kwargs.get("session_id")}}


def test_reminder_persists_core_context_and_becomes_due(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    service = ReminderService(tmp_path / "reminders.json")
    due_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    created = service.create("Test Lumira", due_at, session_id="s1")

    assert created["success"] is True
    assert created["reminder"]["core_context"]["success"] is True

    due = service.due()
    assert len(due["reminders"]) == 1
    assert due["reminders"][0]["status"] == "due"
