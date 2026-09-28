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
