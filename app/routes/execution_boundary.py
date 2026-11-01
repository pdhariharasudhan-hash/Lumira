from fastapi import APIRouter
from app.services.workspace.sandbox_readiness_service import SandboxReadinessService

router = APIRouter(prefix="/system/execution-boundary", tags=["system-readiness"])
_service = SandboxReadinessService()

@router.get("")
def execution_boundary():
    return _service.snapshot()
