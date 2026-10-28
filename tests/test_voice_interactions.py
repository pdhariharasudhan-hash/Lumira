from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry
from app.services.voice.transcript_service import TranscriptService


def test_voice_activation_and_playback_have_truthful_provider_boundaries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    upload = client.post(
        "/voice/upload",
        files={"audio": ("sample.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")},
    )
    audio_id = upload.json()["data"]["artifact"]["artifact_id"]

    activation = client.post("/voice/activation", json={"artifact_id": audio_id})
    playback = client.post("/voice/playback", json={"text": "வணக்கம் Lumira", "language": "ta-en"})
    assert activation.status_code == 503
    assert activation.json()["detail"]["code"] == "provider_unavailable"
    assert playback.status_code == 503
    assert playback.json()["detail"]["code"] == "provider_unavailable"

    class WakeWord:
        def detect(self, audio_path):
            assert audio_path.endswith(".wav")
            return {"success": True, "detected": True}

    class Synthesis:
        def synthesize(self, text, language):
            assert (text, language) == ("வணக்கம் Lumira", "ta-en")
            return {"success": True, "content": b"RIFF\x00\x00\x00\x00WAVE", "extension": "wav"}

    ProviderRegistry.register("wake_word", WakeWord())
    ProviderRegistry.register("speech_synthesis", Synthesis())
    try:
        activated = client.post("/voice/activation", json={"artifact_id": audio_id})
        spoken = client.post("/voice/playback", json={"text": "வணக்கம் Lumira", "language": "ta-en"})
    finally:
        ProviderRegistry.clear()

    assert activated.json()["activated"] is True
    assert spoken.json()["success"] is True
    assert ArtifactManagerService().get_artifact(spoken.json()["artifact"]["artifact_id"])["type"] == "audio"


def test_transcript_provider_registry_persists_transcript_and_detects_tamil_english(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )

    class Transcription:
        def transcribe(self, audio_path):
            return "வணக்கம் Lumira, create a report"

    ProviderRegistry.register("transcription", Transcription())
    try:
        result = TranscriptService().generate_transcript(audio["artifact_id"])
    finally:
        ProviderRegistry.clear()

    assert result["success"] is True
    assert result["transcript_text"] == "வணக்கம் Lumira, create a report"
    assert result["language"] == "ta-en"
    assert result["language_confidence"] > 0
    transcript = ArtifactManagerService().get_artifact(result["transcript_artifact"]["artifact_id"])
    assert transcript["type"] == "transcripts"


def test_transcription_validates_only_audio_header_not_entire_recording(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE" + (b"x" * 4096), "voice_capture", "wav"
    )

    class Transcription:
        def transcribe(self, audio_path):
            assert Path(audio_path).is_file()
            return "header-only validation works"

    def reject_full_file_read(self, *args, **kwargs):
        raise AssertionError("transcription validation must not load the whole audio file")

    monkeypatch.setattr(Path, "read_bytes", reject_full_file_read)
    result = TranscriptService(provider=Transcription()).generate_transcript(audio["artifact_id"])

    assert result["success"] is True
    assert result["language"] in {"en", "ta-en"}


def test_voice_result_is_persisted_to_session_from_stored_artifacts(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    transcript = artifacts.create_artifact(
        "transcripts", "Transcript text that must survive refresh.", audio["artifact_id"], "txt"
    )
    summary = artifacts.create_artifact(
        "summaries", "Summary text that must survive refresh.", transcript["artifact_id"], "txt"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": transcript["artifact_id"],
            "summary_artifact_id": summary["artifact_id"],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    restored = SessionManagerService().get_session(session["session_id"])
    message = restored["recent_messages"][-1]
    assert message["role"] == "assistant"
    assert "Transcript text that must survive refresh." in message["content"]
    assert "Summary text that must survive refresh." in message["content"]
    assert message["metadata"]["voice_capture"]["audio_artifact_id"] == audio["artifact_id"]

    audio_links = artifacts.get_artifact_links(audio["artifact_id"])["links"]
    transcript_links = artifacts.get_artifact_links(transcript["artifact_id"])["links"]
    assert any(
        link["direction"] == "outgoing"
        and link["artifact_id"] == transcript["artifact_id"]
        and link["relation"] == "transcribed_as"
        for link in audio_links
    )
    assert any(
        link["direction"] == "outgoing"
        and link["artifact_id"] == summary["artifact_id"]
        and link["relation"] == "summarized_as"
        for link in transcript_links
    )


def test_voice_result_rejects_transcript_from_another_audio_artifact(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    unrelated_audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    transcript = artifacts.create_artifact(
        "transcripts", "Unrelated transcript.", unrelated_audio["artifact_id"], "txt"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={"audio_artifact_id": audio["artifact_id"], "transcript_artifact_id": transcript["artifact_id"]},
    )

    assert response.status_code == 409
    assert "does not belong" in response.json()["detail"]


def test_voice_result_persists_provider_unavailability_when_only_audio_exists(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={"audio_artifact_id": audio["artifact_id"]},
    )

    assert response.status_code == 200
    message = SessionManagerService().get_session(session["session_id"])["recent_messages"][-1]
    assert "Transcription unavailable or not configured." in message["content"]


def test_voice_process_preserves_audio_and_transcript_when_summary_provider_fails(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact("audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav")

    class Transcription:
        def generate_transcript(self, artifact_id):
            assert artifact_id == audio["artifact_id"]
            transcript = artifacts.create_artifact("transcripts", "வணக்கம் Lumira, capture the idea", artifact_id, "txt")
            return {"success": True, "transcript_text": "வணக்கம் Lumira, capture the idea", "language": "ta-en", "transcript_artifact": transcript}

    class SummaryFailure:
        def generate_summary(self, artifact_id):
            assert artifacts.get_artifact(artifact_id)["type"] == "transcripts"
            return {"success": False, "code": "provider_unavailable", "message": "Summary provider is not configured."}

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", SummaryFailure)
    response = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"], "generate_summary": True})

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert body["stage"] == "summary"
    assert artifacts.get_artifact(audio["artifact_id"])["type"] == "audio"
    assert artifacts.get_artifact(body["transcript_artifact_id"])["type"] == "transcripts"
    assert "preserved" in body["message"]
    links = artifacts.get_artifact_links(audio["artifact_id"])["links"]
    assert any(
        link["artifact_id"] == body["transcript_artifact_id"]
        and link["relation"] == "transcribed_as"
        for link in links
    )
    assert body["memory"]["success"] is True
    assert body["memory"]["state"] == "saved"
    from app.services.memory.memory_service import MemoryService
    memories = MemoryService().get_all()["experiences"]
    saved = next(item for item in memories if audio["artifact_id"] in item.get("artifact_ids", []))
    assert body["transcript_artifact_id"] in saved["artifact_ids"]
    assert saved["verified"] is False


def test_voice_process_can_finish_with_audio_and_transcript_without_summary(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact("audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav")

    class Transcription:
        def generate_transcript(self, artifact_id):
            transcript = artifacts.create_artifact("transcripts", "A saved idea", artifact_id, "txt")
            return {"success": True, "transcript_text": "A saved idea", "transcript_artifact": transcript}

    class UnexpectedSummary:
        def generate_summary(self, artifact_id):
            raise AssertionError("summary must not run when disabled")

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", UnexpectedSummary)
    response = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"], "generate_summary": False})

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["stage"] == "completed"
    assert body["audio_artifact_id"] == audio["artifact_id"]
    assert artifacts.get_artifact(body["transcript_artifact_id"])["type"] == "transcripts"
    assert body["memory"]["success"] is True
    assert body["memory"]["state"] == "saved"


def test_retry_summary_attaches_summary_artifact_to_existing_voice_memory(tmp_path, monkeypatch):
    from app.routes import voice_capture
    from app.services.memory.memory_service import MemoryService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact("audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav")
    transcript = artifacts.create_artifact("transcripts", "A captured idea", audio["artifact_id"], "txt")
    experience = MemoryService().record_experience(
        experience_type="workflow", summary="A captured idea", outcome="Voice capture saved.",
        artifact_ids=[audio["artifact_id"], transcript["artifact_id"]], verified=False,
    )

    class Summary:
        def generate_summary(self, transcript_id):
            summary = artifacts.create_artifact("summaries", "The idea summary", transcript_id, "txt")
            return {"success": True, "summary_text": "The idea summary", "summary_artifact": summary}

    monkeypatch.setattr(voice_capture, "SummaryService", Summary)
    response = client.post("/voice/retry-summary", json={"transcript_artifact_id": transcript["artifact_id"]})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["memory"]["state"] == "updated"
    memory_record = next(item for item in MemoryService().get_all()["experiences"] if item["experience_id"] == experience["experience_id"])
    assert body["summary_artifact_id"] in memory_record["artifact_ids"]


def test_voice_process_reuses_existing_transcript_on_retry(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF" + bytes(4) + b"WAVE", "voice_capture", "wav"
    )
    calls = {"transcription": 0}

    class Transcription:
        def generate_transcript(self, artifact_id):
            calls["transcription"] += 1
            transcript = artifacts.create_artifact(
                "transcripts", "வணக்கம் Lumira, retry safely", artifact_id, "txt"
            )
            return {
                "success": True,
                "transcript_text": "வணக்கம் Lumira, retry safely",
                "transcript_artifact": transcript,
            }

    class UnexpectedSummary:
        def generate_summary(self, artifact_id):
            raise AssertionError("summary generation was disabled")

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", UnexpectedSummary)

    first = client.post(
        "/voice/process",
        json={"audio_artifact_id": audio["artifact_id"], "generate_summary": False},
    )
    second = client.post(
        "/voice/process",
        json={"audio_artifact_id": audio["artifact_id"], "generate_summary": False},
    )

    assert first.status_code == second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert first_body["success"] is True
    assert second_body["success"] is True
    assert first_body["transcript_artifact_id"] == second_body["transcript_artifact_id"]
    assert second_body["transcription"]["reused"] is True
    assert calls["transcription"] == 1
    transcript_artifacts = [
        item for item in artifacts.get_all_artifacts()
        if item.get("type") == "transcripts" and item.get("source") == audio["artifact_id"]
    ]
    assert len(transcript_artifacts) == 1


def test_voice_process_reuses_transcript_and_summary_on_full_retry(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF" + bytes(4) + b"WAVE", "voice_capture", "wav"
    )
    calls = {"transcription": 0, "summary": 0}

    class Transcription:
        def generate_transcript(self, artifact_id):
            calls["transcription"] += 1
            transcript = artifacts.create_artifact(
                "transcripts", "A voice idea to summarize", artifact_id, "txt"
            )
            return {
                "success": True,
                "transcript_text": "A voice idea to summarize",
                "transcript_artifact": transcript,
            }

    class Summary:
        def generate_summary(self, transcript_id):
            calls["summary"] += 1
            summary = artifacts.create_artifact(
                "summaries", "A concise voice idea summary", transcript_id, "txt"
            )
            return {
                "success": True,
                "summary_text": "A concise voice idea summary",
                "summary_artifact": summary,
            }

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", Summary)

    first = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})
    second = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})

    assert first.status_code == second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert first_body["success"] is True
    assert second_body["success"] is True
    assert first_body["transcript_artifact_id"] == second_body["transcript_artifact_id"]
    assert first_body["summary_artifact_id"] == second_body["summary_artifact_id"]
    assert second_body["transcription"]["reused"] is True
    assert second_body["summary"]["reused"] is True
    assert calls == {"transcription": 1, "summary": 1}
    stored = artifacts.get_all_artifacts()
    assert len([item for item in stored if item.get("type") == "transcripts"]) == 1
    assert len([item for item in stored if item.get("type") == "summaries"]) == 1


def test_voice_process_retries_failed_summary_without_retranscribing(tmp_path, monkeypatch):
    from app.routes import voice_capture
    from app.services.memory.memory_service import MemoryService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF" + bytes(4) + b"WAVE", "voice_capture", "wav"
    )
    calls = {"transcription": 0, "summary": 0}

    class Transcription:
        def generate_transcript(self, artifact_id):
            calls["transcription"] += 1
            transcript = artifacts.create_artifact(
                "transcripts", "Build a personal AI memory system", artifact_id, "txt"
            )
            return {
                "success": True,
                "transcript_text": "Build a personal AI memory system",
                "transcript_artifact": transcript,
            }

    class Summary:
        def generate_summary(self, transcript_id):
            calls["summary"] += 1
            if calls["summary"] == 1:
                return {
                    "success": False,
                    "code": "provider_unavailable",
                    "message": "Summary provider is unavailable",
                }
            summary = artifacts.create_artifact(
                "summaries", "Build a personal AI memory system", transcript_id, "txt"
            )
            return {
                "success": True,
                "summary_text": "Build a personal AI memory system",
                "summary_artifact": summary,
            }

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", Summary)

    first = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})
    second = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})

    assert first.status_code == second.status_code == 200
    assert first.json()["success"] is False
    assert first.json()["stage"] == "summary"
    assert second.json()["success"] is True
    assert second.json()["stage"] == "completed"
    assert second.json()["transcription"]["reused"] is True
    assert calls == {"transcription": 1, "summary": 2}
    assert second.json()["memory"]["state"] == "already_exists"
    memory_record = next(
        item for item in MemoryService().get_all()["experiences"]
        if item.get("experience_id") == first.json()["memory"]["experience_id"]
    )
    assert second.json()["summary_artifact_id"] in memory_record["artifact_ids"]
    stored = artifacts.get_all_artifacts()
    assert len([item for item in stored if item.get("type") == "transcripts"]) == 1
    assert len([item for item in stored if item.get("type") == "summaries"]) == 1



def test_voice_process_does_not_reuse_archived_summary_on_retry(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF" + bytes(4) + b"WAVE", "voice_capture", "wav"
    )
    calls = {"transcription": 0, "summary": 0}

    class Transcription:
        def generate_transcript(self, artifact_id):
            calls["transcription"] += 1
            transcript = artifacts.create_artifact(
                "transcripts", "A durable voice idea", artifact_id, "txt"
            )
            return {
                "success": True,
                "transcript_text": "A durable voice idea",
                "transcript_artifact": transcript,
            }

    class Summary:
        def generate_summary(self, transcript_id):
            calls["summary"] += 1
            summary = artifacts.create_artifact(
                "summaries", f"Summary attempt {calls['summary']}", transcript_id, "txt"
            )
            return {
                "success": True,
                "summary_text": f"Summary attempt {calls['summary']}",
                "summary_artifact": summary,
            }

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", Summary)

    first = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})
    assert first.status_code == 200 and first.json()["success"] is True
    old_summary_id = first.json()["summary_artifact_id"]
    assert artifacts.archive_artifact(old_summary_id) is True

    second = client.post("/voice/process", json={"audio_artifact_id": audio["artifact_id"]})
    assert second.status_code == 200 and second.json()["success"] is True
    body = second.json()

    assert body["transcript_artifact_id"] == first.json()["transcript_artifact_id"]
    assert body["transcription"]["reused"] is True
    assert body["summary_artifact_id"] != old_summary_id
    assert body["summary"].get("reused") is not True
    assert calls == {"transcription": 1, "summary": 2}
    assert artifacts.get_artifact(old_summary_id)["archived"] is True
    assert artifacts.get_artifact(body["summary_artifact_id"])["archived"] is not True



def test_voice_process_does_not_reuse_archived_transcript_on_retry(tmp_path, monkeypatch):
    from app.routes import voice_capture

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF" + bytes(4) + b"WAVE", "voice_capture", "wav"
    )
    calls = {"transcription": 0}

    class Transcription:
        def generate_transcript(self, artifact_id):
            calls["transcription"] += 1
            transcript = artifacts.create_artifact(
                "transcripts", f"Transcript attempt {calls['transcription']}", artifact_id, "txt"
            )
            return {
                "success": True,
                "transcript_text": f"Transcript attempt {calls['transcription']}",
                "transcript_artifact": transcript,
            }

    class UnexpectedSummary:
        def generate_summary(self, artifact_id):
            raise AssertionError("summary generation was disabled")

    monkeypatch.setattr(voice_capture, "TranscriptService", Transcription)
    monkeypatch.setattr(voice_capture, "SummaryService", UnexpectedSummary)

    first = client.post(
        "/voice/process",
        json={"audio_artifact_id": audio["artifact_id"], "generate_summary": False},
    )
    assert first.status_code == 200 and first.json()["success"] is True
    old_transcript_id = first.json()["transcript_artifact_id"]
    assert artifacts.archive_artifact(old_transcript_id) is True

    second = client.post(
        "/voice/process",
        json={"audio_artifact_id": audio["artifact_id"], "generate_summary": False},
    )
    assert second.status_code == 200 and second.json()["success"] is True
    body = second.json()

    assert body["transcript_artifact_id"] != old_transcript_id
    assert body["transcription"].get("reused") is not True
    assert calls["transcription"] == 2
    assert artifacts.get_artifact(old_transcript_id)["archived"] is True
    assert artifacts.get_artifact(body["transcript_artifact_id"])["archived"] is not True
