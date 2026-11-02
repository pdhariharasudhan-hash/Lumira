from app.services.research.research_library_service import ResearchLibraryService

def test_research_update_preserves_identity(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    item = service.add("Old", "https://example.com", tags=["old"])
    updated = service.update(item["research_id"], title="New", tags=["new"])
    assert updated["research_id"] == item["research_id"]
    assert updated["title"] == "New"
    assert updated["tags"] == ["new"]

def test_research_update_requires_change(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    item = service.add("Test", "https://example.com")
    try:
        service.update(item["research_id"])
        assert False
    except ValueError:
        assert True
