"""Deterministic paper-trading ledger. This service never routes real orders."""
from datetime import datetime, timezone
from pathlib import Path
import math
import re
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class PaperTradingService:
    MAX_TRADES = 5000
    DEFAULT_CASH = 100000.0

    def __init__(self, path: str | Path = "memory/paper_trading.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": 1, "initial_cash": self.DEFAULT_CASH, "cash": self.DEFAULT_CASH, "positions": {}, "trades": []})

    @staticmethod
    def _number(value, name, allow_zero=False):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite number")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite number") from None
        if not math.isfinite(number) or (number < 0 if allow_zero else number <= 0):
            raise ValueError(f"{name} must be {'non-negative' if allow_zero else 'positive'} and finite")
        return number

    @staticmethod
    def _symbol(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9._&^=-]{0,23}", value.strip().upper()):
            raise ValueError("symbol is invalid")
        return value.strip().upper()

    @staticmethod
    def _validate(data):
        if (not isinstance(data, dict) or data.get("schema_version") != 1
                or not isinstance(data.get("positions"), dict) or not isinstance(data.get("trades"), list)
                or len(data["trades"]) > PaperTradingService.MAX_TRADES):
            raise PersistenceIntegrityError("Paper-trading ledger schema is invalid")
        for key in ("cash", "initial_cash"):
            if isinstance(data.get(key), bool) or not isinstance(data.get(key), (int, float)) or not math.isfinite(data[key]) or data[key] < 0:
                raise PersistenceIntegrityError("Paper-trading cash balance is invalid")
        return data

    def execute(self, symbol, side, quantity, price, fee_bps=10, exchange="NSE"):
        symbol = self._symbol(symbol)
        side = str(side).lower() if isinstance(side, str) else ""
        exchange = str(exchange).upper()
        if exchange not in {"NSE", "BSE", "NASDAQ", "NYSE", "CRYPTO", "OTHER"}:
            raise ValueError("exchange is unsupported")
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        quantity = self._number(quantity, "quantity")
        price = self._number(price, "price")
        fee_bps = self._number(fee_bps, "fee_bps", allow_zero=True)
        if fee_bps > 500:
            raise ValueError("fee_bps cannot exceed 500")
        key = f"{exchange}:{symbol}"
        result = {}

        def update(data):
            self._validate(data)
            if len(data["trades"]) >= self.MAX_TRADES:
                raise ValueError("paper-trading ledger retention limit reached")
            positions = data["positions"]
            current = positions.get(key, {"symbol": symbol, "exchange": exchange, "quantity": 0.0, "average_cost": 0.0})
            notional = quantity * price
            fee = notional * fee_bps / 10000
            if side == "buy":
                total_cost = notional + fee
                if total_cost > data["cash"] + 1e-9:
                    raise ValueError("insufficient paper cash for this simulated buy")
                old_qty = float(current["quantity"])
                new_qty = old_qty + quantity
                current["average_cost"] = ((old_qty * float(current["average_cost"])) + total_cost) / new_qty
                current["quantity"] = new_qty
                data["cash"] -= total_cost
                realized = 0.0
            else:
                old_qty = float(current["quantity"])
                if quantity > old_qty + 1e-9:
                    raise ValueError("paper sell quantity exceeds the held position")
                average_cost = float(current["average_cost"])
                proceeds = notional - fee
                realized = proceeds - quantity * average_cost
                data["cash"] += proceeds
                current["quantity"] = max(0.0, old_qty - quantity)
                if current["quantity"] <= 1e-9:
                    current = {"symbol": symbol, "exchange": exchange, "quantity": 0.0, "average_cost": 0.0}
            positions[key] = current
            trade = {
                "trade_id": str(uuid4()), "symbol": symbol, "exchange": exchange, "side": side,
                "quantity": quantity, "price": price, "notional": notional, "fee": fee,
                "realized_pnl": realized, "cash_after": data["cash"],
                "created_at": datetime.now(timezone.utc).isoformat(), "mode": "paper_only",
            }
            data["trades"].append(trade)
            result.update(trade)
        self.store.update(update, {"schema_version": 1, "initial_cash": self.DEFAULT_CASH, "cash": self.DEFAULT_CASH, "positions": {}, "trades": []})
        return result

    def summary(self):
        data = self._validate(self.store.read({"schema_version": 1, "initial_cash": self.DEFAULT_CASH, "cash": self.DEFAULT_CASH, "positions": {}, "trades": []}))
        return {
            "success": True, "mode": "paper_only", "initial_cash": data["initial_cash"], "cash": data["cash"],
            "positions": list(data["positions"].values()), "trade_count": len(data["trades"]),
            "realized_pnl": sum(float(x.get("realized_pnl", 0)) for x in data["trades"]),
            "warning": "Simulated ledger only. No broker, exchange, live order or real money is connected.",
        }

    def trades(self, limit=100):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 500:
            raise ValueError("limit must be between 0 and 500")
        data = self._validate(self.store.read({"schema_version": 1, "initial_cash": self.DEFAULT_CASH, "cash": self.DEFAULT_CASH, "positions": {}, "trades": []}))
        return list(reversed(data["trades"][-limit:])) if limit else []
