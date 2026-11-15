from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock
from typing import Any, Protocol


class MultiModelProvider(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        context: dict[str, Any],
        task_type: str,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    capabilities: frozenset[str]
    enabled: bool = True
    priority: int = 100


class MultiModelRegistry:
    """Thread-safe registry with explicit replacement and validated profiles."""

    _entries: dict[str, tuple[ModelProfile, MultiModelProvider]] = {}
    _lock = RLock()

    @classmethod
    def _validated_profile(cls, profile: ModelProfile) -> ModelProfile:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        if not isinstance(profile.model_id, str):
            raise ValueError("model_id must be a string containing 1 to 120 characters")
        model_id = profile.model_id.strip()
        if not model_id or len(model_id) > 120:
            raise ValueError("model_id must contain 1 to 120 characters")
        if (
            not isinstance(profile.provider, str)
            or not profile.provider.strip()
            or len(profile.provider.strip()) > 80
        ):
            raise ValueError("provider must contain 1 to 80 characters")
        if not isinstance(profile.capabilities, (set, frozenset)):
            raise ValueError("capabilities must be a set of non-empty strings")
        if not all(
            isinstance(value, str) and value.strip() and len(value.strip()) <= 80
            for value in profile.capabilities
        ):
            raise ValueError("capabilities must be a non-empty set of bounded strings")
        capabilities = frozenset(value.strip() for value in profile.capabilities)
        if not capabilities:
            raise ValueError("capabilities must be a non-empty set of bounded strings")
        if not isinstance(profile.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if isinstance(profile.priority, bool) or not isinstance(profile.priority, int):
            raise ValueError("priority must be an integer")

        return replace(
            profile,
            model_id=model_id,
            provider=profile.provider.strip(),
            capabilities=capabilities,
        )

    @classmethod
    def register(
        cls,
        profile: ModelProfile,
        provider: MultiModelProvider,
        *,
        replace_existing: bool = False,
    ) -> None:
        validated = cls._validated_profile(profile)
        if provider is None or not callable(getattr(provider, "generate", None)):
            raise ValueError("provider must implement generate")

        with cls._lock:
            if validated.model_id in cls._entries and not replace_existing:
                raise ValueError(f"model already registered: {validated.model_id}")
            cls._entries[validated.model_id] = (validated, provider)

    @classmethod
    def get(cls, model_id: str) -> tuple[ModelProfile, MultiModelProvider] | None:
        if not isinstance(model_id, str):
            return None
        with cls._lock:
            return cls._entries.get(model_id.strip())

    @classmethod
    def unregister(cls, model_id: str) -> bool:
        if not isinstance(model_id, str) or not model_id.strip():
            return False
        with cls._lock:
            return cls._entries.pop(model_id.strip(), None) is not None

    @classmethod
    def list(cls) -> list[ModelProfile]:
        with cls._lock:
            return sorted(
                (profile for profile, _ in cls._entries.values()),
                key=lambda profile: (profile.priority, profile.model_id),
            )

    @classmethod
    def eligible(
        cls,
        task_type: str,
    ) -> list[tuple[ModelProfile, MultiModelProvider]]:
        if not isinstance(task_type, str) or not task_type.strip():
            return []
        normalized_task = task_type.strip()
        with cls._lock:
            return [
                (profile, provider)
                for profile, provider in sorted(
                    cls._entries.values(),
                    key=lambda entry: (entry[0].priority, entry[0].model_id),
                )
                if profile.enabled
                and (
                    "general" in profile.capabilities
                    or normalized_task in profile.capabilities
                )
            ]

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._entries.clear()
