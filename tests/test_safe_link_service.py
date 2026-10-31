from app.services.links.safe_link_service import SafeLinkService

def test_public_https_link_is_allowed():
    result = SafeLinkService().validate("https://example.com/path")
    assert result["safe"] is True

def test_localhost_is_rejected():
    result = SafeLinkService().validate("http://localhost:8000")
    assert result["safe"] is False
