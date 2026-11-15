from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.services.multi_model.multi_model_orchestrator import MultiModelIntelligenceOrchestrator
from app.services.multi_model.model_health_service import ModelHealthService
from app.services.security.security_audit_log_service import SecurityAuditLogService

router=APIRouter(prefix="/multi-model",tags=["Multi-Model Intelligence"])
service=MultiModelIntelligenceOrchestrator()

class ModelHealthResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool


class OrchestrateRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    prompt:str=Field(min_length=1,max_length=20000)
    task_type:str=Field(default="reply",max_length=32)
    mode:str=Field(default="smart",max_length=32)
    context:dict=Field(default_factory=dict)

@router.get("/models")
def list_models(): return {"success":True,"models":service.available_models()}

@router.get("/health")
def model_health():
    result = ModelHealthService().snapshot()
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    return result

@router.post("/models/{model_id}/reset-health")
def reset_model_health(model_id: str, request: ModelHealthResetRequest):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    audit = SecurityAuditLogService()
    try:
        audit.append(
            event_type="model_health",
            action="model.health_reset",
            outcome="requested",
            actor="local_owner",
            details={"model_id": model_id},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Model health reset was blocked because the audit log is unavailable.") from exc
    result = ModelHealthService().reset(model_id, owner_confirmed=request.confirm)
    if result.get("success") is not True:
        code = result.get("code")
        status = 404 if code == "model_not_found" else 503 if code and "unavailable" in code else 422
        raise HTTPException(status_code=status, detail=result)
    try:
        audit.append(
            event_type="model_health",
            action="model.health_reset",
            outcome="completed",
            actor="local_owner",
            details={"model_id": model_id},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "model_health_reset_audit_failed", "side_effect_may_have_occurred": True, "model_id": model_id},
        ) from exc
    return result


@router.get("/modes")
def list_modes(): return {"success":True,"modes":sorted(service.MODES)}

@router.post("/orchestrate")
def orchestrate(request:OrchestrateRequest):
    try: return service.run(**request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
