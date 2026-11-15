"""Consent-bound audio retention planning and explicit expiry cleanup."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.memory.memory_service import MemoryService
from app.services.security.security_audit_log_service import SecurityAuditLogService


class VoiceRetentionService:
    """Preview expired recordings; delete only after an explicit owner confirmation."""

    MAX_CANDIDATES = 200

    def __init__(self, artifacts=None, memory=None, audit_log=None):
        self.artifacts = artifacts or ArtifactManagerService()
        self.memory = memory or MemoryService()
        self.audit = audit_log or SecurityAuditLogService()

    @staticmethod
    def _parse_expiry(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except (ValueError, OverflowError):
            return None

    def preview(self, *, now: datetime | None = None, limit: int = MAX_CANDIDATES) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= self.MAX_CANDIDATES:
            raise ValueError("limit must be between 0 and 200")
        reference = now or datetime.now(UTC)
        if not isinstance(reference, datetime):
            raise ValueError("now must be a datetime")
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        reference = reference.astimezone(UTC)

        records = self.artifacts.get_all_artifacts()
        if not isinstance(records, list):
            raise ValueError("artifact index must return a list")
        candidates = []
        retained = []
        unknown = []
        for record in records:
            if not isinstance(record, dict) or record.get("type") != "audio":
                continue
            artifact_id = record.get("artifact_id")
            consent = record.get("consent")
            retention = consent.get("retention") if isinstance(consent, dict) else None
            if (
                not isinstance(artifact_id, str)
                or not artifact_id.strip()
                or not isinstance(consent, dict)
                or not isinstance(consent.get("receipt_id"), str)
                or not consent.get("receipt_id").strip()
                or not isinstance(retention, dict)
                or retention.get("mode") not in {"days", "until_deleted"}
            ):
                unknown.append({"artifact_id": artifact_id, "reason": "consent_or_retention_metadata_missing"})
                continue
            if retention.get("mode") == "until_deleted":
                retained.append({"artifact_id": artifact_id, "reason": "owner_selected_until_deleted"})
                continue
            expiry = self._parse_expiry(retention.get("expires_at"))
            if expiry is None:
                unknown.append({"artifact_id": artifact_id, "reason": "retention_expiry_invalid"})
                continue
            if expiry > reference:
                retained.append({
                    "artifact_id": artifact_id,
                    "expires_at": expiry.isoformat(),
                })
                continue
            candidates.append({
                "artifact_id": artifact_id,
                "expires_at": expiry.isoformat(),
                "consent_receipt_id": consent["receipt_id"],
                "archived": record.get("archived") is True,
            })

        candidates.sort(key=lambda item: (item["expires_at"], item["artifact_id"]))
        selected = candidates[:limit]
        return {
            "success": True,
            "mode": "preview_only",
            "reference_time": reference.isoformat(),
            "expired_count": len(candidates),
            "candidates": selected,
            "retained_count": len(retained),
            "retained": retained[:self.MAX_CANDIDATES],
            "unknown_count": len(unknown),
            "unknown": unknown[:self.MAX_CANDIDATES],
            "truncated": len(candidates) > len(selected),
            "deletion_performed": False,
        }

    def expire(self, *, confirm: bool, limit: int = MAX_CANDIDATES) -> dict:
        if not isinstance(confirm, bool):
            raise ValueError("confirm must be a boolean")
        preview = self.preview(limit=limit)
        if confirm is not True:
            return {
                **preview,
                "success": False,
                "code": "explicit_confirmation_required",
                "message": "No recording was deleted. Explicit owner confirmation is required.",
            }

        deleted = []
        failed = []
        for candidate in preview["candidates"]:
            artifact_id = candidate["artifact_id"]
            details = {
                "artifact_id": artifact_id,
                "consent_receipt_id": candidate["consent_receipt_id"],
            }
            try:
                self.audit.append(
                    event_type="voice_retention",
                    action="voice.audio.expire",
                    outcome="requested",
                    actor="local_owner",
                    details=details,
                )
            except Exception:
                failed.append({"artifact_id": artifact_id, "stage": "audit_preflight"})
                continue

            # Remove durable memory references before deleting the binary.
            # If reference cleanup fails, keep the audio artifact available for
            # a retry rather than creating an unrecoverable dangling reference.
            try:
                unlink = getattr(self.memory, "remove_artifact_references", None)
                unlinked = unlink(artifact_id) if callable(unlink) else 0
            except Exception as exc:
                failed.append({
                    "artifact_id": artifact_id,
                    "stage": "memory_reference_cleanup",
                    "error_type": type(exc).__name__,
                    "side_effect_may_have_occurred": True,
                })
                continue

            try:
                removed = self.artifacts.delete_artifact(artifact_id)
                if not removed:
                    failed.append({
                        "artifact_id": artifact_id,
                        "stage": "artifact_delete",
                        "memory_references_removed": unlinked,
                    })
                    continue
            except Exception as exc:
                failed.append({
                    "artifact_id": artifact_id,
                    "stage": "artifact_delete",
                    "memory_references_removed": unlinked,
                    "error_type": type(exc).__name__,
                    "side_effect_may_have_occurred": True,
                })
                continue

            deletion_record = {
                "artifact_id": artifact_id,
                "memory_references_removed": unlinked,
            }
            deleted.append(deletion_record)

            try:
                self.audit.append(
                    event_type="voice_retention",
                    action="voice.audio.expire",
                    outcome="completed",
                    actor="local_owner",
                    details={**details, "memory_references_removed": unlinked},
                )
            except Exception:
                failed.append({
                    "artifact_id": artifact_id,
                    "stage": "audit_completion",
                    "side_effect_may_have_occurred": True,
                })

        return {
            "success": not failed,
            "mode": "explicit_expiry_cleanup",
            "deletion_performed": bool(deleted),
            "requested_count": len(preview["candidates"]),
            "deleted_count": len(deleted),
            "deleted": deleted,
            "failed_count": len(failed),
            "failures": failed,
            "remaining_candidates": max(0, preview["expired_count"] - len(deleted)),
            "preview_truncated": preview["truncated"],
        }
