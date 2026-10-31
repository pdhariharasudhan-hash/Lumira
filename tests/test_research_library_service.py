from app.services.research.research_library_service import ResearchLibraryService


def test_add_and_search_research(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    service.add("ESP32 guide", "https://example.com", "WiFi microcontroller", tags=["esp32", "iot"])
    results = service.search("esp32")
    assert len(results) == 1
    assert results[0]["title"] == "ESP32 guide"


def test_empty_research_query_returns_no_matches(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    assert service.search("") == []
