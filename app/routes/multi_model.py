from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.multi_model.multi_model_orchestrator import MultiModelIntelligenceOrchestrator

router=APIRouter(prefix="/multi-model",tags=["Multi-Model Intelligence"])
service=MultiModelIntelligenceOrchestrator()

class OrchestrateRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    prompt:str=Field(min_length=1,max_length=20000)
    task_type:str=Field(default="reply",max_length=32)
    mode:str=Field(default="smart",max_length=32)
    context:dict=Field(default_factory=dict)

@router.get("/models")
def list_models(): return {"success":True,"models":service.available_models()}

@router.get("/modes")
def list_modes(): return {"success":True,"modes":sorted(service.MODES)}

@router.post("/orchestrate")
def orchestrate(request:OrchestrateRequest):
    try: return service.run(**request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
