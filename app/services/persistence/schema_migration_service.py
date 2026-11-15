"""Versioned, fail-closed JSON document migrations for Lumira data stores."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable
import json
import os
import tempfile

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


@dataclass(frozen=True)
class SchemaMigration:
    version: int
    name: str
    apply: Callable[[dict[str, Any]], dict[str, Any]]


class SchemaMigrationService:
    """Apply caller-defined migrations without silently repairing corrupt data."""

    MAX_MIGRATIONS = 50
    MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.store = AtomicJsonStore(self.path)

    @staticmethod
    def _validate_migrations(migrations: Iterable[SchemaMigration]) -> list[SchemaMigration]:
        items = list(migrations)
        if len(items) > SchemaMigrationService.MAX_MIGRATIONS:
            raise ValueError("too many schema migrations")
        versions = [item.version for item in items]
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in versions):
            raise ValueError("migration versions must be positive integers")
        if len(set(versions)) != len(versions):
            raise ValueError("migration versions must be unique")
        if any(not isinstance(item.name, str) or not item.name.strip() for item in items):
            raise ValueError("migration names are required")
        if any(not callable(item.apply) for item in items):
            raise ValueError("migration apply functions are required")
        return sorted(items, key=lambda item: item.version)

    def _read_document(self) -> dict[str, Any]:
        if not self.path.exists():
            raise PersistenceIntegrityError("data store does not exist; migration will not create an empty replacement")
        size = self.path.stat().st_size
        if size <= 0 or size > self.MAX_DOCUMENT_BYTES:
            raise PersistenceIntegrityError("data store size is invalid")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PersistenceIntegrityError("data store is corrupt; original file was preserved") from exc
        if not isinstance(value, dict):
            raise PersistenceIntegrityError("versioned data store must contain a JSON object")
        version = value.get("schema_version", 0)
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise PersistenceIntegrityError("schema_version is invalid")
        return value

    def _backup(self) -> dict[str, str]:
        raw = self.path.read_bytes()
        digest = sha256(raw).hexdigest()
        backup = self.path.with_name(f"{self.path.name}.pre-migration-{digest[:12]}.bak")
        if not backup.exists():
            with backup.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        return {"path": str(backup), "sha256": digest, "bytes": str(len(raw))}

    def _atomic_replace(self, value: dict[str, Any]) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.migration-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except (OSError, TypeError, ValueError, RecursionError) as exc:
            raise PersistenceIntegrityError("migration write failed; original store must be restored from its backup") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def migrate(self, migrations: Iterable[SchemaMigration], target_version: int | None = None) -> dict[str, Any]:
        ordered = self._validate_migrations(migrations)
        available = {item.version: item for item in ordered}
        outcome: dict[str, Any] = {}

        def apply_locked(document: Any) -> dict[str, Any]:
            if not self.path.exists():
                raise PersistenceIntegrityError("data store does not exist; migration will not create an empty replacement")
            if self.path.stat().st_size <= 0 or self.path.stat().st_size > self.MAX_DOCUMENT_BYTES:
                raise PersistenceIntegrityError("data store size is invalid")
            if not isinstance(document, dict):
                raise PersistenceIntegrityError("versioned data store must contain a JSON object")
            current = document.get("schema_version", 0)
            if isinstance(current, bool) or not isinstance(current, int) or current < 0:
                raise PersistenceIntegrityError("schema_version is invalid")
            target = max(available, default=current) if target_version is None else target_version
            if isinstance(target, bool) or not isinstance(target, int) or target < current:
                raise ValueError("target_version must be an integer not lower than current schema")
            if target > max(available, default=current):
                raise ValueError("target_version has no registered migration")
            if target == current:
                outcome.update({
                    "changed": False, "from_version": current, "to_version": current,
                    "applied": [], "backup": None,
                })
                return outcome

            pending = list(range(current + 1, target + 1))
            missing = [version for version in pending if version not in available]
            if missing:
                raise PersistenceIntegrityError(f"migration chain is incomplete at version {missing[0]}")

            backup = self._backup()
            working = dict(document)
            applied = []
            for version in pending:
                migration = available[version]
                try:
                    result = migration.apply(dict(working))
                except Exception as exc:
                    raise PersistenceIntegrityError(
                        f"migration {migration.name} failed; original store remains preserved"
                    ) from exc
                if not isinstance(result, dict):
                    raise PersistenceIntegrityError(
                        f"migration {migration.name} returned a non-object document"
                    )
                if result.get("schema_version") != version:
                    raise PersistenceIntegrityError(
                        f"migration {migration.name} must set schema_version={version}"
                    )
                working = result
                applied.append({"version": version, "name": migration.name})

            document.clear()
            document.update(working)
            outcome.update({
                "changed": True, "from_version": current, "to_version": target,
                "applied": applied, "backup": backup,
            })
            return outcome

        # AtomicJsonStore holds its cross-process lock for the entire migration,
        # preventing a concurrent writer from being overwritten by stale data.
        self.store.update(apply_locked, {})
        return dict(outcome)
