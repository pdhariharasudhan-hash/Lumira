from __future__ import annotations

from app.services.features.feature_registry_service import FeatureRegistryService


class FeatureDependencyAuditService:
    """Read-only audit of feature dependency references and cycles."""

    def snapshot(self) -> dict:
        registry = FeatureRegistryService().get_all()
        findings = []
        for feature_id, record in registry.items():
            if not isinstance(record, dict):
                findings.append({"feature_id": feature_id, "code": "invalid_record"})
                continue
            deps = record.get("dependencies", [])
            if not isinstance(deps, list):
                findings.append({"feature_id": feature_id, "code": "dependencies_invalid"})
                continue
            for dependency in deps:
                if dependency not in registry:
                    findings.append({"feature_id": feature_id, "code": "dependency_missing", "dependency": dependency})
            stack = [(feature_id, [])]
            visited = set()
            while stack:
                node, chain = stack.pop()
                if node in chain:
                    findings.append({"feature_id": feature_id, "code": "dependency_cycle"})
                    break
                if node in visited or node not in registry:
                    continue
                visited.add(node)
                children = registry[node].get("dependencies", [])
                if isinstance(children, list):
                    for child in children:
                        stack.append((child, chain + [node]))
        return {"success": not findings, "status": "healthy" if not findings else "degraded", "feature_count": len(registry), "findings": findings[:100]}
