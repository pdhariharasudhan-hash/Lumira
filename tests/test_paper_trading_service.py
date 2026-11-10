from app.services.market.paper_trading_service import PaperTradingService


def test_buy_sell_ledger_tracks_cash_and_realized_pnl(tmp_path):
    service = PaperTradingService(tmp_path / "paper.json")
    bought = service.execute("ABC", "buy", 10, 100, fee_bps=10)
    assert bought["mode"] == "paper_only"
    assert round(service.summary()["cash"], 2) == 98999.0
    sold = service.execute("ABC", "sell", 4, 120, fee_bps=10)
    assert round(sold["realized_pnl"], 2) == round((120 * 4 * .999) - (100.1 * 4), 2)
    summary = service.summary()
    assert summary["positions"][0]["quantity"] == 6
    assert summary["trade_count"] == 2
    assert "No broker" in summary["warning"]


def test_rejects_oversell_and_insufficient_cash(tmp_path):
    service = PaperTradingService(tmp_path / "paper.json")
    try:
        service.execute("ABC", "sell", 1, 10)
        assert False, "oversell should fail"
    except ValueError as exc:
        assert "exceeds" in str(exc)
    try:
        service.execute("ABC", "buy", 2000, 100)
        assert False, "overspend should fail"
    except ValueError as exc:
        assert "insufficient" in str(exc)


def test_persists_between_instances(tmp_path):
    path = tmp_path / "paper.json"
    PaperTradingService(path).execute("ABC", "buy", 2, 50)
    assert PaperTradingService(path).summary()["positions"][0]["quantity"] == 2
