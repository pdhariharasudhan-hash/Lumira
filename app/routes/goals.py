from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.memory.memory_service import MemoryService, MemoryValidationError

router = APIRouter()


class GoalCreateRequest(BaseModel):
    title: str
    objective: str = ""
    priority: str = "normal"
    project_id: str | None = None
    parent_goal_id: str | None = None
    blockers: list[str] = Field(default_factory=list)


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    objective: str | None = None
    priority: str | None = None
    status: str | None = None
    progress: float | None = None
    milestones: list[dict] | None = None
    dependencies: list[str] | None = None
    blockers: list[str] | None = None
    project_id: str | None = None
    artifact_ids: list[str] | None = None


@router.get("/goals")
def list_goals(project_id: str | None = None, status: str | None = None):
    try:
        records = MemoryService().get_all().get("goals", [])
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc
    if project_id:
        records = [record for record in records if record.get("project_id") == project_id]
    if status:
        records = [record for record in records if record.get("status") == status]
    records.sort(key=lambda record: (record.get("updated_at", ""), record.get("goal_id", "")))
    return {"goals": records}


@router.post("/goals")
def create_goal(request: GoalCreateRequest):
    try:
        return MemoryService().create_goal(**request.model_dump())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: str, request: GoalUpdateRequest):
    updates = {key: value for key, value in request.model_dump(exclude_unset=True).items() if value is not None}
    try:
        return MemoryService().update_goal(goal_id, **updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
