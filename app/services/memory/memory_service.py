import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from app.services.modes.models.mode_state import (
    ModeState,
)
from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)


VALID_STAGES = ["validate", "builder", "execute", "code"]
VALID_STATUSES = ["running", "stopped", "completed"]


class MemoryValidationError(Exception):
    pass


class MemoryService:
    _sensitive_key_pattern = re.compile(
        r"(?i)password|api[_ -]?key|access[_ -]?token|secret|authorization"
    )
    _secret_pattern = re.compile(
        r"(?i)(password|api[_ -]?key|access[_ -]?token|secret|authorization)"
        r"(\s*[:=]\s*)([^\r\n]+)|\bBearer\s+[A-Za-z0-9._~+/-]+=*"
    )

    @classmethod
    def _safe_text(cls, value: str) -> str:
        return cls._secret_pattern.sub(
            lambda match: (
                f"{match.group(1)}{match.group(2)}[REDACTED]"
                if match.group(1)
                else "Bearer [REDACTED]"
            ),
            value,
        )

    # --------------------------------------------------------
    # Mode Context
    # --------------------------------------------------------

    def _mode_context(
        self,
        mode: ModeState | None,
    ) -> Optional[Dict[str, Any]]:
        """
        Return deterministic memory context for the
        active operating mode.

        Memory remains a persistence layer.
        Mode does not alter pipeline validation rules.
        """

        if mode is None:
            return None

        contexts = {
            "builder": {
                "mode": "builder",
                "memory_focus": "implementation",
            },

            "research": {
                "mode": "research",
                "memory_focus": "evidence",
            },

            "generator": {
                "mode": "generator",
                "memory_focus": "artifacts",
            },

            "creator": {
                "mode": "creator",
                "memory_focus": "content",
            },

            "growth": {
                "mode": "growth",
                "memory_focus": "strategy",
            },

            "business": {
                "mode": "business",
                "memory_focus": "business_objectives_and_operations",
            },

            "operations": {
                "mode": "operations",
                "memory_focus": "operations",
            },

            "assistant": {
                "mode": "assistant",
                "memory_focus": "user_alignment",
            },

            "personal": {
                "mode": "personal",
                "memory_focus": "general",
            },
        }

        return contexts.get(
            mode.active_mode
        )

    def __init__(self, file_path: str = "data/project_memory.json"):
        self.file_path = Path(file_path)
        self.store = AtomicJsonStore(self.file_path)
        self.cognitive_file = self.file_path.with_name("cognitive_memory.json")
        self.cognitive_store = AtomicJsonStore(self.cognitive_file)
        self._ensure_file()

    @staticmethod
    def _default_cognitive_memory() -> dict:
        return {
            "schema_version": 1,
            "goals": [],
            "decisions": [],
            "experiences": [],
            "learning_records": [],
        }

    def _read_cognitive_memory(self) -> dict:
        try:
            data = self.cognitive_store.read(self._default_cognitive_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc
        if not isinstance(data, dict):
            raise MemoryValidationError("Cognitive memory root must be an object")
        if data.get("schema_version") != 1:
            raise MemoryValidationError(
                f"Unsupported cognitive memory schema version: {data.get('schema_version')!r}"
            )
        for key in ("goals", "decisions", "experiences", "learning_records"):
            if not isinstance(data.get(key), list):
                raise MemoryValidationError(f"{key} must be a list")
            if any(
                not isinstance(record, dict) or record.get("schema_version") != 1
                for record in data[key]
            ):
                raise MemoryValidationError(f"{key} contains an invalid record")
        return data

    def _default_memory(self) -> Dict[str, Any]:
         return {
            "project_name": "Personal AI Core",

            "pipeline_runs": [],

            "latest_pipeline_run": None,

            "artifacts": [],

            "feature_history": [],
            "schema_version": 1,
            "goals": [],
            "decisions": [],
            "experiences": [],
            "learning_records": [],
        }

    def _normalize_pipeline_run(self, run: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if run is None:
            return None

        normalized = dict(run)

        normalized.setdefault("type", "pipeline_run")
        normalized.setdefault("input", "")
        normalized.setdefault("final_status", "incomplete")

        normalized.setdefault("validate", None)
        normalized.setdefault("builder", None)
        normalized.setdefault("execute", None)
        normalized.setdefault("code", None)

        normalized.setdefault("current_stage", "validate")
        normalized.setdefault("last_completed_stage", None)
        normalized.setdefault("status", "running")

        normalized.setdefault("error", None)
        normalized.setdefault("retry_count", 0)
        normalized.setdefault("resume_allowed", True)

        normalized.setdefault("aborted", False)
        normalized.setdefault("manual_override", None)
        normalized.setdefault("state_fixes", [])

        return normalized

    def _validate_pipeline_run(self, run: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if run is None:
            return None

        if not isinstance(run, dict):
            raise MemoryValidationError("pipeline payload must be a dictionary")

        current_stage = run.get("current_stage")
        last_completed_stage = run.get("last_completed_stage")
        status = run.get("status")
        final_status = run.get("final_status")

        allowed_stage_values = VALID_STAGES + [None]

        if current_stage not in allowed_stage_values:
            raise MemoryValidationError(f"invalid current_stage: {current_stage}")

        if last_completed_stage not in allowed_stage_values:
            raise MemoryValidationError(f"invalid last_completed_stage: {last_completed_stage}")

        if status not in VALID_STATUSES:
            raise MemoryValidationError(f"invalid status: {status}")

        if status == "completed" and current_stage is not None:
            raise MemoryValidationError("completed pipeline must have current_stage = null")

        if status == "completed" and final_status != "completed":
            raise MemoryValidationError("completed pipeline must have final_status = completed")

        if final_status == "completed" and current_stage is not None:
            raise MemoryValidationError("final_status completed requires current_stage = null")

        validate_result = run.get("validate")
        builder_result = run.get("builder")
        execute_result = run.get("execute")
        code_result = run.get("code")

        if validate_result is not None:
            if not isinstance(validate_result, dict):
                raise MemoryValidationError("validate result must be a dictionary or null")

            verdict = validate_result.get("verdict")
            if verdict == "reject":
                if builder_result is not None or execute_result is not None or code_result is not None:
                    raise MemoryValidationError(
                        "rejected validate stage cannot have builder/execute/code data"
                    )

                if final_status not in ["rejected", "incomplete", None]:
                    raise MemoryValidationError(
                        "rejected validate stage must keep final_status consistent"
                    )

        if builder_result is not None:
            if not isinstance(builder_result, dict):
                raise MemoryValidationError("builder result must be a dictionary or null")

            builder_status = builder_result.get("status")
            if builder_status == "refine":
                if execute_result is not None or code_result is not None:
                    raise MemoryValidationError("builder refine cannot have execute/code data")

                if final_status not in ["refine_required", "incomplete", None]:
                    raise MemoryValidationError(
                        "builder refine must keep final_status consistent"
                    )

        if execute_result is not None:
            if not isinstance(execute_result, dict):
                raise MemoryValidationError("execute result must be a dictionary or null")

            execute_status = execute_result.get("status")
            if execute_status == "refine":
                if code_result is not None:
                    raise MemoryValidationError("execute refine cannot have code data")

                if final_status not in ["refine_required", "incomplete", None]:
                    raise MemoryValidationError(
                        "execute refine must keep final_status consistent"
                    )

        if code_result is not None and not isinstance(code_result, dict):
            raise MemoryValidationError("code result must be a dictionary or null")

        aborted = run.get("aborted")
        if not isinstance(aborted, bool):
            raise MemoryValidationError("aborted must be boolean")

        if aborted:
            if run.get("resume_allowed") is not False:
                raise MemoryValidationError("aborted pipeline must have resume_allowed = false")
            if final_status != "aborted":
                raise MemoryValidationError("aborted pipeline must have final_status = aborted")

        retry_count = run.get("retry_count")
        if isinstance(retry_count, bool) or not isinstance(retry_count, int) or retry_count < 0:
            raise MemoryValidationError("retry_count must be a non-negative integer")

        resume_allowed = run.get("resume_allowed")
        if not isinstance(resume_allowed, bool):
            raise MemoryValidationError("resume_allowed must be boolean")

        state_fixes = run.get("state_fixes")
        if state_fixes is not None and not isinstance(state_fixes, list):
            raise MemoryValidationError("state_fixes must be a list")

        return run

    def _validate_memory_update(self, key: str, value: Any) -> Any:
        if not isinstance(key, str) or not key.strip():
            raise MemoryValidationError("memory key must be a non-empty string")

        if key in ("pipeline_run", "latest_pipeline_run"):
            normalized_value = self._normalize_pipeline_run(value)
            return self._validate_pipeline_run(normalized_value)

        return value

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_memory(self._default_memory())

    def _read_memory(self) -> Dict[str, Any]:
        self._ensure_file()

        try:
            data = self.store.read()

            if not isinstance(data, dict):
                raise PersistenceIntegrityError("Memory store root must be an object")

            schema_version = data.get("schema_version", 0)
            if schema_version == 0:
                data = self._migrate_memory_v0_to_v1(data)
                self._write_memory(data)
            elif schema_version != 1:
                raise PersistenceIntegrityError(
                    f"Unsupported memory schema version: {schema_version!r}"
                )

            data.setdefault("project_name", "Personal AI Core")

            data.setdefault(
                "artifacts",
                []
            )

            data.setdefault(
                "feature_history",
                []
            )
            for key in ("goals", "decisions", "experiences", "learning_records"):
                data.setdefault(key, [])

            if "pipeline_runs" not in data:
                data["pipeline_runs"] = []
            pipeline_runs = data.get("pipeline_runs")
            if not isinstance(pipeline_runs, list):
                raise MemoryValidationError("pipeline_runs must be a list")
            if any(not isinstance(run, dict) for run in pipeline_runs):
                raise MemoryValidationError("pipeline_runs contains an invalid record")
            data["pipeline_runs"] = [
                self._validate_pipeline_run(self._normalize_pipeline_run(run))
                for run in pipeline_runs
            ]

            latest_pipeline_run = data.get("latest_pipeline_run")
            if latest_pipeline_run is not None and not isinstance(latest_pipeline_run, dict):
                raise MemoryValidationError("latest_pipeline_run must be an object or null")
            data["latest_pipeline_run"] = self._validate_pipeline_run(
                self._normalize_pipeline_run(latest_pipeline_run)
            )

            return data

        except (json.JSONDecodeError, PersistenceIntegrityError) as exc:
            raise MemoryValidationError(str(exc)) from exc

    @staticmethod
    def _migrate_memory_v0_to_v1(data: dict) -> dict:
        migrated = dict(data)
        migrated.setdefault("pipeline_runs", [])
        migrated.setdefault("latest_pipeline_run", None)
        migrated.setdefault("artifacts", [])
        migrated.setdefault("feature_history", [])
        migrated.setdefault("goals", [])
        migrated.setdefault("decisions", [])
        migrated.setdefault("experiences", [])
        migrated.setdefault("learning_records", [])
        migrated["schema_version"] = 1
        return migrated

    def _write_memory(self, data: Dict[str, Any]) -> None:
        self.store.write(data)

    @classmethod
    def _redact_nested(cls, value):
        if isinstance(value, str):
            return cls._safe_text(value)
        if isinstance(value, list):
            return [cls._redact_nested(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): "[REDACTED]" if cls._sensitive_key_pattern.search(str(key)) else cls._redact_nested(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _record(kind: str, **fields) -> dict:
        now = datetime.now(UTC).isoformat()
        return {
            f"{kind}_id": str(uuid4()),
            "owner_id": "local",
            **fields,
            "created_at": now,
            "updated_at": now,
            "schema_version": 1,
        }

    @staticmethod
    def _bounded_text(value: Any, field: str, maximum: int, *, optional: bool = False) -> str | None:
        if optional and (value is None or (isinstance(value, str) and not value.strip())):
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise MemoryValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
        return value.strip()

    @classmethod
    def _bounded_string_list(cls, value: Any, field: str, maximum_items: int, maximum_length: int) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or len(value) > maximum_items:
            raise MemoryValidationError(f"{field} must be a list of at most {maximum_items} items")
        result = []
        for item in value:
            if not isinstance(item, str) or not item.strip() or len(item) > maximum_length:
                raise MemoryValidationError(f"{field} contains an empty, invalid, or oversized item")
            result.append(item.strip())
        return result

    def _append_record(self, collection: str, record: dict) -> dict:
        cognitive_collections = {
            "goals",
            "decisions",
            "experiences",
            "learning_records",
        }
        target_store = (
            self.cognitive_store
            if collection in cognitive_collections
            else self.store
        )
        default_document = (
            self._default_cognitive_memory()
            if collection in cognitive_collections
            else self._default_memory()
        )

        def append(memory):
            if not isinstance(memory, dict):
                raise MemoryValidationError("memory root must be an object")
            version = memory.get("schema_version", 0)
            if version not in {0, 1}:
                raise MemoryValidationError(f"unsupported memory schema version: {version!r}")
            memory.setdefault("schema_version", 1)
            records = memory.setdefault(collection, [])
            if not isinstance(records, list):
                raise MemoryValidationError(f"{collection} must be a list")
            records.append(record)
            return deepcopy(record)

        try:
            return target_store.update(append, default_document)
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    @staticmethod
    def _validate_goal_fields(fields: dict, *, creating: bool = False) -> dict:
        allowed = {
            "title", "objective", "priority", "status", "progress", "milestones",
            "dependencies", "blockers", "project_id", "parent_goal_id", "artifact_ids", "deadline",
        }
        if set(fields) - allowed:
            raise MemoryValidationError("unsupported goal field")
        try:
            payload_size = len(json.dumps(fields, ensure_ascii=False))
        except (TypeError, ValueError, RecursionError) as exc:
            raise MemoryValidationError("goal fields must be JSON-compatible") from exc
        if payload_size > 100_000:
            raise MemoryValidationError("goal fields exceed the 100000-character limit")

        limits = {"title": 500, "objective": 2000, "project_id": 100, "parent_goal_id": 128, "deadline": 40}
        for field, maximum in limits.items():
            if field not in fields:
                continue
            value = fields[field]
            if value is None and field in {"project_id", "parent_goal_id", "deadline"}:
                continue
            if not isinstance(value, str) or len(value) > maximum:
                raise MemoryValidationError(f"{field} must be a string of at most {maximum} characters")
            if field == "title" and not value.strip():
                raise MemoryValidationError("title must not be empty")

        if fields.get("deadline") is not None:
            try:
                datetime.fromisoformat(fields["deadline"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                raise MemoryValidationError("deadline must be an ISO 8601 date or datetime") from None

        if "priority" in fields:
            value = fields["priority"]
            if not isinstance(value, str) or value not in {"low", "normal", "high", "urgent"}:
                raise MemoryValidationError("priority must be low, normal, high, or urgent")
        if "status" in fields:
            value = fields["status"]
            if not isinstance(value, str) or value not in {"active", "paused", "completed", "blocked", "cancelled"}:
                raise MemoryValidationError("invalid goal status")

        if "progress" in fields:
            value = fields["progress"]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value))
                or not 0 <= value <= 100
            ):
                raise MemoryValidationError("progress must be a finite number between 0 and 100")

        list_limits = {
            "milestones": (50, dict),
            "dependencies": (50, str),
            "blockers": (20, str),
            "artifact_ids": (50, str),
        }
        for field, (maximum, item_type) in list_limits.items():
            if field not in fields:
                continue
            value = fields[field]
            if value is None and not creating:
                raise MemoryValidationError(f"{field} must be a list")
            if not isinstance(value, list) or len(value) > maximum:
                raise MemoryValidationError(f"{field} must be a list of at most {maximum} items")
            if any(not isinstance(item, item_type) for item in value):
                raise MemoryValidationError(f"{field} contains an invalid item")
            if item_type is str and any(not item.strip() or len(item) > 500 for item in value):
                raise MemoryValidationError(f"{field} contains an empty or oversized item")

        return fields

    def create_goal(self, title: str, objective: str = "", priority: str = "normal", project_id: str | None = None, parent_goal_id: str | None = None, status: str = "active", blockers: list[str] | None = None, deadline: str | None = None) -> dict:
        fields = self._validate_goal_fields({
            "title": title,
            "objective": objective,
            "priority": priority,
            "project_id": project_id,
            "parent_goal_id": parent_goal_id,
            "status": status,
            "blockers": blockers if blockers is not None else [],
            "deadline": deadline,
        }, creating=True)
        now = datetime.now(UTC).isoformat()
        parent_goal_id = fields["parent_goal_id"]
        if parent_goal_id:
            existing = self._read_cognitive_memory().get("goals", [])
            if not any(item.get("goal_id") == parent_goal_id and not item.get("archived") for item in existing):
                raise MemoryValidationError("parent_goal_id does not reference an existing goal")
        return self._append_record("goals", self._record(
            "goal", parent_goal_id=parent_goal_id, title=self._safe_text(fields["title"].strip()),
            objective=self._safe_text(fields["objective"]), priority=fields["priority"], status=fields["status"],
            progress=0.0, milestones=[], dependencies=[],
            blockers=[self._safe_text(item) for item in fields["blockers"]], project_id=fields["project_id"],
            artifact_ids=[], deadline=fields.get("deadline"), history=[{"event": "created", "at": now, "status": fields["status"], "progress": 0.0}],
        ))

    def decompose_goal(self, goal_id: str, objectives: list[str]) -> dict:
        """Create a bounded set of persistent child goals under an existing parent goal."""
        if not isinstance(goal_id, str) or not goal_id.strip() or len(goal_id) > 128:
            raise MemoryValidationError("goal_id must contain 1 to 128 characters")
        if not isinstance(objectives, list) or not 1 <= len(objectives) <= 20:
            raise MemoryValidationError("objectives must contain 1 to 20 items")
        normalized = []
        for objective in objectives:
            if not isinstance(objective, str) or not objective.strip() or len(objective.strip()) > 500:
                raise MemoryValidationError("each objective must contain 1 to 500 characters")
            normalized.append(self._safe_text(objective.strip()))
        now = datetime.now(UTC).isoformat()
        created = []
        def decompose(memory):
            if not isinstance(memory, dict) or memory.get("schema_version") != 1:
                raise MemoryValidationError("unsupported cognitive memory schema version")
            goals = memory.setdefault("goals", [])
            parent = next((item for item in goals if item.get("goal_id") == goal_id and not item.get("archived")), None)
            if parent is None:
                raise KeyError("goal not found")
            if parent.get("status") in {"completed", "cancelled"}:
                raise MemoryValidationError("completed or cancelled goals cannot be decomposed")
            children = [item for item in goals if item.get("parent_goal_id") == goal_id and not item.get("archived")]
            if len(children) + len(normalized) > 50:
                raise MemoryValidationError("a goal can have at most 50 active child objectives")
            existing_titles = {item.get("title", "").casefold() for item in children}
            if any(title.casefold() in existing_titles for title in normalized):
                raise MemoryValidationError("an objective already exists under this goal")
            for title in normalized:
                child = self._record(
                    "goal", parent_goal_id=goal_id, title=title, objective="", priority=parent.get("priority", "normal"),
                    status="active", progress=0.0, milestones=[], dependencies=[], blockers=[],
                    project_id=parent.get("project_id"), artifact_ids=[], deadline=None,
                    history=[{"event": "created_by_decomposition", "at": now, "status": "active", "progress": 0.0}],
                )
                goals.append(child)
                created.append(deepcopy(child))
            history = parent.setdefault("history", [])
            history.append({"event": "decomposed", "at": now, "child_goal_ids": [item["goal_id"] for item in created]})
            parent["history"] = history[-50:]
            parent["updated_at"] = now
            parent["milestones"] = list(parent.get("milestones", [])) + [{"title": item["title"], "goal_id": item["goal_id"], "status": "pending"} for item in created]
            parent["milestones"] = parent["milestones"][-50:]
            return {"parent": deepcopy(parent), "objectives": deepcopy(created)}
        try:
            return self.cognitive_store.update(decompose, self._default_cognitive_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    def update_goal(self, goal_id: str, **updates) -> dict:
        if not isinstance(goal_id, str) or not goal_id.strip() or len(goal_id) > 128:
            raise MemoryValidationError("goal_id must contain 1 to 128 characters")
        if not updates:
            raise MemoryValidationError("at least one goal field is required")
        updates = self._validate_goal_fields(updates)
        updates = self._redact_nested(updates)

        def update(memory):
            if memory.get("schema_version") != 1:
                raise MemoryValidationError("unsupported cognitive memory schema version")
            goals = memory.setdefault("goals", [])
            target = next((record for record in goals if record.get("goal_id") == goal_id), None)
            if target is None:
                raise KeyError("goal not found")
            if "dependencies" in updates:
                dependencies = updates["dependencies"]
                known_ids = {record.get("goal_id") for record in goals if isinstance(record.get("goal_id"), str)}
                if goal_id in dependencies:
                    raise MemoryValidationError("a goal cannot depend on itself")
                missing = [dependency for dependency in dependencies if dependency not in known_ids]
                if missing:
                    raise MemoryValidationError("goal dependency references an unknown goal")
                graph = {
                    record.get("goal_id"): list(record.get("dependencies", []))
                    for record in goals if isinstance(record.get("goal_id"), str)
                }
                graph[goal_id] = dependencies
                visiting = set()
                visited = set()
                def visit_dependency(node_id):
                    if node_id in visiting:
                        raise MemoryValidationError("goal dependencies cannot contain a cycle")
                    if node_id in visited:
                        return
                    visiting.add(node_id)
                    for dependency_id in graph.get(node_id, []):
                        visit_dependency(dependency_id)
                    visiting.remove(node_id)
                    visited.add(node_id)
                for node_id in graph:
                    visit_dependency(node_id)
            for record in goals:
                if record.get("goal_id") == goal_id:
                    now = datetime.now(UTC).isoformat()
                    history = record.setdefault("history", [])
                    history.append({
                        "event": "updated", "at": now,
                        "changed_fields": sorted(updates.keys()),
                        "status": updates.get("status", record.get("status")),
                        "progress": updates.get("progress", record.get("progress", 0.0)),
                    })
                    record["history"] = history[-50:]
                    record.update(updates)
                    record["updated_at"] = now
                    return deepcopy(record)
            raise KeyError("goal not found")

        try:
            return self.cognitive_store.update(update, self._default_cognitive_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    def record_decision(self, decision: str, reason: str = "", session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None, alternatives: list[str] | None = None, constraints: list[str] | None = None, confidence: float = 0.0) -> dict:
        decision_text = self._bounded_text(decision, "decision", 2000)
        reason_text = "" if reason == "" else self._bounded_text(reason, "reason", 5000)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise MemoryValidationError("confidence must be a finite number between 0 and 1")
        session_id = self._bounded_text(session_id, "session_id", 128, optional=True)
        project_id = self._bounded_text(project_id, "project_id", 100, optional=True)
        goal_id = self._bounded_text(goal_id, "goal_id", 128, optional=True)
        alternatives = self._bounded_string_list(alternatives, "alternatives", 20, 1000)
        constraints = self._bounded_string_list(constraints, "constraints", 50, 1000)
        return self._append_record("decisions", self._record(
            "decision", session_id=session_id, project_id=project_id,
            goal_id=goal_id, decision=self._safe_text(decision_text),
            reason=self._safe_text(reason_text),
            alternatives=[self._safe_text(item) for item in alternatives],
            constraints=[self._safe_text(item) for item in constraints],
            confidence=float(confidence),
        ))

    def record_experience(self, experience_type: str, summary: str, outcome: str, project_id: str | None = None, goal_id: str | None = None, lessons: list[str] | None = None, artifact_ids: list[str] | None = None, source_run: str | None = None, verified: bool = False) -> dict:
        if not isinstance(experience_type, str) or experience_type not in {"success", "failure", "decision", "workflow"}:
            raise MemoryValidationError("unsupported experience type")
        summary_text = self._bounded_text(summary, "summary", 4000)
        outcome_text = self._bounded_text(outcome, "outcome", 5000)
        project_id = self._bounded_text(project_id, "project_id", 100, optional=True)
        goal_id = self._bounded_text(goal_id, "goal_id", 128, optional=True)
        source_run = self._bounded_text(source_run, "source_run", 128, optional=True)
        lessons = self._bounded_string_list(lessons, "lessons", 50, 2000)
        artifact_ids = self._bounded_string_list(artifact_ids, "artifact_ids", 50, 128)
        return self._append_record("experiences", self._record(
            "experience", type=experience_type, project_id=project_id,
            goal_id=goal_id, source_run=source_run, summary=self._safe_text(summary_text),
            outcome=self._safe_text(outcome_text),
            lessons=[self._safe_text(item) for item in lessons],
            artifact_ids=artifact_ids, verified=verified is True,
        ))

    def attach_artifacts_to_experience(self, source_artifact_id: str, artifact_ids: list[str]) -> dict:
        """Idempotently attach newly created artifacts to an existing memory experience."""
        source_id = self._bounded_text(source_artifact_id, "source_artifact_id", 128)
        additions = self._bounded_string_list(artifact_ids, "artifact_ids", 50, 128)
        now = datetime.now(UTC).isoformat()

        def attach(memory):
            experiences = memory.get("experiences", []) if isinstance(memory, dict) else []
            for record in experiences if isinstance(experiences, list) else []:
                current_ids = record.get("artifact_ids", []) if isinstance(record, dict) else []
                if isinstance(record, dict) and isinstance(current_ids, list) and source_id in current_ids:
                    record["artifact_ids"] = list(dict.fromkeys([*current_ids, *additions]))
                    record["updated_at"] = now
                    return dict(record)
            raise KeyError("voice memory experience not found")

        try:
            return self.cognitive_store.update(attach, self._default_cognitive_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    def verify_experience(self, experience_id: str) -> dict:
        """Explicitly verify a persisted experience, then consolidate eligible learning."""
        experience_id = self._bounded_text(experience_id, "experience_id", 128)
        now = datetime.now(UTC).isoformat()

        def verify(memory):
            if not isinstance(memory, dict) or memory.get("schema_version") != 1:
                raise MemoryValidationError("unsupported cognitive memory schema version")
            experiences = memory.get("experiences", [])
            if not isinstance(experiences, list):
                raise MemoryValidationError("experiences must be a list")
            for record in experiences:
                if isinstance(record, dict) and record.get("experience_id") == experience_id:
                    if record.get("archived"):
                        raise MemoryValidationError("archived experiences cannot be verified")
                    record["verified"] = True
                    record["verified_at"] = record.get("verified_at") or now
                    record["updated_at"] = now
                    return deepcopy(record)
            raise KeyError("experience not found")

        try:
            experience = self.cognitive_store.update(verify, self._default_cognitive_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc
        return {
            "experience": experience,
            "learning": self.consolidate_learning(experience),
        }

    def consolidate_learning(self, experience: dict) -> dict | None:
        """Consolidate only an explicitly verified experience already stored in memory."""
        if not isinstance(experience, dict):
            return None
        experience_id = experience.get("experience_id")
        if not isinstance(experience_id, str) or not experience_id:
            return None

        cognitive_memory = self._read_cognitive_memory()
        persisted = next(
            (
                record
                for record in cognitive_memory.get("experiences", [])
                if isinstance(record, dict) and record.get("experience_id") == experience_id
            ),
            None,
        )
        if not isinstance(persisted, dict) or persisted.get("verified") is not True:
            return None

        lessons = [
            self._safe_text(lesson.strip())
            for lesson in persisted.get("lessons", [])
            if isinstance(lesson, str) and len(lesson.strip()) >= 20
        ]
        if not lessons or persisted.get("type") not in {"success", "failure"}:
            return None
        existing_learning = next(
            (
                record
                for record in cognitive_memory.get("learning_records", [])
                if isinstance(record, dict) and record.get("source_experience") == experience_id
            ),
            None,
        )
        if existing_learning is not None:
            return deepcopy(existing_learning)
        return self._append_record("learning_records", self._record(
            "learning", source_experience=experience_id,
            source_run=persisted.get("source_run"),
            source_project=persisted.get("project_id"),
            pattern=persisted.get("type"),
            observation=persisted.get("summary", ""),
            outcome=persisted.get("outcome", ""), lesson=lessons[0],
            confidence=0.75,
            applicability="same_project_or_matching_workflow",
        ))

    def retrieve_relevant(self, query: str = "", project_id: str | None = None, goal_id: str | None = None, limit: int = 20) -> dict:
        memory = self._read_cognitive_memory()
        tokens = {token for token in query.lower().split() if len(token) > 2}
        result = {}
        for collection in ("goals", "decisions", "experiences", "learning_records"):
            ranked = []
            for record in memory.get(collection, []):
                record_project = record.get("project_id", record.get("source_project"))
                if record_project and record_project != project_id:
                    continue
                if goal_id and record.get("goal_id") not in {None, goal_id}:
                    continue
                searchable = json.dumps(record, ensure_ascii=False).lower()
                score = sum(1 for token in tokens if token in searchable)
                if project_id and record_project == project_id:
                    score += 100
                if goal_id and record.get("goal_id") == goal_id:
                    score += 100
                if score:
                    record_id = next((value for key, value in record.items() if key.endswith("_id") and key != "source_run"), "")
                    ranked.append((score, record.get("created_at", ""), record_id, record))
            ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
            result[collection] = [deepcopy(row[3]) for row in ranked[:max(0, limit)]]
        return result

    def search(
        self,
        query: str,
        project_id: str | None = None,
        goal_id: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Search bounded cognitive memory using deterministic ranking."""
        if not isinstance(query, str) or len(query) > 500:
            raise MemoryValidationError("memory search query must be at most 500 characters")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise MemoryValidationError("memory search limit must be an integer")
        return self.retrieve_relevant(query, project_id, goal_id, min(max(limit, 0), 100))

    def link(self, source_id: str, target_id: str, relation: str) -> dict:
        """Persist an auditable relationship between two memory records."""
        source_id = self._bounded_text(source_id, "source_id", 128)
        target_id = self._bounded_text(target_id, "target_id", 128)
        relation = self._bounded_text(relation, "relation", 100)
        source_id = self._safe_text(source_id)
        target_id = self._safe_text(target_id)
        relation = self._safe_text(relation)
        return self._append_record(
            "memory_links",
            self._record(
                "memory_link",
                source_id=source_id,
                target_id=target_id,
                relation=relation,
            ),
        )

    def summarize(self, project_id: str | None = None, goal_id: str | None = None) -> dict:
        """Return a bounded deterministic summary of cognitive memory."""
        memory = self._read_cognitive_memory()
        summary = {}
        for collection in ("goals", "decisions", "experiences", "learning_records"):
            records = memory.get(collection, [])
            if project_id:
                records = [r for r in records if r.get("project_id", r.get("source_project")) in {None, project_id}]
            if goal_id:
                records = [r for r in records if r.get("goal_id") in {None, goal_id}]
            summary[collection] = len(records)
        return {"counts": summary, "total": sum(summary.values())}

    def archive(self, collection: str, record_id: str) -> bool:
        """Archive a record without deleting it from memory history."""
        allowed = {"goals", "decisions", "experiences", "learning_records", "artifacts"}
        if collection not in allowed:
            raise MemoryValidationError("unsupported memory archive collection")
        record_id = self._safe_text(record_id).strip()
        if not record_id:
            raise MemoryValidationError("record_id is required")
        id_key = {
            "goals": "goal_id",
            "decisions": "decision_id",
            "experiences": "experience_id",
            "learning_records": "learning_id",
            "artifacts": "artifact_id",
        }[collection]

        def apply(memory):
            records = memory.setdefault(collection, [])
            for record in records:
                if isinstance(record, dict) and record.get(id_key) == record_id:
                    record["archived"] = True
                    record["archived_at"] = datetime.now(UTC).isoformat()
                    return True
            return False

        target_store = (
            self.cognitive_store
            if collection in {"goals", "decisions", "experiences", "learning_records"}
            else self.store
        )
        default_document = (
            self._default_cognitive_memory()
            if collection in {"goals", "decisions", "experiences", "learning_records"}
            else self._default_memory()
        )
        try:
            return bool(target_store.update(apply, default_document))
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    def get_all(self) -> Dict[str, Any]:
        memory = self._read_memory()
        cognitive = self._read_cognitive_memory()
        for key in ("goals", "decisions", "experiences", "learning_records"):
            memory[key] = cognitive[key]
        return memory

    def get_value(self, key: str) -> Any:
        memory = self._read_memory()
        return memory.get(key)

    def get_latest_pipeline_run(self) -> Optional[Dict[str, Any]]:
        memory = self._read_memory()
        return memory.get("latest_pipeline_run")

    # ==========================
    # 🔥 FIXED DETERMINISTIC UPDATE
    # ==========================
    def update(
        self,
        key: str,
        value: Any,
        mode: ModeState | None = None,
    ) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise MemoryValidationError("memory key must contain 1 to 200 characters")
        if self._sensitive_key_pattern.search(key):
            raise MemoryValidationError("credential-like memory keys are not allowed")
        try:
            value_size = len(json.dumps(value, ensure_ascii=False))
        except (TypeError, ValueError, RecursionError) as exc:
            raise MemoryValidationError("memory values must be JSON-compatible") from exc
        if value_size > 250_000:
            raise MemoryValidationError("memory value exceeds the 250000-character limit")
        validated_value = self._redact_nested(
            self._validate_memory_update(key, value)
        )

        mode_context = self._mode_context(
            mode
        )

        def apply(memory):
            if not isinstance(memory, dict):
                raise MemoryValidationError("memory root must be an object")
            schema_version = memory.get("schema_version", 0)
            if schema_version not in {0, 1}:
                raise MemoryValidationError(f"unsupported memory schema version: {schema_version!r}")
            memory.setdefault("schema_version", 1)

            if key == "pipeline_run":
                if not isinstance(validated_value, dict):
                    raise MemoryValidationError("pipeline_run must be a valid dict")
                run_id = validated_value.get("id")
                if not run_id:
                    raise MemoryValidationError("pipeline_run must have an id")
                existing = memory.setdefault("pipeline_runs", [])
                runs = [record for record in existing if isinstance(record, dict) and record.get("id") != run_id]
                run = dict(validated_value)
                if mode_context is not None:
                    run.setdefault("mode_context", mode_context)
                runs.append(run)
                memory["pipeline_runs"] = runs
                memory["latest_pipeline_run"] = run
            elif key == "pipeline_runs":
                if not isinstance(validated_value, list):
                    raise MemoryValidationError("pipeline_runs must be a list")
                unique = {run["id"]: run for run in validated_value if isinstance(run, dict) and run.get("id")}
                memory["pipeline_runs"] = list(unique.values())
            elif key == "latest_pipeline_run":
                if not isinstance(validated_value, dict):
                    raise MemoryValidationError("latest_pipeline_run must be dict")
                memory[key] = validated_value
            else:
                memory[key] = validated_value
            return deepcopy(memory)

        try:
            return self.store.update(apply, self._default_memory())
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc
        
        # ==========================
        # ARTIFACTS
        # ==========================

    def add_artifact(
        self,
        artifact_record: dict
    ):

        self._append_record("artifacts", artifact_record)

        return artifact_record

    def get_artifacts(
        self
    ):

        memory = self._read_memory()

        return memory.get(
            "artifacts",
            []
        )

    def update_artifact(self, artifact_id: str, updates: dict) -> bool:
        if not isinstance(artifact_id, str) or not artifact_id.strip() or len(artifact_id) > 128:
            raise MemoryValidationError("artifact_id is invalid")
        if not isinstance(updates, dict) or set(updates) - {"archived", "archived_at"}:
            raise MemoryValidationError("artifact updates contain unsupported fields")
        if "archived" in updates and not isinstance(updates["archived"], bool):
            raise MemoryValidationError("artifact archived flag must be boolean")
        if "archived_at" in updates and (not isinstance(updates["archived_at"], str) or len(updates["archived_at"]) > 40):
            raise MemoryValidationError("artifact archived timestamp is invalid")

        def apply(memory):
            records = memory.setdefault("artifacts", [])
            for record in records:
                if isinstance(record, dict) and record.get("artifact_id") == artifact_id:
                    record.update(updates)
                    return True
            return False

        try:
            return bool(self.store.update(apply, self._default_memory()))
        except PersistenceIntegrityError as exc:
            raise MemoryValidationError(str(exc)) from exc

    def remove_artifact(self, artifact_id: str) -> bool:
        def remove(memory):
            records = memory.setdefault("artifacts", [])
            remaining = [
                record
                for record in records
                if record.get("artifact_id") != artifact_id
            ]
            memory["artifacts"] = remaining
            return len(remaining) != len(records)

        return bool(self.store.update(remove, self._default_memory()))

    # ==========================
    # FEATURE HISTORY
    # ==========================

    def add_feature_history(
        self,
        record: dict
    ):

        self._append_record("feature_history", record)

        return record

    def get_feature_history(
        self
    ):

        memory = self._read_memory()

        return memory.get(
            "feature_history",
            []
        )
