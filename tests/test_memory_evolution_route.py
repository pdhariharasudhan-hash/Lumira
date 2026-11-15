import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.memory as memory_routes
from app.services.memory.memory_service import MemoryService


@pytest.fixture
def memory_client(tmp_path, monkeypatch):
    service = MemoryService(str(tmp_path / "memory.json"))
    monkeypatch.setattr(memory_routes, "memory_service", service)
    app = FastAPI()
    app.include_router(memory_routes.router)
    return TestClient(app), service


def test_memory_evolution_route_records_user_correction_provenance(memory_client):
    client, service = memory_client
    original = service.record_decision("Use keyword retrieval", reason="Current baseline")

    response = client.post(
        "/memory/evolve",
        json={
            "collection": "decisions",
            "record_id": original["decision_id"],
            "correction": {"decision": "Use relevance-ranked keyword retrieval"},
            "reason": "The original decision was too broad",
        },
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["decision"] == "Use relevance-ranked keyword retrieval"
    assert updated["superseded_record"]["decision"] == "Use keyword retrieval"
    assert updated["evolution_reason"] == "The original decision was too broad"
    assert updated["evolution_source"] == "user_api"
    assert service.get_all()["decisions"][0]["evolution_source"] == "user_api"


def test_memory_evolution_route_supports_controlled_forgetting(memory_client):
    client, service = memory_client
    decision = service.record_decision("Remember this only temporarily")

    response = client.post(
        "/memory/evolve",
        json={
            "collection": "decisions",
            "record_id": decision["decision_id"],
            "forget": True,
            "reason": "The user requested removal from active memory",
        },
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["archived"] is True
    assert updated["evolution_source"] == "user_api"
    assert updated["evolution_reason"] == "The user requested removal from active memory"
    assert service.get_all()["decisions"][0]["archived"] is True


@pytest.mark.parametrize(
    "action",
    [
        {},
        {"correction": {}},
        {"correction": {"decision": "Corrected"}, "forget": True},
    ],
)
def test_memory_evolution_route_requires_exactly_one_valid_action(memory_client, action):
    client, _ = memory_client
    response = client.post(
        "/memory/evolve",
        json={"collection": "decisions", "record_id": "missing", **action},
    )

    assert response.status_code == 422


def test_memory_evolution_route_rejects_identity_changes(memory_client):
    client, service = memory_client
    decision = service.record_decision("Keep identity stable")

    response = client.post(
        "/memory/evolve",
        json={
            "collection": "decisions",
            "record_id": decision["decision_id"],
            "correction": {"decision_id": "forged-id", "decision": "Changed"},
        },
    )

    assert response.status_code == 422
    assert service.get_all()["decisions"][0]["decision_id"] == decision["decision_id"]
