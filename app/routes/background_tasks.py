from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService

router = APIRouter(prefix="/background-tasks", tags=["Background Tasks"])
service = BackgroundAgentTaskService()

class BackgroundTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10_000)
    agent_name: str | None = Field(default=None, pattern="^(planner_agent|research_agent|code_agent)$")
    autonomous: StrictBool = False

@router.post("", status_code=202)
def create_background_task(request: BackgroundTaskCreate, background_tasks: BackgroundTasks):
    created = service.create(request.task, request.agent_name, request.autonomous)
    if not created.get("success"):
        raise HTTPException(status_code=422, detail=created)
    task_id = created["task"]["task_id"]
    background_tasks.add_task(service.execute, task_id)
    return {"success": True, "status": "queued", "task": created["task"]}

@router.get("")
def list_background_tasks(
    status: str | None = Query(default=None, pattern="^(queued|running|completed|failed|interrupted)$"),
    limit: int = Query(default=100, ge=1, le=200),
):
    return service.list(status, limit)

@router.get("/{task_id}")
def get_background_task(task_id: str):
    task = service.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Background task not found.")
    return {"success": True, "task": task}
