from fastapi import APIRouter, HTTPException
from app.services.work_items.work_item_service import WorkItemService
from app.services.system.task_recovery_evidence_service import TaskRecoveryEvidenceService
from app.services.system.task_recovery_analysis_service import TaskRecoveryAnalysisService
from app.services.system.task_recovery_package_service import TaskRecoveryPackageService
from app.services.system.task_specific_recovery_plan_service import TaskSpecificRecoveryPlanService
from app.services.system.recovery_plan_bridge_service import RecoveryPlanBridgeService
from app.services.system.recovery_readiness_service import RecoveryReadinessService
from app.services.system.recovery_next_step_service import RecoveryNextStepService

router = APIRouter(prefix="/system/task-recovery-plan", tags=["task-recovery-plan"])
_package = TaskRecoveryPackageService(
    TaskRecoveryEvidenceService(WorkItemService()),
    TaskRecoveryAnalysisService(),
)
_bridge = RecoveryPlanBridgeService(_package, TaskSpecificRecoveryPlanService())
_readiness = RecoveryReadinessService()
_next_step = RecoveryNextStepService()

@router.get("/{workflow_id}/{task_id}")
def recovery_plan(workflow_id: str, task_id: str):
    try:
        result = _bridge.build(workflow_id, task_id)
        result["readiness"] = _readiness.evaluate(result["package"])
        result["next_step"] = _next_step.next_step(result["task_plan"])
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow or task not found")
