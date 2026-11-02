from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


class ElectronicsAssistantService:
    """Deterministic planning aid for the user's electronics and invention projects."""

    CATEGORIES = {"robotics", "microcontroller", "iot", "power", "pcb", "sensor", "audio", "other"}

    def create_plan(self, title: str, category: str, objective: str, components: list[str] | None = None) -> dict:
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
            raise ValueError("title must contain 1 to 300 characters")
        if category not in self.CATEGORIES:
            raise ValueError("unsupported electronics category")
        if not isinstance(objective, str) or not objective.strip() or len(objective.strip()) > 5000:
            raise ValueError("objective must contain 1 to 5000 characters")
        components = components or []
        if not isinstance(components, list) or len(components) > 100 or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in components):
            raise ValueError("components must contain at most 100 valid names")
        stages = ["define requirements", "research constraints", "select components", "design interfaces", "build prototype", "test and document"]
        return {
            "plan_id": str(uuid4()), "title": title.strip(), "category": category,
            "objective": objective.strip(), "components": [item.strip() for item in components],
            "stages": stages, "status": "planned", "created_at": datetime.now(UTC).isoformat(),
            "safety_note": "Validate voltage, current, thermal limits and manufacturer documentation before physical construction.",
        }

    def bom_template(self, components: list[str]) -> list[dict]:
        if not isinstance(components, list) or len(components) > 100:
            raise ValueError("components must contain at most 100 entries")
        return [{"component": item.strip(), "quantity": 1, "specification": "", "source": "", "status": "to_verify"} for item in components if isinstance(item, str) and item.strip()]
