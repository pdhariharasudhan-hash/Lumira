from app.services.knowledge.knowledge_library_service import KnowledgeLibraryService

class Search:
    def search_all(self, query):
        return {"items": [{"title": "Robot idea", "type": "note"}], "notes": [{"id": "n1"}]}

class Notes:
    def note_summary(self): return {"total": 0}
    def recent_notes(self, limit): return []

class Research:
    def summary(self): return {"total": 0}
    def list_recent(self, limit): return []

def test_digest_returns_bounded_highlights():
    service = KnowledgeLibraryService(Notes(), Research(), Search())
    digest = service.digest("robot", 10)
    assert digest["result_count"] == 1
    assert digest["highlights"][0]["title"] == "Robot idea"
