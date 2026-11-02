from fastapi import APIRouter, HTTPException
from app.services.work_items.work_item_service import WorkItemService
from app.services.system.task_recovery_evidence_service import TaskRecoveryEvidenceService
from app.services.system.task_recovery_analysis_service import TaskRecoveryAnalysisService
from app.services.system.task_recovery_package_service import TaskRecoveryPackageService

router = APIRouter(prefix="/system/task-recovery", tags=["task-recovery"])
_service = TaskRecoveryPackageService(
    TaskRecoveryEvidenceService(WorkItemService()),
    TaskRecoveryAnalysisService(),
)

@router.get("/{workflow_id}/{task_id}")
def task_recovery(workflow_id: str, task_id: str):
    try:
        return _service.build(workflow_id, task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow or task not found")
