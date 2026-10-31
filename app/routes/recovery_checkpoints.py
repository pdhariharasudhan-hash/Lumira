from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.recovery.recovery_checkpoint_service import RecoveryCheckpointService

router = APIRouter(prefix="/recovery/checkpoints")


class CheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(min_length=1, max_length=200)
    stage: str = Field(min_length=1, max_length=128)
    state: dict = Field(default_factory=dict)


@router.post("", status_code=201)
def save_checkpoint(request: CheckpointRequest):
    try:
        checkpoint = RecoveryCheckpointService().save(
            request.workflow_id, request.stage, request.state
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "checkpoint": checkpoint}


@router.get("/{workflow_id}")
def get_checkpoint(workflow_id: str):
    checkpoint = RecoveryCheckpointService().resume(workflow_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="checkpoint not found")
    return {"success": True, "checkpoint": checkpoint}
