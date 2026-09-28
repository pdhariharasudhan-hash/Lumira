import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.sessions.session_manager_service import (
    SessionManagerService,
    redact_sensitive_value,
)

router = APIRouter()
memory_service = MemoryService()


class MemoryUpdatePayload(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: object


# ==========================
# CREATE / UPDATE MEMORY
# ==========================
@router.post("/memory")
def set_memory(payload: MemoryUpdatePayload):
    try:
        key = payload.key
        value = payload.value
        if len(json.dumps(value, ensure_ascii=False)) > 250_000:
            raise MemoryValidationError("memory value exceeds the 250000-character limit")

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
        raise HTTPException(status_code=500, detail="Memory update failed safely") from e


# ==========================
# GET SINGLE VALUE
# ==========================
@router.get("/memory/relevant")
def get_relevant_memory(
    q: str = Query(default="", max_length=500),
    session_id: str | None = Query(default=None, max_length=128),
    project_id: str | None = Query(default=None, max_length=100),
):
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
