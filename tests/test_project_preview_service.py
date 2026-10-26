import json

import pytest

from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.workspace.project_preview_service import ProjectPreviewService


def test_preview_url_accepts_explicit_loopback_port():
    assert ProjectPreviewService._valid_url("http://127.0.0.1:5173")
    assert ProjectPreviewService._valid_url("http://localhost:8000/preview")
    assert ProjectPreviewService._valid_url("http://[::1]:4173")


def test_preview_url_rejects_external_hosts_and_missing_ports():
    assert not ProjectPreviewService._valid_url("https://example.com:443")
    assert not ProjectPreviewService._valid_url("http://localhost")
    assert not ProjectPreviewService._valid_url("http://192.168.1.20:5173")
    assert not ProjectPreviewService._valid_url("file:///etc/passwd")


def test_preview_url_rejects_credentials_and_invalid_ports():
    assert not ProjectPreviewService._valid_url("http://user:pass@localhost:5173")
    assert not ProjectPreviewService._valid_url("http://localhost:99999")
    assert not ProjectPreviewService._valid_url("http://[::1]:bad")


def test_get_missing_preview_reports_failure(tmp_path):
    service = ProjectPreviewService(tmp_path / "previews.json")

    result = service.get("demo", "v1")

    assert result == {"success": False, "preview": None}


def test_register_and_stop_preview_are_consistent(tmp_path, monkeypatch):
    project_path = tmp_path / "generated" / "demo" / "v1"
    project_path.mkdir(parents=True)
    monkeypatch.setattr(
        "app.services.workspace.project_preview_service.resolve_project_path",
        lambda project, version: project_path if (project, version) == ("demo", "v1") else None,
    )
    service = ProjectPreviewService(tmp_path / "previews.json")

    registered = service.register("demo", "v1", "http://127.0.0.1:5173")
    assert registered["success"] is True
    assert service.get("demo", "v1")["preview"]["status"] == "registered"

    stopped = service.stop("demo", "v1")
    assert stopped["success"] is True
    assert service.get("demo", "v1")["preview"]["status"] == "stopped"


def test_register_rejects_preview_for_missing_project(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.workspace.project_preview_service.resolve_project_path",
        lambda project, version: None,
    )
    service = ProjectPreviewService(tmp_path / "previews.json")

    result = service.register("missing", "v1", "http://127.0.0.1:5173")

    assert result["success"] is False
    assert result["code"] == "project_not_found"


@pytest.mark.parametrize("action", ["get", "register", "stop"])
def test_preview_index_rejects_non_list_root_without_overwriting(tmp_path, monkeypatch, action):
    index_path = tmp_path / "previews.json"
    original = '{"schema_version": 99}'
    index_path.write_text(original, encoding="utf-8")
    project_path = tmp_path / "generated" / "demo" / "v1"
    project_path.mkdir(parents=True)
    monkeypatch.setattr(
        "app.services.workspace.project_preview_service.resolve_project_path",
        lambda project, version: project_path if (project, version) == ("demo", "v1") else None,
    )
    service = ProjectPreviewService(index_path)

    with pytest.raises(PersistenceIntegrityError, match="preview index"):
        if action == "get":
            service.get("demo", "v1")
        elif action == "register":
            service.register("demo", "v1", "http://127.0.0.1:5173")
        else:
            service.stop("demo", "v1")

    assert index_path.read_text(encoding="utf-8") == original



def test_get_rejects_tampered_external_preview_url_without_overwriting(tmp_path):
    index_path = tmp_path / "previews.json"
    original = '[{"project":"demo","version":"v1","url":"https://example.com:443","status":"registered","updated_at":"now"}]'
    index_path.write_text(original, encoding="utf-8")
    service = ProjectPreviewService(index_path)

    with pytest.raises(PersistenceIntegrityError, match="unsafe URL"):
        service.get("demo", "v1")

    assert index_path.read_text(encoding="utf-8") == original


def test_preview_index_rejects_missing_version(tmp_path):
    index_path = tmp_path / "previews.json"
    original = '[{"project":"demo","url":"http://127.0.0.1:5173","status":"registered","updated_at":"now"}]'
    index_path.write_text(original, encoding="utf-8")
    service = ProjectPreviewService(index_path)

    with pytest.raises(PersistenceIntegrityError, match="invalid project reference"):
        service.get("demo", "v1")

    assert index_path.read_text(encoding="utf-8") == original


def test_preview_index_rejects_duplicate_project_versions(tmp_path):
    index_path = tmp_path / "previews.json"
    record = {
        "project": "demo",
        "version": "v1",
        "url": "http://127.0.0.1:5173",
        "status": "registered",
        "updated_at": "now",
    }
    original = json.dumps([record, record])
    index_path.write_text(original, encoding="utf-8")
    service = ProjectPreviewService(index_path)

    with pytest.raises(PersistenceIntegrityError, match="duplicate project versions"):
        service.get("demo", "v1")

    assert index_path.read_text(encoding="utf-8") == original
