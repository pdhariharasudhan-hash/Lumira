from pathlib import Path

import pytest
from fastapi import HTTPException

import app.routes.artifacts as route
from app.services.artifacts.artifact_manager_service import ArtifactManagerService


class FakeMemory:
    def __init__(self):
        self.artifacts = {}

    def _safe_text(self, value):
        return str(value)

    def add_artifact(self, record):
        self.artifacts[record["artifact_id"]] = dict(record)

    def update_artifact(self, artifact_id, updates):
        if artifact_id in self.artifacts:
            self.artifacts[artifact_id].update(updates)

    def remove_artifact(self, artifact_id):
        self.artifacts.pop(artifact_id, None)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.artifacts.artifact_manager_service.MemoryService",
        FakeMemory,
    )
    return ArtifactManagerService(
        base_path=tmp_path / "artifacts",
        index_path=tmp_path / "memory" / "artifact_index.json",
    )


def create_report(manager, source):
    return manager.create_artifact(
        artifact_type="reports",
        content=f"Content from {source}",
        source=source,
    )


def test_artifact_links_are_persisted_idempotent_and_bidirectionally_discoverable(manager):
    source = create_report(manager, "voice transcript")
    target = create_report(manager, "voice summary")

    first = manager.link_artifacts(source["artifact_id"], target["artifact_id"], "summarizes")
    second = manager.link_artifacts(source["artifact_id"], target["artifact_id"], "summarizes")

    assert first["changed"] is True
    assert second["changed"] is False
    assert first["link"] == second["link"]

    outgoing = manager.get_artifact_links(source["artifact_id"])["links"]
    incoming = manager.get_artifact_links(target["artifact_id"])["links"]
    assert len(outgoing) == 1
    assert outgoing[0]["direction"] == "outgoing"
    assert outgoing[0]["artifact"]["artifact_id"] == target["artifact_id"]
    assert len(incoming) == 1
    assert incoming[0]["direction"] == "incoming"
    assert incoming[0]["artifact"]["artifact_id"] == source["artifact_id"]
    assert "file" not in incoming[0]["artifact"]


def test_artifact_links_reject_self_missing_and_archived_artifacts(manager):
    source = create_report(manager, "source")
    target = create_report(manager, "target")

    with pytest.raises(ValueError, match="cannot link to itself"):
        manager.link_artifacts(source["artifact_id"], source["artifact_id"])

    with pytest.raises(KeyError):
        manager.link_artifacts(source["artifact_id"], "missing-artifact")

    assert manager.archive_artifact(target["artifact_id"]) is True
    with pytest.raises(ValueError, match="Archived artifacts"):
        manager.link_artifacts(source["artifact_id"], target["artifact_id"])


def test_deleting_an_artifact_removes_inbound_relationships(manager):
    source = create_report(manager, "source")
    target = create_report(manager, "target")
    manager.link_artifacts(source["artifact_id"], target["artifact_id"], "derived_from")

    assert manager.delete_artifact(target["artifact_id"]) is True
    assert manager.get_artifact_links(source["artifact_id"])["links"] == []


def test_artifact_relationship_api_exposes_links_without_file_paths(manager, monkeypatch):
    source = create_report(manager, "source")
    target = create_report(manager, "target")
    monkeypatch.setattr(route, "_manager", lambda: manager)

    created = route.link_artifact(
        source["artifact_id"],
        route.ArtifactLinkRequest(
            target_artifact_id=target["artifact_id"],
            relation="derived_from",
        ),
    )
    assert created["success"] is True
    assert created["changed"] is True

    result = route.get_artifact_links(target["artifact_id"])
    assert result["success"] is True
    assert result["links"][0]["direction"] == "incoming"
    assert result["links"][0]["artifact"]["artifact_id"] == source["artifact_id"]

    with pytest.raises(HTTPException) as error:
        route.get_artifact_links("not-found")
    assert error.value.status_code == 404
