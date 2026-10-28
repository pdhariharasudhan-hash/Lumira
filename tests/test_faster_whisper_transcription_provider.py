from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.providers.faster_whisper_transcription_provider import (
    FasterWhisperTranscriptionProvider,
)
from app.services.resources.resource_budget_service import ResourceBudgetService


def _provider_with_fake_model(monkeypatch, segments):
    provider = FasterWhisperTranscriptionProvider()
    calls = []

    class FakeModel:
        def transcribe(self, path, **kwargs):
            calls.append((path, kwargs))
            if isinstance(segments, Exception):
                raise segments
            return iter(segments), SimpleNamespace(language="en")

    monkeypatch.setattr(provider, "_load_model", lambda: FakeModel())
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False},
    )
    return provider, calls


def test_local_transcription_joins_segments_and_uses_bounded_cpu_options(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 8 + b"WAVE")
    provider, calls = _provider_with_fake_model(
        monkeypatch,
        [
            SimpleNamespace(text="  Vanakkam "),
            SimpleNamespace(text=" "),
            SimpleNamespace(text=" Lumira.  "),
        ],
    )

    assert provider.transcribe(str(audio)) == "Vanakkam Lumira."
    assert calls == [
        (
            str(audio),
            {
                "beam_size": 1,
                "vad_filter": True,
                "condition_on_previous_text": False,
            },
        )
    ]


def test_local_transcription_rejects_missing_or_unsupported_audio_before_model_load(tmp_path, monkeypatch):
    provider = FasterWhisperTranscriptionProvider()
    monkeypatch.setattr(
        provider,
        "_load_model",
        lambda: (_ for _ in ()).throw(AssertionError("model must not load")),
    )

    with pytest.raises(ValueError, match="does not exist"):
        provider.transcribe(str(tmp_path / "missing.wav"))

    unsupported = tmp_path / "sample.ogg"
    unsupported.write_bytes(b"audio")
    with pytest.raises(ValueError, match="not supported"):
        provider.transcribe(str(unsupported))

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        provider.transcribe(str(empty))


def test_local_transcription_defers_under_memory_pressure_without_loading_model(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 8 + b"WAVE")
    provider = FasterWhisperTranscriptionProvider()
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": True},
    )
    monkeypatch.setattr(
        provider,
        "_load_model",
        lambda: (_ for _ in ()).throw(AssertionError("model must not load under pressure")),
    )

    with pytest.raises(RuntimeError, match="memory is constrained"):
        provider.transcribe(str(audio))


def test_local_transcription_rejects_empty_and_oversized_transcripts(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 8 + b"WAVE")

    empty_provider, _ = _provider_with_fake_model(monkeypatch, [])
    with pytest.raises(ValueError, match="no speech"):
        empty_provider.transcribe(str(audio))

    long_provider, _ = _provider_with_fake_model(
        monkeypatch,
        [SimpleNamespace(text="A transcript longer than the configured test limit.")],
    )
    monkeypatch.setattr(long_provider, "MAX_TRANSCRIPT_CHARS", 10)
    with pytest.raises(ValueError, match="size limit"):
        long_provider.transcribe(str(audio))


def test_local_transcription_sanitizes_model_failures(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 8 + b"WAVE")
    provider, _ = _provider_with_fake_model(
        monkeypatch,
        RuntimeError("private model or filesystem detail"),
    )

    with pytest.raises(RuntimeError, match="failed to process"):
        provider.transcribe(str(audio))
