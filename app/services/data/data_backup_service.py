from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class BackupIntegrityError(ValueError):
    """Raised when a backup cannot be trusted or safely restored."""


class DataBackupService:
    """Create and restore bounded, manifest-verified JSON data backups."""

    MAX_FILES = 2_000
    MAX_FILE_BYTES = 10 * 1024 * 1024
    MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
    MAX_TOTAL_BYTES = 250 * 1024 * 1024
    ALLOWED_SUFFIXES = {".json", ".jsonl"}
    MANIFEST_NAME = "manifest.json"

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root).resolve()

    def export_backup(self, destination: str | Path) -> dict[str, Any]:
        destination_path = Path(destination).resolve()
        if destination_path.suffix.lower() != ".zip":
            raise BackupIntegrityError("backup destination must be a .zip file")
        files = self._source_files(destination_path)
        if len(files) > self.MAX_FILES:
            raise BackupIntegrityError("backup contains too many files")

        manifest_files: list[dict[str, Any]] = []
        total_bytes = 0
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".zip", dir=destination_path.parent, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
            with zipfile.ZipFile(
                temporary_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for source in files:
                    relative = source.relative_to(self.data_root).as_posix()
                    content = source.read_bytes()
                    if len(content) > self.MAX_FILE_BYTES:
                        raise BackupIntegrityError(
                            f"backup file exceeds the {self.MAX_FILE_BYTES} byte limit"
                        )
                    total_bytes += len(content)
                    if total_bytes > self.MAX_TOTAL_BYTES:
                        raise BackupIntegrityError("backup exceeds the total size limit")
                    manifest_files.append(
                        {
                            "path": relative,
                            "bytes": len(content),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
                    archive.writestr(relative, content)
                manifest = {
                    "format": 1,
                    "files": manifest_files,
                    "total_bytes": total_bytes,
                }
                archive.writestr(
                    self.MANIFEST_NAME,
                    json.dumps(manifest, sort_keys=True).encode("utf-8"),
                )
            os.replace(temporary_path, destination_path)
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return {
            "success": True,
            "path": str(destination_path),
            "file_count": len(manifest_files),
            "total_bytes": total_bytes,
        }

    def restore_backup(self, backup: str | Path) -> dict[str, Any]:
        backup_path = Path(backup).resolve()
        if not backup_path.is_file():
            raise BackupIntegrityError("backup file does not exist")
        if backup_path.stat().st_size > self.MAX_ARCHIVE_BYTES:
            raise BackupIntegrityError("backup archive exceeds the size limit")

        with zipfile.ZipFile(backup_path) as archive:
            manifest = self._read_manifest(archive)
            entries = manifest["files"]
            if len(entries) > self.MAX_FILES:
                raise BackupIntegrityError("backup contains too many files")
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BackupIntegrityError("backup contains duplicate archive entries")
            expected_names = {self.MANIFEST_NAME}
            for entry in entries:
                if not isinstance(entry, dict):
                    raise BackupIntegrityError("backup manifest entry is invalid")
                expected_names.add(self._safe_relative_path(entry.get("path")).as_posix())
            if set(names) != expected_names:
                raise BackupIntegrityError("backup contains unlisted or missing archive entries")
            for info in infos:
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise BackupIntegrityError("backup contains a symbolic link")
                if info.flag_bits & 0x1:
                    raise BackupIntegrityError("encrypted backup entries are not supported")

            temporary_files: list[tuple[Path, Path]] = []
            total_bytes = 0
            seen_paths: set[str] = set()
            try:
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise BackupIntegrityError("backup manifest entry is invalid")
                    relative = self._safe_relative_path(entry.get("path"))
                    relative_name = relative.as_posix()
                    if relative_name in seen_paths:
                        raise BackupIntegrityError("backup manifest contains duplicate paths")
                    seen_paths.add(relative_name)
                    declared_bytes = entry.get("bytes")
                    digest = entry.get("sha256")
                    if (
                        isinstance(declared_bytes, bool)
                        or not isinstance(declared_bytes, int)
                        or declared_bytes < 0
                        or not isinstance(digest, str)
                        or len(digest) != 64
                        or any(char not in "0123456789abcdef" for char in digest)
                    ):
                        raise BackupIntegrityError("backup manifest metadata is invalid")
                    info = archive.getinfo(relative_name)
                    if info.file_size > self.MAX_FILE_BYTES:
                        raise BackupIntegrityError("backup file exceeds the size limit")
                    if info.file_size != declared_bytes:
                        raise BackupIntegrityError("backup checksum or manifest size verification failed")
                    total_bytes += info.file_size
                    if total_bytes > self.MAX_TOTAL_BYTES:
                        raise BackupIntegrityError("backup exceeds the total size limit")
                    content = archive.read(info)
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise BackupIntegrityError("backup checksum verification failed")
                    target = self.data_root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    root = self.data_root.resolve()
                    parent = target.parent.resolve()
                    if parent != root and root not in parent.parents:
                        raise BackupIntegrityError("backup target resolves outside the data directory")
                    if target.is_symlink():
                        raise BackupIntegrityError("backup target is a symbolic link")
                    with tempfile.NamedTemporaryFile(
                        mode="wb", dir=parent, delete=False
                    ) as temporary:
                        temporary.write(content)
                        temporary.flush()
                        os.fsync(temporary.fileno())
                        temporary_files.append((Path(temporary.name), target))
                if total_bytes != manifest.get("total_bytes"):
                    raise BackupIntegrityError("backup manifest total size verification failed")
                for temporary, target in temporary_files:
                    os.replace(temporary, target)
            finally:
                for temporary, _ in temporary_files:
                    if temporary.exists():
                        temporary.unlink()
        return {"success": True, "file_count": len(entries), "total_bytes": total_bytes}

    def _source_files(self, destination: Path) -> list[Path]:
        if not self.data_root.is_dir():
            return []
        root = self.data_root.resolve()
        return sorted(
            path
            for path in self.data_root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.resolve() != destination
            and (path.resolve() == root or root in path.resolve().parents)
            and path.suffix.lower() in self.ALLOWED_SUFFIXES
        )

    def _read_manifest(self, archive: zipfile.ZipFile) -> dict[str, Any]:
        try:
            info = archive.getinfo(self.MANIFEST_NAME)
            if info.file_size > 1_000_000:
                raise BackupIntegrityError("backup manifest exceeds the size limit")
            raw = json.loads(archive.read(info))
        except BackupIntegrityError:
            raise
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise BackupIntegrityError("backup manifest is invalid") from exc
        total_bytes = raw.get("total_bytes") if isinstance(raw, dict) else None
        if (
            not isinstance(raw, dict)
            or isinstance(raw.get("format"), bool)
            or raw.get("format") != 1
            or not isinstance(raw.get("files"), list)
            or isinstance(total_bytes, bool)
            or not isinstance(total_bytes, int)
            or total_bytes < 0
            or total_bytes > self.MAX_TOTAL_BYTES
        ):
            raise BackupIntegrityError("backup manifest is invalid")
        return raw

    def _safe_relative_path(self, value: Any) -> Path:
        if not isinstance(value, str) or not value:
            raise BackupIntegrityError("backup contains an invalid path")
        relative = Path(value)
        if (
            relative.is_absolute()
            or bool(relative.drive)
            or ":" in value
            or relative.as_posix() != value
            or relative.suffix.lower() not in self.ALLOWED_SUFFIXES
            or ".." in relative.parts
        ):
            raise BackupIntegrityError("backup contains an unsafe path")
        return relative
