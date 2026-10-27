from app.services.capabilities import capability_router_service as module


class FakePipeline:
    calls = []

    def execute(self, goal):
        type(self).calls.append(goal)
        if not isinstance(goal, str) or not goal.strip():
            return {"success": False, "state": "blocked", "code": "invalid_goal"}
        return {
            "success": True,
            "state": "completed",
            "goal": goal.strip(),
            "execution_mode": "planning_only",
        }


def test_project_pipeline_capability_dispatches_to_existing_pipeline(monkeypatch):
    FakePipeline.calls = []
    monkeypatch.setattr(module, "PlanExecutorV3", FakePipeline)
    router = object.__new__(module.CapabilityRouterService)

    result = router.execute("project_pipeline", {"request": "  build a notes API  "})

    assert result["success"] is True
    assert result["execution_mode"] == "planning_only"
    assert result["goal"] == "build a notes API"
    assert FakePipeline.calls == ["  build a notes API  "]


def test_project_pipeline_capability_preserves_blocked_result(monkeypatch):
    FakePipeline.calls = []
    monkeypatch.setattr(module, "PlanExecutorV3", FakePipeline)
    router = object.__new__(module.CapabilityRouterService)

    result = router.execute("project_pipeline", {"goal": ""})

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "invalid_goal"
