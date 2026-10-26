# Third-party notices

## faster-whisper (optional local speech-to-text)

- Project: https://github.com/SYSTRAN/faster-whisper
- License: MIT
- Copyright: Copyright (c) 2023 SYSTRAN
- Use in Lumira: optional runtime dependency used by `FasterWhisperTranscriptionProvider` through its public `WhisperModel` API. Lumira does not vendor or copy the upstream implementation source.
- Installation is optional; the standard `requirements.txt` remains unchanged.

The MIT license permits use, copying, modification, distribution, sublicensing, and sale, provided the copyright and permission notice are included in copies or substantial portions of the software. The upstream software is provided without warranty. Read the full license in the upstream repository before redistributing packaged builds: https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE


## Ollama (optional local image understanding and summarization runtime)

- Project: https://github.com/ollama/ollama
- License: MIT
- Copyright: Copyright (c) Ollama
- Use in Lumira: the optional `OllamaVisionProvider` calls the local Ollama HTTP API; Lumira does not vendor or copy the Ollama server implementation.
- Runtime and model weights are installed separately by the user. Individual model licenses and terms may differ; review the chosen model's license before use or redistribution.

The Ollama project license is available at https://github.com/ollama/ollama/blob/main/LICENSE
