from app.services.memory.memory_service import MemoryService
from app.services.notepad_service import NotepadService

class PersonalContextService:
    """Read-only personal context assembled from existing Lumira stores."""
    def __init__(self, memory=None, notes=None):
        self.memory = memory or MemoryService()
        self.notes = notes or NotepadService()

    def snapshot(self, query="", note_limit=10):
        query = str(query).strip()
        data = self.memory.get_all()
        experiences = data.get("experiences", []) if isinstance(data, dict) else []
        if query:
            needle = query.casefold()
            experiences = [item for item in experiences if needle in str(item).casefold()]
        notes = self.notes.recent_notes(note_limit)
        return {
            "query": query,
            "experience_count": len(experiences),
            "experiences": experiences[-20:],
            "notes": notes,
        }
