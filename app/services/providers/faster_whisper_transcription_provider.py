"""Optional local speech-to-text provider powered by the MIT-licensed faster-whisper project.

The model is loaded lazily on the first transcription request. CPU + int8 is
chosen by default for low-memory laptops; no microphone is opened by this class.
"""
from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any

from app.services.resources.resource_budget_service import ResourceBudgetService


class FasterWhisperTranscriptionProvider:

    """Transcribe supported audio locally; never send recordings to a remote API."""

    provider_scope = "local"
    MAX_AUDIO_BYTES = 25_000_000
    MAX_TRANSCRIPT_CHARS = 100_000
    # faster-whisper/AV can decode the same formats accepted by Lumira's audio store.
    SUPPORTED_EXTENSIONS = {"wav", "mp3", "m4a", "ogg", "webm"}
    _model_cache: dict[tuple[str, str, str], Any] = {}
    _model_lock = Lock()
    _inference_lock = Lock()

    def __init__(self) -> None:
        self.model_name = os.getenv("LUMIRA_LOCAL_TRANSCRIPTION_MODEL", "base").strip()
        self.model_path = os.getenv("LUMIRA_LOCAL_TRANSCRIPTION_MODEL_PATH", "").strip()
        self.compute_type = os.getenv("LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE", "int8").strip()
        self.cpu_threads = self._bounded_int(os.getenv("LUMIRA_LOCAL_TRANSCRIPTION_CPU_THREADS", "2"), 1, 8)
        self.download_root = os.getenv("LUMIRA_LOCAL_TRANSCRIPTION_MODEL_CACHE", "").strip() or None
        if not self.model_name or len(self.model_name) > 160:
            raise ValueError("Local transcription model name is invalid.")
        if self.compute_type not in {"int8", "int8_float32", "float32"}:
            raise ValueError("Local transcription compute type must be int8, int8_float32, or float32.")

    @staticmethod
    def _bounded_int(raw: str, minimum: int, maximum: int) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = minimum
        return max(minimum, min(value, maximum))

    def _load_model(self) -> Any:
        model_ref = self.model_path or self.model_name
        key = (model_ref, self.compute_type, str(self.cpu_threads))
        with self._model_lock:
            cached = self._model_cache.get(key)
            if cached is not None:
                return cached
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError(
                    "Local transcription is enabled but faster-whisper is not installed. "
                    "Install it with: python -m pip install faster-whisper"
                ) from None
            try:
                options: dict[str, Any] = {
                    "device": "cpu",
                    "compute_type": self.compute_type,
                    "cpu_threads": self.cpu_threads,
                }
                if self.download_root:
                    options["download_root"] = self.download_root
                model = WhisperModel(model_ref, **options)
            except Exception:
                raise RuntimeError(
                    "The local speech model could not be loaded. Check the model name/path, "
                    "available disk space, and first-run model download access."
                ) from None
            self._model_cache[key] = model
            return model

    @staticmethod
    def _decode_audio_compat(path: Path):
        """Decode through PyAV without the metadata_errors kwarg removed by some PyAV builds.

        faster-whisper 1.2.x currently passes metadata_errors to av.open(). Some
        installed PyAV builds reject that keyword. Passing a decoded float32
        waveform to WhisperModel.transcribe() avoids that incompatible call
        while retaining PyAV's bundled FFmpeg support for stored audio formats.
        """
        import av
        import numpy as np

        resampler = av.audio.resampler.AudioResampler(
            format="s16",
            layout="mono",
            rate=16000,
        )
        chunks = []
        with av.open(str(path), mode="r") as container:
            audio_streams = container.streams.audio
            if not audio_streams:
                raise ValueError("Audio file contains no audio stream.")
            for frame in container.decode(audio=audio_streams[0].index):
                for converted in resampler.resample(frame):
                    chunks.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                chunks.append(converted.to_ndarray().reshape(-1))
        if not chunks:
            raise ValueError("Audio file contains no decodable audio frames.")
        waveform = np.concatenate(chunks).astype(np.float32)
        return waveform / 32768.0

    def transcribe(self, audio_path: str) -> str:
        path = Path(audio_path)
        extension = path.suffix.removeprefix(".").lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError("Audio format is not supported for local transcription.")
        if not path.is_file():
            raise ValueError("Audio file does not exist.")
        try:
            size = path.stat().st_size
        except OSError:
            raise ValueError("Audio file cannot be read.") from None
        if size <= 0 or size > self.MAX_AUDIO_BYTES:
            raise ValueError("Audio file is empty or exceeds the local transcription size limit.")

        guidance = ResourceBudgetService().execution_guidance()
        if guidance.get("defer_optional_heavy_media_work") is True:
            raise RuntimeError("Local transcription was deferred because available system memory is constrained.")

        if not self._inference_lock.acquire(timeout=1):
            raise RuntimeError("Local transcription was deferred because another local model request is active.")
        try:
            model = self._load_model()
            try:
                waveform = self._decode_audio_compat(path)
                initial_prompt = os.getenv(
                    "LUMIRA_LOCAL_TRANSCRIPTION_INITIAL_PROMPT",
                    "Lumira",
                ).strip()[:500]
                segments, _info = model.transcribe(
                    waveform,
                    beam_size=1,
                    vad_filter=True,
                    condition_on_previous_text=False,
                    initial_prompt=initial_prompt or None,
                )
                pieces: list[str] = []
                total_chars = 0
                for segment in segments:
                    piece = segment.text.strip()
                    if not piece:
                        continue
                    total_chars += len(piece) + (1 if pieces else 0)
                    if total_chars > self.MAX_TRANSCRIPT_CHARS:
                        raise ValueError("Local transcription output exceeds the transcript size limit.")
                    pieces.append(piece)
                transcript = " ".join(pieces).strip()
            except ValueError:
                raise
            except Exception:
                raise RuntimeError("The local transcription model failed to process this audio.") from None
        finally:
            self._inference_lock.release()
        if not transcript:
            raise ValueError("The local transcription model returned no speech.")
        return transcript
