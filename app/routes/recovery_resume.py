from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.memory.memory_service import MemoryService
from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.execution_policy_service import ExecutionPolicyService
from app.services.system.recovery_completion_service import RecoveryCompletionService
from app.services.system.recovery_recheck_service import RecoveryRecheckService
from app.services.system.workflow_recovery_resume_service import WorkflowRecoveryResumeService

router = APIRouter(prefix="/system/recovery-resume", tags=["recovery-resume"])
_policy = ExecutionPolicyService(OutcomePatternService(MemoryService()))
_service = WorkflowRecoveryResumeService(
    RecoveryCompletionService(),
    RecoveryRecheckService(_policy),
)

class RecoveryResumeRequest(BaseModel):
    steps: list[str] = Field(default_factory=list, max_length=20)
    completed_steps: list[str] = Field(default_factory=list, max_length=20)
    recommendation: str = Field(min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=128)

@router.post("/evaluate")
def evaluate_resume(request: RecoveryResumeRequest):
    return _service.evaluate(
        {"steps": request.steps},
        request.completed_steps,
        request.recommendation,
        request.project_id,
    )
