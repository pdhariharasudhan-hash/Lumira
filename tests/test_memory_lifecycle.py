from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.routes.goals import GoalCreateRequest, GoalUpdateRequest


def test_memory_lifecycle_search_link_summarize_archive(tmp_path):
    service = MemoryService(str(tmp_path / "memory.json"))
    goal = service.create_goal("Build Lumira memory", "Expand deterministic memory lifecycle", project_id="lumira")
    decision = service.record_decision("Use deterministic ranking", project_id="lumira", goal_id=goal["goal_id"])
    experience = service.record_experience(
        "success",
        "Memory lifecycle implementation passed validation",
        "The new lifecycle is available",
        project_id="lumira",
        goal_id=goal["goal_id"],
        lessons=["Keep cognitive memory operations deterministic and auditable"],
        verified=True,
    )
    learning = service.consolidate_learning(experience)
    repeated_learning = service.consolidate_learning(experience)

    assert repeated_learning["learning_id"] == learning["learning_id"]
    assert service.summarize(project_id="lumira")["counts"]["learning_records"] == 1
    results = service.search("deterministic memory", project_id="lumira")
    assert results["goals"]
    assert results["decisions"]
    assert results["experiences"]
    assert learning is not None
    assert results["learning_records"]

    link = service.link(goal["goal_id"], decision["decision_id"], "supported_by")
    assert link["source_id"] == goal["goal_id"]
    assert link["target_id"] == decision["decision_id"]

    summary = service.summarize(project_id="lumira")
    assert summary["counts"]["goals"] == 1
    assert summary["counts"]["decisions"] == 1
    assert summary["counts"]["experiences"] == 1
    assert summary["counts"]["learning_records"] == 1

    assert service.archive("goals", goal["goal_id"]) is True
    archived = service.get_all()["goals"][0]
    assert archived["archived"] is True
    assert "archived_at" in archived


def test_memory_evolution_preserves_original_and_supports_controlled_forgetting(tmp_path):
    service = MemoryService(str(tmp_path / "memory.json"))
    experience = service.record_experience(
        "success", "Original verified memory", "Original outcome",
        lessons=["A sufficiently long lesson is retained for audited evolution"],
        verified=True,
    )
    corrected = service.evolve(
        "experiences", experience["experience_id"],
        correction={"outcome": "Corrected outcome"}, reason="user correction",
    )
    assert corrected["outcome"] == "Corrected outcome"
    assert corrected["superseded_record"]["outcome"] == "Original outcome"
    forgotten = service.evolve("experiences", experience["experience_id"], forget=True)
    assert forgotten["archived"] is True
    assert forgotten["evolution_reason"] == "controlled_forgetting"


def test_memory_pipeline_history_corruption_is_rejected_without_rewriting(tmp_path):
    import json
    import pytest

    path = tmp_path / "memory.json"
    service = MemoryService(str(path))
    original = json.loads(path.read_text(encoding="utf-8"))
    original["pipeline_runs"] = "not-a-list"
    path.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(MemoryValidationError, match="pipeline_runs must be a list"):
        service.get_all()
    assert json.loads(path.read_text(encoding="utf-8"))["pipeline_runs"] == "not-a-list"

    original["pipeline_runs"] = ["not-a-record"]
    path.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(MemoryValidationError, match="invalid record"):
        service.get_all()
    assert json.loads(path.read_text(encoding="utf-8"))["pipeline_runs"] == ["not-a-record"]


def test_memory_search_is_bounded(tmp_path):
    service = MemoryService(str(tmp_path / "memory.json"))
    try:
        service.search("x" * 501)
    except MemoryValidationError as exc:
        assert "500" in str(exc)
    else:
        raise AssertionError("oversized memory query must be rejected")

    import pytest
    for invalid_limit in (True, False, "10", 1.5, None):
        with pytest.raises(MemoryValidationError, match="limit must be an integer"):
            service.search("memory", limit=invalid_limit)

    # Preserve the existing bounded behavior for integer limits.
    assert service.search("memory", limit=-1)["goals"] == []
    assert service.search("memory", limit=101) is not None



def test_non_boolean_verification_cannot_create_learning(tmp_path):
    service = MemoryService(str(tmp_path / "memory.json"))
    experience = service.record_experience(
        "success",
        "This experience must not be trusted by a truthy string",
        "Unverified input should not become a learning record",
        lessons=["Only explicitly verified experiences may be consolidated into learning"],
        verified="false",
    )

    assert experience["verified"] is False
    assert service.consolidate_learning(experience) is None
    assert service.summarize()["counts"]["learning_records"] == 0



def test_fabricated_experience_cannot_be_consolidated(tmp_path):
    service = MemoryService(str(tmp_path / "memory.json"))
    fabricated = {
        "experience_id": "not-persisted",
        "type": "success",
        "summary": "Fabricated success",
        "outcome": "This was never recorded in durable memory",
        "lessons": ["Only durable verified experiences may produce learning records"],
        "verified": True,
    }

    assert service.consolidate_learning(fabricated) is None
    assert service.summarize()["counts"]["learning_records"] == 0



def test_goal_creation_rejects_invalid_fields_before_persistence(tmp_path):
    import pytest

    service = MemoryService(str(tmp_path / "memory.json"))
    with pytest.raises(MemoryValidationError, match="title must not be empty"):
        service.create_goal("   ")
    with pytest.raises(MemoryValidationError, match="invalid goal status"):
        service.create_goal("Build Lumira", status="done-ish")
    with pytest.raises(MemoryValidationError, match="priority must be"):
        service.create_goal("Build Lumira", priority="critical")
    with pytest.raises(MemoryValidationError, match="blockers contains an invalid item"):
        service.create_goal("Build Lumira", blockers=["valid", 7])

    assert service.summarize()["counts"]["goals"] == 0


def test_goal_updates_reject_invalid_progress_and_unbounded_lists(tmp_path):
    import math
    import pytest

    service = MemoryService(str(tmp_path / "memory.json"))
    goal = service.create_goal("Build Lumira")
    goal_id = goal["goal_id"]

    for invalid_progress in (-1, 101, True, math.nan, math.inf, "50"):
        with pytest.raises(MemoryValidationError, match="progress must be"):
            service.update_goal(goal_id, progress=invalid_progress)

    with pytest.raises(MemoryValidationError, match="dependencies must be a list"):
        service.update_goal(goal_id, dependencies=None)
    with pytest.raises(MemoryValidationError, match="dependencies must be a list"):
        service.update_goal(goal_id, dependencies=["dep"] * 51)
    with pytest.raises(MemoryValidationError, match="invalid goal status"):
        service.update_goal(goal_id, status=["completed"])
    with pytest.raises(MemoryValidationError, match="at least one goal field"):
        service.update_goal(goal_id)

    unchanged = service.get_all()["goals"][0]
    assert unchanged["progress"] == 0.0
    assert unchanged["status"] == "active"
    assert unchanged["dependencies"] == []



def test_goal_updates_bound_nested_payloads_and_require_json_data(tmp_path):
    import pytest

    service = MemoryService(str(tmp_path / "memory.json"))
    goal = service.create_goal("Build Lumira")

    with pytest.raises(MemoryValidationError, match="100000-character limit"):
        service.update_goal(goal["goal_id"], milestones=[{"notes": "x" * 100_001}])
    with pytest.raises(MemoryValidationError, match="JSON-compatible"):
        service.update_goal(goal["goal_id"], milestones=[{"not_json": {1, 2}}])

    assert service.get_all()["goals"][0]["milestones"] == []



def test_goal_api_schemas_reject_invalid_values_and_normalize_titles():
    import pytest
    from pydantic import ValidationError

    assert GoalCreateRequest(title="  Build Lumira  ").title == "Build Lumira"
    with pytest.raises(ValidationError):
        GoalCreateRequest(title="   ")
    with pytest.raises(ValidationError):
        GoalCreateRequest(title="Build Lumira", priority="critical")
    with pytest.raises(ValidationError):
        GoalUpdateRequest(status="done")
    with pytest.raises(ValidationError):
        GoalUpdateRequest(title="   ")


def test_decision_writes_reject_malformed_or_unbounded_fields(tmp_path):
    import math
    import pytest

    service = MemoryService(str(tmp_path / "memory.json"))
    with pytest.raises(MemoryValidationError, match="alternatives must be a list"):
        service.record_decision("A valid decision", alternatives="not-a-list")
    with pytest.raises(MemoryValidationError, match="confidence must be"):
        service.record_decision("A valid decision", confidence=math.nan)
    with pytest.raises(MemoryValidationError, match="constraints must be a list"):
        service.record_decision("A valid decision", constraints=[f"item-{i}" for i in range(51)])
    with pytest.raises(MemoryValidationError, match="decision must be"):
        service.record_decision("x" * 2001)
    assert service.summarize()["counts"]["decisions"] == 0


def test_experience_writes_reject_malformed_or_unbounded_fields(tmp_path):
    import pytest

    service = MemoryService(str(tmp_path / "memory.json"))
    with pytest.raises(MemoryValidationError, match="lessons must be a list"):
        service.record_experience("success", "Valid summary", "Valid outcome", lessons="not-a-list")
    with pytest.raises(MemoryValidationError, match="summary must be"):
        service.record_experience("success", "x" * 4001, "Valid outcome")
    with pytest.raises(MemoryValidationError, match="artifact_ids contains"):
        service.record_experience("success", "Valid summary", "Valid outcome", artifact_ids=[7])
    with pytest.raises(MemoryValidationError, match="outcome must be"):
        service.record_experience("success", "Valid summary", " ")
    assert service.summarize()["counts"]["experiences"] == 0
