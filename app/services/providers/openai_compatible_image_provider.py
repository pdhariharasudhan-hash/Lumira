from __future__ import annotations

import base64
import binascii
import json
import os
from urllib.parse import urlparse

import requests


class OpenAICompatibleImageProvider:
    """Bounded image-generation adapter for an OpenAI-compatible images API."""

    MAX_PROMPT_CHARS = 10_000
    MAX_RESPONSE_BYTES = 32_000_000
    MAX_IMAGE_BYTES = 20_000_000
    SUPPORTED_TYPES = {"image", "diagram", "blueprint", "schematic"}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 90,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LUMIRA_IMAGE_API_KEY", "")
        self.base_url = (base_url or os.getenv("LUMIRA_IMAGE_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("LUMIRA_IMAGE_MODEL", "gpt-image-1")
        self.timeout = max(5, min(int(timeout), 120))
        parsed_url = urlparse(self.base_url)
        try:
            parsed_url.port  # Validate malformed or out-of-range ports at startup.
        except ValueError:
            raise ValueError("Image base URL is invalid.") from None
        is_local_http = parsed_url.scheme == "http" and parsed_url.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed_url.scheme != "https" and not is_local_http:
            raise ValueError("Image base URL must use HTTPS unless it targets localhost.")
        if not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError("Image base URL is invalid.")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("Image model must contain 1 to 100 characters.")

    def generate(self, prompt: str, image_type: str) -> dict:
        if not self.api_key.strip():
            raise RuntimeError("Image API key is not configured.")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError("Image prompt is empty or exceeds the generation input limit.")
        if image_type not in self.SUPPORTED_TYPES:
            raise ValueError("Image type is not supported.")

        response = None
        try:
            response = requests.post(
                f"{self.base_url}/images/generations",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "prompt": prompt.strip(), "size": "1024x1024", "n": 1},
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
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Image service response exceeds the response size limit.")
                chunks.append(chunk)
        except ValueError:
            raise
        except requests.RequestException:
            raise RuntimeError("Image service request failed; check connectivity and provider configuration.") from None
        finally:
            if response is not None:
                response.close()

        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
            image_data = payload.get("data") if isinstance(payload, dict) else None
            encoded = image_data[0].get("b64_json") if isinstance(image_data, list) and image_data and isinstance(image_data[0], dict) else None
            if not isinstance(encoded, str) or not encoded:
                raise ValueError
            image_bytes = base64.b64decode(encoded, validate=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, binascii.Error, IndexError):
            raise ValueError("Image service returned an invalid or empty base64 image response.") from None

        if not image_bytes or len(image_bytes) > self.MAX_IMAGE_BYTES:
            raise ValueError("Generated image is empty or exceeds the image size limit.")
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = "png"
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            extension = "jpg"
        elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            extension = "webp"
        else:
            raise ValueError("Image service output does not match a supported image format.")
        return {"success": True, "content": image_bytes, "extension": extension}
