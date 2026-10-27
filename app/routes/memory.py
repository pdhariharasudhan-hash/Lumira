import json

from fastapi import APIRouter, HTTPException, Query
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.sessions.session_manager_service import (
    SessionManagerService,
    redact_sensitive_value,
)

router = APIRouter()
memory_service = MemoryService()


class MemoryUpdatePayload(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: object


class MemoryLinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=128)
    target_id: str = Field(min_length=1, max_length=128)
    relation: str = Field(min_length=1, max_length=100)


class MemoryArchivePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collection: str = Field(min_length=1, max_length=40)
    record_id: str = Field(min_length=1, max_length=128)


class DecisionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(min_length=1, max_length=2000)
    reason: str = Field(default="", max_length=5000)
    session_id: str | None = Field(default=None, max_length=128)
    project_id: str | None = Field(default=None, max_length=100)
    goal_id: str | None = Field(default=None, max_length=128)
    alternatives: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def reject_boolean_confidence(cls, value):
        if isinstance(value, bool):
            raise ValueError("confidence must be a number between 0 and 1")
        return value


class ExperienceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience_type: str = Field(pattern="^(success|failure|decision|workflow)$")
    summary: str = Field(min_length=1, max_length=4000)
    outcome: str = Field(min_length=1, max_length=5000)
    project_id: str | None = Field(default=None, max_length=100)
    goal_id: str | None = Field(default=None, max_length=128)
    lessons: list[str] = Field(default_factory=list, max_length=50)
    artifact_ids: list[str] = Field(default_factory=list, max_length=50)
    source_run: str | None = Field(default=None, max_length=128)


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
    q: Annotated[str, Query(max_length=500)] = "",
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    project_id: Annotated[str | None, Query(max_length=100)] = None,
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


@router.post("/memory/decisions")
def create_memory_decision(request: DecisionCreateRequest):
    if request.session_id and SessionManagerService().get_session(request.session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        decision = memory_service.record_decision(
            decision=request.decision,
            reason=request.reason,
            session_id=request.session_id,
            project_id=request.project_id,
            goal_id=request.goal_id,
            alternatives=request.alternatives,
            constraints=request.constraints,
            confidence=request.confidence,
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session_link_status = "not_applicable"
    if request.session_id:
        try:
            SessionManagerService().link_record(request.session_id, "decision", decision["decision_id"])
            session_link_status = "linked"
        except Exception:
            session_link_status = "link_failed"
    return {"status": "ok", "decision": redact_sensitive_value(decision), "session_link_status": session_link_status}


@router.get("/memory/decisions")
def list_memory_decisions(
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    goal_id: Annotated[str | None, Query(max_length=128)] = None,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=0, le=100)] = 50,
):
    if session_id and SessionManagerService().get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        decisions = memory_service.get_all().get("decisions", [])
        if session_id or project_id or goal_id:
            decisions = [
                item for item in decisions
                if (
                    (session_id and item.get("session_id") == session_id)
                    or (project_id and item.get("project_id") == project_id)
                    or (goal_id and item.get("goal_id") == goal_id)
                )
            ]
        decisions = [item for item in decisions if not item.get("archived")]
        return {"status": "ok", "decisions": redact_sensitive_value(decisions[-limit:] if limit else [])}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


@router.get("/memory/search")
def search_memory(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    goal_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=0, le=100)] = 20,
):
    try:
        return {"status": "ok", "data": memory_service.search(q, project_id, goal_id, limit)}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory/summary")
def summarize_memory(
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    goal_id: Annotated[str | None, Query(max_length=128)] = None,
):
    try:
        return {"status": "ok", "data": memory_service.summarize(project_id, goal_id)}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


@router.post("/memory/link")
def link_memory(payload: MemoryLinkPayload):
    try:
        memory = memory_service.get_all()
        known_ids = set()
        id_fields = ("goal_id", "decision_id", "experience_id", "learning_id", "artifact_id")
        for collection in ("goals", "decisions", "experiences", "learning_records"):
            for record in memory.get(collection, []) if isinstance(memory.get(collection, []), list) else []:
                if isinstance(record, dict):
                    known_ids.update(record.get(key) for key in id_fields if isinstance(record.get(key), str))
        for record in ArtifactManagerService().get_all_artifacts():
            if isinstance(record, dict) and isinstance(record.get("artifact_id"), str):
                known_ids.add(record["artifact_id"])
        if payload.source_id not in known_ids or payload.target_id not in known_ids:
            raise HTTPException(status_code=404, detail="source or target memory record not found")
        if payload.source_id == payload.target_id:
            raise HTTPException(status_code=422, detail="a memory record cannot link to itself")
        return {"status": "ok", "data": memory_service.link(payload.source_id, payload.target_id, payload.relation)}
    except HTTPException:
        raise
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


@router.post("/memory/archive")
def archive_memory(payload: MemoryArchivePayload):
    try:
        archived = (
            ArtifactManagerService().archive_artifact(payload.record_id)
            if payload.collection == "artifacts"
            else memory_service.archive(payload.collection, payload.record_id)
        )
        if not archived:
            raise HTTPException(status_code=404, detail="memory record not found")
        return {"status": "ok", "archived": True, "collection": payload.collection, "record_id": payload.record_id}
    except HTTPException:
        raise
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
