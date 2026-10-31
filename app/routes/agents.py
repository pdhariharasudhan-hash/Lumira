from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.agents.agent_manager import AgentManager
from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator

router = APIRouter()


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10000)


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


@router.post("/agents/dispatch")
def dispatch_agent(request: AgentTask):
    return BrainAgentOrchestrator().execute(request.task)


@router.post("/agents/{agent_name}/run")
def run_agent(agent_name: str, request: AgentTask):
    return BrainAgentOrchestrator().execute(request.task, agent_name=agent_name)
