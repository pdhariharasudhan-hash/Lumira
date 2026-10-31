from app.services.context.context_service import ContextService


def test_engineering_domain_detection():
    assert ContextService()._detect_domain("build an esp32 robot") == "engineering"


def test_business_domain_detection():
    assert ContextService()._detect_domain("startup revenue market") == "business"
