"""Read-only, validated configuration access for Lumira's Brain layer.

Configuration is captured from the process environment. The manager never
loads arbitrary files, mutates process environment, or exposes secret values
in its default diagnostic snapshot.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from threading import RLock
from typing import Any


class ConfigurationError(ValueError):
    """Raised when a configuration key or value violates its contract."""


class BrainConfig:
    """Thread-safe configuration snapshot with explicit parsing and redaction."""

    PREFIX = "LUMIRA_"
    SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
    FALSE_VALUES = frozenset({"0", "false", "no", "off", "disabled"})

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._source = environ
        self._lock = RLock()
        self._values: dict[str, str] = {}
        self.reload()

    @classmethod
    def _validate_key(cls, key: str) -> str:
        if not isinstance(key, str) or not re.fullmatch(r"LUMIRA_[A-Z0-9_]+", key):
            raise ConfigurationError("Configuration keys must use the LUMIRA_ namespace")
        return key

    @staticmethod
    def _is_secret(key: str) -> bool:
        upper = key.upper()
        return any(marker in upper for marker in BrainConfig.SECRET_MARKERS)

    def reload(self) -> None:
        """Refresh the snapshot; an injected mapping remains the source if supplied."""
        source = os.environ if self._source is None else self._source
        refreshed: dict[str, str] = {}
        for key, value in source.items():
            if not isinstance(key, str) or not key.startswith(self.PREFIX):
                continue
            self._validate_key(key)
            if not isinstance(value, str):
                raise ConfigurationError(f"Configuration value for {key} must be text")
            refreshed[key] = value
        with self._lock:
            self._values = refreshed

    def get(self, key: str, default: Any = None) -> Any:
        name = self._validate_key(key)
        with self._lock:
            return self._values.get(name, default)

    def require(self, key: str) -> str:
        value = self.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"Required configuration value is missing: {key}")
        return value.strip()

    def get_bool(self, key: str, default: bool = False) -> bool:
        if not isinstance(default, bool):
            raise ConfigurationError("Boolean configuration default must be bool")
        value = self.get(key)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in self.TRUE_VALUES:
            return True
        if normalized in self.FALSE_VALUES:
            return False
        raise ConfigurationError(f"Invalid boolean configuration value: {key}")

    def get_int(
        self,
        key: str,
        default: int | None = None,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int | None:
        if default is not None and (isinstance(default, bool) or not isinstance(default, int)):
            raise ConfigurationError("Integer configuration default must be an integer")
        value = self.get(key)
        if value is None:
            parsed = default
        else:
            try:
                if not re.fullmatch(r"[+-]?\d+", value.strip()):
                    raise ValueError
                parsed = int(value.strip())
            except ValueError as exc:
                raise ConfigurationError(f"Invalid integer configuration value: {key}") from exc
        if parsed is not None:
            if minimum is not None and parsed < minimum:
                raise ConfigurationError(f"Configuration value is below minimum: {key}")
            if maximum is not None and parsed > maximum:
                raise ConfigurationError(f"Configuration value exceeds maximum: {key}")
        return parsed

    def get_secret(self, key: str) -> str | None:
        name = self._validate_key(key)
        if not self._is_secret(name):
            raise ConfigurationError("get_secret may only be used for secret-designated keys")
        value = self.get(name)
        return value if isinstance(value, str) and value.strip() else None

    def snapshot(self, *, redact_secrets: bool = True) -> dict[str, str]:
        """Return a detached snapshot; secret-bearing keys are redacted by default."""
        if not isinstance(redact_secrets, bool):
            raise ConfigurationError("redact_secrets must be bool")
        with self._lock:
            values = dict(self._values)
        if redact_secrets:
            return {
                key: ("[REDACTED]" if self._is_secret(key) else value)
                for key, value in values.items()
            }
        return values
