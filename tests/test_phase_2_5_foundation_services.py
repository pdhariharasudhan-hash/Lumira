import json
import math
import struct
import wave
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.artifacts.artifact_integrity_audit_service import ArtifactIntegrityAuditService
from app.services.brain.tool_execution_policy_service import (
    ToolApprovalService,
    ToolExecutionBudget,
    ToolExecutionPolicyService,
)
from app.services.memory.memory_retention_service import MemoryRetentionService
from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.persistence.schema_migration_service import SchemaMigration, SchemaMigrationService
from app.services.voice.audio_quality_service import AudioQualityService, VoiceActivityDetector
from app.services.voice.voice_capture_policy_service import VoiceCapturePolicyService


def _wav_bytes(samples, rate=16000):
    from io import BytesIO
    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return buffer.getvalue()


def test_tool_policy_fails_closed_and_validates_arguments():
    policy = ToolExecutionPolicyService({"notes.read": True})
    manifest = {
        "name": "read_note",
        "capability": "notes.read",
        "parameters": {
            "type": "object",
            "properties": {"note_id": {"type": "string", "minLength": 1}},
            "required": ["note_id"],
            "additionalProperties": False,
        },
    }
    assert policy.authorize(manifest, {"note_id": "n-1"}).allowed is True
    assert policy.authorize(manifest, {"note_id": ""}).code == "arguments_invalid"
    assert policy.authorize(manifest, {"note_id": "n-1", "path": "C:/"}).code == "arguments_invalid"
    assert ToolExecutionPolicyService().authorize(manifest, {"note_id": "n-1"}).code == "permission_denied"


def test_tool_policy_requires_exact_one_time_approval_for_high_risk_action():
    policy = ToolExecutionPolicyService({"filesystem.delete": True})
    approvals = ToolApprovalService(ttl_seconds=30)
    manifest = {
        "name": "delete_file",
        "capability": "filesystem.delete",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    }
    arguments = {"path": "workspace/tmp.txt"}
    assert policy.authorize(manifest, arguments).code == "approval_required"
    receipt = approvals.grant(
        session_id="session-1",
        tool_name="delete_file",
        arguments=arguments,
        user_confirmed=True,
    )
    assert receipt["success"] is True
    assert policy.authorize(
        manifest, arguments, approval_id=receipt["approval_id"],
        session_id="session-1", approval_service=approvals,
    ).allowed is True
    assert policy.authorize(
        manifest, arguments, approval_id=receipt["approval_id"],
        session_id="session-1", approval_service=approvals,
    ).code == "approval_missing_or_consumed"


def test_tool_approval_is_bound_to_session_and_arguments():
    approvals = ToolApprovalService()
    receipt = approvals.grant(
        session_id="s1", tool_name="tool", arguments={"x": 1}, user_confirmed=True,
    )
    assert approvals.consume(
        approval_id=receipt["approval_id"], session_id="s2",
        tool_name="tool", arguments={"x": 1},
    )["allowed"] is False


def test_tool_budget_bounds_calls_bytes_and_cancellation():
    budget = ToolExecutionBudget(max_calls=1, max_total_argument_bytes=10, timeout_seconds=30)
    budget.begin_call(10)
    with pytest.raises(RuntimeError, match="call budget"):
        budget.begin_call(0)
    budget.cancel()
    with pytest.raises(RuntimeError, match="cancelled"):
        budget.record_result(1)


def test_schema_migration_creates_backup_and_preserves_unknown_fields(tmp_path):
    path = tmp_path / "memory.json"
    original = {"schema_version": 0, "keep": {"legacy": True}}
    path.write_text(json.dumps(original), encoding="utf-8")
    service = SchemaMigrationService(path)
    result = service.migrate([
        SchemaMigration(
            1, "add_records",
            lambda data: {**data, "schema_version": 1, "records": []},
        )
    ])
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert result["changed"] is True
    assert result["from_version"] == 0 and result["to_version"] == 1
    assert migrated["keep"] == {"legacy": True}
    assert migrated["records"] == []
    assert json.loads((tmp_path / Path(result["backup"]["path"]).name).read_text(encoding="utf-8")) == original


def test_schema_migration_failure_leaves_original_unchanged(tmp_path):
    path = tmp_path / "memory.json"
    original = {"schema_version": 0, "safe": True}
    path.write_text(json.dumps(original), encoding="utf-8")
    service = SchemaMigrationService(path)
    with pytest.raises(PersistenceIntegrityError, match="migration"):
        service.migrate([
            SchemaMigration(1, "broken", lambda data: (_ for _ in ()).throw(RuntimeError("nope")))
        ])
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_memory_retention_is_preview_only_and_protects_important_records():
    service = MemoryRetentionService()
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    records = [
        {"id": "old", "type": "cache", "timestamp": "2025-12-01T00:00:00Z"},
        {"id": "pinned", "type": "cache", "timestamp": "2025-12-01T00:00:00Z", "pinned": True},
        {"id": "active", "type": "cache", "timestamp": "2025-12-01T00:00:00Z", "status": "active"},
    ]
    result = service.plan(records, {"cache": 7}, now=now)
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["id"] == "old"
    assert result["protected_count"] == 2
    assert result["deletion_performed"] is False
    assert records[0]["id"] == "old"


def test_memory_retention_rejects_duplicate_ids_even_across_retained_records():
    service = MemoryRetentionService()
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    records = [
        {"id": "same", "type": "cache", "timestamp": "2025-12-01T00:00:00Z"},
        {"id": "same", "type": "cache", "timestamp": "2026-01-30T00:00:00Z"},
    ]
    result = service.plan(records, {"cache": 7}, now=now)
    assert result["candidate_count"] == 0
    assert result["unknown_count"] == 2


def test_artifact_audit_detects_checksum_mismatch_without_mutation(tmp_path):
    class Manager:
        def __init__(self, root):
            self.base_path = root
            self.records = []

        def get_all_artifacts(self):
            return self.records

    root = tmp_path / "artifacts"
    root.mkdir()
    payload = root / "note.txt"
    payload.write_text("actual", encoding="utf-8")
    manager = Manager(root)
    manager.records.append({
        "artifact_id": "a1",
        "file": str(payload),
        "content_bytes": 6,
        "content_sha256": "0" * 64,
    })
    before = payload.read_bytes()
    report = ArtifactIntegrityAuditService(manager).audit()
    assert report["counts"]["checksum_mismatch"] == 1
    assert report["mutations_performed"] is False
    assert payload.read_bytes() == before
    assert len(manager.records) == 1


def test_audio_quality_and_voice_activity_detector_handle_partial_final_frame():
    samples = [0] * 1600 + [int(9000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(4800)]
    payload = _wav_bytes(samples)
    quality = AudioQualityService().analyze_bytes(payload)
    assert quality["success"] is True
    assert quality["analysis"]["duration_seconds"] == 0.4

    result = VoiceActivityDetector(frame_ms=30, minimum_speech_ms=100).detect_stream(
        __import__("io").BytesIO(payload)
    )
    assert result["success"] is True
    assert result["transcription_performed"] is False
    assert result["segments"]
    assert result["segments"][0]["start_seconds"] >= 0.09


def test_voice_capture_policy_requires_explicit_consent_and_retention_choice():
    policy = VoiceCapturePolicyService()
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    consent = {
        "voice_capture": True,
        "audio_storage": True,
        "transcription": False,
        "receipt_id": "consent-1",
        "consented_at": "2026-01-01T00:00:00Z",
        "retention_mode": "days",
        "retention_days": 30,
    }
    denied = policy.evaluate(
        filename="idea.wav", size_bytes=1024, consent=None, now=now,
    )
    assert denied["allowed"] is False
    assert denied["code"] == "explicit_consent_required"

    approved = policy.evaluate(
        filename=r"C:\\recordings\\idea.WAV",
        size_bytes=1024, consent=consent, now=now,
    )
    assert approved["allowed"] is True
    assert approved["format"] == "wav"
    assert approved["transcription_allowed"] is False
    assert approved["retention"]["expires_at"] == "2026-01-31T00:00:00+00:00"
