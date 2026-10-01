from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
from app.services.autonomous_development.worker.development_worker import (
    DevelopmentWorker,
)
from app.services.autonomous_development.worker.openai_compatible_provider import (
    OpenAICompatibleDevelopmentProvider,
)
from app.services.autonomous_development.worker.workspace_boundary import (
    WorkspaceBoundary,
    WorkspaceBoundaryError,
)
from app.services.work_items.work_item_service import WorkItemService


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
        recovery=object(),
    )
    service.development_loop.inspect_and_plan = lambda goal: {
        "success": True,
        "plan": {"steps": ["inspect", "plan", "implement", "test", "verify"]},
    }

    worker = service.development_loop.worker
    generation_contexts: list[dict] = []

    def generate(*, goal: str, iteration: int, context: dict) -> dict:
        worker.begin_iteration(iteration)
        generation_contexts.append(context)
        if not apply_changes:
            return {"success": True, "files_changed": []}
        relative_path = f"generated_iteration_{iteration}.txt"
        worker.write_file(
            relative_path,
            f"Generated for iteration {iteration}\n",
            iteration=iteration,
        )
        return {"success": True, "files_changed": [relative_path]}

    worker.generate_and_apply = generate
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
        raise RuntimeError("provider unavailable")

    service.development_loop.worker.generate_and_apply = fail_generation
    result = service.execute("Add a harmless operational test")

    workflow = service.work_items.get_workflow(result["workflow_id"])
    assert result["state"] == "failed"
    assert workflow["status"] == "failed"
    assert workflow["tasks"][2]["status"] == "failed"
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


def test_actionable_goal_with_no_changes_fails_durably(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _service(
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
    service, _ = _service(
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
        tasks=["Implement the requested test"],
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

    result = service.execute(goal)

    assert result["success"] is True
    assert result["verification"]["prior_goal_changes_reused"] is True


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
                        "content": '{"success": true, "changes": []}',
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
    )

    assert result == {"success": True, "changes": []}
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["request"].get_header("Authorization") is None


def test_provider_parses_fenced_or_embedded_json_and_rejects_invalid_output() -> None:
    fenced = OpenAICompatibleDevelopmentProvider._parse_changes(
        '```json\n{"success": true, "changes": []}\n```'
    )
    embedded = OpenAICompatibleDevelopmentProvider._parse_changes(
        'Model response: {"success": true, "changes": []} done.'
    )
    invalid = OpenAICompatibleDevelopmentProvider._parse_changes("not json")
    unsuccessful = OpenAICompatibleDevelopmentProvider._parse_changes(
        '{"success": false, "changes": []}'
    )

    assert fenced["success"] is True
    assert embedded["success"] is True
    assert invalid["success"] is False
    assert unsuccessful["success"] is False


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
    assert secret not in json.dumps(result)


def test_provider_context_remains_bounded_and_excludes_generated_output(
    tmp_path: Path,
) -> None:
    for index in range(15):
        path = tmp_path / "tests" / f"test_item_{index}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 100, encoding="utf-8")
    focused_test = tmp_path / "tests" / "test_autonomous_development.py"
    focused_test.write_text("focused test context", encoding="utf-8")
    backup = tmp_path / "tests" / "test_autonomous_development.py.backup"
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
    assert "tests/test_autonomous_development.py" in {
        item["path"].replace("\\", "/") for item in generator.files
    }
    assert sum(len(item["content"]) for item in generator.files) <= 100_000
    assert all(len(item["content"]) <= 50_000 for item in generator.files)
    assert all(not item["path"].startswith("generated/") for item in generator.files)
    assert all(not item["path"].endswith(".backup") for item in generator.files)
    assert all(".pytest-work" not in Path(item["path"]).parts for item in generator.files)