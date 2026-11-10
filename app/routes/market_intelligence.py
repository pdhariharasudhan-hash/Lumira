from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from typing import Any
from app.services.market.market_intelligence_service import MarketIntelligenceService
from app.services.market.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/market", tags=["Kronos Market Intelligence"])
service = MarketIntelligenceService()
paper_trading = PaperTradingService()


class WatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    notes: str = Field(default="", max_length=500)


class HoldingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    average_price: float = Field(gt=0, allow_inf_nan=False)


class CandleImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    candles: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    fast: int = Field(default=20, ge=2, le=249)
    slow: int = Field(default=50, ge=3, le=250)
    capital: float = Field(default=100000, gt=0, allow_inf_nan=False)
    fee_bps: float = Field(default=10, ge=0, allow_inf_nan=False)
    slippage_bps: float = Field(default=5, ge=0, allow_inf_nan=False)


def _call(fn):
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class PaperTradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    side: str = Field(pattern=r"^(buy|sell)$")
    quantity: float = Field(gt=0, allow_inf_nan=False)
    price: float = Field(gt=0, allow_inf_nan=False)
    fee_bps: float = Field(default=10, ge=0, le=500, allow_inf_nan=False)


@router.get("/paper/portfolio")
def paper_portfolio():
    return paper_trading.summary()


@router.get("/paper/trades")
def paper_trade_history(limit: int = Query(default=100, ge=0, le=500)):
    return {"success": True, "mode": "paper_only", "trades": paper_trading.trades(limit)}


@router.post("/paper/trades")
def execute_paper_trade(request: PaperTradeRequest):
    return {"success": True, "mode": "paper_only", "trade": _call(lambda: paper_trading.execute(**request.model_dump()))}


@router.get("/status")
def market_status():
    from app.services.providers.provider_registry import ProviderRegistry
    provider = ProviderRegistry.get("market_data")
    return {"success": True, "name": "Kronos", "capabilities": ["watchlist", "portfolio", "OHLCV import", "fundamentals", "peer comparison", "SMA", "EMA", "RSI", "MACD", "Bollinger Bands", "ATR", "descriptive candle patterns", "watchlist scanner", "SMA crossover backtesting", "paper trading simulation"], "quote_provider": "yahoo_finance_optional" if provider is not None else "not_configured", "external_provider_policy_required": True, "data_policy": "Live/history retrieval requires an explicitly enabled adapter and external-provider consent; imported history remains available offline."}


@router.get("/watchlist")
def get_watchlist():
    return {"success": True, "watchlist": service.list_watchlist()}


@router.post("/watchlist")
def add_watchlist(request: WatchlistRequest):
    return {"success": True, "item": _call(lambda: service.add_watchlist(**request.model_dump()))}


@router.delete("/watchlist/{symbol}")
def remove_watchlist(symbol: str, exchange: str = Query(default="NSE", max_length=12)):
    return {"success": _call(lambda: service.remove_watchlist(symbol, exchange))}


@router.get("/portfolio")
def get_portfolio():
    return service.portfolio_summary()


@router.get("/portfolio/holdings")
def get_holdings():
    return {"success": True, "holdings": service.list_holdings()}


@router.post("/portfolio/holdings")
def add_holding(request: HoldingRequest):
    return {"success": True, "holding": _call(lambda: service.add_holding(**request.model_dump()))}


@router.post("/history/import")
def import_history(request: CandleImportRequest):
    return _call(lambda: service.import_candles(**request.model_dump()))


@router.get("/history/{symbol}")
def get_history(symbol: str, exchange: str = Query(default="NSE", max_length=12)):
    return {"success": True, "symbol": symbol.upper(), "exchange": exchange.upper(), "candles": _call(lambda: service.candles(symbol, exchange))}


@router.get("/analysis/{symbol}")
def analyze_symbol(symbol: str, exchange: str = Query(default="NSE", max_length=12)):
    return _call(lambda: service.analyze(symbol, exchange))


@router.post("/backtest/sma-crossover")
def backtest(request: BacktestRequest):
    if request.fast >= request.slow:
        raise HTTPException(status_code=422, detail="fast period must be smaller than slow period")
    return _call(lambda: service.backtest(**request.model_dump()))

@router.post("/history/fetch/{symbol}")
def fetch_history(symbol: str, exchange: str = Query(default="NSE", max_length=12),
                  period: str = Query(default="1y", max_length=8), interval: str = Query(default="1d", max_length=4)):
    result = _call(lambda: service.fetch_history(symbol, exchange, period, interval))
    if result.get("code") == "market_provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if result.get("code") in {"external_provider_consent_required", "local_provider_blocked"}:
        raise HTTPException(status_code=403, detail=result)
    if result.get("code") in {"provider_policy_unavailable", "provider_policy_invalid"}:
        raise HTTPException(status_code=503, detail=result)
    if result.get("code") == "market_provider_error":
        raise HTTPException(status_code=502, detail=result)
    return result

class FundamentalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="NSE", max_length=12)
    metrics: dict[str, float]
    as_of: str | None = Field(default=None, max_length=10)
    source: str = Field(default="user_entered", max_length=120)


class PeerCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(min_length=2, max_length=20)
    exchange: str = Field(default="NSE", max_length=12)


@router.post("/fundamentals/import")
def import_fundamentals(request: FundamentalsRequest):
    return _call(lambda: service.save_fundamentals(**request.model_dump()))


@router.get("/fundamentals/{symbol}")
def fundamentals(symbol: str, exchange: str = Query(default="NSE", max_length=12)):
    return _call(lambda: service.fundamental_analysis(symbol, exchange))


@router.post("/fundamentals/peers")
def compare_peers(request: PeerCompareRequest):
    return _call(lambda: service.compare_fundamental_peers(**request.model_dump()))


@router.get("/scanner/watchlist")
def scan_watchlist():
    return service.scan_watchlist()


@router.get("/patterns/{symbol}")
def detect_patterns(symbol: str, exchange: str = Query(default="NSE", max_length=12)):
    return _call(lambda: service.detect_patterns(symbol, exchange))

class PositionRiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_value: float = Field(gt=0, allow_inf_nan=False)
    risk_percent: float = Field(gt=0, le=5, allow_inf_nan=False)
    entry_price: float = Field(gt=0, allow_inf_nan=False)
    stop_price: float = Field(gt=0, allow_inf_nan=False)
    side: str = Field(default="long", pattern=r"^(long|short)$")


@router.post("/risk/position-size")
def position_risk(request: PositionRiskRequest):
    return _call(lambda: service.position_risk(**request.model_dump()))
