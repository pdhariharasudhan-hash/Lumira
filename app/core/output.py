"""Shared response metadata for text, structured, and media outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_MEDIA_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
}
_MEDIA_ARTIFACT_TYPES = {"images": "image", "video": "video", "audio": "audio"}


def _artifact_output(value: Mapping[str, Any]) -> dict[str, Any] | None:
    artifact_id = value.get("artifact_id")
    artifact_type = value.get("type")
    extension = str(value.get("extension", "")).lower().lstrip(".")
    output_type = _MEDIA_ARTIFACT_TYPES.get(str(artifact_type))
    mime = _MEDIA_MIME_TYPES.get(extension)
    if not isinstance(artifact_id, str) or not artifact_id or not output_type or not mime:
        return None
    return {
        "type": output_type,
        "mime": mime,
        "url": f"/artifacts/{artifact_id}/content",
        "artifact_id": artifact_id,
    }


def _find_media(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        output = _artifact_output(value)
        if output:
            return output
        for child in value.values():
            output = _find_media(child)
            if output:
                return output
    elif isinstance(value, list):
        for child in value:
            output = _find_media(child)
            if output:
                return output
    return None


def annotate_json_payload(payload: Any) -> Any:
    """Add non-breaking type/mime metadata to a JSON API payload."""
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    media = _find_media(result)
    message = result.get("message")
    if media:
        output = media
    elif isinstance(message, str) and message.strip():
        output = {"type": "text", "mime": "text/plain", "content": message}
    else:
        output = {"type": "json", "mime": "application/json"}
    result.setdefault("type", output["type"])
    result.setdefault("mime", output["mime"])
    result.setdefault("output", output)
    return result
