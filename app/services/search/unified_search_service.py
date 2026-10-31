from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.history.pipeline_history_service import PipelineHistoryService
from app.services.memory.memory_service import MemoryService
from app.services.projects.project_discovery_service import ProjectDiscoveryService
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.projects.project_paths import resolve_project_path
from app.services.work_items.work_item_service import WorkItemService
from app.services.devices.device_registry_service import DeviceRegistryService


class UnifiedSearchService:
    """Bounded local search across projects, files, artifacts and durable state."""

    STOP_WORDS = {
        "find", "everything", "related", "about", "the", "my", "for", "with",
        "show", "search", "all", "of", "to", "in", "on", "please", "everything",
    }
    TEXT_EXTENSIONS = {".py", ".md", ".txt", ".json", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".toml", ".yaml", ".yml"}
    CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}

    def __init__(self):
        self.projects = ProjectDiscoveryService()
        self.memory = MemoryService()
        self.artifacts = ArtifactManagerService()
        self.pipeline_history = PipelineHistoryService()
        self.sessions = SessionManagerService()
        self.work_items = WorkItemService()
        self.devices = DeviceRegistryService()

    @classmethod
    def _terms(cls, query: str) -> list[str]:
        """Normalize a bounded query into a small set of searchable terms."""
        if not isinstance(query, str) or not query.strip():
            return []
        bounded_query = query[:4000].lower()
        terms = [term for term in re.findall(r"[a-z0-9_+\-]+|[\u0B80-\u0BFF]+", bounded_query)
                 if len(term) > 1 and term not in cls.STOP_WORDS]
        # Avoid repeated work on huge or repetitive user-supplied search strings.
        return list(dict.fromkeys(terms))[:32]

    @classmethod
    def _matches(cls, searchable: str, query: str) -> bool:
        terms = cls._terms(query)
        lowered = searchable.lower()
        return bool(terms) and all(term in lowered for term in terms)

    @staticmethod
    def _read_text(path: Path, max_bytes: int = 1_000_000) -> str | None:
        try:
            if not path.is_file() or path.stat().st_size > max_bytes:
                return None
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _safe_snippet(text: str, limit: int = 500) -> str:
        return MemoryService._safe_text(text[:limit])

    def search_projects(self, query: str) -> list[dict]:
        return [project for project in self.projects.get_projects()
                if self._matches(json.dumps(project, ensure_ascii=False), query)]

    def search_project_versions(self, query: str) -> list[dict]:
        results = []
        for project in self.projects.get_projects():
            for version in self.projects.get_versions(project["project"]):
                if self._matches(json.dumps(version, ensure_ascii=False), query):
                    results.append({"project": project["project"], **version})
                    if len(results) >= 200:
                        return results
        return results

    def search_project_files(self, query: str) -> list[dict]:
        root = Path("generated")
        resolved_root = root.resolve()
        results = []
        if not root.exists():
            return results
        try:
            for path in root.glob("*/v*/*"):
                if len(results) >= 200:
                    break
                if path.suffix.lower() not in self.TEXT_EXTENSIONS or path.name.lower() in {".env", "secrets.json", "credentials.json"}:
                    continue
                resolved = path.resolve()
                relative_parts = path.relative_to(root).parts
                if (
                    resolved_root not in resolved.parents
                    or len(relative_parts) != 3
                    or resolve_project_path(*relative_parts) != resolved
                ):
                    continue
                content = self._read_text(resolved)
                if content is None:
                    continue
                relative = str(path.relative_to(root))
                if self._matches(f"{relative} {content}", query):
                    kind = "code" if path.suffix.lower() in self.CODE_EXTENSIONS else "documentation"
                    results.append({
                        "project": path.parts[1],
                        "version": path.parts[2],
                        "path": relative,
                        "kind": kind,
                        "snippet": self._safe_snippet(content),
                    })
        except OSError:
            return results
        return results

    def search_documentation(self, query: str) -> list[dict]:
        root = Path("docs")
        results = []
        if not root.exists():
            return results
        resolved_root = root.resolve()
        for path in root.rglob("*.md"):
            if len(results) >= 200:
                break
            resolved = path.resolve()
            if resolved_root not in resolved.parents:
                continue
            content = self._read_text(resolved)
            if content is not None and self._matches(f"{path} {content}", query):
                results.append({"path": str(path), "kind": "documentation", "snippet": self._safe_snippet(content)})
        return results

    def search_artifacts(self, query: str) -> list[dict]:
        results = []
        for artifact in self.artifacts.get_all_artifacts():
            if artifact.get("archived", False):
                continue
            # The persisted file path is an implementation detail, not searchable
            # user metadata. Keep it available only for the guarded content read.
            public_metadata = {
                key: value for key, value in artifact.items() if key != "file"
            }
            searchable = json.dumps(public_metadata, ensure_ascii=False)
            text = None
            if Path(str(artifact.get("file", ""))).suffix.lower() in {".txt", ".md", ".json", ".csv", ".svg"}:
                try:
                    path = self.artifacts.get_artifact_path(artifact["artifact_id"])
                    text = self._read_text(path) if path else None
                except (ValueError, OSError, KeyError):
                    text = None
                if text:
                    searchable += " " + text
            if self._matches(searchable, query):
                result = dict(public_metadata)
                if text:
                    result["snippet"] = self._safe_snippet(text)
                results.append(result)
                if len(results) >= 200:
                    break
        return results

    def search_memory(self, query: str) -> dict:
        if not self._terms(query):
            return {}
        memory = self.memory.get_all()
        return {
            key: value for key, value in memory.items()
            if self._matches(json.dumps(value, ensure_ascii=False), query)
        }

    def search_pipeline_history(self, query: str) -> list[dict]:
        return self._search_records(self.pipeline_history.get_history(), query)

    def search_feature_history(self, query: str) -> list[dict]:
        return self._search_records(self.memory.get_feature_history(), query)

    @classmethod
    def _search_records(cls, records: list[dict], query: str) -> list[dict]:
        if not cls._terms(query):
            return []
        return [record for record in records
                if cls._matches(json.dumps(record, ensure_ascii=False), query)][:200]

    def search_notes(self, query: str) -> list[dict]:
        if not self._terms(query):
            return []
        try:
            from app.services.notepad_service import NotepadService
            return NotepadService().search_notes(query, limit=100)
        except (ValueError, OSError):
            return []

    def search_workflows(self, query: str) -> list[dict]:
        """Search durable workflows and their task metadata."""
        if not self._terms(query):
            return []
        results = []
        for workflow in self.work_items.list_workflows(limit=200):
            searchable = json.dumps(workflow, ensure_ascii=False)
            if self._matches(searchable, query):
                results.append({
                    **workflow,
                    "type": "workflow",
                    "title": workflow.get("title", "Untitled workflow"),
                    "source": "work_items",
                    "reference": workflow.get("workflow_id"),
                    "timestamp": workflow.get("updated_at") or workflow.get("created_at"),
                    "project": workflow.get("project_id"),
                    "relevance": sum(
                        1 for term in self._terms(query)
                        if term in searchable.lower()
                    ),
                })
            if len(results) >= 200:
                break
        return results

    def search_devices(self, query: str) -> list[dict]:
        """Search only the persisted device registry; never probe hardware."""
        if not self._terms(query):
            return []
        return [
            device for device in self.devices.list_devices(limit=200)
            if self._matches(json.dumps(device, ensure_ascii=False), query)
        ][:200]

    @classmethod
    def _build_unified_items(cls, grouped_results: dict[str, Any], query: str) -> list[dict]:
        """Build a bounded, backwards-compatible flat list with common metadata."""
        items = []
        terms = cls._terms(query)
        for result_type, records in grouped_results.items():
            if result_type == "items" or not isinstance(records, (list, dict)):
                continue
            if isinstance(records, dict):
                iterable = [
                    {"memory_key": key, "value": value}
                    for key, value in records.items()
                ]
            else:
                iterable = records
            for record in iterable:
                if isinstance(record, dict):
                    payload = record
                else:
                    payload = {"value": record}
                searchable = json.dumps(payload, ensure_ascii=False).lower()
                score = sum(1 for term in terms if term in searchable)
                identifier = next((
                    payload.get(key) for key in (
                        "reference", "artifact_id", "workflow_id", "goal_id",
                        "session_id", "project_id", "version_id", "experience_id",
                        "decision_id", "learning_id", "id", "path"
                    ) if payload.get(key) is not None
                ), None)
                title = next((
                    payload.get(key) for key in (
                        "title", "name", "project", "path", "file", "memory_key",
                        "summary", "request"
                    ) if isinstance(payload.get(key), str) and payload.get(key).strip()
                ), result_type.replace("_", " ").title())
                timestamp = next((
                    payload.get(key) for key in (
                        "timestamp", "updated_at", "created_at", "last_updated"
                    ) if payload.get(key) is not None
                ), None)
                project = payload.get("project_id", payload.get("project"))
                snippet = next((
                    payload.get(key) for key in (
                        "snippet", "summary", "description", "request", "lesson", "observation"
                    ) if isinstance(payload.get(key), str) and payload.get(key).strip()
                ), None)
                items.append({
                    "type": result_type,
                    "title": cls._safe_snippet(str(title), 180),
                    "relevance": score,
                    "source": payload.get("source", result_type),
                    "timestamp": timestamp,
                    "project": project,
                    "reference": identifier,
                    "snippet": cls._safe_snippet(snippet, 500) if snippet else None,
                    "record": payload,
                })
                if len(items) >= 1000:
                    return sorted(items, key=lambda item: (item["relevance"], str(item.get("timestamp") or "")), reverse=True)
        return sorted(items, key=lambda item: (item["relevance"], str(item.get("timestamp") or "")), reverse=True)

    def search_sessions(self, query: str) -> list[dict]:
        if not self._terms(query):
            return []
        return [session for session in self.sessions.list_sessions(limit=200)
                if self._matches(json.dumps({k: v for k, v in session.items() if k != "cognitive_state"}, ensure_ascii=False), query)]

    def search_conversations(self, query: str) -> list[dict]:
        if not self._terms(query):
            return []
        results = []
        for session in self.sessions.list_sessions(limit=200):
            conversation = {
                "session_id": session.get("session_id"),
                "conversation_id": session.get("conversation_id"),
                "summary": session.get("conversation", {}).get("summary", ""),
                "recent_messages": session.get("recent_messages", []),
            }
            if self._matches(json.dumps(conversation, ensure_ascii=False), query):
                results.append(conversation)
        return results

    def search_all(self, query: str) -> dict[str, Any]:
        if not self._terms(query):
            return {key: [] for key in (
                "projects", "project_versions", "files", "code", "documentation",
                "voice_ideas", "images", "artifacts", "memory", "feature_history",
                "pipeline_history", "sessions", "conversations", "goals", "decisions",
                "experiences", "learning", "memory_links", "notes", "workflows", "devices", "items",
            )}
        memory = self.memory.get_all()
        artifacts = self.search_artifacts(query)
        files = self.search_project_files(query)
        grouped = {
            "projects": self.search_projects(query),
            "project_versions": self.search_project_versions(query),
            "files": files,
            "code": [item for item in files if item["kind"] == "code"],
            "documentation": self.search_documentation(query),
            "voice_ideas": [item for item in artifacts if item.get("type") in {"audio", "transcripts", "summaries"}],
            "images": [item for item in artifacts if item.get("type") in {"images", "diagrams", "blueprints", "schematics"}],
            "artifacts": artifacts,
            "memory": self.search_memory(query),
            "feature_history": self.search_feature_history(query),
            "pipeline_history": self.search_pipeline_history(query),
            "sessions": self.search_sessions(query),
            "conversations": self.search_conversations(query),
            "goals": self._search_records(memory.get("goals", []), query),
            "decisions": self._search_records(memory.get("decisions", []), query),
            "experiences": self._search_records(memory.get("experiences", []), query),
            "learning": self._search_records(memory.get("learning_records", []), query),
            "memory_links": self._search_records(memory.get("memory_links", []), query),
            "notes": self.search_notes(query),
            "workflows": self.search_workflows(query),
            "devices": self.search_devices(query),
        }
        grouped["items"] = self._build_unified_items(grouped, query)
        return MemoryService._redact_nested(grouped)
