from pathlib import Path
from datetime import UTC, datetime
from app.services.persistence.atomic_json_store import AtomicJsonStore

class ResearchLibraryService:
    """Personal research library with bounded source records."""
    def __init__(self, path="memory/research_library.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": 1, "items": []})

    def get(self, research_id):
        if not isinstance(research_id, str) or not research_id.strip():
            raise ValueError("research_id is required")
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])
        return next((item for item in records if item.get("research_id") == research_id.strip()), None)

    def update(self, research_id, title=None, source=None, summary=None, project_id=None, tags=None):
        if not isinstance(research_id, str) or not research_id.strip():
            raise ValueError("research_id is required")
        if title is source is summary is project_id is tags is None:
            raise ValueError("at least one field must be supplied")
        if title is not None and (not isinstance(title, str) or not title.strip() or len(title.strip()) > 300):
            raise ValueError("title is invalid")
        if source is not None and (not isinstance(source, str) or not source.strip() or len(source.strip()) > 2000):
            raise ValueError("source is invalid")
        if summary is not None and len(str(summary)) > 10000:
            raise ValueError("summary is too long")
        if tags is not None and (not isinstance(tags, list) or len(tags) > 20):
            raise ValueError("tags are invalid")
        target = research_id.strip()
        def mutate(document):
            for item in document.setdefault("items", []):
                if item.get("research_id") != target:
                    continue
                if title is not None: item["title"] = title.strip()
                if source is not None: item["source"] = source.strip()
                if summary is not None: item["summary"] = str(summary)
                if project_id is not None: item["project_id"] = project_id
                if tags is not None: item["tags"] = [str(tag)[:64] for tag in tags]
                item["updated_at"] = datetime.now(UTC).isoformat()
                return dict(item)
            raise KeyError(target)
        return self.store.update(mutate, {"schema_version": 1, "items": []})

    def remove(self, research_id):
        if not isinstance(research_id, str) or not research_id.strip():
            raise ValueError("research_id is required")
        target = research_id.strip()
        def mutate(document):
            records = document.setdefault("items", [])
            before = len(records)
            records[:] = [item for item in records if item.get("research_id") != target]
            return before != len(records)
        return self.store.update(mutate, {"schema_version": 1, "items": []})

    def add(self, title, source, summary="", project_id=None, tags=None):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        if not isinstance(source, str) or not source.strip() or len(source) > 2000:
            raise ValueError("source is invalid")
        item={"research_id": datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"),"title":title.strip()[:300],"source":source.strip(),"summary":str(summary)[:10000],"project_id":project_id,"tags":[str(tag)[:64] for tag in (tags or [])[:20]],"created_at":datetime.now(UTC).isoformat(),"updated_at":datetime.now(UTC).isoformat()}
        def mutate(document):
            document.setdefault("items", []).append(item)
            document["items"]=document["items"][-1000:]
            return item
        return self.store.update(mutate, {"schema_version":1,"items":[]})

    def list_recent(self, limit=20):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
            raise ValueError("limit must be between 0 and 100")
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])
        return list(reversed(records[-limit:]))

    def tag_counts(self):
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])
        counts = {}
        for item in records:
            for tag in item.get("tags", []):
                key = str(tag)[:64]
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:100])

    def summary(self):
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])
        projects = {item.get("project_id") for item in records if item.get("project_id")}
        tags = {tag.casefold() for item in records for tag in item.get("tags", [])}
        return {"total": len(records), "linked_projects": len(projects), "unique_tags": len(tags)}

    def trend_analysis(self, limit: int = 1000):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 1000:
            raise ValueError("limit must be between 0 and 1000")
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])[-limit:]
        buckets = {}
        for item in records:
            created = item.get("created_at")
            bucket = created[:7] if isinstance(created, str) and len(created) >= 7 else "unknown"
            buckets[bucket] = buckets.get(bucket, 0) + 1
        return {
            "basis": "persisted research records only",
            "total_records": len(records),
            "periods": [
                {"period": period, "record_count": count}
                for period, count in sorted(buckets.items())
            ],
        }

    def knowledge_graph(self, limit: int = 1000):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 1000:
            raise ValueError("limit must be between 0 and 1000")
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])[-limit:]
        nodes = {}
        edges = set()
        for item in records:
            research_id = item.get("research_id")
            if not isinstance(research_id, str):
                continue
            nodes[research_id] = {"id": research_id, "type": "research", "title": item.get("title", "")}
            tags = sorted({str(tag).strip().casefold() for tag in item.get("tags", []) if str(tag).strip()})
            for tag in tags:
                tag_id = f"tag:{tag}"
                nodes[tag_id] = {"id": tag_id, "type": "tag", "label": tag}
                edges.add((research_id, tag_id, "tagged_with"))
        return {
            "basis": "persisted research records and tags only",
            "nodes": list(nodes.values()),
            "edges": [
                {"from": source, "to": target, "relation": relation}
                for source, target, relation in sorted(edges)
            ],
        }

    def export(self, limit=1000):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 1000:
            raise ValueError("limit must be between 0 and 1000")
        records = self.store.read({"schema_version": 1, "items": []}).get("items", [])
        items = [dict(item) for item in records[-limit:]]
        return {
            "schema_version": 1,
            "exported_count": len(items),
            "items": items,
        }

    def search(self, query, limit=50):
        terms=[term.casefold() for term in str(query).split() if term][:10]
        if not terms: return []
        records=self.store.read({"schema_version":1,"items":[]}).get("items",[])
        matches=[item for item in records if all(term in (" ".join([item.get("title",""),item.get("summary","")," ".join(item.get("tags",[]))])).casefold() for term in terms)]
        return matches[-max(0,min(int(limit),100)):][::-1]
