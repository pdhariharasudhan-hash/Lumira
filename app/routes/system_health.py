from fastapi import APIRouter
from app.services.system.system_health_service import SystemHealthService

router = APIRouter(prefix="/system/health", tags=["system-health"])
_service = SystemHealthService()

@router.get("")
def system_health():
    return _service.snapshot()
