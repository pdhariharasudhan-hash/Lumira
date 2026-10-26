from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Any


class PicovoiceWakeWordProvider:
    """Detect the configured Lumira keyword in a bounded local WAV clip.

    This provider processes a supplied recording; it is not an always-listening
    microphone service. The keyword model and access key must be configured
    locally, and the optional pvporcupine package is imported only on use.
    """

    MAX_AUDIO_BYTES = 25_000_000
    MAX_DURATION_SECONDS = 60
    MAX_MODEL_PATH_CHARS = 1_024

    def __init__(
        self,
        *,
        access_key: str | None = None,
        model_path: str | Path | None = None,
        sensitivity: float = 0.5,
    ) -> None:
        self.access_key = access_key if access_key is not None else os.getenv("LUMIRA_WAKE_WORD_API_KEY", "")
        configured_path = model_path if model_path is not None else os.getenv("LUMIRA_WAKE_WORD_MODEL_PATH", "")
        self.model_path = Path(configured_path).expanduser() if str(configured_path).strip() else None
        if not self.access_key.strip():
            raise ValueError("Wake-word access key is not configured.")
        if self.model_path is None or len(str(self.model_path)) > self.MAX_MODEL_PATH_CHARS:
            raise ValueError("A valid custom Lumira keyword model path is required.")
        if not self.model_path.is_file() or self.model_path.suffix.lower() != ".ppn":
            raise ValueError("The Lumira keyword model must be an existing .ppn file.")
        if isinstance(sensitivity, bool) or not isinstance(sensitivity, (int, float)) or not 0.0 <= sensitivity <= 1.0:
            raise ValueError("Wake-word sensitivity must be between 0 and 1.")
        self.sensitivity = float(sensitivity)

    def detect(self, audio_path: str) -> dict[str, Any]:
        path = Path(audio_path)
        if path.suffix.lower() != ".wav" or not path.is_file():
            raise ValueError("Wake-word detection requires an existing WAV recording.")
        size = path.stat().st_size
        if size < 44 or size > self.MAX_AUDIO_BYTES:
            raise ValueError("WAV recording is empty or exceeds the wake-word size limit.")

        try:
            import pvporcupine
        except ImportError:
            raise RuntimeError("Optional pvporcupine dependency is not installed.") from None

        detector = None
        try:
            detector = pvporcupine.create(
                access_key=self.access_key,
                keyword_paths=[str(self.model_path)],
                sensitivities=[self.sensitivity],
            )
            with wave.open(str(path), "rb") as recording:
                if (
                    recording.getcomptype() != "NONE"
                    or recording.getnchannels() != 1
                    or recording.getsampwidth() != 2
                    or recording.getframerate() != detector.sample_rate
                ):
                    raise ValueError(
                        f"WAV must be mono, 16-bit PCM at {detector.sample_rate} Hz."
                    )
                frame_length = int(detector.frame_length)
                max_frames = int(detector.sample_rate * self.MAX_DURATION_SECONDS / frame_length)
                processed = 0
                while processed < max_frames:
                    pcm = recording.readframes(frame_length)
                    if len(pcm) != frame_length * 2:
                        break
                    frame = [
                        int.from_bytes(pcm[index:index + 2], "little", signed=True)
                        for index in range(0, len(pcm), 2)
                    ]
                    if detector.process(frame) >= 0:
                        return {"success": True, "detected": True}
                    processed += 1
                return {"success": True, "detected": False}
        finally:
            if detector is not None:
                detector.delete()
