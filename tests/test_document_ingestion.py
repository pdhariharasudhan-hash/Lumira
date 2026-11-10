from app.services.knowledge.document_ingestion_service import DocumentIngestionService
from fastapi.testclient import TestClient


class FakeLibrary:
    def __init__(self):
        self.items = []

    def add(self, **kwargs):
        item = {"item_id": "doc-1", "type": kwargs.get("item_type"), **kwargs}
        self.items.append(item)
        return item


def test_ingests_bounded_text_document_into_library():
    library = FakeLibrary()
    result = DocumentIngestionService(library).ingest("notes.md", b"# Hello\n\nTamil: vanakkam")

    assert result["success"] is True
    assert result["document"]["title"] == "notes.md"
    assert result["document"]["characters"] > 0
    assert library.items[0]["type"] == "document"


def test_normalizes_json_and_csv_documents():
    service = DocumentIngestionService(FakeLibrary())

    json_result = service.ingest("data.json", b'{"name":"Lumira"}')
    csv_result = service.ingest("data.csv", b"name,value\nLumira,1\n")

    assert json_result["success"] is True
    assert '"name": "Lumira"' in json_result["document"]["content"]
    assert csv_result["success"] is True
    assert "Lumira | 1" in csv_result["document"]["content"]


def test_rejects_unsupported_or_oversized_documents():
    service = DocumentIngestionService(FakeLibrary())

    assert service.ingest("image.png", b"not text")["code"] == "unsupported_document_type"
    result = service.ingest("large.txt", b"x" * (service.MAX_BYTES + 1))
    assert result["code"] == "document_too_large"


def test_oversized_input_is_rejected_before_extraction(monkeypatch):
    service = DocumentIngestionService(FakeLibrary())
    monkeypatch.setattr(
        service,
        "_extract_text",
        lambda *_args: (_ for _ in ()).throw(AssertionError("extractor must not run")),
    )

    result = service.ingest("large.pdf", b"x" * (service.MAX_BYTES + 1))

    assert result == {
        "success": False,
        "code": "document_too_large",
        "max_bytes": service.MAX_BYTES,
    }


def test_malformed_documents_and_storage_failures_do_not_add_entries():
    library = FakeLibrary()
    service = DocumentIngestionService(library)

    assert service.ingest("broken.json", b"{not-json}")["code"] == "invalid_json_document"
    assert service.ingest("broken.csv", b'"unterminated')["code"] == "invalid_csv_document"
    assert service.ingest("broken.pdf", b"not-a-pdf")["code"] == "pdf_extraction_failed"
    assert library.items == []

    class FailingLibrary(FakeLibrary):
        def add(self, **kwargs):
            raise OSError("storage unavailable")

    result = DocumentIngestionService(FailingLibrary()).ingest("safe.txt", b"content")
    assert result["code"] == "document_storage_failed"


def test_preserves_bounded_source_metadata_without_overwriting_existing_entries():
    library = FakeLibrary()
    first = DocumentIngestionService(library).ingest(
        r"uploads\brief.md",
        b"first",
        project_id="project-1",
    )
    second = DocumentIngestionService(library).ingest(
        "second.md",
        b"second",
        project_id="project-2",
    )

    assert first["success"] is True
    assert second["success"] is True
    assert len(library.items) == 2
    assert library.items[0]["source"] == r"uploads\brief.md"
    assert library.items[0]["project_id"] == "project-1"
    assert library.items[1]["source"] == "second.md"
    assert library.items[1]["project_id"] == "project-2"


def test_extracts_pdf_text_when_pdf_extractor_is_installed():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = __import__("io").BytesIO()
    writer.write(buffer)

    result = DocumentIngestionService(FakeLibrary()).ingest("blank.pdf", buffer.getvalue())

    assert result["success"] is False
    assert result["code"] == "empty_document"


def test_knowledge_document_route_accepts_multipart_upload(tmp_path, monkeypatch):
    from app.main import app
    from app.routes import knowledge
    from app.services.knowledge.personal_library_service import PersonalLibraryService

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        knowledge,
        "document_ingestion",
        DocumentIngestionService(PersonalLibraryService(tmp_path / "library.json")),
    )

    response = TestClient(app).post(
        "/knowledge/documents",
        files={"file": ("brief.md", b"# Lumira\n\nA bounded note.", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["document"]["title"] == "brief.md"
