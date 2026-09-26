import json
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
        if not isinstance(retry_count, int) or retry_count < 0:
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

            pipeline_runs = data.get("pipeline_runs")
            if not isinstance(pipeline_runs, list):
                pipeline_runs = []
            data["pipeline_runs"] = [
                self._validate_pipeline_run(self._normalize_pipeline_run(run))
                for run in pipeline_runs
                if isinstance(run, dict)
            ]

            data["latest_pipeline_run"] = self._validate_pipeline_run(
                self._normalize_pipeline_run(data.get("latest_pipeline_run"))
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
            **fields,
            "created_at": now,
            "updated_at": now,
            "schema_version": 1,
        }

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

    def create_goal(self, title: str, objective: str = "", priority: str = "normal", project_id: str | None = None, parent_goal_id: str | None = None, status: str = "active", blockers: list[str] | None = None) -> dict:
        return self._append_record("goals", self._record(
            "goal", parent_goal_id=parent_goal_id, title=self._safe_text(title),
            objective=self._safe_text(objective), priority=priority, status=status,
            progress=0.0, milestones=[], dependencies=[],
            blockers=[self._safe_text(item) for item in (blockers or [])], project_id=project_id,
            artifact_ids=[],
        ))

    def update_goal(self, goal_id: str, **updates) -> dict:
        allowed = {"title", "objective", "priority", "status", "progress", "milestones", "dependencies", "blockers", "project_id", "artifact_ids"}
        if set(updates) - allowed:
            raise MemoryValidationError("unsupported goal field")
        updates = self._redact_nested(updates)

        def update(memory):
            if memory.get("schema_version") != 1:
                raise MemoryValidationError("unsupported cognitive memory schema version")
            for record in memory.setdefault("goals", []):
                if record.get("goal_id") == goal_id:
                    record.update(updates)
                    record["updated_at"] = datetime.now(UTC).isoformat()
                    return deepcopy(record)
            raise KeyError("goal not found")

        return self.cognitive_store.update(update, self._default_cognitive_memory())

    def record_decision(self, decision: str, reason: str = "", session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None, alternatives: list[str] | None = None, constraints: list[str] | None = None, confidence: float = 0.0) -> dict:
        return self._append_record("decisions", self._record(
            "decision", session_id=session_id, project_id=project_id,
            goal_id=goal_id, decision=self._safe_text(decision), reason=self._safe_text(reason),
            alternatives=[self._safe_text(item) for item in (alternatives or [])],
            constraints=[self._safe_text(item) for item in (constraints or [])],
            confidence=max(0.0, min(1.0, float(confidence))),
        ))

    def record_experience(self, experience_type: str, summary: str, outcome: str, project_id: str | None = None, goal_id: str | None = None, lessons: list[str] | None = None, artifact_ids: list[str] | None = None, source_run: str | None = None, verified: bool = False) -> dict:
        if experience_type not in {"success", "failure", "decision", "workflow"}:
            raise MemoryValidationError("unsupported experience type")
        return self._append_record("experiences", self._record(
            "experience", type=experience_type, project_id=project_id,
            goal_id=goal_id, source_run=source_run, summary=self._safe_text(summary),
            outcome=self._safe_text(outcome), lessons=[self._safe_text(item) for item in (lessons or [])],
            artifact_ids=list(artifact_ids or []), verified=bool(verified),
        ))

    def consolidate_learning(self, experience: dict) -> dict | None:
        lessons = [self._safe_text(lesson.strip()) for lesson in experience.get("lessons", []) if isinstance(lesson, str) and len(lesson.strip()) >= 20]
        if not lessons or experience.get("type") not in {"success", "failure"} or experience.get("verified") is not True:
            return None
        return self._append_record("learning_records", self._record(
            "learning", source_experience=experience.get("experience_id"),
            source_run=experience.get("source_run"),
            source_project=experience.get("project_id"),
            pattern=experience.get("type"),
            observation=experience.get("summary", ""),
            outcome=experience.get("outcome", ""), lesson=lessons[0],
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
        if self._sensitive_key_pattern.search(key):
            raise MemoryValidationError("credential-like memory keys are not allowed")
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