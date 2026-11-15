from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_core_app_starts_when_an_unavailable_optional_http_provider_is_enabled():
    repo_root = Path(__file__).resolve().parents[1]
    code = r'''
import importlib.abc
import sys

class BlockRequests(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "requests" or fullname.startswith("requests."):
            raise ModuleNotFoundError("requests intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockRequests())
import app.main
from app.services.providers.provider_registry import ProviderRegistry
assert ProviderRegistry.get("transcription") is None
'''
    env = os.environ.copy()
    env["LUMIRA_TRANSCRIPTION_ENABLED"] = "true"
    env["LUMIRA_TRANSCRIPTION_API_KEY"] = "test-placeholder"
    env["LUMIRA_LOCAL_TRANSCRIPTION_ENABLED"] = "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
