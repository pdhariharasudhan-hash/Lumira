from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.agents.agent_manager import AgentManager
from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator
from app.agents.agent_collaboration_service import AgentCollaborationService

router = APIRouter()


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10000)
    agent_name: str | None = Field(default=None, pattern="^(planner_agent|research_agent|code_agent)$")
    autonomous: StrictBool = False


class CollaborationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[dict[str, str]] = Field(min_length=1, max_length=3)


class AgentMessageBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[dict[str, str]] = Field(min_length=1, max_length=8)


class AgentOutcomeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[dict] = Field(min_length=1, max_length=8)


@router.get("/agents")
def list_agents():
    manager = AgentManager()
    return {
        "success": True,
        "agents": [
            {"name": agent.name, "description": agent.description, "capabilities": agent.capabilities}
            for agent in (manager.registry.get(name) for name in manager.list_agents())
        ],
    }


@router.get("/agents/core-context")
def agents_core_context():
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
    return CoreRuntimeBridgeService().overview()


@router.get("/agents/summary")
def agent_summary():
    manager = AgentManager()
    agents = []
    for name in manager.list_agents():
        agent = manager.registry.get(name)
        agents.append({
            "name": name,
            "capability_count": len(getattr(agent, "capabilities", []) or []),
            "description": getattr(agent, "description", ""),
        })
    return {"success": True, "count": len(agents), "agents": agents}


@router.post("/agents/communicate")
def communicate_agents(request: AgentMessageBatch):
    return AgentCollaborationService().communicate(request.messages)


@router.post("/agents/evaluate")
def evaluate_agents(request: AgentOutcomeBatch):
    return AgentCollaborationService.evaluate(request.results)


@router.post("/agents/optimize")
def optimize_agents(request: AgentOutcomeBatch):
    return AgentCollaborationService.optimize(request.results)


@router.post("/agents/collaborate")
def collaborate_agents(request: CollaborationRequest):
    return AgentCollaborationService().collaborate(request.tasks)


@router.post("/agents/dispatch")
def dispatch_agent(request: AgentTask):
    kwargs = {"agent_name": request.agent_name}
    if request.autonomous:
        kwargs["autonomous"] = True
    return BrainAgentOrchestrator().execute(request.task, **kwargs)


@router.post("/agents/{agent_name}/run")
def run_agent(agent_name: str, request: AgentTask):
    kwargs = {"agent_name": agent_name}
    if request.autonomous:
        kwargs["autonomous"] = True
    return BrainAgentOrchestrator().execute(request.task, **kwargs)
