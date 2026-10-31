from pathlib import Path
from datetime import UTC, datetime
from app.services.persistence.atomic_json_store import AtomicJsonStore

class ResearchLibraryService:
    """Personal research library with bounded source records."""
    def __init__(self, path="memory/research_library.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": 1, "items": []})

    def add(self, title, source, summary="", project_id=None, tags=None):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        if not isinstance(source, str) or not source.strip() or len(source) > 2000:
            raise ValueError("source is invalid")
        item={"research_id": datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"),"title":title.strip()[:300],"source":source.strip(),"summary":str(summary)[:10000],"project_id":project_id,"tags":[str(tag)[:64] for tag in (tags or [])[:20]],"created_at":datetime.now(UTC).isoformat()}
        def mutate(document):
            document.setdefault("items", []).append(item)
            document["items"]=document["items"][-1000:]
            return item
        return self.store.update(mutate, {"schema_version":1,"items":[]})

    def search(self, query, limit=50):
        terms=[term.casefold() for term in str(query).split() if term][:10]
        if not terms: return []
        records=self.store.read({"schema_version":1,"items":[]}).get("items",[])
        matches=[item for item in records if all(term in (" ".join([item.get("title",""),item.get("summary","")," ".join(item.get("tags",[]))])).casefold() for term in terms)]
        return matches[-max(0,min(int(limit),100)):][::-1]
