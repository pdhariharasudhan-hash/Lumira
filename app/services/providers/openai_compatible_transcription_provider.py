from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from app.services.resources.resource_budget_service import ResourceBudgetService


class OpenAICompatibleTranscriptionProvider:
    """Bounded audio transcription through an OpenAI-compatible API.

    Credentials are read from the local environment and are never included in
    exceptions or logs. The provider is opt-in and does not download a model.
    """

    MAX_AUDIO_BYTES = 25_000_000
    MAX_RESPONSE_BYTES = 1_000_000
    MAX_TRANSCRIPT_CHARS = 100_000
    SUPPORTED_EXTENSIONS = {"wav", "mp3", "m4a"}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LUMIRA_TRANSCRIPTION_API_KEY", "")
        self.base_url = (base_url or os.getenv("LUMIRA_TRANSCRIPTION_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("LUMIRA_TRANSCRIPTION_MODEL", "whisper-1")
        self.timeout = max(5, min(int(timeout), 120))
        parsed_url = urlparse(self.base_url)
        try:
            parsed_url.port  # Validate malformed or out-of-range ports at startup.
        except ValueError:
            raise ValueError("Transcription base URL is invalid.") from None
        is_local_http = parsed_url.scheme == "http" and parsed_url.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed_url.scheme != "https" and not is_local_http:
            raise ValueError("Transcription base URL must use HTTPS unless it targets localhost.")
        if not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError("Transcription base URL is invalid.")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("Transcription model must contain 1 to 100 characters.")

    def transcribe(self, audio_path: str) -> str:
        if not self.api_key.strip():
            raise RuntimeError("Transcription API key is not configured.")
        path = Path(audio_path)
        extension = path.suffix.removeprefix(".").lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError("Audio format is not supported for transcription.")
        if not path.is_file():
            raise ValueError("Audio file does not exist.")
        size = path.stat().st_size
        if size <= 0 or size > self.MAX_AUDIO_BYTES:
            raise ValueError("Audio file is empty or exceeds the transcription size limit.")

        # Transcription is optional media processing. Respect the same host
        # pressure policy used by image and speech generation.
        try:
            guidance = ResourceBudgetService().execution_guidance()
        except Exception:
            guidance = {}
        if guidance.get("defer_optional_heavy_media_work") is True:
            raise RuntimeError(
                "Transcription was deferred because available system memory is constrained."
            )

        response = None
        try:
            with path.open("rb") as audio_file:
                response = requests.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": self.model, "response_format": "json"},
                    files={"file": (path.name, audio_file, self._content_type(extension))},
                    timeout=self.timeout,
                    stream=True,
                )
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Transcription response exceeds the response size limit.")
                chunks.append(chunk)
        except requests.RequestException:
            raise RuntimeError("Transcription service request failed; check connectivity and provider configuration.") from None
        finally:
            if response is not None:
                response.close()

        try:
            payload: Any = json.loads(b"".join(chunks).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Transcription service returned an invalid response.") from None

        transcript = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Transcription service returned an empty transcript.")
        transcript = transcript.strip()
        if len(transcript) > self.MAX_TRANSCRIPT_CHARS:
            raise ValueError("Transcription output exceeds the transcript size limit.")
        return transcript

    @staticmethod
    def _content_type(extension: str) -> str:
        return {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4"}[extension]
