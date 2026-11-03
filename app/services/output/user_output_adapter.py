"""User Output Adapter.

Capabilities return structured dictionaries (JSON) internally. This module is the
single boundary that turns those dictionaries into what the user should actually
see: a human-readable ``message`` plus renderable ``attachments`` (images, audio,
video, PDFs, files). Raw JSON stays available under ``result`` for developer/API
use, but the chat UI should render ``message`` and ``attachments`` first.

Pure Python: no FastAPI or service imports, so it is trivial to unit test.
"""

from __future__ import annotations

import json
import re
from typing import Any

# artifact type (as stored by ArtifactService) -> how the UI should render it
_KIND_BY_TYPE = {
    "images": "image", "image": "image", "generated_images": "image",
    "audio": "audio", "voice": "audio", "recordings": "audio",
    "video": "video", "videos": "video",
    "pdf": "pdf", "pdfs": "pdf",
    "transcripts": "text", "summaries": "text",
    "reports": "document", "documents": "document",
    "code": "code", "source_code": "code",
    "exports": "file", "generated_files": "file",
    "diagrams": "image", "schematics": "image", "blueprints": "image",
}

_CODE_EXTENSIONS = {"py", "js", "jsx", "ts", "tsx", "css", "html", "json", "sh", "ps1", "bat", "c", "cpp", "h", "hpp", "java", "go", "rs", "sql", "yaml", "yml", "toml"}

_MESSAGE_KEYS = ("message", "summary", "response", "reply", "text", "answer", "description")
_MAX_DEPTH = 6
_MAX_ATTACHMENTS = 12


def _humanize(name: str) -> str:
    return str(name or "result").replace("_", " ").strip().capitalize()


def _first_text(data: dict) -> str | None:
    for key in _MESSAGE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _explicitly_requests_json(prompt: str | None) -> bool:
    if not isinstance(prompt, str) or not re.search(r"\bjson\b", prompt, re.IGNORECASE):
        return False
    if re.search(
        r"\b(?:no|not|never|hide|avoid|without|don't|do not)\b[^.!?]{0,40}\bjson\b",
        prompt,
        re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(
            r"\b(?:as|in|format(?:ted)? as|return|respond(?: with)?|output|show|display|give|provide|print|convert|serialize|want|need|generate)\b[^.!?]{0,40}\bjson\b"
            r"|\bjson\b[^.!?]{0,24}\b(?:format|response|output|object|schema)\b",
            prompt,
            re.IGNORECASE,
        )
    )


def _normalize_text(value: str, *, allow_json: bool = False, depth: int = 0) -> str:
    text = value.strip()
    if not text:
        return ""
    candidate = text
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```json", "```"} and lines[-1].strip() == "```":
            candidate = " ".join(lines[1:-1]).strip()
    elif "```json" in candidate.lower():
        start = candidate.lower().find("```json") + len("```json")
        end = candidate.find("```", start)
        if end >= 0:
            candidate = candidate[start:end].strip()
    if allow_json or depth >= 4 or not candidate or candidate[0] not in "{[":
        return text
    try:
        parsed = json.loads(candidate)
    except (TypeError, ValueError):
        return text
    if isinstance(parsed, dict):
        nested = _first_text(parsed)
        if nested and nested != text:
            return _normalize_text(nested, depth=depth + 1)
    return (
        "I received structured data, but couldn't turn it into a readable answer. "
        "Please tell me what you'd like to do with it."
    )


def collect_attachments(value: Any, _depth: int = 0, _seen: set | None = None) -> list[dict]:
    """Find every artifact-like record in a nested result and describe it for rendering."""
    seen = _seen if _seen is not None else set()
    found: list[dict] = []
    if _depth > _MAX_DEPTH:
        return found
    if isinstance(value, dict):
        artifact_id = value.get("artifact_id")
        artifact_type = value.get("type") or value.get("artifact_type")
        if isinstance(artifact_id, str) and artifact_id and artifact_id not in seen:
            seen.add(artifact_id)
            filename = value.get("filename") or value.get("file")
            extension_value = value.get("extension") or (str(filename).rsplit(".", 1)[-1] if isinstance(filename, str) and "." in filename else "")
            extension = str(extension_value or "").lower().lstrip(".")
            normalized_type = str(artifact_type or "").lower()
            kind = _KIND_BY_TYPE.get(normalized_type, "file")
            if extension:
                if extension in {"png", "jpg", "jpeg", "webp", "svg"}:
                    kind = "image"
                elif extension in {"mp4", "webm", "mov"}:
                    kind = "video"
                elif extension in {"wav", "mp3", "m4a", "ogg"}:
                    kind = "audio"
                elif extension == "pdf":
                    kind = "pdf"
                elif extension in {"md", "txt", "rtf", "doc", "docx"}:
                    kind = "document"
                elif normalized_type in {"images", "image", "diagrams", "schematics", "blueprints"}:
                    kind = "document" if extension in {"json", "xml"} else "file"
            if normalized_type == "generated_files" and extension in _CODE_EXTENSIONS:
                kind = "code"
            attachment = {
                "artifact_id": artifact_id,
                "kind": kind,
                "type": artifact_type,
                "title": value.get("title") or value.get("name") or value.get("source") or _humanize(str(artifact_type or "file")),
                "url": f"/artifacts/{artifact_id}/content",
            }
            if extension:
                attachment["extension"] = extension
            found.append(attachment)
        for child in value.values():
            found.extend(collect_attachments(child, _depth + 1, seen))
    elif isinstance(value, list):
        for child in value[:50]:
            found.extend(collect_attachments(child, _depth + 1, seen))
    return found[:_MAX_ATTACHMENTS]


def _describe_search(result: dict) -> str | None:
    groups = result.get("results")
    if isinstance(groups, dict):
        parts = [f"{len(v)} in {k.replace('_', ' ')}" for k, v in groups.items() if isinstance(v, list) and v]
        total = sum(len(v) for v in groups.values() if isinstance(v, list))
        if total == 0:
            return "I searched your projects, memory and artifacts but found nothing matching that."
        return f"I found {total} match{'es' if total != 1 else ''}: " + ", ".join(parts) + "."
    return None


def _describe_scalars(result: dict, capability: str) -> str:
    """Last resort: a short readable sentence from top-level scalar fields."""
    bits = []
    for key, value in result.items():
        if key in {"success", "capability", "status", "code", "state"}:
            continue
        if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value).strip():
            text = str(value).strip()
            if len(text) <= 120:
                bits.append(f"{_humanize(key)}: {text}")
        if len(bits) == 4:
            break
    head = f"{_humanize(capability)} {'finished' if result.get('success') is not False else 'did not complete'}."
    return head + (" " + "; ".join(bits) + "." if bits else "")


def build_message(
    result: Any,
    capability: str | None = None,
    *,
    allow_json: bool = False,
) -> str:
    """Return readable text by default; preserve JSON only for explicit JSON requests."""
    if isinstance(result, str):
        return _normalize_text(result, allow_json=allow_json) or "Done."
    if not isinstance(result, dict):
        return "Done."
    capability = capability or str(result.get("capability") or "request")
    failed = result.get("success") is False

    text = _first_text(result)
    if text:
        return _normalize_text(text, allow_json=allow_json)

    if capability in {"search", "unified_search"}:
        described = _describe_search(result)
        if described:
            return described

    attachments = collect_attachments(result)
    if attachments and not failed:
        kinds = {a["kind"] for a in attachments}
        noun = {"image": "image", "audio": "audio recording", "video": "video", "pdf": "PDF"}.get(next(iter(kinds)), "file") if len(kinds) == 1 else "files"
        count = len(attachments)
        return f"Here {'is your' if count == 1 else 'are your'} {noun}{'' if count == 1 else 's' if noun != 'files' else ''}."

    if failed:
        reason = result.get("error") or result.get("reason") or result.get("code")
        if isinstance(reason, dict):
            reason = reason.get("message") or reason.get("code")
        base = f"{_humanize(capability)} could not be completed"
        if isinstance(reason, str) and reason.strip():
            detail = reason.strip().replace("_", " ").rstrip(".!?")
            return f"{base}: {detail}."
        return base + "."

    return _describe_scalars(result, capability)


def build_output(attachments: list[dict]) -> dict | None:
    """Create the primary renderer contract from the first renderable artifact.

    Keep the complete attachment list for additional files, but expose one
    primary output so the chat renderer can show media inline consistently.
    """
    if not attachments:
        return None
    item = attachments[0]
    kind = item.get("kind")
    output_type = {
        "image": "image",
        "audio": "audio",
        "video": "video",
        "pdf": "pdf",
    }.get(kind)
    if not output_type:
        return None
    output = {
        "type": output_type,
        "url": item.get("url"),
        "artifact_id": item.get("artifact_id"),
        "title": item.get("title"),
    }
    if item.get("extension"):
        output["language"] = item["extension"]
    return {key: value for key, value in output.items() if value is not None}


def adapt(response: dict, prompt: str | None = None) -> dict:
    """Add readable user output while retaining structured data for API consumers.

    Raw JSON is kept only when the user's prompt explicitly requests it.
    """
    if not isinstance(response, dict):
        return response
    allow_json = _explicitly_requests_json(prompt)
    result = response.get("result")
    capability = None
    if isinstance(result, dict):
        capability = result.get("capability")
    if not capability:
        parsed = response.get("parsed")
        if isinstance(parsed, dict):
            capability = parsed.get("capability")

    existing_message = response.get("message")
    if isinstance(existing_message, str) and existing_message.strip():
        response["message"] = _normalize_text(existing_message, allow_json=allow_json)
    elif isinstance(result, (dict, str)):
        response["message"] = build_message(result, capability, allow_json=allow_json)
    elif response.get("success") is False:
        response["message"] = "I could not complete that request. Please try rephrasing it."
    else:
        response["message"] = "Done."

    if not isinstance(response.get("attachments"), list) or not response["attachments"]:
        response["attachments"] = collect_attachments(result) if result is not None else []

    # The desktop chat renderer consumes a single primary output descriptor.
    # Derive it from the same attachment metadata so media is rendered inline
    # instead of leaving the user with an empty response or internal JSON.
    if "output" not in response or not isinstance(response.get("output"), dict):
        primary = build_output(response.get("attachments", []))
        if primary:
            response["output"] = primary
    return response
