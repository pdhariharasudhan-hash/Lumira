import json

from app.services.search.unified_search_service import UnifiedSearchService


def test_unified_search_matches_natural_language_across_projects_files_and_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    version = tmp_path / "generated" / "expense_api" / "v1"
    version.mkdir(parents=True)
    (version / "metadata.json").write_text(json.dumps({"idea": "expense API", "version": "v1"}), encoding="utf-8")
    (version / "main.py").write_text("# expense API\napp = True\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "expense.md").write_text("Expense API implementation guide", encoding="utf-8")

    results = UnifiedSearchService().search_all("Find everything related to my expense API")
    assert results["projects"][0]["project"] == "expense_api"
    assert results["project_versions"][0]["version"] == "v1"
    assert results["code"][0]["path"].endswith("main.py")
    assert results["documentation"][0]["path"].endswith("expense.md")


def test_empty_unified_search_does_not_return_memory_dump(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = UnifiedSearchService().search_all("  ")
    assert all(value == [] for value in results.values())


def test_unified_search_finds_text_artifact_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = UnifiedSearchService()
    artifact = service.artifacts.create_artifact("transcripts", "Expense API meeting notes", "voice", "txt")
    results = service.search_all("Find my expense API")
    assert any(item["artifact_id"] == artifact["artifact_id"] for item in results["voice_ideas"])


def test_search_api_never_returns_internal_artifact_paths(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.chdir(tmp_path)
    service = UnifiedSearchService()
    artifact = service.artifacts.create_artifact(
        "transcripts", "Public meeting notes", "voice", "txt"
    )
    response = TestClient(app).get("/search", params={"q": "Public meeting"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    serialized = json.dumps(body)
    assert artifact["file"] not in serialized
    assert '"file":' not in serialized


def test_search_api_treats_whitespace_only_query_as_empty(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.chdir(tmp_path)
    response = TestClient(app).get("/search", params={"q": "   "})
    assert response.status_code == 200
    assert response.json() == {"success": True, "query": "", "results": []}


def test_unified_artifact_search_does_not_match_or_return_internal_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = UnifiedSearchService()
    service.artifacts.get_all_artifacts = lambda: [{
        "artifact_id": "public-artifact",
        "type": "transcripts",
        "source": "voice capture",
        "timestamp": "2026-10-25T00:00:00+00:00",
        "file": "private-secret-folder/hidden.txt",
    }]
    service.artifacts.get_artifact_path = lambda artifact_id: None

    private_path_match = service.search_artifacts("private-secret-folder")
    public_metadata_match = service.search_artifacts("voice capture")

    assert private_path_match == []
    assert len(public_metadata_match) == 1
    assert public_metadata_match[0]["artifact_id"] == "public-artifact"
    assert "file" not in public_metadata_match[0]



def test_memory_search_filters_matching_records_and_links_safe_artifact_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = UnifiedSearchService()
    artifact = service.artifacts.create_artifact(
        "transcripts",
        "Private transcript body stays in the artifact store.",
        "voice capture",
        "txt",
    )
    service.memory.record_experience(
        experience_type="workflow",
        summary="unique phrase memory recovery",
        outcome="The voice idea was saved.",
        artifact_ids=[artifact["artifact_id"]],
        lessons=["Use the saved transcript when retrying memory persistence."],
        verified=False,
    )
    service.memory.record_experience(
        experience_type="workflow",
        summary="Unrelated memory entry",
        outcome="Different subject",
        artifact_ids=[],
        lessons=[],
        verified=False,
    )

    result = service.search_memory("unique phrase memory recovery")

    assert len(result["experiences"]) == 1
    record = result["experiences"][0]
    assert record["summary"] == "unique phrase memory recovery"
    assert record["related_artifacts"] == [{
        "artifact_id": artifact["artifact_id"],
        "type": "transcripts",
        "source": "voice capture",
        "timestamp": artifact["timestamp"],
    }]
    assert "file" not in record["related_artifacts"][0]
    assert "Private transcript body" not in json.dumps(result)
