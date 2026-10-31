from app.services.notifications.notification_service import NotificationService


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {"success": True, "operation": args[0]}


def test_notification_persists_core_context_and_read_state(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    service = NotificationService(tmp_path / "notifications.json")
    created = service.create("Workflow completed", "success", session_id="s1")
    assert created["success"] is True
    assert created["notification"]["core_context"]["operation"] == "notification_create"

    notification_id = created["notification"]["id"]
    read = service.mark_read(notification_id)
    assert read["success"] is True
    assert read["notification"]["status"] == "read"
