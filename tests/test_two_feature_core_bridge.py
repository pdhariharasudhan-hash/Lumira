from app.services.tasks.quick_task_service import QuickTaskService
from app.services.system.core_event_log_service import CoreEventLogService


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {"success": True, "operation": args[0]}


def test_two_new_features_bridge_to_core(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    tasks=QuickTaskService(tmp_path/"tasks.json")
    task=tasks.create("Ship feature",session_id="s1")
    assert task["task"]["core_context"]["operation"]=="quick_task_create"
    assert tasks.complete(task["task"]["id"])["task"]["status"]=="completed"

    events=CoreEventLogService(tmp_path/"events.json")
    result=events.record("task_completed","quick_tasks",{"task_id":task["task"]["id"]})
    assert result["event_record"]["core_context"]["operation"]=="core_event_record"
    assert len(events.recent()["events"])==1
