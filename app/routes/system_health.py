from fastapi import APIRouter, Request
from app.services.system.system_health_service import SystemHealthService

router = APIRouter(prefix="/system/health", tags=["system-health"])
_service = SystemHealthService()

@router.get("")
def system_health(request: Request):
    result = _service.snapshot()
    plugin_runtime = getattr(request.app.state, "plugin_runtime", None)
    if plugin_runtime is None:
        result["checks"]["plugin_runtime"] = {
            "status": "degraded",
            "available": False,
            "error": getattr(request.app.state, "plugin_runtime_error", None) or "plugin_runtime_unavailable",
        }
    else:
        try:
            handlers = plugin_runtime.list_handlers()
            result["checks"]["plugin_runtime"] = {
                "status": "healthy",
                "available": True,
                "registered_handler_count": len(handlers),
                "builtin_binding": getattr(request.app.state, "builtin_plugin_binding", None),
                "dynamic_plugin_code_execution": False,
            }
        except Exception as exc:
            result["checks"]["plugin_runtime"] = {
                "status": "degraded",
                "available": False,
                "error": type(exc).__name__,
            }
    if result["checks"]["plugin_runtime"]["status"] != "healthy":
        result["degraded_subsystems"] = sorted(set(
            result.get("degraded_subsystems", []) + ["plugin_runtime"]
        ))
        result["status"] = "degraded"

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
