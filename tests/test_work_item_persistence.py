import json

import pytest

from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.work_items.work_item_service import WorkItemService, WorkItemValidationError


def _workflow_file(tmp_path):
    path = tmp_path / "work_items.json"
    service = WorkItemService(path)
    service.create_workflow(
        "operations",
        "Dependency validation",
        "Validate persisted task dependencies",
        ["First task", "Second task", "Third task"],
    )
    return path


def _corrupt_dependencies(path, configure):
    document = json.loads(path.read_text(encoding="utf-8"))
    tasks = document["workflows"][0]["tasks"]
    configure(tasks)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize(
    ("configure", "message"),
    [
        (lambda tasks: tasks[1].update(dependencies=["missing-task"]), "does not exist"),
        (lambda tasks: tasks[0].update(dependencies=[tasks[0]["task_id"]]), "depend on itself"),
        (
            lambda tasks: (
                tasks[0].update(dependencies=[tasks[1]["task_id"]]),
                tasks[1].update(dependencies=[tasks[0]["task_id"]]),
            ),
            "contain a cycle",
        ),
        (
            lambda tasks: tasks[1].update(dependencies=[tasks[0]["task_id"], tasks[0]["task_id"]]),
            "duplicate task dependencies",
        ),
    ],
)
def test_work_item_store_rejects_invalid_dependency_graph(tmp_path, configure, message):
    path = _workflow_file(tmp_path)
    _corrupt_dependencies(path, configure)

    with pytest.raises(PersistenceIntegrityError, match=message):
        WorkItemService(path).list_workflows()


def test_work_item_store_accepts_valid_dependency_chain(tmp_path):
    path = _workflow_file(tmp_path)

    workflows = WorkItemService(path).list_workflows()

    assert len(workflows) == 1
    tasks = workflows[0]["tasks"]
    assert tasks[0]["dependencies"] == []
    assert tasks[1]["dependencies"] == [tasks[0]["task_id"]]
    assert tasks[2]["dependencies"] == [tasks[1]["task_id"]]


def test_work_item_store_rejects_workflow_status_mismatch_without_rewriting(tmp_path):
    path = _workflow_file(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["workflows"][0]["status"] = "completed"
    path.write_text(json.dumps(document), encoding="utf-8")
    corrupted_contents = path.read_text(encoding="utf-8")

    with pytest.raises(PersistenceIntegrityError, match="status does not match"):
        WorkItemService(path).list_workflows()

    assert path.read_text(encoding="utf-8") == corrupted_contents


def test_completed_work_item_task_cannot_be_reopened(tmp_path):
    path = tmp_path / "work_items.json"
    service = WorkItemService(path)
    workflow = service.create_workflow(
        "operations",
        "Terminal task state",
        "Ensure completed work remains completed",
        ["Finish the first task", "Continue to the next task"],
    )
    task_id = workflow["tasks"][0]["task_id"]

    service.update_task(workflow["workflow_id"], task_id, "in_progress")
    service.update_task(
        workflow["workflow_id"],
        task_id,
        "completed",
        result="Verified complete",
    )

    with pytest.raises(
        WorkItemValidationError,
        match="cannot transition from completed to pending",
    ):
        service.update_task(workflow["workflow_id"], task_id, "pending")

    persisted = service.get_workflow(workflow["workflow_id"])
    assert persisted["tasks"][0]["status"] == "completed"
    assert persisted["tasks"][0]["result"] == "Verified complete"
    assert persisted["status"] == "in_progress"


def test_pending_work_item_cannot_be_marked_failed_without_starting(tmp_path):
    path = tmp_path / "work_items.json"
    service = WorkItemService(path)
    workflow = service.create_workflow(
        "operations",
        "Valid task transitions",
        "Reject invalid lifecycle changes",
        ["First task"],
    )
    task_id = workflow["tasks"][0]["task_id"]

    with pytest.raises(WorkItemValidationError, match="cannot transition from pending to failed"):
        service.update_task(workflow["workflow_id"], task_id, "failed")

    persisted = service.get_workflow(workflow["workflow_id"])
    assert persisted["tasks"][0]["status"] == "pending"



def test_completed_work_item_task_accepts_idempotent_completion_update(tmp_path):
    path = tmp_path / "work_items.json"
    service = WorkItemService(path)
    workflow = service.create_workflow(
        "operations",
        "Idempotent completion",
        "Repeated completion must not break workflow recovery",
        ["Finish the first task"],
    )
    task_id = workflow["tasks"][0]["task_id"]
    service.update_task(workflow["workflow_id"], task_id, "in_progress")
    first = service.update_task(
        workflow["workflow_id"], task_id, "completed", result="Verified complete"
    )
    second = service.update_task(
        workflow["workflow_id"], task_id, "completed", result="Verified complete"
    )

    assert first["tasks"][0]["status"] == "completed"
    assert second["tasks"][0]["status"] == "completed"
    assert second["tasks"][0]["result"] == "Verified complete"
    assert second["status"] == "completed"
