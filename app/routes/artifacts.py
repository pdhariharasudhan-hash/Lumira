from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StrictBool
import base64
import binascii

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService,
    SUPPORTED_ARTIFACT_TYPES,
)
from app.services.artifacts.artifact_library_query_service import ArtifactLibraryQueryService
from app.services.artifacts.artifact_integrity_audit_service import ArtifactIntegrityAuditService
from app.services.artifacts.artifact_memory_consistency_service import ArtifactMemoryConsistencyService
from app.services.security.security_audit_log_service import SecurityAuditLogService

router = APIRouter()


class ArtifactCreateRequest(BaseModel):
    type: str
    content: str = Field(max_length=ArtifactManagerService.MAX_CONTENT_LENGTH)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(default="txt", pattern=r"^[A-Za-z0-9]{1,12}$")


class BinaryArtifactCreateRequest(BaseModel):
    type: str
    content_base64: str = Field(min_length=4, max_length=33_333_336)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(pattern=r"^[A-Za-z0-9]{1,12}$")


class ArtifactConsistencyRepairRequest(BaseModel):
    confirm: StrictBool
    limit: int = Field(default=10000, ge=0, le=10000)


class ArtifactDeletionRecoveryRequest(BaseModel):
    confirm: StrictBool
    limit: int = Field(default=25, ge=1, le=100)


def _manager() -> ArtifactManagerService:
    return ArtifactManagerService()


def _public_artifact(record: dict) -> dict:
    """Return artifact metadata without exposing internal filesystem paths."""
    public = {key: value for key, value in record.items() if key != "file"}
    filename = record.get("file")
    if isinstance(filename, str) and "." in filename:
        public["extension"] = filename.rsplit(".", 1)[-1].lower()
    return public


def _audited_artifact_change(action: str, identity: str, operation):
    """Fail closed before artifact mutation and record its outcome without content."""
    audit = SecurityAuditLogService()
    details = {"identity": identity[:128]}
    try:
        audit.append(
            event_type="artifact_lifecycle",
            action=action,
            outcome="requested",
            actor="local_owner",
            details=details,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Artifact mutation blocked because audit storage is unavailable.",
        ) from exc
    try:
        result = operation()
    except Exception as exc:
        try:
            audit.append(
                event_type="artifact_lifecycle",
                action=action,
                outcome="failed",
                actor="local_owner",
                details={**details, "error_type": type(exc).__name__},
            )
        except Exception:
            pass
        raise
    try:
        audit.append(
            event_type="artifact_lifecycle",
            action=action,
            outcome="completed" if result else "not_found",
            actor="local_owner",
            details=details,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "artifact_mutation_audit_failed",
                "side_effect_may_have_occurred": True,
                "action": action,
            },
        ) from exc
    return result


@router.post("/artifacts", status_code=201)
def create_artifact(request: ArtifactCreateRequest):
    if request.type not in SUPPORTED_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported artifact type: {request.type}",
        )
    try:
        artifact = _audited_artifact_change(
            "artifact.create",
            request.type,
            lambda: _manager().create_artifact(
                artifact_type=request.type,
                content=request.content,
                source=request.source,
                extension=request.extension,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "artifact": _public_artifact(artifact)}


@router.post("/artifacts/binary", status_code=201)
def create_binary_artifact(request: BinaryArtifactCreateRequest):
    if request.type not in {"audio", "images", "video", "pdf", "generated_files"}:
        raise HTTPException(status_code=400, detail="Unsupported binary artifact type")
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="content_base64 must be valid Base64") from exc
    if not content or len(content) > ArtifactManagerService.MAX_BINARY_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="Binary artifact exceeds the 25 MB limit")
    extension = request.extension.lower()
    if request.type == "pdf" and (extension != "pdf" or not content.startswith(b"%PDF-")):
        raise HTTPException(status_code=422, detail="PDF artifacts must contain a valid PDF signature")
    if request.type == "video":
        valid_video = (extension == "mp4" and len(content) >= 12 and content[4:8] == b"ftyp") or (extension == "webm" and content.startswith(b"\x1aE\xdf\xa3"))
        if not valid_video:
            raise HTTPException(status_code=422, detail="Video artifacts must be MP4 or WebM content")
    try:
        artifact = _audited_artifact_change(
            "artifact.create_binary",
            request.type,
            lambda: _manager().create_binary_artifact(request.type, content, request.source, extension),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "artifact": _public_artifact(artifact)}


@router.get("/artifacts")
def list_artifacts(
    artifact_type: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
):
    try:
        result = ArtifactLibraryQueryService(_manager()).list_artifacts(
            artifact_type=artifact_type,
            query=q,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/artifacts/recent")
def recent_artifacts(limit: int = Query(default=20, ge=0, le=100), include_archived: bool = False):
    records = _manager().recent_artifacts(limit, include_archived)
    return {"success": True, "artifacts": [_public_artifact(item) for item in records]}


@router.get("/artifacts/types")
def artifact_types():
    counts = _manager().type_counts()
    return {"success": True, "types": counts, "total": sum(counts.values())}


@router.get("/artifacts/stats")
def artifact_stats():
    manager = _manager()
    stats = manager.stats()
    artifacts = manager.get_all_artifacts()
    stats["archived"] = sum(1 for item in artifacts if item.get("archived", False))
    stats["active"] = len(artifacts) - stats["archived"]
    return {"success": True, "stats": stats}


@router.get("/artifacts/integrity")
def artifact_integrity_audit(
    limit: int = Query(default=1000, ge=0, le=100000),
    verify_hashes: bool = True,
):
    """Run a bounded, read-only integrity audit over indexed artifact files."""
    manager = _manager()
    try:
        return ArtifactIntegrityAuditService(manager).audit(
            limit=limit,
            verify_hashes=verify_hashes,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Artifact integrity audit could not be completed safely.") from exc


@router.get("/artifacts/consistency")
def artifact_memory_consistency(
    limit: int = Query(default=10000, ge=0, le=10000),
):
    """Preview drift between the canonical artifact index and memory mirror."""
    try:
        return ArtifactMemoryConsistencyService(_manager()).reconcile(
            apply=False,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Artifact consistency preview could not be completed safely.",
        ) from exc


@router.post("/artifacts/consistency/repair")
def repair_artifact_memory_consistency(request: ArtifactConsistencyRepairRequest):
    """Repair only the derived memory mirror after explicit owner confirmation."""
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    audit = SecurityAuditLogService()
    try:
        audit.append(
            event_type="artifact_consistency",
            action="artifact.memory.reconcile",
            outcome="requested",
            actor="local_owner",
            details={"limit": request.limit},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Artifact repair blocked because audit storage is unavailable.") from exc
    try:
        result = ArtifactMemoryConsistencyService(_manager()).reconcile(
            apply=True,
            limit=request.limit,
        )
    except Exception as exc:
        try:
            audit.append(
                event_type="artifact_consistency",
                action="artifact.memory.reconcile",
                outcome="failed",
                actor="local_owner",
                details={"error_type": type(exc).__name__},
            )
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Artifact mirror repair could not be completed safely.") from exc
    try:
        audit.append(
            event_type="artifact_consistency",
            action="artifact.memory.reconcile",
            outcome="completed" if result.get("success") is True else "partial",
            actor="local_owner",
            details={
                "changes": result.get("changes", {}),
                "remaining_findings": result.get("remaining_findings"),
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "artifact_repair_audit_failed", "side_effect_may_have_occurred": True, "result": result},
        ) from exc
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/artifacts/deletions/pending")
def pending_artifact_deletions(limit: int = Query(default=25, ge=1, le=100)):
    """List bounded deletion tombstones without changing artifact state."""
    try:
        return {
            "success": True,
            "pending": _manager().pending_deletions(limit),
        }
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Pending artifact deletions could not be read safely.") from exc


@router.post("/artifacts/deletions/recover")
def recover_pending_artifact_deletions(request: ArtifactDeletionRecoveryRequest):
    """Resume only previously requested deletions after explicit confirmation."""
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    audit = SecurityAuditLogService()
    details = {"limit": request.limit}
    try:
        audit.append(
            event_type="artifact_lifecycle",
            action="artifact.deletion.recover",
            outcome="requested",
            actor="local_owner",
            details=details,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Deletion recovery blocked because audit storage is unavailable.") from exc
    try:
        result = _manager().recover_pending_deletions(request.limit)
    except Exception as exc:
        try:
            audit.append(
                event_type="artifact_lifecycle",
                action="artifact.deletion.recover",
                outcome="failed",
                actor="local_owner",
                details={**details, "error_type": type(exc).__name__},
            )
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Pending artifact deletion recovery failed safely.") from exc
    try:
        audit.append(
            event_type="artifact_lifecycle",
            action="artifact.deletion.recover",
            outcome="completed" if result.get("success") is True else "partial",
            actor="local_owner",
            details={
                **details,
                "examined": result.get("examined", 0),
                "recovered": result.get("recovered", 0),
                "failed": result.get("failed", 0),
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "artifact_recovery_audit_failed", "side_effect_may_have_occurred": True, "result": result},
        ) from exc
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str):
    manager = _manager()
    try:
        path = manager.get_artifact_path(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path)


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    manager = _manager()
    artifact = manager.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    try:
        content_path = manager.get_artifact_path(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="artifact content path is invalid") from exc
    public_artifact = _public_artifact(artifact)
    # Expose availability, never the local filesystem path itself.
    public_artifact["content_available"] = content_path is not None and content_path.is_file()
    public_artifact["content_integrity"] = manager.verify_artifact_content(artifact_id)
    return {"success": True, "artifact": public_artifact}


@router.post("/artifacts/{artifact_id}/archive")
def archive_artifact(artifact_id: str):
    try:
        archived = _audited_artifact_change(
            "artifact.archive", artifact_id,
            lambda: _manager().archive_artifact(artifact_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not archived:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id, "archived": True}


@router.post("/artifacts/{artifact_id}/restore")
def restore_artifact(artifact_id: str):
    try:
        restored = _audited_artifact_change(
            "artifact.restore", artifact_id,
            lambda: _manager().restore_artifact(artifact_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not restored:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id, "archived": False}


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str):
    try:
        deleted = _audited_artifact_change(
            "artifact.delete", artifact_id,
            lambda: _manager().delete_artifact(artifact_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id}
