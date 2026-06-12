import os
from typing import Dict, Any

from core.constants import GENERATED_DIR


def ensure_generated_dir() -> None:

    os.makedirs(
        GENERATED_DIR,
        exist_ok=True
    )


def write_file(
    path: str,
    content: str
) -> None:

    ensure_generated_dir()

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)


def materialize_code_output(
    code_output: Dict[str, Any],
    pipeline_id: str
) -> Dict[str, Any]:

    ensure_generated_dir()

    run_dir = os.path.join(
        GENERATED_DIR,
        pipeline_id
    )

    os.makedirs(
        run_dir,
        exist_ok=True
    )

    files = code_output.get(
        "files",
        {}
    )

    generated_files = []

    for file_name, content in files.items():

        file_path = os.path.join(
            run_dir,
            file_name
        )

        write_file(
            file_path,
            content
        )

        generated_files.append(
            file_path
        )

    return {
        "generated_files": generated_files,
        "generated_dir": run_dir,
        "status": "success"
    }