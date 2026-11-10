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


def test_get_and_remove_research(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    item = service.add("Test", "https://example.com")
    assert service.get(item["research_id"])["title"] == "Test"
    assert service.remove(item["research_id"]) is True
    assert service.get(item["research_id"]) is None


def test_trends_and_graph_use_only_persisted_records_and_tags(tmp_path):
    service = ResearchLibraryService(tmp_path / "research.json")
    first = service.add("ESP32 guide", "https://example.com/esp32", tags=["ESP32", "iot"])
    second = service.add("Pi guide", "https://example.com/pi", tags=["iot", "linux"])

    trends = service.trend_analysis()
    graph = service.knowledge_graph()

    assert trends["total_records"] == 2
    assert sum(item["record_count"] for item in trends["periods"]) == 2
    assert {node["id"] for node in graph["nodes"]} >= {
        first["research_id"], second["research_id"], "tag:iot"
    }
    assert {
        (edge["from"], edge["to"], edge["relation"])
        for edge in graph["edges"]
    } >= {
        (first["research_id"], "tag:esp32", "tagged_with"),
        (second["research_id"], "tag:iot", "tagged_with"),
    }
