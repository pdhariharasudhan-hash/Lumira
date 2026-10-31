from app.services.notepad_service import NotepadService
from app.services.research.research_library_service import ResearchLibraryService
from app.services.search.unified_search_service import UnifiedSearchService

class KnowledgeLibraryService:
    """Single bounded entry point for the user's saved notes, research and indexed knowledge."""

    def __init__(self, notes=None, research=None, search=None):
        self.notes = notes or NotepadService()
        self.research = research or ResearchLibraryService()
        self.search_service = search or UnifiedSearchService()

    def overview(self):
        note_summary = self.notes.note_summary()
        research_summary = self.research.summary()
        return {
            "notes": note_summary,
            "research": research_summary,
            "total_saved_items": int(note_summary.get("total", 0)) + int(research_summary.get("total", 0)),
        }

    def recent(self, note_limit=10, research_limit=10):
        return {
            "notes": self.notes.recent_notes(note_limit),
            "research": self.research.list_recent(research_limit),
        }

    def digest(self, query, limit=10):
        result = self.search(query, limit)
        highlights = []
        for item in result.get("items", [])[:limit]:
            if not isinstance(item, dict):
                continue
            highlights.append({
                "title": str(item.get("title") or item.get("name") or item.get("summary") or "Untitled")[:300],
                "source": str(item.get("source") or item.get("type") or "knowledge")[:100],
            })
        return {
            "query": result.get("query", ""),
            "result_count": result.get("count", 0),
            "categories": result.get("categories", {}),
            "highlights": highlights,
        }

    def search(self, query, limit=50):
        query = str(query).strip()
        if not query:
            return {"query": "", "items": [], "count": 0}
        results = self.search_service.search_all(query)
        items = list(results.get("items", []))[:max(0, min(int(limit), 100))]
        return {
            "query": query,
            "items": items,
            "count": len(items),
            "categories": {
                key: len(value)
                for key, value in results.items()
                if key != "items" and isinstance(value, (list, dict)) and value
            },
        }
