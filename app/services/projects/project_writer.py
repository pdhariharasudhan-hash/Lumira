from typing import Dict
from pathlib import Path
import re
import json
import os
import shutil
import uuid
from datetime import datetime

from app.services.project_context.project_context_service import (
    ProjectContextService
)

from app.services.project_context.project_history_service import (
    ProjectHistoryService
)
from app.services.sessions.session_manager_service import redact_sensitive_value


class ProjectWriter:

    def save(
        self,
        project_name: str,
        files: Dict[str, str],
        metadata: Dict
    ):

        project_name = str(project_name).strip()
        if not project_name or "/" in project_name or "\\" in project_name or project_name in {".", ".."}:
            raise ValueError("project_name must be a single safe path component")

        project_name = re.sub(r"[^A-Za-z0-9_-]+", "_", project_name).strip("_-")
        if not project_name:
            raise ValueError("project_name must contain letters or digits")

        if not isinstance(files, dict) or not files:
            raise ValueError("files must be a non-empty mapping")
        if len(files) > 100:
            raise ValueError("generated projects may contain at most 100 files")
        total_bytes = 0
        for filename, content in files.items():
            if (
                not isinstance(filename, str)
                or not filename
                or Path(filename).is_absolute()
                or "/" in filename
                or "\\" in filename
                or filename in {".", ".."}
            ):
                raise ValueError("generated filenames must be safe path components")
            if not isinstance(content, str):
                raise ValueError("generated file contents must be text")
            file_bytes = len(content.encode("utf-8"))
            total_bytes += file_bytes
            if file_bytes > 2_000_000 or total_bytes > 10_000_000:
                raise ValueError("generated project exceeds the 10000000-byte write limit")

        generated_root = Path("generated").resolve()
        base_folder = generated_root / project_name
        if generated_root not in base_folder.resolve().parents:
            raise ValueError("project path escapes the generated directory")
        base_folder.mkdir(parents=True, exist_ok=True)

        version = 1
        while (base_folder / f"v{version}").exists():
            version += 1

        project_version = f"v{version}"
        folder = base_folder / project_version
        staging_folder = base_folder / f".{project_version}.{uuid.uuid4().hex}.tmp"
        staging_folder.mkdir(parents=False, exist_ok=False)

        project_metadata = dict(metadata or {})
        project_metadata.update({
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": project_version,
            "status": "generated",
        })
        project_metadata = redact_sensitive_value(project_metadata)

        try:
            for filename, content in files.items():
                (staging_folder / filename).write_text(content, encoding="utf-8")
            with (staging_folder / "metadata.json").open("w", encoding="utf-8") as stream:
                json.dump(project_metadata, stream, indent=4)
            if folder.exists():
                raise FileExistsError(f"Project version already exists: {folder}")
            os.replace(staging_folder, folder)
        except Exception:
            shutil.rmtree(staging_folder, ignore_errors=True)
            raise

        ProjectContextService().update_project(

            project_name=
            project_name,

            updates={

                "latest_version":
                project_version
            }
        )

        ProjectHistoryService().log_event(

            project_name,

            "version_created",

            {
                "version":
                project_version
            }
        )

        return str(
            folder
        )
