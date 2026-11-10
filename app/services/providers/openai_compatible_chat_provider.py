from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.services.identity.system_prompt_service import SystemPromptService
from app.services.conversation.context_budget_service import ContextBudgetService


class OpenAICompatibleChatProvider:

    """Explicitly configured HTTPS chat provider using the OpenAI-compatible API."""

    provider_scope = "external"
    MAX_INPUT_CHARS = 10_000
    MAX_HISTORY_MESSAGES = 12
    MAX_HISTORY_CHARS = 12_000
    MAX_OUTPUT_CHARS = 12_000

    def __init__(self, *, base_url=None, model=None, api_key=None, timeout=60):
        self.base_url = (
            base_url or os.getenv("LUMIRA_CLOUD_CHAT_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = model or os.getenv("LUMIRA_CLOUD_CHAT_MODEL", "")
        self.api_key = api_key or os.getenv("LUMIRA_CLOUD_CHAT_API_KEY", "")
        self.timeout = max(5, min(int(timeout), 120))
        parsed = urlparse(self.base_url)
        self.provider_scope = "local" if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"} else "external"
        try:
            parsed.port
        except ValueError:
            raise ValueError("Cloud chat provider URL contains an invalid port.") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Cloud chat provider requires an HTTPS endpoint without embedded credentials.")
        if not self.model.strip():
            raise ValueError("Cloud chat provider model is not configured.")
        if not self.api_key.strip():
            raise ValueError("Cloud chat provider API key is not configured.")

    @classmethod
    def _history(cls, messages):
        return ContextBudgetService.select_recent_history(
            messages,
            max_messages=cls.MAX_HISTORY_MESSAGES,
            max_chars=cls.MAX_HISTORY_CHARS,
        )

    def chat(self, message: str, history=None, context=None) -> str:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Message must not be empty.")
        if len(message) > self.MAX_INPUT_CHARS:
            raise ValueError("Message exceeds the cloud chat input limit.")

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
            "max_tokens": 1024,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.MAX_OUTPUT_CHARS * 4 + 1)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Cloud chat provider returned HTTP {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("Cloud chat provider is unavailable.") from None

        if len(raw) > self.MAX_OUTPUT_CHARS * 4:
            raise ValueError("Cloud chat response exceeded the response limit.")
        try:
            data = json.loads(raw.decode("utf-8"))
            choices = data.get("choices")
            content = (
                choices[0].get("message", {}).get("content")
                if isinstance(choices, list) and choices
                else None
            )
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, IndexError):
            raise ValueError("Cloud chat provider returned an invalid response.") from None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Cloud chat provider returned an empty response.")
        content = content.strip()
        if len(content) > self.MAX_OUTPUT_CHARS:
            raise ValueError("Cloud chat output exceeded the response limit.")
        return content
