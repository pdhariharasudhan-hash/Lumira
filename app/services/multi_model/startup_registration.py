"""Register explicitly configured chat models without network calls at startup."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.brain.brain_config import BrainConfig
from app.services.multi_model.model_registry import ModelProfile, MultiModelRegistry


class ChatProviderAdapter:
    """Adapt Lumira chat providers to the bounded multi-model interface."""

    def __init__(self, provider: Any):
        self.provider = provider
        self.provider_scope = getattr(provider, "provider_scope", "external")

    def generate(self, *, prompt: str, context: dict[str, Any], task_type: str) -> dict[str, Any]:
        history = context.get("history", []) if isinstance(context, dict) else []
        safe_context = {
            key: value for key, value in (context or {}).items()
            if key != "history"
        }
        context_text = json.dumps(
            {"task_type": task_type, "context": safe_context},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        content = self.provider.chat(
            prompt,
            history=history,
            context=context_text if len(context_text) <= 4000 else context_text[:4000],
        )
        if not isinstance(content, str) or not content.strip():
            return {"success": False, "content": ""}
        return {"success": True, "content": content.strip()}


def register_configured_chat_models(config: BrainConfig | None = None) -> dict:
    """Register local/cloud adapters only when explicitly enabled by configuration."""
    settings = config or BrainConfig()
    registered = []
    unavailable = []

    try:
        if settings.get_bool("LUMIRA_OLLAMA_CHAT_ENABLED", default=False):
            from app.services.providers.ollama_chat_provider import OllamaChatProvider

            provider = OllamaChatProvider(
                base_url=settings.get("LUMIRA_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
                model=settings.get("LUMIRA_OLLAMA_CHAT_MODEL", settings.get("LUMIRA_OLLAMA_MODEL", "qwen2.5-coder:3b")),
            )
            model_id = str(settings.get("LUMIRA_OLLAMA_CHAT_MODEL", settings.get("LUMIRA_OLLAMA_MODEL", "qwen2.5-coder:3b"))).strip()
            MultiModelRegistry.register(
                ModelProfile(
                    model_id=model_id,
                    provider="ollama",
                    capabilities=frozenset({"general", "reply", "coding", "research", "planning"}),
                    enabled=True,
                    priority=10,
                ),
                ChatProviderAdapter(provider),
                replace_existing=True,
            )
            registered.append(model_id)
    except Exception as exc:
        unavailable.append({"provider": "ollama", "reason": type(exc).__name__})
        logging.getLogger(__name__).warning("Local chat model registration unavailable (%s).", type(exc).__name__)

    try:
        if settings.get_bool("LUMIRA_CLOUD_CHAT_ENABLED", default=False):
            from app.services.providers.openai_compatible_chat_provider import OpenAICompatibleChatProvider

            provider = OpenAICompatibleChatProvider(
                base_url=settings.get("LUMIRA_CLOUD_CHAT_BASE_URL", "https://api.openai.com/v1"),
                model=settings.get("LUMIRA_CLOUD_CHAT_MODEL", ""),
                api_key=settings.get_secret("LUMIRA_CLOUD_CHAT_API_KEY") or "",
            )
            model_id = str(settings.get("LUMIRA_CLOUD_CHAT_MODEL", "")).strip()
            MultiModelRegistry.register(
                ModelProfile(
                    model_id=model_id,
                    provider="openai_compatible",
                    capabilities=frozenset({"general", "reply", "coding", "research", "planning"}),
                    enabled=True,
                    priority=50,
                ),
                ChatProviderAdapter(provider),
                replace_existing=True,
            )
            registered.append(model_id)
    except Exception as exc:
        unavailable.append({"provider": "cloud", "reason": type(exc).__name__})
        logging.getLogger(__name__).warning("Cloud chat model registration unavailable (%s).", type(exc).__name__)

    return {
        "success": True,
        "registered_models": registered,
        "unavailable_providers": unavailable,
        "network_calls_during_startup": 0,
    }
