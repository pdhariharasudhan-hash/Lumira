from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.tasks.personal_todo_service import PersonalTodoService

router = APIRouter(prefix="/todos", tags=["Personal To-Do"])
service = PersonalTodoService()

class TodoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    priority: str = Field(default="medium", max_length=20)
    project_id: str | None = Field(default=None, max_length=200)
    blocker: str | None = Field(default=None, max_length=1000)

class ProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    progress: int = Field(ge=0, le=100)

@router.post("", status_code=201)
def create(request: TodoCreate):
    try: return {"success": True, "task": service.create(**request.model_dump())}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("")
def list_tasks(status: str | None = None):
    try: return {"success": True, "tasks": service.list(status)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.patch("/{task_id}/progress")
def progress(task_id: str, request: ProgressUpdate):
    try: return {"success": True, "task": service.update_progress(task_id, request.progress)}
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
