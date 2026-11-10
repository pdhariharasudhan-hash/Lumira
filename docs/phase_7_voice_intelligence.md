# Phase 7 — Voice Intelligence

**Implementation status:** Desktop capture, stored-audio workflow, transcription/speech adapters and wake-word listener code exist; hardware/provider acceptance is blocked.
**Release status:** NOT ACCEPTED.

## Verified in this session — 2026-11-06
- Windows reports an audio input endpoint (`Microphone Array`) and output endpoint (`Speaker (Realtek(R) Audio)`). Device enumeration is not proof of recording/playback quality or application permission.
- Desktop MainLayout tests include microphone recording flow, explicit wake-word start/stop, and saved voice pipeline integration.
- Focused backend tests cover voice idea pipeline/recovery, route readiness, transcription, speech synthesis, audio playback and wake-word listener behavior.
- `faster-whisper` Python module is installed.
- Backend Phase 6–8 focused matrix: **104 passed, 0 failed**; desktop focused suite: **32 passed, 0 failed**.

## Remaining blockers
- No actual microphone recording or speaker playback was performed during this remote verification.
- Local transcription is not enabled in the inspected process environment; no live transcription was run.
- Picovoice dependencies (`pvporcupine`, `pvrecorder`) are absent, and wake-word access key/model path are not configured. Always-listening wake-word activation is therefore unavailable.
- Tamil, English and mixed Tamil-English semantic quality needs real recordings and human acceptance, not mocked browser tests.
- TTS provider is not configured; synthesized voice output is not live-verified.

## Acceptance required
1. Start Lumira on the laptop and grant microphone permission.
2. Record a short Tamil, English and mixed-language clip; verify audio artifact integrity and playback.
3. Enable a local transcription provider with an available model, then verify transcripts and summaries.
4. Configure a supported wake-word engine and its model/dependencies before claiming wake-word support is active.
5. Configure speech synthesis if voice responses are required, then test playback and interruption.

No microphone listener was started and no recording was made during this session.


## 2026-11-10 — Live local voice acceptance and decoder compatibility

- Confirmed `faster-whisper` 1.2.1 was installed, but its decoder passed `metadata_errors` to the installed PyAV 19.0.2 build, whose `av.open()` rejected that keyword. Local transcription therefore failed before inference.
- Implemented a compatibility decoder using PyAV's supported `av.open()` API, resampling supported audio streams to mono 16 kHz float32 and passing the waveform to Faster-Whisper. This preserves local-only processing and supports the audio formats decoded by the installed PyAV/FFmpeg build.
- Added a configurable `LUMIRA_LOCAL_TRANSCRIPTION_INITIAL_PROMPT` (default `Lumira`) to improve recognition of Lumira-specific vocabulary.
- Added decoder and waveform-contract tests: **2 passed**. Live Faster-Whisper tiny-model transcription of a Windows SAPI-generated acceptance WAV correctly returned: “Lumira is ready to capture a new idea. The next task is to build the voice recording system.”
- Ran the full voice idea pipeline with real local Faster-Whisper transcription and real Ollama summarization. Audio and transcript artifacts were created, summary generation completed, and the cognitive-memory experience linked the audio/transcript/summary artifacts successfully.
- This acceptance used a generated test WAV, not a physical microphone. Microphone capture, speaker playback, Tamil speech accuracy, wake-word activation and TTS remain unaccepted.


## 2026-11-10 — Local Windows speech synthesis

- Added `WindowsSapiSpeechProvider`, a local Windows text-to-speech adapter using the built-in `System.Speech` voices through PowerShell. It requires no cloud key, network call, or additional Python package.
- The provider validates bounded input, language, process timeout, WAV header and output size; it passes text/path through a base64-encoded process environment payload, sanitizes process failures, and removes temporary files.
- Startup registration is explicit via `LUMIRA_WINDOWS_SAPI_TTS_ENABLED`; packaged Electron launches enable this local provider by default. Health diagnostics identify it as local and do not claim reachability.
- The installed Windows host exposes English voices (Microsoft David and Zira) but no Tamil SAPI voice. This provider therefore advertises English only; Tamil/mixed speech requires a separately installed Tamil voice or configured compatible provider.
- Focused provider, registration, creator-audio, speech-provider and health suite: **20 passed**. Live `CreatorOSService.synthesize_audio()` generated a real 6.69-second mono 22.05 kHz WAV and persisted a checksum-verified audio artifact.
- This verifies local speech generation and artifact storage, not physical speaker playback or Tamil TTS quality.
