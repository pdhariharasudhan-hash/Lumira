from __future__ import annotations

from app.services.research.research_library_service import ResearchLibraryService


class ResearchComparisonService:
    """Compare selected saved research records without inventing source facts."""

    def __init__(self, library: ResearchLibraryService | None = None):
        self.library = library or ResearchLibraryService()

    def compare(self, research_ids: list[str]) -> dict:
        if not isinstance(research_ids, list) or not 2 <= len(research_ids) <= 10:
            raise ValueError("provide between 2 and 10 research IDs")
        if len(set(research_ids)) != len(research_ids):
            raise ValueError("research IDs must be unique")
        records = []
        missing = []
        for research_id in research_ids:
            if not isinstance(research_id, str) or not research_id.strip() or len(research_id) > 200:
                raise ValueError("each research ID must contain 1 to 200 characters")
            item = self.library.get(research_id.strip())
            if item is None:
                missing.append(research_id.strip())
            else:
                records.append(item)
        return {
            "requested_count": len(research_ids),
            "found_count": len(records),
            "missing_ids": missing,
            "items": [{
                "research_id": item.get("research_id"),
                "title": item.get("title"),
                "source": item.get("source"),
                "summary": item.get("summary"),
                "project_id": item.get("project_id"),
                "tags": item.get("tags", []),
            } for item in records],
            "note": "Comparison presents saved source records and does not fabricate a recommendation.",
        }
