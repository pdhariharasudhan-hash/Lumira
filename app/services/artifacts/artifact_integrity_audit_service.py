"""Read-only artifact index/content audit for data-foundation maintenance.

This service reports index inconsistencies and content-integrity findings. It
never rewrites the index, moves files, or deletes artifacts.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class ArtifactIntegrityAuditService:
    """Perform bounded, non-mutating integrity audits over an artifact manager."""

    MAX_RECORDS = 100_000
    MAX_FILE_BYTES = 100_000_000
    MAX_TOTAL_HASH_BYTES = 100_000_000
    MAX_FINDINGS = 500
    CHUNK_BYTES = 1024 * 1024

    def __init__(self, artifact_manager: Any):
        if artifact_manager is None:
            raise ValueError("artifact_manager is required")
        base_path = getattr(artifact_manager, "base_path", None)
        if base_path is None:
            raise ValueError("artifact_manager must expose base_path")
        self.artifacts = artifact_manager
        self.base_path = Path(base_path).resolve()

    def audit(self, limit: int = 10_000, *, verify_hashes: bool = True) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= self.MAX_RECORDS:
            raise ValueError("limit must be between 0 and 100000")
        if not isinstance(verify_hashes, bool):
            raise ValueError("verify_hashes must be a boolean")

        records = self.artifacts.get_all_artifacts()
        if not isinstance(records, list):
            raise ValueError("artifact manager returned an invalid index")
        if len(records) > self.MAX_RECORDS:
            raise ValueError("artifact index exceeds audit bound")

        selected = records[-limit:] if limit else []
        findings: list[dict] = []
        finding_total = 0
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        counts = {
            "checked": 0,
            "healthy": 0,
            "missing": 0,
            "invalid_path": 0,
            "size_mismatch": 0,
            "checksum_mismatch": 0,
            "checksum_unavailable": 0,
            "duplicate_id": 0,
            "duplicate_path": 0,
            "oversized": 0,
            "hash_budget_exhausted": 0,
            "path_valid": 0,
            "invalid_record": 0,
        }

        def add(code: str, artifact_id: str | None) -> None:
            nonlocal finding_total
            finding_total += 1
            counts[code] += 1
            if len(findings) < self.MAX_FINDINGS:
                findings.append({"code": code, "artifact_id": artifact_id})

        bytes_hashed = 0
        for record in selected:
            counts["checked"] += 1
            if not isinstance(record, dict):
                add("invalid_record", None)
                continue
            artifact_id = record.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                add("invalid_record", None)
                continue
            if artifact_id in seen_ids:
                add("duplicate_id", artifact_id)
            seen_ids.add(artifact_id)

            raw_path = record.get("file")
            if not isinstance(raw_path, str) or not raw_path:
                add("invalid_record", artifact_id)
                continue
            try:
                path = Path(raw_path).resolve()
                if path == self.base_path or self.base_path not in path.parents:
                    add("invalid_path", artifact_id)
                    continue
            except (OSError, RuntimeError, ValueError):
                add("invalid_path", artifact_id)
                continue

            path_key = str(path).casefold()
            if path_key in seen_paths:
                add("duplicate_path", artifact_id)
            seen_paths.add(path_key)

            try:
                if not path.is_file():
                    add("missing", artifact_id)
                    continue
                size = path.stat().st_size
                if size < 0 or size > self.MAX_FILE_BYTES:
                    add("oversized", artifact_id)
                    continue
            except OSError:
                add("missing", artifact_id)
                continue

            expected_size = record.get("content_bytes")
            if expected_size is not None and (
                isinstance(expected_size, bool)
                or not isinstance(expected_size, int)
                or expected_size < 0
                or expected_size != size
            ):
                add("size_mismatch", artifact_id)
                continue

            counts["path_valid"] += 1
            expected_hash = record.get("content_sha256")
            if not verify_hashes:
                continue
            if bytes_hashed + size > self.MAX_TOTAL_HASH_BYTES:
                add("hash_budget_exhausted", artifact_id)
                continue
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                add("checksum_unavailable", artifact_id)
                continue

            digest = hashlib.sha256()
            try:
                with path.open("rb") as handle:
                    while True:
                        chunk = handle.read(self.CHUNK_BYTES)
                        if not chunk:
                            break
                        digest.update(chunk)
                bytes_hashed += size
            except OSError:
                add("missing", artifact_id)
                continue
            if digest.hexdigest() != expected_hash:
                add("checksum_mismatch", artifact_id)
                continue
            counts["healthy"] += 1

        return {
            "success": True,
            "read_only": True,
            "mutations_performed": False,
            "verify_hashes": verify_hashes,
            "total_index_records": len(records),
            "selected_records": len(selected),
            "finding_limit": self.MAX_FINDINGS,
            "bytes_hashed": bytes_hashed,
            "hash_byte_budget": self.MAX_TOTAL_HASH_BYTES,
            "findings_truncated": finding_total > len(findings),
            "counts": counts,
            "findings": findings,
        }
