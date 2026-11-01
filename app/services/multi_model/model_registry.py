from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol

class MultiModelProvider(Protocol):
    def generate(self, *, prompt: str, context: dict[str, Any], task_type: str) -> dict[str, Any]: ...

@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    capabilities: frozenset[str]
    enabled: bool = True
    priority: int = 100

class MultiModelRegistry:
    _entries: dict[str, tuple[ModelProfile, MultiModelProvider]] = {}
    _lock = RLock()
    @classmethod
    def register(cls, profile: ModelProfile, provider: MultiModelProvider) -> None:
        if not profile.model_id.strip() or len(profile.model_id) > 120: raise ValueError("model_id must contain 1 to 120 characters")
        if provider is None or not callable(getattr(provider, "generate", None)): raise ValueError("provider must implement generate")
        with cls._lock: cls._entries[profile.model_id] = (profile, provider)
    @classmethod
    def unregister(cls, model_id: str) -> None:
        with cls._lock: cls._entries.pop(model_id, None)
    @classmethod
    def list(cls) -> list[ModelProfile]:
        with cls._lock: return sorted((p for p,_ in cls._entries.values()), key=lambda x:(x.priority,x.model_id))
    @classmethod
    def eligible(cls, task_type: str):
        with cls._lock:
            return [(p,w) for p,w in sorted(cls._entries.values(), key=lambda x:(x[0].priority,x[0].model_id)) if p.enabled and ("general" in p.capabilities or task_type in p.capabilities)]
    @classmethod
    def clear(cls) -> None:
        with cls._lock: cls._entries.clear()
