from __future__ import annotations

from datetime import UTC, datetime


class ProjectDocumentationService:
    """Creates a structured documentation draft from user-supplied project facts."""

    def generate(self, title: str, objective: str, components: list[str] | None = None, decisions: list[str] | None = None) -> dict:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
            raise ValueError("title must contain 1 to 300 characters")
        if not isinstance(objective, str) or not objective.strip() or len(objective.strip()) > 5000:
            raise ValueError("objective must contain 1 to 5000 characters")
        components, decisions = components or [], decisions or []
        return {
            "title": title.strip(),
            "generated_at": datetime.now(UTC).isoformat(),
            "sections": {
                "objective": objective.strip(),
                "components": components,
                "decisions": decisions,
                "build_notes": "",
                "test_results": "",
                "known_issues": "",
                "next_steps": [],
            },
            "status": "draft",
        }
