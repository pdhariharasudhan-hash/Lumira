"""Optional public Yahoo Finance chart adapter. Network access is policy-gated by callers."""
from datetime import datetime, timezone
import requests


class YahooMarketDataProvider:
    provider_scope = "external"
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def fetch_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> dict:
        allowed_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"}
        allowed_intervals = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}
        if period not in allowed_periods or interval not in allowed_intervals:
            raise ValueError("unsupported history period or interval")
        response = requests.get(self.BASE_URL + requests.utils.quote(symbol, safe="^=.-"), params={"range": period, "interval": interval}, headers={"User-Agent": "Lumira/1.0"}, timeout=(3, 10))
        response.raise_for_status()
        payload = response.json()
        result = payload.get("chart", {}).get("result")
        if not isinstance(result, list) or not result:
            raise ValueError("market provider returned no quote history")
        item = result[0]
        timestamps = item.get("timestamp") or []
        quote = (item.get("indicators", {}).get("quote") or [{}])[0]
        candles = []
        for index, stamp in enumerate(timestamps):
            values = [quote.get(key, [None] * len(timestamps))[index] for key in ("open", "high", "low", "close", "volume")]
            if any(v is None for v in values[:4]):
                continue
            candles.append({"date": datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
                            "open": values[0], "high": values[1], "low": values[2], "close": values[3], "volume": values[4] or 0})
        meta = item.get("meta", {})
        return {"success": True, "symbol": meta.get("symbol", symbol), "currency": meta.get("currency"),
                "exchange": meta.get("fullExchangeName"), "market_state": meta.get("marketState"),
                "fetched_at": datetime.now(timezone.utc).isoformat(), "candles": candles,
                "source": "Yahoo Finance chart endpoint", "disclaimer": "Provider data may be delayed, adjusted, incomplete or rate-limited."}
