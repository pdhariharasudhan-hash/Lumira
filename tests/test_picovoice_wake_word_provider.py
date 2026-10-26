import sys
import types
import wave
from pathlib import Path

import pytest

from app.services.providers.picovoice_wake_word_provider import PicovoiceWakeWordProvider


class FakeDetector:
    sample_rate = 16_000
    frame_length = 4

    def __init__(self, detections):
        self.detections = iter(detections)
        self.deleted = False

    def process(self, frame):
        assert len(frame) == self.frame_length
        return next(self.detections, -1)

    def delete(self):
        self.deleted = True


def write_wav(path: Path, *, rate=16_000, channels=1, width=2, frames=12):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        audio.writeframes(b"\x00" * frames * channels * width)


def configure_provider(tmp_path):
    model = tmp_path / "lumira.ppn"
    model.write_bytes(b"test model placeholder")
    return PicovoiceWakeWordProvider(access_key="test-only-key", model_path=model)


def install_fake_porcupine(monkeypatch, detector):
    monkeypatch.setitem(
        sys.modules,
        "pvporcupine",
        types.SimpleNamespace(create=lambda **kwargs: detector),
    )


def test_detects_lumira_in_local_wav_and_releases_detector(tmp_path, monkeypatch):
    path = tmp_path / "sample.wav"
    write_wav(path)
    detector = FakeDetector([-1, 0, -1])
    model = tmp_path / "lumira.ppn"
    model.write_bytes(b"test")
    monkeypatch.setitem(
        sys.modules,
        "pvporcupine",
        types.SimpleNamespace(
            create=lambda **kwargs: detector
            if kwargs["keyword_paths"] == [str(model)] and kwargs["sensitivities"] == [0.5]
            else (_ for _ in ()).throw(AssertionError("unexpected detector configuration"))
        ),
    )

    result = PicovoiceWakeWordProvider(access_key="test-only-key", model_path=model).detect(str(path))

    assert result == {"success": True, "detected": True}
    assert detector.deleted is True


def test_returns_false_when_keyword_is_not_detected(tmp_path, monkeypatch):
    path = tmp_path / "sample.wav"
    write_wav(path)
    detector = FakeDetector([-1, -1, -1])
    install_fake_porcupine(monkeypatch, detector)

    result = configure_provider(tmp_path).detect(str(path))

    assert result == {"success": True, "detected": False}
    assert detector.deleted is True


def test_rejects_wav_with_unsupported_audio_format(tmp_path, monkeypatch):
    path = tmp_path / "stereo.wav"
    write_wav(path, channels=2)
    detector = FakeDetector([])
    install_fake_porcupine(monkeypatch, detector)

    with pytest.raises(ValueError, match="mono, 16-bit PCM"):
        configure_provider(tmp_path).detect(str(path))

    assert detector.deleted is True


def test_rejects_missing_custom_keyword_model(tmp_path):
    with pytest.raises(ValueError, match="existing .ppn"):
        PicovoiceWakeWordProvider(access_key="test-only-key", model_path=tmp_path / "missing.ppn")


def test_requires_wav_and_enforces_recording_size_limit(tmp_path):
    provider = configure_provider(tmp_path)
    mp3 = tmp_path / "sample.mp3"
    mp3.write_bytes(b"not wav")
    with pytest.raises(ValueError, match="WAV"):
        provider.detect(str(mp3))
