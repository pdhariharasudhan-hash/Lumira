from fastapi import APIRouter, Request
from app.services.system.system_health_service import SystemHealthService

router = APIRouter(prefix="/system/health", tags=["system-health"])
_service = SystemHealthService()

@router.get("")
def system_health(request: Request):
    result = _service.snapshot()
    worker = getattr(request.app.state, "managed_scheduled_worker", None)
    if worker is not None:
        snapshot = worker.snapshot()
        state = snapshot.get("status")
        result["checks"]["managed_scheduled_worker"] = {
            "status": "degraded" if state == "stop_requested" else "healthy",
            **snapshot,
        }
        if state == "stop_requested":
            result["degraded_subsystems"] = sorted(set(
                result.get("degraded_subsystems", []) + ["managed_scheduled_worker"]
            ))
            result["status"] = "degraded"
    return result
