from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.autonomous_development.autonomous_development_service import (
    AutonomousDevelopmentService,
)
from app.services.autonomous_development.worker.change_applier import (
    ChangeApplier,
    ChangeValidationError,
    FileChange,
)
from app.services.autonomous_development.worker.development_provider import (
    DevelopmentProvider,
)
from app.services.autonomous_development.worker.development_code_generator import (
    DevelopmentCodeGenerator,
)
from app.services.autonomous_development.worker.development_provider_registry import (
    DevelopmentProviderRegistry,
)
from app.services.autonomous_development.worker.development_worker import (
    DevelopmentWorker,
)
from app.services.autonomous_development.worker.openai_compatible_provider import (
    OpenAICompatibleDevelopmentProvider,
)
from app.services.autonomous_development.worker.development_planner import (
    DevelopmentPlanner,
)
from app.services.autonomous_development.worker.workspace_boundary import (
    WorkspaceBoundary,
    WorkspaceBoundaryError,
)
from app.services.work_items.work_item_service import WorkItemService
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.sessions.session_manager_service import SessionManagerService


@pytest.fixture(autouse=True)
def deterministic_resource_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # Provider contract tests exercise request/response behavior, not the
    # machine's transient RAM availability during a long repository suite.
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_profile": "low_memory",
            "resource_pressure": "normal",
            "max_concurrent_agents": 1,
            "max_concurrent_local_model_requests": 1,
            "max_provider_files": 6,
            "max_context_characters": 30000,
            "max_file_characters": 12000,
            "avoid_loading_multiple_local_models": True,
            "defer_optional_heavy_media_work": False,
        },
    )


def _service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    return_codes: list[int],
    *,
    apply_changes: bool = True,
) -> tuple[AutonomousDevelopmentService, list[dict]]:
    work_items = WorkItemService(tmp_path / "work_items.json")
    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=work_items,
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )
    service.development_loop.inspect_and_plan = lambda goal: {
        "success": True,
        "plan": {"steps": ["inspect", "plan", "implement", "test", "verify"]},
    }

    worker = service.development_loop.worker
    # Unit tests inject a fake command runner; production remains blocked without OS isolation.
    monkeypatch.setattr(worker, "_os_sandbox_is_verified", lambda: True)
    apply_worker_changes = worker.apply_changes
    generation_contexts: list[dict] = []

    def generate(*, goal: str, iteration: int, context: dict) -> dict:
        worker.begin_iteration(iteration)
        generation_contexts.append(context)
        if not apply_changes:
            return {"success": True, "changes": []}
        return {
            "success": True,
            "changes": [
                {
                    "path": f"generated_iteration_{iteration}.txt",
                    "old_content": None,
                    "new_content": f"Generated for iteration {iteration}\n",
                    "reason": "Apply the bounded test fixture change.",
                }
            ],
        }

    def apply(*, iteration: int, changes: list[dict]) -> dict:
        applied = apply_worker_changes(iteration=iteration, changes=changes)
        return applied

    worker.generate_changes = generate
    worker.apply_changes = apply
    validation_count = 0

    def run(command, **kwargs):
        nonlocal validation_count
        assert command == ["python", "-m", "pytest", "-q"]
        assert kwargs["shell"] is False
        return_code = return_codes[min(validation_count, len(return_codes) - 1)]
        validation_count += 1
        return subprocess.CompletedProcess(
            command,
            return_code,
            "validation failed" if return_code else "",
            "",
        )

    monkeypatch.setattr(subprocess, "run", run)
    return service, generation_contexts


def test_validation_is_blocked_without_verified_os_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = DevelopmentWorker(tmp_path)
    worker.begin_iteration(1)

    def forbidden_run(*args, **kwargs):
        pytest.fail("project-controlled validation command must not run without OS isolation")

    monkeypatch.setattr(subprocess, "run", forbidden_run)

    result = worker.run_validation(1)

    assert result.status == "blocked"
    assert result.return_code is None
    assert "OS-level sandboxing is not implemented" in result.output


def test_autonomous_development_requires_code_permission_before_creating_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService

    permissions = AutonomyPermissionService(tmp_path / "autonomy.json")
    service, _ = _service(tmp_path, monkeypatch, [0])
    service.autonomy = permissions

    result = service.execute("Add a bounded development test", autonomous=True)

    assert result["success"] is False
    assert result["code"] == "autonomous_permission_required"
    assert permissions.status()["recent_events"] == []
    assert service.work_items.list_workflows() == []


def test_authorized_autonomous_development_records_start_before_workflow_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService

    permissions = AutonomyPermissionService(tmp_path / "autonomy.json")
    permissions.set_permission("code.execute", True, "bounded test")
    service, _ = _service(tmp_path, monkeypatch, [0])
    service.autonomy = permissions
    monkeypatch.setattr(service, "_recover_stale_workflows", lambda: None)
    monkeypatch.setattr(service, "_is_continuation_request", lambda goal: True)
    monkeypatch.setattr(service, "_continue_development_program", lambda goal, session_id=None: {"success": True, "state": "completed"})

    result = service.execute("Continue the bounded development task", autonomous=True)

    assert result["success"] is True
    assert permissions.status()["recent_events"][-1]["state"] == "started"


def test_blocked_validation_stops_autonomous_loop_without_diagnosis_or_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, generation_contexts = _service(tmp_path, monkeypatch, [0, 0])
    worker = service.development_loop.worker
    monkeypatch.setattr(worker, "_os_sandbox_is_verified", lambda: False)

    def forbidden_run(*args, **kwargs):
        pytest.fail("project-controlled validation must not run without verified isolation")

    monkeypatch.setattr(subprocess, "run", forbidden_run)

    result = service.execute("Add a harmless operational test")

    workflow = service.work_items.get_workflow(result["workflow_id"])
    recovery = service.recovery.get_run(result["recovery_run_id"])
    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "os_sandbox_unverified"
    assert len(generation_contexts) == 1
    assert workflow["status"] == "blocked"
    assert workflow["tasks"][3]["status"] == "blocked"
    assert all(task["status"] != "pending" for task in workflow["tasks"])
    assert recovery["status"] == "blocked"
    assert recovery["resume_allowed"] is False


def test_write_file_limit_rejects_before_creating_extra_file(tmp_path: Path) -> None:
    worker = DevelopmentWorker(tmp_path)
    worker.begin_iteration(1)
    record = worker._get_iteration(1)
    record.files_changed = [
        f"existing_{index}.txt"
        for index in range(worker.MAX_FILES_PER_ITERATION)
    ]
    target = tmp_path / "limit_exceeded.txt"

    with pytest.raises(ValueError, match="Maximum changed files"):
        worker.write_file(
            "limit_exceeded.txt",
            "must not be written",
            iteration=1,
        )

    assert not target.exists()
    assert len(record.files_changed) == worker.MAX_FILES_PER_ITERATION


def test_write_file_limit_counts_utf8_bytes_not_characters(tmp_path: Path) -> None:
    worker = DevelopmentWorker(tmp_path)
    worker.begin_iteration(1)
    target = tmp_path / "oversized_unicode.txt"
    content = "界" * (worker.MAX_FILE_SIZE // 2)

    with pytest.raises(ValueError, match="maximum size"):
        worker.write_file(
            "oversized_unicode.txt",
            content,
            iteration=1,
        )

    assert not target.exists()


def test_first_pass_completes_optional_stages_as_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])

    result = service.execute("Add a harmless operational test")

    assert result["success"] is True
    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert workflow["status"] == "completed"
    assert all(task["status"] == "completed" for task in workflow["tasks"])
    assert '"skipped": true' in workflow["tasks"][4]["result"].lower()
    assert '"skipped": true' in workflow["tasks"][5]["result"].lower()
    assert result["verification"]["durable_workflow_completed"] is True


def test_failed_validation_runs_bounded_fix_and_revalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, contexts = _service(tmp_path, monkeypatch, [1, 0])

    result = service.execute("Add a harmless operational test")

    assert result["success"] is True
    assert result["iteration"] == 2
    assert len(contexts) == 2
    assert contexts[1]["diagnosis"]["stage"] == "diagnose"
    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert all(task["status"] == "completed" for task in workflow["tasks"])
    assert "skipped" not in workflow["tasks"][4]["result"].lower()


def test_generation_exception_persists_failure_and_blocks_remaining_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])

    def fail_generation(*, goal: str, iteration: int, context: dict) -> dict:
        service.development_loop.worker.begin_iteration(iteration)
        raise RuntimeError("provider unavailable api_key=provider-secret-value")

    service.development_loop.worker.generate_changes = fail_generation
    result = service.execute("Add a harmless operational test")

    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert result["state"] == "failed"
    assert "provider-secret-value" not in str(result)
    assert "[REDACTED]" in result["message"]
    assert workflow["status"] == "failed"
    assert workflow["tasks"][2]["status"] == "failed"
    assert "provider-secret-value" not in str(workflow)
    assert all(
        task["status"] in {"completed", "failed", "blocked"}
        for task in workflow["tasks"]
    )


def test_stale_workflows_fail_active_tasks_and_block_pending_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    stale = service.work_items.create_workflow(
        category="operations",
        title="Interrupted development",
        request="Recover this interrupted task",
        tasks=["Inspect workspace", "Implement change", "Run tests"],
    )
    service.work_items.update_task(
        stale["workflow_id"],
        stale["tasks"][0]["task_id"],
        "in_progress",
    )
    recent = service.work_items.create_workflow(
        category="operations",
        title="Recent development",
        request="Keep this active task",
        tasks=["Inspect workspace"],
    )
    service.work_items.update_task(
        recent["workflow_id"],
        recent["tasks"][0]["task_id"],
        "in_progress",
    )

    old_timestamp = "2026-09-29T14:27:08+00:00"

    def age_stale_record(document: dict) -> dict:
        record = next(
            item
            for item in document["workflows"]
            if item["workflow_id"] == stale["workflow_id"]
        )
        record["updated_at"] = old_timestamp
        record["tasks"][0]["updated_at"] = old_timestamp
        return document

    service.work_items.store.update(age_stale_record)

    recovered = service._recover_stale_workflows(
        now=datetime(2026, 10, 1, tzinfo=UTC)
    )

    stale_after = service.work_items.get_workflow(stale["workflow_id"])
    recent_after = service.work_items.get_workflow(recent["workflow_id"])
    assert recovered == 1
    assert stale_after["status"] == "failed"
    assert stale_after["tasks"][0]["status"] == "failed"
    assert all(task["status"] == "blocked" for task in stale_after["tasks"][1:])
    assert recent_after["status"] == "in_progress"
    assert recent_after["tasks"][0]["status"] == "in_progress"


def test_broad_planning_uses_bounded_evidence_derived_work_items() -> None:
    class Planner:
        def execute(self, task):
            return {
                "success": True,
                "steps": ["inspect", "plan", "implement", "test", "verify"],
            }

    plan = DevelopmentPlanner(Planner()).create_plan(
        "Complete all remaining Lumira development",
        {
            "file_count": 3,
            "files": [
                "app/agents/research_agent.py",
                "app/services/research/research_capability_service.py",
                "tests/test_agents.py",
            ],
            "audit_findings": [
                {
                    "path": "app/agents/research_agent.py",
                    "objective": "Connect research dispatch to the existing ResearchCapabilityService",
                    "acceptance": "Research dispatch uses the existing service.",
                }
            ],
        },
    )

    assert plan["success"] is True
    assert len(plan["work_items"]) == 1
    item = plan["work_items"][0]
    assert item["objective"].startswith("Connect research dispatch")
    assert item["relevant_files"] == ["app/agents/research_agent.py"]
    assert item["dependencies"] == []
    assert item["acceptance_criteria"]
    assert item["validation_command"] == ["python", "-m", "pytest", "-q"]
    assert item["bounded_scope"]["max_iterations"] <= 5
    assert item["status"] == "planned"


def test_audit_detects_disconnected_research_agent(tmp_path: Path) -> None:
    agent = tmp_path / "app/agents/research_agent.py"
    service = tmp_path / "app/services/research/research_capability_service.py"
    agent.parent.mkdir(parents=True)
    service.parent.mkdir(parents=True)
    agent.write_text(
        'return {"code": "provider_unavailable"}\n',
        encoding="utf-8",
    )
    service.write_text("class ResearchCapabilityService: pass\n", encoding="utf-8")

    findings = DevelopmentWorker(tmp_path)._audit_workspace(
        [
            "app/agents/research_agent.py",
            "app/services/research/research_capability_service.py",
        ]
    )

    assert len(findings) == 1
    assert findings[0]["path"] == "app/agents/research_agent.py"
    assert "ResearchCapabilityService" in findings[0]["objective"]


def test_audit_ignores_todo_string_literals_and_reports_comment_markers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "app/services/audit_target.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'MARKER = "TODO: this is data, not a task"\n'
        "# FIXME: handle the verified edge case\n",
        encoding="utf-8",
    )

    findings = DevelopmentWorker(tmp_path)._audit_workspace(
        ["app/services/audit_target.py"]
    )

    assert len(findings) == 1
    assert "FIXME" in findings[0]["objective"]
    assert "MARKER" not in findings[0]["evidence"]


def test_broad_goal_persists_bounded_child_workflows_and_stops_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    objectives = ["Resolve verified finding one", "Resolve verified finding two"]
    service.audit_service.run = lambda: {
        "file_count": 25,
        "findings": [
            {
                "path": f"app/{index}.py",
                "objective": objective,
                "acceptance": "Verify the change.",
            }
            for index, objective in enumerate(objectives)
        ],
    }
    real_execute = service.execute
    child_calls = []

    def fake_child(goal, *, session_id=None, **kwargs):
        child_calls.append(goal)
        if goal == objectives[1]:
            return {"success": False, "state": "failed", "code": "child_blocked"}
        return {
            "success": True,
            "state": "completed",
            "workflow_id": "child-1",
            "validation": {"status": "completed", "return_code": 0},
            "workflow": {"status": "completed"},
        }

    service.execute = fake_child
    result = real_execute("Complete all remaining Lumira development")

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["remaining_task_count"] == 0
    assert result["blocked_task_count"] == 1
    assert child_calls == objectives
    program = service.backlog.get_program(result["program_id"])
    assert program["tasks"][0]["status"] == "completed"
    assert program["tasks"][1]["status"] == "blocked"


def test_actionable_goal_with_no_changes_fails_durably(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, generation_contexts = _service(
        tmp_path,
        monkeypatch,
        [0],
        apply_changes=False,
    )

    result = service.execute("Add a pytest test for a new behavior")

    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert result["success"] is False
    assert result["result"]["code"] == "no_changes_generated"
    assert workflow["status"] == "failed"
    assert workflow["tasks"][2]["status"] == "failed"
    assert all(task["status"] != "pending" for task in workflow["tasks"])


def test_no_op_can_reuse_exact_prior_durable_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, generation_contexts = _service(
        tmp_path,
        monkeypatch,
        [0],
        apply_changes=False,
    )
    goal = "Add a pytest test for a new behavior"
    previous = service.work_items.create_workflow(
        category="operations",
        title="Prior development run",
        request=goal,
        tasks=["Implement the requested test", "Run validation"],
    )
    artifact_path = "tests/test_prior_goal_artifact.py"
    service.development_loop.worker.boundary.write_text(
        artifact_path,
        "def test_prior_goal_artifact():\n    assert True\n",
    )
    task = previous["tasks"][0]
    service.work_items.update_task(
        previous["workflow_id"],
        task["task_id"],
        "in_progress",
    )
    service.work_items.update_task(
        previous["workflow_id"],
        task["task_id"],
        "completed",
        result=json.dumps({"files_changed": [artifact_path]}),
    )
    validation_task = previous["tasks"][1]
    service.work_items.update_task(
        previous["workflow_id"],
        validation_task["task_id"],
        "in_progress",
    )
    service.work_items.update_task(
        previous["workflow_id"],
        validation_task["task_id"],
        "failed",
        blocker="Prior validation failed before the recovery run.",
    )
    assert service.work_items.get_workflow(previous["workflow_id"])["status"] == "failed"

    result = service.execute(goal)

    assert result["success"] is True, {
        key: result.get(key)
        for key in ("state", "code", "stage", "message", "result")
    }
    assert result["verification"]["prior_goal_changes_reused"] is True
    assert generation_contexts == []


def test_successful_autonomous_run_persists_recovery_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])

    result = service.execute("Add a harmless operational test")

    run = service.recovery.get_run(result["recovery_run_id"])
    assert run["status"] == "completed"
    assert run["last_completed_stage"] == "record"
    assert [stage["stage"] for stage in run["stage_records"]] == [
        "inspect",
        "plan",
        "generate_changes",
        "apply_changes",
        "validate",
        "diagnose",
        "fix",
        "verify",
        "record",
    ]


def _interrupted_validation_run(
    service: AutonomousDevelopmentService,
    tmp_path: Path,
) -> tuple[str, str]:
    workflow = service.work_items.create_workflow(
        category="operations",
        title="Recoverable development",
        request="Add a test after interrupted validation",
        tasks=[
            "Inspect workspace",
            "Plan changes",
            "Implement test",
            "Run validation",
            "Diagnose failures",
            "Apply fixes",
            "Re-run validation",
            "Verify changes",
            "Record result",
        ],
    )
    for task in workflow["tasks"][:3]:
        service.work_items.update_task(
            workflow["workflow_id"],
            task["task_id"],
            "in_progress",
        )
        service.work_items.update_task(
            workflow["workflow_id"],
            task["task_id"],
            "completed",
            result="{}",
        )
    changed_file = "resumed_test.py"
    (tmp_path / changed_file).write_text("assert True\n", encoding="utf-8")
    recovery_run = service.recovery.create_run(
        workflow["request"],
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": [
                "inspect",
                "plan",
                    "generate_changes",
                "apply_changes",
                "validate",
                "diagnose",
                "fix",
                "verify",
                "record",
            ],
        },
    )
    for stage, result in (
        ("inspect", {}),
        ("plan", {}),
        ("generate_changes", {"iteration": 1, "change_count": 1}),
        ("apply_changes", {"iteration": 1, "files_changed": [changed_file]}),
    ):
        service.recovery.update(recovery_run["run_id"], "start_stage", stage=stage)
        service.recovery.update(
            recovery_run["run_id"],
            "complete_stage",
            stage=stage,
            result=result,
        )
    service.recovery.update(
        recovery_run["run_id"],
        "start_stage",
        stage="validate",
    )
    return recovery_run["run_id"], workflow["workflow_id"]


def test_safe_resume_revalidates_without_repeating_completed_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    run_id, workflow_id = _interrupted_validation_run(service, tmp_path)
    calls = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: (
            calls.append(command)
            or subprocess.CompletedProcess(command, 0, "ok", "")
        ),
    )

    result = service.resume(run_id)

    assert result["success"] is True, result
    assert result["workflow_id"] == workflow_id
    assert calls == [["python", "-m", "pytest", "-q"]]
    run = service.recovery.get_run(run_id)
    assert run["status"] == "completed"
    assert [
        stage["stage"]
        for stage in run["stage_records"]
        if stage["status"] == "completed"
    ][:4] == ["inspect", "plan", "generate_changes", "apply_changes"]
    assert run["stage_records"][3]["attempts"] == 1


def test_uncertain_apply_is_blocked_and_never_replayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    workflow = service.work_items.create_workflow(
        category="operations",
        title="Interrupted apply",
        request="Add a test",
        tasks=["Implement test"],
    )
    run = service.recovery.create_run(
        "Add a test",
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["apply_changes", "validate"],
        },
    )
    service.recovery.update(run["run_id"], "start_stage", stage="apply_changes")
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: called.append(args))

    result = service.resume(run["run_id"])

    assert result["code"] == "manual_reconciliation_required"
    assert service.recovery.get_run(run["run_id"])["status"] == "blocked"
    assert called == []


def test_provider_timeout_checkpoint_has_safe_generation_retry_point(
    tmp_path: Path,
) -> None:
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run(
        "Add a focused test",
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": "workflow-timeout",
            "steps": ["inspect", "plan", "generate_changes", "apply_changes"],
        },
    )
    for stage in ("inspect", "plan"):
        recovery.update(run["run_id"], "start_stage", stage=stage)
        recovery.update(run["run_id"], "complete_stage", stage=stage, result={})
    recovery.update(run["run_id"], "start_stage", stage="generate_changes")
    recovery.update(
        run["run_id"],
        "fail_stage",
        stage="generate_changes",
        error="provider_timeout",
    )

    state = recovery.get_run(run["run_id"])

    assert state["status"] == "failed"
    assert state["current_stage"] == "generate_changes"
    assert state["safe_resume_point"] == "generate_changes"
    assert state["resume_allowed"] is True


def test_generation_failure_resumes_same_workflow_without_reinspection_or_replan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    worker = service.development_loop.worker
    calls = 0
    original_apply = worker.apply_changes
    content = "def test_resumed_provider_generation():\n    assert True\n"

    def generation(*, goal: str, iteration: int, context: dict) -> dict:
        nonlocal calls
        calls += 1
        worker.begin_iteration(iteration)
        if calls == 1:
            return {
                "success": False,
                "code": "provider_unreachable",
                "message": "Provider timeout.",
            }
        return {
            "success": True,
            "changes": [
                {
                    "path": "tests/test_resumed_provider_generation.py",
                    "old_content": None,
                    "new_content": content,
                    "reason": "Add a focused recovery test.",
                }
            ],
        }

    def apply(*, iteration: int, changes: list[dict]) -> dict:
        return original_apply(iteration=iteration, changes=changes)

    worker.generate_changes = generation
    worker.apply_changes = apply
    planning_calls = []
    inspect_and_plan = service.development_loop.inspect_and_plan

    def count_planning(goal: str) -> dict:
        planning_calls.append(goal)
        return inspect_and_plan(goal)

    service.development_loop.inspect_and_plan = count_planning
    first = service.execute("Add a regression test after provider recovery")
    run_id = first["recovery_run_id"]
    workflow_id = first["workflow_id"]
    run_before = service.recovery.get_run(run_id)
    assert first["success"] is False
    assert run_before["safe_resume_point"] == "generate_changes"
    assert run_before["stage_records"][0]["stage"] == "inspect"
    assert run_before["stage_records"][1]["stage"] == "plan"
    assert len(planning_calls) == 1

    resumed = service.resume(run_id)

    assert resumed["success"] is True
    assert resumed["workflow_id"] == workflow_id
    assert resumed["recovery_run_id"] == run_id
    assert resumed["resumed"] is True
    assert calls == 2
    assert len(planning_calls) == 1
    assert (tmp_path / "tests/test_resumed_provider_generation.py").is_file()
    assert service.recovery.get_run(run_id)["status"] == "completed"


def test_resume_rejects_completed_runs_and_enforces_resume_limit(
    tmp_path: Path,
) -> None:
    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )
    workflow = service.work_items.create_workflow(
        category="operations",
        title="Completed development",
        request="No changes needed",
        tasks=["Verify"],
    )
    completed = service.recovery.create_run(
        "No changes needed",
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["verify"],
        },
    )
    service.recovery.update(completed["run_id"], "start_stage", stage="verify")
    service.recovery.update(completed["run_id"], "complete_stage", stage="verify", result={})
    service.recovery.update(completed["run_id"], "complete_run", last_completed_stage="verify")
    assert service.resume(completed["run_id"])["code"] == "run_already_completed"

    limited = service.recovery.create_run(
        "Recover a validation",
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["validate"],
        },
    )
    for _ in range(service.recovery.MAX_RESUMES):
        service.recovery.update(limited["run_id"], "resume")
    assert service.resume(limited["run_id"])["code"] == "resume_limit_reached"


def test_autonomous_resume_rejects_closed_session(tmp_path: Path) -> None:
    previous_cwd = Path.cwd()
    import os

    os.chdir(tmp_path)
    try:
        sessions = SessionManagerService()
        session = sessions.create_session()
        sessions.close_session(session["session_id"])
        work_items = WorkItemService("work_items.json")
        workflow = work_items.create_workflow(
            category="operations",
            title="Closed-session development",
            request="Recover a closed session run",
            tasks=["Validate"],
            session_id=session["session_id"],
        )
        recovery = RunRecoveryService("workflow_runs.json")
        run = recovery.create_run(
            "Recover a closed session run",
            {
                "success": True,
                "autonomous_development": True,
                "workflow_id": workflow["workflow_id"],
                "steps": ["validate"],
            },
            session["session_id"],
        )
        service = AutonomousDevelopmentService(
            tmp_path,
            workflow_engine=object(),
            work_items=work_items,
            recovery=recovery,
        )

        result = service.resume(run["run_id"])
    finally:
        os.chdir(previous_cwd)

    assert result["success"] is False
    assert result["code"] == "session_closed"


def test_validation_retries_stop_at_worker_iteration_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, contexts = _service(tmp_path, monkeypatch, [1])

    result = service.execute("Add a harmless operational test")

    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert result["success"] is False
    assert len(contexts) == service.development_loop.worker.MAX_ITERATIONS
    assert workflow["status"] == "failed"
    assert workflow["tasks"][6]["status"] == "failed"
    assert all(task["status"] != "pending" for task in workflow["tasks"])


def test_change_applier_requires_exact_old_content_and_workspace_boundary(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.py"
    existing.write_text("original\n", encoding="utf-8")
    applier = ChangeApplier(WorkspaceBoundary(tmp_path))

    with pytest.raises(ChangeValidationError, match="old_content is required"):
        applier.validate([FileChange("existing.py", None, "replacement", "test")])

    with pytest.raises(ChangeValidationError, match="changed since planning"):
        applier.validate(
            [FileChange("existing.py", "stale\n", "replacement", "test")]
        )

    assert applier.validate(
        [FileChange("existing.py", "original\n", "replacement", "test")]
    )

    with pytest.raises(WorkspaceBoundaryError, match="escapes workspace"):
        applier.validate([FileChange("../outside.py", None, "x", "test")])


def test_worker_can_create_new_file_inside_workspace(tmp_path: Path) -> None:
    worker = DevelopmentWorker(tmp_path)
    worker.begin_iteration(1)

    result = worker.apply_changes(
        iteration=1,
        changes=[
            {
                "path": "tests/test_new_feature.py",
                "old_content": None,
                "new_content": "def test_new_feature():\n    assert True\n",
                "reason": "Add a harmless regression test.",
            }
        ],
    )

    assert result["success"] is True
    assert (tmp_path / "tests/test_new_feature.py").is_file()


def test_worker_accepts_only_explicit_validation_argv(tmp_path: Path) -> None:
    worker = DevelopmentWorker(tmp_path)

    assert worker._is_allowed_command(("python", "-m", "pytest", "-q"))
    assert worker._is_allowed_command(("npm", "test", "--", "--run"))
    assert not worker._is_allowed_command(
        ("python", "-m", "pytest", "-p", "unexpected_plugin")
    )
    assert not worker._is_allowed_command(("python", "-c", "print('unsafe')"))


def test_provider_defaults_to_local_ollama_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LUMIRA_DEV_API_URL", raising=False)
    monkeypatch.delenv("LUMIRA_DEV_API_KEY", raising=False)
    monkeypatch.delenv("LUMIRA_DEV_MODEL", raising=False)
    provider = OpenAICompatibleDevelopmentProvider()

    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model == "qwen2.5-coder:3b"
    assert provider._requires_api_key() is False
    assert OpenAICompatibleDevelopmentProvider(
        base_url="https://example.com/v1"
    )._requires_api_key() is True


def test_code_generator_fails_over_to_registered_provider_with_a_hard_cap(
    tmp_path: Path,
) -> None:
    class Provider(DevelopmentProvider):
        def __init__(self, name: str, result: dict):
            self.name = name
            self.result = result
            self.calls = 0

        def generate_changes(self, **kwargs):
            self.calls += 1
            return self.result

    registry = DevelopmentProviderRegistry()
    unavailable = Provider("openai_compatible", {"success": False, "code": "provider_unreachable"})
    available = Provider("backup", {"success": True, "changes": [{"path": "x.py"}]})
    ignored = Provider("third", {"success": True, "changes": [{"path": "y.py"}]})
    registry.register(unavailable)
    registry.register(available)
    registry.register(ignored)
    generator = DevelopmentCodeGenerator(tmp_path, registry)

    result = generator.generate_changes(goal="Add a test", files=[])

    assert result["success"] is True
    assert unavailable.calls == 1
    assert available.calls == 1
    assert ignored.calls == 0
    assert generator.MAX_PROVIDER_FALLBACKS == 2


def test_explicit_provider_selection_does_not_fail_over(tmp_path: Path) -> None:
    class Provider(DevelopmentProvider):
        def __init__(self, name: str):
            self.name = name
            self.calls = 0

        def generate_changes(self, **kwargs):
            self.calls += 1
            return {"success": False, "code": "provider_unreachable"}

    registry = DevelopmentProviderRegistry()
    selected = Provider("selected")
    backup = Provider("backup")
    registry.register(selected)
    registry.register(backup)
    generator = DevelopmentCodeGenerator(tmp_path, registry)

    result = generator.generate_changes(
        goal="Add a test",
        files=[],
        provider_name="selected",
    )

    assert result["code"] == "provider_unreachable"
    assert selected.calls == 1
    assert backup.calls == 0


def test_local_provider_requests_json_mode_without_dummy_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
        model="qwen2.5-coder:3b",
    )
    response_body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "success": True,
                                "changes": [
                                    {
                                        "path": "tests/test_new.py",
                                        "old_content": None,
                                        "new_content": "def test_new(): pass\n",
                                        "reason": "Add the requested test.",
                                    }
                                ],
                            }
                        ),
                    }
                }
            ]
        }
    ).encode()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return response_body

    captured = {}

    def complete(request, timeout):
        captured["request"] = request
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(
        "app.services.autonomous_development.worker.openai_compatible_provider.urllib.request.urlopen",
        complete,
    )
    result = provider.generate_changes(
        goal="Add a test",
        workspace=".",
        files=[],
        context={
            "task": "Add a retry regression test",
            "acceptance_criteria": ["Retry exhaustion has a test."],
            "relevant_files": ["tests/test_autonomous_development.py"],
            "iteration": 2,
            "previous_validation": {"return_code": 1},
            "previous_error": {"code": "stale_change", "message": "Source changed after planning."},
        },
    )

    assert result["success"] is True
    assert len(result["changes"]) == 1
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["request"].get_header("Authorization") is None
    prompt = captured["payload"]["messages"][1]["content"]
    assert "Add a retry regression test" in prompt
    assert "Retry exhaustion has a test." in prompt
    assert "tests/test_autonomous_development.py" in prompt
    assert '"iteration": 2' in prompt
    assert '"return_code": 1' in prompt
    assert '"code": "stale_change"' in prompt


def test_provider_falls_back_to_ipv4_only_for_refused_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )
    response_body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "success": True,
                                "changes": [
                                    {
                                        "path": "tests/test_local.py",
                                        "old_content": None,
                                        "new_content": "def test_local(): pass\n",
                                        "reason": "Add the requested test.",
                                    }
                                ],
                            }
                        ),
                    }
                }
            ]
        }
    ).encode()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return response_body

    requests = []

    def open_url(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.URLError(
                OSError(10061, "connection refused")
            )
        return Response()

    monkeypatch.setattr(
        "app.services.autonomous_development.worker.openai_compatible_provider.urllib.request.urlopen",
        open_url,
    )
    result = provider.generate_changes(
        goal="Add a local test",
        workspace=".",
        files=[],
    )

    assert result["success"] is True
    assert requests[0].full_url.startswith("http://localhost:")
    assert requests[1].full_url.startswith("http://127.0.0.1:")
    assert requests[1].get_header("Authorization") is None


def test_provider_parses_fenced_or_embedded_json_and_rejects_invalid_output() -> None:
    valid_change = {
        "path": "tests/test_new.py",
        "old_content": None,
        "new_content": "def test_new(): pass\n",
        "reason": "Add the requested test.",
    }
    fenced = OpenAICompatibleDevelopmentProvider._parse_changes(
        "```json\n"
        + json.dumps({"success": True, "changes": [valid_change]})
        + "\n```"
    )
    embedded = OpenAICompatibleDevelopmentProvider._parse_changes(
        "Model response: "
        + json.dumps({"success": True, "changes": [valid_change]})
        + " done."
    )
    invalid = OpenAICompatibleDevelopmentProvider._parse_changes("not json")
    unsuccessful = OpenAICompatibleDevelopmentProvider._parse_changes(
        '{"success": false, "changes": []}'
    )
    explicit_no_change = OpenAICompatibleDevelopmentProvider._parse_changes(
        '{"status": "no_change", "already_satisfied": true, "evidence": "Existing test covers it"}'
    )

    assert fenced["success"] is True
    assert embedded["success"] is True
    assert invalid["success"] is False
    assert unsuccessful["success"] is False
    assert explicit_no_change["code"] == "provider_no_change"


def test_worker_retries_no_change_with_task_context_then_accepts_changes(
    tmp_path: Path,
) -> None:
    class RetryingGenerator(DevelopmentProvider):
        name = "retrying"

        def __init__(self):
            self.contexts = []

        def generate_changes(self, **kwargs):
            self.contexts.append(kwargs["context"])
            if len(self.contexts) == 1:
                return {
                    "success": False,
                    "code": "provider_no_change",
                    "status": "no_change",
                    "message": "No evidence provided.",
                }
            return {"success": True, "changes": []}

    generator = RetryingGenerator()
    worker = DevelopmentWorker(tmp_path, code_generator=generator)
    result = worker.generate_changes(
        goal="Add a regression test",
        iteration=1,
        context={
            "task": "Add the missing bounded retry test",
            "acceptance_criteria": ["Test verifies retry exhaustion."],
            "previous_validation": {"return_code": 1},
        },
    )

    assert result["success"] is True
    assert len(generator.contexts) == 2
    assert generator.contexts[0]["task"] == "Add the missing bounded retry test"
    assert generator.contexts[0]["acceptance_criteria"] == [
        "Test verifies retry exhaustion."
    ]
    assert generator.contexts[1]["provider_attempt"] == 2
    assert "retry_instruction" in generator.contexts[1]
    assert "previous_provider_result" in generator.contexts[1]


def test_worker_retries_malformed_changes_before_application(
    tmp_path: Path,
) -> None:
    class MalformedThenValidGenerator(DevelopmentProvider):
        name = "malformed_then_valid"

        def __init__(self):
            self.contexts = []

        def generate_changes(self, **kwargs):
            self.contexts.append(kwargs["context"])
            if len(self.contexts) == 1:
                return {
                    "success": True,
                    "changes": [
                        {
                            "path": "tests/test_retry.py",
                            "old_content": None,
                            "reason": "Missing required new_content.",
                        }
                    ],
                }
            return {
                "success": True,
                "changes": [
                    {
                        "path": "tests/test_retry.py",
                        "old_content": None,
                        "new_content": "def test_retry(): pass\n",
                        "reason": "Add the requested regression test.",
                    }
                ],
            }

    generator = MalformedThenValidGenerator()
    worker = DevelopmentWorker(tmp_path, code_generator=generator)
    result = worker.generate_changes(
        goal="Add a test",
        iteration=1,
    )

    assert result["success"] is True
    assert len(generator.contexts) == 2
    assert generator.contexts[1]["previous_provider_result"]["code"] == "provider_invalid_changes"
    assert "new_content" in generator.contexts[1]["previous_provider_result"]["message"]
    assert not (tmp_path / "tests/test_retry.py").exists()


def test_worker_stops_after_bounded_no_change_attempts(tmp_path: Path) -> None:
    class NoChangeGenerator(DevelopmentProvider):
        name = "no_change"

        def __init__(self):
            self.calls = 0

        def generate_changes(self, **kwargs):
            self.calls += 1
            return {
                "success": False,
                "code": "provider_no_change",
                "message": "No supported change proposed.",
            }

    generator = NoChangeGenerator()
    worker = DevelopmentWorker(tmp_path, code_generator=generator)
    result = worker.generate_changes(
        goal="Add a missing test",
        iteration=1,
    )

    assert result["success"] is False
    assert result["code"] == "provider_retry_exhausted"
    assert result["attempts"] == worker.MAX_PROVIDER_ATTEMPTS
    assert result["last_error"]["code"] == "provider_no_change"
    assert generator.calls == worker.MAX_PROVIDER_ATTEMPTS


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out with private detail"),
        urllib.error.URLError("offline with private detail"),
    ],
)
def test_provider_network_failures_are_bounded_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="http://localhost:11434/v1",
    )

    def fail_request(*args, **kwargs):
        raise failure

    monkeypatch.setattr(
        "app.services.autonomous_development.worker.openai_compatible_provider.urllib.request.urlopen",
        fail_request,
    )
    result = provider.generate_changes(
        goal="test",
        workspace=".",
        files=[],
    )

    assert result["success"] is False
    assert result["code"] == "provider_unreachable"
    assert "private detail" not in json.dumps(result)


def test_provider_error_does_not_expose_http_response_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "credential-value-that-must-not-escape"
    provider = OpenAICompatibleDevelopmentProvider(
        base_url="https://example.com/v1",
        api_key="configured-key",
    )
    error = urllib.error.HTTPError(
        "https://example.com/v1/chat/completions",
        500,
        "failure",
        {},
        io.BytesIO(secret.encode()),
    )

    def fail_request(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        "app.services.autonomous_development.worker.openai_compatible_provider.urllib.request.urlopen",
        fail_request,
    )
    result = provider.generate_changes(
        goal="test",
        workspace=".",
        files=[],
    )

    assert result["success"] is False
    assert result["code"] == "provider_http_error"
    assert result["status_code"] == 500
    assert secret not in json.dumps(result)


def test_provider_context_remains_bounded_and_excludes_generated_output(
    tmp_path: Path,
) -> None:
    for index in range(15):
        path = tmp_path / "tests" / f"test_item_{index}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 100, encoding="utf-8")
    focused_test = tmp_path / "tests" / "test_lumira_autonomous_development.py"
    focused_test.write_text("focused test context", encoding="utf-8")
    oversized_test = tmp_path / "tests" / "test_autonomous_development.py"
    oversized_test.write_text("large generic test context\n" * 2_000, encoding="utf-8")
    backup = tmp_path / "tests" / "test_lumira_autonomous_development.py.backup"
    backup.write_text("backup context", encoding="utf-8")
    pytest_work = tmp_path / ".pytest-work" / "generated.py"
    pytest_work.parent.mkdir()
    pytest_work.write_text("pytest output", encoding="utf-8")
    generated = tmp_path / "generated" / "ignored.py"
    generated.parent.mkdir()
    generated.write_text("secretly irrelevant", encoding="utf-8")

    class CaptureGenerator(DevelopmentProvider):
        name = "capture"

        def generate_changes(self, **kwargs):
            self.files = kwargs["files"]
            self.context = kwargs["context"]
            return {"success": True, "changes": []}

    generator = CaptureGenerator()
    worker = DevelopmentWorker(tmp_path, code_generator=generator)
    result = worker.generate_changes(
        goal="pytest autonomous development test",
        iteration=1,
    )

    assert result["success"] is True
    assert len(generator.files) <= 12
    assert "tests/test_lumira_autonomous_development.py" in {
        item["path"].replace("\\", "/") for item in generator.files
    }
    assert all("test_item_" not in item["path"] for item in generator.files)
    assert all(
        item["path"].replace("\\", "/") != "tests/test_autonomous_development.py"
        for item in generator.files
    )
    assert sum(len(item["content"]) for item in generator.files) <= 100_000
    assert all(len(item["content"]) <= 50_000 for item in generator.files)
    assert all(not item["path"].startswith("generated/") for item in generator.files)
    assert all(not item["path"].endswith(".backup") for item in generator.files)
    assert all(".pytest-work" not in Path(item["path"]).parts for item in generator.files)


def test_failure_persistence_transitions_pending_stage_before_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(tmp_path, monkeypatch, [0])
    workflow = service.work_items.create_workflow(
        category="operations",
        title="Failure lifecycle regression",
        request="Record an early provider failure",
        tasks=["Generate changes", "Apply changes", "Validate"],
    )

    service._persist_workflow_failure(
        workflow["workflow_id"],
        {"success": False, "code": "provider_unreachable"},
    )

    persisted = service.work_items.get_workflow(workflow["workflow_id"])
    assert persisted["status"] == "failed"
    assert persisted["tasks"][0]["status"] == "failed"
    assert persisted["tasks"][1]["status"] == "blocked"
    assert persisted["tasks"][2]["status"] == "blocked"
