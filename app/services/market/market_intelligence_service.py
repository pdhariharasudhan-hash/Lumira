"""Kronos: deterministic analysis of user-imported market data."""
from datetime import date, datetime, timezone
from pathlib import Path
import math
import re
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class MarketIntelligenceService:
    MAX_CANDLES = 5000
    EXCHANGES = {"NSE", "BSE", "NASDAQ", "NYSE", "CRYPTO", "OTHER"}

    def __init__(self, path: str | Path = "memory/market_intelligence.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})

    @staticmethod
    def symbol(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9._&^=-]{0,23}", value.strip().upper()):
            raise ValueError("symbol must be 1-24 valid exchange ticker characters")
        return value.strip().upper()

    @staticmethod
    def number(value, name, positive=True):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite {'positive' if positive else 'non-negative'} number")
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite number") from None
        if not math.isfinite(result) or (result <= 0 if positive else result < 0):
            raise ValueError(f"{name} must be a finite {'positive' if positive else 'non-negative'} number")
        return result

    def read(self):
        data = self.store.read({"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not all(isinstance(data.get(k), t) for k, t in (("watchlist", list), ("holdings", list), ("history", dict))):
            raise PersistenceIntegrityError("Market intelligence store has an invalid schema")
        return data

    def add_watchlist(self, symbol, exchange="NSE", notes=""):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        if exchange not in self.EXCHANGES or not isinstance(notes, str) or len(notes) > 500:
            raise ValueError("invalid exchange or notes")
        item = {"symbol": symbol, "exchange": exchange, "notes": notes.strip(), "added_at": datetime.now(timezone.utc).isoformat()}
        def update(data):
            self.read_validate(data)
            old = next((x for x in data["watchlist"] if x["symbol"] == symbol and x["exchange"] == exchange), None)
            if old:
                old["notes"] = item["notes"]
                return dict(old)
            if len(data["watchlist"]) >= 300:
                raise ValueError("watchlist limit reached")
            data["watchlist"].append(item)
            return item
        return self.store.update(update, {"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})

    @staticmethod
    def read_validate(data):
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("watchlist"), list) or not isinstance(data.get("holdings"), list) or not isinstance(data.get("history"), dict):
            raise PersistenceIntegrityError("Market intelligence store has an invalid schema")

    def list_watchlist(self):
        return self.read()["watchlist"]

    def remove_watchlist(self, symbol, exchange="NSE"):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        result = {"removed": False}
        def update(data):
            self.read_validate(data)
            before = len(data["watchlist"])
            data["watchlist"] = [x for x in data["watchlist"] if (x["symbol"], x["exchange"]) != (symbol, exchange)]
            result["removed"] = before != len(data["watchlist"])
        self.store.update(update, {"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})
        return result["removed"]

    def add_holding(self, symbol, quantity, average_price, exchange="NSE"):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        if exchange not in self.EXCHANGES:
            raise ValueError("unsupported exchange")
        item = {"symbol": symbol, "exchange": exchange, "quantity": self.number(quantity, "quantity"),
                "average_price": self.number(average_price, "average_price"), "updated_at": datetime.now(timezone.utc).isoformat()}
        def update(data):
            self.read_validate(data)
            old = next((x for x in data["holdings"] if (x["symbol"], x["exchange"]) == (symbol, exchange)), None)
            if old:
                old.update(item)
                return dict(old)
            if len(data["holdings"]) >= 500:
                raise ValueError("portfolio holding limit reached")
            data["holdings"].append(item)
            return item
        return self.store.update(update, {"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})

    def list_holdings(self):
        return self.read()["holdings"]

    def import_candles(self, symbol, candles, exchange="NSE", source="user_import"):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        if exchange not in self.EXCHANGES or not isinstance(candles, list) or not 1 <= len(candles) <= self.MAX_CANDLES:
            raise ValueError(f"provide 1-{self.MAX_CANDLES} candles and a supported exchange")
        rows, seen = [], set()
        for row in candles:
            if not isinstance(row, dict):
                raise ValueError("each candle must be an object")
            try:
                day = date.fromisoformat(row.get("date", "")[:10]).isoformat()
            except (ValueError, TypeError, AttributeError):
                raise ValueError("candle date must use YYYY-MM-DD") from None
            if day in seen:
                raise ValueError("duplicate candle date")
            seen.add(day)
            o, h, l, c = (self.number(row.get(k), k) for k in ("open", "high", "low", "close"))
            v = self.number(row.get("volume", 0), "volume", positive=False)
            if h < max(o, c, l) or l > min(o, c, h):
                raise ValueError(f"inconsistent OHLC values for {day}")
            rows.append({"date": day, "open": o, "high": h, "low": l, "close": c, "volume": v})
        rows.sort(key=lambda x: x["date"])
        key = f"{exchange}:{symbol}"
        if not isinstance(source, str) or not source.strip() or len(source) > 120:
            raise ValueError("source must contain 1-120 characters")
        record = {"symbol": symbol, "exchange": exchange, "candles": rows, "source": source.strip(), "updated_at": datetime.now(timezone.utc).isoformat()}
        def update(data):
            self.read_validate(data)
            data["history"][key] = record
        self.store.update(update, {"schema_version": 1, "watchlist": [], "holdings": [], "history": {}})
        return {"success": True, "symbol": symbol, "exchange": exchange, "count": len(rows), "from": rows[0]["date"], "to": rows[-1]["date"], "source": source.strip()}

    def candles(self, symbol, exchange="NSE"):
        key = f"{exchange.strip().upper()}:{self.symbol(symbol)}"
        return self.read()["history"].get(key, {}).get("candles", [])

    @staticmethod
    def sma(values, period):
        return sum(values[-period:]) / period if len(values) >= period else None

    @staticmethod
    def ema(values, period):
        if len(values) < period:
            return []
        out = [None] * (period - 1)
        current = sum(values[:period]) / period
        out.append(current)
        alpha = 2 / (period + 1)
        for value in values[period:]:
            current = value * alpha + current * (1 - alpha)
            out.append(current)
        return out

    def analyze(self, symbol, exchange="NSE"):
        rows = self.candles(symbol, exchange)
        if not rows:
            return {"success": False, "code": "history_unavailable", "message": "Import verified OHLCV data before analysis."}
        closes = [x["close"] for x in rows]
        s20, s50 = self.sma(closes, 20), self.sma(closes, 50)
        std = math.sqrt(sum((x - s20) ** 2 for x in closes[-20:]) / 20) if s20 is not None else None
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains, losses = [max(x, 0) for x in changes], [max(-x, 0) for x in changes]
        rsi = None
        if len(changes) >= 14:
            ag, al = sum(gains[:14])/14, sum(losses[:14])/14
            for i in range(14, len(changes)):
                ag, al = (ag*13+gains[i])/14, (al*13+losses[i])/14
            rsi = 100.0 if al == 0 and ag > 0 else 50.0 if al == 0 else 100 - 100/(1+ag/al)
        e12, e26 = self.ema(closes, 12), self.ema(closes, 26)
        macd = [a-b for a,b in zip(e12,e26) if a is not None and b is not None]
        signal = self.ema(macd, 9)
        macd_value = macd[-1] if macd else None
        signal_value = signal[-1] if signal else None
        true_ranges = []
        for i, row in enumerate(rows):
            prev = closes[i-1] if i else closes[i]
            true_ranges.append(max(row["high"]-row["low"], abs(row["high"]-prev), abs(row["low"]-prev)))
        atr = sum(true_ranges[-14:])/14 if len(true_ranges) >= 14 else None
        trend = "insufficient_history" if s20 is None or s50 is None else "bullish" if closes[-1] > s20 > s50 else "bearish" if closes[-1] < s20 < s50 else "mixed"
        source = self.read()["history"].get(f"{exchange.strip().upper()}:{self.symbol(symbol)}", {}).get("source", "unknown")
        return {"success": True, "symbol": self.symbol(symbol), "exchange": exchange.upper(), "source": source,
                "as_of": rows[-1]["date"], "observations": len(rows), "last_close": closes[-1],
                "change_percent": (closes[-1]/closes[-2]-1)*100 if len(closes)>1 else None,
                "sma_20": s20, "sma_50": s50, "rsi_14": rsi, "macd": macd_value, "macd_signal": signal_value,
                "macd_histogram": macd_value-signal_value if macd_value is not None and signal_value is not None else None,
                "bollinger_20": {"middle": s20, "upper": s20+2*std if std is not None else None, "lower": s20-2*std if std is not None else None},
                "atr_14": atr, "trend": trend, "disclaimer": "Historical technical indicators are not forecasts or investment advice."}

    def portfolio_summary(self):
        items, invested, value = [], 0.0, 0.0
        for holding in self.list_holdings():
            cost = holding["quantity"]*holding["average_price"]
            history = self.candles(holding["symbol"], holding["exchange"])
            last = history[-1]["close"] if history else None
            current = holding["quantity"]*last if last is not None else None
            invested += cost
            if current is not None:
                value += current
            items.append({**holding, "invested_value": cost, "last_close": last, "market_value": current,
                          "unrealized_pnl": current-cost if current is not None else None,
                          "quote_status": "historical_data_available" if current is not None else "missing_historical_data"})
        return {"success": True, "holdings": items, "invested_value": invested, "priced_market_value": value,
                "priced_unrealized_pnl": value-sum(x["invested_value"] for x in items if x["market_value"] is not None),
                "note": "Valuation uses the last imported close, not a live quote."}

    def backtest(self, symbol, exchange="NSE", fast=20, slow=50, capital=100000, fee_bps=10, slippage_bps=5):
        symbol = self.symbol(symbol)
        if isinstance(fast, bool) or isinstance(slow, bool) or not isinstance(fast, int) or not isinstance(slow, int) or not 2 <= fast < slow <= 250:
            raise ValueError("periods must satisfy 2 <= fast < slow <= 250")
        capital = self.number(capital, "capital")
        fee, slip = self.number(fee_bps, "fee_bps", False)/10000, self.number(slippage_bps, "slippage_bps", False)/10000
        rows = self.candles(symbol, exchange)
        if len(rows) < slow+1:
            raise ValueError(f"at least {slow+1} candles are required")
        closes = [x["close"] for x in rows]
        cash, units, entry, trades, equity = capital, 0.0, None, [], []
        for i, price in enumerate(closes):
            f = sum(closes[i-fast+1:i+1])/fast if i+1 >= fast else None
            s = sum(closes[i-slow+1:i+1])/slow if i+1 >= slow else None
            if f is not None and s is not None:
                if units == 0 and f > s:
                    px = price*(1+slip); units = cash/(px*(1+fee)); cash -= units*px*(1+fee)
                    entry = {"date": rows[i]["date"], "price": px}
                elif units and f <= s:
                    px = price*(1-slip); proceeds = units*px*(1-fee)
                    trades.append({"entry": entry, "exit": {"date": rows[i]["date"], "price": px}, "units": units, "pnl": proceeds-entry["price"]*units})
                    cash += proceeds; units, entry = 0.0, None
            equity.append(cash+units*price)
        if units:
            px = closes[-1]*(1-slip); proceeds = units*px*(1-fee)
            trades.append({"entry": entry, "exit": {"date": rows[-1]["date"], "price": px, "note": "end_of_test"}, "units": units, "pnl": proceeds-entry["price"]*units})
            cash += proceeds
        peak, drawdown = equity[0], 0.0
        for amount in equity:
            peak = max(peak, amount)
            drawdown = max(drawdown, (peak-amount)/peak if peak else 0)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        return {"success": True, "strategy": "long_only_sma_crossover", "symbol": symbol, "exchange": exchange.upper(),
                "parameters": {"fast_sma": fast, "slow_sma": slow, "capital": capital, "fee_bps": fee_bps, "slippage_bps": slippage_bps},
                "period": {"from": rows[0]["date"], "to": rows[-1]["date"], "observations": len(rows)},
                "metrics": {"final_value": cash, "net_return_percent": (cash/capital-1)*100, "max_drawdown_percent": drawdown*100,
                            "closed_trades": len(trades), "win_rate_percent": wins/len(trades)*100 if trades else 0},
                "trades": trades, "assumptions": ["long-only; no leverage or shorting", "signals use closing prices",
                "fees and slippage modeled in basis points", "taxes, dividends, corporate actions and market impact excluded"],
                "disclaimer": "Historical simulation only; not a forecast or investment advice."}

    def fetch_history(self, symbol, exchange="NSE", period="1y", interval="1d"):
        from app.services.providers.provider_registry import ProviderRegistry
        from app.services.providers.provider_access_policy_service import ProviderAccessPolicyService, ProviderAccessDenied
        ticker = self.symbol(symbol)
        exchange = exchange.strip().upper()
        if exchange not in self.EXCHANGES:
            raise ValueError("unsupported exchange")
        provider = ProviderRegistry.get("market_data")
        if provider is None:
            return {"success": False, "code": "market_provider_unavailable", "message": "Enable LUMIRA_MARKET_DATA_ENABLED and restart Lumira to configure the optional Yahoo market-data adapter."}
        provider_policy = ProviderAccessPolicyService()
        try:
            provider_policy.authorize(provider, "market data retrieval")
        except ProviderAccessDenied as exc:
            return {"success": False, "code": exc.code, "message": exc.user_message}
        remote_symbol = ticker
        if exchange == "NSE" and not ticker.startswith("^") and not ticker.endswith(".NS"):
            remote_symbol = ticker + ".NS"
        elif exchange == "BSE" and not ticker.startswith("^") and not ticker.endswith(".BO"):
            remote_symbol = ticker + ".BO"
        if interval not in {"1d", "1wk", "1mo"}:
            raise ValueError("Kronos currently stores daily, weekly or monthly candles only")
        try:
            result = provider.fetch_history(remote_symbol, period, interval)
        except Exception:
            return {"success": False, "code": "market_provider_error", "message": "The market-data provider failed or was unavailable; no new quote history was stored."}
        candles = result.get("candles") if isinstance(result, dict) else None
        if not isinstance(candles, list) or not candles:
            return {"success": False, "code": "market_history_empty", "message": "The provider returned no usable candles."}
        imported = self.import_candles(ticker, candles, exchange, source=str(result.get("source", "external_provider"))[:120])
        return {"success": True, "import": imported, "provider": result.get("source"),
                "currency": result.get("currency"), "market_state": result.get("market_state"),
                "fetched_at": result.get("fetched_at"), "data_note": result.get("disclaimer")}

    def save_fundamentals(self, symbol, metrics, exchange="NSE", as_of=None, source="user_entered"):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        allowed = {"eps", "pe", "debt_to_equity", "roe_percent", "revenue_growth_percent", "profit_margin_percent", "market_cap"}
        if exchange not in self.EXCHANGES or not isinstance(metrics, dict) or not metrics or set(metrics) - allowed:
            raise ValueError("provide supported fundamental metrics and exchange")
        cleaned = {}
        for key, value in metrics.items():
            if isinstance(value, bool):
                raise ValueError(f"{key} must be a finite number")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be a finite number") from None
            if not math.isfinite(number):
                raise ValueError(f"{key} must be finite")
            cleaned[key] = number
        date_value = as_of or datetime.now(timezone.utc).date().isoformat()
        try:
            date.fromisoformat(date_value)
        except (TypeError, ValueError):
            raise ValueError("as_of must use YYYY-MM-DD") from None
        record = {"symbol": symbol, "exchange": exchange, "metrics": cleaned, "as_of": date_value,
                  "source": str(source)[:120], "updated_at": datetime.now(timezone.utc).isoformat()}
        store = AtomicJsonStore("memory/market_fundamentals.json")
        def update(data):
            if not isinstance(data, dict) or data.get("schema_version", 1) != 1 or not isinstance(data.get("records", {}), dict):
                raise PersistenceIntegrityError("Fundamental store schema is invalid")
            data["schema_version"] = 1
            data.setdefault("records", {})[f"{exchange}:{symbol}"] = record
        store.update(update, {"schema_version": 1, "records": {}})
        return {"success": True, "record": record}

    def fundamental_analysis(self, symbol, exchange="NSE"):
        symbol, exchange = self.symbol(symbol), exchange.strip().upper()
        store = AtomicJsonStore("memory/market_fundamentals.json")
        data = store.read({"schema_version": 1, "records": {}})
        record = data.get("records", {}).get(f"{exchange}:{symbol}") if isinstance(data, dict) else None
        if not isinstance(record, dict):
            return {"success": False, "code": "fundamentals_unavailable", "message": "No fundamentals have been imported for this symbol."}
        return {"success": True, **record,
                "interpretation": "Raw reported metrics only. Compare companies within the same industry and reporting period; no buy/sell verdict is generated.",
                "missing_metrics": sorted({"eps", "pe", "debt_to_equity", "roe_percent", "revenue_growth_percent", "profit_margin_percent"} - set(record.get("metrics", {})))}

    def compare_fundamental_peers(self, symbols, exchange="NSE"):
        if not isinstance(symbols, list) or not 2 <= len(symbols) <= 20:
            raise ValueError("peer comparison requires 2-20 symbols")
        records = [self.fundamental_analysis(item, exchange) for item in symbols]
        available = [item for item in records if item.get("success")]
        metrics = {}
        for field in ("pe", "roe_percent", "debt_to_equity", "revenue_growth_percent", "profit_margin_percent"):
            values = [item["metrics"][field] for item in available if field in item.get("metrics", {})]
            metrics[field] = {"peer_average": sum(values)/len(values) if values else None, "reported_count": len(values)}
        return {"success": True, "exchange": exchange.upper(), "peers": records, "group_averages": metrics,
                "note": "Peer averages are descriptive only; confirm industry comparability and source dates."}

    def scan_watchlist(self):
        results = []
        for item in self.list_watchlist():
            analysis = self.analyze(item["symbol"], item["exchange"])
            results.append({"symbol": item["symbol"], "exchange": item["exchange"], "analysis": analysis})
        return {"success": True, "scanned": len(results), "results": results,
                "note": "Scanner only evaluates stored historical data; missing histories are not inferred."}

    def position_risk(self, account_value, risk_percent, entry_price, stop_price, side="long"):
        account = self.number(account_value, "account_value")
        risk = self.number(risk_percent, "risk_percent")
        entry = self.number(entry_price, "entry_price")
        stop = self.number(stop_price, "stop_price")
        if risk > 5:
            raise ValueError("risk_percent must be at most 5 percent")
        if side not in {"long", "short"}:
            raise ValueError("side must be long or short")
        if (side == "long" and stop >= entry) or (side == "short" and stop <= entry):
            raise ValueError("stop_price must be below entry for long positions and above entry for short positions")
        per_unit = abs(entry - stop)
        risk_budget = account * risk / 100
        units = risk_budget / per_unit
        return {"success": True, "side": side, "risk_budget": risk_budget, "risk_per_unit": per_unit,
                "maximum_units_by_risk": units, "estimated_position_notional": units * entry,
                "notional_as_percent_of_account": (units * entry / account) * 100,
                "note": "Risk sizing is a mathematical estimate; gaps, slippage, fees, liquidity and execution may cause larger losses. Not investment advice."}

    def detect_patterns(self, symbol, exchange="NSE"):
        """Describe simple candle geometry; these are not predictive trading signals."""
        rows = self.candles(symbol, exchange)
        if not rows:
            return {"success": False, "code": "history_unavailable", "message": "Import OHLCV history before pattern analysis."}
        found = []
        for index, row in enumerate(rows):
            body = abs(row["close"] - row["open"])
            span = max(row["high"] - row["low"], 1e-12)
            upper = row["high"] - max(row["open"], row["close"])
            lower = min(row["open"], row["close"]) - row["low"]
            previous = rows[index - 1] if index else None
            label = None
            if body / span <= 0.1:
                label = "doji"
            elif lower >= body * 2 and upper <= max(body * 0.5, span * 0.03) and body / span <= 0.35:
                label = "hammer_like" if row["close"] >= row["open"] else "hanging_man_like"
            elif upper >= body * 2 and lower <= max(body * 0.5, span * 0.03) and body / span <= 0.35:
                label = "inverted_hammer_like" if row["close"] >= row["open"] else "shooting_star_like"
            if previous:
                if row["low"] > previous["high"]:
                    found.append({"date": row["date"], "pattern": "gap_up", "description": "Current low is above previous high."})
                elif row["high"] < previous["low"]:
                    found.append({"date": row["date"], "pattern": "gap_down", "description": "Current high is below previous low."})
                prev_bear = previous["close"] < previous["open"]
                prev_bull = previous["close"] > previous["open"]
                curr_bull = row["close"] > row["open"]
                curr_bear = row["close"] < row["open"]
                if prev_bear and curr_bull and row["open"] <= previous["close"] and row["close"] >= previous["open"]:
                    found.append({"date": row["date"], "pattern": "bullish_engulfing", "description": "Current real body engulfs previous bearish real body."})
                elif prev_bull and curr_bear and row["open"] >= previous["close"] and row["close"] <= previous["open"]:
                    found.append({"date": row["date"], "pattern": "bearish_engulfing", "description": "Current real body engulfs previous bullish real body."})
            if label:
                found.append({"date": row["date"], "pattern": label, "description": "Single-candle shape heuristic; context is not assessed."})
        return {"success": True, "symbol": self.symbol(symbol), "exchange": exchange.upper(),
                "observations": len(rows), "patterns": found[-200:],
                "disclaimer": "Descriptive OHLC geometry only. Pattern labels are heuristic, not validated signals, predictions or investment advice."}
