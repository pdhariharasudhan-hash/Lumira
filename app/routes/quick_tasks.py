from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.tasks.quick_task_service import QuickTaskService

router=APIRouter(prefix="/quick-tasks", tags=["quick-tasks"])
_service=QuickTaskService()

class TaskCreate(BaseModel):
    title:str=Field(min_length=1,max_length=1000)
    session_id:str|None=None
    project_id:str|None=None
    goal_id:str|None=None

@router.post("")
def create_task(request:TaskCreate):
    return _service.create(request.title,request.session_id,request.project_id,request.goal_id)

@router.get("")
def list_tasks(status:str|None=None):
    return _service.list(status)

@router.post("/{task_id}/complete")
def complete_task(task_id:str):
    return _service.complete(task_id)
