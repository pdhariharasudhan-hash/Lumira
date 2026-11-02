from app.services.knowledge.knowledge_library_service import KnowledgeLibraryService

class Notes:
    def note_summary(self): return {"total": 0}
    def recent_notes(self, limit): return []

class Research:
    def summary(self): return {"total": 0}
    def list_recent(self, limit): return []

class Search:
    def search_all(self, query):
        return {"items": [{"title": query}], "research": [{"title": query}], "projects": []}

def test_knowledge_search_reports_non_empty_categories():
    service = KnowledgeLibraryService(Notes(), Research(), Search())
    result = service.search("robot")
    assert result["categories"]["research"] == 1
