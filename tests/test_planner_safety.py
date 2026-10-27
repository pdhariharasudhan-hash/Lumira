from app.services.decision.decision_models import DecisionState
from app.services.planner.planner_models import PlannerState
from app.services.planner.planner_service import PlannerService
from app.services.reasoning.reasoning_models import ReasoningState


class UnknownIntent:
    def decompose(self, goal):
        return {"intent": "unsupported_intent", "goal": goal}


class MissingPlanRegistry:
    def get_plan(self, intent):
        return None


class OversizedPlanRegistry:
    def get_plan(self, intent):
        return ["  step-{}  ".format(index) for index in range(30)] + [None, "   "]


def test_planner_blocks_execution_when_intent_has_no_registered_plan():
    planner = PlannerService()
    planner.decomposer = UnknownIntent()
    planner.registry = MissingPlanRegistry()

    state = planner.analyze(
        DecisionState(selected_option="complete a task", next_action="execute", confidence=0.9),
        ReasoningState(conclusions=["Should be discarded while blocked"]),
        PlannerState(),
    )

    assert state.execution_steps == []
    assert state.execution_order == []
    assert state.milestones == ["Planning Blocked"]
    assert state.blocked_tasks == ["planner"]
    assert "Execution Ready" not in state.milestones
    assert state.confidence <= 0.25
    assert any("no registered plan" in item for item in state.dependencies)


def test_planner_bounds_and_normalizes_registered_steps():
    planner = PlannerService()
    planner.decomposer = UnknownIntent()
    planner.registry = OversizedPlanRegistry()

    result = planner.create_plan("  a goal  ")

    assert result["success"] is True
    assert len(result["steps"]) == planner.MAX_PLAN_STEPS
    assert result["steps"][0] == "step-0"
    assert all(len(step) <= planner.MAX_STEP_LENGTH for step in result["steps"])


def test_planner_rejects_registry_entries_without_usable_steps():
    planner = PlannerService()
    planner.decomposer = UnknownIntent()
    planner.registry = type("EmptyStrings", (), {"get_plan": lambda self, intent: [None, " ", 4]})()

    result = planner.create_plan("a goal")

    assert result["success"] is False
    assert result["steps"] == []
    assert result["error"] == "registered plan contains no valid steps"
