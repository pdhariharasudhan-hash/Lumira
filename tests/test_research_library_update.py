from app.services.research.research_library_service import ResearchLibraryService

def test_update_preserves_research_identity(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    item = service.add("Old title", "https://example.com")
    updated = service.update(item["research_id"], title="New title", tags=["robotics"])
    assert updated["research_id"] == item["research_id"]
    assert updated["title"] == "New title"
    assert updated["tags"] == ["robotics"]
    assert updated["updated_at"]
