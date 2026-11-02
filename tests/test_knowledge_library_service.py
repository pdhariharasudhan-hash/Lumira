from app.services.knowledge.knowledge_library_service import KnowledgeLibraryService

class Notes:
    def note_summary(self):
        return {"total": 2, "with_content": 1}
    def recent_notes(self, limit):
        return [{"title": "robot"}][:limit]

class Research:
    def summary(self):
        return {"total": 3, "linked_projects": 1, "unique_tags": 2}
    def list_recent(self, limit):
        return [{"title": "ESP32"}][:limit]

class Search:
    def search_all(self, query):
        return {"items": [{"source": "notes", "title": query}]}

def test_overview_combines_saved_knowledge():
    service = KnowledgeLibraryService(Notes(), Research(), Search())
    assert service.overview()["total_saved_items"] == 5

def test_search_is_bounded_and_empty_query_is_safe():
    service = KnowledgeLibraryService(Notes(), Research(), Search())
    assert service.search("")["items"] == []
    assert service.search("robot", 1)["count"] == 1
