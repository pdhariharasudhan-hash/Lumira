from app.agents.agent_manager import AgentManager
from app.services.multi_model.multi_model_orchestrator import MultiModelIntelligenceOrchestrator


def test_tool_selection_routes_task_families_without_execution():
    selected = MultiModelIntelligenceOrchestrator.select_tool("Investigate evidence for the database choice")
    assert selected["success"] is True
    assert selected["selected_tool"] == "research"
    assert selected["agent"] == "research_agent"


def test_tool_selection_rejects_unknown_and_unbounded_tasks():
    unknown = MultiModelIntelligenceOrchestrator.select_tool("write a poem")
    assert unknown["success"] is False
    assert unknown["code"] == "no_matching_tool"
    invalid = MultiModelIntelligenceOrchestrator.select_tool("x" * 20001)
    assert invalid["code"] == "invalid_task"


def test_tool_selection_uses_word_boundaries_and_research_synonyms():
    selected = MultiModelIntelligenceOrchestrator.select_tool("Analyze the design risks")
    unrelated = MultiModelIntelligenceOrchestrator.select_tool("I am a happy user")

    assert selected["success"] is True
    assert selected["selected_tool"] == "research"
    assert unrelated["success"] is False


def test_agent_manager_dispatch_uses_the_central_tool_selector(monkeypatch):
    manager = AgentManager()
    calls = []

    def fake_run(agent_name, task):
        calls.append((agent_name, task))
        return {"success": True, "state": "completed", "agent": agent_name}

    monkeypatch.setattr(manager, "run", fake_run)
    result = manager.dispatch("Investigate evidence for the database choice")

    assert calls == [("research_agent", "Investigate evidence for the database choice")]
    assert result["success"] is True
    assert result["selection"] == {
        "tool": "research",
        "agent": "research_agent",
        "reason": "deterministic_task_capability_match",
    }
