from __future__ import annotations

import ast
from pathlib import Path


class RouterIntegrityService:
    """Static import audit for registered API routes without importing app modules."""

    def snapshot(self) -> dict:
        registry = Path("app/router_registry.py")
        findings = []
        if not registry.is_file():
            return {"success": False, "status": "failed", "findings": [{"code": "router_registry_missing"}]}
        try:
            tree = ast.parse(registry.read_text(encoding="utf-8"), filename=str(registry))
        except (OSError, SyntaxError) as exc:
            return {"success": False, "status": "failed", "findings": [{"code": "router_registry_unreadable", "type": type(exc).__name__}]}
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.routes."):
                modules.append(node.module)
        for module in modules:
            relative = Path(*module.split(".")).with_suffix(".py")
            package = Path(*module.split(".")) / "__init__.py"
            if not relative.is_file() and not package.is_file():
                findings.append({"code": "missing_route_module", "module": module})
        return {
            "success": not findings,
            "status": "healthy" if not findings else "degraded",
            "registered_route_modules": len(modules),
            "findings": findings[:100],
        }
