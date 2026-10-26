from threading import RLock
from typing import Any


PROVIDER_STATUS_NAMES = (
    "summarization",
    "transcription",
    "speech_synthesis",
    "image_generation",
    "image_understanding",
    "research",
    "wake_word",
    "device_transport",
)


class ProviderRegistry:
    """Thread-safe in-process registry for explicitly configured providers."""

    _providers: dict[str, Any] = {}
    _lock = RLock()

    @classmethod
    def register(cls, name: str, provider: Any) -> None:
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Provider name must contain 1 to 80 characters")
        if provider is None:
            raise ValueError("Provider cannot be None")
        with cls._lock:
            cls._providers[name.strip().lower()] = provider

    @classmethod
    def get(cls, name: str) -> Any | None:
        with cls._lock:
            return cls._providers.get(name.strip().lower()) if isinstance(name, str) else None

    @classmethod
    def unregister(cls, name: str) -> None:
        with cls._lock:
            cls._providers.pop(name.strip().lower(), None)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._providers.clear()
