# Third-party notices

## pypdf (PDF text extraction)

- Project: https://github.com/py-pdf/pypdf
- License: BSD-3-Clause
- Use in Lumira: `DocumentIngestionService` uses the public `PdfReader` API for bounded PDF text extraction. Lumira does not vendor or copy the upstream implementation.
- Version declared by Lumira: `5.4.0`

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

## Nanobot (adapted context-budget algorithm)

- Project: https://github.com/HKUDS/nanobot
- Revision inspected: `cdaae66c894b3364fc4aeed21072b37e913ee917`
- License: MIT
- Copyright: Copyright (c) 2025-present Xubin Ren and the nanobot contributors
- Use in Lumira: `ContextBudgetService` adapts the conservative UTF-8 byte-based message token-estimation and bounded-history selection approach from Nanobot's `nanobot/utils/helpers.py`. Lumira uses its own implementation and provider interfaces; Nanobot's agent runtime is not imported.
- Modification: adapted to Lumira's provider history format and limits; newest valid user/assistant messages are retained in chronological order under message, character, and estimated-token budgets.
- The MIT license permits use and modification subject to retaining the copyright and permission notice. Full upstream license: https://github.com/HKUDS/nanobot/blob/main/LICENSE

Full MIT license notice for the adapted Nanobot algorithm:

```text
MIT License

Copyright (c) 2025-present Xubin Ren and the nanobot contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
