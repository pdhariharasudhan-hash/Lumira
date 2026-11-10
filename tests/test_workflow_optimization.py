from app.agents.workflow_engine import WorkflowEngine


def test_workflow_optimizer_orders_prerequisites_and_preserves_steps():
    result = WorkflowEngine.optimize_plan(["save_project", "code", "builder", "validate"])
    assert result["success"] is True
    assert result["steps"] == ["validate", "builder", "code", "save_project"]


def test_workflow_optimizer_rejects_duplicates_and_unknown_stages():
    assert WorkflowEngine.optimize_plan(["validate", "validate"])["code"] == "duplicate_stage"
    assert WorkflowEngine.optimize_plan(["validate", "unknown"])["code"] == "capability_unavailable"
