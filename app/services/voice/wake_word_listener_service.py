from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.services.providers.provider_registry import ProviderRegistry


class WakeWordListenerService:
    """Own one opt-in local microphone listener; detection never runs commands."""

    def __init__(self, provider: Any | None = None) -> None:
        self._provider_override = provider
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._detected_event = threading.Event()
        self._started_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = "stopped"
        self._activated = False
        self._last_detected_at: str | None = None
        self._last_error: str | None = None

    def _provider(self) -> Any | None:
        return self._provider_override or ProviderRegistry.get("wake_word")

    def status(self) -> dict[str, Any]:
        with self._lock:
            alive = self._thread is not None and self._thread.is_alive()
            return {
                "success": True,
                "state": self._state if alive or self._state in {"error", "activated"} else "stopped",
                "listening": alive and not self._stop_event.is_set(),
                "activated": self._activated,
                "wake_word": "Lumira" if self._activated else None,
                "last_detected_at": self._last_detected_at,
                "error": self._last_error,
            }

    def start(self) -> dict[str, Any]:
        provider = self._provider()
        if provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "Wake-word listening is not configured. Enable the provider and configure its local model and access key.",
            }
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return {"success": True, "already_running": True, **self.status()}
            self._stop_event = threading.Event()
            self._detected_event = threading.Event()
            self._started_event = threading.Event()
            self._activated = False
            self._last_detected_at = None
            self._last_error = None
            self._state = "starting"
            self._thread = threading.Thread(
                target=self._listen,
                args=(provider, self._stop_event),
                name="lumira-wake-word-listener",
                daemon=True,
            )
            self._thread.start()
        if not self._started_event.wait(timeout=2.0):
            with self._lock:
                self._stop_event.set()
                self._state = "error"
                self._last_error = "ListenerStartupTimeout"
            return {
                **self.status(),
                "success": False,
                "code": "listener_start_timeout",
                "message": "The microphone listener did not finish starting in time.",
            }
        with self._lock:
            if self._state == "error":
                return {
                    **self.status(),
                    "success": False,
                    "code": "listener_start_failed",
                    "message": "The microphone listener could not start. Check the local audio setup.",
                }
        return {"success": True, "already_running": False, **self.status()}

    def stop(self, timeout_seconds: float = 4.0) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                if self._state != "error":
                    self._state = "stopped"
                self._activated = False
                return {"success": True, "stopped": True, **self.status()}
            self._stop_event.set()
            self._state = "stopping"
        thread.join(timeout=max(0.1, min(float(timeout_seconds), 5.0)))
        with self._lock:
            alive = thread.is_alive()
            if not alive:
                self._thread = None
                if self._state != "error":
                    self._state = "stopped"
                self._activated = False
            return {
                "success": not alive,
                "stopped": not alive,
                "code": None if not alive else "listener_stop_timeout",
                "message": None if not alive else "Microphone listener has not stopped yet.",
                **self.status(),
            }

    def wait_for_detection(self, timeout_seconds: float = 0.0) -> bool:
        return self._detected_event.wait(max(0.0, min(float(timeout_seconds), 5.0)))

    def _listen(self, provider: Any, stop_event: threading.Event) -> None:
        detector = None
        recorder = None
        try:
            import pvporcupine
            from pvrecorder import PvRecorder

            detector = pvporcupine.create(
                access_key=provider.access_key,
                keyword_paths=[str(provider.model_path)],
                sensitivities=[provider.sensitivity],
            )
            recorder = PvRecorder(device_index=-1, frame_length=detector.frame_length)
            recorder.start()
            with self._lock:
                if not stop_event.is_set():
                    self._state = "listening"
                self._started_event.set()
            while not stop_event.is_set():
                frame = recorder.read()
                if stop_event.is_set():
                    break
                if detector.process(frame) >= 0:
                    with self._lock:
                        self._activated = True
                        self._last_detected_at = datetime.now(timezone.utc).isoformat()
                        self._state = "activated"
                    self._detected_event.set()
        except Exception as error:
            # Only expose a stable error category; never leak SDK details or credentials.
            with self._lock:
                self._last_error = type(error).__name__
                self._state = "error"
                self._started_event.set()
        finally:
            if recorder is not None:
                try:
                    recorder.stop()
                except Exception:
                    pass
                try:
                    recorder.delete()
                except Exception:
                    pass
            if detector is not None:
                try:
                    detector.delete()
                except Exception:
                    pass
            with self._lock:
                self._started_event.set()
                # Preserve startup errors even if stop() races with cleanup and
                # temporarily changes the state to "stopping".
                if self._last_error is not None:
                    self._state = "error"
                elif self._state != "activated":
                    self._state = "stopped"
