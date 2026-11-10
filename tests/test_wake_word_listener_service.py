import sys
import threading
import time
import types

from fastapi.testclient import TestClient

from app.main import app
from app.services.providers.provider_registry import ProviderRegistry
from app.services.voice.wake_word_listener_service import WakeWordListenerService


class FakeProvider:
    provider_scope = "local"
    access_key = "test-only-key"
    model_path = "C:/fake/lumira.ppn"
    sensitivity = 0.5


class FakeDetector:
    frame_length = 4
    sample_rate = 16_000

    def __init__(self, detect=True):
        self.detect = detect
        self.deleted = False

    def process(self, frame):
        assert frame == [0, 0, 0, 0]
        return 0 if self.detect else -1

    def delete(self):
        self.deleted = True


class FakeRecorder:
    def __init__(self, device_index, frame_length):
        assert device_index == -1
        assert frame_length == 4
        self.started = False
        self.deleted = False
        self.stopped = False

    def start(self):
        self.started = True

    def read(self):
        time.sleep(0.005)
        return [0, 0, 0, 0]

    def stop(self):
        self.stopped = True

    def delete(self):
        self.deleted = True


def install_audio_fakes(monkeypatch, detector):
    recorder_box = []

    class Recorder(FakeRecorder):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            recorder_box.append(self)

    monkeypatch.setitem(
        sys.modules,
        "pvporcupine",
        types.SimpleNamespace(create=lambda **kwargs: detector),
    )
    monkeypatch.setitem(
        sys.modules,
        "pvrecorder",
        types.SimpleNamespace(PvRecorder=Recorder),
    )
    return recorder_box


def wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


def test_listener_starts_detects_and_stops_cleanly(monkeypatch):
    detector = FakeDetector(detect=True)
    recorders = install_audio_fakes(monkeypatch, detector)
    listener = WakeWordListenerService(provider=FakeProvider())
    core_context_operations = []
    original_emit_core_event = listener._emit_core_event

    def record_core_context_operation(operation):
        core_context_operations.append(operation)
        return original_emit_core_event(operation)

    listener._emit_core_event = record_core_context_operation
    started = listener.start()
    assert started["success"] is True
    assert wait_for(lambda: listener.status()["activated"])
    status = listener.status()
    assert status["state"] == "activated"
    assert status["listening"] is True
    assert status["wake_word"] == "Lumira"
    assert status["last_detected_at"] is not None

    stopped = listener.stop()
    assert stopped["success"] is True
    assert stopped["stopped"] is True
    assert listener.status()["listening"] is False
    assert listener.status()["activated"] is False
    assert detector.deleted is True
    assert recorders[0].started is True
    assert recorders[0].stopped is True
    assert recorders[0].deleted is True
    # Core Runtime context is captured once at startup, not synchronously
    # refreshed from the hot microphone loop on every wake-word detection.
    assert core_context_operations == ["wake_word_start"]


def test_listener_start_is_idempotent(monkeypatch):
    detector = FakeDetector(detect=False)
    install_audio_fakes(monkeypatch, detector)
    listener = WakeWordListenerService(provider=FakeProvider())

    first = listener.start()
    assert first["success"] is True
    assert wait_for(lambda: listener.status()["listening"])
    second = listener.start()
    assert second["success"] is True
    assert second["already_running"] is True
    assert listener.stop()["success"] is True


def test_listener_reports_missing_provider_without_starting():
    listener = WakeWordListenerService(provider=None)
    ProviderRegistry.unregister("wake_word")
    result = listener.start()
    assert result["success"] is False
    assert result["code"] == "provider_unavailable"
    assert listener.status()["listening"] is False


def test_listener_does_not_leak_audio_sdk_error(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "pvporcupine",
        types.SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret-access-key"))),
    )
    monkeypatch.setitem(
        sys.modules,
        "pvrecorder",
        types.SimpleNamespace(PvRecorder=FakeRecorder),
    )
    listener = WakeWordListenerService(provider=FakeProvider())
    started = listener.start()
    assert started["success"] is False
    assert started["code"] == "listener_start_failed"
    assert wait_for(lambda: listener.status()["state"] == "error")
    status = listener.status()
    assert status["error"] == "RuntimeError"
    assert "secret-access-key" not in str(status)
    assert listener.stop()["success"] is True
    assert listener.status()["state"] == "error"


def test_wake_word_routes_report_status_and_unavailable_provider(monkeypatch):
    ProviderRegistry.unregister("wake_word")
    client = TestClient(app)
    status = client.get("/voice/wake-word/status")
    start = client.post("/voice/wake-word/start")
    assert status.status_code == 200
    assert status.json()["listening"] is False
    assert start.status_code == 501
    assert start.json()["detail"]["code"] == "provider_unavailable"


def test_stop_during_listener_cleanup_preserves_error_state(monkeypatch):
    release_cleanup = threading.Event()

    class FailingDetector(FakeDetector):
        def process(self, frame):
            raise RuntimeError("secret-access-key")

        def delete(self):
            assert release_cleanup.wait(timeout=2.0)
            self.deleted = True

    detector = FailingDetector()
    recorders = install_audio_fakes(monkeypatch, detector)
    listener = WakeWordListenerService(provider=FakeProvider())
    started = listener.start()
    assert started["success"] is True
    assert wait_for(lambda: listener.status()["state"] == "error")

    stop_result = {}
    stop_thread = threading.Thread(
        target=lambda: stop_result.update(listener.stop(timeout_seconds=2.0))
    )
    stop_thread.start()
    assert wait_for(lambda: listener.status()["state"] == "stopping")
    release_cleanup.set()
    stop_thread.join(timeout=2.0)

    assert not stop_thread.is_alive()
    assert stop_result["success"] is True
    assert listener.status()["state"] == "error"
    assert listener.status()["error"] == "RuntimeError"
    assert "secret-access-key" not in str(listener.status())
    assert detector.deleted is True
    assert recorders[0].deleted is True
