from app.services.market.market_intelligence_service import MarketIntelligenceService
from app.services.creator.creator_os_service import CreatorOSService
from app.services.providers.provider_registry import ProviderRegistry


def test_pattern_scan_finds_doji_and_engulfing(tmp_path):
    service = MarketIntelligenceService(tmp_path / "market.json")
    service.import_candles("TEST", [
        {"date": "2026-01-01", "open": 10, "high": 11, "low": 8, "close": 9, "volume": 100},
        {"date": "2026-01-02", "open": 8.5, "high": 11, "low": 8, "close": 10.5, "volume": 120},
        {"date": "2026-01-03", "open": 10, "high": 11, "low": 9, "close": 10.02, "volume": 90},
    ])
    result = service.detect_patterns("TEST")
    labels = {item["pattern"] for item in result["patterns"]}
    assert "bullish_engulfing" in labels
    assert "doji" in labels
    assert "not validated signals" in result["disclaimer"]


def test_video_generation_fails_closed_without_provider(monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "get", staticmethod(lambda name: None))
    result = CreatorOSService().generate_video("A short product introduction")
    assert result["success"] is False
    assert result["code"] == "video_provider_unavailable"
