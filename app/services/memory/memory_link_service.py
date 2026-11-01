from __future__ import annotations

from collections import deque
from typing import Any

from app.services.memory.memory_service import MemoryService, MemoryValidationError


class MemoryLinkService:
    """Personal memory relationship graph built on Lumira's durable memory links."""

    MAX_RESULTS = 100
    MAX_DEPTH = 5

    def __init__(self, memory: MemoryService | None = None):
        self.memory = memory or MemoryService()

    @staticmethod
    def _text(value: Any, name: str, limit: int = 200) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise MemoryValidationError(f"{name} must contain 1 to {limit} characters")
        return value.strip()

    def create(self, source_id: str, target_id: str, relation: str) -> dict:
        source_id = self._text(source_id, "source_id")
        target_id = self._text(target_id, "target_id")
        relation = self._text(relation, "relation", 100)
        if source_id == target_id:
            raise MemoryValidationError("a memory item cannot link to itself")
        existing = self.list(source_id)
        if any(item.get("target_id") == target_id and item.get("relation") == relation for item in existing):
            return {"source_id": source_id, "target_id": target_id, "relation": relation, "duplicate": True}
        record = self.memory.add_memory_link(source_id, target_id, relation)
        return {**record, "duplicate": False}

    def list(self, memory_id: str | None = None, limit: int = MAX_RESULTS) -> list[dict]:
        if not 0 <= limit <= self.MAX_RESULTS:
            raise MemoryValidationError(f"limit must be between 0 and {self.MAX_RESULTS}")
        if memory_id is not None:
            memory_id = self._text(memory_id, "memory_id")
        records = self.memory.get_all().get("memory_links", [])
        links = [
            dict(item) for item in records
            if isinstance(item, dict)
            and (memory_id is None or item.get("source_id") == memory_id or item.get("target_id") == memory_id)
        ]
        return links[-limit:] if limit else []

    def related(self, memory_id: str, depth: int = 1, limit: int = MAX_RESULTS) -> dict:
        memory_id = self._text(memory_id, "memory_id")
        if not 1 <= depth <= self.MAX_DEPTH:
            raise MemoryValidationError(f"depth must be between 1 and {self.MAX_DEPTH}")
        if not 1 <= limit <= self.MAX_RESULTS:
            raise MemoryValidationError(f"limit must be between 1 and {self.MAX_RESULTS}")
        links = self.list(limit=self.MAX_RESULTS)
        adjacency: dict[str, list[dict]] = {}
        for link in links:
            adjacency.setdefault(link.get("source_id", ""), []).append(link)
            reverse = dict(link)
            reverse["source_id"], reverse["target_id"] = link.get("target_id"), link.get("source_id")
            reverse["direction"] = "reverse"
            adjacency.setdefault(reverse.get("source_id", ""), []).append(reverse)

        seen = {memory_id}
        queue = deque([(memory_id, 0)])
        results = []
        while queue and len(results) < limit:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for link in adjacency.get(current, []):
                target = link.get("target_id")
                if not isinstance(target, str) or target in seen:
                    continue
                seen.add(target)
                results.append({**link, "depth": current_depth + 1})
                queue.append((target, current_depth + 1))
                if len(results) >= limit:
                    break
        return {"memory_id": memory_id, "depth": depth, "links": results}
