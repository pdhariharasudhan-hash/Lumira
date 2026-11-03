"""User Output Adapter.

Capabilities return structured dictionaries (JSON) internally. This module is the
single boundary that turns those dictionaries into what the user should actually
see: a human-readable ``message`` plus renderable ``attachments`` (images, audio,
video, PDFs, files). Raw JSON stays available under ``result`` for developer/API
use, but the chat UI should render ``message`` and ``attachments`` first.

Pure Python: no FastAPI or service imports, so it is trivial to unit test.
"""

from __future__ import annotations

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
            kind = _KIND_BY_TYPE.get(str(artifact_type or "").lower(), "file")
            if str(artifact_type or "").lower() == "generated_files" and extension in _CODE_EXTENSIONS:
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


def build_message(result: Any, capability: str | None = None) -> str:
    """Return a human-readable sentence for a capability result. Never returns JSON."""
    if isinstance(result, str):
        return result.strip() or "Done."
    if not isinstance(result, dict):
        return "Done."
    capability = capability or str(result.get("capability") or "request")
    failed = result.get("success") is False

    text = _first_text(result)
    if text:
        return text

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
        base = f"{_humanize(capability)} could not be completed"
        return f"{base}: {str(reason).replace('_', ' ')}." if reason else base + "."

    return _describe_scalars(result, capability)


def adapt(response: dict) -> dict:
    """Add ``message`` and ``attachments`` to a /command response without removing anything.

    Existing consumers keep working (``result`` and everything else is untouched).
    A ``message`` already set by the route (greetings, conversation) is preserved.
    """
    if not isinstance(response, dict):
        return response
    result = response.get("result")
    capability = None
    if isinstance(result, dict):
        capability = result.get("capability")
    if not capability:
        parsed = response.get("parsed")
        if isinstance(parsed, dict):
            capability = parsed.get("capability")

    if not (isinstance(response.get("message"), str) and response["message"].strip()):
        if isinstance(result, (dict, str)):
            response["message"] = build_message(result, capability)
        elif response.get("success") is False:
            response["message"] = "I could not complete that request. Please try rephrasing it."
        else:
            response["message"] = "Done."

    if "attachments" not in response:
        response["attachments"] = collect_attachments(result) if result is not None else []
    return response
