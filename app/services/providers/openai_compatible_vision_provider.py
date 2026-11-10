from __future__ import annotations

import base64
import json
import os
from urllib.parse import urlparse

import requests


class OpenAICompatibleVisionProvider:

    """Bounded OpenAI-compatible vision adapter for image description and OCR-like analysis."""

    provider_scope = "external"
    MAX_PROMPT_CHARS = 4_000
    MAX_IMAGE_BYTES = 10_000_000
    MAX_RESPONSE_BYTES = 1_000_000

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, timeout: int = 45) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LUMIRA_VISION_API_KEY", "")
        self.base_url = (base_url or os.getenv("LUMIRA_VISION_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("LUMIRA_VISION_MODEL", "gpt-4o-mini")
        self.timeout = max(5, min(int(timeout), 90))
        parsed = urlparse(self.base_url)
        self.provider_scope = "local" if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"} else "external"
        try:
            parsed.port  # Validate malformed or out-of-range ports at startup.
        except ValueError:
            raise ValueError("Vision base URL is invalid.") from None
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not local_http:
            raise ValueError("Vision base URL must use HTTPS unless it targets localhost.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Vision base URL is invalid.")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("Vision model must contain 1 to 100 characters.")

    @staticmethod
    def _image_mime(data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        raise ValueError("Image must be a valid PNG, JPEG, or WebP file.")

    def analyze(self, image_bytes: bytes, prompt: str = "Describe this image and extract any readable text.") -> dict:
        if not self.api_key.strip():
            raise RuntimeError("Vision API key is not configured.")
        if not isinstance(image_bytes, bytes) or not image_bytes or len(image_bytes) > self.MAX_IMAGE_BYTES:
            raise ValueError("Image is empty or exceeds the 10 MB limit.")
        mime = self._image_mime(image_bytes)
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError("Analysis prompt is empty or exceeds the input limit.")
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        response = None
        chunks: list[bytes] = []
        total = 0
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "max_tokens": 1200, "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt.strip()},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]}]},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=32 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Vision service response exceeds the size limit.")
                chunks.append(chunk)
        except ValueError:
            raise
        except requests.RequestException:
            raise RuntimeError("Vision service request failed; check connectivity and provider configuration.") from None
        finally:
            if response is not None:
                response.close()
        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise ValueError("Vision service returned an invalid response.") from None
        if not isinstance(content, str) or not content.strip() or len(content) > 20_000:
            raise ValueError("Vision service returned an empty or oversized analysis.")
        return {"success": True, "description": content.strip(), "model": self.model}
