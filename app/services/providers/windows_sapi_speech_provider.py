"""Local Windows text-to-speech using the built-in System.Speech SAPI voices.

No API key, network request, or third-party Python package is required. The
provider only reports success when a supported installed voice produces a
valid bounded WAV artifact.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

class WindowsSapiSpeechProvider:
    provider_scope = "local"
    MAX_INPUT_CHARS = 20_000
    MAX_AUDIO_BYTES = 25_000_000
    SUPPORTED_LANGUAGES = {"en"}
    DEFAULT_TIMEOUT_SECONDS = 60

    _POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$synth = $null
try {
    $payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:LUMIRA_SAPI_PAYLOAD)) | ConvertFrom-Json
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voice = $synth.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } |
        Select-Object -First 1
    if (-not $voice) { throw 'NO_SUPPORTED_ENGLISH_VOICE' }
    $synth.SelectVoice($voice.VoiceInfo.Name)
    $synth.SetOutputToWaveFile($payload.output_path)
    $synth.Speak($payload.text)
    $synth.SetOutputToNull()
    [Console]::Out.WriteLine('LUMIRA_SAPI_OK')
} catch {
    [Console]::Error.WriteLine('LUMIRA_SAPI_FAILED')
    exit 2
} finally {
    if ($null -ne $synth) { $synth.Dispose() }
}
"""

    def __init__(self, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows SAPI speech synthesis is available only on Windows.")
        self.timeout = max(5, min(int(timeout), 120))
        self.powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not self.powershell:
            raise RuntimeError("Windows PowerShell is unavailable.")

    def synthesize(self, text: str, language: str) -> dict:
        if not isinstance(text, str) or not text.strip() or len(text) > self.MAX_INPUT_CHARS:
            raise ValueError("Speech text is empty or exceeds the synthesis input limit.")
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError("This Windows SAPI installation supports English synthesis only.")
        # Windows SAPI is an OS voice engine, not a resident ML model. Keep
        # it available under low-memory profiles; bounded text/output and a
        # strict subprocess timeout constrain its resource use.
        output_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="lumira_sapi_", suffix=".wav", delete=False) as handle:
                output_path = Path(handle.name)
            payload = json.dumps({"text": text.strip(), "output_path": str(output_path)})
            encoded_payload = base64.b64encode(payload.encode("utf-8")).decode("ascii")
            encoded_script = base64.b64encode(self._POWERSHELL_SCRIPT.encode("utf-16le")).decode("ascii")
            environment = os.environ.copy()
            environment["LUMIRA_SAPI_PAYLOAD"] = encoded_payload
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                result = subprocess.run(
                    [
                        self.powershell,
                        "-NoLogo",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-EncodedCommand",
                        encoded_script,
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                    creationflags=creation_flags,
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("Windows speech synthesis timed out.") from None
            except OSError:
                raise RuntimeError("Windows speech synthesis could not start.") from None
            if result.returncode != 0 or not output_path.is_file():
                raise RuntimeError("Windows speech synthesis failed; verify an English SAPI voice is installed.")
            size = output_path.stat().st_size
            if size < 44 or size > self.MAX_AUDIO_BYTES:
                raise ValueError("Synthesized audio is empty or exceeds the audio size limit.")
            content = output_path.read_bytes()
            if content[:4] != b"RIFF" or content[8:12] != b"WAVE":
                raise ValueError("Windows speech synthesis returned an invalid WAV stream.")
            return {"success": True, "content": content, "extension": "wav", "voice_engine": "Windows SAPI"}
        finally:
            if output_path is not None:
                output_path.unlink(missing_ok=True)
