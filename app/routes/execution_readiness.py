from fastapi import APIRouter, Query
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.system.execution_readiness_service import ExecutionReadinessService

router = APIRouter(prefix="/system/execution", tags=["system-execution"])
_service = ExecutionReadinessService(NextActionService(), BlockerQueueService())

@router.get("/readiness")
def execution_readiness(project_id: str | None = Query(default=None, max_length=128)):
    return _service.status(project_id)
