import base64
import json
import os
import subprocess
import wave

import pytest

from app.services.providers.windows_sapi_speech_provider import WindowsSapiSpeechProvider


def _provider(monkeypatch, run):
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.os.name", "nt")
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.shutil.which", lambda _: "powershell.exe")
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.subprocess.run", run)
    return WindowsSapiSpeechProvider(timeout=999)


def _valid_wav(path):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(b"\x00\x00" * 2205)


def test_windows_sapi_provider_generates_bounded_local_wav(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        payload = json.loads(base64.b64decode(kwargs["env"]["LUMIRA_SAPI_PAYLOAD"]))
        _valid_wav(payload["output_path"])
        return subprocess.CompletedProcess(args, 0, stdout="LUMIRA_SAPI_OK", stderr="")

    provider = _provider(monkeypatch, fake_run)
    result = provider.synthesize("Hello from Lumira.", "en")

    assert result["success"] is True
    assert result["extension"] == "wav"
    assert result["content"].startswith(b"RIFF")
    assert result["content"][8:12] == b"WAVE"
    assert result["voice_engine"] == "Windows SAPI"
    assert captured["args"][0] == "powershell.exe"
    assert captured["args"][-2] == "-EncodedCommand"
    assert base64.b64decode(captured["args"][-1]).decode("utf-16le") == provider._POWERSHELL_SCRIPT
    assert captured["kwargs"]["timeout"] == 120
    assert captured["kwargs"]["capture_output"] is True


def test_windows_sapi_provider_rejects_unsupported_language_before_process(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unsupported language must not launch PowerShell")

    provider = _provider(monkeypatch, forbidden)
    with pytest.raises(ValueError, match="English synthesis only"):
        provider.synthesize("வணக்கம்", "ta")


def test_windows_sapi_provider_sanitizes_process_failure_and_cleans_temp(monkeypatch):
    captured = {}

    def failed(args, **kwargs):
        captured["path"] = json.loads(base64.b64decode(kwargs["env"]["LUMIRA_SAPI_PAYLOAD"]))["output_path"]
        return subprocess.CompletedProcess(args, 2, stdout="", stderr="private host details")

    provider = _provider(monkeypatch, failed)
    with pytest.raises(RuntimeError, match="verify an English SAPI voice") as error:
        provider.synthesize("Hello", "en")
    assert "private host details" not in str(error.value)
    assert not os.path.exists(captured["path"])


def test_windows_sapi_provider_rejects_invalid_wave_output(monkeypatch):
    captured = {}

    def invalid(args, **kwargs):
        captured["path"] = json.loads(base64.b64decode(kwargs["env"]["LUMIRA_SAPI_PAYLOAD"]))["output_path"]
        with open(captured["path"], "wb") as output:
            output.write(b"not-a-wave-file" * 10)
        return subprocess.CompletedProcess(args, 0, stdout="LUMIRA_SAPI_OK", stderr="")

    provider = _provider(monkeypatch, invalid)
    with pytest.raises(ValueError, match="invalid WAV"):
        provider.synthesize("Hello", "en")
    assert not os.path.exists(captured["path"])


def test_windows_sapi_provider_uses_bounded_os_voice_without_loading_an_ml_model(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        payload = json.loads(base64.b64decode(kwargs["env"]["LUMIRA_SAPI_PAYLOAD"]))
        captured["payload"] = payload
        _valid_wav(payload["output_path"])
        return subprocess.CompletedProcess(args, 0, stdout="LUMIRA_SAPI_OK", stderr="")

    provider = _provider(monkeypatch, fake_run)
    result = provider.synthesize("Hello", "en")

    assert result["success"] is True
    assert captured["payload"]["text"] == "Hello"
    assert provider.timeout == 120


def test_windows_sapi_provider_requires_windows_and_powershell(monkeypatch):
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.os.name", "posix")
    with pytest.raises(RuntimeError, match="only on Windows"):
        WindowsSapiSpeechProvider()
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.os.name", "nt")
    monkeypatch.setattr("app.services.providers.windows_sapi_speech_provider.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="PowerShell is unavailable"):
        WindowsSapiSpeechProvider()
