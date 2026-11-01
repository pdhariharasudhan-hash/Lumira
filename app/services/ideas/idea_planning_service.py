from __future__ import annotations

from app.services.ideas.text_idea_capture_service import TextIdeaCaptureService


class IdeaPlanningService:
    """Turns a captured personal idea into a deterministic editable plan."""

    def __init__(self, ideas: TextIdeaCaptureService | None = None):
        self.ideas = ideas or TextIdeaCaptureService()

    def create_plan(self, idea_id: str) -> dict:
        if not isinstance(idea_id, str) or not idea_id.strip() or len(idea_id) > 200:
            raise ValueError("idea_id must contain 1 to 200 characters")
        idea = next((x for x in self.ideas.list(limit=200) if x.get("idea_id") == idea_id.strip()), None)
        if idea is None:
            raise KeyError("idea not found")
        title = idea["title"]
        return {
            "idea_id": idea["idea_id"],
            "title": title,
            "project_id": idea.get("project_id"),
            "steps": [
                {"order": 1, "title": "Clarify objective", "status": "pending"},
                {"order": 2, "title": "Identify constraints", "status": "pending"},
                {"order": 3, "title": "Research requirements", "status": "pending"},
                {"order": 4, "title": "Build an MVP", "status": "pending"},
                {"order": 5, "title": "Test and review", "status": "pending"},
            ],
            "source_text": idea["raw_text"],
            "note": "This is a deterministic planning template; it does not claim feasibility without validation.",
        }
