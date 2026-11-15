"""Fail-closed policy and schema validation for Brain tool invocations.

This module decides whether a declared tool call is structurally valid and
whether it may proceed. It never executes tools or grants user approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import json
import math


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    code: str
    message: str
    requires_approval: bool = False
    normalized_arguments: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "message": self.message,
            "requires_approval": self.requires_approval,
            "normalized_arguments": self.normalized_arguments,
        }


class ToolExecutionPolicyService:
    """Validate tool manifests, arguments, permissions and bounded results."""

    MAX_TOOL_NAME = 128
    MAX_SCHEMA_BYTES = 32_768
    MAX_ARGUMENT_BYTES = 64_000
    MAX_RESULT_BYTES = 128_000
    MAX_DEPTH = 12
    MAX_PROPERTIES = 128
    ALLOWED_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
    HIGH_RISK_CAPABILITIES = {
        "filesystem.write", "filesystem.delete", "process.execute",
        "network.request", "device.command", "account.change",
        "message.send", "purchase", "payment",
    }

    def __init__(self, permissions: Mapping[str, bool] | None = None):
        self._permissions = {
            key.strip(): value
            for key, value in (permissions or {}).items()
            if isinstance(key, str) and key.strip()
        }

    @staticmethod
    def _json_size(value: Any) -> int:
        try:
            return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, OverflowError):
            return -1

    @classmethod
    def _validate_schema(cls, schema: Any, depth: int = 0) -> str | None:
        if depth > cls.MAX_DEPTH:
            return "schema_too_deep"
        if not isinstance(schema, dict):
            return "schema_must_be_object"
        kind = schema.get("type")
        if kind not in cls.ALLOWED_TYPES:
            return "unsupported_schema_type"
        type_keywords = {
            "object": {"properties", "required", "additionalProperties", "minProperties", "maxProperties"},
            "array": {"items", "minItems", "maxItems", "uniqueItems"},
            "string": {"minLength", "maxLength"},
            "integer": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
            "number": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
            "boolean": set(),
            "null": set(),
        }
        if set(schema) - ({"type", "enum"} | type_keywords[kind]):
            return "unsupported_schema_keyword"
        if "enum" in schema:
            choices = schema["enum"]
            if not isinstance(choices, list) or not choices or len(choices) > 256:
                return "invalid_schema_enum"
            if cls._json_size(choices) > cls.MAX_SCHEMA_BYTES:
                return "invalid_schema_enum"
            base_schema = dict(schema)
            base_schema.pop("enum", None)
            try:
                if any(not cls._matches(choice, base_schema) for choice in choices):
                    return "invalid_schema_enum_value"
            except (KeyError, TypeError, ValueError):
                return "invalid_schema_enum_value"
        if kind == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            if (
                not isinstance(properties, dict)
                or len(properties) > cls.MAX_PROPERTIES
                or any(not isinstance(key, str) or not key for key in properties)
            ):
                return "invalid_schema_properties"
            if not isinstance(required, list) or any(
                not isinstance(item, str) or item not in properties for item in required
            ) or len(required) != len(set(required)):
                return "invalid_schema_required"
            if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
                return "invalid_schema_additional_properties"
            for key in ("minProperties", "maxProperties"):
                if key in schema and (
                    isinstance(schema[key], bool) or not isinstance(schema[key], int)
                    or schema[key] < 0 or schema[key] > cls.MAX_PROPERTIES
                ):
                    return "invalid_schema_property_bound"
            if schema.get("minProperties", 0) > schema.get("maxProperties", cls.MAX_PROPERTIES):
                return "invalid_schema_property_bounds"
            for child in properties.values():
                error = cls._validate_schema(child, depth + 1)
                if error:
                    return error
        if kind == "array":
            if "items" not in schema:
                return "array_schema_requires_items"
            error = cls._validate_schema(schema["items"], depth + 1)
            if error:
                return error
        if kind == "string":
            for key in ("minLength", "maxLength"):
                if key in schema and (
                    isinstance(schema[key], bool) or not isinstance(schema[key], int)
                    or schema[key] < 0 or schema[key] > 100_000
                ):
                    return "invalid_string_bound"
            if schema.get("minLength", 0) > schema.get("maxLength", 100_000):
                return "invalid_string_bounds"
        if kind in {"integer", "number"}:
            for key in ("minimum", "maximum"):
                if key in schema and (
                    isinstance(schema[key], bool)
                    or not isinstance(schema[key], (int, float))
                    or not math.isfinite(schema[key])
                ):
                    return "invalid_numeric_bound"
            if schema.get("minimum", float("-inf")) > schema.get("maximum", float("inf")):
                return "invalid_numeric_bounds"
        if kind == "array":
            for key in ("minItems", "maxItems"):
                if key in schema and (
                    isinstance(schema[key], bool) or not isinstance(schema[key], int)
                    or schema[key] < 0 or schema[key] > 10_000
                ):
                    return "invalid_array_bound"
            if schema.get("minItems", 0) > schema.get("maxItems", 10_000):
                return "invalid_array_bounds"
            if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
                return "invalid_unique_items_flag"
        if kind in {"integer", "number"}:
            for key in ("exclusiveMinimum", "exclusiveMaximum", "multipleOf"):
                if key in schema and (
                    isinstance(schema[key], bool)
                    or not isinstance(schema[key], (int, float))
                    or not math.isfinite(schema[key])
                ):
                    return "invalid_numeric_bound"
            if "multipleOf" in schema and schema["multipleOf"] <= 0:
                return "invalid_numeric_multiple"
            lower = max(
                schema.get("minimum", float("-inf")),
                schema.get("exclusiveMinimum", float("-inf")),
            )
            upper = min(
                schema.get("maximum", float("inf")),
                schema.get("exclusiveMaximum", float("inf")),
            )
            if lower >= upper:
                return "invalid_numeric_bounds"
        return None

    @classmethod
    def _matches(cls, value: Any, schema: dict[str, Any], depth: int = 0) -> bool:
        if depth > cls.MAX_DEPTH:
            return False
        kind = schema["type"]
        if kind == "null":
            valid = value is None
        elif kind == "boolean":
            valid = isinstance(value, bool)
        elif kind == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "number":
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        elif kind == "string":
            valid = isinstance(value, str)
            if valid:
                valid = schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 100_000)
        elif kind == "array":
            valid = isinstance(value, list)
            if valid:
                valid = schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10_000)
                valid = valid and all(cls._matches(item, schema["items"], depth + 1) for item in value)
                if valid and schema.get("uniqueItems") is True:
                    try:
                        encoded = [json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False) for item in value]
                        valid = len(encoded) == len(set(encoded))
                    except (TypeError, ValueError, OverflowError):
                        valid = False
        else:
            valid = isinstance(value, dict)
            if valid:
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                valid = all(key in value for key in required)
                valid = valid and schema.get("minProperties", 0) <= len(value) <= schema.get("maxProperties", cls.MAX_PROPERTIES)
                if valid and schema.get("additionalProperties", False) is False:
                    valid = all(key in properties for key in value)
                if valid:
                    valid = all(
                        key not in properties or cls._matches(item, properties[key], depth + 1)
                        for key, item in value.items()
                    )
        if not valid:
            return False
        if kind == "number" and isinstance(value, float) and not math.isfinite(value):
            return False
        if "enum" in schema and value not in schema["enum"]:
            return False
        if kind in {"integer", "number"}:
            if "minimum" in schema and value < schema["minimum"]:
                return False
            if "maximum" in schema and value > schema["maximum"]:
                return False
            if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
                return False
            if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
                return False
            if "multipleOf" in schema:
                quotient = value / schema["multipleOf"]
                if not math.isclose(quotient, round(quotient), rel_tol=1e-9, abs_tol=1e-9):
                    return False
        return True

    def validate_manifest(self, manifest: Any) -> ToolPolicyDecision:
        if not isinstance(manifest, dict):
            return ToolPolicyDecision(False, "invalid_manifest", "Tool manifest must be an object.")
        name = manifest.get("name")
        capability = manifest.get("capability")
        schema = manifest.get("parameters")
        if "requires_approval" in manifest and not isinstance(manifest["requires_approval"], bool):
            return ToolPolicyDecision(False, "invalid_approval_flag", "Tool approval flag must be boolean.")
        if not isinstance(name, str) or not name.strip() or len(name) > self.MAX_TOOL_NAME:
            return ToolPolicyDecision(False, "invalid_tool_name", "Tool name is invalid.")
        if not isinstance(capability, str) or not capability.strip() or len(capability) > 128:
            return ToolPolicyDecision(False, "invalid_capability", "Tool capability is invalid.")
        if self._json_size(schema) < 0 or self._json_size(schema) > self.MAX_SCHEMA_BYTES:
            return ToolPolicyDecision(False, "schema_size_invalid", "Tool schema is malformed or too large.")
        error = self._validate_schema(schema)
        if error:
            return ToolPolicyDecision(False, error, "Tool parameter schema is invalid.")
        if schema.get("type") != "object":
            return ToolPolicyDecision(False, "parameters_must_be_object", "Tool parameters must use an object schema.")
        return ToolPolicyDecision(True, "manifest_valid", "Tool manifest is structurally valid.")

    def authorize(
        self,
        manifest: Any,
        arguments: Any,
        *,
        approval_id: str | None = None,
        session_id: str | None = None,
        approval_service: ToolApprovalService | None = None,
    ) -> ToolPolicyDecision:
        checked = self.validate_manifest(manifest)
        if not checked.allowed:
            return checked
        capability = manifest["capability"].strip()
        if self._permissions.get(capability) is not True:
            return ToolPolicyDecision(False, "permission_denied", "This tool capability has not been explicitly enabled.")
        size = self._json_size(arguments)
        if size < 0 or size > self.MAX_ARGUMENT_BYTES:
            return ToolPolicyDecision(False, "arguments_too_large", "Tool arguments are malformed or exceed the size limit.")
        schema = manifest["parameters"]
        if not isinstance(arguments, dict) or not self._matches(arguments, schema):
            return ToolPolicyDecision(False, "arguments_invalid", "Tool arguments do not match the declared schema.")
        requires_approval = capability in self.HIGH_RISK_CAPABILITIES or manifest.get("requires_approval") is True
        if requires_approval:
            if approval_service is None or not approval_id or not session_id:
                return ToolPolicyDecision(
                    False, "approval_required", "This action requires a matching one-time user approval.",
                    requires_approval=True,
                )
            approval = approval_service.consume(
                approval_id=approval_id,
                session_id=session_id,
                tool_name=manifest["name"].strip(),
                arguments=arguments,
            )
            if approval.get("allowed") is not True:
                return ToolPolicyDecision(
                    False, str(approval.get("code") or "approval_required"),
                    "A valid, unexpired approval for this exact action is required.",
                    requires_approval=True,
                )
        return ToolPolicyDecision(
            True, "authorized", "Tool invocation passed policy and schema checks.",
            requires_approval=requires_approval,
            normalized_arguments=dict(arguments),
        )

    def bound_result(self, result: Any) -> dict[str, Any]:
        """Return a bounded JSON-safe result envelope without executing or persisting it."""
        size = self._json_size(result)
        if size < 0:
            return {"success": False, "code": "invalid_tool_result", "result": None}
        if size > self.MAX_RESULT_BYTES:
            return {"success": False, "code": "tool_result_too_large", "result": None}
        return {"success": True, "code": "ok", "result": result, "size_bytes": size}


class ToolExecutionBudget:
    """Per-run call, payload and wall-clock budget for a tool executor."""

    def __init__(
        self,
        *,
        max_calls: int = 12,
        max_total_argument_bytes: int = 256_000,
        max_total_result_bytes: int = 512_000,
        timeout_seconds: float = 120.0,
    ):
        from threading import Event, RLock
        from time import monotonic

        for name, value, ceiling in (
            ("max_calls", max_calls, 100),
            ("max_total_argument_bytes", max_total_argument_bytes, 5_000_000),
            ("max_total_result_bytes", max_total_result_bytes, 10_000_000),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be between 1 and {ceiling}")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be numeric")
        if not 0 < float(timeout_seconds) <= 600:
            raise ValueError("timeout_seconds must be between 0 and 600 seconds")

        self.max_calls = max_calls
        self.max_total_argument_bytes = max_total_argument_bytes
        self.max_total_result_bytes = max_total_result_bytes
        self.deadline = monotonic() + float(timeout_seconds)
        self._calls = 0
        self._argument_bytes = 0
        self._result_bytes = 0
        self._cancelled = Event()
        self._lock = RLock()

    def cancel(self) -> None:
        self._cancelled.set()

    def _check_deadline(self) -> None:
        from time import monotonic

        if self._cancelled.is_set():
            raise RuntimeError("tool execution budget cancelled")
        if monotonic() >= self.deadline:
            raise RuntimeError("tool execution time budget exceeded")

    def begin_call(self, argument_bytes: int) -> dict[str, int]:
        if isinstance(argument_bytes, bool) or not isinstance(argument_bytes, int) or argument_bytes < 0:
            raise ValueError("argument_bytes must be a non-negative integer")
        with self._lock:
            self._check_deadline()
            if self._calls >= self.max_calls:
                raise RuntimeError("tool call budget exceeded")
            if self._argument_bytes + argument_bytes > self.max_total_argument_bytes:
                raise RuntimeError("tool argument budget exceeded")
            self._calls += 1
            self._argument_bytes += argument_bytes
            return self.snapshot()

    def record_result(self, result_bytes: int) -> dict[str, int]:
        if isinstance(result_bytes, bool) or not isinstance(result_bytes, int) or result_bytes < 0:
            raise ValueError("result_bytes must be a non-negative integer")
        with self._lock:
            self._check_deadline()
            if self._result_bytes + result_bytes > self.max_total_result_bytes:
                raise RuntimeError("tool result budget exceeded")
            self._result_bytes += result_bytes
            return self.snapshot()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self._calls,
                "max_calls": self.max_calls,
                "argument_bytes": self._argument_bytes,
                "max_argument_bytes": self.max_total_argument_bytes,
                "result_bytes": self._result_bytes,
                "max_result_bytes": self.max_total_result_bytes,
            }


class ToolApprovalService:
    """One-time, session-bound approvals that expire and cannot be replayed."""

    def __init__(self, ttl_seconds: int = 120, max_pending: int = 256):
        import threading
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 900:
            raise ValueError("ttl_seconds must be between 1 and 900")
        if isinstance(max_pending, bool) or not isinstance(max_pending, int) or not 1 <= max_pending <= 2048:
            raise ValueError("max_pending must be between 1 and 2048")
        self.ttl_seconds = ttl_seconds
        self.max_pending = max_pending
        self._lock = threading.RLock()
        self._pending: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _fingerprint(tool_name: str, arguments: dict[str, Any]) -> str:
        import hashlib
        payload = json.dumps(
            {"tool": tool_name, "arguments": arguments},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def grant(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        user_confirmed: bool,
    ) -> dict[str, Any]:
        import secrets
        from time import monotonic

        if user_confirmed is not True:
            return {"success": False, "code": "explicit_confirmation_required"}
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 256:
            return {"success": False, "code": "invalid_session"}
        if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > ToolExecutionPolicyService.MAX_TOOL_NAME:
            return {"success": False, "code": "invalid_tool"}
        argument_size = ToolExecutionPolicyService._json_size(arguments)
        if not isinstance(arguments, dict) or argument_size < 0 or argument_size > ToolExecutionPolicyService.MAX_ARGUMENT_BYTES:
            return {"success": False, "code": "invalid_arguments"}
        try:
            fingerprint = self._fingerprint(tool_name.strip(), arguments)
        except (TypeError, ValueError, OverflowError):
            return {"success": False, "code": "invalid_arguments"}

        approval_id = secrets.token_urlsafe(24)
        record = {
            "session_id": session_id.strip(),
            "tool_name": tool_name.strip(),
            "fingerprint": fingerprint,
            "expires_at": monotonic() + self.ttl_seconds,
        }
        with self._lock:
            now = monotonic()
            self._pending = {
                key: value for key, value in self._pending.items()
                if value["expires_at"] > now
            }
            if len(self._pending) >= self.max_pending:
                return {"success": False, "code": "approval_capacity_reached"}
            self._pending[approval_id] = record
        return {
            "success": True,
            "approval_id": approval_id,
            "expires_in_seconds": self.ttl_seconds,
            "single_use": True,
        }

    def consume(
        self,
        *,
        approval_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        from time import monotonic

        if not all(isinstance(value, str) and value.strip() for value in (approval_id, session_id, tool_name)):
            return {"allowed": False, "code": "invalid_approval"}
        try:
            fingerprint = self._fingerprint(tool_name.strip(), arguments)
        except (TypeError, ValueError, OverflowError):
            return {"allowed": False, "code": "invalid_arguments"}
        with self._lock:
            record = self._pending.pop(approval_id, None)
            if record is None:
                return {"allowed": False, "code": "approval_missing_or_consumed"}
            if record["expires_at"] <= monotonic():
                return {"allowed": False, "code": "approval_expired"}
            if (
                record["session_id"] != session_id.strip()
                or record["tool_name"] != tool_name.strip()
                or record["fingerprint"] != fingerprint
            ):
                return {"allowed": False, "code": "approval_context_mismatch"}
            return {"allowed": True, "code": "approved", "single_use": True}
