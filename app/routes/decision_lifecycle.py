from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.memory.decision_lifecycle_service import DecisionLifecycleService
from app.services.memory.memory_service import MemoryValidationError
from app.services.sessions.session_manager_service import redact_sensitive_value

router = APIRouter(prefix="/memory/decisions", tags=["decision-intelligence"])
_service = DecisionLifecycleService()


class DecisionOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome_status: str = Field(pattern="^(success|failure|partial|reversed)$")
    outcome: str = Field(default="", max_length=3000)


@router.get("/{decision_id}")
def get_decision(decision_id: str):
    try:
        decision = _service.get(decision_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Decision memory is unavailable") from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return {"success": True, "decision": redact_sensitive_value(decision)}


@router.post("/{decision_id}/outcome")
def record_decision_outcome(decision_id: str, request: DecisionOutcomeRequest):
    try:
        result = _service.record_outcome(
            decision_id, request.outcome_status, request.outcome
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="decision not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return redact_sensitive_value(result)
