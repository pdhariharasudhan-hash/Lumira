from app.services.system.router_integrity_service import RouterIntegrityService
from app.services.system.provider_readiness_service import ProviderReadinessService
from app.services.system.feature_dependency_audit_service import FeatureDependencyAuditService


def test_router_integrity_reports_registered_route_modules():
    result = RouterIntegrityService().snapshot()
    assert result["registered_route_modules"] > 0


def test_provider_readiness_has_known_provider_statuses():
    result = ProviderReadinessService().snapshot()
    assert result["total_known_providers"] >= result["registered_count"]


def test_feature_dependency_audit_returns_bounded_findings():
    result = FeatureDependencyAuditService().snapshot()
    assert result["feature_count"] > 0
    assert len(result["findings"]) <= 100
