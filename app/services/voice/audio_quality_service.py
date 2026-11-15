"""Bounded WAV quality analysis for voice capture diagnostics.

The analyzer is dependency-free, read-only and does not retain audio samples.
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
import math
import struct
import wave


class AudioQualityService:
    MAX_INPUT_BYTES = 25_000_000
    MAX_DURATION_SECONDS = 2 * 60 * 60
    MAX_SAMPLE_RATE = 96_000
    WINDOW_SECONDS = 0.25

    def analyze_path(self, path: str | Path) -> dict:
        source = Path(path)
        try:
            size = source.stat().st_size
        except OSError:
            return self._failure("audio_unavailable")
        if size <= 0 or size > self.MAX_INPUT_BYTES:
            return self._failure("audio_size_invalid")
        try:
            with source.open("rb") as handle:
                return self.analyze_stream(handle)
        except OSError:
            return self._failure("audio_unavailable")

    def analyze_bytes(self, payload: bytes) -> dict:
        if not isinstance(payload, bytes) or not payload or len(payload) > self.MAX_INPUT_BYTES:
            return self._failure("audio_size_invalid")
        from io import BytesIO
        return self.analyze_stream(BytesIO(payload))

    @staticmethod
    def _failure(code: str) -> dict:
        return {"success": False, "code": code, "analysis": None}

    @staticmethod
    def _decode_samples(raw: bytes, width: int) -> list[int]:
        if width == 1:
            return [(sample - 128) << 8 for sample in raw]
        if width == 2:
            count = len(raw) // 2
            return list(struct.unpack("<" + "h" * count, raw[:count * 2])) if count else []
        if width == 3:
            usable = len(raw) - (len(raw) % 3)
            values = []
            for index in range(0, usable, 3):
                value = raw[index] | (raw[index + 1] << 8) | (raw[index + 2] << 16)
                if value & 0x800000:
                    value -= 1 << 24
                values.append(value >> 8)
            return values
        if width == 4:
            count = len(raw) // 4
            unpacked = struct.unpack("<" + "i" * count, raw[:count * 4]) if count else ()
            return [value >> 16 for value in unpacked]
        raise ValueError("unsupported_sample_width")

    def analyze_stream(self, stream: BinaryIO) -> dict:
        try:
            with wave.open(stream, "rb") as audio:
                channels = audio.getnchannels()
                sample_rate = audio.getframerate()
                width = audio.getsampwidth()
                frames = audio.getnframes()
                compression = audio.getcomptype()
                if compression != "NONE":
                    return self._failure("compressed_wav_unsupported")
                if channels not in {1, 2} or sample_rate < 8_000 or sample_rate > self.MAX_SAMPLE_RATE:
                    return self._failure("audio_format_unsupported")
                if width not in {1, 2, 3, 4}:
                    return self._failure("audio_sample_width_unsupported")
                duration = frames / sample_rate if sample_rate else 0
                if frames <= 0 or duration > self.MAX_DURATION_SECONDS:
                    return self._failure("audio_duration_invalid")

                window_frames = max(1, int(sample_rate * self.WINDOW_SECONDS))
                peak = 0
                square_sum = 0
                sample_count = 0
                clipped = 0
                silent_windows = 0
                total_windows = 0
                while True:
                    raw = audio.readframes(window_frames)
                    if not raw:
                        break
                    samples = self._decode_samples(raw, width)
                    if not samples:
                        continue
                    local_peak = max(abs(value) for value in samples)
                    local_squares = sum(value * value for value in samples)
                    peak = max(peak, local_peak)
                    square_sum += local_squares
                    sample_count += len(samples)
                    full_scale = 32768 if width in {1, 2} else (1 << (8 * width - 1)) >> (8 * width - 16)
                    clipped += sum(1 for value in samples if abs(value) >= int(full_scale * 0.999))
                    total_windows += 1
                    local_rms = math.sqrt(local_squares / len(samples))
                    if local_rms < 80:
                        silent_windows += 1

                if sample_count == 0:
                    return self._failure("audio_has_no_samples")
                rms = math.sqrt(square_sum / sample_count)
                peak_dbfs = 20 * math.log10(max(peak / 32768, 1e-9))
                rms_dbfs = 20 * math.log10(max(rms / 32768, 1e-9))
                silence_ratio = silent_windows / max(total_windows, 1)
                clipping_ratio = clipped / sample_count
                warnings = []
                if silence_ratio >= 0.8:
                    warnings.append("mostly_silent")
                if clipping_ratio >= 0.01:
                    warnings.append("clipping_detected")
                if rms_dbfs < -45:
                    warnings.append("very_low_level")
                return {
                    "success": True,
                    "code": "analyzed",
                    "analysis": {
                        "format": "wav_pcm",
                        "channels": channels,
                        "sample_rate_hz": sample_rate,
                        "sample_width_bytes": width,
                        "duration_seconds": round(duration, 3),
                        "peak_dbfs": round(peak_dbfs, 2),
                        "rms_dbfs": round(rms_dbfs, 2),
                        "silence_ratio": round(silence_ratio, 4),
                        "clipping_ratio": round(clipping_ratio, 6),
                        "warnings": warnings,
                        "retained_audio": False,
                    },
                }
        except (wave.Error, EOFError, OSError, struct.error, ValueError, OverflowError):
            return self._failure("invalid_or_unsupported_wav")


class VoiceActivityDetector:
    """Energy-based speech-region detector for bounded PCM WAV recordings.

    This is a lightweight local pre-segmentation aid, not a speech recognizer.
    It deliberately returns timestamps only and never writes or uploads audio.
    """

    MAX_INPUT_BYTES = AudioQualityService.MAX_INPUT_BYTES
    MAX_DURATION_SECONDS = AudioQualityService.MAX_DURATION_SECONDS

    def __init__(
        self,
        frame_ms: int = 30,
        minimum_speech_ms: int = 180,
        merge_silence_ms: int = 240,
        energy_floor: float = 0.003,
    ):
        if not 10 <= frame_ms <= 100:
            raise ValueError("frame_ms must be between 10 and 100")
        if not 50 <= minimum_speech_ms <= 5000:
            raise ValueError("minimum_speech_ms must be between 50 and 5000")
        if not 0 <= merge_silence_ms <= 2000:
            raise ValueError("merge_silence_ms must be between 0 and 2000")
        if not 0.0001 <= energy_floor <= 0.2:
            raise ValueError("energy_floor must be between 0.0001 and 0.2")
        self.frame_ms = frame_ms
        self.minimum_speech_ms = minimum_speech_ms
        self.merge_silence_ms = merge_silence_ms
        self.energy_floor = energy_floor

    def detect_path(self, path: str | Path) -> dict:
        source = Path(path)
        try:
            if source.stat().st_size > self.MAX_INPUT_BYTES:
                return {"success": False, "code": "audio_size_invalid", "segments": []}
            with source.open("rb") as handle:
                return self.detect_stream(handle)
        except OSError:
            return {"success": False, "code": "audio_unavailable", "segments": []}

    def detect_stream(self, stream: BinaryIO) -> dict:
        try:
            with wave.open(stream, "rb") as audio:
                channels = audio.getnchannels()
                rate = audio.getframerate()
                width = audio.getsampwidth()
                frames = audio.getnframes()
                duration = frames / rate if rate else 0
                if channels not in {1, 2} or not 8_000 <= rate <= 48_000 or width not in {1, 2, 3, 4}:
                    return {"success": False, "code": "audio_format_unsupported", "segments": []}
                if frames <= 0 or duration > self.MAX_DURATION_SECONDS:
                    return {"success": False, "code": "audio_duration_invalid", "segments": []}

                frame_count = max(1, round(rate * self.frame_ms / 1000))
                energy_frames: list[tuple[float, float, float]] = []
                cursor = 0
                while True:
                    raw = audio.readframes(frame_count)
                    if not raw:
                        break
                    samples = AudioQualityService._decode_samples(raw, width)
                    if not samples:
                        continue
                    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
                    start = cursor / rate
                    cursor += len(samples) // channels
                    end = cursor / rate
                    energy_frames.append((rms, start, end))

                if not energy_frames:
                    return {"success": False, "code": "audio_has_no_samples", "segments": []}

                peak_energy = max(item[0] for item in energy_frames)
                threshold = max(self.energy_floor, min(0.08, peak_energy * 0.12))
                raw_segments = []
                active_start = None
                last_active_end = None
                for energy, start, end in energy_frames:
                    if energy >= threshold:
                        if active_start is None:
                            active_start = start
                        last_active_end = end
                    elif active_start is not None and last_active_end is not None:
                        if start - last_active_end > self.merge_silence_ms / 1000:
                            raw_segments.append((active_start, last_active_end))
                            active_start = None
                            last_active_end = None
                if active_start is not None and last_active_end is not None:
                    raw_segments.append((active_start, last_active_end))

                minimum = self.minimum_speech_ms / 1000
                segments = [
                    {"start_seconds": round(start, 3), "end_seconds": round(end, 3)}
                    for start, end in raw_segments if end - start >= minimum
                ]
                return {
                    "success": True,
                    "code": "speech_regions_detected" if segments else "no_speech_detected",
                    "threshold_rms": round(threshold, 6),
                    "segments": segments,
                    "duration_seconds": round(duration, 3),
                    "method": "pcm_energy_vad",
                    "transcription_performed": False,
                }
        except (wave.Error, EOFError, OSError, ValueError, struct.error, OverflowError):
            return {"success": False, "code": "invalid_or_unsupported_wav", "segments": []}
