from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
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
    def _validate_document(document: object) -> dict:
        if not isinstance(document, dict) or document.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
            raise PersistenceIntegrityError("Unsupported workflow store schema")
        workflows = document.get("workflows")
        if not isinstance(workflows, list):
            raise PersistenceIntegrityError("Workflow store must contain a workflows list")
        for workflow in workflows:
            if not isinstance(workflow, dict) or not isinstance(workflow.get("tasks"), list):
                raise PersistenceIntegrityError("Workflow record is incomplete")
            if workflow.get("status") not in WORKFLOW_STATES:
                raise PersistenceIntegrityError("Workflow has an invalid status")
            if len(workflow["tasks"]) > WorkItemService.MAX_TASKS:
                raise PersistenceIntegrityError("Workflow contains too many tasks")
            if any(not isinstance(task, dict) or task.get("status") not in TASK_STATES for task in workflow["tasks"]):
                raise PersistenceIntegrityError("Workflow contains an invalid task")
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
    ) -> dict:
        if category not in {"business", "operations"}:
            raise WorkItemValidationError("Workflow category must be business or operations")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise WorkItemValidationError("Workflow title must contain 1 to 200 characters")
        if not isinstance(request, str) or not 1 <= len(request.strip()) <= 10_000:
            raise WorkItemValidationError("Workflow request must contain 1 to 10000 characters")
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= self.MAX_TASKS:
            raise WorkItemValidationError(f"Workflow must contain 1 to {self.MAX_TASKS} tasks")
        if any(not isinstance(task, str) or not 1 <= len(task.strip()) <= 500 for task in tasks):
            raise WorkItemValidationError("Every task must contain 1 to 500 characters")

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
            "tasks": records,
            "created_at": now,
            "updated_at": now,
            "schema_version": WORKFLOW_SCHEMA_VERSION,
        }

        def append(document):
            self._validate_document(document)
            document["workflows"].append(workflow)
            document["workflows"] = document["workflows"][-self.MAX_WORKFLOWS:]
            return deepcopy(workflow)

        try:
            return self.store.update(append, {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})
        except PersistenceIntegrityError:
            raise

    def get_workflow(self, workflow_id: str) -> dict | None:
        document = self._validate_document(self.store.read({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []}))
        workflow = next((item for item in document["workflows"] if item.get("workflow_id") == workflow_id), None)
        return deepcopy(workflow) if workflow else None

    def list_workflows(self, *, category: str | None = None, session_id: str | None = None, limit: int = 50) -> list[dict]:
        if not 0 <= limit <= 200:
            raise WorkItemValidationError("limit must be between 0 and 200")
        document = self._validate_document(self.store.read({"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []}))
        workflows = document["workflows"]
        if category:
            workflows = [item for item in workflows if item.get("category") == category]
        if session_id:
            workflows = [item for item in workflows if item.get("session_id") == session_id]
        return deepcopy(sorted(workflows, key=lambda item: item["created_at"], reverse=True)[:limit])

    def update_task(self, workflow_id: str, task_id: str, status: str, blocker: str | None = None, result: str | None = None) -> dict:
        if status not in TASK_STATES:
            raise WorkItemValidationError("Unsupported task status")
        if blocker is not None and (not isinstance(blocker, str) or len(blocker) > 1000):
            raise WorkItemValidationError("blocker must be at most 1000 characters")
        if result is not None and (not isinstance(result, str) or len(result) > 4000):
            raise WorkItemValidationError("result must be at most 4000 characters")
        updated = {}

        def mutate(document):
            self._validate_document(document)
            workflow = next((item for item in document["workflows"] if item.get("workflow_id") == workflow_id), None)
            if workflow is None:
                raise KeyError("workflow not found")
            task = next((item for item in workflow["tasks"] if item.get("task_id") == task_id), None)
            if task is None:
                raise KeyError("task not found")
            dependencies = set(task.get("dependencies", []))
            completed = {item["task_id"] for item in workflow["tasks"] if item.get("status") == "completed"}
            if status in {"in_progress", "completed"} and not dependencies.issubset(completed):
                raise WorkItemValidationError("Task dependencies must be completed first")
            if status == "completed":
                if task.get("status") not in {"in_progress", "completed"}:
                    raise WorkItemValidationError("A task must be in progress before completion")
            task["status"] = status
            task["blocker"] = redact_sensitive_text(blocker) if blocker else None
            task["result"] = redact_sensitive_text(result) if result else None
            task["updated_at"] = datetime.now(UTC).isoformat()
            statuses = {item["status"] for item in workflow["tasks"]}
            workflow["status"] = "completed" if statuses == {"completed"} else "failed" if "failed" in statuses else "blocked" if "blocked" in statuses else "in_progress" if "in_progress" in statuses or "completed" in statuses else "planned"
            workflow["updated_at"] = task["updated_at"]
            updated.update(deepcopy(workflow))
            return True

        self.store.update(mutate, {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflows": []})
        return updated
