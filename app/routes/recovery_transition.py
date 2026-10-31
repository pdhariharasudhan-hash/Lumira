from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.work_items.work_item_service import WorkItemService
from app.services.memory.memory_service import MemoryService
from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.execution_policy_service import ExecutionPolicyService
from app.services.system.recovery_completion_service import RecoveryCompletionService
from app.services.system.recovery_recheck_service import RecoveryRecheckService
from app.services.system.workflow_recovery_resume_service import WorkflowRecoveryResumeService
from app.services.system.recovery_transition_proposal_service import RecoveryTransitionProposalService
from app.services.system.recovery_transition_apply_service import RecoveryTransitionApplyService

router = APIRouter(prefix="/system/recovery-transition", tags=["recovery-transition"])
_work_items = WorkItemService()
_policy = ExecutionPolicyService(OutcomePatternService(MemoryService()))
_resume = WorkflowRecoveryResumeService(RecoveryCompletionService(), RecoveryRecheckService(_policy))
_proposal = RecoveryTransitionProposalService(_work_items, _resume)
_apply = RecoveryTransitionApplyService(_work_items)

class TransitionRequest(BaseModel):
    workflow_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    steps: list[str] = Field(default_factory=list, max_length=20)
    completed_steps: list[str] = Field(default_factory=list, max_length=20)
    recommendation: str = Field(min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=128)

class ApplyRequest(BaseModel):
    proposal: dict
    confirmation: bool = False

@router.post("/propose")
def propose_transition(request: TransitionRequest):
    try:
        return _proposal.propose(
            request.workflow_id, request.task_id, {"steps": request.steps},
            request.completed_steps, request.recommendation, request.project_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow or task not found")

@router.post("/apply")
def apply_transition(request: ApplyRequest):
    return _apply.apply(request.proposal, request.confirmation)
