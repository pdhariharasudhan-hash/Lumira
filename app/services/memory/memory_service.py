import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.modes.models.mode_state import (
    ModeState,
)


VALID_STAGES = ["validate", "builder", "execute", "code"]
VALID_STATUSES = ["running", "stopped", "completed"]


class MemoryValidationError(Exception):
    pass


class MemoryService:

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
        self._ensure_file()

    def _default_memory(self) -> Dict[str, Any]:
         return {
            "project_name": "Personal AI Core",

            "pipeline_runs": [],

            "latest_pipeline_run": None,

            "artifacts": [],

            "feature_history": []
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
            content = self.file_path.read_text(encoding="utf-8").strip()

            if not content:
                clean_data = self._default_memory()
                self._write_memory(clean_data)
                return clean_data

            data = json.loads(content)

            if not isinstance(data, dict):
                clean_data = self._default_memory()
                self._write_memory(clean_data)
                return clean_data

            data.setdefault("project_name", "Personal AI Core")

            data.setdefault(
                "artifacts",
                []
            )

            data.setdefault(
                "feature_history",
                []
            )

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

        except json.JSONDecodeError:
            clean_data = self._default_memory()
            self._write_memory(clean_data)
            return clean_data

    def _write_memory(self, data: Dict[str, Any]) -> None:
        self.file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_all(self) -> Dict[str, Any]:
        return self._read_memory()

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
        memory = self._read_memory()
        validated_value = self._validate_memory_update(key, value)

        mode_context = self._mode_context(
            mode
        )

        # -------------------------
        # PIPELINE RUN (append safely, no duplicates)
        # -------------------------
        if key == "pipeline_run":
            if not isinstance(validated_value, dict):
                raise MemoryValidationError("pipeline_run must be a valid dict")

            run_id = validated_value.get("id")
            if not run_id:
                raise MemoryValidationError("pipeline_run must have an id")

            existing_runs = memory.get("pipeline_runs", [])

            # 🔥 REMOVE DUPLICATES
            filtered_runs = [
                r for r in existing_runs
                if isinstance(r, dict) and r.get("id") != run_id
            ]

            if mode_context is not None:
                validated_value = dict(
                    validated_value
                )

                validated_value.setdefault(
                    "mode_context",
                    mode_context,
                )

            filtered_runs.append(
                validated_value
            )

            memory["pipeline_runs"] = filtered_runs
            memory["latest_pipeline_run"] = validated_value

        # -------------------------
        # PIPELINE RUNS (overwrite safely)
        # -------------------------
        elif key == "pipeline_runs":
            if not isinstance(validated_value, list):
                raise MemoryValidationError("pipeline_runs must be a list")

            unique = {}
            for run in validated_value:
                if isinstance(run, dict) and run.get("id"):
                    unique[run["id"]] = run

            memory["pipeline_runs"] = list(unique.values())

        # -------------------------
        # LATEST PIPELINE
        # -------------------------
        elif key == "latest_pipeline_run":
            if not isinstance(validated_value, dict):
                raise MemoryValidationError("latest_pipeline_run must be dict")

            memory["latest_pipeline_run"] = validated_value

        # -------------------------
        # GENERIC KEYS
        # -------------------------
        else:
            memory[key] = validated_value

        self._write_memory(memory)
        return memory
        
        # ==========================
        # ARTIFACTS
        # ==========================

    def add_artifact(
        self,
        artifact_record: dict
    ):

        memory = self._read_memory()

        memory.setdefault(
            "artifacts",
            []
        )

        memory["artifacts"].append(
            artifact_record
        )

        self._write_memory(
            memory
        )

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

        memory = self._read_memory()

        memory.setdefault(
            "feature_history",
            []
        )

        memory["feature_history"].append(
            record
        )

        self._write_memory(
            memory
        )

        return record

    def get_feature_history(
        self
    ):

        memory = self._read_memory()

        return memory.get(
            "feature_history",
            []
        )