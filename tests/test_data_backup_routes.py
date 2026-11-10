import asyncio
import io
import zipfile

import pytest
from starlette.datastructures import UploadFile

from app.routes import data_backup


def test_export_backup_route_returns_zip(monkeypatch, tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    (root / "state.json").write_text('{"ok":true}', encoding="utf-8")
    monkeypatch.setenv("LUMIRA_DATA_ROOT", str(root))

    response = data_backup.export_data_backup()

    assert response.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        assert "state.json" in archive.namelist()


def test_restore_backup_route_rejects_non_zip(monkeypatch):
    upload = type(
        "Upload",
        (),
        {"filename": "backup.txt"},
    )()

    with pytest.raises(data_backup.HTTPException) as error:
        asyncio.run(data_backup.restore_data_backup(upload))
    assert error.value.status_code == 400


def test_restore_backup_route_restores_verified_archive(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.json").write_text('{"restored":true}', encoding="utf-8")
    backup = tmp_path / "backup.zip"
    data_backup.DataBackupService(source).export_backup(backup)
    target = tmp_path / "target"
    monkeypatch.setenv("LUMIRA_DATA_ROOT", str(target))

    upload = UploadFile(filename="lumira.zip", file=backup.open("rb"))
    result = asyncio.run(data_backup.restore_data_backup(upload))

    assert result["success"] is True
    assert (target / "state.json").read_text(encoding="utf-8") == '{"restored":true}'
