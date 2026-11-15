"""Durable model health ledger and bounded circuit breaker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class ModelHealthService:
    MAX_MODELS = 100
    FAILURE_THRESHOLD = 3
    COOLDOWN_SECONDS = 120

    def __init__(self, storage_path: str = "memory/model_health.json"):
        self.store = AtomicJsonStore(storage_path)
        self.store.read_or_create({"schema_version": 1, "models": {}})

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _validate(cls, document: Any) -> dict[str, dict]:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("model health schema is invalid")
        models = document.get("models")
        if not isinstance(models, dict) or len(models) > cls.MAX_MODELS:
            raise PersistenceIntegrityError("model health registry is invalid")
        for model_id, item in models.items():
            if not isinstance(model_id, str) or not model_id or len(model_id) > 120:
                raise PersistenceIntegrityError("model health ID is invalid")
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("model health record is invalid")
            for key in ("success_count", "failure_count", "failure_streak"):
                value = item.get(key, 0)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise PersistenceIntegrityError("model health counters are invalid")
            average = item.get("average_latency_ms", 0.0)
            if isinstance(average, bool) or not isinstance(average, (int, float)) or average < 0:
                raise PersistenceIntegrityError("model health latency is invalid")
        return models

    def can_attempt(self, model_id: str) -> dict:
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120:
            return {"allowed": False, "code": "invalid_model_id"}
        try:
            document = self.store.read({"schema_version": 1, "models": {}})
            models = self._validate(document)
            record = models.get(model_id.strip(), {})
            disabled_until = record.get("disabled_until")
            if disabled_until:
                expiry = datetime.fromisoformat(disabled_until)
                if expiry.tzinfo is None:
                    raise ValueError("timezone required")
                if expiry.astimezone(timezone.utc) > self._now():
                    return {
                        "allowed": False,
                        "code": "model_circuit_open",
                        "retry_at": disabled_until,
                        "failure_streak": record.get("failure_streak", 0),
                    }
            return {"allowed": True, "code": "model_available", "health": dict(record)}
        except Exception:
            return {"allowed": False, "code": "model_health_unavailable"}

    def record(self, model_id: str, *, success: bool, latency_ms: float, error_code: str | None = None) -> dict:
        if (
            not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120
            or not isinstance(success, bool)
            or isinstance(latency_ms, bool) or not isinstance(latency_ms, (int, float))
            or not 0 <= latency_ms <= 600_000
        ):
            return {"success": False, "code": "invalid_model_health_record"}
        now = self._now()
        now_text = now.isoformat()

        def update(document):
            models = self._validate(document)
            if model_id.strip() not in models and len(models) >= self.MAX_MODELS:
                return {"error": "model_health_capacity_reached"}
            item = models.setdefault(model_id.strip(), {
                "success_count": 0,
                "failure_count": 0,
                "failure_streak": 0,
                "average_latency_ms": 0.0,
                "last_success": None,
                "last_failure": None,
                "last_error_code": None,
                "disabled_until": None,
            })
            previous_count = item["success_count"] + item["failure_count"]
            previous_average = float(item.get("average_latency_ms", 0.0))
            item["average_latency_ms"] = (
                (previous_average * previous_count + float(latency_ms)) / (previous_count + 1)
            )
            if success:
                item["success_count"] += 1
                item["failure_streak"] = 0
                item["last_success"] = now_text
                item["last_error_code"] = None
                item["disabled_until"] = None
            else:
                item["failure_count"] += 1
                item["failure_streak"] += 1
                item["last_failure"] = now_text
                item["last_error_code"] = str(error_code or "provider_failed")[:80]
                if item["failure_streak"] >= self.FAILURE_THRESHOLD:
                    item["disabled_until"] = (now + timedelta(seconds=self.COOLDOWN_SECONDS)).isoformat()
            item["updated_at"] = now_text
            return dict(item)

        try:
            result = self.store.update(update, {"schema_version": 1, "models": {}})
        except Exception:
            return {"success": False, "code": "model_health_storage_unavailable"}
        if isinstance(result, dict) and result.get("error"):
            return {"success": False, "code": result["error"]}
        return {"success": True, "health": result}

    def snapshot(self) -> dict:
        try:
            document = self.store.read({"schema_version": 1, "models": {}})
            models = self._validate(document)
            now = self._now()
            output = {}
            for model_id, record in models.items():
                disabled_until = record.get("disabled_until")
                open_circuit = False
                if disabled_until:
                    expiry = datetime.fromisoformat(disabled_until)
                    open_circuit = expiry.tzinfo is not None and expiry.astimezone(timezone.utc) > now
                output[model_id] = {**record, "circuit_open": open_circuit}
            return {"success": True, "models": output, "count": len(output)}
        except Exception:
            return {"success": False, "code": "model_health_unavailable", "models": {}, "count": 0}

    def reset(self, model_id: str, *, owner_confirmed: bool) -> dict:
        if owner_confirmed is not True:
            return {"success": False, "code": "explicit_owner_confirmation_required"}
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120:
            return {"success": False, "code": "invalid_model_id"}

        def clear(document):
            models = self._validate(document)
            record = models.get(model_id.strip())
            if record is None:
                return {"error": "model_not_found"}
            record["failure_streak"] = 0
            record["disabled_until"] = None
            record["last_error_code"] = None
            record["updated_at"] = self._now().isoformat()
            return dict(record)

        try:
            result = self.store.update(clear, {"schema_version": 1, "models": {}})
        except Exception:
            return {"success": False, "code": "model_health_storage_unavailable"}
        return {"success": "error" not in result, "health": result if "error" not in result else None, "code": result.get("error")}
