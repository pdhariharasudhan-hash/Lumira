from __future__ import annotations

import os
from urllib.parse import urlparse

import requests

from app.services.resources.resource_budget_service import ResourceBudgetService


class OpenAICompatibleSpeechProvider:
    """Bounded text-to-speech adapter for OpenAI-compatible audio APIs."""

    MAX_INPUT_CHARS = 20_000
    MAX_AUDIO_BYTES = 25_000_000
    SUPPORTED_LANGUAGES = {"en", "ta", "ta-en"}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LUMIRA_SPEECH_API_KEY", "")
        self.base_url = (base_url or os.getenv("LUMIRA_SPEECH_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("LUMIRA_SPEECH_MODEL", "tts-1")
        self.voice = voice or os.getenv("LUMIRA_SPEECH_VOICE", "alloy")
        self.timeout = max(5, min(int(timeout), 120))
        parsed_url = urlparse(self.base_url)
        try:
            parsed_url.port  # Validate malformed or out-of-range ports at startup.
        except ValueError:
            raise ValueError("Speech base URL is invalid.") from None
        is_local_http = parsed_url.scheme == "http" and parsed_url.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed_url.scheme != "https" and not is_local_http:
            raise ValueError("Speech base URL must use HTTPS unless it targets localhost.")
        if not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError("Speech base URL is invalid.")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("Speech model must contain 1 to 100 characters.")
        if not self.voice.strip() or len(self.voice) > 100:
            raise ValueError("Speech voice must contain 1 to 100 characters.")

    def synthesize(self, text: str, language: str) -> dict:
        if not self.api_key.strip():
            raise RuntimeError("Speech API key is not configured.")
        if not isinstance(text, str) or not text.strip() or len(text) > self.MAX_INPUT_CHARS:
            raise ValueError("Speech text is empty or exceeds the synthesis input limit.")
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError("Speech language must be en, ta, or ta-en.")

        # Speech synthesis is optional media work; avoid starting another request
        # when the host is already under resource pressure.
        try:
            guidance = ResourceBudgetService().execution_guidance()
        except Exception:
            guidance = {}
        if guidance.get("defer_optional_heavy_media_work") is True:
            raise RuntimeError(
                "Speech synthesis was deferred because available system memory is constrained."
            )

        response = None
        try:
            response = requests.post(
                f"{self.base_url}/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "voice": self.voice, "input": text.strip(), "response_format": "mp3"},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.MAX_AUDIO_BYTES:
                    raise ValueError("Synthesized audio exceeds the audio size limit.")
                chunks.append(chunk)
        except ValueError:
            raise
        except requests.RequestException:
            raise RuntimeError("Speech service request failed; check connectivity and provider configuration.") from None
        finally:
            if response is not None:
                response.close()

        content = b"".join(chunks)
        if not content:
            raise ValueError("Speech service returned empty audio.")
        if not content.startswith(b"ID3") and not (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0):
            raise ValueError("Speech service returned audio that is not a valid MP3 stream.")
        return {"success": True, "content": content, "extension": "mp3"}
