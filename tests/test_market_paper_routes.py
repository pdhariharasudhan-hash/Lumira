from fastapi.testclient import TestClient
from app.main import app


def test_paper_trade_api_is_simulation_only_and_persists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    summary = client.get("/market/paper/portfolio")
    assert summary.status_code == 200
    assert summary.json()["mode"] == "paper_only"
    trade = client.post("/market/paper/trades", json={
        "symbol": "ABC", "exchange": "NSE", "side": "buy",
        "quantity": 2, "price": 50, "fee_bps": 10,
    })
    assert trade.status_code == 200
    assert trade.json()["mode"] == "paper_only"
    assert trade.json()["trade"]["mode"] == "paper_only"
    assert client.get("/market/paper/trades").json()["trades"][0]["symbol"] == "ABC"


def test_paper_trade_api_rejects_oversell(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/market/paper/trades", json={
        "symbol": "ABC", "exchange": "NSE", "side": "sell",
        "quantity": 1, "price": 10,
    })
    assert response.status_code == 422
