from fastapi import APIRouter, HTTPException

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.sessions.session_manager_service import (
    SessionManagerService,
    redact_sensitive_value,
)

router = APIRouter()
memory_service = MemoryService()


# ==========================
# CREATE / UPDATE MEMORY
# ==========================
@router.post("/memory")
def set_memory(payload: dict):
    try:
        key = payload.get("key")
        value = payload.get("value")

        if not key:
            raise MemoryValidationError("key is required")

        updated_memory = memory_service.update(key, value)

        return {
            "status": "ok",
            "data": {
                "key": key,
                "value": redact_sensitive_value(value)
            }
        }

    except MemoryValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


# ==========================
# GET SINGLE VALUE
# ==========================
@router.get("/memory/relevant")
def get_relevant_memory(q: str = "", session_id: str | None = None, project_id: str | None = None):
    if session_id:
        session = SessionManagerService().get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        project_id = project_id or session.get("active_project")
        goal_id = session.get("goal_id")
    else:
        goal_id = None
    try:
        return {
            "status": "ok",
            "data": memory_service.retrieve_relevant(
                query=q,
                project_id=project_id,
                goal_id=goal_id,
            ),
        }
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


# ==========================
# GET SINGLE VALUE
# ==========================
@router.get("/memory/{key}")
def get_memory(key: str):
    try:
        value = memory_service.get_value(key)

        if value is None:
            raise HTTPException(status_code=404, detail="key not found")

        return {
            "status": "ok",
            "data": {
                "key": key,
                "value": redact_sensitive_value(value)
            }
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


# ==========================
# GET ALL MEMORY
# ==========================
@router.get("/memory")
def get_all_memory():
    try:
        memory = memory_service.get_all()

        return {
            "status": "ok",
            "data": redact_sensitive_value(memory)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))