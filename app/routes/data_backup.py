import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.services.data.data_backup_service import (
    BackupIntegrityError,
    DataBackupService,
)

router = APIRouter()


def _service() -> DataBackupService:
    return DataBackupService(Path(os.environ.get("LUMIRA_DATA_ROOT", "memory")))


@router.get("/data/backup")
def export_data_backup():
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        _service().export_backup(temporary_path)
        content = temporary_path.read_bytes()
    except (BackupIntegrityError, OSError) as exc:
        raise HTTPException(status_code=422, detail="data backup could not be created") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lumira-backup.zip"'},
    )


@router.post("/data/restore")
async def restore_data_backup(file: UploadFile = File(...)):
    if file.filename is None or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="a .zip backup is required")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > DataBackupService.MAX_ARCHIVE_BYTES:
                    raise BackupIntegrityError("backup archive exceeds the size limit")
                temporary.write(chunk)
        return _service().restore_backup(temporary_path)
    except (BackupIntegrityError, OSError) as exc:
        raise HTTPException(status_code=422, detail="data backup could not be restored") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
