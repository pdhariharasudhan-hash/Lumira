import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.memory.memory_retention_service import MemoryRetentionService
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


class MemoryEvolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collection: Literal["goals", "decisions", "experiences", "learning_records"]
    record_id: str = Field(min_length=1, max_length=128)
    correction: dict[str, object] | None = None
    forget: bool = Field(default=False, strict=True)
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_action(self):
        if self.forget == (self.correction is not None):
            raise ValueError("provide one correction or set forget=true")
        if self.correction is not None:
            if not self.correction:
                raise ValueError("correction must be a non-empty object")
            try:
                correction_size = len(json.dumps(self.correction, ensure_ascii=False))
            except (TypeError, ValueError, RecursionError) as exc:
                raise ValueError("correction must contain JSON-compatible values") from exc
            if correction_size > 250_000:
                raise ValueError("correction exceeds the 250000-character limit")
        return self


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


class MemoryRetentionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_days: dict[str, StrictInt] = Field(min_length=1, max_length=7)


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


@router.post("/memory/retention/preview")
def preview_memory_retention(request: MemoryRetentionPreviewRequest):
    """Build an owner-configured retention plan without deleting memory."""
    collections = {
        "pipeline_runs": "pipeline_run",
        "artifacts": "artifact",
        "feature_history": "feature_history",
        "goals": "goal",
        "decisions": "decision",
        "experiences": "experience",
        "learning_records": "learning_record",
    }
    try:
        memory = memory_service.get_all()
        records = []
        for collection, category in collections.items():
            values = memory.get(collection, [])
            if not isinstance(values, list):
                raise MemoryValidationError(f"{collection} must be a list")
            for value in values:
                if isinstance(value, dict):
                    records.append({**value, "type": category})
                else:
                    records.append(value)
        result = MemoryRetentionService().plan(records, request.retention_days)
    except (MemoryValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Memory retention preview is unavailable.") from exc
    return {**result, "records_scanned": len(records), "collections_scanned": list(collections)}


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
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
    session_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=0, le=100),
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
    q: str = Query(min_length=1, max_length=500),
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=0, le=100),
):
    try:
        return {"status": "ok", "data": memory_service.search(q, project_id, goal_id, limit)}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory/summary")
def summarize_memory(
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
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


@router.post("/memory/evolve")
def evolve_memory(payload: MemoryEvolutionRequest):
    try:
        record = memory_service.evolve(
            payload.collection,
            payload.record_id,
            correction=payload.correction,
            forget=payload.forget,
            reason=payload.reason,
            source="user_api",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="memory record not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "data": redact_sensitive_value(record)}


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
