import json
import zipfile

import pytest

from app.services.data.data_backup_service import (
    BackupIntegrityError,
    DataBackupService,
)


def test_export_and_restore_verifies_manifest_and_preserves_nested_data(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "memory.json").write_text('{"idea":"keep"}', encoding="utf-8")
    (source / "nested").mkdir()
    (source / "nested" / "tasks.jsonl").write_text('{"status":"done"}\n', encoding="utf-8")
    backup = tmp_path / "backup.zip"

    result = DataBackupService(source).export_backup(backup)
    assert result["file_count"] == 2

    target = tmp_path / "restored"
    restored = DataBackupService(target).restore_backup(backup)
    assert restored["file_count"] == 2
    assert (target / "memory.json").read_text(encoding="utf-8") == '{"idea":"keep"}'
    assert (target / "nested" / "tasks.jsonl").exists()


def test_restore_rejects_tampered_content_without_overwriting_existing_data(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "memory.json").write_text('{"new":true}', encoding="utf-8")
    backup = tmp_path / "backup.zip"
    DataBackupService(source).export_backup(backup)
    target = tmp_path / "target"
    target.mkdir()
    existing = target / "memory.json"
    existing.write_text('{"old":true}', encoding="utf-8")

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(backup) as original, zipfile.ZipFile(tampered, "w") as replacement:
        for item in original.infolist():
            content = original.read(item)
            if item.filename == "memory.json":
                content = b'{"tampered":true}'
            replacement.writestr(item, content)

    with pytest.raises(BackupIntegrityError, match="checksum"):
        DataBackupService(target).restore_backup(tampered)
    assert existing.read_text(encoding="utf-8") == '{"old":true}'


def test_restore_rejects_path_traversal(tmp_path):
    backup = tmp_path / "unsafe.zip"
    manifest = {
        "format": 1,
        "files": [{"path": "../outside.json", "bytes": 2, "sha256": "x"}],
        "total_bytes": 2,
    }
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("../outside.json", b"{}")

    with pytest.raises(BackupIntegrityError, match="unsafe path"):
        DataBackupService(tmp_path / "target").restore_backup(backup)


def _write_manifest_backup(path, files, extra_entries=None, total_bytes=None):
    with zipfile.ZipFile(path, "w") as archive:
        manifest_files = []
        for name, payload in files:
            archive.writestr(name, payload)
            manifest_files.append({
                "path": name,
                "bytes": len(payload),
                "sha256": __import__("hashlib").sha256(payload).hexdigest(),
            })
        for name, payload in extra_entries or []:
            archive.writestr(name, payload)
        archive.writestr("manifest.json", json.dumps({
            "format": 1,
            "files": manifest_files,
            "total_bytes": sum(item["bytes"] for item in manifest_files) if total_bytes is None else total_bytes,
        }))


def test_restore_rejects_unlisted_archive_payload(tmp_path):
    backup = tmp_path / "extra.zip"
    _write_manifest_backup(backup, [("state.json", b'{"ok":true}')], [("secret.json", b'{"leak":true}')])
    target = tmp_path / "target"
    with pytest.raises(BackupIntegrityError, match="unlisted"):
        DataBackupService(target).restore_backup(backup)
    assert not (target / "state.json").exists()


def test_restore_rejects_duplicate_manifest_paths(tmp_path):
    backup = tmp_path / "duplicate.zip"
    payload = b'{"ok":true}'
    _write_manifest_backup(backup, [("state.json", payload)])
    manifest = {
        "format": 1,
        "files": [
            {"path": "state.json", "bytes": len(payload), "sha256": __import__("hashlib").sha256(payload).hexdigest()},
            {"path": "state.json", "bytes": len(payload), "sha256": __import__("hashlib").sha256(payload).hexdigest()},
        ],
        "total_bytes": len(payload) * 2,
    }
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("state.json", payload)
        archive.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(BackupIntegrityError, match="duplicate"):
        DataBackupService(tmp_path / "target").restore_backup(backup)


def test_restore_rejects_manifest_total_size_mismatch(tmp_path):
    backup = tmp_path / "bad-total.zip"
    _write_manifest_backup(backup, [("state.json", b'{}')], total_bytes=99)
    target = tmp_path / "target"
    with pytest.raises(BackupIntegrityError, match="total size"):
        DataBackupService(target).restore_backup(backup)
    assert not (target / "state.json").exists()


def test_export_skips_symlinked_json_files_outside_data_root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":true}', encoding="utf-8")
    try:
        (source / "linked.json").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted")
    backup = tmp_path / "safe.zip"
    result = DataBackupService(source).export_backup(backup)
    assert result["file_count"] == 0
    with zipfile.ZipFile(backup) as archive:
        assert archive.namelist() == ["manifest.json"]


@pytest.mark.parametrize(
    "manifest, message",
    [
        ({"format": True, "files": [], "total_bytes": 0}, "manifest is invalid"),
        ({"format": 1, "files": [], "total_bytes": True}, "manifest is invalid"),
        ({"format": 1, "files": [], "total_bytes": -1}, "manifest is invalid"),
    ],
)
def test_restore_rejects_invalid_manifest_scalar_types(tmp_path, manifest, message):
    backup = tmp_path / "invalid-manifest.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(BackupIntegrityError, match=message):
        DataBackupService(tmp_path / "target").restore_backup(backup)


def test_restore_rejects_oversized_manifest_before_parsing(tmp_path):
    backup = tmp_path / "large-manifest.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", b" " * 1_000_001)
    with pytest.raises(BackupIntegrityError, match="manifest exceeds"):
        DataBackupService(tmp_path / "target").restore_backup(backup)


@pytest.mark.parametrize("unsafe_path", ["C:outside.json", "folder:stream.json"])
def test_restore_rejects_drive_or_stream_qualified_paths(tmp_path, unsafe_path):
    backup = tmp_path / "drive-path.zip"
    manifest = {
        "format": 1,
        "files": [{"path": unsafe_path, "bytes": 2, "sha256": "0" * 64}],
        "total_bytes": 2,
    }
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(unsafe_path, b"{}")
    with pytest.raises(BackupIntegrityError, match="unsafe path"):
        DataBackupService(tmp_path / "target").restore_backup(backup)
