from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from threading import Lock
from urllib.parse import urlparse

from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.identity.system_prompt_service import SystemPromptService
from app.services.conversation.context_budget_service import ContextBudgetService


class OllamaChatProvider:
    provider_scope = "local"

    MAX_INPUT_CHARS = 10_000
    MAX_OUTPUT_CHARS = 12_000
    MAX_HISTORY_MESSAGES = 12
    MAX_HISTORY_CHARS = 12_000
    _request_lock = Lock()

    def __init__(self, *, base_url=None, model=None, timeout=90):
        self.base_url = (
            base_url or os.getenv("LUMIRA_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        ).rstrip("/")
        self.model = model or os.getenv(
            "LUMIRA_OLLAMA_CHAT_MODEL",
            os.getenv("LUMIRA_OLLAMA_MODEL", "qwen2.5-coder:3b"),
        )
        self.timeout = max(5, min(int(timeout), 120))
        parsed = urlparse(self.base_url)
        try:
            parsed.port
        except ValueError:
            raise ValueError("Local chat provider requires a valid local endpoint.") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Local chat provider must use a local HTTP endpoint without credentials.")

    @classmethod
    def _history(cls, messages):
        return ContextBudgetService.select_recent_history(
            messages,
            max_messages=cls.MAX_HISTORY_MESSAGES,
            max_chars=cls.MAX_HISTORY_CHARS,
        )

    def chat(self, message, history=None, context=None):
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Message must not be empty.")
        if len(message) > self.MAX_INPUT_CHARS:
            raise ValueError("Message exceeds the local chat input limit.")
        try:
            guidance = ResourceBudgetService().execution_guidance()
        except Exception:
            guidance = {}
        if guidance.get("resource_pressure") == "critical":
            raise RuntimeError("Local conversation is deferred because system memory pressure is critical.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SystemPromptService().render()},
                *([{"role": "system", "content": context.strip()[:4000]}]
                  if isinstance(context, str) and context.strip() else []),
                *self._history(history),
                {"role": "user", "content": message.strip()},
            ],
            "temperature": 0.4,
            "max_tokens": 768 if guidance.get("resource_profile") == "low_memory" else 1536,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if not self._request_lock.acquire(timeout=1):
            raise RuntimeError("Another local model request is active; conversation was deferred to protect RAM.")
        try:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(self.MAX_OUTPUT_CHARS * 4 + 1)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Local conversation endpoint returned HTTP {exc.code}.") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise RuntimeError("Local Ollama conversation endpoint is unavailable.") from None
        finally:
            self._request_lock.release()

        if len(raw) > self.MAX_OUTPUT_CHARS * 4:
            raise ValueError("Local chat response exceeded the response limit.")
        try:
            data = json.loads(raw.decode("utf-8"))
            choices = data.get("choices")
            result = (
                choices[0].get("message", {}).get("content")
                if isinstance(choices, list) and choices
                else None
            )
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, IndexError):
            raise ValueError("Local Ollama endpoint returned an invalid response.") from None
        if not isinstance(result, str) or not result.strip():
            raise ValueError("Local Ollama endpoint returned an empty response.")
        result = result.strip()
        if len(result) > self.MAX_OUTPUT_CHARS:
            raise ValueError("Local chat output exceeded the response limit.")
        return result
