"""Fail-closed, side-effect-free policy for voice recording storage.

The caller must obtain explicit user consent and pass the consent receipt.
This module does not start a microphone, persist audio, or schedule deletion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


class VoiceCapturePolicyService:
    SUPPORTED_FORMATS = frozenset({"wav", "mp3", "m4a", "ogg", "webm"})
    MAX_UPLOAD_BYTES = 25_000_000
    MAX_RETENTION_DAYS = 36_500

    def evaluate(
        self,
        *,
        filename: str,
        size_bytes: int,
        consent: Mapping[str, Any] | None,
        now: datetime | None = None,
    ) -> dict:
        """Return an explicit allow/deny decision and retention snapshot."""
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 512:
            return self._deny("invalid_filename")
        safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        extension = Path(safe_name).suffix.removeprefix(".").lower()
        if extension not in self.SUPPORTED_FORMATS:
            return self._deny("unsupported_audio_format")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            return self._deny("invalid_size")
        if not 1 <= size_bytes <= self.MAX_UPLOAD_BYTES:
            return self._deny("audio_size_out_of_range")
        if not isinstance(consent, Mapping):
            return self._deny("explicit_consent_required")

        if consent.get("voice_capture") is not True:
            return self._deny("voice_capture_not_consented")
        if consent.get("audio_storage") is not True:
            return self._deny("audio_storage_not_consented")
        if consent.get("transcription") is not True and consent.get("transcription") is not False:
            return self._deny("transcription_choice_required")

        receipt_id = consent.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 128:
            return self._deny("consent_receipt_missing")
        consented_at = self._parse_time(consent.get("consented_at"))
        if consented_at is None:
            return self._deny("consent_timestamp_invalid")

        retention_mode = consent.get("retention_mode")
        reference = now if now is not None else datetime.now(timezone.utc)
        if not isinstance(reference, datetime):
            return self._deny("invalid_reference_time")
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        reference = reference.astimezone(timezone.utc)
        if consented_at > reference:
            return self._deny("consent_timestamp_in_future")

        if retention_mode == "until_deleted":
            retention_days = None
            expires_at = None
        elif retention_mode == "days":
            retention_days = consent.get("retention_days")
            if (
                isinstance(retention_days, bool)
                or not isinstance(retention_days, int)
                or not 1 <= retention_days <= self.MAX_RETENTION_DAYS
            ):
                return self._deny("retention_period_invalid")
            expiry = consented_at + timedelta(days=retention_days)
            if expiry <= reference:
                return self._deny("audio_retention_expired")
            expires_at = expiry.isoformat()
        else:
            return self._deny("retention_choice_required")

        return {
            "allowed": True,
            "code": "capture_policy_approved",
            "format": extension,
            "size_bytes": size_bytes,
            "consent_receipt_id": receipt_id.strip(),
            "consented_at": consented_at.isoformat(),
            "transcription_allowed": consent["transcription"],
            "retention": {
                "mode": retention_mode,
                "days": retention_days,
                "expires_at": expires_at,
            },
            "policy_version": 1,
            "side_effects_performed": False,
        }

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _deny(code: str) -> dict:
        return {
            "allowed": False,
            "code": code,
            "policy_version": 1,
            "side_effects_performed": False,
        }
