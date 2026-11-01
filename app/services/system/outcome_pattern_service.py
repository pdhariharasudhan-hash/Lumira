from __future__ import annotations

from collections import Counter


class OutcomePatternService:
    """Derive deterministic, project-scoped patterns from recorded experiences."""

    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def summary(self, project_id=None, limit=100):
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        limit = max(1, min(limit, 500))
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        data = memory._read_cognitive_memory()
        experiences = data.get("experiences", []) if isinstance(data, dict) else []
        experiences = [
            item for item in experiences
            if isinstance(item, dict)
            and not item.get("archived")
            and (not project_id or item.get("project_id") == project_id)
        ][-limit:]
        successes = [item for item in experiences if item.get("type", item.get("outcome")) == "success"]
        failures = [item for item in experiences if item.get("type", item.get("outcome")) == "failure"]
        verified = [item for item in experiences if item.get("verified") is True]
        pattern = (
            "failure_trend" if len(failures) > len(successes)
            else "success_trend" if successes
            else "insufficient_data"
        )
        lessons = []
        for item in verified:
            for lesson in item.get("lessons", []):
                if isinstance(lesson, str) and lesson.strip() and lesson not in lessons:
                    lessons.append(lesson)
        source_counts = Counter(
            str(item.get("source_run") or "unspecified")
            for item in experiences
            if item.get("type") == "failure"
        )
        repeated_failure_sources = [
            {"source_run": key, "count": count}
            for key, count in source_counts.items()
            if key != "unspecified" and count > 1
        ][:20]
        sample_count = len(experiences)
        return {
            "success": True,
            "pattern": pattern,
            "samples": sample_count,
            "successes": len(successes),
            "failures": len(failures),
            "verified_samples": len(verified),
            "success_rate": round(len(successes) / sample_count, 3) if sample_count else None,
            "lessons": lessons[:50],
            "repeated_failure_sources": repeated_failure_sources,
        }
