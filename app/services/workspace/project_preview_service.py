from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.projects.project_paths import resolve_project_path


class ProjectPreviewService:
    """Persistent, safe preview registration for generated project versions."""

    MAX_RECORDS = 100

    def __init__(self, root: str | Path = "memory/project_previews.json"):
        self.store = AtomicJsonStore(root)

    @classmethod
    def _require_records(cls, data: Any) -> list:
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Project preview index must contain a list of records")
        seen_projects: set[tuple[str, str]] = set()
        for record in data:
            if not isinstance(record, dict):
                raise PersistenceIntegrityError("Project preview index contains an invalid record")
            project = record.get("project")
            version = record.get("version")
            if (
                not isinstance(project, str)
                or not isinstance(version, str)
                or resolve_project_path(project, version) is None
            ):
                raise PersistenceIntegrityError("Project preview index contains an invalid project reference")
            identity = (project, version)
            if identity in seen_projects:
                raise PersistenceIntegrityError("Project preview index contains duplicate project versions")
            seen_projects.add(identity)
            url = record.get("url")
            if not isinstance(url, str) or not cls._valid_url(url):
                raise PersistenceIntegrityError("Project preview index contains an unsafe URL")
            status = record.get("status")
            if not isinstance(status, str) or status not in {"registered", "stopped"}:
                raise PersistenceIntegrityError("Project preview index contains an invalid status")
            if not isinstance(record.get("updated_at"), str):
                raise PersistenceIntegrityError("Project preview index contains an invalid timestamp")
        return data

    @staticmethod
    def _valid_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError:
            # urlparse raises for malformed IPv6 authorities and invalid port text/ranges.
            return False
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and port is not None
            and 1 <= port <= 65535
            and not parsed.username and not parsed.password
        )

    def register(self, project: str, version: str, url: str) -> dict[str, Any]:
        project_path = resolve_project_path(project, version)
        if project_path is None or not project_path.is_dir():
            return {"success": False, "code": "project_not_found",
                    "message": "Project version was not found."}
        if not self._valid_url(url):
            return {"success": False, "code": "unsafe_preview_url",
                    "message": "Preview URLs must use localhost or loopback with an explicit port."}

        record = {"project": project, "version": version, "url": url,
                  "status": "registered", "updated_at": datetime.now(UTC).isoformat()}

        def mutate(data: Any) -> Any:
            records = self._require_records(data)
            records[:] = [item for item in records if not (
                isinstance(item, dict) and item.get("project") == project
                and item.get("version") == version)]
            records.append(record)
            del records[:-self.MAX_RECORDS]
            return records

        self.store.update(mutate, default=[])
        return {"success": True, "preview": record}

    def stop(self, project: str, version: str) -> dict[str, Any]:
        def mutate(data: Any) -> Any:
            records = self._require_records(data)
            changed = False
            for item in records:
                if isinstance(item, dict) and item.get("project") == project and item.get("version") == version:
                    item["status"] = "stopped"
                    item["updated_at"] = datetime.now(UTC).isoformat()
                    changed = True
            return records

        data = self.store.update(mutate, default=[])
        current = next((x for x in data if isinstance(x, dict)
                        and x.get("project") == project and x.get("version") == version), None)
        return {"success": current is not None, "preview": current}

    def get(self, project: str, version: str) -> dict[str, Any]:
        data = self._require_records(self.store.read([]))
        current = next((x for x in data if isinstance(x, dict)
                        and x.get("project") == project and x.get("version") == version), None)
        return {"success": current is not None, "preview": current}
