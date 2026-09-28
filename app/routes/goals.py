from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.memory.memory_service import MemoryService, MemoryValidationError

router = APIRouter()


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(default="", max_length=2000)
    priority: str = Field(default="normal", max_length=30)
    project_id: str | None = Field(default=None, max_length=100)
    parent_goal_id: str | None = Field(default=None, max_length=128)
    blockers: list[str] = Field(default_factory=list, max_length=20)


class GoalUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    objective: str | None = Field(default=None, max_length=2000)
    priority: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, max_length=30)
    progress: float | None = None
    milestones: list[dict] | None = Field(default=None, max_length=50)
    dependencies: list[str] | None = Field(default=None, max_length=50)
    blockers: list[str] | None = Field(default=None, max_length=20)
    project_id: str | None = Field(default=None, max_length=100)
    artifact_ids: list[str] | None = Field(default=None, max_length=50)


@router.get("/goals")
def list_goals(
    project_id: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=30),
):
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
