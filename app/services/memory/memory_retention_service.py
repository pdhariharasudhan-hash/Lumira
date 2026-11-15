"""Explicit, preview-only retention planning for durable memory records."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


class MemoryRetentionService:
    """Calculate retention candidates without deleting or mutating memory."""

    MAX_RECORDS = 100_000
    MAX_REPORTED_RECORDS = 500
    MAX_RETENTION_DAYS = 36_500
    PROTECTED_FLAGS = ("pinned", "legal_hold", "retention_exempt")

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _record_id(record: dict[str, Any]) -> str | None:
        for key in (
            "memory_id", "experience_id", "decision_id", "goal_id",
            "artifact_id", "session_id", "id",
        ):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def plan(
        self,
        records: Any,
        retention_days: Mapping[str, int],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not isinstance(records, list) or len(records) > self.MAX_RECORDS:
            raise ValueError("records must be a bounded list")
        if not isinstance(retention_days, Mapping):
            raise ValueError("retention_days must be a mapping")
        policies: dict[str, int] = {}
        for category, days in retention_days.items():
            if not isinstance(category, str) or not category.strip():
                raise ValueError("retention category names must be non-empty strings")
            if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= self.MAX_RETENTION_DAYS:
                raise ValueError("retention days must be between 1 and 36500")
            policies[category.strip()] = days

        reference = now if now is not None else datetime.now(timezone.utc)
        if not isinstance(reference, datetime):
            raise ValueError("now must be a datetime")
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        reference = reference.astimezone(timezone.utc)

        # Detect duplicate IDs across every record before considering eligibility.
        # A duplicate identity is never safe to classify as a deletion candidate.
        identifier_counts: dict[str, int] = {}
        for item in records:
            if isinstance(item, dict):
                identifier = self._record_id(item)
                if identifier is not None:
                    identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1

        candidates = []
        protected = []
        retained = []
        unknown = []
        for record in records:
            if not isinstance(record, dict):
                unknown.append({"reason": "invalid_record"})
                continue
            identifier = self._record_id(record)
            if identifier is not None and identifier_counts.get(identifier, 0) > 1:
                unknown.append({"id": identifier, "reason": "duplicate_record_id"})
                continue
            category = record.get("type") or record.get("category")
            if not isinstance(category, str) or category not in policies:
                unknown.append({"id": identifier, "reason": "no_retention_policy"})
                continue
            if any(record.get(flag) is True for flag in self.PROTECTED_FLAGS):
                protected.append({"id": identifier, "reason": "protected"})
                continue
            # Verified learning and active goals are durable knowledge, not
            # disposable cache entries. They require an explicit owner decision.
            if record.get("verified") is True or record.get("status") == "active":
                protected.append({"id": identifier, "reason": "verified_or_active"})
                continue
            timestamp = self._parse_timestamp(
                record.get("updated_at") or record.get("created_at") or record.get("timestamp")
            )
            if timestamp is None:
                unknown.append({"id": identifier, "reason": "timestamp_unavailable"})
                continue
            expires_at = timestamp + timedelta(days=policies[category])
            if expires_at <= reference:
                if identifier is None:
                    unknown.append({"id": identifier, "reason": "missing_id"})
                    continue
                candidates.append({
                    "id": identifier,
                    "category": category,
                    "last_updated": timestamp.isoformat(),
                    "expires_at": expires_at.isoformat(),
                })
            else:
                retained.append({
                    "id": identifier,
                    "category": category,
                    "expires_at": expires_at.isoformat(),
                })

        report_limit = self.MAX_REPORTED_RECORDS
        return {
            "success": True,
            "mode": "preview_only",
            "reference_time": reference.isoformat(),
            "candidate_count": len(candidates),
            "candidates": candidates[:report_limit],
            "candidate_truncated": len(candidates) > report_limit,
            "protected_count": len(protected),
            "protected": protected[:report_limit],
            "protected_truncated": len(protected) > report_limit,
            "retained_count": len(retained),
            "retained": retained[:report_limit],
            "retained_truncated": len(retained) > report_limit,
            "unknown_count": len(unknown),
            "unknown": unknown[:report_limit],
            "unknown_truncated": len(unknown) > report_limit,
            "reported_record_limit": report_limit,
            "deletion_performed": False,
        }
