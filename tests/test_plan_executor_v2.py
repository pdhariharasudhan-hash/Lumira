from app.services.planner.plan_executor_v2 import PlanExecutorV2


def test_executor_does_not_claim_success_without_real_handler():
    result = PlanExecutorV2().execute({
        "goal": "build an API",
        "intent": "build_api",
        "steps": ["validate", "builder"],
    })

    assert result["success"] is False
    assert result["state"] == "failed"
    assert result["code"] == "handler_not_registered"
    assert result["failed_step"] == "validate"
    assert result["blocked_steps"] == 1
    assert len(result["results"]) == 1


def test_executor_runs_registered_steps_in_order_and_reports_completion():
    calls = []
    executor = PlanExecutorV2({
        "validate": lambda: calls.append("validate") or {"success": True, "output": "valid"},
        "builder": lambda: calls.append("builder") or {"success": True, "output": "built"},
    })

    result = executor.execute({"goal": "build an API", "steps": ["validate", "builder"]})

    assert calls == ["validate", "builder"]
    assert result["success"] is True
    assert result["state"] == "completed"
    assert result["completed_steps"] == 2
    assert result["blocked_steps"] == 0


def test_executor_stops_after_first_failed_step():
    calls = []
    executor = PlanExecutorV2({
        "validate": lambda: {"success": False, "code": "validation_failed"},
        "builder": lambda: calls.append("builder") or {"success": True},
    })

    result = executor.execute({"steps": ["validate", "builder"]})

    assert result["success"] is False
    assert result["failed_step"] == "validate"
    assert result["blocked_steps"] == 1
    assert calls == []


def test_executor_rejects_empty_and_unbounded_plans():
    executor = PlanExecutorV2()

    assert executor.execute({"steps": []})["code"] == "empty_plan"
    oversized = executor.execute({"steps": ["step"] * (executor.MAX_STEPS + 1)})
    assert oversized["code"] == "plan_too_large"


def test_executor_contains_handler_exceptions_and_continues_never():
    calls = []
    def fail():
        raise RuntimeError("private path should not be returned")

    executor = PlanExecutorV2({
        "first": fail,
        "second": lambda: calls.append("second") or {"success": True},
    })
    result = executor.execute({"steps": ["first", "second"]})

    assert result["success"] is False
    assert result["code"] == "handler_execution_failed"
    assert "private path" not in str(result)
    assert calls == []
