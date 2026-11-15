"""Reconcile the artifact index with its searchable memory mirror.

The artifact index is canonical. Memory is a derived lookup mirror and may be
rebuilt from the canonical index. Reconciliation is explicit and idempotent;
the default operation is a read-only preview.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


class ArtifactMemoryConsistencyService:
    MAX_RECORDS = 10_000
    MAX_REPORTED_IDS = 200

    def __init__(self, artifact_manager: Any) -> None:
        if artifact_manager is None or not hasattr(artifact_manager, "memory"):
            raise ValueError("artifact_manager with memory service is required")
        self.artifacts = artifact_manager
        self.memory = artifact_manager.memory

    @staticmethod
    def _index_by_id(records: list[dict]) -> tuple[dict[str, dict], Counter]:
        grouped: dict[str, list[dict]] = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("artifact mirror contains a non-object record")
            artifact_id = record.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise ValueError("artifact mirror contains a record without an artifact_id")
            grouped.setdefault(artifact_id, []).append(record)
        duplicates = Counter({key: len(value) for key, value in grouped.items() if len(value) > 1})
        return {key: values[-1] for key, values in grouped.items()}, duplicates

    @staticmethod
    def _canonical_fields(record: dict) -> dict:
        # Keep the full metadata record: it includes ownership, type, source,
        # path, timestamp, checksum and lifecycle metadata.
        return dict(record)

    def reconcile(self, *, apply: bool = False, limit: int = MAX_RECORDS) -> dict:
        if not isinstance(apply, bool):
            raise ValueError("apply must be a boolean")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= self.MAX_RECORDS:
            raise ValueError("limit must be between 0 and 10000")

        canonical = self.artifacts.get_all_artifacts()
        mirrored = self.memory.get_artifacts()
        if not isinstance(canonical, list) or not isinstance(mirrored, list):
            raise ValueError("artifact stores must return lists")
        if len(canonical) > self.MAX_RECORDS or len(mirrored) > self.MAX_RECORDS:
            raise ValueError("artifact store exceeds reconciliation bound")
        canonical_by_id, canonical_duplicates = self._index_by_id(canonical)
        mirror_by_id, mirror_duplicates = self._index_by_id(mirrored)

        missing = sorted(set(canonical_by_id) - set(mirror_by_id))
        stale = sorted(set(mirror_by_id) - set(canonical_by_id))
        mismatched = sorted(
            artifact_id
            for artifact_id in set(canonical_by_id).intersection(mirror_by_id)
            if self._canonical_fields(canonical_by_id[artifact_id])
            != self._canonical_fields(mirror_by_id[artifact_id])
        )
        duplicate_ids = sorted(set(canonical_duplicates) | set(mirror_duplicates))
        canonical_duplicate_ids = set(canonical_duplicates)
        affected = sorted(set(missing) | set(stale) | set(mismatched) | set(duplicate_ids))
        selected = affected[:limit]
        changes = {"added": 0, "removed": 0, "replaced": 0, "failed": 0}
        failures: list[dict] = []

        if apply:
            for artifact_id in selected:
                try:
                    if artifact_id in canonical_duplicate_ids:
                        changes["failed"] += 1
                        if len(failures) < self.MAX_REPORTED_IDS:
                            failures.append({
                                "artifact_id": artifact_id,
                                "error_type": "CanonicalIndexDuplicateId",
                            })
                        continue
                    canonical_record = canonical_by_id.get(artifact_id)
                    mirror_count = mirror_duplicates.get(artifact_id, 1 if artifact_id in mirror_by_id else 0)
                    if canonical_record is None:
                        if self.memory.remove_artifact(artifact_id):
                            changes["removed"] += 1
                        continue
                    if mirror_count > 1 or artifact_id in mismatched:
                        self.memory.remove_artifact(artifact_id)
                        self.memory.add_artifact(self._canonical_fields(canonical_record))
                        changes["replaced"] += 1
                    elif artifact_id in missing:
                        self.memory.add_artifact(self._canonical_fields(canonical_record))
                        changes["added"] += 1
                except Exception as exc:
                    changes["failed"] += 1
                    if len(failures) < self.MAX_REPORTED_IDS:
                        failures.append({
                            "artifact_id": artifact_id,
                            "error_type": type(exc).__name__,
                        })

        applied_changes = changes["added"] + changes["removed"] + changes["replaced"]
        return {
            "success": changes["failed"] == 0,
            "read_only": not apply,
            "mutations_performed": apply and applied_changes > 0,
            "canonical_store": "artifact_index",
            "mirror_store": "memory.artifacts",
            "canonical_count": len(canonical),
            "mirror_count": len(mirrored),
            "missing_in_memory": len(missing),
            "stale_in_memory": len(stale),
            "metadata_mismatches": len(mismatched),
            "duplicate_ids": len(duplicate_ids),
            "affected_ids": selected[:self.MAX_REPORTED_IDS],
            "truncated": len(affected) > len(selected),
            "changes": changes,
            "failures": failures,
            "remaining_findings": max(0, len(affected) - applied_changes),
        }
