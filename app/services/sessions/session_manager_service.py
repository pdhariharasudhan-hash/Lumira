from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)
from app.services.history.event_logger_service import EventLoggerService


SESSION_SCHEMA_VERSION = 1
MAX_RECENT_MESSAGES = 20
MAX_CONTEXT_SNAPSHOTS = 30
SECRET_PATTERN = re.compile(
    r"(?i)(password|api[_ -]?key|access[_ -]?token|secret|authorization)"
    r"(\s*[:=]\s*)([^\r\n]+)|\bBearer\s+[A-Za-z0-9._~+/-]+=*"
)
SECRET_KEY_PATTERN = re.compile(
    r"(?i)password|api[_ -]?key|access[_ -]?token|secret|authorization"
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _redact_secrets(text: str) -> str:
    return SECRET_PATTERN.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}[REDACTED]"
            if match.group(1)
            else "Bearer [REDACTED]"
        ),
        text,
    )


def _redact_value(value):
    if isinstance(value, str):
        return _redact_secrets(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            safe[str(key)] = "[REDACTED]" if SECRET_KEY_PATTERN.search(str(key)) else _redact_value(item)
        return safe
    return value


redact_sensitive_text = _redact_secrets
redact_sensitive_value = _redact_value


class SessionManagerService:
    """Own durable short-term session, conversation, and resume snapshots."""

    def __init__(self, file_path: str | Path = "memory/cognitive_sessions.json"):
        self.store = AtomicJsonStore(file_path)
        self.emit_events = Path(file_path) == Path("memory/cognitive_sessions.json")
        if not Path(file_path).exists():
            self.store.write({"schema_version": SESSION_SCHEMA_VERSION, "sessions": []})

    def _log_event(self, event: str, session_id: str, **metadata) -> None:
        if not self.emit_events:
            return
        EventLoggerService().log(
            event=event,
            source="session_manager",
            data={"session_id": session_id, **metadata},
        )

    @staticmethod
    def _validate_document(document: Any) -> dict:
        if not isinstance(document, dict):
            raise PersistenceIntegrityError("Session store root must be an object")
        version = document.get("schema_version")
        if version != SESSION_SCHEMA_VERSION:
            raise PersistenceIntegrityError(
                f"Unsupported session schema version: {version!r}"
            )
        if not isinstance(document.get("sessions"), list):
            raise PersistenceIntegrityError("Session store sessions must be a list")
        required = {
            "session_id",
            "conversation_id",
            "created_at",
            "updated_at",
            "status",
            "workspace_id",
            "conversation",
            "recent_messages",
            "context_snapshots",
            "schema_version",
        }
        for session in document["sessions"]:
            if not isinstance(session, dict) or not required.issubset(session):
                raise PersistenceIntegrityError("Session record is incomplete")
            if session["schema_version"] != SESSION_SCHEMA_VERSION:
                raise PersistenceIntegrityError("Unsupported session record schema version")
            if session["status"] not in {"active", "paused", "closed"}:
                raise PersistenceIntegrityError("Session record has an invalid status")
            if not isinstance(session["conversation"], dict):
                raise PersistenceIntegrityError("Session conversation must be an object")
            if not isinstance(session["recent_messages"], list):
                raise PersistenceIntegrityError("Session messages must be a list")
            if not isinstance(session["context_snapshots"], list):
                raise PersistenceIntegrityError("Session snapshots must be a list")
        return document

    def create_session(
        self,
        workspace_id: str = "default",
        project_id: str | None = None,
    ) -> dict:
        now = _timestamp()
        session = {
            "session_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "workspace_id": workspace_id or "default",
            "project_id": project_id,
            "active_project": project_id,
            "active_version": None,
            "active_mode": None,
            "current_goal": None,
            "goal_id": None,
            "last_command": None,
            "conversation": {
                "summary": "",
                "current_topic": "",
                "active_objective": "",
                "pending_questions": [],
                "recent_references": [],
                "language_context": "en",
            },
            "recent_messages": [],
            "cognitive_state": None,
            "context_snapshots": [],
            "schema_version": SESSION_SCHEMA_VERSION,
        }

        def add(document):
            self._validate_document(document)
            document["sessions"].append(session)
            return deepcopy(session)

        created = self.store.update(
            add,
            {"schema_version": SESSION_SCHEMA_VERSION, "sessions": []},
        )
        self._log_event("session_created", created["session_id"], workspace_id=created["workspace_id"])
        return created

    def get_session(self, session_id: str) -> dict | None:
        document = self._validate_document(self.store.read())
        for session in document["sessions"]:
            if session.get("session_id") == session_id:
                return deepcopy(session)
        return None

    def resolve_session(
        self,
        session_id: str | None = None,
        workspace_id: str = "default",
        project_id: str | None = None,
    ) -> dict:
        if session_id:
            session = self.get_session(session_id)
            if session is None:
                raise KeyError("session not found")
            if session["status"] == "closed":
                raise ValueError("session is closed; resume it explicitly first")
            if session["status"] == "paused":
                session = self.resume_session(session_id)
            self._log_event("session_loaded", session_id, status=session["status"])
            return session
        return self.create_session(workspace_id, project_id)

    def list_sessions(self, limit: int = 50) -> list[dict]:
        document = self._validate_document(self.store.read())
        sessions = sorted(
            document["sessions"],
            key=lambda item: (item.get("updated_at", ""), item.get("session_id", "")),
            reverse=True,
        )
        return [deepcopy(item) for item in sessions[: max(0, min(limit, 200))]]

    def _mutate_session(self, session_id: str, callback) -> dict:
        def update(document):
            self._validate_document(document)
            for index, session in enumerate(document["sessions"]):
                if session.get("session_id") == session_id:
                    callback(session)
                    session["updated_at"] = _timestamp()
                    document["sessions"][index] = session
                    return deepcopy(session)
            raise KeyError("session not found")

        return self.store.update(
            update,
            {"schema_version": SESSION_SCHEMA_VERSION, "sessions": []},
        )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("unsupported conversation role")
        message = {
            "message_id": str(uuid4()),
            "role": role,
            "content": _redact_secrets(content)[:4000],
            "metadata": deepcopy(metadata or {}),
            "created_at": _timestamp(),
        }

        def append(session):
            recent = session.setdefault("recent_messages", [])
            recent.append(message)
            session["recent_messages"] = recent[-MAX_RECENT_MESSAGES:]
            session["last_command"] = message["content"] if role == "user" else session.get("last_command")

        self._mutate_session(session_id, append)
        return deepcopy(message)

    def save_cognitive_state(
        self,
        session_id: str,
        state: dict,
        goal_id: str | None = None,
        success: bool = True,
    ) -> dict:
        conversation = state.get("conversation") or {}
        goal = state.get("goal") or {}
        objective = state.get("objective") or {}
        verification = state.get("verification") or {}
        reflection = state.get("reflection") or {}
        constraints = state.get("constraints") or {}
        mode = state.get("mode") or {}
        execution = state.get("execution_context") or {}

        cognitive = {
            "state_id": str(uuid4()),
            "session_id": session_id,
            "objective": _redact_secrets(objective.get("primary_objective", "")),
            "goal_id": goal_id,
            "goal": _redact_secrets(goal.get("primary_goal", "")),
            "selected_action": _redact_secrets((state.get("decision") or {}).get("selected_option", "")),
            "decision_confidence": float((state.get("decision") or {}).get("confidence") or 0.0),
            "mode": mode.get("active_mode"),
            "execution_status": "completed" if success else "failed",
            "verification_status": "ready" if verification.get("ready_for_execution") else "not_ready",
            "reflection_status": reflection.get("overall_quality"),
            "confidence": float(reflection.get("confidence") or goal.get("confidence") or 0.0),
            "blockers": (
                list(constraints.get("missing_information", []))
                + list(constraints.get("risks", []))
            )[:20],
            "updated_at": _timestamp(),
            "source_execution_id": execution.get("execution_id"),
            "schema_version": SESSION_SCHEMA_VERSION,
        }

        def save(session):
            session["cognitive_state"] = cognitive
            session["cognitive_state_id"] = cognitive["state_id"]
            session["goal_id"] = goal_id
            session["current_goal"] = goal.get("primary_goal") or session.get("current_goal")
            session["active_mode"] = mode.get("active_mode") or session.get("active_mode")
            if conversation:
                stored = session.setdefault("conversation", {})
                stored["summary"] = _redact_secrets(conversation.get("conversation_summary", ""))[:2000]
                stored["current_topic"] = _redact_secrets(conversation.get("current_topic", ""))[:500]
                stored["active_objective"] = _redact_secrets(objective.get("primary_objective", ""))[:500]
                stored["pending_questions"] = list(conversation.get("pending_questions", []))[:20]
                stored["language_context"] = conversation.get("detected_language", "en")
                stored["recent_references"] = list(session.get("conversation", {}).get("recent_references", []))[-20:]
            snapshots = session.setdefault("context_snapshots", [])
            snapshots.append({
                "snapshot_id": str(uuid4()),
                "session_id": session_id,
                "active_project": session.get("active_project"),
                "active_version": session.get("active_version"),
                "active_mode": cognitive["mode"],
                "goal_id": goal_id,
                "recent_artifacts": list(session.get("recent_artifact_ids", []))[-10:],
                "recent_decisions": list(session.get("recent_decision_ids", []))[-10:],
                "recent_memory_ids": list(session.get("recent_memory_ids", []))[-10:],
                "pending_tasks": [],
                "blockers": cognitive["blockers"],
                "created_at": _timestamp(),
                "schema_version": SESSION_SCHEMA_VERSION,
            })
            session["context_snapshots"] = snapshots[-MAX_CONTEXT_SNAPSHOTS:]

        self._mutate_session(session_id, save)
        self._log_event("cognitive_state_saved", session_id, state_id=cognitive["state_id"])
        return deepcopy(cognitive)

    def snapshot_context(self, session_id: str) -> dict:
        def save(session):
            snapshots = session.setdefault("context_snapshots", [])
            snapshot = {
                "snapshot_id": str(uuid4()),
                "session_id": session_id,
                "active_project": session.get("active_project"),
                "active_version": session.get("active_version"),
                "active_mode": session.get("active_mode"),
                "goal_id": session.get("goal_id"),
                "recent_artifacts": list(session.get("recent_artifact_ids", []))[-10:],
                "recent_decisions": list(session.get("recent_decision_ids", []))[-10:],
                "recent_memory_ids": list(session.get("recent_memory_ids", []))[-10:],
                "pending_tasks": [],
                "blockers": (session.get("cognitive_state") or {}).get("blockers", []),
                "created_at": _timestamp(),
                "schema_version": SESSION_SCHEMA_VERSION,
            }
            snapshots.append(snapshot)
            session["context_snapshots"] = snapshots[-MAX_CONTEXT_SNAPSHOTS:]
            return deepcopy(snapshot)

        return self._mutate_session(session_id, save)

    def update_context(self, session_id: str, **values) -> dict:
        allowed = {"active_project", "active_version", "active_mode", "current_goal", "goal_id", "project_id"}
        if set(values) - allowed:
            raise ValueError("unsupported session context field")

        def update(session):
            session.update(values)
            if "active_project" in values:
                session["project_id"] = values["active_project"]
                if values["active_project"]:
                    conversation = session.setdefault("conversation", {})
                    references = conversation.setdefault("recent_references", [])
                    if values["active_project"] not in references:
                        references.append(values["active_project"])
                    conversation["recent_references"] = references[-20:]

        return self._mutate_session(session_id, update)

    def add_reference(self, session_id: str, reference: str) -> None:
        def update(session):
            conversation = session.setdefault("conversation", {})
            references = conversation.setdefault("recent_references", [])
            if reference not in references:
                references.append(reference)
            conversation["recent_references"] = references[-20:]

        self._mutate_session(session_id, update)

    def link_record(self, session_id: str, relation: str, record_id: str) -> None:
        fields = {
            "artifact": "recent_artifact_ids",
            "decision": "recent_decision_ids",
            "memory": "recent_memory_ids",
            "experience": "recent_experience_ids",
        }
        if relation not in fields:
            raise ValueError("unsupported session record relation")

        def update(session):
            identifiers = session.setdefault(fields[relation], [])
            if record_id not in identifiers:
                identifiers.append(record_id)
            session[fields[relation]] = identifiers[-20:]

        self._mutate_session(session_id, update)

    def close_session(self, session_id: str) -> dict:
        session = self._mutate_session(
            session_id,
            lambda session: session.update(status="closed"),
        )
        self._log_event("session_closed", session_id)
        return session

    def pause_session(self, session_id: str) -> dict:
        current = self.get_session(session_id)
        if current is None:
            raise KeyError("session not found")
        if current["status"] == "closed":
            raise ValueError("closed sessions cannot be paused")
        if current["status"] == "paused":
            return current
        paused = self._mutate_session(
            session_id,
            lambda session: session.update(status="paused"),
        )
        self._log_event("session_paused", session_id)
        return paused

    def resume_session(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError("session not found")
        if session["status"] == "closed":
            raise ValueError("closed sessions cannot be resumed")
        session = self._mutate_session(
            session_id,
            lambda record: record.update(status="active"),
        )
        self._log_event("session_resumed", session_id)
        return session