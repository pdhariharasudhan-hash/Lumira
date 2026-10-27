import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.memory.memory_service import MemoryService
from app.services.history.event_logger_service import EventLoggerService
from app.services.sessions.session_manager_service import redact_sensitive_text


WORKFLOW_SCHEMA_VERSION = 1
WORKFLOW_STATES = {"planned", "in_progress", "blocked", "completed", "failed"}
TASK_STATES = {"pending", "in_progress", "blocked", "completed", "failed"}


class WorkItemValidationError(ValueError):
    pass


class WorkItemService:
    """Durable, single-user task/workflow tracking for business and operations."""

    MAX_WORKFLOWS = 500
    MAX_TASKS = 20

    def __init__(self, path: str | Path = "memory/work_items.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})

    @staticmethod
    def _status_for_tasks(tasks: list[dict]) -> str:
        statuses = {task.get("status") for task in tasks}
        if statuses == {"completed"}:
            return "completed"
        if "failed" in statuses:
            return "failed"
        if "blocked" in statuses:
            return "blocked"
        if "in_progress" in statuses or "completed" in statuses:
            return "in_progress"
        return "planned"

    @staticmethod
    def _validate_document(document: object) -> dict:
        if not isinstance(document, dict) or document.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
            raise PersistenceIntegrityError("Unsupported workflow store schema")
        workflows = document.get("workflows")
        if not isinstance(workflows, list) or len(workflows) > WorkItemService.MAX_WORKFLOWS:
            raise PersistenceIntegrityError("Workflow store must contain a bounded workflows list")
        seen_workflow_ids = set()
        for workflow in workflows:
            if not isinstance(workflow, dict) or not isinstance(workflow.get("tasks"), list):
                raise PersistenceIntegrityError("Workflow record is incomplete")
            workflow_id = workflow.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id or workflow_id in seen_workflow_ids:
                raise PersistenceIntegrityError("Workflow has an invalid or duplicate ID")
            seen_workflow_ids.add(workflow_id)
            title = workflow.get("title")
            request = workflow.get("request")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                raise PersistenceIntegrityError("Workflow has an invalid title")
            if not isinstance(request, str) or not request.strip() or len(request) > 10_000:
                raise PersistenceIntegrityError("Workflow has an invalid request")
            for timestamp_field in ("created_at", "updated_at"):
                timestamp = workflow.get(timestamp_field)
                if not isinstance(timestamp, str) or not timestamp or len(timestamp) > 40:
                    raise PersistenceIntegrityError("Workflow has an invalid timestamp")
            category = workflow.get("category")
            if not isinstance(category, str) or category not in {"business", "operations"}:
                raise PersistenceIntegrityError("Workflow has an invalid category")
            workflow_status = workflow.get("status")
            if not isinstance(workflow_status, str) or workflow_status not in WORKFLOW_STATES:
                raise PersistenceIntegrityError("Workflow has an invalid status")
            plan_metadata = workflow.get("plan_metadata")
            if plan_metadata is not None:
                if not isinstance(plan_metadata, dict):
                    raise PersistenceIntegrityError("Workflow plan metadata must be an object")
                try:
                    metadata_size = len(json.dumps(plan_metadata, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                except (TypeError, ValueError, RecursionError) as exc:
                    raise PersistenceIntegrityError("Workflow plan metadata is not valid JSON") from exc
                if metadata_size > 10_000:
                    raise PersistenceIntegrityError("Workflow plan metadata exceeds its size limit")
            if not 1 <= len(workflow["tasks"]) <= WorkItemService.MAX_TASKS:
                raise PersistenceIntegrityError("Workflow has an invalid task count")
            seen_task_ids = set()
            for task in workflow["tasks"]:
                if not isinstance(task, dict):
                    raise PersistenceIntegrityError("Workflow contains an invalid task")
                task_id = task.get("task_id")
                if not isinstance(task_id, str) or not task_id or task_id in seen_task_ids:
                    raise PersistenceIntegrityError("Workflow contains an invalid or duplicate task ID")
                seen_task_ids.add(task_id)
                task_status = task.get("status")
                if not isinstance(task_status, str) or task_status not in TASK_STATES:
                    raise PersistenceIntegrityError("Workflow contains an invalid task status")
                dependencies = task.get("dependencies", [])
                if (
                    not isinstance(dependencies, list)
                    or len(dependencies) > WorkItemService.MAX_TASKS
                    or any(
                        not isinstance(dependency, str) or not dependency
                        or len(dependency) > 128
                        for dependency in dependencies
                    )
                ):
                    raise PersistenceIntegrityError("Workflow contains invalid task dependencies")
                title = task.get("title")
                if not isinstance(title, str) or not title.strip() or len(title) > 500:
                    raise PersistenceIntegrityError("Workflow contains an invalid task title")
                history = task.get("history", [])
                if not isinstance(history, list) or len(history) > 20:
                    raise PersistenceIntegrityError("Workflow task history must be a bounded list")
                for timestamp_field in ("created_at", "updated_at"):
                    timestamp = task.get(timestamp_field)
                    if not isinstance(timestamp, str) or not timestamp or len(timestamp) > 40:
                        raise PersistenceIntegrityError("Workflow task has an invalid timestamp")

            # Dependency references are persisted input: validate them against
            # this workflow instead of allowing phantom IDs or cycles to leave
            # tasks permanently blocked.
            task_ids = {task["task_id"] for task in workflow["tasks"]}
            graph = {}
            for task in workflow["tasks"]:
                task_id = task["task_id"]
                dependencies = task.get("dependencies", [])
                if len(set(dependencies)) != len(dependencies):
                    raise PersistenceIntegrityError("Workflow contains duplicate task dependencies")
                if task_id in dependencies:
                    raise PersistenceIntegrityError("Workflow task cannot depend on itself")
                if any(dependency not in task_ids for dependency in dependencies):
                    raise PersistenceIntegrityError("Workflow task dependency does not exist")
                graph[task_id] = dependencies

            visiting = set()
            visited = set()

            def visit(task_id):
                if task_id in visiting:
                    raise PersistenceIntegrityError("Workflow task dependencies contain a cycle")
                if task_id in visited:
                    return
                visiting.add(task_id)
                for dependency in graph[task_id]:
                    visit(dependency)
                visiting.remove(task_id)
                visited.add(task_id)

            for task_id in graph:
                visit(task_id)

            expected_status = WorkItemService._status_for_tasks(workflow["tasks"])
            if workflow_status != expected_status:
                raise PersistenceIntegrityError(
                    "Workflow status does not match its task states"
                )
        return document

    def create_workflow(
        self,
        category: str,
        title: str,
        request: str,
        tasks: list[str],
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        goal_id: str | None = None,
        plan_metadata: dict | None = None,
    ) -> dict:
        if not isinstance(category, str) or category not in {"business", "operations"}:
            raise WorkItemValidationError("Workflow category must be business or operations")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise WorkItemValidationError("Workflow title must contain 1 to 200 characters")
        if not isinstance(request, str) or not 1 <= len(request.strip()) <= 10_000:
            raise WorkItemValidationError("Workflow request must contain 1 to 10000 characters")
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= self.MAX_TASKS:
            raise WorkItemValidationError(f"Workflow must contain 1 to {self.MAX_TASKS} tasks")
        if any(not isinstance(task, str) or not 1 <= len(task.strip()) <= 500 for task in tasks):
            raise WorkItemValidationError("Every task must contain 1 to 500 characters")
        if plan_metadata is not None:
            if not isinstance(plan_metadata, dict):
                raise WorkItemValidationError("plan_metadata must be an object")
            try:
                metadata_size = len(json.dumps(plan_metadata, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            except (TypeError, ValueError, RecursionError) as exc:
                raise WorkItemValidationError("plan_metadata must contain JSON-compatible values") from exc
            if metadata_size > 10_000:
                raise WorkItemValidationError("plan_metadata exceeds 10000 bytes")
        for field, value in (
            ("session_id", session_id),
            ("project_id", project_id),
            ("goal_id", goal_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 128
            ):
                raise WorkItemValidationError(f"{field} must be a non-empty identifier of at most 128 characters")

        now = datetime.now(UTC).isoformat()
        workflow_id = str(uuid4())
        records = []
        task_ids: list[str] = []
        for task in tasks:
            task_id = str(uuid4())
            records.append({
                "task_id": task_id,
                "title": redact_sensitive_text(task.strip()),
                "status": "pending",
                "dependencies": [task_ids[-1]] if task_ids else [],
                "blocker": None,
                "result": None,
                "history": [{"status": "pending", "at": now, "reason": "created"}],
                "created_at": now,
                "updated_at": now,
            })
            task_ids.append(task_id)
        workflow = {
            "workflow_id": workflow_id,
            "owner_id": "local",
            "category": category,
            "title": redact_sensitive_text(title.strip()),
            "request": redact_sensitive_text(request.strip()),
            "status": "planned",
            "session_id": session_id,
            "project_id": project_id,
            "goal_id": goal_id,
            "plan_metadata": deepcopy(plan_metadata) if plan_metadata is not None else None,
            "tasks": records,
            "created_at": now,
            "updated_at": now,
            "schema_version": WORKFLOW_SCHEMA_VERSION,
        }

        def append(document):
            self._validate_document(document)
            if len(document["workflows"]) >= self.MAX_WORKFLOWS:
                raise WorkItemValidationError(
                    "Workflow capacity reached; archive or remove old workflows before creating another"
                )
            document["workflows"].append(workflow)
            return deepcopy(workflow)

        try:
            return self.store.update(append, {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})
        except PersistenceIntegrityError:
            raise

    def get_workflow(self, workflow_id: str) -> dict | None:
        document = self._validate_document(self.store.read({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []}))
        workflow = next((item for item in document["workflows"] if item.get("workflow_id") == workflow_id), None)
        return deepcopy(workflow) if workflow else None

    def list_workflows(self, *, category: str | None = None, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
        if not 0 <= limit <= 200:
            raise WorkItemValidationError("limit must be between 0 and 200")
        document = self._validate_document(self.store.read({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []}))
        workflows = document["workflows"]
        if category:
            workflows = [item for item in workflows if item.get("category") == category]
        if session_id:
            workflows = [item for item in workflows if item.get("session_id") == session_id]
        if project_id:
            workflows = [item for item in workflows if item.get("project_id") == project_id]
        if goal_id:
            workflows = [item for item in workflows if item.get("goal_id") == goal_id]
        if status:
            if status not in WORKFLOW_STATES:
                raise WorkItemValidationError("Unsupported workflow status")
            workflows = [item for item in workflows if item.get("status") == status]
        return deepcopy(sorted(workflows, key=lambda item: item["created_at"], reverse=True)[:limit])

    def get_workflow_progress(self, workflow_id: str) -> dict:
        """Return a bounded, read-only progress summary and dependency-ready tasks."""
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise KeyError("workflow not found")

        tasks = workflow.get("tasks", [])
        completed_ids = {
            task.get("task_id") for task in tasks
            if task.get("status") == "completed"
        }
        failed_ids = {
            task.get("task_id") for task in tasks
            if task.get("status") == "failed"
        }
        completed_count = len(completed_ids)
        total_count = len(tasks)
        ready_tasks = []
        active_tasks = []
        blocked_tasks = []

        for task in tasks:
            status = task.get("status")
            dependencies = task.get("dependencies", [])
            unmet = [
                dependency for dependency in dependencies
                if dependency not in completed_ids
            ]
            item = {
                "task_id": task.get("task_id"),
                "title": task.get("title"),
                "status": status,
                "dependencies": list(dependencies)[:20],
                "unmet_dependencies": unmet[:20],
                "blocker": task.get("blocker"),
            }
            if status == "in_progress":
                active_tasks.append(item)
            elif status == "pending" and not unmet:
                ready_tasks.append(item)
            elif status == "blocked":
                item["dependency_failure"] = any(dep in failed_ids for dep in unmet)
                item["manually_blocked"] = not unmet
                blocked_tasks.append(item)
            elif status == "pending" and unmet:
                item["dependency_failure"] = any(dep in failed_ids for dep in unmet)
                blocked_tasks.append(item)

        return {
            "workflow_id": workflow_id,
            "title": workflow.get("title"),
            "status": workflow.get("status"),
            "progress": {
                "completed": completed_count,
                "total": total_count,
                "percent": round((completed_count / total_count) * 100) if total_count else 0,
            },
            "ready_tasks": ready_tasks[:20],
            "active_tasks": active_tasks[:20],
            "blocked_tasks": blocked_tasks[:20],
            "failed_tasks": [
                {
                    "task_id": task.get("task_id"),
                    "title": task.get("title"),
                    "blocker": task.get("blocker"),
                    "result": task.get("result"),
                }
                for task in tasks if task.get("status") == "failed"
            ][:20],
            "is_complete": bool(total_count) and completed_count == total_count,
        }

    def get_task_history(self, workflow_id: str, task_id: str) -> dict:
        """Return the bounded status and outcome history for one workflow task."""
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise KeyError("workflow not found")
        task = next((item for item in workflow.get("tasks", []) if item.get("task_id") == task_id), None)
        if task is None:
            raise KeyError("task not found")
        history = task.get("history", [])
        if not isinstance(history, list):
            raise PersistenceIntegrityError("Workflow task history must be a list")
        return {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "title": task.get("title"),
            "current_status": task.get("status"),
            "history": deepcopy(history[-20:]),
        }

    def update_task(self, workflow_id: str, task_id: str, status: str, blocker: str | None = None, result: str | None = None) -> dict:
        if not isinstance(status, str) or status not in TASK_STATES:
            raise WorkItemValidationError("Unsupported task status")
        if blocker is not None and (not isinstance(blocker, str) or len(blocker) > 1000):
            raise WorkItemValidationError("blocker must be at most 1000 characters")
        if result is not None and (not isinstance(result, str) or len(result) > 4000):
            raise WorkItemValidationError("result must be at most 4000 characters")
        updated = {}
        transition = {"previous_status": None}

        def mutate(document):
            self._validate_document(document)
            workflow = next((item for item in document["workflows"] if item.get("workflow_id") == workflow_id), None)
            if workflow is None:
                raise KeyError("workflow not found")
            task = next((item for item in workflow["tasks"] if item.get("task_id") == task_id), None)
            if task is None:
                raise KeyError("task not found")
            current_status = task.get("status")
            transition["previous_status"] = current_status
            allowed_transitions = {
                "pending": {"pending", "in_progress", "blocked"},
                "in_progress": {"in_progress", "completed", "blocked", "failed"},
                "blocked": {"blocked", "pending", "in_progress", "failed"},
                "failed": {"failed", "pending", "in_progress", "blocked"},
                # Completion is terminal: do not silently reopen completed work.
                "completed": {"completed"},
            }
            if status not in allowed_transitions.get(current_status, set()):
                raise WorkItemValidationError(
                    f"Task status cannot transition from {current_status} to {status}"
                )
            dependencies = set(task.get("dependencies", []))
            completed = {item["task_id"] for item in workflow["tasks"] if item.get("status") == "completed"}
            if status in {"in_progress", "completed"} and not dependencies.issubset(completed):
                raise WorkItemValidationError("Task dependencies must be completed first")
            if status == "completed" and current_status not in {"in_progress", "completed"}:
                raise WorkItemValidationError("A task must be in progress before completion")
            updated_at = datetime.now(UTC).isoformat()
            history = task.setdefault("history", [])
            if not isinstance(history, list):
                raise PersistenceIntegrityError("Workflow task history must be a list")
            if current_status != status or blocker is not None or result is not None:
                history.append({
                    "previous_status": current_status,
                    "status": status,
                    "at": updated_at,
                    "blocker": redact_sensitive_text(blocker) if blocker else None,
                    "result": redact_sensitive_text(result) if result else None,
                })
                task["history"] = history[-20:]
            task["status"] = status
            task["blocker"] = redact_sensitive_text(blocker) if blocker else None
            task["result"] = redact_sensitive_text(result) if result else None
            task["updated_at"] = updated_at
            workflow["status"] = self._status_for_tasks(workflow["tasks"])
            workflow["updated_at"] = task["updated_at"]
            updated.update(deepcopy(workflow))
            return True

        self.store.update(mutate, {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})
        try:
            EventLoggerService().log(
                event="workflow_task_transition",
                source="work_items",
                data={
                    "workflow_id": workflow_id,
                    "task_id": task_id,
                    "previous_status": transition["previous_status"],
                    "status": status,
                    "goal_id": updated.get("goal_id"),
                    "project_id": updated.get("project_id"),
                    "timestamp": updated.get("updated_at"),
                },
            )
            updated["event_log_status"] = "recorded"
        except Exception:
            # Durable task history is authoritative if the secondary event log fails.
            updated["event_log_status"] = "recording_failed"
        linked_goal_id = updated.get("goal_id")
        if linked_goal_id:
            try:
                workflow_document = self._validate_document(
                    self.store.read({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})
                )
                linked_workflows = [
                    item for item in workflow_document["workflows"]
                    if item.get("goal_id") == linked_goal_id
                ]
                task_states = [
                    task_record
                    for workflow_record in linked_workflows
                    for task_record in workflow_record.get("tasks", [])
                ]
                total_linked_tasks = len(task_states)
                completed_linked_tasks = sum(1 for task_record in task_states if task_record.get("status") == "completed")
                computed_progress = round((completed_linked_tasks / total_linked_tasks) * 100, 2) if total_linked_tasks else 0
                memory = MemoryService()
                goal_record = next(
                    (item for item in memory.get_all().get("goals", []) if item.get("goal_id") == linked_goal_id),
                    None,
                )
                if goal_record is not None and float(goal_record.get("progress", 0) or 0) != computed_progress:
                    memory.update_goal(linked_goal_id, progress=computed_progress)
                updated["goal_progress_status"] = "updated" if goal_record is not None else "goal_not_found"
                updated["goal_progress"] = computed_progress
            except Exception:
                # Task state is already durable; a secondary goal-progress failure
                # must be observable without rolling back the primary transition.
                updated["goal_progress_status"] = "recording_failed"
        else:
            updated["goal_progress_status"] = "not_applicable"
        task = next((item for item in updated.get("tasks", []) if item.get("task_id") == task_id), None)
        if task is not None and task.get("status") in {"completed", "failed"} and transition["previous_status"] != status:
            try:
                memory = MemoryService()
                outcome = "success" if status == "completed" else "failure"
                lesson = (
                    "Task completion was explicitly recorded after all declared dependencies were completed."
                    if status == "completed"
                    else "Task was explicitly marked failed; inspect its blocker and result before retrying."
                )
                experience = memory.record_experience(
                    experience_type=outcome,
                    summary=f"Workflow task {task.get('title', task_id)} ({status})",
                    outcome=task.get("result") or task.get("blocker") or status,
                    project_id=updated.get("project_id"),
                    goal_id=updated.get("goal_id"),
                    lessons=[lesson],
                    source_run=f"{workflow_id}:{task_id}:{status}:{task.get('updated_at', '')}",
                    verified=True,
                )
                learning = memory.consolidate_learning(experience)
                updated["learning_status"] = "consolidated" if learning else "experience_recorded"
            except Exception:
                # The work-item transition is already durable; report the secondary
                # learning failure without undoing or misreporting that transition.
                updated["learning_status"] = "recording_failed"
        else:
            updated["learning_status"] = "not_applicable"
        return updated
