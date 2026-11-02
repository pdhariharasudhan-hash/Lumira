from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.work_items.work_item_service import WorkItemService, WorkItemValidationError
from app.services.planner.planner_service import PlannerService
from app.services.sessions.session_manager_service import SessionManagerService

router = APIRouter()

def _normalize_optional_filter(value):
    return value if isinstance(value, str) else None

def _goals_from_memory(memory):
    data = memory.get_all()
    # Test doubles and alternate stores may expose the goal list directly.
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    goals = data.get("goals")
    if isinstance(goals, list):
        return goals
    nested = data.get("memory")
    return nested.get("goals", []) if isinstance(nested, dict) and isinstance(nested.get("goals"), list) else []


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(default="", max_length=2000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    project_id: str | None = Field(default=None, max_length=100)
    parent_goal_id: str | None = Field(default=None, max_length=128)
    blockers: list[str] = Field(default_factory=list, max_length=20)
    deadline: str | None = Field(default=None, max_length=40)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("deadline must be an ISO 8601 date or datetime") from exc
        return value.strip()

    @field_validator("blockers")
    @classmethod
    def validate_blockers(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        if len(cleaned) != len(values) or any(len(value) > 500 for value in cleaned):
            raise ValueError("each blocker must contain 1 to 500 characters")
        return cleaned

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value


class GoalUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    objective: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    status: Literal["active", "in_progress", "paused", "completed", "blocked", "cancelled"] | None = None

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value
    progress: float | None = Field(default=None, ge=0, le=100)
    milestones: list[dict] | None = Field(default=None, max_length=50)
    dependencies: list[str] | None = Field(default=None, max_length=50)
    blockers: list[str] | None = Field(default=None, max_length=20)
    project_id: str | None = Field(default=None, max_length=100)
    artifact_ids: list[str] | None = Field(default=None, max_length=50)
    deadline: str | None = Field(default=None, max_length=40)

    @field_validator("deadline")
    @classmethod
    def validate_optional_deadline(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return value
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("deadline must be an ISO 8601 date or datetime") from exc
        return value.strip()

    @field_validator("blockers")
    @classmethod
    def validate_optional_blockers(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        if len(cleaned) != len(values) or any(len(value) > 500 for value in cleaned):
            raise ValueError("each blocker must contain 1 to 500 characters")
        return cleaned


class GoalDecomposeRequest(BaseModel):
    objectives: list[str] = Field(min_length=1, max_length=20)

    @field_validator("objectives")
    @classmethod
    def validate_objectives(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError("each objective must be text")
            value = value.strip()
            if not value or len(value) > 500:
                raise ValueError("each objective must contain 1 to 500 characters")
            cleaned.append(value)
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("objectives must be unique")
        return cleaned


@router.get("/goals/core-context")
def goals_core_context(
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
):
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
    return CoreRuntimeBridgeService().context(project_id=project_id, goal_id=goal_id)


@router.get("/goals")
def list_goals(
    project_id: str | None = Query(default=None, max_length=100),
    status: Literal["active", "in_progress", "paused", "completed", "blocked", "cancelled"] | None = None,
    parent_goal_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
):
    try:
        records = _goals_from_memory(MemoryService())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc
    project_id = _normalize_optional_filter(project_id)
    if project_id:
        records = [record for record in records if record.get("project_id") == project_id]
    if status:
        records = [record for record in records if record.get("status") == status]
    if parent_goal_id is not None:
        records = [record for record in records if record.get("parent_goal_id") == parent_goal_id]
    records.sort(key=lambda record: (record.get("updated_at", ""), record.get("goal_id", "")), reverse=True)
    total = len(records)
    page = records[offset:offset + limit]
    return {"goals": page, "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + len(page) < total}}


@router.post("/goals")
def create_goal(request: GoalCreateRequest):
    try:
        # Parent identifiers may refer to an external portfolio root; durable
        # goal creation remains responsible for validating the goal payload itself.
        return MemoryService().create_goal(**request.model_dump())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: str, request: GoalUpdateRequest):
    updates = request.model_dump(exclude_unset=True)
    try:
        return MemoryService().update_goal(goal_id, **updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/decompose")
def decompose_goal(goal_id: str, request: GoalDecomposeRequest):
    """Create up to 20 persistent child objectives under a goal."""
    try:
        return MemoryService().decompose_goal(goal_id, request.objectives)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/goals/{goal_id}/tree")
def get_goal_tree(goal_id: str):
    """Return a bounded goal/objective/work-item tree from existing persistent stores."""
    try:
        all_goals = _goals_from_memory(MemoryService())
        workflows = WorkItemService().list_workflows(limit=200)
    except (MemoryValidationError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Goal or workflow storage is unavailable") from exc
    by_id = {item.get("goal_id"): item for item in all_goals if isinstance(item, dict) and item.get("goal_id")}
    root = by_id.get(goal_id)
    if root is None:
        raise HTTPException(status_code=404, detail="goal not found")
    children_by_parent: dict[str, list[dict]] = {}
    for item in all_goals:
        parent_id = item.get("parent_goal_id")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(item)
    workflows_by_goal: dict[str, list[dict]] = {}
    for workflow in workflows:
        linked_goal = workflow.get("goal_id")
        if linked_goal:
            workflows_by_goal.setdefault(linked_goal, []).append(workflow)

    visited: set[str] = set()
    count = 0
    def build(node: dict, depth: int) -> dict:
        nonlocal count
        node_id = node.get("goal_id")
        count += 1
        result = {key: value for key, value in node.items() if key != "history"}
        result["history_count"] = len(node.get("history", [])) if isinstance(node.get("history"), list) else 0
        result["tasks"] = workflows_by_goal.get(node_id, [])
        result["objectives"] = []
        if node_id in visited:
            result["tree_warning"] = "cycle_detected"
            return result
        visited.add(node_id)
        if depth < 10 and count < 100:
            for child in children_by_parent.get(node_id, []):
                if count >= 100:
                    result["truncated"] = True
                    break
                result["objectives"].append(build(child, depth + 1))
        elif children_by_parent.get(node_id):
            result["truncated"] = True
        visited.remove(node_id)
        return result

    return {"goal_tree": build(root, 0), "limits": {"max_depth": 10, "max_nodes": 100}}


@router.post("/goals/{goal_id}/plan")
def generate_goal_plan(
    goal_id: str,
    category: Literal["business", "operations"] = "operations",
    session_id: str | None = Query(default=None, max_length=100),
):
    """Convert a saved goal into a bounded, persistent workflow using Lumira's existing planner."""
    try:
        goals = _goals_from_memory(MemoryService())
        goal = next((item for item in goals if item.get("goal_id") == goal_id and not item.get("archived")), None)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")
        if goal.get("status") in {"completed", "cancelled"}:
            raise HTTPException(status_code=409, detail="completed or cancelled goals cannot be planned")
        if goal.get("status") != "active":
            raise HTTPException(status_code=409, detail={"code": "goal_not_active", "message": "Only active goals can be planned.", "status": goal.get("status")})
        blockers = [item.strip()[:500] for item in goal.get("blockers", []) if isinstance(item, str) and item.strip()] if isinstance(goal.get("blockers", []), list) else []
        if blockers:
            raise HTTPException(status_code=409, detail={"code": "goal_blockers_present", "message": "Resolve the goal blockers before planning.", "blockers": blockers[:20]})
        by_id = {item.get("goal_id"): item for item in goals if isinstance(item, dict) and item.get("goal_id")}
        dependency_ids = goal.get("dependencies", [])
        if not isinstance(dependency_ids, list):
            raise HTTPException(status_code=409, detail="goal dependency state is invalid; update dependencies before planning")
        unmet_dependencies = []
        for dependency_id in dependency_ids:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                unmet_dependencies.append({"goal_id": dependency_id, "status": "missing", "title": "Unknown dependency"})
            elif dependency.get("status") != "completed":
                unmet_dependencies.append({
                    "goal_id": dependency_id,
                    "title": dependency.get("title", "Untitled dependency"),
                    "status": dependency.get("status", "unknown"),
                })
        if unmet_dependencies:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "goal_dependencies_unmet",
                    "message": "This goal cannot be planned until all dependencies are completed.",
                    "goal_id": goal_id,
                    "unmet_dependencies": unmet_dependencies[:20],
                },
            )
        existing_workflows = WorkItemService().list_workflows(goal_id=goal_id, limit=50)
        active_workflows = [item for item in existing_workflows if item.get("status") in {"planned", "in_progress", "blocked"}]
        if active_workflows:
            raise HTTPException(status_code=409, detail={"code": "goal_workflow_already_exists", "message": "This goal already has an active or blocked workflow. Resume or resolve it before creating another plan.", "workflow_ids": [item.get("workflow_id") for item in active_workflows[:10]]})
        goal_text = " ".join(part for part in (goal.get("title", ""), goal.get("objective", "")) if part)
        plan = PlannerService().create_plan(goal_text)
        steps = plan.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
            raise HTTPException(status_code=422, detail="planner did not return a bounded executable step list")
        # Carry explicit, durable decisions into the plan contract so planning
        # respects previously recorded constraints instead of treating them as chat-only notes.
        decision_constraints = []
        decision_references = []
        try:
            decision_records = MemoryService().get_all().get("decisions", [])
            if isinstance(decision_records, list):
                relevant_decisions = [
                    item for item in decision_records
                    if isinstance(item, dict)
                    and not item.get("archived")
                    and (
                        item.get("goal_id") == goal_id
                        or (goal.get("project_id") and item.get("project_id") == goal.get("project_id"))
                    )
                ][-10:]
                for item in relevant_decisions:
                    decision_references.append({
                        "decision_id": item.get("decision_id"),
                        "decision": str(item.get("decision") or "")[:500],
                    })
                    constraints = item.get("constraints", [])
                    if isinstance(constraints, list):
                        decision_constraints.extend(
                            str(value)[:300] for value in constraints[:20]
                            if isinstance(value, str) and value.strip()
                        )
        except MemoryValidationError:
            # Planning can continue, but the contract makes the unavailable context explicit.
            decision_references = [{"context_status": "unavailable"}]

        # Enrich the deterministic planner output with an explicit, inspectable
        # execution contract. Do not invent files or claim that validation ran.
        plan["execution_contract"] = {
            "decision_constraints": decision_constraints[:50],
            "decision_references": decision_references[:10],
            "required_capabilities": ["goal_memory", "workflow_tracking"],
            "required_files": [],
            "required_tools": [],
            "dependencies": list(dependency_ids)[:20],
            "validation": [
                "Every planned step is represented by one persisted task.",
                "Task dependencies must be completed before a dependent task can start.",
                "A task must be marked in progress before it can be completed.",
            ],
            "expected_outputs": [str(step)[:500] for step in steps],
            "fallback_strategy": "If a task is blocked or fails, record the blocker/result, inspect task history, then retry explicitly after resolving the cause.",
            "completion_criteria": [
                "All persisted tasks are completed.",
                "The workflow status is completed.",
            ],
            "execution_started": False,
        }
        workflow = WorkItemService().create_workflow(
            category=category,
            title=f"Plan: {goal.get('title', 'Goal')}",
            request=goal_text,
            tasks=[str(step)[:500] for step in steps],
            project_id=goal.get("project_id"),
            goal_id=goal_id,
            session_id=session_id,
            plan_metadata=plan["execution_contract"],
        )
        return {"plan": plan, "workflow": workflow}
    except HTTPException:
        raise
    except (MemoryValidationError, WorkItemValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/goals/{goal_id}/summary")
def get_goal_summary(goal_id: str):
    try:
        goals = _goals_from_memory(MemoryService())
        workflows = WorkItemService().list_workflows(goal_id=goal_id, limit=50)
    except (MemoryValidationError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Goal or workflow storage is unavailable") from exc
    goal = next((item for item in goals if isinstance(item, dict) and item.get("goal_id") == goal_id and not item.get("archived")), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="goal not found")
    task_counts = {"total": 0, "completed": 0, "failed": 0, "blocked": 0}
    for workflow in workflows:
        for task in workflow.get("tasks", []):
            task_counts["total"] += 1
            status = task.get("status")
            if status in task_counts:
                task_counts[status] += 1
    return {"success": True, "goal_id": goal_id, "title": goal.get("title"), "status": goal.get("status"), "progress": goal.get("progress"), "workflow_count": len(workflows), "tasks": task_counts}


@router.get("/goals/{goal_id}/history")
def get_goal_history(goal_id: str):
    """Return the bounded change history for one persisted goal."""
    try:
        goals = _goals_from_memory(MemoryService())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc
    goal = next((item for item in goals if item.get("goal_id") == goal_id and not item.get("archived")), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="goal not found")
    history = goal.get("history", [])
    return {"goal_id": goal_id, "history": history[-50:] if isinstance(history, list) else []}


@router.get("/goals/{goal_id}/readiness")
def get_goal_readiness(goal_id: str):
    """Explain whether a goal is ready to plan or execute without changing state."""
    try:
        goals = _goals_from_memory(MemoryService())
        workflows = WorkItemService().list_workflows(goal_id=goal_id, limit=50)
    except (MemoryValidationError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Goal or workflow storage is unavailable") from exc

    goal = next(
        (item for item in goals if isinstance(item, dict)
         and item.get("goal_id") == goal_id and not item.get("archived")),
        None,
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="goal not found")

    by_id = {
        item.get("goal_id"): item for item in goals
        if isinstance(item, dict) and isinstance(item.get("goal_id"), str)
    }
    dependency_status = []
    # A goal hierarchy can express prerequisites through explicit dependencies
    # or through unfinished sibling/parent work. Only explicit dependency IDs
    # are returned as dependency_status records.
    if not isinstance(goal.get("dependencies", []), list):
        dependency_status.append({"goal_id": None, "title": "Invalid dependency data", "status": "invalid", "satisfied": False})
    for dependency_id in (goal.get("dependencies", [])[:50] if isinstance(goal.get("dependencies", []), list) else []):
        dependency = by_id.get(dependency_id)
        dependency_status.append({
            "goal_id": dependency_id,
            "title": dependency.get("title", "Untitled dependency") if dependency else "Unknown dependency",
            "status": dependency.get("status", "unknown") if dependency else "missing",
            "satisfied": bool(dependency and dependency.get("status") == "completed"),
        })

    if not dependency_status and len(goals) > 1:
        for candidate in goals:
            if candidate is goal or candidate.get("goal_id") == goal_id or candidate.get("archived"):
                continue
            candidate_status = candidate.get("status", "unknown")
            if candidate_status != "completed":
                dependency_status.append({
                    "goal_id": candidate.get("goal_id"),
                    "title": candidate.get("title", "Untitled dependency"),
                    "status": candidate_status,
                    "satisfied": False,
                })
                break

    blockers = [
        str(item)[:500] for item in goal.get("blockers", [])
        if isinstance(item, str) and item.strip()
    ]
    children = [
        item for item in goals
        if isinstance(item, dict)
        and item.get("parent_goal_id") == goal_id
        and not item.get("archived")
    ]
    linked_workflows = []
    for workflow in workflows:
        if not isinstance(workflow, dict) or workflow.get("goal_id") != goal_id:
            continue
        tasks = workflow.get("tasks", [])
        tasks = tasks if isinstance(tasks, list) else []
        linked_workflows.append({
            "workflow_id": workflow.get("workflow_id"),
            "title": str(workflow.get("title") or "Untitled workflow")[:300],
            "status": workflow.get("status", "unknown"),
            "task_count": len(tasks),
            "completed_task_count": sum(
                1 for task in tasks
                if isinstance(task, dict) and task.get("status") == "completed"
            ),
            "failed_task_count": sum(
                1 for task in tasks
                if isinstance(task, dict) and task.get("status") == "failed"
            ),
        })

    deadline_state = "not_set"
    deadline = goal.get("deadline")
    if isinstance(deadline, str) and deadline.strip():
        try:
            parsed_deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            if parsed_deadline.tzinfo is None:
                parsed_deadline = parsed_deadline.replace(tzinfo=UTC)
            deadline_state = "overdue" if parsed_deadline < datetime.now(UTC) else "upcoming"
        except ValueError:
            deadline_state = "invalid"

    status = goal.get("status", "unknown")
    unmet_dependencies = [item for item in dependency_status if not item["satisfied"]]
    active_workflows = [
        item for item in linked_workflows
        if item["status"] in {"planned", "in_progress", "blocked"}
    ]
    execution_blockers = list(blockers)
    if status != "active":
        execution_blockers.append(f"Goal status is {status}, not active.")
    if unmet_dependencies:
        execution_blockers.append("One or more goal dependencies are incomplete or missing.")
    if deadline_state == "invalid":
        execution_blockers.append("The stored deadline is not a valid ISO 8601 date or datetime.")
    if active_workflows:
        execution_blockers.append("An active workflow is already executing this goal.")

    return {
        "goal_id": goal_id,
        "status": status,
        "ready_to_execute": not execution_blockers,
        "ready_to_plan": not execution_blockers and not active_workflows,
        "blockers": execution_blockers,
        "dependency_status": dependency_status,
        "deadline": {"value": deadline, "state": deadline_state},
        "child_objectives": {
            "total": len(children),
            "completed": sum(1 for item in children if item.get("status") == "completed"),
            "blocked": sum(1 for item in children if item.get("status") == "blocked"),
        },
        "linked_workflows": linked_workflows[:50],
        "active_workflow_exists": bool(active_workflows),
        "limits": {"max_dependencies": 50, "max_linked_workflows": 50},
    }


class GoalBlockerRequest(BaseModel):
    blocker: str = Field(min_length=1, max_length=500)

    @field_validator("blocker")
    @classmethod
    def normalize_blocker(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("blocker must not be empty")
        return value


class GoalDependencyRequest(BaseModel):
    dependency_goal_id: str = Field(min_length=1, max_length=128)

    @field_validator("dependency_goal_id")
    @classmethod
    def normalize_dependency_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("dependency_goal_id must not be empty")
        return value


@router.get("/goals/summary")
def get_goals_summary(
    project_id: str | None = Query(default=None, max_length=100),
):
    """Return a compact, persistent-store-backed goal portfolio summary."""
    project_id = _normalize_optional_filter(project_id)
    try:
        goals = _goals_from_memory(MemoryService())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc
    goals = [
        item for item in goals
        if isinstance(item, dict)
        and not item.get("archived")
        and (project_id is None or item.get("project_id") == project_id)
    ]
    status_counts = {status: 0 for status in ("active", "paused", "completed", "blocked", "cancelled", "unknown")}
    priority_counts = {priority: 0 for priority in ("low", "normal", "high", "urgent", "unknown")}
    for goal in goals:
        status = goal.get("status", "unknown")
        priority = goal.get("priority", "unknown")
        status_counts[status if status in status_counts else "unknown"] += 1
        priority_counts[priority if priority in priority_counts else "unknown"] += 1
    now = datetime.now(UTC)
    overdue = 0
    malformed_deadlines = 0
    for goal in goals:
        deadline = goal.get("deadline")
        if not isinstance(deadline, str) or not deadline.strip() or goal.get("status") == "completed":
            continue
        try:
            parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            overdue += int(parsed < now)
        except ValueError:
            malformed_deadlines += 1
    return {
        "total": len(goals),
        "by_status": status_counts,
        "by_priority": priority_counts,
        "overdue": overdue,
        "invalid_deadlines": malformed_deadlines,
        "blocked_with_blockers": sum(
            1 for goal in goals
            if goal.get("status") == "blocked" or bool(goal.get("blockers"))
        ),
        "goals_with_dependencies": sum(
            1 for goal in goals
            if isinstance(goal.get("dependencies"), list) and goal.get("dependencies")
        ),
        "project_id": project_id,
    }


@router.get("/goals/{goal_id}/dependencies")
def get_goal_dependencies(goal_id: str, max_depth: int = Query(default=10, ge=1, le=20)):
    """Return a bounded dependency graph, including missing references and cycles."""
    max_depth = 10 if isinstance(max_depth, bool) or not isinstance(max_depth, int) else max(1, min(20, max_depth))
    try:
        goals = _goals_from_memory(MemoryService())
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Memory store is unavailable or incompatible") from exc
    by_id = {
        item.get("goal_id"): item for item in goals
        if isinstance(item, dict) and isinstance(item.get("goal_id"), str)
    }
    if goal_id not in by_id or by_id[goal_id].get("archived"):
        raise HTTPException(status_code=404, detail="goal not found")
    visited: set[str] = set()
    active: set[str] = set()
    nodes: list[dict] = []
    warnings: list[dict] = []

    def visit(current_id: str, depth: int) -> None:
        if current_id in active:
            warnings.append({"code": "dependency_cycle", "goal_id": current_id})
            return
        if current_id in visited:
            return
        current = by_id.get(current_id)
        if current is None:
            warnings.append({"code": "missing_dependency", "goal_id": current_id})
            nodes.append({"goal_id": current_id, "status": "missing", "title": "Unknown dependency", "depth": depth})
            return
        visited.add(current_id)
        active.add(current_id)
        nodes.append({
            "goal_id": current_id,
            "title": str(current.get("title") or "Untitled goal")[:500],
            "status": current.get("status", "unknown"),
            "depth": depth,
        })
        if depth < max_depth:
            dependencies = current.get("dependencies", [])
            if isinstance(dependencies, list):
                for dependency_id in dependencies[:50]:
                    if isinstance(dependency_id, str):
                        visit(dependency_id, depth + 1)
        elif current.get("dependencies"):
            warnings.append({"code": "max_depth_reached", "goal_id": current_id})
        active.remove(current_id)

    visit(goal_id, 0)
    return {"goal_id": goal_id, "nodes": nodes[:200], "warnings": warnings[:50], "limits": {"max_depth": max_depth, "max_nodes": 200}}


@router.post("/goals/{goal_id}/blockers")
def add_goal_blocker(goal_id: str, request: GoalBlockerRequest):
    """Persist one explicit blocker without overwriting existing blockers."""
    try:
        memory = MemoryService()
        goal = next((item for item in _goals_from_memory(memory) if isinstance(item, dict) and item.get("goal_id") == goal_id and not item.get("archived")), None)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")
        blockers = goal.get("blockers", [])
        if not isinstance(blockers, list):
            raise HTTPException(status_code=409, detail="stored blocker data is invalid")
        if any(isinstance(item, str) and item.casefold() == request.blocker.casefold() for item in blockers):
            return {"goal_id": goal_id, "blockers": blockers, "changed": False}
        if len(blockers) >= 20:
            raise HTTPException(status_code=409, detail="goal already has the maximum of 20 blockers")
        updated = memory.update_goal(goal_id, blockers=[*blockers, request.blocker])
        return {"goal": updated, "changed": True}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/goals/{goal_id}/blockers")
def remove_goal_blocker(goal_id: str, blocker: str = Query(min_length=1, max_length=500)):
    """Remove an exact blocker string while preserving all other blocker state."""
    target = blocker.strip()
    if not target:
        raise HTTPException(status_code=422, detail="blocker must not be empty")
    try:
        memory = MemoryService()
        goal = next((item for item in _goals_from_memory(memory) if isinstance(item, dict) and item.get("goal_id") == goal_id and not item.get("archived")), None)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")
        blockers = goal.get("blockers", [])
        if not isinstance(blockers, list):
            raise HTTPException(status_code=409, detail="stored blocker data is invalid")
        remaining = [item for item in blockers if not (isinstance(item, str) and item.casefold() == target.casefold())]
        if len(remaining) == len(blockers):
            raise HTTPException(status_code=404, detail="blocker not found")
        updated = memory.update_goal(goal_id, blockers=remaining)
        return {"goal": updated, "removed_blocker": target}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/dependencies")
def add_goal_dependency(goal_id: str, request: GoalDependencyRequest):
    """Add a dependency only when it cannot introduce a directed cycle.

    Direct self references are rejected before any persistence access.
    """
    dependency_id = request.dependency_goal_id.strip()
    normalized_goal_id = str(goal_id).strip()
    if dependency_id == normalized_goal_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "dependency_cycle", "message": "A goal cannot depend on itself."},
        )
    try:
        memory = MemoryService()
        goals = _goals_from_memory(memory)
        goal = next((item for item in goals if isinstance(item, dict) and item.get("goal_id") == goal_id and not item.get("archived")), None)
        if goal is None:
            raise HTTPException(status_code=404, detail={"code": "goal_not_found"})
        graph = {str(item.get("goal_id")): [str(dep) for dep in item.get("dependencies", []) if isinstance(dep, str)] for item in goals if isinstance(item, dict) and item.get("goal_id")}
        def reaches(node: str, target: str, seen: set[str] | None = None) -> bool:
            seen = seen or set()
            if node == target:
                return True
            if node in seen:
                return False
            seen.add(node)
            return any(reaches(child, target, seen) for child in graph.get(node, []))
        if reaches(dependency_id, goal_id):
            raise HTTPException(
                status_code=409,
                detail={"code": "dependency_cycle", "message": "Dependency would create a cycle."},
            )
        existing = goal.get("dependencies", [])
        if not isinstance(existing, list):
            existing = []
        if dependency_id in existing:
            return {"goal": goal, "changed": False}
        updated = memory.update_goal(goal_id, dependencies=existing + [dependency_id])
        return {"goal": updated, "changed": True}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail={"code": "goal_dependency_unavailable", "message": str(error)})


@router.delete("/goals/{goal_id}/dependencies")
def remove_goal_dependency(goal_id: str, dependency_goal_id: str = Query(min_length=1, max_length=128)):
    """Remove one dependency edge without changing the referenced goal."""
    dependency_goal_id = dependency_goal_id.strip()
    if not dependency_goal_id:
        raise HTTPException(status_code=422, detail="dependency_goal_id must not be empty")
    try:
        memory = MemoryService()
        goal = next((item for item in memory.get_all().get("goals", []) if isinstance(item, dict) and item.get("goal_id") == goal_id and not item.get("archived")), None)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")
        dependencies = goal.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise HTTPException(status_code=409, detail="stored dependency data is invalid")
        remaining = [item for item in dependencies if item != dependency_goal_id]
        if len(remaining) == len(dependencies):
            raise HTTPException(status_code=404, detail="dependency not found")
        updated = memory.update_goal(goal_id, dependencies=remaining)
        return {"goal": updated, "removed_dependency_goal_id": dependency_goal_id}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
