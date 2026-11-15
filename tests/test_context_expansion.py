from app.services.context.context_service import ContextService


def test_engineering_domain_detection():
    assert ContextService()._detect_domain("build an esp32 robot") == "engineering"


def test_business_domain_detection():
    assert ContextService()._detect_domain("startup revenue market") == "business"


def test_fastapi_implies_python_language_for_execution_planning():
    assert ContextService()._detect_language("Build a FastAPI expense API") == "Python"


def test_explicit_language_detection_is_preserved():
    service = ContextService()
    assert service._detect_language("Build a TypeScript API") == "TypeScript"
    assert service._detect_language("Build a JavaScript API") == "JavaScript"
