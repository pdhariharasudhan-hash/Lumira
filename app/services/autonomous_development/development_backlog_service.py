from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value


BACKLOG_SCHEMA_VERSION = 1
TASK_STATES = {"planned", "in_progress", "blocked", "completed", "failed"}
PROGRAM_STATES = {"planned", "in_progress", "blocked", "completed"}


class DevelopmentBacklogService:
    """Durable autonomous-development program and task backlog."""

    MAX_PROGRAMS = 20
    MAX_TASKS_PER_PROGRAM = 50
    MAX_ATTEMPTS = 3
    MAX_LESSONS = 200

    def __init__(self, path: str | Path = "memory/development_backlog.json") -> None:
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})

    @staticmethod
    def _validate(document: object) -> dict[str, Any]:
        if not isinstance(document, dict) or document.get("schema_version") != BACKLOG_SCHEMA_VERSION:
            raise PersistenceIntegrityError("Unsupported development backlog schema")
        programs = document.get("programs")
        lessons = document.get("lessons")
        if not isinstance(programs, list) or not isinstance(lessons, list):
            raise PersistenceIntegrityError("Development backlog collections are invalid")
        if len(programs) > DevelopmentBacklogService.MAX_PROGRAMS:
            raise PersistenceIntegrityError("Too many development programs")
        required_task_fields = {
            "task_id", "goal", "objective", "category", "priority", "dependencies",
            "relevant_files", "acceptance_criteria", "validation_commands", "status",
            "attempts", "iteration", "last_error", "last_validation", "created_at",
            "updated_at", "recovery_run_id",
        }
        for program in programs:
            if not isinstance(program, dict) or not isinstance(program.get("tasks"), list):
                raise PersistenceIntegrityError("Development program is incomplete")
            if program.get("status") not in PROGRAM_STATES:
                raise PersistenceIntegrityError("Development program state is invalid")
            if len(program["tasks"]) > DevelopmentBacklogService.MAX_TASKS_PER_PROGRAM:
                raise PersistenceIntegrityError("Development program exceeds task limit")
            ids = {task.get("task_id") for task in program["tasks"] if isinstance(task, dict)}
            for task in program["tasks"]:
                if not isinstance(task, dict) or not required_task_fields.issubset(task):
                    raise PersistenceIntegrityError("Development task is incomplete")
                if task["status"] not in TASK_STATES:
                    raise PersistenceIntegrityError("Development task state is invalid")
                if not isinstance(task["dependencies"], list) or not set(task["dependencies"]).issubset(ids):
                    raise PersistenceIntegrityError("Development task dependencies are invalid")
        return document

    def get_program(self, program_id: str) -> dict[str, Any] | None:
        document = self._validate(self.store.read({"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []}))
        program = next((item for item in document["programs"] if item["program_id"] == program_id), None)
        return deepcopy(program) if program else None

    def list_programs(self, *, status: str | None = None) -> list[dict[str, Any]]:
        document = self._validate(self.store.read({"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []}))
        programs = document["programs"]
        if status is not None:
            programs = [program for program in programs if program["status"] == status]
        return deepcopy(sorted(programs, key=lambda item: item["created_at"], reverse=True))

    def active_program(self) -> dict[str, Any] | None:
        programs = self.list_programs()
        return next((item for item in programs if item["status"] in {"planned", "in_progress", "blocked"}), None)

    def latest_program(self) -> dict[str, Any] | None:
        programs = self.list_programs()
        return programs[0] if programs else None

    def append_tasks(self, program_id: str, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(tasks, list):
            raise ValueError("Development tasks must be a list")
        now = datetime.now(UTC).isoformat()
        updated: dict[str, Any] = {}

        def mutate(document: dict[str, Any]) -> bool:
            self._validate(document)
            program = next((item for item in document["programs"] if item["program_id"] == program_id), None)
            if program is None:
                raise KeyError("development program not found")
            existing = {task["objective"].casefold() for task in program["tasks"]}
            for source in tasks:
                objective = source.get("objective") if isinstance(source, dict) else None
                if not isinstance(objective, str) or not objective.strip() or objective.casefold() in existing:
                    continue
                if len(program["tasks"]) >= self.MAX_TASKS_PER_PROGRAM:
                    break
                record = {
                    "task_id": str(uuid4()),
                    "goal": program["goal"],
                    "objective": redact_sensitive_text(objective.strip()),
                    "category": str(source.get("category", "implementation"))[:80],
                    "priority": max(0, min(int(source.get("priority", 50)), 100)),
                    "dependencies": [],
                    "relevant_files": [str(path)[:500] for path in source.get("relevant_files", []) if isinstance(path, str)][:12],
                    "acceptance_criteria": [redact_sensitive_text(str(value))[:1000] for value in source.get("acceptance_criteria", [])][:10],
                    "validation_commands": [list(command) for command in source.get("validation_commands", [["python", "-m", "pytest", "-q"]]) if isinstance(command, (list, tuple))][:5],
                    "status": "planned",
                    "attempts": 0,
                    "iteration": 0,
                    "last_error": None,
                    "last_validation": None,
                    "recovery_run_id": None,
                    "source_workflow_id": source.get("source_workflow_id"),
                    "audit_evidence": redact_sensitive_value(source.get("audit_evidence")),
                    "resume_run_id": source.get("recovery_run_id"),
                    "created_at": now,
                    "updated_at": now,
                    "order": len(program["tasks"]),
                }
                program["tasks"].append(record)
                existing.add(objective.casefold())
            if any(task["status"] == "planned" for task in program["tasks"]):
                program["status"] = "planned" if not program.get("current_task_id") else "in_progress"
            program["updated_at"] = now
            updated.update(deepcopy(program))
            return True

        self.store.update(mutate, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})
        return updated

    def create_program(self, goal: str, tasks: list[dict[str, Any]], *, audit: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 10_000:
            raise ValueError("Development program goal must contain 1 to 10000 characters")
        if not isinstance(tasks, list) or len(tasks) > self.MAX_TASKS_PER_PROGRAM:
            raise ValueError(f"Development program may contain at most {self.MAX_TASKS_PER_PROGRAM} tasks")
        now = datetime.now(UTC).isoformat()
        task_ids = [str(uuid4()) for _ in tasks]
        records: list[dict[str, Any]] = []
        for index, (task, task_id) in enumerate(zip(tasks, task_ids)):
            objective = task.get("objective") if isinstance(task, dict) else None
            if not isinstance(objective, str) or not objective.strip():
                raise ValueError("Every development task requires an objective")
            dependencies = task.get("dependencies", [])
            if not isinstance(dependencies, list):
                raise ValueError("Task dependencies must be a list")
            dependency_ids = [
                task_ids[value] if isinstance(value, int) and 0 <= value < len(task_ids)
                else value for value in dependencies
            ]
            records.append({
                "task_id": task_id,
                "goal": redact_sensitive_text(goal.strip()),
                "objective": redact_sensitive_text(objective.strip()),
                "category": str(task.get("category", "implementation"))[:80],
                "priority": max(0, min(int(task.get("priority", 50)), 100)),
                "dependencies": dependency_ids,
                "relevant_files": [str(path)[:500] for path in task.get("relevant_files", []) if isinstance(path, str)][:12],
                "acceptance_criteria": [redact_sensitive_text(str(value))[:1000] for value in task.get("acceptance_criteria", [])][:10],
                "validation_commands": [list(command) for command in task.get("validation_commands", [["python", "-m", "pytest", "-q"]]) if isinstance(command, (list, tuple))][:5],
                "status": "planned",
                "attempts": 0,
                "iteration": 0,
                "last_error": None,
                "last_validation": None,
                "recovery_run_id": None,
                "source_workflow_id": task.get("source_workflow_id"),
                "audit_evidence": redact_sensitive_value(task.get("audit_evidence")),
                "resume_run_id": task.get("recovery_run_id"),
                "created_at": now,
                "updated_at": now,
                "order": index,
            })

        program = {
            "program_id": str(uuid4()),
            "goal": redact_sensitive_text(goal.strip()),
            "status": "planned",
            "audit": redact_sensitive_value(audit),
            "tasks": records,
            "current_task_id": None,
            "completion_blockers": [],
            "created_at": now,
            "updated_at": now,
        }

        def append(document: dict[str, Any]) -> dict[str, Any]:
            self._validate(document)
            document["programs"].append(program)
            document["programs"] = document["programs"][-self.MAX_PROGRAMS:]
            return deepcopy(program)

        return self.store.update(append, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})

    def update_audit(self, program_id: str, audit: dict[str, Any]) -> dict[str, Any]:
        updated: dict[str, Any] = {}
        now = datetime.now(UTC).isoformat()

        def mutate(document: dict[str, Any]) -> bool:
            self._validate(document)
            program = next((item for item in document["programs"] if item["program_id"] == program_id), None)
            if program is None:
                raise KeyError("development program not found")
            program["audit"] = redact_sensitive_value(audit)
            program["updated_at"] = now
            updated.update(deepcopy(program))
            return True

        self.store.update(mutate, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})
        return updated

    def next_ready_task(
        self,
        program_id: str,
        *,
        exclude_task_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        program = self.get_program(program_id)
        if program is None:
            return None
        completed = {task["task_id"] for task in program["tasks"] if task["status"] == "completed"}
        excluded = exclude_task_ids or set()
        candidates = [
            task for task in program["tasks"]
            if task["status"] == "planned"
            and task["task_id"] not in excluded
            and set(task["dependencies"]).issubset(completed)
            and task["attempts"] < self.MAX_ATTEMPTS
        ]
        return deepcopy(sorted(candidates, key=lambda task: (-task["priority"], task["order"], task["created_at"]))[0]) if candidates else None

    def update_task(self, program_id: str, task_id: str, **updates: Any) -> dict[str, Any]:
        allowed = {"status", "attempts", "iteration", "last_error", "last_validation", "recovery_run_id", "relevant_files", "acceptance_criteria"}
        if set(updates) - allowed:
            raise ValueError("Unsupported development-task update")
        if "status" in updates and updates["status"] not in TASK_STATES:
            raise ValueError("Unsupported development-task status")
        now = datetime.now(UTC).isoformat()
        updated: dict[str, Any] = {}

        def mutate(document: dict[str, Any]) -> bool:
            self._validate(document)
            program = next((item for item in document["programs"] if item["program_id"] == program_id), None)
            if program is None:
                raise KeyError("development program not found")
            task = next((item for item in program["tasks"] if item["task_id"] == task_id), None)
            if task is None:
                raise KeyError("development task not found")
            for key, value in updates.items():
                if key in {"last_error", "last_validation"}:
                    task[key] = redact_sensitive_value(value)
                elif key in {"relevant_files", "acceptance_criteria"}:
                    task[key] = redact_sensitive_value(value)
                else:
                    task[key] = redact_sensitive_text(str(value)) if isinstance(value, str) else value
            task["updated_at"] = now
            if task["status"] == "in_progress":
                program["current_task_id"] = task_id
            elif program.get("current_task_id") == task_id:
                program["current_task_id"] = None
            statuses = {item["status"] for item in program["tasks"]}
            if statuses == {"completed"}:
                program["status"] = "completed"
            elif "in_progress" in statuses or "planned" in statuses:
                program["status"] = "in_progress"
            elif statuses.intersection({"blocked", "failed"}):
                program["status"] = "blocked"
            program["updated_at"] = now
            updated.update(deepcopy(task))
            return True

        self.store.update(mutate, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})
        return updated

    def set_program_status(
        self,
        program_id: str,
        status: str,
        *,
        completion_blockers: list[str] | None = None,
    ) -> dict[str, Any]:
        if status not in PROGRAM_STATES:
            raise ValueError("Unsupported development program status")
        updated: dict[str, Any] = {}
        now = datetime.now(UTC).isoformat()

        def mutate(document: dict[str, Any]) -> bool:
            self._validate(document)
            program = next((item for item in document["programs"] if item["program_id"] == program_id), None)
            if program is None:
                raise KeyError("development program not found")
            program["status"] = status
            if completion_blockers is not None:
                program["completion_blockers"] = [
                    redact_sensitive_text(str(item))[:1000]
                    for item in completion_blockers[:20]
                ]
            program["updated_at"] = now
            updated.update(deepcopy(program))
            return True

        self.store.update(mutate, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})
        return updated

    def link_recovery_run(self, program_id: str, task_id: str, recovery_run_id: str) -> dict[str, Any]:
        return self.update_task(program_id, task_id, recovery_run_id=recovery_run_id)

    def add_lesson(self, lesson: dict[str, Any]) -> None:
        safe = redact_sensitive_value(lesson)
        now = datetime.now(UTC).isoformat()

        def append(document: dict[str, Any]) -> bool:
            self._validate(document)
            document["lessons"].append({"lesson_id": str(uuid4()), "created_at": now, **safe})
            document["lessons"] = document["lessons"][-self.MAX_LESSONS:]
            return True

        self.store.update(append, {"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []})

    def lessons(self, limit: int = 20) -> list[dict[str, Any]]:
        if not 0 <= limit <= self.MAX_LESSONS:
            raise ValueError("lesson limit is out of range")
        document = self._validate(self.store.read({"schema_version": BACKLOG_SCHEMA_VERSION, "programs": [], "lessons": []}))
        return deepcopy(document["lessons"][-limit:]) if limit else []