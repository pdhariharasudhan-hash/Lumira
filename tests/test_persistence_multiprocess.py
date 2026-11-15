from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_reading_missing_store_does_not_create_files_or_directories(tmp_path):
    from app.services.persistence.atomic_json_store import AtomicJsonStore

    store_path = tmp_path / "not-created" / "state.json"

    assert AtomicJsonStore(store_path).read(default={"items": []}) == {"items": []}
    assert not store_path.parent.exists()


def test_atomic_json_store_serializes_updates_across_processes(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    store_path = tmp_path / "shared.json"
    worker = r'''
import sys
import time
from app.services.persistence.atomic_json_store import AtomicJsonStore

store = AtomicJsonStore(sys.argv[1])
for _ in range(8):
    def append_item(items):
        time.sleep(0.02)
        items.append("written")
    store.update(append_item, default=[])
'''
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = [
        subprocess.Popen(
            [sys.executable, "-B", "-c", worker, str(store_path)],
            cwd=repo_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(4)
    ]

    outcomes = [process.communicate(timeout=20) for process in processes]

    assert [process.returncode for process in processes] == [0, 0, 0, 0], "\n".join(
        stderr for _, stderr in outcomes
    )
    assert len(json.loads(store_path.read_text(encoding="utf-8"))) == 32
