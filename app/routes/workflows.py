import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.agents.agent_manager import AgentManager
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.work_items.work_item_service import WorkItemService, WorkItemValidationError, PersistenceIntegrityError

router = APIRouter()


class TaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(min_length=1, max_length=20)
    blocker: str | None = Field(default=None, max_length=1000)
    result: str | None = Field(default=None, max_length=4000)


class WorkflowCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(pattern="^(business|operations)$")
    title: str = Field(min_length=1, max_length=200)
    request: str = Field(min_length=1, max_length=10000)
    tasks: list[str] = Field(min_length=1, max_length=20)
    session_id: str | None = Field(default=None, max_length=100)
    project_id: str | None = Field(default=None, max_length=100)
    goal_id: str | None = Field(default=None, max_length=128)


@router.post("/workflows")
def create_workflow(request: WorkflowCreateRequest):
    try:
        return WorkItemService().create_workflow(
            category=request.category,
            title=request.title,
            request=request.request,
            tasks=request.tasks,
            session_id=request.session_id,
            project_id=request.project_id,
            goal_id=request.goal_id,
        )
    except WorkItemValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/workflows")
def list_workflows(
    category: str | None = Query(default=None, pattern="^(business|operations)$"),
    session_id: str | None = Query(default=None, max_length=100),
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
    status: str | None = Query(default=None, pattern="^(planned|in_progress|blocked|completed|failed)$"),
    limit: int = Query(default=50, ge=0, le=200),
):
    return {"workflows": WorkItemService().list_workflows(
        category=category, session_id=session_id, project_id=project_id,
        goal_id=goal_id, status=status, limit=limit
    )}


@router.get("/workflows/core-context")
def workflows_core_context(
    session_id: str | None = Query(default=None, max_length=100),
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
):
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
    return CoreRuntimeBridgeService().context(session_id, project_id, goal_id)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    workflow = WorkItemService().get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@router.get("/workflows/{workflow_id}/progress")
def get_workflow_progress(workflow_id: str):
    try:
        return WorkItemService().get_workflow_progress(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except WorkItemValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/workflows/{workflow_id}/tasks/{task_id}/history")
def get_task_history(workflow_id: str, task_id: str):
    try:
        return WorkItemService().get_task_history(workflow_id, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except WorkItemValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/workflows/{workflow_id}/tasks/{task_id}/result")
def get_workflow_task_result(workflow_id: str, task_id: str):
    """Retrieve a task's persisted agent outcome and linked artifact metadata."""
    service = WorkItemService()
    try:
        workflow = service.get_workflow(workflow_id)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    task = next((item for item in workflow.get("tasks", []) if item.get("task_id") == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    raw_result = task.get("result")
    parsed_result = None
    if raw_result:
        try:
            parsed_result = json.loads(raw_result)
        except (TypeError, json.JSONDecodeError):
            parsed_result = {"text": str(raw_result)}
    artifact_id = parsed_result.get("artifact_id") if isinstance(parsed_result, dict) else None
    artifact = None
    if artifact_id:
        try:
            record = ArtifactManagerService().get_artifact(artifact_id)
            if record:
                artifact = {key: value for key, value in record.items() if key != "file"}
                artifact["content_available"] = ArtifactManagerService().get_artifact_path(artifact_id) is not None
        except (ValueError, OSError):
            artifact = {"artifact_id": artifact_id, "content_available": False}
    return {
        "workflow_id": workflow_id,
        "task_id": task_id,
        "title": task.get("title"),
        "status": task.get("status"),
        "blocker": task.get("blocker"),
        "result": parsed_result,
        "artifact": artifact,
        "has_result": raw_result is not None and raw_result != "",
    }


@router.get("/workflows/{workflow_id}/deliverables")
def list_workflow_deliverables(workflow_id: str, include_archived: bool = False):
    """List stored artifacts produced by tasks in one workflow, without leaking local paths."""
    service = WorkItemService()
    try:
        workflow = service.get_workflow(workflow_id)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    prefix = f"workflow:{workflow_id}:task:"
    try:
        records = ArtifactManagerService().get_all_artifacts()
    except (ValueError, OSError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Artifact index is unavailable or invalid") from exc
    task_lookup = {item.get("task_id"): item for item in workflow.get("tasks", [])}
    deliverables = []
    for record in records:
        source = record.get("source", "")
        if not isinstance(source, str) or not source.startswith(prefix):
            continue
        if record.get("archived", False) and not include_archived:
            continue
        task_id = source[len(prefix):]
        item = {key: value for key, value in record.items() if key != "file"}
        item["task_id"] = task_id
        item["task_title"] = task_lookup.get(task_id, {}).get("title")
        try:
            item["content_available"] = ArtifactManagerService().get_artifact_path(record.get("artifact_id")) is not None
        except (ValueError, OSError):
            item["content_available"] = False
        deliverables.append(item)
    deliverables.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"workflow_id": workflow_id, "count": len(deliverables), "deliverables": deliverables}


@router.patch("/workflows/{workflow_id}/tasks/{task_id}")
def update_task(workflow_id: str, task_id: str, request: TaskStatusUpdate):
    try:
        return WorkItemService().update_task(
            workflow_id, task_id, request.status, blocker=request.blocker, result=request.result
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except WorkItemValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



class WorkflowAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int = Field(default=1, ge=1, le=3)
    stop_on_failure: bool = True
    agent_mode: str = Field(default="auto", pattern="^(auto|planner_agent|research_agent|code_agent)$")


@router.post("/workflows/{workflow_id}/run-ready")
def run_ready_workflow_tasks(workflow_id: str, request: WorkflowAgentRunRequest):
    """Execute dependency-ready workflow tasks through bounded local agents, in order."""
    service = WorkItemService()
    try:
        workflow = service.get_workflow(workflow_id)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")

    outcomes = []
    executed_count = 0
    stop_reason = "task_limit_reached"
    manager = AgentManager(timeout_seconds=20.0)

    while executed_count < request.max_tasks:
        # Re-read durable state after every task so dependency checks use the
        # authoritative persisted statuses rather than a stale in-memory copy.
        try:
            workflow = service.get_workflow(workflow_id)
        except (WorkItemValidationError, PersistenceIntegrityError) as exc:
            raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        completed_ids = {
            item.get("task_id") for item in workflow.get("tasks", [])
            if isinstance(item, dict) and item.get("status") == "completed"
        }
        ready = next((
            item for item in workflow.get("tasks", [])
            if isinstance(item, dict)
            and item.get("status") == "pending"
            and set(item.get("dependencies", [] )).issubset(completed_ids)
        ), None)
        if ready is None:
            stop_reason = "no_dependency_ready_tasks"
            break

        task_id = ready.get("task_id")
        task_title = ready.get("title", "")
        try:
            service.update_task(workflow_id, task_id, "in_progress")
        except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
            raise HTTPException(status_code=409, detail="Task could not be started; workflow state may have changed") from exc

        agent_prompt = (
            "Execute the following single workflow step. Work only within the capabilities "
            "available to you; do not claim external actions, file changes, deployments, or "
            "messages were performed unless your tool actually performed them. Return a concise "
            "result, concrete deliverables, and any unresolved blockers.\n\n"
            f"Workflow: {workflow.get('title', '')}\n"
            f"Overall request: {workflow.get('request', '')}\n"
            f"Step: {task_title}\n"
            f"Project context: {workflow.get('project_id') or 'not specified'}"
        )
        try:
            outcome = manager.dispatch(agent_prompt) if request.agent_mode == "auto" else manager.run(request.agent_mode, agent_prompt)
        except Exception as exc:
            # Persist infrastructure failures instead of leaving tasks stuck in progress.
            outcome = {"success": False, "state": "failed", "code": "agent_dispatch_exception",
                       "message": f"Agent dispatch failed ({type(exc).__name__}); inspect the environment before retrying."}
        succeeded = isinstance(outcome, dict) and outcome.get("success") is True
        serialized = json.dumps(outcome, ensure_ascii=False, default=str)
        result_text = serialized[:3900]
        artifact_id = None
        artifact_storage = "failed"
        try:
            artifact = ArtifactManagerService().create_artifact(
                artifact_type="reports", content=result_text,
                source=f"workflow:{workflow_id}:task:{task_id}", extension="json",
            )
            artifact_id = artifact.get("artifact_id") if isinstance(artifact, dict) else None
            artifact_storage = "recorded" if artifact_id else "unknown"
        except Exception:
            # Task state remains authoritative; report artifact persistence separately.
            artifact_storage = "failed"
        task_result_text = json.dumps({"agent_outcome": outcome, "artifact_id": artifact_id, "artifact_storage": artifact_storage}, ensure_ascii=False, default=str)[:3900]
        if succeeded:
            try:
                service.update_task(workflow_id, task_id, "completed", result=task_result_text)
            except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
                # Keep the outcome visible even if durable completion fails.
                outcomes.append({"task_id": task_id, "title": task_title, "success": False,
                                 "state": "completion_persistence_failed", "error_type": type(exc).__name__})
                stop_reason = "completion_persistence_failed"
                break
            outcomes.append({"task_id": task_id, "title": task_title, "success": True,
                             "agent": outcome.get("agent"), "state": "completed",
                             "result": outcome.get("result"), "artifact_id": artifact_id, "artifact_storage": artifact_storage})
            executed_count += 1
        else:
            failure_reason = str(outcome.get("message") or outcome.get("code") or "agent_execution_failed")
            try:
                service.update_task(workflow_id, task_id, "failed", blocker=failure_reason[:900], result=task_result_text)
            except (KeyError, WorkItemValidationError, PersistenceIntegrityError):
                outcomes.append({"task_id": task_id, "title": task_title, "success": False,
                                 "state": "failure_persistence_failed"})
                stop_reason = "failure_persistence_failed"
                break
            outcomes.append({"task_id": task_id, "title": task_title, "success": False,
                             "agent_state": outcome.get("state"), "code": outcome.get("code"),
                             "message": failure_reason[:500], "artifact_id": artifact_id, "artifact_storage": artifact_storage})
            stop_reason = "agent_task_failed"
            if request.stop_on_failure:
                break
            executed_count += 1

    try:
        final_workflow = service.get_workflow(workflow_id)
        progress = service.get_workflow_progress(workflow_id)
    except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow progress could not be retrieved") from exc
    return {
        "success": bool(outcomes) and all(item.get("success") is True for item in outcomes),
        "workflow_id": workflow_id,
        "executed_count": len(outcomes),
        "requested_max_tasks": request.max_tasks,
        "stop_on_failure": request.stop_on_failure,
        "stop_reason": stop_reason,
        "outcomes": outcomes,
        "workflow": final_workflow,
        "progress": progress,
        "note": "Agent execution produces recorded task outcomes. It does not execute arbitrary generated code or guarantee external side effects."
    }



class WorkflowGoalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int = Field(default=3, ge=1, le=5)


@router.get("/workflows/{workflow_id}/execution-preview")
def preview_workflow_execution(workflow_id: str):
    """Return a read-only execution plan without invoking agents or changing state."""
    service = WorkItemService()
    try:
        workflow = service.get_workflow(workflow_id)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        progress = service.get_workflow_progress(workflow_id)
    except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow progress is unavailable or invalid") from exc

    completed_ids = {
        task.get("task_id") for task in workflow.get("tasks", [])
        if task.get("status") == "completed"
    }
    tasks = []
    for task in workflow.get("tasks", [])[:20]:
        dependencies = task.get("dependencies", [])
        unmet = [dependency for dependency in dependencies if dependency not in completed_ids]
        status = task.get("status", "unknown")
        tasks.append({
            "task_id": task.get("task_id"),
            "title": task.get("title"),
            "status": status,
            "dependencies": dependencies[:20],
            "unmet_dependencies": unmet[:20],
            "ready": status == "pending" and not unmet,
            "retry_required": status == "failed",
            "blocker": task.get("blocker"),
            "has_recorded_result": bool(task.get("result")),
        })
    ready = [task for task in tasks if task["ready"]]
    return {
        "workflow_id": workflow_id,
        "title": workflow.get("title"),
        "workflow_status": workflow.get("status"),
        "mode": "preview_only",
        "agent_calls": 0,
        "state_changed": False,
        "ready_count": len(ready),
        "tasks": tasks,
        "progress": progress.get("progress", {}),
        "can_start": bool(ready),
        "blocked_by_failures": any(
            task.get("status") == "pending" and any(
                next((candidate.get("status") for candidate in workflow.get("tasks", [])
                      if candidate.get("task_id") == dependency), None) == "failed"
                for dependency in task.get("dependencies", [])
            ) for task in workflow.get("tasks", [])
        ),
    }


@router.get("/goals/{goal_id}/deliverables")
def list_goal_deliverables(goal_id: str, include_archived: bool = False):
    """Aggregate durable task artifacts across every workflow linked to a goal."""
    service = WorkItemService()
    try:
        workflows = service.list_workflows(goal_id=goal_id, limit=50)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Goal workflow data is unavailable or invalid") from exc
    workflow_lookup = {}
    task_lookup = {}
    for workflow in workflows:
        workflow_id = workflow.get("workflow_id")
        if not workflow_id:
            continue
        workflow_lookup[workflow_id] = workflow.get("title")
        for task in workflow.get("tasks", []):
            task_lookup[(workflow_id, task.get("task_id"))] = task.get("title")
    try:
        records = ArtifactManagerService().get_all_artifacts()
    except (ValueError, OSError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Artifact index is unavailable or invalid") from exc
    deliverables = []
    for record in records:
        source = record.get("source", "")
        if not isinstance(source, str) or not source.startswith("workflow:"):
            continue
        parts = source.split(":", 3)
        if len(parts) != 4 or parts[0] != "workflow" or parts[1] not in workflow_lookup or parts[2] != "task":
            continue
        if record.get("archived", False) and not include_archived:
            continue
        workflow_id, task_id = parts[1], parts[3]
        item = {key: value for key, value in record.items() if key != "file"}
        item["workflow_id"] = workflow_id
        item["workflow_title"] = workflow_lookup[workflow_id]
        item["task_id"] = task_id
        item["task_title"] = task_lookup.get((workflow_id, task_id))
        try:
            path = ArtifactManagerService().get_artifact_path(record.get("artifact_id"))
            item["content_available"] = path is not None and callable(getattr(path, "is_file", None)) and path.is_file()
        except (ValueError, OSError):
            item["content_available"] = False
        deliverables.append(item)
    deliverables.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {
        "goal_id": goal_id,
        "workflows_scanned": len(workflow_lookup),
        "count": len(deliverables),
        "deliverables": deliverables[:200],
    }


@router.post("/goals/{goal_id}/run-ready")
def run_goal_ready_workflows(goal_id: str, request: WorkflowGoalRunRequest):
    """Run dependency-ready tasks across a goal's linked workflows under one task budget."""
    service = WorkItemService()
    try:
        workflows = service.list_workflows(goal_id=goal_id, limit=50)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Goal workflow data is unavailable or invalid") from exc
    if not workflows:
        raise HTTPException(status_code=404, detail="No workflows are linked to this goal")

    outcomes = []
    remaining = request.max_tasks
    skipped_no_ready_tasks = 0
    stop_reason = "no_dependency_ready_tasks"
    for workflow in workflows:
        if remaining <= 0:
            break
        if workflow.get("status") not in {"planned", "in_progress", "blocked"}:
            continue
        result = run_ready_workflow_tasks(
            workflow.get("workflow_id"),
            WorkflowAgentRunRequest(max_tasks=min(3, remaining), stop_on_failure=True),
        )
        task_outcomes = result.get("outcomes", []) if isinstance(result, dict) else []
        if result.get("stop_reason") == "no_dependency_ready_tasks" and not task_outcomes:
            skipped_no_ready_tasks += 1
            continue
        outcomes.append({
            "workflow_id": workflow.get("workflow_id"),
            "title": workflow.get("title"),
            "success": result.get("success") is True,
            "stop_reason": result.get("stop_reason"),
            "outcomes": task_outcomes,
        })
        remaining -= len(task_outcomes)
        if result.get("stop_reason") in {
            "agent_task_failed", "completion_persistence_failed", "failure_persistence_failed"
        }:
            stop_reason = result.get("stop_reason")
            break
    if remaining <= 0:
        stop_reason = "task_limit_reached"
    elif outcomes and stop_reason == "no_dependency_ready_tasks":
        stop_reason = "no_more_ready_tasks"
    return {
        "success": bool(outcomes) and all(item["success"] for item in outcomes),
        "goal_id": goal_id,
        "task_budget": request.max_tasks,
        "task_outcomes_count": sum(len(item["outcomes"]) for item in outcomes),
        "workflows_considered": len(workflows),
        "workflows_run": len(outcomes),
        "skipped": skipped_no_ready_tasks,
        "stop_reason": stop_reason,
        "workflows": outcomes,
        "note": "Only persisted dependency-ready tasks are considered. Failed tasks require explicit retry; arbitrary project code is not executed.",
    }



class WorkflowRetryFailedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int = Field(default=20, ge=1, le=20)


@router.post("/workflows/{workflow_id}/retry-failed")
def reset_failed_workflow_tasks(workflow_id: str, request: WorkflowRetryFailedRequest):
    """Explicitly requeue failed tasks while preserving history and dependency gates."""
    service = WorkItemService()
    try:
        workflow = service.get_workflow(workflow_id)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")

    failed = [
        task for task in workflow.get("tasks", [])
        if isinstance(task, dict) and task.get("status") == "failed"
    ][:request.max_tasks]
    reset = []
    errors = []
    for task in failed:
        try:
            service.update_task(workflow_id, task.get("task_id"), "pending")
            reset.append({"task_id": task.get("task_id"), "title": task.get("title"), "status": "pending"})
        except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
            errors.append({"task_id": task.get("task_id"), "error_type": type(exc).__name__})
    try:
        updated = service.get_workflow(workflow_id)
        progress = service.get_workflow_progress(workflow_id)
    except (KeyError, WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Updated workflow state could not be retrieved") from exc
    return {
        "success": bool(reset) and not errors,
        "workflow_id": workflow_id,
        "reset_count": len(reset),
        "remaining_failed_count": sum(1 for task in updated.get("tasks", []) if task.get("status") == "failed"),
        "reset_tasks": reset,
        "errors": errors,
        "workflow": updated,
        "progress": progress,
        "note": "Requeued tasks remain subject to dependency checks; no agent was invoked by this endpoint.",
    }
