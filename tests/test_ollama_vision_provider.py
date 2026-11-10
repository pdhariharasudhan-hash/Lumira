import base64
import io
import json
from unittest.mock import Mock, patch

import pytest

from app.services.providers.ollama_vision_provider import OllamaVisionProvider


PNG = b"\x89PNG\r\n\x1a\n" + b"test-image"


def test_ollama_vision_uses_generate_endpoint_and_persists_valid_description():
    opener = Mock()
    opener.open.return_value = io.BytesIO(
        json.dumps({"response": "A purple geometric object.", "done": True}).encode()
    )
    with patch(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
        return_value=opener,
    ) as build_opener:
        result = OllamaVisionProvider().analyze(PNG, "Describe the object.")

    assert result == {
        "success": True,
        "description": "A purple geometric object.",
        "model": "moondream",
    }
    build_opener.assert_called_once()
    request = opener.open.call_args.args[0]
    assert request.full_url.endswith("/api/generate")
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "moondream"
    assert payload["prompt"].endswith("User request: Describe the object.")
    assert payload["images"] == [base64.b64encode(PNG).decode("ascii")]
    assert payload["stream"] is False
    assert payload["keep_alive"] == "5m"


def test_ollama_vision_rejects_empty_model_response():
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps({"response": ""}).encode())
    with patch(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
        return_value=opener,
    ):
        with pytest.raises(ValueError, match="empty or oversized"):
            OllamaVisionProvider().analyze(PNG)


def test_ollama_vision_rejects_invalid_image_before_network_call():
    with patch(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener"
    ) as build_opener:
        with pytest.raises(ValueError, match="valid PNG"):
            OllamaVisionProvider().analyze(b"not-an-image")
    build_opener.assert_not_called()
