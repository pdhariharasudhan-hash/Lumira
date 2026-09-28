from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.work_items.work_item_service import WorkItemService, WorkItemValidationError

router = APIRouter()


class TaskStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    blocker: str | None = Field(default=None, max_length=1000)
    result: str | None = Field(default=None, max_length=4000)


@router.get("/workflows")
def list_workflows(
    category: str | None = Query(default=None, pattern="^(business|operations)$"),
    session_id: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=0, le=200),
):
    return {"workflows": WorkItemService().list_workflows(category=category, session_id=session_id, limit=limit)}


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    workflow = WorkItemService().get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@router.patch("/workflows/{workflow_id}/tasks/{task_id}")
def update_task(workflow_id: str, task_id: str, request: TaskStatusUpdate):
    try:
        return WorkItemService().update_task(
            workflow_id, task_id, request.status, blocker=request.blocker, result=request.result
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except WorkItemValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
