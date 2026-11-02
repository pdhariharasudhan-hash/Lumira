from fastapi import APIRouter
from app.services.system.core_diagnostics_service import CoreDiagnosticsService

router = APIRouter(prefix="/system/diagnostics", tags=["system-diagnostics"])
_service = CoreDiagnosticsService()

@router.get("")
def core_diagnostics():
    return _service.snapshot()
