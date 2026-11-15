from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


def test_legacy_main_entrypoint_uses_the_authenticated_application():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    aliases_canonical_app = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.main"
        and any(alias.name == "app" for alias in node.names)
        for node in tree.body
    )
    legacy_auth_routes = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"register", "login"}
        for node in tree.body
    )

    assert aliases_canonical_app
    assert not legacy_auth_routes


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_run_entrypoint_accepts_loopback_only(host):
    run = importlib.import_module("app.launch_config")

    assert run.validate_bind_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.10", "lumira.example"])
def test_run_entrypoint_rejects_non_loopback_bind(host):
    run = importlib.import_module("app.launch_config")

    with pytest.raises(ValueError, match="loopback"):
        run.validate_bind_host(host)


def test_replit_workflow_does_not_publish_backend_or_frontend_on_all_interfaces():
    replit_config = (Path(__file__).resolve().parents[1] / ".replit").read_text(encoding="utf-8")

    assert "0.0.0.0" not in replit_config
    assert "HOST=127.0.0.1" in replit_config
    assert "--host 127.0.0.1" in replit_config
    assert "externalPort" not in replit_config


def test_electron_source_launch_has_no_developer_machine_fallback():
    electron_main = (
        Path(__file__).resolve().parents[1] / "lumira_desktop" / "electron-main.cjs"
    ).read_text(encoding="utf-8")

    assert "E:\\\\Hari\\\\personal_ai_core" not in electron_main
