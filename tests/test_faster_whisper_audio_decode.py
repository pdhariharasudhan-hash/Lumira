import math
import struct
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from app.services.providers.faster_whisper_transcription_provider import (
    FasterWhisperTranscriptionProvider,
)
from app.services.resources.resource_budget_service import ResourceBudgetService


def _write_test_wav(path):
    sample_rate = 22050
    duration = 0.6
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = [
            struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
            for index in range(int(sample_rate * duration))
        ]
        output.writeframes(b"".join(frames))


def test_pyav_compat_decoder_resamples_pcm_wave_to_float32_16khz(tmp_path):
    pytest.importorskip("av")
    path = tmp_path / "tone.wav"
    _write_test_wav(path)

    waveform = FasterWhisperTranscriptionProvider._decode_audio_compat(path)

    assert waveform.dtype == np.float32
    assert 9_000 <= waveform.size <= 10_000
    assert float(np.max(np.abs(waveform))) > 0.1


def test_local_transcription_passes_decoded_waveform_to_model(tmp_path, monkeypatch):
    path = tmp_path / "speech.wav"
    _write_test_wav(path)
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False},
    )
    monkeypatch.setenv("LUMIRA_LOCAL_TRANSCRIPTION_INITIAL_PROMPT", "Lumira assistant")

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32
            assert kwargs["beam_size"] == 1
            assert kwargs["initial_prompt"] == "Lumira assistant"
            return iter([SimpleNamespace(text=" Lumira voice test.")]), SimpleNamespace(language="en")

    provider = FasterWhisperTranscriptionProvider()
    monkeypatch.setattr(provider, "_load_model", lambda: FakeModel())

    assert provider.transcribe(str(path)) == "Lumira voice test."
