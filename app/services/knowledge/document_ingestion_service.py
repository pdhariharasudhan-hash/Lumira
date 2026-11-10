from __future__ import annotations

import csv
import io
import json
import re
from html import unescape
from pathlib import PurePath
from typing import Any

from app.services.knowledge.personal_library_service import PersonalLibraryService


class DocumentIngestionService:
    """Extract bounded text documents into the persistent personal library.

    PDF extraction is intentionally dependency-gated. The service never stores
    binary input as text or reports a successful extraction when no extractor is
    available.
    """

    MAX_BYTES = 10 * 1024 * 1024
    MAX_TEXT_CHARS = 100_000
    TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".log", ".py", ".json", ".csv", ".html", ".htm"}

    def __init__(self, library: PersonalLibraryService | None = None) -> None:
        self.library = library or PersonalLibraryService()

    @classmethod
    def _extract_text(cls, filename: str, content: bytes) -> tuple[str | None, str | None]:
        extension = PurePath(filename).suffix.casefold()
        if extension == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return None, "pdf_extractor_unavailable"
            try:
                reader = PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                return None, "pdf_extraction_failed"
        elif extension in cls.TEXT_EXTENSIONS:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                return None, "document_encoding_unsupported"
            if extension in {".html", ".htm"}:
                text = unescape(re.sub(r"<[^>]*>", " ", text))
            elif extension == ".json":
                try:
                    text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
                except (TypeError, ValueError):
                    return None, "invalid_json_document"
            elif extension == ".csv":
                try:
                    rows = csv.reader(io.StringIO(text), strict=True)
                    text = "\n".join(" | ".join(row) for row in rows)
                except csv.Error:
                    return None, "invalid_csv_document"
        else:
            return None, "unsupported_document_type"
        text = text.strip()
        if not text:
            return None, "empty_document"
        if len(text) > cls.MAX_TEXT_CHARS:
            return None, "document_text_too_large"
        return text, None

    def ingest(
        self,
        filename: str,
        content: bytes,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 255:
            return {"success": False, "code": "invalid_filename"}
        if not isinstance(content, bytes):
            return {"success": False, "code": "invalid_document_content"}
        if not content:
            return {"success": False, "code": "empty_document"}
        if len(content) > self.MAX_BYTES:
            return {"success": False, "code": "document_too_large", "max_bytes": self.MAX_BYTES}
        text, error = self._extract_text(filename, content)
        if error:
            return {"success": False, "code": error}
        try:
            item = self.library.add(
                title=PurePath(filename).name[:300],
                item_type="document",
                content=text or "",
                project_id=project_id,
                source=filename.strip(),
            )
        except (OSError, ValueError):
            return {"success": False, "code": "document_storage_failed"}
        return {
            "success": True,
            "document": {
                "item_id": item["item_id"],
                "title": item["title"],
                "source": item["source"],
                "characters": len(text or ""),
                "content": text,
            },
        }
