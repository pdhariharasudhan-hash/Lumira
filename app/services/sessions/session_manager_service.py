from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import ast
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
MAX_SESSIONS = 1000
MAX_SESSION_ID_LENGTH = 128
SECRET_PATTERN = re.compile(
    r"(?i)(password|api[_ -]?key|access[_ -]?token|secret|authorization)"
    r"(\s*[:=]\s*)([^\r\n]+)|\bBearer\s+[A-Za-z0-9._~+/-]+=*"
)
SECRET_KEY_PATTERN = re.compile(
    r"(?i)password|api[_ -]?key|access[_ -]?token|secret|authorization"
)
PYTHON_FILE_PATTERN = re.compile(r"(?i)\.pyw?$")


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


def _redact_python_source(source: str) -> str:
    """Redact literal credentials in generated Python while preserving valid syntax."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return _redact_secrets(source)

    lines = source.splitlines(keepends=True)
    line_offsets = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line.encode("utf-8"))

    edits: set[tuple[int, int]] = set()

    def span(node: ast.AST):
        start_line = getattr(node, "lineno", None)
        start_col = getattr(node, "col_offset", None)
        end_line = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)
        if None in (start_line, start_col, end_line, end_col):
            return None
        return line_offsets[start_line - 1] + start_col, line_offsets[end_line - 1] + end_col

    def names(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Attribute):
            return [target.attr]
        if isinstance(target, (ast.Tuple, ast.List)):
            return [name for item in target.elts for name in names(item)]
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
            return [target.slice.value]
        return []

    def redact_literal(key: str | None, value: ast.AST) -> None:
        if not key or not SECRET_KEY_PATTERN.search(key):
            return
        if isinstance(value, ast.Constant) and isinstance(value.value, (str, bytes)):
            location = span(value)
            if location:
                edits.add(location)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for key in names(target):
                    redact_literal(key, node.value)
        elif isinstance(node, ast.AnnAssign):
            for key in names(node.target):
                redact_literal(key, node.value)
        elif isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    redact_literal(key_node.value, value_node)
        elif isinstance(node, ast.keyword):
            redact_literal(node.arg, node.value)

    encoded = source.encode("utf-8")
    for start, end in sorted(edits, reverse=True):
        encoded = encoded[:start] + b"'[REDACTED]'" + encoded[end:]
    return encoded.decode("utf-8")


def redact_sensitive_value(value):
    if isinstance(value, str):
        return _redact_secrets(value)
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            safe_key = str(key)
            if SECRET_KEY_PATTERN.search(safe_key):
                safe[safe_key] = "[REDACTED]"
            elif PYTHON_FILE_PATTERN.search(safe_key) and isinstance(item, str):
                safe[safe_key] = _redact_python_source(item)
            else:
                safe[safe_key] = redact_sensitive_value(item)
        return safe
    return value


redact_sensitive_text = _redact_secrets


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
        sessions = document.get("sessions")
        if not isinstance(sessions, list) or len(sessions) > MAX_SESSIONS:
            raise PersistenceIntegrityError("Session store sessions must be a bounded list")
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
        seen_session_ids: set[str] = set()
        for session in document["sessions"]:
            if not isinstance(session, dict) or not required.issubset(session):
                raise PersistenceIntegrityError("Session record is incomplete")
            if session["schema_version"] != SESSION_SCHEMA_VERSION:
                raise PersistenceIntegrityError("Unsupported session record schema version")
            for field in ("session_id", "conversation_id", "workspace_id"):
                value = session.get(field)
                if not isinstance(value, str) or not value.strip() or len(value) > MAX_SESSION_ID_LENGTH:
                    raise PersistenceIntegrityError(f"Session record has an invalid {field}")
            for field in ("created_at", "updated_at"):
                value = session.get(field)
                if not isinstance(value, str) or not value or len(value) > 40:
                    raise PersistenceIntegrityError(f"Session record has an invalid {field}")
            if session["session_id"] in seen_session_ids:
                raise PersistenceIntegrityError("Session IDs must be unique")
            seen_session_ids.add(session["session_id"])
            status = session.get("status")
            if not isinstance(status, str) or status not in {"active", "paused", "closed"}:
                raise PersistenceIntegrityError("Session record has an invalid status")
            if not isinstance(session["conversation"], dict):
                raise PersistenceIntegrityError("Session conversation must be an object")
            messages = session["recent_messages"]
            if not isinstance(messages, list) or len(messages) > MAX_RECENT_MESSAGES:
                raise PersistenceIntegrityError("Session messages must be a bounded list")
            snapshots = session["context_snapshots"]
            if not isinstance(snapshots, list) or len(snapshots) > MAX_CONTEXT_SNAPSHOTS:
                raise PersistenceIntegrityError("Session snapshots must be a bounded list")
        return document

    def create_session(
        self,
        workspace_id: str = "default",
        project_id: str | None = None,
    ) -> dict:
        if not isinstance(workspace_id, str) or not 1 <= len(workspace_id) <= 100:
            raise ValueError("workspace_id must contain 1 to 100 characters")
        if project_id is not None and (not isinstance(project_id, str) or len(project_id) > 100):
            raise ValueError("project_id must contain at most 100 characters")
        now = _timestamp()
        session = {
            "session_id": str(uuid4()),
            "owner_id": "local",
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
            if len(document["sessions"]) >= MAX_SESSIONS:
                raise ValueError("session capacity reached; archive or remove old sessions first")
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
        if not isinstance(role, str) or role not in {"user", "assistant", "system"}:
            raise ValueError("unsupported conversation role")
        if not isinstance(content, str):
            raise ValueError("message content must be a string")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("message metadata must be an object")
        message = {
            "message_id": str(uuid4()),
            "role": role,
            "content": _redact_secrets(content)[:4000],
            "metadata": redact_sensitive_value(metadata or {}),
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
            "blockers": redact_sensitive_value((
                list(constraints.get("missing_information", []))
                + list(constraints.get("risks", []))
            )[:20]),
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
        # Import lazily to avoid a module cycle: WorkItemService uses session redaction.
        from app.services.work_items.work_item_service import WorkItemService

        def save(session):
            snapshots = session.setdefault("context_snapshots", [])
            workflows = WorkItemService().list_workflows(session_id=session_id, limit=200)
            pending_tasks = []
            workflow_summaries = []
            for workflow in workflows:
                incomplete = [
                    task for task in workflow.get("tasks", [])
                    if isinstance(task, dict) and task.get("status") != "completed"
                ]
                if not incomplete:
                    continue
                workflow_summaries.append({
                    "workflow_id": workflow.get("workflow_id"),
                    "title": workflow.get("title"),
                    "status": workflow.get("status"),
                    "project_id": workflow.get("project_id"),
                    "goal_id": workflow.get("goal_id"),
                    "incomplete_task_count": len(incomplete),
                    "updated_at": workflow.get("updated_at"),
                })
                for task in incomplete:
                    pending_tasks.append({
                        "workflow_id": workflow.get("workflow_id"),
                        "workflow_title": workflow.get("title"),
                        "task_id": task.get("task_id"),
                        "title": task.get("title"),
                        "status": task.get("status"),
                        "dependencies": list(task.get("dependencies", []))[:20],
                        "blocker": task.get("blocker"),
                        "result": task.get("result"),
                        "updated_at": task.get("updated_at"),
                    })
                    if len(pending_tasks) >= 50:
                        break
                if len(pending_tasks) >= 50:
                    break
            snapshot = {
                "snapshot_id": str(uuid4()),
                "session_id": session_id,
                "active_project": session.get("active_project"),
                "active_version": session.get("active_version"),
                "active_mode": session.get("active_mode"),
                "current_goal": session.get("current_goal"),
                "goal_id": session.get("goal_id"),
                "recent_artifacts": list(session.get("recent_artifact_ids", []))[-10:],
                "recent_decisions": list(session.get("recent_decision_ids", []))[-10:],
                "recent_memory_ids": list(session.get("recent_memory_ids", []))[-10:],
                "recent_workflow_ids": list(session.get("recent_workflow_ids", []))[-20:],
                "workflows": workflow_summaries[:50],
                "pending_tasks": pending_tasks,
                "blockers": (session.get("cognitive_state") or {}).get("blockers", [])[:50],
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
        limits = {"active_project": 100, "active_version": 100, "active_mode": 50, "current_goal": 4000, "goal_id": 128, "project_id": 100}
        for key, value in values.items():
            if value is not None and (not isinstance(value, str) or len(value) > limits[key]):
                raise ValueError(f"{key} exceeds its supported length")
        values = redact_sensitive_value(values)

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
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 500:
            raise ValueError("reference must contain 1 to 500 characters")
        reference = _redact_secrets(reference)
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
            "workflow": "recent_workflow_ids",
        }
        if relation not in fields:
            raise ValueError("unsupported session record relation")
        if not isinstance(record_id, str) or not record_id or len(record_id) > 128:
            raise ValueError("record identifier is invalid")

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
