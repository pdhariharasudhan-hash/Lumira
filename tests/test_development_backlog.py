from __future__ import annotations

import subprocess

from app.services.autonomous_development.autonomous_development_service import AutonomousDevelopmentService
from app.services.autonomous_development.development_backlog_service import DevelopmentBacklogService
from app.services.autonomous_development.development_audit_service import DevelopmentAuditService
from app.services.autonomous_development.development_progress_service import DevelopmentProgressService
from app.services.autonomous_development.development_task_planner import DevelopmentTaskPlanner
from app.services.autonomous_development.worker.development_worker import DevelopmentWorker
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.work_items.work_item_service import WorkItemService


def _task(objective: str, *, priority: int = 50, dependencies: list = None) -> dict:
    return {
        "objective": objective,
        "category": "implementation",
        "priority": priority,
        "dependencies": dependencies or [],
        "relevant_files": ["app/sample.py"],
        "acceptance_criteria": ["The expected behavior is verified."],
        "validation_commands": [["python", "-m", "pytest", "-q"]],
    }


def test_backlog_persists_required_task_state_and_selects_by_dependencies_priority(tmp_path):
    path = tmp_path / "development_backlog.json"
    backlog = DevelopmentBacklogService(path)
    program = backlog.create_program(
        "Continue Lumira development",
        [
            _task("First prerequisite", priority=1),
            _task("High priority dependent", priority=100, dependencies=[0]),
            _task("Independent work", priority=50),
        ],
        audit={"findings": 3},
    )
    reloaded = DevelopmentBacklogService(path)

    selected = reloaded.next_ready_task(program["program_id"])

    assert selected["objective"] == "Independent work"
    required = {
        "task_id", "goal", "objective", "category", "priority", "dependencies",
        "relevant_files", "acceptance_criteria", "validation_commands", "status",
        "attempts", "iteration", "last_error", "last_validation", "created_at", "updated_at",
    }
    assert required.issubset(selected)
    assert selected["attempts"] == 0

    backlog.update_task(program["program_id"], program["tasks"][0]["task_id"], status="completed")
    selected_after_dependency = backlog.next_ready_task(program["program_id"])
    assert selected_after_dependency["objective"] == "High priority dependent"


def test_backlog_deduplicates_audit_findings_and_records_redacted_lessons(tmp_path):
    backlog = DevelopmentBacklogService(tmp_path / "development_backlog.json")
    planner = DevelopmentTaskPlanner(backlog)
    audit = {
        "findings": [
            {
                "path": "app/sample.py",
                "objective": "Fix verified implementation gap",
                "acceptance": "A regression test passes.",
            }
        ]
    }
    program = planner.create_or_resume_program("Continue Lumira development", audit)
    existing_program_id = program["program_id"]
    refreshed = planner.create_or_resume_program("Continue Lumira development", audit)

    assert refreshed["program_id"] == existing_program_id
    assert len(refreshed["tasks"]) == 1

    task = refreshed["tasks"][0]
    progress = DevelopmentProgressService(backlog)
    progress.start(refreshed["program_id"], task["task_id"], iteration=1)
    progress.complete(
        refreshed["program_id"],
        task["task_id"],
        result={"files_changed": ["app/sample.py"], "lessons": ["api_key=do-not-store"]},
        validation={"status": "completed", "return_code": 0, "command": ["python", "-m", "pytest", "-q"]},
    )
    lesson = backlog.lessons()[0]

    assert refreshed["program_id"] == backlog.latest_program()["program_id"]
    assert backlog.latest_program()["status"] == "completed"
    assert "do-not-store" not in str(lesson)
    assert lesson["validation_status"] == "completed"


def test_backlog_attempt_limit_blocks_task_without_unbounded_retries(tmp_path):
    backlog = DevelopmentBacklogService(tmp_path / "development_backlog.json")
    program = backlog.create_program("Continue", [_task("Bounded failure")], audit={})
    progress = DevelopmentProgressService(backlog)
    task_id = program["tasks"][0]["task_id"]

    for iteration in range(1, backlog.MAX_ATTEMPTS + 1):
        progress.start(program["program_id"], task_id, iteration=iteration)
        progress.fail_or_block(
            program["program_id"],
            task_id,
            error={"code": "provider_unreachable", "message": "offline"},
            retryable=True,
        )

    task = backlog.get_program(program["program_id"])["tasks"][0]
    assert task["status"] == "blocked"
    assert task["attempts"] == backlog.MAX_ATTEMPTS
    assert task["last_error"]["code"] == "provider_unreachable"
    assert backlog.get_program(program["program_id"])["status"] == "blocked"


def test_failure_diagnosis_distinguishes_provider_stale_validation_and_safety():
    cases = [
        ({"code": "provider_unreachable"}, None, "provider_failure"),
        ({"code": "resume_limit_reached"}, None, "recovery_limit"),
        ({"code": "unsafe_changes", "message": "old_content stale"}, None, "malformed_or_stale_change"),
        ({"code": "max_iterations_reached"}, {"return_code": 1}, "test_failure"),
        ({"code": "workspace_boundary_rejected"}, None, "safety_rejection"),
    ]

    for error, validation, expected in cases:
        diagnosed = DevelopmentProgressService.diagnose_failure(error, validation)
        assert diagnosed["category"] == expected
        assert diagnosed["recommended_next_action"]


def test_persisted_validation_output_is_bounded_and_keeps_tail():
    output = "x" * 8_000 + "\n2 passed in 0.1s"
    summary = DevelopmentProgressService.summarize_validation({
        "iteration": 2,
        "status": "completed",
        "command": ["python", "-m", "pytest", "-q"],
        "return_code": 0,
        "output": output,
    })

    assert summary["return_code"] == 0
    assert summary["output_truncated"] is True
    assert len(summary["output_tail"]) <= 4_000
    assert summary["output_tail"].endswith("2 passed in 0.1s")


def test_continue_resumes_persisted_task_and_does_not_create_duplicate_program(tmp_path):
    backlog_path = tmp_path / "memory" / "development_backlog.json"
    backlog = DevelopmentBacklogService(backlog_path)
    task = _task("Recover persisted task")
    program = backlog.create_program("Continue Lumira development", [task], audit={"findings": [task]})
    task_record = program["tasks"][0]
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    workflow = WorkItemService(tmp_path / "work_items.json").create_workflow(
        category="operations",
        title="Interrupted development",
        request=task_record["goal"],
        tasks=["Implement", "Validate"],
    )
    run = recovery.create_run(
        task_record["goal"],
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["generate_changes", "apply_changes", "validate"],
        },
    )
    recovery.update(run["run_id"], "start_stage", stage="generate_changes")
    backlog.update_task(
        program["program_id"],
        task_record["task_id"],
        status="in_progress",
        attempts=1,
        recovery_run_id=run["run_id"],
    )

    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=recovery,
        backlog=DevelopmentBacklogService(backlog_path),
    )
    service.audit_service.run = lambda: {
        "workspace": str(tmp_path),
        "file_count": 0,
        "findings": [],
        "completion_ready": True,
        "completion_blockers": [],
    }
    service.resume = lambda run_id: {
        "success": True,
        "state": "completed",
        "recovery_run_id": run_id,
        "workflow_id": workflow["workflow_id"],
        "validation": {"status": "completed", "return_code": 0, "command": ["python", "-m", "pytest", "-q"]},
        "workflow": {"status": "completed"},
    }

    result = service.execute("Continue Lumira development")

    assert result["success"] is True
    assert result["program_id"] == program["program_id"]
    assert len(service.backlog.list_programs()) == 1
    assert service.backlog.get_program(program["program_id"])["tasks"][0]["status"] == "completed"


def test_audit_finds_real_failed_recovery_run_from_existing_durable_stores(tmp_path):
    work_items = WorkItemService(tmp_path / "work_items.json")
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    workflow = work_items.create_workflow(
        category="operations",
        title="Autonomous Lumira Development",
        request="Add a recovery regression test",
        tasks=["Inspect", "Implement test"],
    )
    first_task = workflow["tasks"][0]
    work_items.update_task(workflow["workflow_id"], first_task["task_id"], "in_progress")
    work_items.update_task(workflow["workflow_id"], first_task["task_id"], "completed", result="{}")
    second_task = workflow["tasks"][1]
    work_items.update_task(workflow["workflow_id"], second_task["task_id"], "in_progress")
    run = recovery.create_run(
        workflow["request"],
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["generate_changes", "apply_changes"],
        },
    )
    recovery.update(run["run_id"], "start_stage", stage="generate_changes")
    recovery.update(run["run_id"], "fail_stage", stage="generate_changes", error="provider_timeout")
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=work_items,
        recovery=recovery,
    ).run()

    finding = next(item for item in audit["findings"] if item.get("recovery_run_id") == run["run_id"])
    assert finding["objective"] == "Add a recovery regression test"
    assert finding["evidence"]["safe_resume_point"] == "generate_changes"


def test_audit_does_not_resurrect_recovery_already_completed_in_backlog(tmp_path):
    work_items = WorkItemService(tmp_path / "work_items.json")
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    backlog = DevelopmentBacklogService(tmp_path / "development_backlog.json")
    goal = "Add a harmless pytest test confirming Lumira autonomous development is operational"
    workflow = work_items.create_workflow(
        category="operations",
        title="Autonomous Lumira Development",
        request=goal,
        tasks=["Inspect", "Implement"],
    )
    run = recovery.create_run(
        goal,
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["generate_changes"],
        },
    )
    recovery.update(run["run_id"], "start_stage", stage="generate_changes")
    recovery.update(run["run_id"], "fail_stage", stage="generate_changes", error="old_provider_failure")
    program = backlog.create_program(goal, [_task(goal)], audit={})
    task = program["tasks"][0]
    backlog.update_task(program["program_id"], task["task_id"], status="in_progress")
    backlog.update_task(program["program_id"], task["task_id"], status="completed")
    worker = DevelopmentWorker(tmp_path)

    audit = DevelopmentAuditService(
        worker,
        work_items=work_items,
        recovery=recovery,
        backlog=backlog,
    ).run()

    assert all(item.get("objective") != goal for item in audit["findings"])


def test_audit_detects_unregistered_router_and_desktop_api_route_mismatch(tmp_path):
    boundary = DevelopmentWorker(tmp_path)
    (tmp_path / "app/routes").mkdir(parents=True)
    (tmp_path / "app/routes/orphan.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n",
        encoding="utf-8",
    )
    (tmp_path / "app/main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    (tmp_path / "lumira_desktop/src/api").mkdir(parents=True)
    (tmp_path / "lumira_desktop/src/api/client.ts").write_text(
        'request<JsonObject>("/api/not-registered");\n',
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(boundary, work_items=WorkItemService(tmp_path / "work_items.json"), recovery=RunRecoveryService(tmp_path / "workflow_runs.json"))
    router_findings = audit._router_registration_findings(
        ["app/main.py", "app/routes/orphan.py"],
        {},
    )
    api_findings = audit._desktop_api_contract_findings(
        ["lumira_desktop/src/api/client.ts"],
        {},
    )

    assert router_findings[0]["category"] == "disconnected_route"
    assert router_findings[0]["evidence"]["registered"] is False
    assert any(item["category"] == "frontend_backend_contract" for item in api_findings)


def test_audit_behavioral_gate_does_not_launch_project_commands_without_sandbox(tmp_path, monkeypatch):
    def forbidden_run(*args, **kwargs):
        raise AssertionError("audit must not execute project-controlled commands without OS isolation")

    monkeypatch.setattr(subprocess, "run", forbidden_run)
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )

    gate = audit._behavioral_gate()

    assert gate["status"] == "blocked"
    assert gate["expected_command_count"] == 4
    assert len(gate["commands"]) == 4
    assert all(command["status"] == "not_run" for command in gate["commands"])
    assert "OS-level sandboxing is not implemented" in gate["reason"]


def test_audit_reports_terminal_sandbox_as_unfinished(tmp_path):
    terminal_path = "app/services/workspace/project_terminal_service.py"
    terminal_file = tmp_path / terminal_path
    terminal_file.parent.mkdir(parents=True)
    terminal_file.write_text(
        'class ProjectTerminalService:\n    OS_SANDBOX_ENABLED = False\n    COMMANDS: dict = {}\n',
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )

    result = audit._project_terminal_security_status([terminal_path])

    assert result["status"] == "blocked"
    assert result["command_allowlist"] is True
    assert result["os_sandbox"] is False
    assert result["sandbox_verification"] == "not_implemented"
    assert result["untrusted_project_code_execution_possible"] is True


def test_audit_does_not_trust_a_sandbox_boolean_flag(tmp_path):
    terminal_path = "app/services/workspace/project_terminal_service.py"
    terminal_file = tmp_path / terminal_path
    terminal_file.parent.mkdir(parents=True)
    terminal_file.write_text(
        'class ProjectTerminalService:\n    OS_SANDBOX_ENABLED = True\n    COMMANDS: dict = {}\n',
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )

    result = audit._project_terminal_security_status([terminal_path])

    assert result["status"] == "blocked"
    assert result["os_sandbox"] is False
    assert result["sandbox_verification"] == "not_implemented"
    assert result["untrusted_project_code_execution_possible"] is True


def test_audit_reports_explicit_desktop_terminal_and_preview_gaps(tmp_path):
    panel = "lumira_desktop/src/components/RightPanel/RightPanel.tsx"
    panel_path = tmp_path / panel
    panel_path.parent.mkdir(parents=True)
    panel_path.write_text(
        '"Terminal unavailable"; "Preview unavailable";\n',
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )

    findings = audit._desktop_capability_findings([panel], {})

    assert {item["category"] for item in findings} == {"desktop_capability_gap"}
    assert len(findings) == 2


def test_audit_does_not_report_terminal_available_without_verified_sandbox(tmp_path):
    panel_path = "lumira_desktop/src/components/RightPanel/RightPanel.tsx"
    terminal_path = "app/services/workspace/project_terminal_service.py"
    panel = tmp_path / panel_path
    terminal = tmp_path / terminal_path
    panel.parent.mkdir(parents=True)
    terminal.parent.mkdir(parents=True)
    panel.write_text('const terminalLabel = "Terminal"; const previewLabel = "Preview";\n', encoding="utf-8")
    terminal.write_text(
        'class ProjectTerminalService:\n    OS_SANDBOX_ENABLED = False\n    COMMANDS: dict = {}\n',
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )
    checks = {}

    findings = audit._desktop_capability_findings([panel_path, terminal_path], checks)

    assert findings == []
    assert checks["desktop_capabilities"]["terminal_ui_present"] is True
    assert checks["desktop_capabilities"]["terminal_available"] is False
    assert checks["desktop_capabilities"]["preview_provider_registered"] is True


def test_audit_uses_ast_for_unsafe_shell_and_broken_local_import_detection(tmp_path):
    unsafe_path = "app/services/unsafe.py"
    broken_path = "app/services/broken.py"
    (tmp_path / "app/services").mkdir(parents=True)
    (tmp_path / unsafe_path).write_text(
        "import subprocess\nsubprocess.run(['echo', 'x'], shell=True)\n",
        encoding="utf-8",
    )
    (tmp_path / broken_path).write_text(
        "from app.services.missing_module import Missing\n",
        encoding="utf-8",
    )
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )
    security_findings = audit._security_findings([unsafe_path], {})
    integrity_findings = audit._source_integrity_findings([unsafe_path, broken_path], {})

    assert security_findings[0]["category"] == "unsafe_process_execution"
    assert any(item["category"] == "broken_local_import" for item in integrity_findings)


def test_source_integrity_audit_accepts_utf8_bom_python_sources(tmp_path):
    source_path = tmp_path / "app/services/bom_module.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("VALUE = 1\n" + "# valid filler\n" * 5_000, encoding="utf-8-sig")
    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
    )
    checks = {}

    findings = audit._source_integrity_findings(["app/services/bom_module.py"], checks)

    assert findings == []
    assert checks["source_integrity"]["syntax_error_count"] == 0
    assert checks["source_integrity"]["source_chars_checked"] > 50_000


def test_continuation_retries_provider_failure_then_blocks_without_duplicates(tmp_path):
    backlog_path = tmp_path / "memory" / "development_backlog.json"
    backlog = DevelopmentBacklogService(backlog_path)
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    workflow = WorkItemService(tmp_path / "work_items.json").create_workflow(
        category="operations",
        title="Autonomous Lumira Development",
        request="Add an operational smoke test",
        tasks=["Implement", "Validate"],
    )
    run = recovery.create_run(
        workflow["request"],
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["generate_changes", "apply_changes"],
        },
    )
    program = backlog.create_program(
        "Continue Lumira development",
        [{
            **_task("Add an operational smoke test", priority=80),
            "recovery_run_id": run["run_id"],
            "source_workflow_id": workflow["workflow_id"],
        }],
        audit={"findings": ["durable provider-failure record"]},
    )

    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=recovery,
        backlog=DevelopmentBacklogService(backlog_path),
    )
    service.audit_service.run = lambda: {
        "workspace": str(tmp_path),
        "file_count": 0,
        "findings": [],
        "completion_ready": True,
        "completion_blockers": [],
    }
    service.resume = lambda run_id: {
        "success": False,
        "state": "failed",
        "code": "provider_retry_exhausted",
        "recovery_run_id": run_id,
        "result": {"code": "provider_retry_exhausted", "message": "Provider attempts exhausted."},
    }

    for attempt in range(1, backlog.MAX_ATTEMPTS + 1):
        service.execute("Continue")
        program_state = service.backlog.get_program(program["program_id"])
        assert len(program_state["tasks"]) == 1
        assert program_state["tasks"][0]["attempts"] == attempt

    final_task = service.backlog.get_program(program["program_id"])["tasks"][0]
    assert final_task["status"] == "blocked"
    assert final_task["last_error"]["code"] == "provider_retry_exhausted"
    assert service.backlog.get_program(program["program_id"])["status"] == "blocked"


def test_bounded_audit_without_whole_program_coverage_never_marks_complete(tmp_path):
    backlog_path = tmp_path / "memory" / "development_backlog.json"
    backlog = DevelopmentBacklogService(backlog_path)
    program = backlog.create_program(
        "Continue Lumira development",
        [_task("A verified task")],
        audit={"findings": ["a verified item"]},
    )
    task = program["tasks"][0]
    backlog.update_task(program["program_id"], task["task_id"], status="in_progress")
    backlog.update_task(program["program_id"], task["task_id"], status="completed")
    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
        backlog=DevelopmentBacklogService(backlog_path),
    )
    service.audit_service.run = lambda: {
        "workspace": str(tmp_path),
        "file_count": 1,
        "findings": [],
        "completion_ready": False,
        "completion_blockers": ["Whole-program audit is not available."],
    }

    result = service.execute("Continue")

    assert result["success"] is False
    assert result["code"] == "final_audit_incomplete"
    persisted = service.backlog.get_program(program["program_id"])
    assert persisted["status"] == "blocked"
    assert persisted["completion_blockers"] == ["Whole-program audit is not available."]


def test_continuation_reclassifies_old_resume_limit_blocker_without_retry(tmp_path):
    backlog_path = tmp_path / "memory" / "development_backlog.json"
    backlog = DevelopmentBacklogService(backlog_path)
    program = backlog.create_program(
        "Continue Lumira development",
        [_task("Recover a blocked run")],
        audit={},
    )
    task = program["tasks"][0]
    backlog.update_task(
        program["program_id"],
        task["task_id"],
        status="blocked",
        attempts=3,
        last_error={"code": "resume_limit_reached", "message": "Development task did not satisfy its acceptance criteria."},
    )
    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
        backlog=DevelopmentBacklogService(backlog_path),
    )
    service.audit_service.run = lambda: {
        "workspace": ".",
        "file_count": 0,
        "findings": [],
        "completion_ready": False,
        "completion_blockers": ["Whole-program audit is not available."],
    }
    called = []
    service.resume = lambda run_id: called.append(run_id)

    service.execute("Continue")

    updated = service.backlog.get_program(program["program_id"])["tasks"][0]
    assert updated["status"] == "blocked"
    assert updated["last_error"]["category"] == "recovery_limit"
    assert "maximum resume count" in updated["last_error"]["message"]
    assert called == []


def test_fresh_backlog_execution_links_recovery_run_and_task_checkpoint(tmp_path, monkeypatch):
    backlog_path = tmp_path / "memory" / "development_backlog.json"
    service = AutonomousDevelopmentService(
        tmp_path,
        workflow_engine=object(),
        work_items=WorkItemService(tmp_path / "work_items.json"),
        recovery=RunRecoveryService(tmp_path / "workflow_runs.json"),
        backlog=DevelopmentBacklogService(backlog_path),
    )
    service.audit_service.run = lambda: {
        "workspace": str(tmp_path),
        "file_count": 1,
        "findings": [{
            "path": "tests/test_handoff.py",
            "objective": "Add a handoff regression test",
            "acceptance": "The new test passes.",
        }],
        "completion_ready": True,
        "completion_blockers": [],
    }
    service.development_loop.inspect_and_plan = lambda goal: {
        "success": True,
        "plan": {"steps": ["inspect", "plan", "implement", "test", "verify"]},
    }
    worker = service.development_loop.worker
    # This unit test injects a fake runner to exercise the success path without launching code.
    monkeypatch.setattr(worker, "_os_sandbox_is_verified", lambda: True)

    def generate(**kwargs):
        worker.begin_iteration(kwargs["iteration"])
        return {
            "success": True,
            "changes": [{
                "path": "tests/test_handoff.py",
                "old_content": None,
                "new_content": "def test_handoff():\n    assert True\n",
                "reason": "Add the requested handoff regression.",
            }],
        }

    worker.generate_changes = generate
    validation_calls = []
    monkeypatch.setattr(
        "app.services.autonomous_development.worker.development_worker.subprocess.run",
        lambda command, **kwargs: (
            validation_calls.append(command)
            or __import__("subprocess").CompletedProcess(command, 0, "ok", "")
        ),
    )

    result = service.execute("Continue")
    program = service.backlog.get_program(result["program_id"])
    task = program["tasks"][0]
    recovery = service.inspect(task["recovery_run_id"])

    assert result["success"] is True, {
        "state": result.get("state"),
        "results": [
            {
                "objective": item.get("objective"),
                "success": item.get("result", {}).get("success"),
                "code": item.get("result", {}).get("code"),
                "message": item.get("result", {}).get("message"),
                "nested": item.get("result", {}).get("result"),
            }
            for item in result.get("results", [])
        ],
    }
    assert task["status"] == "completed"
    assert task["attempts"] == 1
    assert task["iteration"] == 1
    assert recovery["development_program_id"] == program["program_id"]
    assert recovery["development_task_id"] == task["task_id"]
    assert validation_calls == [["python", "-m", "pytest", "-q"]]

def test_audit_blocks_repeated_sandbox_recovery_until_os_isolation_exists(tmp_path):
    work_items = WorkItemService(tmp_path / "work_items.json")
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    objective = "Implement a sandboxed project terminal provider using only the validation command allowlist."
    workflow = work_items.create_workflow(
        category="operations",
        title="Autonomous Lumira Development",
        request=objective,
        tasks=["Inspect", "Implement"],
    )
    task = workflow["tasks"][0]
    work_items.update_task(workflow["workflow_id"], task["task_id"], "in_progress")
    run = recovery.create_run(
        objective,
        {
            "success": True,
            "autonomous_development": True,
            "workflow_id": workflow["workflow_id"],
            "steps": ["generate_changes", "apply_changes"],
        },
    )
    recovery.update(run["run_id"], "start_stage", stage="generate_changes")
    recovery.update(
        run["run_id"],
        "fail_stage",
        stage="generate_changes",
        error="Provider did not produce applicable changes after 2 bounded attempts.",
    )

    audit = DevelopmentAuditService(
        DevelopmentWorker(tmp_path),
        work_items=work_items,
        recovery=recovery,
    ).run()

    assert all(item.get("recovery_run_id") != run["run_id"] for item in audit["findings"])
    historical = audit["checks"]["historical_recovery"]
    assert historical["status"] == "blocked"
    assert historical["count"] == 1
    assert "missing verified OS sandbox" in historical["runs"][0]["reason"]
    assert audit["completion_ready"] is False
    assert any("OS sandbox" in blocker for blocker in audit["completion_blockers"])
