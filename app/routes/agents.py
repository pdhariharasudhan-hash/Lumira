from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.agent_manager import AgentManager

router = APIRouter()


class AgentTask(BaseModel):
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


@router.post("/agents/dispatch")
def dispatch_agent(request: AgentTask):
    return AgentManager().dispatch(request.task)


@router.post("/agents/{agent_name}/run")
def run_agent(agent_name: str, request: AgentTask):
    return AgentManager().run(agent_name, request.task)
